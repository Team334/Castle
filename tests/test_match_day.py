"""Match-day fixes: TBA keys, duplicate block, add-form redirects, edit identity and exclusion.

MongoDB is never contacted: managers are built with __new__ and a MagicMock db."""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from bson import ObjectId
from flask import Flask

from app.scout.match13_fuel import match_key
from app.scout.routes import common, records
from app.scout.scouting_utils import ScoutingManager
from app.scout.TBA import tba_match_key
from tests.app_harness import USER_ID


def manager():
    """A ScoutingManager whose db is a MagicMock; aggregate returns no rows by default."""
    m = ScoutingManager.__new__(ScoutingManager)
    m.db = MagicMock()
    m.db.team_data.aggregate.return_value = []
    return m


class MatchKeyTests(unittest.TestCase):
    def test_labels_map_to_tba_keys_in_any_year(self):
        self.assertEqual(tba_match_key("2027nyny", "Qual 12"), "2027nyny_qm12")
        self.assertEqual(tba_match_key("2027nyny", "Semifinal 2-1"), "2027nyny_sf2m1")
        self.assertEqual(tba_match_key("2027nyny", "Final 2"), "2027nyny_f1m2")
        self.assertEqual(tba_match_key("2026test1", "Qual 3"), "2026test1_qm3")
        self.assertEqual(tba_match_key("2027nyny", "2027nyny_qm3"), "2027nyny_qm3")

    def test_bad_event_or_label_gives_none(self):
        for event, label in [("nyny", "Qual 1"), ("", "Qual 1"), ("2027NYNY", "Qual 1"),
                             ("2027nyny", "Practice 1"), ("2027nyny", ""), ("2027nyny", "2026other_qm1")]:
            self.assertIsNone(tba_match_key(event, label), (event, label))

    def test_match13_stays_2026_only(self):
        self.assertIsNone(match_key("2027nyny", "Qual 1"))
        self.assertEqual(match_key("2026nyny", "Qual 1"), "2026nyny_qm1")


def form(**kw):
    return {"team_number": "254", "event_code": "NYC Regional", "match_number": "Qual 12",
            "_event_key": "2026nyny", **kw}


class AddRecordTests(unittest.TestCase):
    def setUp(self):
        self.m = manager()

    def test_valid_keys_are_stored(self):
        ok, _ = self.m.add_scouting_data(form(), USER_ID, 334)
        doc = self.m.db.team_data.insert_one.call_args.args[0]
        self.assertTrue(ok)
        self.assertEqual((doc["event_key"], doc["match_key"]), ("2026nyny", "2026nyny_qm12"))
        self.assertEqual((doc["event_code"], doc["match_number"]), ("NYC Regional", "Qual 12"))

    def test_missing_or_invalid_event_key_saves_without_keys_or_check(self):
        for bad in ["", "javascript:", None]:
            self.m.db.reset_mock()
            ok, _ = self.m.add_scouting_data(form(_event_key=bad), USER_ID, 334)
            doc = self.m.db.team_data.insert_one.call_args.args[0]
            self.assertTrue(ok, bad)
            self.assertNotIn("event_key", doc)
            self.assertNotIn("match_key", doc)
            self.m.db.team_data.aggregate.assert_not_called()

    def test_same_team_duplicate_is_blocked_with_scout_name(self):
        self.m.db.team_data.aggregate.return_value = [{"scouter": {"username": "sam"}}]
        ok, msg = self.m.add_scouting_data(form(), USER_ID, 334)
        self.assertFalse(ok)
        self.assertEqual(msg, "Team 254 in Qual 12 was already scouted by sam. "
                              "Edit that entry from the scouting list instead.")
        self.m.db.team_data.insert_one.assert_not_called()

    def test_duplicate_query_scopes_to_team_and_skips_excluded(self):
        self.m.add_scouting_data(form(), USER_ID, 334)
        pipeline = self.m.db.team_data.aggregate.call_args.args[0]
        self.assertEqual(pipeline[0]["$match"],
                         {"match_key": "2026nyny_qm12", "team_number": 254, "excluded": {"$ne": True}})
        self.assertIn({"$match": {"scouter.teamNumber": 334}}, pipeline)

    def test_teamless_scout_is_checked_against_own_records_only(self):
        self.m.add_scouting_data(form(), USER_ID, None)
        pipeline = self.m.db.team_data.aggregate.call_args.args[0]
        self.assertIn({"$match": {"scouter_id": ObjectId(USER_ID)}}, pipeline)


class AddRedirectTests(unittest.TestCase):
    BASE = {"team_number": "254", "event_code": "NYC Regional", "alliance": "red"}
    GOOD = {"_event_key": "2026nyny", "match_number": "Qual 12", "_station": "red2", "_draft_id": "abc-123"}

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(LOGIN_DISABLED=True, SECRET_KEY="test-only")
        self.app.add_url_rule("/scouting", endpoint="scouting.home", view_func=lambda: "ok")
        self.app.add_url_rule("/scouting/add", endpoint="scouting.add", view_func=records.add, methods=["GET", "POST"])
        self.manager = MagicMock()
        self.manager.add_scouting_data.return_value = (True, str(ObjectId()))
        user = SimpleNamespace(get_id=lambda: USER_ID, teamNumber=334, is_authenticated=True, username="tester")
        for item in (patch.object(records, "current_user", user), patch.object(common, "scouting_manager", self.manager)):
            item.start()
            self.addCleanup(item.stop)

    def post(self, data):
        response = self.app.test_client().post("/scouting/add", data={**self.BASE, **data})
        self.assertEqual(response.status_code, 302)
        url = urlparse(response.location)
        return url.path, parse_qs(url.query)

    def test_success_redirects_to_next_match_with_validated_params(self):
        path, query = self.post(self.GOOD)
        self.assertEqual(path, "/scouting/add")
        self.assertEqual(query, {"event": ["2026nyny"], "after": ["Qual 12"], "station": ["red2"], "saved": ["abc-123"]})

    def test_failure_redirects_to_same_match_without_saved(self):
        self.manager.add_scouting_data.return_value = (False, "dup")
        path, query = self.post(self.GOOD)
        self.assertEqual(path, "/scouting/add")
        self.assertEqual(query, {"event": ["2026nyny"], "match": ["Qual 12"], "station": ["red2"]})

    def test_invalid_redirect_params_are_dropped(self):
        _, query = self.post({"_event_key": "javascript:", "match_number": "x" * 500,
                              "_station": "../x", "_draft_id": "a b<"})
        self.assertNotIn("event", query)
        self.assertNotIn("station", query)
        self.assertNotIn("saved", query)
        self.assertEqual(query["after"], ["x" * 32])

    def test_bad_auto_path_json_returns_to_add_form(self):
        path, query = self.post({"auto_path": "{not json", "_event_key": "2026nyny", "match_number": "Qual 1"})
        self.assertEqual(path, "/scouting/add")
        self.assertEqual(query, {"event": ["2026nyny"], "match": ["Qual 1"]})
        self.manager.add_scouting_data.assert_not_called()


class EditTests(unittest.TestCase):
    OID = ObjectId()
    EXISTING = {"_id": OID, "event_code": "A", "match_number": "Qual 1", "team_number": 334, "alliance": "red",
                "event_key": "2026a", "match_key": "2026a_qm1"}

    def setUp(self):
        self.m = manager()
        self.m.db.team_data.find_one.return_value = dict(self.EXISTING)
        self.m.db.team_data.update_one.return_value.matched_count = 1

    def update(self, **change):
        payload = {"event_code": "A", "match_number": "Qual 1", "team_number": "334", "alliance": "red", **change}
        self.assertTrue(self.m.update_team_data(str(self.OID), payload, USER_ID))
        return self.m.db.team_data.update_one.call_args.args[1]

    def test_event_change_unsets_both_keys(self):
        self.assertEqual(self.update(event_code="B")["$unset"], {"event_key": "", "match_key": ""})

    def test_match_change_unsets_match_key_only(self):
        self.assertEqual(self.update(match_number="Qual 2")["$unset"], {"match_key": ""})

    def test_edit_without_identity_change_sends_no_unset(self):
        for change in [{}, {"team_number": "335"}]:
            self.assertNotIn("$unset", self.update(**change), change)

    def test_excluded_checkbox_round_trips(self):
        self.assertIs(self.update(excluded="true")["$set"]["excluded"], True)
        self.assertIs(self.update()["$set"]["excluded"], False)


if __name__ == '__main__':
    unittest.main()
