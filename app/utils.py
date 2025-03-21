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
from flask import flash, jsonify, render_template, request, send_file
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
        self.last_used = time.time()
        self.connection_timeout = 300  # 5 minutes by default
        
        # Use existing connection if provided
        if existing_connection and existing_connection.get('client') and existing_connection.get('db'):
            self.client = existing_connection['client']
            self.db = existing_connection['db']
            logger.info("Using existing MongoDB connection")
        else:
            self.connect()

    def connect(self):
        """Establish connection to MongoDB"""
        try:
            if self.client is None:
                # Add maxPoolSize and minPoolSize to reduce threads
                # Also increase serverSelectionTimeoutMS to avoid rapid reconnects
                self.client = MongoClient(
                    self.mongo_uri, 
                    serverSelectionTimeoutMS=10000,
                    maxPoolSize=10,        # Limit maximum connections
                    minPoolSize=1,         # Minimum connections to maintain
                    connectTimeoutMS=5000, # Connection timeout
                    socketTimeoutMS=30000, # Socket timeout
                    waitQueueTimeoutMS=10000  # How long to wait in queue
                )
                self.client.server_info()
                self.db = self.client.get_default_database()
                self.last_used = time.time()
                logger.info("Successfully connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    def ensure_connected(self):
        """Ensure database connection is active and not timed out"""
        try:
            current_time = time.time()
            
            # If client is None, connect
            if self.client is None:
                logger.info("No MongoDB connection. Connecting...")
                self.connect()
                return
            
            # Check if connection has timed out
            if (current_time - self.last_used) > self.connection_timeout:
                logger.info("Connection timed out. Reconnecting...")
                self.close()
                self.connect()
                return
            
            # Test if connection is still alive with a lightweight command
            self.client.admin.command('ismaster')
            self.last_used = current_time  # Update last used time
        except Exception as e:
            logger.warning(f"Lost connection to MongoDB: {str(e)}. Attempting to reconnect...")
            self.close()
            self.connect()

    def close(self):
        """Explicitly close the MongoDB connection"""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MongoDB connection closed")

    def get_connection(self):
        """Return the current connection for reuse"""
        try:
            if self.client is None:
                self.connect()
            else:
                # Test if the connection is still valid
                self.client.server_info()
        except Exception:
            # Reconnect if there was an error
            logger.warning("Connection invalid in get_connection. Reconnecting...")
            self.close()
            self.connect()
            
        self.last_used = time.time()  # Update last used time
        return {'client': self.client, 'db': self.db}

    def __del__(self):
        """Cleanup MongoDB connection on object deletion"""
        with contextlib.suppress(ImportError, AttributeError, TypeError):
            self.close()

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