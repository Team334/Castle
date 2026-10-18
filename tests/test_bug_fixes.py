"""Regression tests for notification, username-check and assignment fixes; MongoDB mocked."""
import threading
import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId

from app.notifications import routes as notification_routes
from app.notifications.notification_manager import NotificationManager
from tests.app_harness import logged_in_client, start_app


class BugFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.patches = start_app()

    @classmethod
    def tearDownClass(cls):
        for item in reversed(cls.patches):
            item.stop()

    def test_requests_do_not_stop_the_notification_worker(self):
        with patch.object(NotificationManager, "stop_notification_service") as stop:
            client, _ = logged_in_client(self.app)
            client.get("/")
            client.get("/scouting/matches")
            stop.assert_not_called()

    def test_creating_an_assignment_notifies_assignees(self):
        client, token = logged_in_client(self.app)
        assignment = {"_id": ObjectId(), "title": "Scout Q12", "assigned_to": ["u1"]}
        with patch("app.team.routes.team_manager") as teams, \
                patch.object(notification_routes, "notification_manager") as notifier:
            teams.create_or_update_assignment.return_value = (True, assignment)
            response = client.post("/team/334/assignments", json={"title": "Scout Q12"}, headers={"X-CSRFToken": token})
            self.assertEqual(response.status_code, 200)
            notifier.notify_assignment_created.assert_called_once_with(assignment, 334)
            teams.create_or_update_assignment.return_value = (False, "Only team admins can create assignments")
            response = client.post("/team/334/assignments", json={}, headers={"X-CSRFToken": token})
            self.assertEqual(response.json["message"], "Only team admins can create assignments")
            notifier.notify_assignment_created.assert_called_once()

    def test_notify_sends_on_a_background_thread(self):
        manager = NotificationManager.__new__(NotificationManager)
        sent = threading.Event()
        with patch.object(NotificationManager, "send_instant_assignment_notification",
                          side_effect=lambda *a: sent.set()) as send:
            manager.notify_assignment_created({"title": "t"}, 334)
            self.assertTrue(sent.wait(2))
            send.assert_called_once_with({"title": "t"}, 334)

    def test_username_check_handles_non_json_body(self):
        client, token = logged_in_client(self.app)
        with patch("app.auth.routes.user_manager", MagicMock()):
            response = client.post("/auth/check_username", data="x", headers={"X-CSRFToken": token})
        self.assertEqual(response.status_code, 200)
        self.assertIn("available", response.json)


if __name__ == '__main__':
    unittest.main()
