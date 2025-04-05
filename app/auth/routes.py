from __future__ import annotations

import asyncio
import os
from functools import wraps
from urllib.parse import urljoin, urlparse
import hashlib

from bson import ObjectId
from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, send_file, url_for)
from flask_login import current_user, login_required, login_user, logout_user
from flask_pymongo import PyMongo
from werkzeug.utils import secure_filename

from app.auth.auth_utils import UserManager
from app.utils import (async_route, handle_route_errors, is_safe_url, limiter,
                       send_gridfs_file, get_gridfs)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_profile_picture(file):
    """Save profile picture to GridFS"""
    if file and allowed_file(file.filename):
        return get_gridfs().put(
            file.stream.read(),
            filename=secure_filename(file.filename),
            content_type=file.content_type,
        )
    return None

def send_profile_picture(file_id):
    """Retrieve profile picture from GridFS"""
    try:
        # Convert string ID to ObjectId if necessary
        if isinstance(file_id, str):
            file_id = ObjectId(file_id)
            
        # Get the file from GridFS
        file_data = get_gridfs().get(file_id)
        
        return send_file(
            file_data,
            mimetype=file_data.content_type,
            download_name=file_data.filename
        )
    except Exception as e:
        # Log the error and return default profile picture
        print(f"Error retrieving profile picture: {e}")
        return send_file("static/images/default_profile.png")


def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def async_route(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return run_async(f(*args, **kwargs))

    return wrapper


auth_bp = Blueprint("auth", __name__)
user_manager = None
mongo = None


@auth_bp.record
def on_blueprint_init(state):
    global user_manager, mongo
    app = state.app
    mongo = PyMongo(app)
    
    # Create the UserManager with the singleton connection
    user_manager = UserManager(app.config["MONGO_URI"])
    
    # Store in app context for proper cleanup
    if not hasattr(app, 'db_managers'):
        app.db_managers = {}
    app.db_managers['auth'] = user_manager


def is_safe_url(target):
    if not target:
        return False

    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))

    return (
        test_url.scheme in ('http', 'https')
        and ref_url.netloc == test_url.netloc
        and all(c not in target for c in ['\\', '//', '..'])
    )


@auth_bp.route("/login", methods=["GET", "POST"])
# @limiter.limit("8 per minute")
@async_route
@handle_route_errors
async def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        login = request.form.get("login", "").strip()
        password = request.form.get("password", "").strip()
        remember = bool(request.form.get("remember", False))
        team_passcode = request.form.get("team_passcode", "").strip()

        if not login or not password or not team_passcode:
            current_app.logger.info(f"Invalid login, password, or team access code {login}, {password}, {team_passcode} for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
            flash("Please provide login, password, and team access code", "error")
            return render_template("auth/login.html", form_data={"login": login})
            
        # Verify the team access code by comparing hashes
        hashed_passcode = hashlib.sha256(team_passcode.encode()).hexdigest()
        if hashed_passcode != current_app.config.get("TEAM_ACCESS_CODE_HASH"):
            current_app.logger.info(f"Invalid team access code {team_passcode} for user {current_user.username if current_user.is_authenticated else "Anonymous"}")
            flash("Invalid team access code. This application is restricted to Team 334 members only.", "error")
            return render_template("auth/login.html", form_data={"login": login})

        success, user = await user_manager.authenticate_user(login, password)
        if success and user:
            current_app.logger.info(f"Successfully authenticated user {user.username} for user {current_user.username if current_user.is_authenticated else "Anonymous"}")
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            if not next_page or not is_safe_url(next_page):
                next_page = url_for('index')

            flash("Successfully logged in", "success")
            return redirect(next_page)
        
        current_app.logger.info(f"Failed to authenticate user {login} for user {current_user.username if current_user.is_authenticated else "Anonymous"}")
        flash("Invalid login credentials", "error")

    return render_template("auth/login.html", form_data={})


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("8 per minute")
@async_route
async def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    form_data = {}
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        team_passcode = request.form.get("team_passcode", "").strip()

        form_data = {"email": email, "username": username}
        
        # Verify the team access code by comparing hashes
        hashed_passcode = hashlib.sha256(team_passcode.encode()).hexdigest()
        if hashed_passcode != current_app.config.get("TEAM_ACCESS_CODE_HASH"):
            current_app.logger.info(f"Invalid team access code {team_passcode} for user {current_user.username if current_user.is_authenticated else "Anonymous"}")
            flash("Invalid team access code. This application is restricted to Team 334 members only.", "error")
            return render_template("auth/register.html", form_data=form_data)

        if not all([email, username, password, confirm_password, team_passcode]):
            current_app.logger.info(f"All fields are required {email}, {username}, {password}, {confirm_password}, {team_passcode} for user {current_user.username if current_user.is_authenticated else "Anonymous"}")
            flash("All fields are required", "error")
            return render_template("auth/register.html", form_data=form_data)

        if password != confirm_password:
            current_app.logger.info(f"Passwords do not match {password} != {confirm_password} for user {current_user.username if current_user.is_authenticated else "Anonymous"}")
            flash("Passwords do not match", "error")
            return render_template("auth/register.html", form_data=form_data)

        try:
            success, message = await user_manager.create_user(
                email=email,
                username=username,
                password=password
            )
            if success:
                current_app.logger.info(f"Successfully registered user {username} for user {current_user.username if current_user.is_authenticated else "Anonymous"}")
                flash("Registration successful! Please login.", "success")
                return redirect(url_for("auth.login"))
            flash(message, "error")
        except Exception as e:
            current_app.logger.error(f"An internal error has occurred: {str(e)}", exc_info=True)
            flash("An internal error has occurred.", "error")

    return render_template("auth/register.html", form_data=form_data)


@auth_bp.route("/logout")
@login_required
def logout():
    current_app.logger.info(f"Successfully logged out user {current_user.username if current_user.is_authenticated else "Anonymous"}")
    logout_user()
    flash("Successfully logged out", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/settings", methods=["GET", "POST"])
@limiter.limit("15 per minute")
@login_required
@async_route
async def settings():
    try:
        if request.method == "POST":
            # Handle form submission
            form_data = request.form
            file = request.files.get("profile_picture")
            
            success = await user_manager.update_user_settings(
                current_user.get_id(),
                form_data,
                file
            )
            
            if success:
                current_app.logger.info(f"Successfully updated settings for user {current_user.username if current_user.is_authenticated else "Anonymous"}")
                flash("Settings updated successfully", "success")
            else:
                current_app.logger.info(f"Failed to update settings for user {current_user.username if current_user.is_authenticated else "Anonymous"}")
                flash("Unable to update settings", "error")
                
        return render_template("auth/settings.html")
    except Exception as e:
        current_app.logger.error(f"Error in settings: {str(e)}", exc_info=True)
        flash("An error occurred while processing your request", "error")
        return redirect(url_for("auth.settings"))


@auth_bp.route("/profile/<username>")
def profile(username):
    user = user_manager.get_user_profile(username)
    if not user:
        flash("User not found", "error")
        current_app.logger.info(f"User not found {username} for user {current_user.username if current_user.is_authenticated else "Anonymous"}")
        return redirect(url_for("index"))
    
    return render_template("auth/profile.html", profile_user=user)


@auth_bp.route("/profile/picture/<user_id>")
def profile_picture(user_id):
    """Get user's profile picture"""
    user = user_manager.get_user_by_id(user_id)
    if not user or not user.profile_picture_id:
        return send_file(os.path.join(current_app.root_path, "static", "images", "default_profile.png"))
    
    return send_gridfs_file(
        user.profile_picture_id,
        user_manager.db,
        "static/images/default_profile.png"
    )


@auth_bp.route("/check_username", methods=["POST"])
@login_required
@async_route
async def check_username():
    """Check if a username is available"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        current_app.logger.info(f"Checking username {username} for user {current_user.username if current_user.is_authenticated else "Anonymous"}")

        # Don't query if it's the user's current username
        if username == current_user.username and current_user.is_authenticated:
            return jsonify({"available": True})
        
        # Check if username exists in database
        existing_user = user_manager.db.users.find_one({"username": username})
        current_app.logger.info(f'Tried to check username {username} for user {current_user.username if current_user.is_authenticated else "Anonymous"} Status: {not existing_user}')
        return jsonify({
            "available": not existing_user
        })
    except Exception as e:
        current_app.logger.error(f'Error checking username {username} for user {current_user.username if current_user.is_authenticated else "Anonymous"} {str(e)}', exc_info=True)
        return jsonify({
            "available": False,
            "error": "An internal error has occurred."
        }), 500


@auth_bp.route("/delete_account", methods=["POST"])
@login_required
@async_route
async def delete_account():
    """Delete user account"""
    try:
        # Create a UserManager with the singleton connection
        user_manager = UserManager(current_app.config["MONGO_URI"])
        success, message = await user_manager.delete_user(current_user.get_id())

        if success:
            logout_user()
            current_app.logger.info(f'Successfully deleted account for user {current_user.username if current_user.is_authenticated else "Anonymous"}')
            flash("Your account has been successfully deleted", "success")
            return jsonify({"success": True, "redirect": url_for("index")})
        else:
            current_app.logger.info(f'Failed to delete account for user {current_user.username if current_user.is_authenticated else "Anonymous"}')
            flash(message, "error")
            return jsonify({"success": False, "message": message})

    except Exception as e:
        current_app.logger.error(f'Error deleting account for user {current_user.username if current_user.is_authenticated else "Anonymous"} {str(e)}', exc_info=True)
        return jsonify({"success": False, "message": "An internal error has occurred."})
