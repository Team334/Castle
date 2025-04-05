from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required

from app.utils import async_route, limiter
from .notification_manager import NotificationManager

notifications_bp = Blueprint("notifications", __name__)
notification_manager = None

@notifications_bp.record
def on_blueprint_init(state):
    """Initialize the notification manager"""
    global notification_manager
    app = state.app
    
    # Get VAPID keys from config
    vapid_private_key = app.config.get("VAPID_PRIVATE_KEY")
    vapid_claims = {
        "sub": f"mailto:{app.config.get('VAPID_CLAIM_EMAIL', 'admin@example.com')}"
    }
    
    # Create notification manager with the singleton connection
    notification_manager = NotificationManager(
        mongo_uri=app.config["MONGO_URI"],
        vapid_private_key=vapid_private_key,
        vapid_claims=vapid_claims
    )
    
    # Store in app context for proper cleanup
    if not hasattr(app, 'db_managers'):
        app.db_managers = {}
    app.db_managers['notification'] = notification_manager
    
    # Start the notification service
    notification_manager.start_notification_service()
    
    # Register shutdown function
    @app.teardown_appcontext
    def shutdown_notification_service(exception=None):
        if notification_manager:
            notification_manager.stop_notification_service()

@notifications_bp.route("/vapid-public-key")
def get_vapid_public_key():
    """Return the VAPID public key for push notifications"""
    return jsonify({
        "publicKey": current_app.config.get("VAPID_PUBLIC_KEY", "")
    })

@notifications_bp.route("/subscribe", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
@async_route
async def create_subscription():
    """Create or update a push notification subscription"""
    try:
        data = request.get_json()
        
        if not data or not data.get("subscription"):
            return jsonify({
                "success": False,
                "message": "Subscription data is required"
            }), 400
            
        team_number = current_user.teamNumber
        if not team_number:
            return jsonify({
                "success": False,
                "message": "User is not in a team"
            }), 400
            
        subscription_json = data.get("subscription")
        assignment_id = data.get("assignment_id")
        reminder_time = data.get("reminder_time", 1440)  # Default: 1 day
        
        success, message = await notification_manager.create_subscription(
            user_id=current_user.get_id(),
            team_number=team_number,
            subscription_json=subscription_json,
            assignment_id=assignment_id,
            reminder_time=reminder_time
        )
        
        if success:
            current_app.logger.info(f"Successfully created subscription {subscription_json} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
            return jsonify({
                "success": True,
                "message": message
            }), 200
        else:
            current_app.logger.info(f"Failed to create subscription {subscription_json} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
            return jsonify({
                "success": False,
                "message": message
            }), 400
    
    except Exception as e:
        current_app.logger.error(f"Error creating subscription: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": "An internal error has occurred."
        }), 500

@notifications_bp.route("/unsubscribe", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
@async_route
async def delete_subscription():
    """Delete a push notification subscription"""
    try:
        data = request.get_json()
        team_number = current_user.teamNumber
        assignment_id = data.get("assignment_id") if data else None
        
        success, message = await notification_manager.delete_subscription(
            user_id=current_user.get_id(),
            team_number=team_number,
            assignment_id=assignment_id
        )
        current_app.logger.info(f"Successfully deleted subscription {assignment_id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return jsonify({
            "success": success,
            "message": message
        }), 200 if success else 400
    
    except Exception as e:
        current_app.logger.error(f"Error deleting subscription: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "message": "An internal error has occurred."
        }), 500

# @notifications_bp.route("/test", methods=["POST"])
# @login_required
# @limiter.limit("3 per minute")
# @async_route
# async def test_notification():
#     """Send a test notification to the current user"""
#     try:
#         success, message = await notification_manager.test_notification(
#             user_id=current_user.get_id()
#         )
        
#         return jsonify({
#             "success": success,
#             "message": message
#         }), 200 if success else 400
    
#     except Exception as e:
#         current_app.logger.error(f"Error sending test notification: {str(e)}")
#         return jsonify({
#             "success": False,
#             "message": "An internal error has occurred."
#         }), 500 