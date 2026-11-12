"""Venue laptop (offline phase 4): export scope, CLI commands, stub users. MongoDB is mocked throughout."""
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from bson import ObjectId

from app.models import User
from app.scout.routes import common
from tests.app_harness import USER_ID, logged_in_client, start_app
from tests.test_match_day import manager


class ExportScopeTests(unittest.TestCase):
    def test_venue_export_scope(self):
        m = manager()
        m.db.pit_scouting.aggregate.return_value = []
        m.db.users.find.return_value = []
        m.export_data(USER_ID, 334, scope="venue")
        pipeline = m.db.team_data.aggregate.call_args.args[0]
        self.assertIn({"$match": {"origin": "venue"}}, pipeline)
        self.assertFalse(any("created_at" in stage.get("$match", {}) for stage in pipeline))

    def test_stub_users_cannot_log_in(self):
        self.assertFalse(User.create_from_db({"_id": ObjectId(), "username": "s"}).check_password("x"))


class VenueAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.patches = start_app()

    @classmethod
    def tearDownClass(cls):
        for item in reversed(cls.patches):
            item.stop()

    def setUp(self):
        self.db = MagicMock()
        swap = patch.object(common.scouting_manager, "db", self.db)
        swap.start()
        self.addCleanup(swap.stop)
        self.app.config["VENUE_MODE"] = True
        self.addCleanup(self.app.config.update, VENUE_MODE=False)

    def run_cli(self, *args):
        return self.app.test_cli_runner().invoke(args=list(args))

    def test_venue_export_records_the_push_and_is_venue_only(self):
        self.db.team_data.aggregate.return_value = []
        self.db.pit_scouting.aggregate.return_value = []
        self.db.users.find.return_value = []
        client, token = logged_in_client(self.app)
        # Recording the push changes what venue-reset may delete, so it is a CSRF-protected POST, never a GET.
        self.assertEqual(client.get("/scouting/export/venue").status_code, 405)
        self.assertIn(client.post("/scouting/export/venue").status_code, (302, 400))  # no CSRF token: refused
        self.db.venue_meta.update_one.assert_not_called()
        response = client.post("/scouting/export/venue", data={"csrf_token": token})
        self.assertEqual(response.status_code, 200)
        self.assertIn("venue", response.headers["Content-Disposition"])
        update = self.db.venue_meta.update_one.call_args
        self.assertEqual(update.args[0], {"_id": "push"})
        self.assertIsInstance(update.args[1]["$set"]["at"], datetime)
        self.assertTrue(update.kwargs.get("upsert"))
        self.app.config["VENUE_MODE"] = False
        self.assertEqual(client.post("/scouting/export/venue", data={"csrf_token": token}).status_code, 404)

    def test_reset_refuses_unpushed_venue_entries(self):
        pushed = datetime(2026, 11, 10, tzinfo=timezone.utc)
        self.db.venue_meta.find_one.return_value = {"_id": "push", "at": pushed}
        self.db.team_data.count_documents.return_value = 2
        result = self.run_cli("venue-reset")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("2 entries", result.output)
        self.assertEqual(self.db.team_data.count_documents.call_args.args[0],
                         {"origin": "venue", "venue_at": {"$gt": pushed}})
        self.db.team_data.delete_many.assert_not_called()

    def test_reset_with_nothing_unpushed_or_forced(self):
        self.db.venue_meta.find_one.return_value = None
        self.db.team_data.count_documents.return_value = 3
        result = self.run_cli("venue-reset", "--force")
        self.assertEqual(result.exit_code, 0, result.output)
        for collection in (self.db.team_data, self.db.pit_scouting, self.db.venue_meta):
            collection.delete_many.assert_called_once_with({})
        self.db.team_data.count_documents.return_value = 0
        self.assertEqual(self.run_cli("venue-reset").exit_code, 0)

    def test_commands_refuse_outside_venue_mode(self):
        self.app.config["VENUE_MODE"] = False
        result = self.run_cli("venue-reset", "--force")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("VENUE_MODE=1", result.output)
        self.db.team_data.delete_many.assert_not_called()

    def test_leaderboard_renders_teams_whose_fuel_is_all_pending(self):
        team = {"team_number": 254, "matches_played": 2, "auto_climb_pct": 50.0, "climb_l1_pct": 0, "climb_l2_pct": 0,
                "climb_l3_pct": 0, "climb_success_rate": 0.5, "defense_rating": 3.0, "ferrying_count": 0,
                "ferrying_rating": 0, "herd_count": 0, "herd_rating": 0, "robot_disabled_list": [],
                **{field: None for field in ("auto_fuel", "transition_fuel", "ferried_fuel", "teleop_fuel_total",
                                             "endgame_fuel", "total_fuel")}}
        client, _ = logged_in_client(self.app)
        with patch.object(common.scouting_manager, "get_team_leaderboard", return_value=[team]),                 patch.object(common.scouting_manager, "get_leaderboard_events", return_value=[]):
            response = client.get("/leaderboard")
        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("254", html)
        self.assertIn("—", html)

    def test_venue_user_creates_a_login(self):
        with patch("app.venue.UserManager") as users:
            users.return_value.create_user.return_value = (True, "User created")
            result = self.run_cli("venue-user", "--username", "lead", "--password", "secret123", "--team", "334")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(users.return_value.create_user.call_args.args, ("lead@venue.local", "lead", "secret123", 334))


FUEL = ("auto_fuel", "transition_fuel", "ferried_fuel", "teleop_shift_1_fuel", "teleop_shift_2_fuel",
        "teleop_shift_3_fuel", "teleop_shift_4_fuel", "endgame_fuel")


def group_stage(pipeline):
    return next(stage["$group"] for stage in pipeline if "$group" in stage)


class FuelPendingTests(unittest.TestCase):
    def test_fuel_averages_skip_pending(self):
        m = manager()
        pending = lambda field: {"$avg": {"$cond": [{"$eq": ["$fuel_pending", True]}, None,
                                                    {"$ifNull": ["$" + field, 0]}]}}
        m.get_compare_stats(254, USER_ID, 334)
        compare = group_stage(m.db.team_data.aggregate.call_args.args[0])
        m.get_team_leaderboard(USER_ID, 334)
        board = group_stage(m.db.team_data.aggregate.call_args.args[0])
        for field in FUEL:
            self.assertEqual(compare["avg_" + field], pending(field), field)
            self.assertEqual(board[field], pending(field), field)
        self.assertNotIn('{"$avg": {"$ifNull": ["$auto_fuel"', str(compare) + str(board))

    def test_list_shows_fuel_pending(self):
        m = manager()
        m.get_all_scouting_data(334, USER_ID, page=1)
        project = next(stage for stage in m.db.team_data.aggregate.call_args.args[0] if "$project" in stage)["$project"]
        self.assertEqual(project["fuel_pending"], 1)


if __name__ == '__main__':
    unittest.main()
