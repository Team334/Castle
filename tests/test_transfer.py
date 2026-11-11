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


if __name__ == '__main__':
    unittest.main()
