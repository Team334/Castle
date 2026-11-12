"""Offline phase 1: entry export and import. MongoDB is never contacted (MagicMock db / minimal Flask app)."""
import io
import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

from bson import ObjectId
from flask import Flask

from app.scout.routes import common, records
from tests.app_harness import USER_ID
from tests.test_match_day import form, manager


class InsertTests(unittest.TestCase):
    def setUp(self):
        self.m = manager()

    def test_meta_fields_are_stored_only_when_given_and_valid(self):
        oid, uploader = ObjectId(), ObjectId()
        when = datetime(2026, 3, 1, tzinfo=timezone.utc)
        status, _ = self.m._insert_record(form(), USER_ID, 334, _id=oid, client_id="abc-1",
                                          created_at=when, uploaded_by=str(uploader))
        doc = self.m.db.team_data.insert_one.call_args.args[0]
        self.assertEqual(status, "saved")
        self.assertEqual((doc["_id"], doc["client_id"], doc["created_at"], doc["uploaded_by"]),
                         (oid, "abc-1", when, uploader))
        self.m._insert_record(form(), USER_ID, 334, client_id="bad id!")
        doc = self.m.db.team_data.insert_one.call_args.args[0]
        self.assertNotIn("client_id", doc)
        self.assertNotIn("_id", doc)
        self.assertNotIn("uploaded_by", doc)

    def test_statuses(self):
        self.m.db.team_data.aggregate.return_value = [{"scouter": {"username": "sam"}}]
        self.assertEqual(self.m._insert_record(form(), USER_ID, 334)[0], "duplicate")
        self.assertEqual(self.m._insert_record(form(team_number="0"), USER_ID, 334)[0], "rejected")

    def test_add_route_stores_draft_id_as_client_id(self):
        app = Flask(__name__)
        app.config.update(LOGIN_DISABLED=True, SECRET_KEY="test-only")
        app.add_url_rule("/scouting", endpoint="scouting.home", view_func=lambda: "ok")
        app.add_url_rule("/scouting/add", endpoint="scouting.add", view_func=records.add, methods=["GET", "POST"])
        mgr = MagicMock()
        mgr.add_scouting_data.return_value = (True, str(ObjectId()))
        user = SimpleNamespace(get_id=lambda: USER_ID, teamNumber=334, is_authenticated=True, username="tester")
        with patch.object(records, "current_user", user), patch.object(common, "scouting_manager", mgr):
            app.test_client().post("/scouting/add", data={"team_number": "254", "event_code": "E",
                                                          "match_number": "Qual 1", "_draft_id": "abc-123"})
        self.assertEqual(mgr.add_scouting_data.call_args.kwargs["client_id"], "abc-123")


def entry(**kw):
    return {**form(), "scouter_id": USER_ID, "client_id": "c1", **kw}


def visible(existing=(), duplicates=()):
    """aggregate side effect: the existence lookup (first stage matches $or) sees `existing`; the duplicate check sees `duplicates`."""
    return lambda pipeline: list(existing if "$or" in pipeline[0].get("$match", {}) else duplicates)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.m = manager()

    def test_new_entry_is_saved_and_credited(self):
        [result] = self.m.import_matches([entry()], USER_ID, 334)
        self.assertEqual(result["status"], "saved")
        self.assertEqual(result["key"], "c1")
        doc = self.m.db.team_data.insert_one.call_args.args[0]
        self.assertEqual((doc["scouter_id"], doc["client_id"]), (ObjectId(USER_ID), "c1"))
        self.assertNotIn("uploaded_by", doc)

    def test_client_id_seen_before_is_already_have(self):
        self.m.db.team_data.aggregate.side_effect = visible(existing=[{"_id": ObjectId()}])
        results = self.m.import_matches([entry(), entry(client_id=None, _id=str(ObjectId()))], USER_ID, 334)
        self.assertEqual([r["status"] for r in results], ["already_have", "already_have"])
        self.m.db.team_data.insert_one.assert_not_called()

    def test_existence_is_checked_only_among_records_the_uploader_can_see(self):
        oid = ObjectId()
        self.m.import_matches([entry(_id=str(oid))], USER_ID, 334)
        lookup = self.m.db.team_data.aggregate.call_args_list[0].args[0]
        self.assertEqual(lookup[0], {"$match": {"$or": [{"_id": oid}, {"client_id": "c1"}]}})
        self.assertIn({"$match": {"$or": [{"scouter._id": ObjectId(USER_ID)}, {"scouter.teamNumber": 334}]}}, lookup)

    def test_incoming_id_is_never_reused_on_the_main_server(self):
        # Reusing it would let an uploader probe whether another team's record id exists.
        self.m.import_matches([entry(_id=str(ObjectId()))], USER_ID, 334)
        self.assertNotIn("_id", self.m.db.team_data.insert_one.call_args.args[0])

    def test_teammate_upload_keeps_credit_and_records_uploader(self):
        mate = str(ObjectId())
        self.m.db.users.find_one.return_value = {"_id": ObjectId(mate)}
        self.m.import_matches([entry(scouter_id=mate)], USER_ID, 334)
        self.assertEqual(self.m.db.users.find_one.call_args.args[0], {"_id": ObjectId(mate), "teamNumber": 334})
        doc = self.m.db.team_data.insert_one.call_args.args[0]
        self.assertEqual((doc["scouter_id"], doc["uploaded_by"]), (ObjectId(mate), ObjectId(USER_ID)))

    def test_scout_from_another_team_is_rejected(self):
        self.m.db.users.find_one.return_value = None
        for bad in [str(ObjectId()), "not-an-id", None]:
            [result] = self.m.import_matches([entry(scouter_id=bad)], USER_ID, 334)
            self.assertEqual(result["status"], "rejected", bad)
        self.m.db.team_data.insert_one.assert_not_called()

    def test_unknown_and_protected_fields_are_not_trusted(self):
        self.m.import_matches([entry(scouter_team=999, excluded=True, match_key="2026x_qm1",
                                     uploaded_by=str(ObjectId()), origin="venue", fuel_pending=True,
                                     hacked="yes")], USER_ID, 334)
        doc = self.m.db.team_data.insert_one.call_args.args[0]
        for field in ("scouter_team", "excluded", "uploaded_by", "origin", "fuel_pending", "hacked"):
            self.assertNotIn(field, doc)
        self.assertEqual(doc["match_key"], "2026nyny_qm12")  # recomputed from the event key and label

    def test_phone_form_values_are_normalised_like_the_add_route(self):
        # A phone queues raw form values: empty counters and the auto path as JSON text.
        [result] = self.m.import_matches([entry(auto_fuel="", endgame_fuel="", auto_path='[{"points": [1]}]')],
                                         USER_ID, 334)
        self.assertEqual(result["status"], "saved")
        doc = self.m.db.team_data.insert_one.call_args.args[0]
        self.assertEqual((doc["auto_fuel"], doc["endgame_fuel"]), (0, 0))
        self.assertEqual(doc["auto_path"], [{"points": [1]}])
        self.m.import_matches([entry(client_id="c2", auto_path="{broken")], USER_ID, 334)
        self.assertEqual(self.m.db.team_data.insert_one.call_args.args[0]["auto_path"], [])

    def test_export_shaped_entry_uses_event_key(self):
        exported = {k: v for k, v in entry().items() if k != "_event_key"}
        self.m.import_matches([{**exported, "event_key": "2026nyny"}], USER_ID, 334)
        self.assertEqual(self.m.db.team_data.insert_one.call_args.args[0]["match_key"], "2026nyny_qm12")

    def test_duplicate_non_dict_and_created_at(self):
        self.m.db.team_data.aggregate.side_effect = visible(duplicates=[{"scouter": {"username": "sam"}}])
        results = self.m.import_matches([entry(), "junk"], USER_ID, 334)
        self.assertEqual([r["status"] for r in results], ["duplicate", "rejected"])
        self.assertIn("sam", results[0]["reason"])
        self.m.db.team_data.aggregate.side_effect = visible()
        self.m.import_matches([entry(created_at="2026-03-01T10:00:00")], USER_ID, 334)
        self.assertEqual(self.m.db.team_data.insert_one.call_args.args[0]["created_at"],
                         datetime(2026, 3, 1, 10, tzinfo=timezone.utc))
        self.m.import_matches([entry(created_at="yesterday")], USER_ID, 334)
        self.assertGreater(self.m.db.team_data.insert_one.call_args.args[0]["created_at"].year, 2025)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.m = manager()
        self.m.db.pit_scouting.aggregate.return_value = []
        self.m.db.users.find.return_value = []

    def test_export_shape_season_filter_and_roster(self):
        oid = ObjectId()
        self.m.db.team_data.aggregate.return_value = [{"_id": oid, "scouter_id": ObjectId(USER_ID),
                                                       "created_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
                                                       "auto_path": [{"points": [{"x": 1}]}]}]
        self.m.db.users.find.return_value = [{"_id": ObjectId(USER_ID), "username": "tester", "teamNumber": 334}]
        data = self.m.export_data(USER_ID, 334, now=datetime(2026, 11, 11, tzinfo=timezone.utc))
        self.assertEqual((data["format"], data["version"], data["team"]), ("castle-entries", 1, 334))
        self.assertEqual(data["matches"][0]["_id"], str(oid))
        self.assertEqual(data["matches"][0]["scouter_id"], USER_ID)
        self.assertEqual(data["matches"][0]["created_at"], "2026-03-01T00:00:00+00:00")
        self.assertEqual(data["users"], [{"_id": USER_ID, "username": "tester", "teamNumber": 334}])
        pipeline = self.m.db.team_data.aggregate.call_args.args[0]
        self.assertIn({"$match": {"created_at": {"$gte": datetime(2026, 1, 1, tzinfo=timezone.utc)}}}, pipeline)
        self.assertIn({"$project": {"scouter": 0}}, pipeline)
        self.assertIn({"$project": {"scouter": 0}}, self.m.db.pit_scouting.aggregate.call_args.args[0])
        self.assertEqual(self.m.db.users.find.call_args.args,
                         ({"teamNumber": 334}, {"_id": 1, "username": 1, "teamNumber": 1}))
        json.dumps(data)

    def test_export_never_asks_for_secrets(self):
        self.m.db.team_data.aggregate.return_value = []
        self.m.export_data(USER_ID, 334)
        projection = self.m.db.users.find.call_args.args[1]
        self.assertEqual(set(projection), {"_id", "username", "teamNumber"})

    def test_teamless_user_exports_own_profile(self):
        self.m.db.team_data.aggregate.return_value = []
        self.m.db.users.find.return_value = [{"_id": ObjectId(USER_ID), "username": "solo"}]
        self.m.export_data(USER_ID, None)
        self.assertEqual(self.m.db.users.find.call_args.args[0], {"_id": ObjectId(USER_ID)})


def envelope(matches, **extra):
    return {"format": "castle-entries", "version": 1, "matches": matches, **extra}


class RouteTests(unittest.TestCase):
    def setUp(self):
        from app.scout.routes import transfer
        self.app = Flask(__name__)
        self.app.config.update(LOGIN_DISABLED=True, SECRET_KEY="test-only", RATELIMIT_ENABLED=False)
        self.app.add_url_rule("/scouting/export", endpoint="scouting.export_entries", view_func=transfer.export_entries)
        self.app.add_url_rule("/scouting/import", endpoint="scouting.import_entries",
                              view_func=transfer.import_entries, methods=["POST"])
        self.service = MagicMock()
        self.app.extensions["match13_fuel"] = self.service
        self.manager = MagicMock()
        self.manager.db.pit_scouting.find_one.return_value = None
        self.user = SimpleNamespace(get_id=lambda: USER_ID, teamNumber=334, is_authenticated=True, username="tester")
        for item in (patch.object(transfer, "current_user", self.user), patch.object(common, "scouting_manager", self.manager)):
            item.start()
            self.addCleanup(item.stop)
        self.client = self.app.test_client()

    def test_export_downloads_a_dated_json_file(self):
        self.manager.export_data.return_value = {"format": "castle-entries", "version": 1, "matches": []}
        response = self.client.get("/scouting/export")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["format"], "castle-entries")
        self.assertRegex(response.headers["Content-Disposition"],
                         r'attachment; filename="castle-334-\d{4}-\d{2}-\d{2}\.json"')
        self.assertEqual(self.manager.export_data.call_args.args, (USER_ID, 334))

    def test_json_import_returns_results_counts_and_enrolls_zero_fuel(self):
        self.manager.import_matches.return_value = [{"key": "c1", "status": "saved", "id": "rid"},
                                                    {"key": "c2", "status": "duplicate", "reason": "x"}]
        response = self.client.post("/scouting/import", json=envelope(
            [{"client_id": "c1", "event_key": "2026nyny"}, {"client_id": "c2", "auto_fuel": 4}]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["counts"], {"saved": 1, "duplicate": 1})
        self.assertEqual(self.manager.import_matches.call_args.args[1:], (USER_ID, 334))
        self.service.enroll.assert_called_once()
        self.assertEqual(self.service.enroll.call_args.args[0], "rid")
        self.assertEqual(self.service.enroll.call_args.args[1]["_event_key"], "2026nyny")

    def test_saved_entry_with_fuel_is_not_enrolled(self):
        self.manager.import_matches.return_value = [{"key": "c1", "status": "saved", "id": "rid"}]
        self.client.post("/scouting/import", json=envelope([{"client_id": "c1", "auto_fuel": 3}]))
        self.service.enroll.assert_not_called()

    def test_file_import(self):
        self.manager.import_matches.return_value = []
        upload = {"file": (io.BytesIO(json.dumps(envelope([])).encode()), "castle.json")}
        response = self.client.post("/scouting/import", data=upload, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200)
        self.manager.import_matches.assert_called_once()

    def test_bad_payloads_are_400(self):
        for body in [b"{not json", b"[]", json.dumps({"format": "other", "version": 1}).encode(),
                     json.dumps({"format": "castle-entries", "version": 2}).encode(),
                     json.dumps({"format": "castle-entries", "version": 1, "matches": "x"}).encode()]:
            response = self.client.post("/scouting/import", data=body, content_type="application/json")
            self.assertEqual(response.status_code, 400, body)
            self.assertIn("error", response.json)  # the list page shows this message
        bad_file = {"file": (io.BytesIO(b"nope"), "x.json")}
        self.assertEqual(self.client.post("/scouting/import", data=bad_file,
                                          content_type="multipart/form-data").status_code, 400)
        self.manager.import_matches.assert_not_called()

    def test_too_many_or_too_large_json_is_413(self):
        self.assertEqual(self.client.post("/scouting/import", json=envelope([{}] * 501)).status_code, 413)
        self.assertEqual(self.client.post("/scouting/import", json=envelope([], pits=[{}] * 501)).status_code, 413)
        many = {"file": (io.BytesIO(json.dumps(envelope([{}] * 15001, pits=[{}] * 5000)).encode()), "x.json")}
        self.assertEqual(self.client.post("/scouting/import", data=many, content_type="multipart/form-data").status_code, 413)
        self.manager.import_matches.assert_not_called()
        big = json.dumps(envelope([{"notes": "x" * (5 * 1024 * 1024)}])).encode()
        self.assertEqual(self.client.post("/scouting/import", data=big, content_type="application/json").status_code, 413)

    def test_pit_entries_outside_venue_mode(self):
        existing = ObjectId()
        self.manager.import_matches.return_value = []
        self.manager.visible_pit_ids.return_value = {existing}
        response = self.client.post("/scouting/import", json=envelope([], pits=[{"_id": str(existing)},
                                                                                {"_id": str(ObjectId())}, {}, "x"]))
        self.assertEqual([p["status"] for p in response.json["pit_results"]],
                         ["already_have", "rejected", "rejected", "rejected"])
        self.assertEqual(self.manager.visible_pit_ids.call_args.args, (USER_ID, 334))
        self.manager.db.pit_scouting.find_one.assert_not_called()  # no unscoped existence check

    def test_teamless_uploader_is_403(self):
        self.user.teamNumber = None
        self.assertEqual(self.client.post("/scouting/import", json=envelope([])).status_code, 403)
        self.manager.import_matches.assert_not_called()


if __name__ == '__main__':
    unittest.main()
