import os
import threading
import time
from datetime import datetime, timedelta
import json

from dotenv import load_dotenv
from flask import (Flask, jsonify, make_response, render_template,
                   send_from_directory)
from flask_login import LoginManager
from flask_pymongo import PyMongo
from flask_wtf.csrf import CSRFProtect
from pywebpush import webpush, WebPushException

from app.auth.auth_utils import UserManager
from app.models import AssignmentSubscription
from app.utils import limiter

csrf = CSRFProtect()
mongo = PyMongo()
login_manager = LoginManager()

# Global variable to control notification thread
notification_thread = None
stop_notification_thread = False


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
        if "notification_preferences" not in mongo.db.list_collection_names():
            mongo.db.create_collection("notification_preferences")

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
        return send_from_directory(app.static_folder, 'manifest.json')

    @app.route('/service-worker.js')
    def serve_root_service_worker():
        response = make_response(send_from_directory(app.static_folder, 'js/service-worker.js'))
        response.headers['Service-Worker-Allowed'] = '/'
        response.headers['Cache-Control'] = 'no-cache'
        return response
    
    @app.route('/static/js/service-worker.js')
    def serve_service_worker():
        response = make_response(send_from_directory(app.static_folder, 'js/service-worker.js'))
        response.headers['Service-Worker-Allowed'] = '/'
        response.headers['Cache-Control'] = 'no-cache'
        return response

    return app

# if __name__ == "__main__":
#     app = create_app()

#     app.run()
