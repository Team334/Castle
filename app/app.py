import os
import time
import logging

from dotenv import load_dotenv
from flask import (Flask, make_response, render_template,
                   send_from_directory, g, current_app)
from flask_login import LoginManager
from flask_pymongo import PyMongo
from flask_wtf.csrf import CSRFProtect

from app.auth.auth_utils import UserManager
from app.utils import limiter, get_database_connection, release_connection, force_close_connection

csrf = CSRFProtect()
mongo = PyMongo()
login_manager = LoginManager()

# Global variable to control notification thread
notification_thread = None
stop_notification_thread = False

logger = logging.getLogger(__name__)

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
        VAPID_CLAIM_EMAIL=os.getenv("VAPID_CLAIM_EMAIL", "team334@gmail.com")
    )
    
    if not app.config.get("VAPID_PUBLIC_KEY") or not app.config.get("VAPID_PRIVATE_KEY"):
        app.logger.warning("VAPID keys not configured. Push notifications will not work.")
    else:
        app.logger.info("VAPID keys configured properly.")

    mongo.init_app(app)
    app.mongo = mongo
    # csrf.init_app(app)
    limiter.init_app(app)
    
    # Initialize db_managers dictionary to store all database managers for proper cleanup
    app.db_managers = {}

    with app.app_context():
        # Get a shared MongoDB connection
        conn = get_database_connection(app.config["MONGO_URI"])
        db = conn['db']
        
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
            
        # Store the connection in app context for reuse
        app.db_connection = conn
            
        # Release the initial connection reference
        release_connection()
            
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "error"

    # Initialize UserManager with the shared connection
    try:
        # Create user manager with existing connection
        user_manager = UserManager(app.config["MONGO_URI"], existing_connection=app.db_connection)
        
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
        app.logger.error(f"Server error: {str(e)}", exc_info=True)
        return render_template("500.html"), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        return render_template("500.html"), 500
    
    @app.errorhandler(429)
    def rate_limit_error(e):
        return render_template("429.html"), 429

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
    
    @app.teardown_appcontext
    def close_db_connections(exception=None):
        """Release database connections when the app context ends, but only if they were accessed"""
        # Only log at debug level since this happens for every request
        logger.debug("App context teardown - checking database connections")
        
        # Only clean up connections if the request actually accessed the database
        # We can check if g has certain attributes to determine this
        if not hasattr(g, 'db_accessed'):
            logger.debug("No database access detected for this request, skipping connection cleanup")
            return
        
        # Clean up the user manager if it exists
        if hasattr(current_app, 'user_manager') and current_app.user_manager:
            try:
                current_app.user_manager.close()
                logger.info("Closed user_manager database connection")
            except Exception as e:
                logger.error(f"Error closing user_manager connection: {str(e)}")
        
        # Clean up all database managers
        if hasattr(current_app, 'db_managers'):
            for name, manager in list(current_app.db_managers.items()):
                try:
                    if manager and hasattr(manager, 'close'):
                        # Special handling for notification manager to stop the service
                        if name == 'notification' and hasattr(manager, 'stop_notification_service'):
                            manager.stop_notification_service()
                            logger.info("Notification service stopped during app shutdown")
                        
                        # Close the database connection
                        manager.close()
                        logger.info(f"Closed {name} database manager connection")
                except Exception as e:
                    logger.error(f"Error closing {name} connection: {str(e)}")
            
            # Clear the managers dictionary
            current_app.db_managers = {}
            
        # Final check of global connection pool during actual application shutdown
        # (not just request end) - we can detect this by checking if the app is tearing down
        if exception is not None and isinstance(exception, Exception):
            from app.utils import _GLOBAL_DB_CONNECTION
            if _GLOBAL_DB_CONNECTION['count'] > 0:
                logger.warning(f"Connection pool still has {_GLOBAL_DB_CONNECTION['count']} references at shutdown")
                # Force close the connection during application teardown
                force_close_connection()

    # Setup notification service shutdown for app termination
    @app.after_request
    def initialize_notification_cleanup(response):
        """Initialize notification cleanup on first request"""
        # Only run once by using an attribute check
        if not hasattr(app, '_notification_cleanup_initialized'):
            app._notification_cleanup_initialized = True
            
            try:
                # Ensure we only register this once
                from app.notifications.routes import notification_manager
                
                if 'notification' in app.db_managers and app.db_managers['notification']:
                    logger.info("Notification service already registered for cleanup")
                else:
                    # Make sure notification manager is registered for cleanup
                    logger.info("Registering notification service for cleanup")
                    app.db_managers['notification'] = notification_manager
            except ImportError:
                logger.warning("Could not import notification_manager, skipping cleanup setup")
                
        return response

    # Since we're now using a global connection pool, let's add a periodic cleanup
    @app.after_request
    def check_db_connections(response):
        """Occasionally check the global connection pool"""
        # Only run this check occasionally (e.g., 1% of requests) to avoid overhead
        if hash(str(time.time())) % 100 == 0:
            from app.utils import _GLOBAL_DB_CONNECTION
            logger.info(f"Current connection pool count: {_GLOBAL_DB_CONNECTION['count']}")
            
            # If count is high, it might indicate a leak
            if _GLOBAL_DB_CONNECTION['count'] > 10:
                logger.warning(f"High connection count detected: {_GLOBAL_DB_CONNECTION['count']}")
        
        return response

    return app

# if __name__ == "__main__":
#     app = create_app()

#     app.run()
