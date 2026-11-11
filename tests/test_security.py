"""App-level security settings through create_app(); MongoDB and background services are mocked."""
import os
import unittest
from types import SimpleNamespace
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

    def test_uploaded_images_are_served_only_as_safe_image_types(self):
        """Uploads keep the client's Content-Type; HTML or SVG must never be served inline from our origin."""
        client, _ = self.client()
        payload = b"<script>alert(document.domain)</script>"
        for content_type, served in (("text/html", False), ("image/svg+xml", False), ("image/png", True)):
            stored = SimpleNamespace(content_type=content_type, filename="x.png", read=lambda: payload)
            # Patch both lookups so the test still bites if team_logo ever serves GridFS files itself again.
            with patch("app.team.routes.team_manager") as manager, patch("app.utils.get_gridfs") as gridfs, \
                    patch("app.team.routes.get_gridfs", gridfs):
                manager.db.teams.find_one.return_value = {"logo_id": USER_ID}
                gridfs.return_value.get.return_value = stored
                response = client.get("/team/team/334/logo")
            self.assertNotIn(response.mimetype, ("text/html", "image/svg+xml"), content_type)
            self.assertEqual(response.get_data() == payload, served, content_type)
            if served:
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_scouter_join_exposes_only_public_fields(self):
        """Aggregates push $$ROOT to the browser, so the joined user must never carry password_hash or email."""
        from app.scout.scouting_utils import SCOUTER_LOOKUP
        self.assertEqual(SCOUTER_LOOKUP["$lookup"]["pipeline"][-1],
                         {"$project": {"_id": 1, "username": 1, "teamNumber": 1}})

    def test_compare_api_is_served_as_json_not_html(self):
        """Scouting notes in /api/compare must not render as HTML when the URL is opened directly."""
        client, _ = self.client()
        stats = dict.fromkeys(["avg_auto_fuel", "avg_endgame_fuel", "avg_climb_level", "climb_success_rate",
                               "defense_rating", *(f"avg_teleop_shift_{n}_fuel" for n in range(1, 5))], 0)
        stats["matches"] = [{"notes": "<img src=x onerror=alert(1)>"}]
        with patch("app.scout.routes.common.scouting_manager") as manager, \
                patch("app.scout.routes.lighthouse.TBAInterface") as tba:
            manager.get_compare_stats.return_value = stats
            tba.return_value.get_team.return_value = {"nickname": "Test"}
            response = client.get("/api/compare?team1=1&team2=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")

    def test_missing_secret_key_refuses_to_start(self):
        from app.app import create_app
        with patch.dict(os.environ, {"SECRET_KEY": ""}), patch("app.app.load_dotenv"):
            with self.assertRaisesRegex(RuntimeError, "SECRET_KEY"):
                create_app()


if __name__ == '__main__':
    unittest.main()
