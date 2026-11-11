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


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.m = manager()
        self.m.db.team_data.find_one.return_value = None

    def test_new_entry_is_saved_and_credited(self):
        [result] = self.m.import_matches([entry()], USER_ID, 334)
        self.assertEqual(result["status"], "saved")
        self.assertEqual(result["key"], "c1")
        doc = self.m.db.team_data.insert_one.call_args.args[0]
        self.assertEqual((doc["scouter_id"], doc["client_id"]), (ObjectId(USER_ID), "c1"))
        self.assertNotIn("uploaded_by", doc)

    def test_client_id_seen_before_is_already_have(self):
        self.m.db.team_data.find_one.return_value = {"_id": ObjectId()}
        results = self.m.import_matches([entry(), entry(client_id=None, _id=str(ObjectId()))], USER_ID, 334)
        self.assertEqual([r["status"] for r in results], ["already_have", "already_have"])
        self.m.db.team_data.insert_one.assert_not_called()

    def test_existing_id_is_kept_for_new_records(self):
        oid = ObjectId()
        self.m.import_matches([entry(_id=str(oid))], USER_ID, 334)
        self.assertEqual(self.m.db.team_data.insert_one.call_args.args[0]["_id"], oid)

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

    def test_export_shaped_entry_uses_event_key(self):
        exported = {k: v for k, v in entry().items() if k != "_event_key"}
        self.m.import_matches([{**exported, "event_key": "2026nyny"}], USER_ID, 334)
        self.assertEqual(self.m.db.team_data.insert_one.call_args.args[0]["match_key"], "2026nyny_qm12")

    def test_duplicate_non_dict_and_created_at(self):
        self.m.db.team_data.aggregate.return_value = [{"scouter": {"username": "sam"}}]
        results = self.m.import_matches([entry(), "junk"], USER_ID, 334)
        self.assertEqual([r["status"] for r in results], ["duplicate", "rejected"])
        self.assertIn("sam", results[0]["reason"])
        self.m.db.team_data.aggregate.return_value = []
        self.m.import_matches([entry(created_at="2026-03-01T10:00:00")], USER_ID, 334)
        self.assertEqual(self.m.db.team_data.insert_one.call_args.args[0]["created_at"],
                         datetime(2026, 3, 1, 10, tzinfo=timezone.utc))
        self.m.import_matches([entry(created_at="yesterday")], USER_ID, 334)
        self.assertGreater(self.m.db.team_data.insert_one.call_args.args[0]["created_at"].year, 2025)


if __name__ == '__main__':
    unittest.main()
