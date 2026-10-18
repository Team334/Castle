"""Shared scouting route helpers; pure functions, no app or database."""
from types import SimpleNamespace
import unittest

from bson import ObjectId

from app.scout.routes.common import actor_name, fuel_total, team_access_match


class CommonHelperTests(unittest.TestCase):
    def test_access_match_limits_to_own_records_without_team(self):
        user_id = str(ObjectId())
        user = SimpleNamespace(get_id=lambda: user_id, teamNumber=None)
        self.assertEqual(team_access_match(user), {"$match": {"scouter._id": ObjectId(user_id)}})

    def test_access_match_adds_team_records(self):
        user_id = str(ObjectId())
        user = SimpleNamespace(get_id=lambda: user_id, teamNumber=334)
        self.assertEqual(team_access_match(user), {"$match": {"$or": [
            {"scouter._id": ObjectId(user_id)}, {"scouter.teamNumber": 334}]}})

    def test_fuel_total_excludes_ferried(self):
        record = dict.fromkeys(["auto_fuel", "transition_fuel", "teleop_shift_1_fuel", "teleop_shift_2_fuel",
                                "teleop_shift_3_fuel", "teleop_shift_4_fuel", "endgame_fuel"], 2)
        self.assertEqual(fuel_total({**record, "ferried_fuel": 50}), 14)

    def test_actor_name(self):
        self.assertEqual(actor_name(SimpleNamespace(is_authenticated=True, username="a")), "a")
        self.assertEqual(actor_name(SimpleNamespace(is_authenticated=False)), "Anonymous")


if __name__ == '__main__':
    unittest.main()
