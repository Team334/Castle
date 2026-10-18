"""Build the real app via create_app() with MongoDB and background services mocked."""
import os
import re
from unittest.mock import MagicMock, patch

from bson import ObjectId

from app.models import User

USER_ID = "6ac99468539dec0f82df2c4e"
MOCKED = ("app.utils.MongoDB._connect", "app.utils.GridFS", "app.utils.MongoDB.get_db", "app.utils.MongoDB.get_client",
          "app.scout.match13_fuel.FuelEstimateService.start",
          "app.notifications.notification_manager.NotificationManager.start_notification_service")


def start_app():
    """Return (app, patches); stop the patches in tearDownClass."""
    patches = [patch(target, MagicMock()) for target in MOCKED]
    user = User.create_from_db({"_id": ObjectId(USER_ID), "username": "tester", "teamNumber": 334})
    patches.append(patch("app.auth.auth_utils.UserManager.get_user_by_id", return_value=user))
    patches.append(patch.dict(os.environ, {"SECRET_KEY": "test-only"}))
    for item in patches:
        item.start()
    from app.app import create_app
    app = create_app()
    app.config.update(RATELIMIT_ENABLED=False)
    return app, patches


def logged_in_client(app):
    """Test client with a session for USER_ID, plus the page's CSRF token."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = USER_ID
        session["_fresh"] = True
    page = client.get("/auth/settings").get_data(as_text=True)
    return client, re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)
