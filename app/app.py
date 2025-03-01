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
from app.models import ScheduledNotification
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
        VAPID_CLAIM=os.getenv("VAPID_SUBJECT", "mailto:team334@gmail.com")
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
        if "notification_subscriptions" not in mongo.db.list_collection_names():
            mongo.db.create_collection("notification_subscriptions")
        if "scheduled_notifications" not in mongo.db.list_collection_names():
            mongo.db.create_collection("scheduled_notifications")
    

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

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(scouting_bp, url_prefix="/")
    app.register_blueprint(team_bp, url_prefix="/team")

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
    
    # Start notification scheduler
    start_notification_scheduler(app)

    # Register shutdown handler to stop the thread
    @app.teardown_appcontext
    def shutdown_scheduler(exception=None):
        stop_notification_scheduler()

    return app


def start_notification_scheduler(app):
    """Start the notification scheduler in a background thread"""
    global notification_thread, stop_notification_thread
    
    # Reset the stop flag
    stop_notification_thread = False
    
    if notification_thread is None or not notification_thread.is_alive():
        app.logger.info("Starting notification scheduler thread")
        notification_thread = threading.Thread(
            target=notification_scheduler_worker,
            args=(app,),
            daemon=True
        )
        notification_thread.start()
        app.logger.info(f"Notification scheduler thread started: {notification_thread.name}")
    else:
        app.logger.info(f"Notification scheduler already running: {notification_thread.name}")


def notification_scheduler_worker(app):
    """Worker function that runs in the background to send scheduled notifications"""
    with app.app_context():
        app.logger.info("Notification scheduler worker started")
        
        # How often to check for notifications (in seconds)
        check_interval = 60  # Check every minute
        
        while not stop_notification_thread:
            try:
                # Get current time
                now = datetime.now()
                
                # Find notifications that need to be sent
                pending_notifications = mongo.db.scheduled_notifications.find({
                    "scheduled_time": {"$lte": now},
                    "sent": False
                })
                
                # Count how many we found
                count = 0
                for notification in pending_notifications:
                    count += 1
                    
                    # Get the user's subscription
                    subscription = mongo.db.notification_subscriptions.find_one({
                        "user_id": notification["user_id"]
                    })
                    
                    # Skip if no subscription found
                    if not subscription or not subscription.get("subscription_json"):
                        app.logger.warning(f"No subscription found for user {notification['user_id']}")
                        # Mark as sent but failed
                        mongo.db.scheduled_notifications.update_one(
                            {"_id": notification["_id"]},
                            {"$set": {"sent": True, "status": "failed", "sent_at": now}}
                        )
                        continue
                    
                    # Get VAPID keys
                    vapid_private = app.config.get("VAPID_PRIVATE_KEY", "")
                    if not vapid_private:
                        app.logger.error("VAPID private key not found")
                        continue
                        
                    # Prepare notification data
                    notification_data = {
                        "title": notification.get("title", "Assignment Reminder"),
                        "body": notification.get("body", "You have an assignment due soon!"),
                        "url": notification.get("url", "/team/manage"),
                        "timestamp": int(now.timestamp() * 1000),
                        "data": notification.get("data", {})
                    }
                    
                    # Convert to JSON
                    json_data = json.dumps(notification_data)
                    
                    try:
                        # Send push notification
                        webpush(
                            subscription_info=subscription["subscription_json"],
                            data=json_data,
                            vapid_private_key=vapid_private,
                            vapid_claims={"sub": app.config.get("VAPID_SUBJECT", f"mailto:{app.config.get('MAIL_DEFAULT_SENDER', 'test@example.com')}")}
                        )
                        
                        # Mark as sent
                        mongo.db.scheduled_notifications.update_one(
                            {"_id": notification["_id"]},
                            {"$set": {"sent": True, "status": "sent", "sent_at": now}}
                        )
                        
                        app.logger.info(f"Sent notification {notification['_id']} to user {notification['user_id']}")
                        
                    except WebPushException as e:
                        app.logger.error(f"Failed to send notification {notification['_id']}: {str(e)}")
                        # Mark as sent but failed
                        mongo.db.scheduled_notifications.update_one(
                            {"_id": notification["_id"]},
                            {"$set": {"sent": True, "status": "failed", "error": str(e), "sent_at": now}}
                        )
                
                if count > 0:
                    app.logger.info(f"Processed {count} pending notifications")
                
                # Sleep until next check
                time.sleep(check_interval)
                
            except Exception as e:
                app.logger.error(f"Error in notification scheduler: {str(e)}", exc_info=True)
                # Sleep a bit before retrying
                time.sleep(check_interval)


# Add a function to stop the thread when the app shuts down
def stop_notification_scheduler():
    global notification_thread, stop_notification_thread
    if notification_thread and notification_thread.is_alive():
        stop_notification_thread = True
        notification_thread.join(timeout=5)


# if __name__ == "__main__":
#     app = create_app()

#     app.run()
