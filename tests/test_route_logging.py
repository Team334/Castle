"""Route log lines summarise results instead of dumping payloads; MongoDB and TBA mocked."""
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from bson import ObjectId

from app.scout.routes import common
from tests.app_harness import USER_ID, logged_in_client, start_app

SECRET = "payload-marker-should-not-be-logged"


class RouteLoggingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.patches = start_app()

    @classmethod
    def tearDownClass(cls):
        for item in reversed(cls.patches):
            item.stop()

    def setUp(self):
        self.client, self.token = logged_in_client(self.app)
        self.manager = MagicMock()
        team = {"_id": ObjectId(), "team_number": 334, "total_fuel": 1, "notes": SECRET}
        self.manager.get_team_leaderboard.return_value = [team]
        self.manager.get_leaderboard_events.return_value = []
        self.manager.get_scouter_leaderboard.return_value = [{"username": SECRET}]
        self.manager.get_event_codes.return_value = []
        self.manager.get_scouter_teams.return_value = []
        self.manager.get_compare_stats.return_value = {
            "avg_auto_fuel": 1, "avg_transition_fuel": 1, "avg_ferried_fuel": 1, "avg_teleop_shift_1_fuel": 1,
            "avg_teleop_shift_2_fuel": 1, "avg_teleop_shift_3_fuel": 1, "avg_teleop_shift_4_fuel": 1,
            "avg_endgame_fuel": 1, "avg_climb_level": 1, "climb_success_rate": 1, "defense_rating": 1,
            "matches": [{"notes": SECRET}]}
        self.manager.get_team_records.return_value = [{"notes": SECRET}]
        self.manager.get_auto_paths.return_value = [{"auto_notes": SECRET}]
        self.manager.get_all_pit_scouting.return_value = [{"notes": SECRET}]
        self.manager.get_pit_scouting_by_id.return_value = {"scouter_id": ObjectId(USER_ID)}
        self.manager.get_match_alliances.return_value = []
        self.manager.add_scouting_data.return_value = (True, str(ObjectId()))
        self.manager.get_team.return_value = None
        record = SimpleNamespace(scouter_id=USER_ID, scouter_team=334, fuel_estimate=None)
        self.manager.get_team_data.return_value = record
        self.manager.update_team_data.return_value = True
        self.patches = [patch.object(common, "scouting_manager", self.manager),
                        patch("app.scout.routes.lighthouse.TBAInterface"),
                        patch("app.scout.routes.events.TBAInterface", return_value=MagicMock(**{
                            "get_team_status_at_event.return_value": {"rank": SECRET},
                            "get_team_matches_at_event.return_value": {}})),
                        patch("app.scout.routes.records.render_template", return_value="ok"),
                        patch("app.scout.routes.pit.render_template", return_value="ok"),
                        patch("app.scout.routes.leaderboards.render_template", return_value="ok"),
                        patch("requests.get", return_value=SimpleNamespace(status_code=200, json=lambda: {"team_number": 334}))]
        for item in self.patches:
            item.start()
        self.app.extensions.pop("match13_fuel", None)

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def request(self, method, path, **kwargs):
        with self.assertLogs(self.app.logger, logging.INFO) as logs:
            response = self.client.open(path, method=method, headers={"X-CSRFToken": self.token}, **kwargs)
        self.assertLess(response.status_code, 500, path)
        text = "\n".join(logs.output)
        self.assertNotIn(SECRET, text, path)
        self.assertNotIn("Error", text, path)
        return text

    def test_reads_log_counts_not_results(self):
        self.assertIn("Fetched leaderboard: 1 teams", self.request("GET", "/leaderboard"))
        self.assertIn("Fetched scouter leaderboard: 1 scouters", self.request("GET", "/scouter-leaderboard"))
        self.assertIn("Compared teams ['1', '2']", self.request("GET", "/api/compare?team1=1&team2=2"))
        self.assertIn("Searched team 334: 1 records", self.request("GET", "/api/search?q=334"))
        self.assertIn("Fetched 1 auto paths for team 334", self.request("GET", "/api/team_paths?team=334"))
        self.assertIn("Fetched 1 pit scouting records", self.request("GET", "/scouting/pit"))
        self.assertIn("Fetched 0 matches", self.request("GET", "/scouting/matches"))
        self.assertIn("Fetched status for team 334 at 2026nyny",
                      self.request("GET", "/api/tba/team-status?team=334&event=2026nyny"))

    def test_writes_log_identity_not_form_contents(self):
        form = {"team_number": "334", "event_code": "2026NYNY", "match_number": "12", "notes": SECRET}
        self.assertIn("team 334 2026NYNY match 12", self.request("POST", "/scouting/add", data=form))
        self.assertIn("Updated scouting record", self.request("POST", f"/scouting/edit/{ObjectId()}", data=form))
        pit = {"team_number": "334", "notes": SECRET}
        self.assertIn("Added pit scouting for team 334", self.request("POST", "/scouting/pit/add", data=pit))
        self.assertIn("Updated pit scouting entry", self.request("POST", f"/scouting/pit/edit/{ObjectId()}", data=pit))
        with patch("app.notifications.routes.notification_manager") as notifier:
            notifier.create_subscription.return_value = (True, "ok")
            text = self.request("POST", "/notifications/subscribe",
                                json={"subscription": {"keys": {"auth": SECRET}}, "team_number": 334})
            self.assertIn("Created push subscription (team 334", text)


if __name__ == '__main__':
    unittest.main()
