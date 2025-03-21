import os
import threading
import time
from datetime import datetime, timedelta
import json
import logging

from dotenv import load_dotenv
from flask import (Flask, jsonify, make_response, render_template,
                   send_from_directory, g, current_app, redirect, url_for)
from flask_login import LoginManager, current_user
from flask_pymongo import PyMongo
from flask_wtf.csrf import CSRFProtect
from pywebpush import webpush, WebPushException

from app.auth.auth_utils import UserManager
from app.models import AssignmentSubscription
from app.utils import limiter
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

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

    with app.app_context():
        if "users" not in mongo.db.list_collection_names():
            mongo.db.create_collection("users")
        if "teams" not in mongo.db.list_collection_names():
            mongo.db.create_collection("teams")
        if "team_data" not in mongo.db.list_collection_names():
            mongo.db.create_collection("team_data")
        if "pit_scouting" not in mongo.db.list_collection_names():
            mongo.db.create_collection("pit_scouting")
        if "assignments" not in mongo.db.list_collection_names():
            mongo.db.create_collection("assignments")
        if "assignment_subscriptions" not in mongo.db.list_collection_names():
            mongo.db.create_collection("assignment_subscriptions")
            
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "error"

    try:
        user_manager = UserManager(app.config["MONGO_URI"])
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

    user_manager = UserManager(app.config["MONGO_URI"])

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
        """Close all database connections when the app context ends"""
        if hasattr(current_app, 'db_connections'):
            for name, connection in list(current_app.db_connections.items()):
                try:
                    if connection:
                        if hasattr(connection, 'close'):
                            # If this is a DatabaseManager instance
                            connection.close()
                        elif 'client' in connection and connection['client']:
                            # If this is a raw connection dictionary
                            connection['client'].close()
                            connection['client'] = None
                            connection['db'] = None
                    app.logger.info(f"Closed {name} database connection")
                except Exception as e:
                    app.logger.error(f"Error closing {name} connection: {str(e)}")
        
        # Clear the connections dictionary
        if hasattr(current_app, 'db_connections'):
            current_app.db_connections = {}

    # Database connection timeout middleware
    @app.after_request
    def check_db_connections(response):
        """Check and close idle database connections after a request is processed"""
        try:
            # Only run this check occasionally (e.g., 1% of requests) to avoid overhead
            if hasattr(current_app, 'db_connections') and hash(str(time.time())) % 100 == 0:
                logger.info("Checking for idle database connections")
                idle_time = 300  # 5 minutes
                current_time = time.time()
                
                # Store connections to close in a separate list to avoid modifying during iteration
                connections_to_close = []
                
                # First identify idle connections
                for name, connection in current_app.db_connections.items():
                    # Only attempt to close DatabaseManager instances
                    if (connection and 
                        'client' in connection and 
                        connection['client'] and 
                        hasattr(connection, 'last_used') and 
                        (current_time - connection.last_used) > idle_time):
                        connections_to_close.append(name)
                        
                # Log the idle connections
                if connections_to_close:
                    logger.info(f"Closing {len(connections_to_close)} idle connections: {connections_to_close}")
                    
                    # Close the idle connections
                    for name in connections_to_close:
                        try:
                            # Make sure the connection still exists (might have been closed elsewhere)
                            if name in current_app.db_connections and current_app.db_connections[name]:
                                # Only close the client, don't delete from the dict so we know it was closed
                                if hasattr(current_app.db_connections[name], 'close'):
                                    current_app.db_connections[name].close()
                                else:
                                    # Handle raw connection dictionaries
                                    client = current_app.db_connections[name].get('client')
                                    if client:
                                        client.close()
                                        current_app.db_connections[name]['client'] = None
                        except Exception as e:
                            logger.error(f"Error closing idle connection {name}: {str(e)}")
        except Exception as e:
            logger.error(f"Error in check_db_connections: {str(e)}")
        
        return response

    return app

# if __name__ == "__main__":
#     app = create_app()

#     app.run()
