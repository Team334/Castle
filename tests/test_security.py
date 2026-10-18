"""App-level security settings through create_app(); MongoDB and background services are mocked."""
import os
import unittest
from unittest.mock import patch

from tests.app_harness import USER_ID, logged_in_client, start_app


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.patches = start_app()

    @classmethod
    def tearDownClass(cls):
        for item in reversed(cls.patches):
            item.stop()

    def client(self):
        return logged_in_client(self.app)

    def test_writes_without_token_are_rejected(self):
        client, token = self.client()
        with patch("app.team.routes.team_manager") as manager:
            self.assertEqual(client.post("/team/334/leave").status_code, 302)
            manager.leave_team.assert_not_called()
            response = client.post("/notifications/subscribe", json={}, headers={"X-Requested-With": "XMLHttpRequest"})
            self.assertEqual(response.status_code, 400)
            self.assertIn("session expired", response.json["message"])

    def test_form_field_and_header_tokens_are_accepted(self):
        client, token = self.client()
        with patch("app.team.routes.team_manager") as manager:
            manager.leave_team.return_value = (False, "nope")
            client.post("/team/334/leave", data={"csrf_token": token})
            manager.leave_team.assert_called_once()
        with patch("app.notifications.routes.notification_manager") as manager:
            manager.create_subscription.return_value = (True, "ok")
            response = client.post("/notifications/subscribe", json={"subscription": {"endpoint": "x"}},
                                   headers={"X-CSRFToken": token})
            self.assertNotEqual(response.status_code, 400)

    def test_service_worker_status_route_is_exempt_but_json_only(self):
        client, _ = self.client()
        with patch("app.team.routes.team_manager") as manager:
            manager.update_assignment_status.return_value = (True, "ok")
            self.assertEqual(client.put(f"/team/assignments/{USER_ID}/status", json={"status": "completed"}).status_code, 200)
            self.assertGreaterEqual(client.put(f"/team/assignments/{USER_ID}/status", data={"status": "completed"}).status_code, 400)

    def test_state_changing_routes_reject_get(self):
        client, _ = self.client()
        for path in (f"/scouting/delete/{USER_ID}", f"/scouting/pit/delete/{USER_ID}", "/team/334/leave"):
            self.assertEqual(client.get(path).status_code, 405, path)

    def test_session_cookies_are_same_site_and_no_wildcard_cors(self):
        for key in ("SESSION_COOKIE_SAMESITE", "REMEMBER_COOKIE_SAMESITE"):
            self.assertEqual(self.app.config[key], "Lax")
        self.assertIsNone(self.app.config["WTF_CSRF_TIME_LIMIT"])
        response = self.app.test_client().get("/", headers={"Origin": "https://evil.test"})
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_missing_secret_key_refuses_to_start(self):
        from app.app import create_app
        with patch.dict(os.environ, {"SECRET_KEY": ""}), patch("app.app.load_dotenv"):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
                create_app()


if __name__ == '__main__':
    unittest.main()
