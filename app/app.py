import os
import threading
import time
from datetime import datetime, timedelta

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
    
    # Start notification scheduler in a background thread
    notification_thread = threading.Thread(target=notification_scheduler, args=(app,))
    notification_thread.daemon = True
    notification_thread.start()
    app.logger.info("Notification scheduler started")

    return app


def notification_scheduler(app):
    """Background thread that checks for scheduled notifications and sends them"""
    with app.app_context():
        while True:
            try:
                # Find notifications that are scheduled to be sent now and haven't been sent yet
                current_time = datetime.now()
                notifications = mongo.db.scheduled_notifications.find({
                    "scheduled_time": {"$lte": current_time},
                    "sent": False
                })
                
                for notification_data in notifications:
                    notification = ScheduledNotification.create_from_db(notification_data)
                    
                    # Get the user's subscription
                    subscription = mongo.db.notification_subscriptions.find_one({
                        "user_id": notification.user_id
                    })
                    
                    if not subscription or not subscription.get("subscription_json"):
                        app.logger.warning(f"No subscription found for user {notification.user_id}")
                        continue
                    
                    # Send the push notification
                    try:
                        webpush(
                            subscription_info=subscription["subscription_json"],
                            data=jsonify({
                                "title": notification.title,
                                "body": notification.body,
                                "url": notification.url,
                                "assignmentId": notification.assignment_id,
                                "teamNumber": notification.team_number,
                                "timestamp": int(current_time.timestamp() * 1000)
                            }).get_data(as_text=True),
                            vapid_private_key=app.config.get("VAPID_PRIVATE_KEY"),
                            vapid_claims={"sub": app.config.get("VAPID_SUBJECT")}
                        )
                        
                        # Mark notification as sent
                        mongo.db.scheduled_notifications.update_one(
                            {"_id": notification._id},
                            {"$set": {"sent": True, "sent_at": current_time}}
                        )
                        
                        app.logger.info(f"Sent notification {notification.id} to user {notification.user_id}")
                    except WebPushException as e:
                        app.logger.error(f"WebPush error: {e}")
                        
                        # If subscription is expired, remove it
                        if e.response and e.response.status_code == 410:
                            mongo.db.notification_subscriptions.update_one(
                                {"user_id": notification.user_id},
                                {"$set": {"subscription_json": {}}}
                            )
                            app.logger.warning(f"Removed expired subscription for user {notification.user_id}")
                    except Exception as e:
                        app.logger.error(f"Error sending notification: {e}")
                
                # Schedule new notifications for upcoming assignments
                schedule_upcoming_assignment_notifications(app)
                
            except Exception as e:
                app.logger.error(f"Error in notification scheduler: {e}")
            
            # Sleep for a minute before checking again
            time.sleep(60)


def schedule_upcoming_assignment_notifications(app):
    """Schedule notifications for upcoming assignments"""
    try:
        # Find assignments with due dates in the future
        current_time = datetime.now()
        assignments = mongo.db.assignments.find({
            "due_date": {"$gt": current_time}
        })
        
        for assignment in assignments:
            # For each user assigned to this assignment
            for user_id in assignment.get("assigned_to", []):
                # Get user's notification preferences
                subscription = mongo.db.notification_subscriptions.find_one({
                    "user_id": user_id
                })
                
                if not subscription:
                    continue
                
                # Check if user has enabled notifications for this assignment
                enable_all = subscription.get("enable_all_notifications", False)
                assignment_subscriptions = subscription.get("assignment_subscriptions", [])
                
                is_subscribed = enable_all or any(
                    sub.get("assignment_id") == str(assignment["_id"]) 
                    for sub in assignment_subscriptions
                )
                
                if not is_subscribed:
                    continue
                
                # Get reminder time (in minutes before due date)
                reminder_time = 1440  # Default: 1 day
                for sub in assignment_subscriptions:
                    if sub.get("assignment_id") == str(assignment["_id"]):
                        reminder_time = sub.get("reminder_time", 1440)
                        break
                
                if enable_all and not any(sub.get("assignment_id") == str(assignment["_id"]) for sub in assignment_subscriptions):
                    reminder_time = subscription.get("default_reminder_time", 1440)
                
                # Calculate when to send the notification
                due_date = assignment.get("due_date")
                if not due_date:
                    continue
                
                notification_time = due_date - timedelta(minutes=reminder_time)
                
                # If notification time is in the past, skip
                if notification_time <= current_time:
                    continue
                
                # Check if notification is already scheduled
                existing_notification = mongo.db.scheduled_notifications.find_one({
                    "user_id": user_id,
                    "assignment_id": str(assignment["_id"]),
                    "sent": False
                })
                
                if existing_notification:
                    continue
                
                # Schedule the notification
                notification = {
                    "user_id": user_id,
                    "team_number": assignment.get("team_number"),
                    "assignment_id": str(assignment["_id"]),
                    "title": f"Assignment Reminder: {assignment.get('title')}",
                    "body": f"Due {due_date.strftime('%Y-%m-%d %I:%M %p')}",
                    "scheduled_time": notification_time,
                    "created_at": current_time,
                    "sent": False,
                    "url": f"/team/{assignment.get('team_number')}/manage",
                    "data": {
                        "assignmentId": str(assignment["_id"]),
                        "teamNumber": assignment.get("team_number")
                    }
                }
                
                mongo.db.scheduled_notifications.insert_one(notification)
                app.logger.info(f"Scheduled notification for user {user_id}, assignment {assignment['_id']}")
                
    except Exception as e:
        app.logger.error(f"Error scheduling notifications: {e}")


# if __name__ == "__main__":
#     app = create_app()

#     app.run()
