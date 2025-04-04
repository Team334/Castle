import os
import logging
import hashlib
from time import strftime
import traceback

from dotenv import load_dotenv
from flask import (Flask, make_response, render_template,
                   send_from_directory, request, flash, redirect, url_for)
from flask_login import LoginManager, current_user
from flask_pymongo import PyMongo
from flask_wtf.csrf import CSRFProtect
from flask_cors import CORS

from app.auth.auth_utils import UserManager
from app.utils import limiter, get_mongodb_instance, close_mongodb_connection

csrf = CSRFProtect()
mongo = PyMongo()
login_manager = LoginManager()

# Global variable to control notification thread
notification_thread = None
stop_notification_thread = False

logger = logging.getLogger(__name__)

def hash_team_access_code(code: str) -> str:
    """Hash the team access code using SHA-256"""
    return hashlib.sha256(code.encode()).hexdigest()

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # Load config
    load_dotenv()
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "team334"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        WTF_CSRF_ENABLED=True,
        MONGO_URI=os.getenv("MONGO_URI", "mongodb://localhost:27017/scouting_app"),
        VAPID_PUBLIC_KEY=os.getenv("VAPID_PUBLIC_KEY", ""),
        VAPID_PRIVATE_KEY=os.getenv("VAPID_PRIVATE_KEY", ""),
        VAPID_CLAIM_EMAIL=os.getenv("VAPID_CLAIM_EMAIL", "team334@gmail.com"),
        TEAM_ACCESS_CODE_HASH=hash_team_access_code(os.getenv("TEAM_ACCESS_CODE", "your_team_access_code"))
    )
    
    if not app.config.get("VAPID_PUBLIC_KEY") or not app.config.get("VAPID_PRIVATE_KEY"):
        app.logger.warning("VAPID keys not configured. Push notifications will not work.")
    else:
        app.logger.info("VAPID keys configured properly.")

    mongo.init_app(app)
    app.mongo = mongo
    # csrf.init_app(app)
    limiter.init_app(app)
    CORS(app, resources={r"/*": {"origins": "*", "methods": ["GET", "POST", "PUT", "DELETE"]}})
    # Initialize db_managers dictionary to store all database managers for proper cleanup
    app.db_managers = {}

    with app.app_context():
        # Get the singleton MongoDB instance
        mongodb = get_mongodb_instance(app.config["MONGO_URI"])
        db = mongodb.get_db()
        
        # Initialize collections
        if "users" not in db.list_collection_names():
            db.create_collection("users")
        if "teams" not in db.list_collection_names():
            db.create_collection("teams")
        if "team_data" not in db.list_collection_names():
            db.create_collection("team_data")
        if "pit_scouting" not in db.list_collection_names():
            db.create_collection("pit_scouting")
        if "assignments" not in db.list_collection_names():
            db.create_collection("assignments")
        if "assignment_subscriptions" not in db.list_collection_names():
            db.create_collection("assignment_subscriptions")
            
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "error"

    # Initialize UserManager with the singleton connection
    try:
        # Create user manager with singleton connection
        user_manager = UserManager(app.config["MONGO_URI"])
        
        # Store in app context for proper cleanup
        app.user_manager = user_manager
    except Exception as e:
        app.logger.error(f"Failed to initialize UserManager: {e}")
        raise

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return user_manager.get_user_by_id(user_id)
        except Exception as e:
            app.logger.error(f"Error loading user: {e}")
            return None

    # Import blueprints inside create_app to avoid circular imports
    from app.auth.routes import auth_bp
    from app.scout.routes import scouting_bp
    from app.team.routes import team_bp
    from app.notifications.routes import notifications_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(scouting_bp, url_prefix="/")
    app.register_blueprint(team_bp, url_prefix="/team")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")

    @app.route("/")
    def index():
        return render_template("index.html")
    
    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html")

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(f"Server error: {str(e)} - User: {current_user.username if current_user.is_authenticated else "Anonymous"}", exc_info=True)
        return render_template("500.html"), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        trace = traceback.format_exec()
        timestamp = strftime('[%Y-%b-%d %H:%M]')
        app.logger.error(f"{timestamp} User: {current_user.username if current_user.is_authenticated else "Anonymous"} Unhandled exception: {str(e)}\nTraceback: {trace}", exc_info=True)
        return render_template("500.html"), 500
    
    @app.errorhandler(429)
    def rate_limit_error(e):
        return render_template("429.html"), 429

    @app.before_request
    def check_team_access():
        """
        Additional protection to restrict access to only approved team members.
        This blocks IP addresses not associated with team members once they've registered.
        """
        # Skip for static assets, authentication, and public routes
        if request.path.startswith('/static') or \
           request.path == '/' or \
           request.path == '/service-worker.js' or \
           request.path.startswith('/auth/login') or \
           request.path.startswith('/auth/register'):
            return
            
        # Block access for non-authenticated users to protected routes
        if not current_user.is_authenticated:
            flash("Access restricted to Team 334 members only.", "error")
            return redirect(url_for('auth.login'))
        
    @app.after_request
    def after_request(response): 
        timestamp = strftime('[%Y-%b-%d %H:%M]')
        logger.info('%s %s User: %s %s %s %s %s', timestamp, request.remote_addr, current_user.username if current_user.is_authenticated else "Anonymous", request.method, request.scheme, request.full_path, response.status)
        return response

    @app.route('/static/manifest.json')
    def serve_manifest():
        response = make_response(send_from_directory(app.static_folder, 'manifest.json'))
        response.headers['Content-Type'] = 'application/manifest+json'
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    @app.route('/service-worker.js')
    def serve_root_service_worker():
        response = make_response(send_from_directory(app.static_folder, 'js/service-worker.js'))
        response.headers['Service-Worker-Allowed'] = '/'
        response.headers['Content-Type'] = 'application/javascript'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    
    @app.route('/offline.html')
    def offline():
        return render_template('offline.html')

    # Handle application shutdown to close the singleton MongoDB connection
    @app.teardown_appcontext
    def teardown_db_connection(exception=None):
        """Close the singleton MongoDB connection only during application shutdown"""
        if exception is not None and isinstance(exception, Exception):
            # Only close during actual application shutdown, not regular request teardown
            close_mongodb_connection()
            logger.info("Closed singleton MongoDB connection during application shutdown")

    return app

# if __name__ == "__main__":
#     app = create_app()

#     app.run()
