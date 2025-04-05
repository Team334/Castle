from __future__ import annotations

from io import BytesIO
from datetime import datetime

from bson import ObjectId
from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, send_file, url_for)
from flask_login import current_user, login_required
from PIL import Image
from werkzeug.utils import secure_filename

from app.team.team_utils import TeamManager
from app.utils import (allowed_file, async_route, error_response,
                       handle_route_errors, limiter, save_file_to_gridfs,
                       success_response, get_gridfs)

from .forms import CreateTeamForm

team_bp = Blueprint("team", __name__)
team_manager = None

@team_bp.record
def on_blueprint_init(state):
    global team_manager
    app = state.app
    
    # Create TeamManager with the singleton connection
    team_manager = TeamManager(app.config["MONGO_URI"])
    
    # Store in app context for proper cleanup
    if not hasattr(app, 'db_managers'):
        app.db_managers = {}
    app.db_managers['team'] = team_manager

@team_bp.route("/join", methods=["GET", "POST"])
@login_required
@async_route
async def join():
    try:
        if current_user.teamNumber:
            return redirect(url_for("team.manage"))

        if request.method == "POST":
            join_code = request.form.get("join_code")
            current_app.logger.info(f"Team.join Form Details {request.form}")

            if not join_code:
                flash("Join code is required", "error")
                return redirect(url_for("team.join"))

            success, result = await team_manager.join_team(current_user.get_id(), join_code)
            current_app.logger.info(f"Tried to join team ({success}) {join_code} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")

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
@limiter.limit("15 per minute")
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
                
                filename = secure_filename(
                    f"team_{form.team_number.data}_logo.png"
                )
                current_app.logger.debug(f"Uploading file: {filename}")
                logo_id = get_gridfs().put(
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
            current_app.logger.info(f"Tried to create team ({success}) {form.team_number.data} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")

            if success:
                flash("Team created successfully!", "success")
                return redirect(url_for("team.manage"))
            else:
                if logo_id:  # Clean up uploaded file if team creation failed
                    get_gridfs().delete(logo_id)
                flash(f"Error creating team: {result}", "error")

        except Exception as e:
            current_app.logger.error(f"Error in create_team route: {str(e)}")
            flash("An internal error has occurred.", "error")

    return render_template("team/create.html", form=form)


@team_bp.route("/<int:team_number>/leave", methods=["GET", "POST"])
@login_required
@limiter.limit("5 per minute")
@async_route
async def leave(team_number):
    """Leave a team"""

    success, message = await team_manager.leave_team(current_user.get_id(), team_number)

    current_app.logger.info(f"Tried to leave team ({success}) {team_number} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")

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

    current_app.logger.info(f"Tried to add admin ({success}) {user_id} to team {team_number} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}") 

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
    current_app.logger.info(f"Tried to remove admin ({success}) {user_id} from team {team_number} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")

    return jsonify({"success": success, "message": message}), 200 if success else 400


@team_bp.route("/<int:team_number>/assignments", methods=["POST"])
@login_required
# @limiter.limit("10 per minute")
@async_route
async def create_assignment(team_number):
    """Create a new assignment"""

    try:
        data = request.get_json()
        success, message = await team_manager.create_or_update_assignment(
            team_number, data, current_user.get_id()
        )

        current_app.logger.info(f"Tried to create assignment ({success}) for team {team_number} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")

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
# @limiter.limit("5 per minute")
def update_assignment_status(assignment_id):
    """Update assignment status"""

    data = request.get_json()
    new_status = data.get("status")

    if not new_status:
        return jsonify({"success": False, "message": "Status is required"}), 400

    success, message = team_manager.update_assignment_status(
        assignment_id, current_user.get_id(), new_status
    )
    current_app.logger.info(f"Tried to update assignment status ({success}) {assignment_id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
    return jsonify({"success": success, "message": message}), 200 if success else 400


@team_bp.route("/assignments/<assignment_id>/update", methods=["PUT"])
@login_required
# @limiter.limit("15 per minute")
@async_route
async def update_assignment(assignment_id):

    """Update assignment"""
    data = request.get_json()
    success, message = await team_manager.update_assignment(
        assignment_id, current_user.get_id(), data
    )
    current_app.logger.info(f"Tried to update assignment ({success}) {assignment_id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
    return jsonify({"success": success, "message": message}), 200 if success else 400


@team_bp.route("/assignments/<assignment_id>/delete", methods=["DELETE"])
@login_required
# @limiter.limit("10 per minute")
@async_route
async def delete_assignment(assignment_id):

    """Delete assignment"""
    success, message = await team_manager.delete_assignment(
        assignment_id, current_user.get_id()
    )
    current_app.logger.info(f"Tried to delete assignment ({success}) {assignment_id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
    return jsonify({"success": success, "message": message}), 200 if success else 400


@team_bp.route("/manage", methods=["GET", "POST"])
@team_bp.route("/manage/<int:team_number>", methods=["GET", "POST"])
@team_bp.route("/", methods=["GET", "POST"])
@login_required
# @limiter.limit("30 per minute")
@async_route
async def manage(team_number=None):
    """Manage team"""

    if not current_user.teamNumber:
        return redirect(url_for("team.join"))

    success, result = await team_manager.validate_user_team(
        current_user.get_id(), current_user.teamNumber
    )
    current_app.logger.info(f"Tried to validate user team ({success}) {current_user.teamNumber} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
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

    # Sort assignments by creation date (newest first) and split into two groups
    current_user_assignments = []
    other_assignments = []
    
    for assignment in sorted(assignments, key=lambda x: x.created_at if hasattr(x, 'created_at') else datetime.min, reverse=True):
        if hasattr(assignment, "assigned_to"):
            assignment.assigned_to = [str(user_id) for user_id in assignment.assigned_to]
            if str(current_user.get_id()) in assignment.assigned_to:
                current_user_assignments.append(assignment)
            else:
                other_assignments.append(assignment)

    # Combine the lists with user's assignments first
    sorted_assignments = current_user_assignments + other_assignments

    return render_template(
        "team/manage.html",
        team=team,
        current_user=current_user,
        team_members=team_members,
        user_dict=user_dict,
        assignments=sorted_assignments,
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
    current_app.logger.info(f"Tried to remove user ({success}) {user_id} from team {team_number} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
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
@limiter.limit("10 per minute")
@async_route
async def clear_assignments(team_number):
    """Clear all assignments for a team (admin only)"""

    success, message = await team_manager.clear_assignments(
        team_number, current_user.get_id()
    )
    current_app.logger.info(f"Tried to clear assignments ({success}) for team {team_number} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")

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
@limiter.limit("10 per minute")
@async_route
async def delete_team(team_number):
    """Delete team (owner only)"""
    success, message = await team_manager.delete_team(team_number, current_user.get_id())
    current_app.logger.info(f"Tried to delete team ({success}) {team_number} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")

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
        team = team_manager.db.teams.find_one({"team_number": team_number})
        
        if team and team.get("logo_id"):
            logo_id = ObjectId(team["logo_id"]) if isinstance(team["logo_id"], str) else team["logo_id"]
            logo = get_gridfs().get(logo_id)
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
        current_app.logger.info(f"Tried to edit assignment ({success}) {assignment_id} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")

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
    current_app.logger.info(f"Tried to update team logo ({success}) {team_number} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
    if not success:
        get_gridfs().delete(new_logo_id)
        
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
                    
                    # Clean up old logo and its chunks if it exists
                    if team.logo_id:
                        try:
                            # Delete old file and its chunks
                            get_gridfs().delete(team.logo_id)
                            # Also clean up any orphaned chunks
                            team_manager.db.fs.chunks.delete_many({"files_id": team.logo_id})
                        except Exception as e:
                            flash("An internal error has occurred.")
                    
                    filename = secure_filename(f"team_{team_number}_logo_{file.filename}")
                    file_id = get_gridfs().put(
                        file.stream.read(),
                        filename=filename,
                        content_type=file.content_type
                    )
                    updates['logo_id'] = file_id
                    current_app.logger.info(f"Tried to update team logo ({team_number}) for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
                else:
                    flash("Invalid file type. Please use PNG, JPG, or JPEG", "error")
                    return redirect(url_for("team.manage", team_number=team_number))
        

        # Handle description update
        description = request.form.get('description', '').strip()
        updates['description'] = description
        
        # Update team information
        success, message = await team_manager.update_team_info(team_number, updates)
        current_app.logger.info(f"Tried to update team info ({success}) {team_number} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        current_app.logger.info(f"Team.update_team_info Form Details {request.form}")
        flash(message, "success" if success else "error")
        return redirect(url_for("team.manage", team_number=team_number))
        

    except Exception as e:
        flash(f"Error updating team information: {str(e)}", "error")
        return redirect(url_for("team.manage", team_number=team_number))
