from __future__ import annotations

from io import BytesIO
from datetime import datetime, timedelta

from bson import ObjectId
from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, send_file, url_for)
from flask_login import current_user, login_required
from gridfs import GridFS
from PIL import Image
from werkzeug.utils import secure_filename

from app.team.team_utils import TeamManager
from app.utils import (allowed_file, async_route, error_response,
                       handle_route_errors, limiter, save_file_to_gridfs,
                       success_response)
from app.models import NotificationSubscription, ScheduledNotification

from .forms import CreateTeamForm

team_bp = Blueprint("team", __name__)
team_manager = None

@team_bp.record
def on_blueprint_init(state):
    global team_manager
    app = state.app
    team_manager = TeamManager(app.config["MONGO_URI"])

@team_bp.route("/join", methods=["GET", "POST"])
@login_required
@limiter.limit("3 per minute")
@async_route
async def join():
    try:
        if current_user.teamNumber:
            return redirect(url_for("team.manage"))

        if request.method == "POST":
            join_code = request.form.get("join_code")
            if not join_code:
                flash("Join code is required", "error")
                return redirect(url_for("team.join"))

            success, result = await team_manager.join_team(current_user.get_id(), join_code)

            if success:
                team, updated_user = result
                current_user.teamNumber = updated_user.teamNumber
                flash(f"Successfully joined team {team.team_number}", "success")
                return redirect(url_for("team.manage", team_number=team.team_number))
            
            flash("Invalid join code", "error")
            return redirect(url_for("team.join"))
        
        return render_template("team/join.html")



    except Exception as e:
        current_app.logger.error(f"Error in join_team_page: {str(e)}", exc_info=True)
        flash("Unable to process your request. Please try again later.", "error")
        return redirect(url_for("team.join"))

@team_bp.route("/create", methods=["GET", "POST"])
@login_required
@limiter.limit("3 per minute")
@async_route
async def create():
    """Handle team creation"""
    if current_user.teamNumber:

        return redirect(url_for("team.manage"))

    form = CreateTeamForm()


    if form.validate_on_submit():
        current_app.logger.debug("Form validated successfully")
        try:
            # Handle logo upload if provided
            logo_id = None
            if form.logo.data:
                # Open and resize image
                image = Image.open(form.logo.data)
                image = image.convert('RGBA')  # Convert to RGBA mode
                image.thumbnail((200, 200))  # Resize maintaining aspect ratio
                
                # Save to BytesIO
                buffer = BytesIO()
                image.save(buffer, format='PNG')
                buffer.seek(0)
                
                fs = GridFS(team_manager.db)
                filename = secure_filename(
                    f"team_{form.team_number.data}_logo.png"
                )
                current_app.logger.debug(f"Uploading file: {filename}")
                logo_id = fs.put(
                    buffer.getvalue(),
                    filename=filename,
                    content_type='image/png'
                )

            # Create the team
            success, result = await team_manager.create_team(
                team_number=form.team_number.data,
                creator_id=current_user.id,
                team_name=form.team_name.data,
                description=form.description.data,
                logo_id=str(logo_id) if logo_id else None,
            )

            if success:
                flash("Team created successfully!", "success")
                return redirect(url_for("team.manage"))
            else:
                if logo_id:  # Clean up uploaded file if team creation failed

                    fs = GridFS(team_manager.db)
                    fs.delete(logo_id)
                flash(f"Error creating team: {result}", "error")

        except Exception as e:
            current_app.logger.error(f"Error in create_team route: {str(e)}")
            flash("An internal error has occurred.", "error")

    return render_template("team/create.html", form=form)


@team_bp.route("/<int:team_number>/leave", methods=["GET", "POST"])
@login_required
@limiter.limit("3 per minute")
@async_route
async def leave(team_number):
    """Leave a team"""

    success, message = await team_manager.leave_team(current_user.get_id(), team_number)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": success, "message": message})

    if success:
        current_user.teamNumber = None
        flash("Successfully left the team", "success")
        return redirect(url_for("team.join"))
    else:
        flash(f"Failed to leave team: {message}", "error")
        return redirect(url_for("team.manage", team_number=team_number))




@team_bp.route("/<int:team_number>/members", methods=["GET"])
@login_required
@async_route
async def get_team_members(team_number):
    """Get all members of a team"""
    members = await team_manager.get_team_members(team_number)

    return (
        jsonify({"success": True, "members": [member.to_dict() for member in members]}),
        200,
    )


@team_bp.route("/<int:team_number>/admin/add", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
@async_route
async def add_admin(team_number):
    """Add a new admin to the team"""

    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"success": False, "message": "User ID is required"}), 400

    success, message = await team_manager.add_admin(
        team_number, user_id, current_user.get_id()
    )

    return jsonify({"success": success, "message": message}), 200 if success else 400


@team_bp.route("/<int:team_number>/admin/remove", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
@async_route
async def remove_admin(team_number):
    """Remove an admin from the team"""

    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"success": False, "message": "User ID is required"}), 400

    success, message = await team_manager.remove_admin(
        team_number, user_id, current_user.get_id()
    )

    return jsonify({"success": success, "message": message}), 200 if success else 400


@team_bp.route("/<int:team_number>/assignments", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
@async_route
async def create_assignment(team_number):
    """Create a new assignment"""

    try:
        data = request.get_json()
        success, message = await team_manager.create_or_update_assignment(
            team_number, data, current_user.get_id()
        )

        if success:
            return (
                jsonify(
                    {"success": True, "message": "Assignment created successfully"}
                ),
                200,
            )
        return jsonify({"success": False, "message": message}), 400

    except Exception as e:
        current_app.logger.error(f"Error creating assignment: {str(e)}")
        return jsonify({"success": False, "message": "An internal error has occurred."}), 500


@team_bp.route("/assignments/<assignment_id>/status", methods=["PUT"])
@login_required
@limiter.limit("5 per minute")
def update_assignment_status(assignment_id):
    """Update assignment status"""

    data = request.get_json()
    new_status = data.get("status")

    if not new_status:
        return jsonify({"success": False, "message": "Status is required"}), 400

    success, message = team_manager.update_assignment_status(
        assignment_id, current_user.get_id(), new_status
    )

    return jsonify({"success": success, "message": message}), 200 if success else 400


@team_bp.route("/assignments/<assignment_id>/update", methods=["PUT"])
@login_required
@limiter.limit("15 per minute")
@async_route
async def update_assignment(assignment_id):

    """Update assignment"""
    data = request.get_json()
    success, message = await team_manager.update_assignment(
        assignment_id, current_user.get_id(), data
    )
    return jsonify({"success": success, "message": message}), 200 if success else 400


@team_bp.route("/assignments/<assignment_id>/delete", methods=["DELETE"])
@login_required
@limiter.limit("10 per minute")
@async_route
async def delete_assignment(assignment_id):

    """Delete assignment"""
    success, message = await team_manager.delete_assignment(
        assignment_id, current_user.get_id()
    )
    return jsonify({"success": success, "message": message}), 200 if success else 400


@team_bp.route("/manage", methods=["GET", "POST"])
@team_bp.route("/manage/<int:team_number>", methods=["GET", "POST"])
@team_bp.route("/", methods=["GET", "POST"])
@login_required
@limiter.limit("30 per minute")
@async_route
async def manage(team_number=None):
    """Manage team"""

    if not current_user.teamNumber:
        return redirect(url_for("team.join"))

    success, result = await team_manager.validate_user_team(
        current_user.get_id(), current_user.teamNumber
    )

    if not success:
        current_user.teamNumber = None
        flash(result, "warning")
        return redirect(url_for("team.join"))

    team = result  # result is the team object if validation succeeded
    # Get team members and assignments
    team_members = await team_manager.get_team_members(team.team_number)
    assignments = await team_manager.get_team_assignments(team.team_number)

    # Create a dictionary of user IDs to usernames for easier lookup
    user_dict = {str(member.get_id()): member for member in team_members}

    # Ensure assignment.assigned_to contains string IDs
    for assignment in assignments:
        if hasattr(assignment, "assigned_to"):
            assignment.assigned_to = [
                str(user_id) for user_id in assignment.assigned_to
            ]

    return render_template(
        "team/manage.html",
        team=team,
        current_user=current_user,
        team_members=team_members,
        user_dict=user_dict,
        assignments=assignments,
        is_admin=team.is_admin(current_user.get_id()),
    )


@team_bp.route("/<int:team_number>/user/<user_id>/remove", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
@async_route
async def remove_user(team_number, user_id):
    """Remove a user from the team (admin only)"""

    success, message = await team_manager.remove_user(
        team_number, user_id, current_user.get_id()
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return (
            jsonify({"success": success, "message": message}),
            200 if success else 400,
        )

    if success:
        if user_id == current_user.get_id():
            current_user.teamNumber = None
        flash("User removed successfully", "success")
    else:
        flash(message, "error")
    return redirect(url_for("team.manage"))



@team_bp.route("/<int:team_number>/assignments/clear", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
@async_route
async def clear_assignments(team_number):
    """Clear all assignments for a team (admin only)"""

    success, message = await team_manager.clear_assignments(
        team_number, current_user.get_id()
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return (
            jsonify({"success": success, "message": message}),
            200 if success else 400,
        )

    if success:
        flash("All assignments cleared successfully", "success")
    else:
        flash(message, "error")
    return redirect(url_for("team.manage"))



@team_bp.route("/<int:team_number>/delete", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
@async_route
async def delete_team(team_number):
    """Delete team (owner only)"""
    success, message = await team_manager.delete_team(team_number, current_user.get_id())

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": success, "message": message}), 200 if success else 400

    if success:
        flash("Team deleted successfully", "success")
        return redirect(url_for("team.join"))
    else:
        flash(message, "error")
        return redirect(url_for("team.manage"))


@team_bp.route("/team/<int:team_number>/logo")
def team_logo(team_number):
    try:
        fs = GridFS(team_manager.db)
        team = team_manager.db.teams.find_one({"team_number": team_number})
        
        if team and team.get("logo_id"):
            logo_id = ObjectId(team["logo_id"]) if isinstance(team["logo_id"], str) else team["logo_id"]
            logo = fs.get(logo_id)
            return send_file(
                BytesIO(logo.read()),
                mimetype=logo.content_type,
                download_name=logo.filename
            )
    except Exception as e:
        current_app.logger.error(f"Error fetching team logo: {str(e)}", exc_info=True)
    
    # Return default logo on any error
    return send_file("static/images/default_logo.png")


@team_bp.route("/assignments/<assignment_id>/edit", methods=["PUT"])
@login_required
@limiter.limit("15 per minute")
@async_route
async def edit_assignment(assignment_id):
    """Edit an existing assignment"""

    try:
        data = request.get_json()
        success, result = await team_manager.update_assignment(
            assignment_id=assignment_id,
            user_id=current_user.get_id(),
            assignment_data=data,
        )

        return jsonify({"success": success, "message": result}), 200 if success else 400

    except Exception as e:
        current_app.logger.error(f"Error editing assignment: {str(e)}")
        return jsonify({"success": False, "message": "An internal error has occurred."}), 500


@team_bp.route("/view/<int:team_number>")
@async_route
async def view(team_number):
    """Public view of team with limited information"""
    team = await team_manager.get_team_by_number(team_number)
    
    if not team:
        flash("Team not found", "error")
        return redirect(url_for("index"))
    
    # Get team members
    team_members = await team_manager.get_team_members(team_number)
    
    # Check if current user is a member
    is_member = False
    if current_user.is_authenticated:
        is_member = str(current_user.get_id()) in team.users
    
    return render_template(
        "team/view.html",
        team=team,
        team_members=team_members,
        is_member=is_member
    )


@team_bp.route("/<int:team_number>/update_logo", methods=["POST"])
@login_required
@async_route
@handle_route_errors
async def update_team_logo(team_number):
    """Update team logo"""
    team = await team_manager.get_team_by_number(team_number)
    
    if not team or not team.is_admin(current_user.get_id()):
        return error_response("Unauthorized to update team logo")
    
    if 'team_logo' not in request.files:
        return error_response("No file provided")
        
    file = request.files['team_logo']
    if file.filename == '':
        return error_response("No file selected")
        
    new_logo_id = await save_file_to_gridfs(file, team_manager.db)
    if not new_logo_id:
        return error_response("Invalid file type")
        
    success, message = await team_manager.update_team_logo(team_number, new_logo_id)
    if not success:
        fs = GridFS(team_manager.db)
        fs.delete(new_logo_id)
        
    return success_response(message) if success else error_response("An internal error has occurred.", log_message="Error updating team logo")


@team_bp.route("/<int:team_number>/settings")
@login_required
@limiter.limit("10 per minute")
@async_route
async def settings(team_number):
    """Team settings page for admins"""
    team = await team_manager.get_team_by_number(team_number)
    
    if not team or not team.is_admin(current_user.get_id()):
        flash("Unauthorized to access team settings", "error")
        return redirect(url_for("team.manage", team_number=team_number))
        

    return render_template("team/settings.html", team=team)


@team_bp.route("/<int:team_number>/update_team_info", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
@async_route
async def update_team_info(team_number):
    """Update team information including logo and description"""
    team = await team_manager.get_team_by_number(team_number)
    
    if not team or not team.is_admin(current_user.get_id()):
        flash("Unauthorized to update team information", "error")
        return redirect(url_for("team.manage", team_number=team_number))
    

    try:
        updates = {}
        
        # Handle logo upload if provided
        if 'team_logo' in request.files:
            file = request.files['team_logo']
            if file and file.filename:
                if allowed_file(file.filename):
                    # Save new logo to GridFS
                    fs = GridFS(team_manager.db)
                    
                    # Clean up old logo and its chunks if it exists
                    if team.logo_id:
                        try:
                            # Delete old file and its chunks
                            fs.delete(team.logo_id)
                            # Also clean up any orphaned chunks
                            team_manager.db.fs.chunks.delete_many({"files_id": team.logo_id})
                        except Exception as e:
                            flash("An internal error has occurred.")
                    
                    filename = secure_filename(f"team_{team_number}_logo_{file.filename}")
                    file_id = fs.put(
                        file.stream.read(),
                        filename=filename,
                        content_type=file.content_type
                    )
                    updates['logo_id'] = file_id
                else:
                    flash("Invalid file type. Please use PNG, JPG, or JPEG", "error")
                    return redirect(url_for("team.manage", team_number=team_number))
        

        # Handle description update
        description = request.form.get('description', '').strip()
        updates['description'] = description
        
        # Update team information
        success, message = await team_manager.update_team_info(team_number, updates)
        flash(message, "success" if success else "error")
        return redirect(url_for("team.manage", team_number=team_number))
        

    except Exception as e:
        flash(f"Error updating team information: {str(e)}", "error")
        return redirect(url_for("team.manage", team_number=team_number))

@team_bp.route("/notifications/vapid-public-key")
@login_required
def get_vapid_public_key():
    """Return the VAPID public key for push notifications"""
    vapid_key = current_app.config.get("VAPID_PUBLIC_KEY", "")
    if not vapid_key:
        current_app.logger.error("VAPID_PUBLIC_KEY not configured")
    return vapid_key

@team_bp.route("/notifications/subscribe", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
@async_route
async def subscribe_to_push():
    """Subscribe a user to push notifications"""
    try:
        data = request.get_json()
        if not data:
            return error_response("Invalid request data")

        subscription_json = data.get("subscription")
        if not subscription_json:
            current_app.logger.warning("Empty subscription data received")
            return error_response("Empty subscription data")

        # Validate subscription JSON
        if not isinstance(subscription_json, dict) or 'endpoint' not in subscription_json:
            current_app.logger.warning(f"Invalid subscription format: {subscription_json}")
            return error_response("Invalid subscription format")

        # Get user's team number
        user_team = await team_manager.get_user_team(current_user.get_id())
        team_number = user_team.team_number if user_team else None

        if existing := current_app.mongo.db.notification_subscriptions.find_one(
            {"user_id": current_user.get_id()}
        ):
            # Update existing subscription
            current_app.mongo.db.notification_subscriptions.update_one(
                {"user_id": current_user.get_id()},
                {"$set": {
                    "subscription_json": subscription_json,
                    "updated_at": datetime.now(),
                    "team_number": team_number
                }}
            )
        else:
            # Create new subscription
            subscription = NotificationSubscription({
                "user_id": current_user.get_id(),
                "team_number": team_number,
                "subscription_json": subscription_json,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "default_reminder_time": 1440,  # Default: 1 day
                "enable_all_notifications": False,
                "assignment_subscriptions": []
            })

            current_app.mongo.db.notification_subscriptions.insert_one(
                subscription.to_dict()
            )

        return success_response("Subscription successful")
    except Exception as e:
        current_app.logger.error(f"Error subscribing to push: {e}")
        return error_response(f"Error subscribing to push: {str(e)}")

@team_bp.route("/notifications/resubscribe", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def resubscribe_to_push():
    """Resubscribe a user to push notifications (refreshes expired subscription)"""
    try:
        data = request.get_json()
        if not data:
            return error_response("Invalid request data")

        subscription_json = data.get("subscription")
        if not subscription_json:
            current_app.logger.warning("Empty subscription data received")
            return error_response("Empty subscription data")

        # Validate subscription JSON
        if not isinstance(subscription_json, dict) or 'endpoint' not in subscription_json:
            current_app.logger.warning(f"Invalid subscription format: {subscription_json}")
            return error_response("Invalid subscription format")

        # Get user's existing subscription
        existing = current_app.mongo.db.notification_subscriptions.find_one(
            {"user_id": current_user.get_id()}
        )

        if existing:
            # Keep the user's preferences but update the subscription data
            current_app.mongo.db.notification_subscriptions.update_one(
                {"user_id": current_user.get_id()},
                {"$set": {
                    "subscription_json": subscription_json,
                    "updated_at": datetime.now(),
                }}
            )
            
            current_app.logger.info(f"Resubscribed user {current_user.get_id()} with new push subscription")
            
            # Reschedule any pending notifications that failed
            failed_notifications = current_app.mongo.db.scheduled_notifications.find({
                "user_id": current_user.get_id(),
                "sent": True,
                "status": "failed",
                "error": {"$regex": "expired"}
            })
            
            for notification in failed_notifications:
                # Only reschedule if it's less than 24 hours old
                if notification.get("scheduled_time") > datetime.now() - timedelta(hours=24):
                    # Create a new notification with the same data but scheduled for now + 1 minute
                    new_notification = notification.copy()
                    del new_notification["_id"]  # Remove the old ID
                    del new_notification["sent"]
                    del new_notification["status"]
                    del new_notification["error"]
                    if "sent_at" in new_notification:
                        del new_notification["sent_at"]
                    
                    new_notification["scheduled_time"] = datetime.now() + timedelta(minutes=1)
                    new_notification["created_at"] = datetime.now()
                    
                    current_app.mongo.db.scheduled_notifications.insert_one(new_notification)
                    current_app.logger.info(f"Rescheduled failed notification {notification['_id']} for user {current_user.get_id()}")
            
            return success_response("Resubscription successful")
        else:
            # No existing subscription, create new
            return subscribe_to_push()

    except Exception as e:
        current_app.logger.error(f"Error resubscribing to push: {e}")
        return error_response(f"Error resubscribing to push: {str(e)}")

@team_bp.route("/<int:team_number>/notifications/settings", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per minute")
@async_route
async def notification_settings(team_number):
    """Get or update notification settings"""
    try:
        # Check if user is a member of the team
        team = await team_manager.get_team_by_number(team_number)
        
        if not team or current_user.get_id() not in team.users:
            return error_response("You are not a member of this team")
        
        if request.method == "GET":
            # Get user's notification settings
            subscription = current_app.mongo.db.notification_subscriptions.find_one({
                "user_id": current_user.get_id()
            })
            
            if not subscription:
                return success_response("No notification settings found", {
                    "settings": {
                        "defaultReminderTime": 1440,
                        "enableAllNotifications": False
                    }
                })
            
            return success_response("Notification settings retrieved", {
                "settings": {
                    "defaultReminderTime": subscription.get("default_reminder_time", 1440),
                    "enableAllNotifications": subscription.get("enable_all_notifications", False)
                }
            })
        else:  # POST
            data = request.get_json()
            if not data:
                return error_response("Invalid settings data")
            
            default_reminder_time = int(data.get("defaultReminderTime", 1440))
            enable_all_notifications = data.get("enableAllNotifications", False)
            
            # Update user's notification settings
            current_app.mongo.db.notification_subscriptions.update_one(
                {"user_id": current_user.get_id()},
                {"$set": {
                    "default_reminder_time": default_reminder_time,
                    "enable_all_notifications": enable_all_notifications,
                    "updated_at": datetime.now()
                }},
                upsert=True
            )
            
            return success_response("Notification settings updated")
    except Exception as e:
        current_app.logger.error(f"Error handling notification settings: {e}")
        return error_response(f"Error handling notification settings: {str(e)}")

@team_bp.route("/<int:team_number>/notifications/subscribe-all", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
@async_route
async def subscribe_to_all_assignments(team_number):
    """Subscribe to all assignments for a team"""
    try:
        # Check if user is a member of the team
        team = await team_manager.get_team_by_number(team_number)
        
        if not team or current_user.get_id() not in team.users:
            return error_response("You are not a member of this team")
        
        data = request.get_json()
        reminder_time = int(data.get("reminderTime", 1440))
        
        # Get all assignments for the team that the user is assigned to
        assignments = current_app.mongo.db.assignments.find({
            "team_number": team_number,
            "assigned_to": current_user.get_id()
        })
        
        # Get user's notification subscription
        subscription = current_app.mongo.db.notification_subscriptions.find_one({
            "user_id": current_user.get_id()
        })
        
        if not subscription:
            # Create new subscription
            subscription = NotificationSubscription({
                "user_id": current_user.get_id(),
                "team_number": team_number,
                "subscription_json": {},
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "default_reminder_time": reminder_time,
                "enable_all_notifications": True,
                "assignment_subscriptions": []
            })
            
            current_app.mongo.db.notification_subscriptions.insert_one(
                subscription.to_dict()
            )
        else:
            # Update existing subscription
            current_app.mongo.db.notification_subscriptions.update_one(
                {"user_id": current_user.get_id()},
                {"$set": {
                    "default_reminder_time": reminder_time,
                    "enable_all_notifications": True,
                    "updated_at": datetime.now()
                }}
            )
        
        # Schedule notifications for all assignments
        for assignment in assignments:
            due_date = assignment.get("due_date")
            if not due_date:
                continue
            
            notification_time = due_date - timedelta(minutes=reminder_time)
            
            # If notification time is in the past, skip
            if notification_time <= datetime.now():
                continue
            
            # Check if notification is already scheduled
            existing_notification = current_app.mongo.db.scheduled_notifications.find_one({
                "user_id": current_user.get_id(),
                "assignment_id": str(assignment["_id"]),
                "sent": False
            })
            
            if existing_notification:
                continue
            
            # Schedule the notification
            notification = {
                "user_id": current_user.get_id(),
                "team_number": team_number,
                "assignment_id": str(assignment["_id"]),
                "title": f"Assignment Reminder: {assignment.get('title')}",
                "body": f"Due {due_date.strftime('%Y-%m-%d %I:%M %p')}",
                "scheduled_time": notification_time,
                "created_at": datetime.now(),
                "sent": False,
                "url": f"/team/{team_number}/manage",
                "data": {
                    "assignmentId": str(assignment["_id"]),
                    "teamNumber": team_number
                }
            }
            
            current_app.mongo.db.scheduled_notifications.insert_one(notification)
        
        return success_response("Subscribed to all assignments")
    except Exception as e:
        current_app.logger.error(f"Error subscribing to all assignments: {e}")
        return error_response(f"Error subscribing to all assignments: {str(e)}")

@team_bp.route("/assignments/<assignment_id>/subscribe", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
@async_route
async def subscribe_to_assignment(assignment_id):
    """Subscribe to a specific assignment"""
    try:
        current_app.logger.info(f"User {current_user.get_id()} subscribing to assignment {assignment_id}")
        
        # Get the assignment
        assignment = current_app.mongo.db.assignments.find_one({
            "_id": ObjectId(assignment_id)
        })
        
        if not assignment:
            current_app.logger.warning(f"Assignment {assignment_id} not found")
            return error_response("Assignment not found")
        
        # Check if user is assigned to this assignment
        if current_user.get_id() not in assignment.get("assigned_to", []):
            current_app.logger.warning(f"User {current_user.get_id()} not assigned to assignment {assignment_id}")
            return error_response("You are not assigned to this assignment")
        
        data = request.get_json()
        current_app.logger.debug(f"Received data: {data}")
        
        if not data or "reminderTime" not in data:
            current_app.logger.warning(f"Missing reminderTime in request data: {data}")
            return error_response("Missing reminder time")
            
        try:
            reminder_time = int(data.get("reminderTime", 1440))
            current_app.logger.debug(f"Reminder time: {reminder_time}")
        except (ValueError, TypeError) as e:
            current_app.logger.error(f"Invalid reminder time format: {data.get('reminderTime')}, error: {e}")
            return error_response(f"Invalid reminder time format: {str(e)}")
        
        # Get user's notification subscription
        subscription = current_app.mongo.db.notification_subscriptions.find_one({
            "user_id": current_user.get_id()
        })
        
        if not subscription:
            # Create new subscription
            subscription = NotificationSubscription({
                "user_id": current_user.get_id(),
                "team_number": assignment.get("team_number"),
                "subscription_json": {},
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "default_reminder_time": reminder_time,
                "enable_all_notifications": False,
                "assignment_subscriptions": [{
                    "assignment_id": assignment_id,
                    "reminder_time": reminder_time
                }]
            })
            
            current_app.mongo.db.notification_subscriptions.insert_one(
                subscription.to_dict()
            )
        else:
            # Update existing subscription
            subscription_obj = NotificationSubscription.create_from_db(subscription)
            subscription_obj.add_assignment_subscription(assignment_id, reminder_time)
            
            current_app.mongo.db.notification_subscriptions.update_one(
                {"user_id": current_user.get_id()},
                {"$set": {
                    "assignment_subscriptions": subscription_obj.assignment_subscriptions,
                    "updated_at": datetime.now()
                }}
            )
        
        # Schedule the notification
        due_date = assignment.get("due_date")
        current_app.logger.debug(f"Assignment due date: {due_date}, type: {type(due_date)}")
        
        if due_date:
            # Ensure due_date is a datetime object
            if isinstance(due_date, str):
                current_app.logger.debug(f"Converting string due date to datetime: {due_date}")
                try:
                    due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                    current_app.logger.debug(f"Converted using fromisoformat: {due_date}")
                except ValueError as e:
                    current_app.logger.warning(f"Failed to parse with fromisoformat: {e}")
                    # Try another format if ISO format fails
                    try:
                        due_date = datetime.strptime(due_date, '%Y-%m-%dT%H:%M:%S.%f')
                        current_app.logger.debug(f"Converted using strptime with milliseconds: {due_date}")
                    except ValueError as e:
                        current_app.logger.warning(f"Failed to parse with strptime (ms format): {e}")
                        try:
                            due_date = datetime.strptime(due_date, '%Y-%m-%d %H:%M:%S')
                            current_app.logger.debug(f"Converted using strptime without milliseconds: {due_date}")
                        except ValueError as e:
                            current_app.logger.error(f"All date parsing attempts failed: {e}")
                            return error_response("Invalid due date format")
            
            # Now we can safely subtract
            current_app.logger.debug(f"Final due_date: {due_date}, type: {type(due_date)}")
            notification_time = due_date - timedelta(minutes=reminder_time)
            current_app.logger.debug(f"Calculated notification time: {notification_time}")
            
            # If notification time is in the past, skip
            now = datetime.now()
            current_app.logger.debug(f"Current time: {now}")
            if notification_time <= now:
                current_app.logger.info(f"Notification time {notification_time} is in the past (current time: {now})")
                return success_response("Assignment due date is too soon for notification")
            
            # Check if notification is already scheduled
            existing_notification = current_app.mongo.db.scheduled_notifications.find_one({
                "user_id": current_user.get_id(),
                "assignment_id": assignment_id,
                "sent": False
            })
            
            if not existing_notification:
                # Schedule the notification
                notification = {
                    "user_id": current_user.get_id(),
                    "team_number": assignment.get("team_number"),
                    "assignment_id": assignment_id,
                    "title": f"Assignment Reminder: {assignment.get('title')}",
                    "body": f"Due {due_date.strftime('%Y-%m-%d %I:%M %p')}",
                    "scheduled_time": notification_time,
                    "created_at": datetime.now(),
                    "sent": False,
                    "url": f"/team/{assignment.get('team_number')}/manage",
                    "data": {
                        "assignmentId": assignment_id,
                        "teamNumber": assignment.get("team_number")
                    }
                }
                
                current_app.logger.info(f"Scheduling notification for assignment {assignment_id} at {notification_time}")
                current_app.mongo.db.scheduled_notifications.insert_one(notification)
        
        return success_response("Subscribed to assignment")
    except Exception as e:
        current_app.logger.error(f"Error subscribing to assignment: {e}")
        return error_response(f"Error subscribing to assignment: {str(e)}")

@team_bp.route("/notifications/test", methods=["GET", "POST"])
@login_required
@limiter.limit("10 per minute")
def test_notification():
    """Test route for notifications - sends an actual test notification"""
    vapid_key = current_app.config.get("VAPID_PUBLIC_KEY", "")
    vapid_private = current_app.config.get("VAPID_PRIVATE_KEY", "")
    
    # For GET requests, just return the configuration info
    if request.method == "GET":
        return jsonify({
            "success": True,
            "message": "Notification test route",
            "vapid_key_length": len(vapid_key) if vapid_key else 0,
            "vapid_private_length": len(vapid_private) if vapid_private else 0,
            "has_vapid_key": bool(vapid_key),
            "has_vapid_private": bool(vapid_private),
            "user_id": current_user.get_id(),
            "notification_support": {
                "mongo_collections": list(current_app.mongo.db.list_collection_names())
            }
        })
    
    # For POST requests, send an actual test notification
    try:
        # Get the user's subscription
        subscription = current_app.mongo.db.notification_subscriptions.find_one({
            "user_id": current_user.get_id()
        })
        
        if not subscription or not subscription.get("subscription_json"):
            current_app.logger.warning(f"No subscription found for user {current_user.get_id()}")
            return jsonify({
                "success": False,
                "message": "No notification subscription found for this user. Please enable notifications first."
            }), 400
            
        # Send a test push notification
        try:
            from pywebpush import webpush, WebPushException
            
            current_app.logger.info(f"Sending test notification to user {current_user.get_id()}")
            
            webpush(
                subscription_info=subscription["subscription_json"],
                data=jsonify({
                    "title": "Test Notification",
                    "body": "This is a test notification from the Scouting App!",
                    "url": "/team/manage",
                    "timestamp": int(datetime.now().timestamp() * 1000)
                }).get_data(as_text=True),
                vapid_private_key=vapid_private,
                vapid_claims={"sub": current_app.config.get("VAPID_SUBJECT", f"mailto:{current_app.config.get('MAIL_DEFAULT_SENDER', 'test@example.com')}")}
            )
            
            return jsonify({
                "success": True,
                "message": "Test notification sent successfully"
            })
            
        except WebPushException as e:
            current_app.logger.error(f"WebPush error: {e}")
            return jsonify({
                "success": False,
                "message": f"Error sending notification: {str(e)}",
                "error_details": {
                    "status_code": e.response.status_code if hasattr(e, 'response') and e.response else None,
                    "message": str(e)
                }
            }), 500
            
    except Exception as e:
        current_app.logger.error(f"Error in test notification: {e}")
        return jsonify({
            "success": False,
            "message": f"Server error: {str(e)}"
        }), 500

@team_bp.route("/notifications/status", methods=["GET"])
@login_required
def notification_status():
    """Get the notification status for the current user"""
    try:
        # Check if the user has a subscription
        subscription = current_app.mongo.db.notification_subscriptions.find_one({
            "user_id": current_user.get_id()
        })
        
        # Return the status
        return jsonify({
            "success": True,
            "hasSubscription": bool(subscription and subscription.get("subscription_json")),
            "permissionStatus": "granted" if subscription and subscription.get("subscription_json") else "default",
            "enabledAssignments": subscription.get("assignment_subscriptions", []) if subscription else []
        })
    except Exception as e:
        current_app.logger.error(f"Error checking notification status: {e}")
        return jsonify({
            "success": False,
            "hasSubscription": False,
            "permissionStatus": "default",
            "message": f"Error checking notification status: {str(e)}"
        }), 500

@team_bp.route("/notifications/debug", methods=["GET"])
@login_required
def debug_notifications():
    """Debug route to check scheduled notifications"""
    # if not current_user.is_admin:
    #     return jsonify({"success": False, "message": "Unauthorized"}), 403
        
    try:
        # Get pending notifications for current user
        pending_notifications = list(current_app.mongo.db.scheduled_notifications.find({
            "user_id": current_user.get_id(),
            "sent": False
        }))
        
        # Get sent notifications for current user
        sent_notifications = list(current_app.mongo.db.scheduled_notifications.find({
            "user_id": current_user.get_id(),
            "sent": True
        }).sort("sent_at", -1).limit(10))
        
        # Convert ObjectIds to strings for JSON serialization
        for notification in pending_notifications + sent_notifications:
            notification["_id"] = str(notification["_id"])
            if isinstance(notification.get("scheduled_time"), datetime):
                notification["scheduled_time_str"] = notification["scheduled_time"].strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(notification.get("sent_at"), datetime):
                notification["sent_at_str"] = notification["sent_at"].strftime("%Y-%m-%d %H:%M:%S")
        
        return jsonify({
            "success": True,
            "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pending_count": len(pending_notifications),
            "sent_count": len(sent_notifications),
            "pending_notifications": pending_notifications,
            "sent_notifications": sent_notifications
        })
        
    except Exception as e:
        current_app.logger.error(f"Error debugging notifications: {e}")
        return jsonify({
            "success": False,
            "message": f"Error debugging notifications: {str(e)}"
        }), 500
