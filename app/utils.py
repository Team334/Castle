import asyncio
import contextlib
import logging
import os
import smtplib
import ssl
import time
from email.message import EmailMessage
from functools import wraps
from io import BytesIO
from urllib.parse import urljoin, urlparse

from bson import ObjectId
from dotenv import load_dotenv
from flask import flash, jsonify, render_template, request, send_file, g, current_app, url_for
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

class MongoDB:
    """
    Singleton MongoDB connection manager that maintains exactly one connection
    throughout the application lifecycle.
    """
    # Class variables for the single global connection
    _instance = None
    _client = None
    _db = None
    _initialized = False
    
    def __new__(cls, mongo_uri=None, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MongoDB, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, mongo_uri=None):
        # Only initialize once
        if not MongoDB._initialized:
            self.mongo_uri = mongo_uri or os.getenv("MONGO_URI")
            self._connect()
            MongoDB._initialized = True
    
    def _connect(self):
        """Create the MongoDB connection"""
        try:
            logger.info("Creating new MongoDB connection")
            self._client = MongoClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=30000,  # Increased from 10000
                maxPoolSize=50,                  # Increased from 10
                minPoolSize=5,                   # Increased from 1
                connectTimeoutMS=10000,          # Increased from 5000
                socketTimeoutMS=45000,           # Increased from 30000
                waitQueueTimeoutMS=10000,        # Added wait queue timeout
                retryWrites=True,                # Enable retryable writes
                retryReads=True,                 # Enable retryable reads
                heartbeatFrequencyMS=10000,      # Added heartbeat frequency
                maxIdleTimeMS=60000              # Added max idle time
            )
            
            # Test the connection
            self._client.server_info()
            self._db = self._client.get_default_database()
            logger.info("MongoDB connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise
    
    def get_client(self):
        """Get the MongoDB client"""
        try:
            if self._client is None or not self._client.is_primary:
                self._connect()
            return self._client
        except Exception as e:
            logger.error(f"Error getting MongoDB client: {str(e)}")
            self._connect()  # Try to reconnect
            return self._client
    
    def get_db(self):
        """Get the MongoDB database"""
        if self._db is None:
            self._connect()
        return self._db
    
    def close(self):
        """Close the MongoDB connection during application shutdown"""
        if self._client is not None:
            try:
                self._client.close()
                logger.info("Closed MongoDB connection")
            except Exception as e:
                logger.warning(f"Error closing MongoDB connection: {str(e)}")
            finally:
                self._client = None
                self._db = None
                MongoDB._initialized = False

# Global instance
_mongodb_instance = None
fs = None  # Initialize as None, will be set up when needed

def get_mongodb_instance(mongo_uri=None):
    """Get the singleton MongoDB instance"""
    global _mongodb_instance, fs
    if _mongodb_instance is None:
        _mongodb_instance = MongoDB(mongo_uri)
        # Initialize GridFS with the singleton connection
        fs = GridFS(_mongodb_instance.get_db())
    # Mark the database as accessed for the current request
    _mark_db_accessed()
    return _mongodb_instance

def _mark_db_accessed():
    """Mark this request as having accessed the database"""
    try:
        if hasattr(g, '_get_current_object'):
            g.db_accessed = True
    except (RuntimeError, ImportError):
        # Not in a Flask context
        pass

def close_mongodb_connection():
    """Close the MongoDB connection at application shutdown"""
    global _mongodb_instance
    if _mongodb_instance:
        _mongodb_instance.close()
        _mongodb_instance = None

class DBManager:
    """Base database manager that uses the singleton MongoDB connection"""
    
    def __init__(self, mongo_uri=None):
        """Initialize the database manager with the global singleton connection"""
        mongodb = get_mongodb_instance(mongo_uri)
        self.client = mongodb.get_client()
        self.db = mongodb.get_db()

DatabaseManager = DBManager

def get_database_connection(mongo_uri=None):
    """Legacy function for backward compatibility"""
    mongodb = get_mongodb_instance(mongo_uri)
    return {'client': mongodb.get_client(), 'db': mongodb.get_db()}

def release_connection():
    """Legacy function for backward compatibility - now a no-op"""
    pass

def force_close_connection():
    """Legacy function for backward compatibility"""
    close_mongodb_connection()

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

def mark_db_accessed():
    """Mark the current request as having accessed the database"""
    _mark_db_accessed()

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
    default_limits=["50000 per day", "10000 per hour"],
    strategy="moving-window"
)


# ============ File Handling Utilities ============

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file_to_gridfs(file, db, prefix: str = '') -> str:
    """Save file to GridFS and return file ID"""
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{prefix}_{file.filename}" if prefix else file.filename)
        file_id = get_gridfs().put(
            file.stream.read(),
            filename=filename,
            content_type=file.content_type
        )
        return str(file_id)
    return None

def send_gridfs_file(file_id, db, default_path: str = None):
    """Send file from GridFS or return default file"""
    try:
        if isinstance(file_id, str):
            file_id = ObjectId(file_id)
        file_data = get_gridfs().get(file_id)
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

def get_gridfs():
    """Get the GridFS instance"""
    global fs
    if fs is None:
        get_mongodb_instance()  # This will initialize both MongoDB and GridFS
    return fs

# ============ Email Utilities ============

def send_password_reset_email(recipient_email: str, token: str):
    """Sends the password reset email."""
    email_address = current_app.config.get("EMAIL_ADDRESS")
    email_password = current_app.config.get("EMAIL_APP_PASSWORD")

    if not email_address or not email_password:
        logger.error("Email credentials not configured. Cannot send password reset email.")
        return False # Indicate failure but don't raise exception to route

    reset_url = url_for('auth.reset_password', token=token, _external=True)

    subject = "Castle Scouting - Password Reset Request"
    # Enhanced HTML body with basic inline styles
    body = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{subject}</title>
        <style>
            body {{ font-family: sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }}
            .button {{ display: inline-block; padding: 10px 20px; margin: 15px 0; background-color: #007bff; color: #ffffff; text-decoration: none; border-radius: 5px; }}
            .footer {{ margin-top: 20px; font-size: 0.9em; color: #777; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Password Reset Request</h2>
            <p>Hello,</p>
            <p>You (or someone pretending to be you) requested a password reset for your Castle Scouting account associated with this email address.</p>
            <p>If this was you, click the button below to set a new password:</p>
            <a href="{reset_url}" class="button" style="color: #ffffff;">Reset Password</a>
            <p>This link is valid for 30 minutes.</p>
            <p>If you did not request a password reset, please ignore this email. Your password will remain unchanged.</p>
        </div>
    </body>
    </html>
    """

    em = EmailMessage()
    em['From'] = email_address
    em['To'] = recipient_email
    em['Subject'] = subject
    em.set_content(body, subtype='html')

    # Add SSL context
    context = ssl.create_default_context()

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as smtp:
            smtp.login(email_address, email_password)
            smtp.send_message(em)
            logger.info(f"Password reset email sent successfully to {recipient_email}")
            return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP Authentication Error: Check email address and app password.")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP Error sending password reset email to {recipient_email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending password reset email to {recipient_email}: {e}")
        return False
