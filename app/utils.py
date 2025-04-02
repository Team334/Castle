import asyncio
import contextlib
import logging
import os
import time
from functools import wraps
from io import BytesIO
from urllib.parse import urljoin, urlparse

from bson import ObjectId
from dotenv import load_dotenv
from flask import flash, jsonify, render_template, request, send_file, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from gridfs import GridFS
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# File handling constants
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

load_dotenv()

# ============ Database Utilities ============

# Global connection pool singleton
_GLOBAL_DB_CONNECTION = {
    'client': None,
    'db': None,
    'last_used': None,
    'connection_timeout': 120,  # 5 minutes timeout
    'count': 0  # Reference counter
}

def get_database_connection(mongo_uri):
    """
    Get or create a global database connection
    
    Args:
        mongo_uri: MongoDB connection URI
        
    Returns:
        dict with client and db objects
    """
    global _GLOBAL_DB_CONNECTION
    
    # Mark this request as having accessed the database
    mark_db_accessed()
    
    current_time = time.time()
    
    # If we already have a connection that's in use, return it without incrementing the counter
    if (_GLOBAL_DB_CONNECTION['client'] is not None and 
        _GLOBAL_DB_CONNECTION['last_used'] is not None and 
        (current_time - _GLOBAL_DB_CONNECTION['last_used']) <= _GLOBAL_DB_CONNECTION['connection_timeout']):
        
        # Test if the connection is still valid before returning it
        try:
            _GLOBAL_DB_CONNECTION['client'].admin.command('ismaster')
            _GLOBAL_DB_CONNECTION['last_used'] = current_time
            logger.debug("Reusing existing MongoDB connection")
            
            # Only increment the reference counter for new owners
            _GLOBAL_DB_CONNECTION['count'] += 1
            logger.info(f"MongoDB connection reference count increased to: {_GLOBAL_DB_CONNECTION['count']}")
            
            return {
                'client': _GLOBAL_DB_CONNECTION['client'], 
                'db': _GLOBAL_DB_CONNECTION['db']
            }
        except Exception as e:
            logger.warning(f"Existing connection test failed: {str(e)}. Will create new connection.")
    
    # If we get here, we need to create a new connection
    # Close the existing connection if there is one
    if _GLOBAL_DB_CONNECTION['client'] is not None:
        try:
            _GLOBAL_DB_CONNECTION['client'].close()
            logger.info("Closed stale MongoDB connection")
        except Exception as e:
            logger.warning(f"Error closing MongoDB connection: {str(e)}")
    
    # Create a new connection
    try:
        client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=10000,
            maxPoolSize=10,
            minPoolSize=1,
            connectTimeoutMS=5000,
            socketTimeoutMS=30000,
            waitQueueTimeoutMS=10000
        )
        # Test the connection
        client.server_info()
        db = client.get_default_database()
        
        _GLOBAL_DB_CONNECTION['client'] = client
        _GLOBAL_DB_CONNECTION['db'] = db
        _GLOBAL_DB_CONNECTION['last_used'] = current_time
        _GLOBAL_DB_CONNECTION['count'] = 1  # Start with 1 since we're returning it
        
        logger.info("Created new MongoDB connection")
        logger.info(f"MongoDB connection reference count increased to: 1")
        
        return {
            'client': _GLOBAL_DB_CONNECTION['client'], 
            'db': _GLOBAL_DB_CONNECTION['db']
        }
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise

def release_connection():
    """
    Release a reference to the global connection.
    When count reaches 0, the connection remains but is marked as unused.
    """
    global _GLOBAL_DB_CONNECTION
    
    if _GLOBAL_DB_CONNECTION['count'] > 0:
        _GLOBAL_DB_CONNECTION['count'] -= 1
        logger.info(f"MongoDB connection reference count decreased to: {_GLOBAL_DB_CONNECTION['count']}")
    
    # Update last_used time
    _GLOBAL_DB_CONNECTION['last_used'] = time.time()

def force_close_connection():
    """
    Force close the global connection regardless of reference count.
    Should only be used during application shutdown.
    """
    global _GLOBAL_DB_CONNECTION
    
    try:
        if _GLOBAL_DB_CONNECTION['client'] is not None:
            _GLOBAL_DB_CONNECTION['client'].close()
            logger.info("Forced close of MongoDB connection")
    except Exception as e:
        logger.error(f"Error force closing MongoDB connection: {str(e)}")
    
    # Reset all connection values
    _GLOBAL_DB_CONNECTION['client'] = None
    _GLOBAL_DB_CONNECTION['db'] = None
    _GLOBAL_DB_CONNECTION['count'] = 0
    _GLOBAL_DB_CONNECTION['last_used'] = None

def with_mongodb_retry(retries=3, delay=2):
    """Decorator for retrying MongoDB operations"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(retries):
                try:
                    return f(*args, **kwargs)
                except (ServerSelectionTimeoutError, ConnectionFailure) as e:
                    last_error = e
                    if attempt < retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                        time.sleep(delay)
                    else:
                        logger.error(f"All {retries} attempts failed: {str(e)}")
            raise last_error
        return wrapper
    return decorator

class DatabaseManager:
    """Base class for database operations"""
    def __init__(self, mongo_uri: str, existing_connection=None):
        self.mongo_uri = mongo_uri
        self.client = None
        self.db = None
        self.owns_connection = False
        
        # Use existing connection if provided, otherwise get from global pool
        if (existing_connection and 
            existing_connection.get('client') is not None and 
            existing_connection.get('db') is not None):
            # We're reusing an existing connection, don't increment the counter
            self.client = existing_connection['client']
            self.db = existing_connection['db']
            logger.info("Using existing MongoDB connection")
            # This instance doesn't "own" the connection (won't decrement on close)
            self.owns_connection = False
        else:
            # Get a new connection from the pool, counter already incremented
            conn = get_database_connection(self.mongo_uri)
            self.client = conn['client']
            self.db = conn['db']
            # This instance "owns" a reference and will decrement on close
            self.owns_connection = True
            logger.info("Using global MongoDB connection")

    def connect(self):
        """Ensure connection to MongoDB"""
        conn = get_database_connection(self.mongo_uri)
        self.client = conn['client']
        self.db = conn['db']

    def ensure_connected(self):
        """Ensure database connection is active"""
        try:
            # Mark this request as having accessed the database
            mark_db_accessed()

            # Check if client is None first
            if self.client is None or self.db is None:
                logger.warning("No active MongoDB connection. Connecting...")
                self.connect()
                return
                
            # Test if connection is still alive with a lightweight command
            self.client.admin.command('ismaster')
        except Exception as e:
            logger.warning(f"Lost connection to MongoDB: {str(e)}. Attempting to reconnect...")
            self.connect()

    def close(self):
        """Release the MongoDB connection reference"""
        if self.owns_connection:
            release_connection()
            self.client = None
            self.db = None
            logger.info("Released MongoDB connection reference")

    def get_connection(self):
        """Return the current connection for reuse"""
        self.ensure_connected()
        return {'client': self.client, 'db': self.db}

    def __del__(self):
        """Cleanup MongoDB connection reference on object deletion"""
        with contextlib.suppress(ImportError, AttributeError, TypeError):
            self.close()

def mark_db_accessed():
    """Mark the current request as having accessed the database"""
    try:
        if hasattr(g, '_get_current_object'):
            g.db_accessed = True
    except (RuntimeError, ImportError):
        # Handle case when not in a Flask context
        pass

# ============ Route Utilities ============

def async_route(f):
    """Decorator to handle async routes"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper

def handle_route_errors(f):
    """Decorator to handle common route errors"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Route error: {str(e)}", exc_info=True)
            flash("An internal error has occurred.", "error")
            return render_template("500.html"), 500
    return wrapper

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("MONGO_URI"),
    default_limits=["5000 per day", "1000 per hour"],
    strategy="fixed-window-elastic-expiry"
)


# ============ File Handling Utilities ============

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file_to_gridfs(file, db, prefix: str = '') -> str:
    """Save file to GridFS and return file ID"""
    if file and allowed_file(file.filename):
        fs = GridFS(db)
        filename = secure_filename(f"{prefix}_{file.filename}" if prefix else file.filename)
        file_id = fs.put(
            file.stream.read(),
            filename=filename,
            content_type=file.content_type
        )
        return str(file_id)
    return None

def send_gridfs_file(file_id, db, default_path: str = None):
    """Send file from GridFS or return default file"""
    try:
        fs = GridFS(db)
        if isinstance(file_id, str):
            file_id = ObjectId(file_id)
        file_data = fs.get(file_id)
        return send_file(
            BytesIO(file_data.read()),
            mimetype=file_data.content_type,
            download_name=file_data.filename
        )
    except Exception as e:
        logger.error(f"Error retrieving file: {str(e)}")
        if default_path:
            return send_file(default_path)
        return error_response("An internal error has occurred.", 500)

# ============ Response Utilities ============

def success_response(message: str = "Success", data: dict = None, status_code: int = 200):
    """Standard success response"""
    response = {
        "success": True,
        "message": message
    }
    if data is not None:
        response["data"] = data
    return jsonify(response), status_code

def error_response(message: str = "Error", status_code: int = 400, log_message: str = None):
    """Standard error response"""
    if log_message:
        logger.error(log_message)
    return jsonify({
        "success": False,
        "message": message
    }), status_code

# ============ Security Utilities ============

def is_safe_url(target: str) -> bool:
    """Verify URL is safe for redirects"""
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

async def check_password_strength(password: str) -> tuple[bool, str]:
    """
    Check if password meets minimum requirements:
    - At least 8 characters
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    return True, "Password meets all requirements" 