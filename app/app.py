import logging
import os
import traceback
from time import strftime
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import (Flask, flash, jsonify, make_response, redirect,
                   render_template, request, send_from_directory, url_for)
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.exceptions import HTTPException

from app.auth.auth_utils import UserManager
from app.utils import is_safe_url, limiter

csrf = CSRFProtect()
login_manager = LoginManager()

logger = logging.getLogger(__name__)

def create_app():
    app: Flask = Flask(__name__, static_folder="static", template_folder="templates")

    # Load config
    load_dotenv()
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        # Sessions are signed with this key; a public default lets anyone forge a login.
        raise RuntimeError(
            "SECRET_KEY is not set. Add it to the environment or .env, e.g. "
            "SECRET_KEY=$(python -c \"import secrets; print(secrets.token_hex(32))\")")
    app.config.update(
        SECRET_KEY=secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SECURE=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
        WTF_CSRF_ENABLED=True,
        # Scouting pages stay open all event and queue submissions offline; a
        # token is valid for the whole session rather than expiring after an hour.
        WTF_CSRF_TIME_LIMIT=None,
        MONGO_URI=os.getenv("MONGO_URI", "mongodb://localhost:27017/scouting_app"),
        RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI")
            or os.getenv("MONGO_URI", "mongodb://localhost:27017/scouting_app"),
        VAPID_PUBLIC_KEY=os.getenv("VAPID_PUBLIC_KEY", ""),
        VAPID_PRIVATE_KEY=os.getenv("VAPID_PRIVATE_KEY", ""),
        VAPID_CLAIM_EMAIL=os.getenv("VAPID_CLAIM_EMAIL", "team334@gmail.com")
    )
    
    if not app.config.get("VAPID_PUBLIC_KEY") or not app.config.get("VAPID_PRIVATE_KEY"):
        app.logger.warning("VAPID keys not configured. Push notifications will not work.")
    else:
        app.logger.info("VAPID keys configured properly.")

    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "error"

    # First DatabaseManager opens the singleton connection with MONGO_URI
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

    # Import blueprints inside create_app to avoid circular imports
    from app.auth.routes import auth_bp
    from app.notifications.routes import notifications_bp
    from app.scout.routes import scouting_bp
    from app.team.routes import team_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(scouting_bp, url_prefix="/")
    app.register_blueprint(team_bp, url_prefix="/team")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")

    # The service worker's "mark complete" notification action cannot read the
    # page's CSRF token. The route only accepts JSON, which browsers will not
    # send cross-site without a CORS preflight this app never grants.
    csrf.exempt("app.team.routes.update_assignment_status")

    @app.route("/")
    def index():
        return render_template("index.html")
    
    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html")

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error(f"Server error: {str(e)} - User: {current_user.username if current_user.is_authenticated else 'Anonymous'}", exc_info=True)
        return render_template("500.html"), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            # 400/405/415 etc. are client errors with their own responses, not crashes
            return e
        trace = traceback.format_exc()
        timestamp = strftime('[%Y-%b-%d %H:%M]')
        app.logger.error(f"{timestamp} User: {current_user.username if current_user.is_authenticated else 'Anonymous'} Unhandled exception: {str(e)}\nTraceback: {trace}", exc_info=True)
        return render_template("500.html"), 500
    
    @app.errorhandler(CSRFError)
    def csrf_error(e):
        app.logger.warning(f"CSRF rejected {request.method} {request.path}: {e.description}")
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "message": "Your session expired. Reload the page and try again."}), 400
        flash("Your session expired. Please try again.", "error")
        return redirect(url_for("index"))

    @app.errorhandler(429)
    def rate_limit_error(e):
        return render_template("429.html"), 429

    @app.before_request
    def check_team_access():
        """
        Basic protection to restrict access to authenticated users.
        """
        # Skip for static assets, authentication, and public routes
        if request.path.startswith('/static') or \
           request.path == '/' or \
           request.path == '/service-worker.js' or \
           request.path.startswith('/auth/login') or \
           request.path.startswith('/auth/register') or \
           request.path.startswith('/auth/forgot-password'):
            return
            
        # Block access for non-authenticated users to protected routes
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))

    @app.after_request
    def after_request(response): 
        timestamp = strftime('[%Y-%b-%d %H:%M]')
        logger.info('%s %s User: %s %s %s %s %s', timestamp, request.remote_addr, current_user.username if current_user.is_authenticated else 'Anonymous', request.method, request.scheme, request.full_path, response.status)
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

    return app

# if __name__ == "__main__":
#     app = create_app()

#     app.run()
