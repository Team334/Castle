# Offline Phase 1 (Entry Export and Import) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One JSON entry format that every path can repeat safely. `GET /scouting/export` downloads the team's current-season data; `POST /scouting/import` takes entries (a JSON body or a file) and skips anything it already has. It also refuses scouts from other teams and sends zero-fuel entries for AI estimates. Two list-page buttons sit on top.

**Architecture:** The record-building and duplicate rules stay in `ScoutingManager` (`app/scout/scouting_utils.py`).
- `add_scouting_data` becomes a thin wrapper over a new `_insert_record` that reports a status.
- `import_matches` and `export_data` are new manager methods.
- A new route module, `app/scout/routes/transfer.py`, holds the HTTP layer. It parses the envelope, checks the limits, signs entries up for fuel estimates and returns JSON.
- The list page gets a download link and an import button. It uses `base.html`'s fetch patch, which adds CSRF to same-origin writes.

**Tech Stack:** Flask, pymongo aggregation, Jinja, vanilla JS, `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-11-offline-venue-mode-design.md`. This plan covers section 1 outside venue mode, plus the "Fuel estimates" paragraph of section 2. Venue-mode import rules come in phase 4.

## Global Constraints

- **Never connect to or write to the user's MongoDB.** Tests use `ScoutingManager.__new__` with a `MagicMock` db (the `manager()` helper in `tests/test_match_day.py`), or a minimal Flask app.
- Python tests: `.venv/Scripts/python.exe -m unittest tests.<module> -v`. JS tests: `npm test`.
- Envelope: `{"format": "castle-entries", "version": 1, ...}`. Any other `format` or `version` gets a 400.
- **Limits:**
  - JSON body: at most 500 match entries and 5 MB (`5 * 1024 * 1024`).
  - File upload: 50 MB, enforced by `app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024`.
  - Too big gets a 413.
- **Statuses:** `saved`, `already_have`, `duplicate`, `rejected`.
- `client_id` pattern: `[A-Za-z0-9-]{1,64}`.
- **Export:**
  - Never includes `password_hash`, `email` or any user field except `_id`, `username` and `teamNumber`.
  - Covers only records with `created_at` on or after Jan 1 (UTC) of the current year.
  - Ids are strings and datetimes are ISO strings.
- Nothing about venue mode in this phase. The import route doesn't create users, doesn't keep exact copies and never sets `origin`.
- Commit messages end with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push.

## Review Focus

1. **The same entry from three paths.** A scout's own sync, a QR scan and a file import all bring the same entry. It's saved once, and the other two report `already_have` (Task 2 `test_client_id_seen_before_is_already_have`).
2. **Spoofed fields.** An entry carrying `scouter_team`, `excluded`, `match_key` or `uploaded_by` must not have those values stored (Task 2 `test_unknown_and_protected_fields_are_not_trusted`).
3. **A scout from another team.** An entry crediting another team's scout is `rejected` and never inserted (Task 2 `test_scout_from_another_team_is_rejected`).
4. **Bad JSON or wrong format** gets a 400, never a 500 (Task 4 `test_bad_payloads_are_400`).
5. **No team, or not logged in.** An uploader with no team gets a 403. Being logged out hits the normal login redirect (Task 4 `test_teamless_uploader_is_403`).

## Pre-decision (deviation note)

The spec builds new pit entries through the pit builder. But nothing in this design creates pit records off the main server: offline pit scouting is a non-goal. So in this phase, a pit entry whose `_id` already exists is `already_have`, and any other pit entry is `rejected` with `"pit entries are only accepted in venue mode"`. Phase 4 adds the venue copy. This avoids an untested create path with no caller.

---

### Task 1: `_insert_record`, and `client_id` on the add path

**Files:**
- Modify: `app/scout/scouting_utils.py` (`add_scouting_data`, around line 151)
- Modify: `app/scout/routes/records.py`
  - `add` passes `client_id`.
  - Replace the module's `DRAFT_ID_PATTERN` with `CLIENT_ID_PATTERN`, imported from `scouting_utils`.
- Test: `tests/test_transfer.py` (new; the `InsertTests` class)

**Interfaces:**
- Produces:
  - `CLIENT_ID_PATTERN = re.compile(r"[A-Za-z0-9-]{1,64}\Z")` in `scouting_utils.py`.
  - `ScoutingManager._insert_record(self, data: dict, scouter_id: str, scout_team, *, _id=None, client_id=None, created_at=None, uploaded_by=None) -> tuple[str, str]`.
    - Returns `("saved", inserted_id)`, `("duplicate", message)` or `("rejected", reason)`.
    - It contains the current body of `add_scouting_data`: the team-number check, keys, the duplicate check (with the existing duplicate message) and the insert.
    - It adds `_id` (an ObjectId), `client_id` (only when it matches the pattern), `created_at` (a datetime, else now) and `uploaded_by` (an ObjectId) to the document, each only when given.
  - `add_scouting_data(self, data, scouter_id, team_number=None, client_id=None) -> tuple[bool, str]` keeps its old return shape: `status == "saved"`, then the detail.
- The `add` route passes `client_id=data.get("_draft_id")`.

- [ ] **Step 1: Write the failing tests:**

```python
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
        # minimal Flask app as in tests/test_match_day.py AddRedirectTests; manager is a MagicMock
        post({"_draft_id": "abc-123", ...})
        self.assertEqual(manager.add_scouting_data.call_args.kwargs["client_id"], "abc-123")
```

  `form()` comes from `tests/test_match_day.py`. Import it, or copy the 3-line helper.
- [ ] **Step 2: Run the tests.** Run: `.venv/Scripts/python.exe -m unittest tests.test_transfer -v`. Expected: FAIL (`AttributeError: _insert_record`).
- [ ] **Step 3: Implement.** Move the body into `_insert_record`. The duplicate early-return becomes `("duplicate", msg)`, invalid team becomes `("rejected", "Invalid team number")`, and an exception becomes `("rejected", "An internal error has occurred.")`. Then make `add_scouting_data` wrap it, update `records.py`, and replace `DRAFT_ID_PATTERN` with `CLIENT_ID_PATTERN`.
- [ ] **Step 4: Run the tests.** Run `tests.test_transfer tests.test_match_day tests.test_match13_fuel`. Expected: PASS. Batch 1's tests must stay unchanged and green.
- [ ] **Step 5: Commit:** `git commit -m "Split record insert into _insert_record and keep the add form's client id"`.

---

### Task 2: `import_matches`

**Files:**
- Modify: `app/scout/scouting_utils.py` (new method, after `add_scouting_data`)
- Test: `tests/test_transfer.py` (the `ImportTests` class)

**Interfaces:**
- Consumes: `_insert_record`, `CLIENT_ID_PATTERN` (Task 1).
- Produces: `ScoutingManager.import_matches(self, entries: list, uploader_id: str, uploader_team: int) -> list[dict]`. It returns one result per entry, in order: `{"key": <client_id or _id or index as str>, "status": ..., "id"?: <new id when saved>, "reason"?: str}`.
  - **Not a dict:** `rejected` "not an entry".
  - **Already have:** a valid `_id` or `client_id` already exists, using one query `team_data.find_one({"$or": [...]}, {"_id": 1})`, gives `already_have`. Add the comment `# shortcut: unindexed _id/client_id lookup per entry; fine while team_data is small, index client_id if imports slow down`.
  - **Who scouted it:** `scouter_id` must be a valid ObjectId. It must equal `uploader_id`, or `users.find_one({"_id": oid, "teamNumber": uploader_team})` must find someone. Otherwise `rejected` "scout is not on your team".
  - **The record:** build `data = {k: v for k, v in entry.items() if not k.startswith("_") and k not in PROTECTED}` with `PROTECTED = {"scouter_team", "excluded", "event_key", "match_key", "uploaded_by", "origin", "fuel_pending", "client_id", "scouter_id", "created_at"}`. Add `data["_event_key"] = entry.get("event_key") or entry.get("_event_key")`.
  - **Insert:** call `_insert_record(data, scouter_id, uploader_team, _id=..., client_id=..., created_at=<parsed ISO or None>, uploaded_by=uploader_id if scouter != uploader)`.
  - **`created_at` parsing:** `datetime.fromisoformat`. If the result is naive, treat it as UTC. If it's invalid, use None.

- [ ] **Step 1: Write the failing tests.** `entry(**kw)` = `form()` plus `scouter_id=USER_ID`, `client_id="c1"`. Use `self.m.db.team_data.find_one.return_value = None` by default.

```python
def test_new_entry_is_saved_and_credited(self):
    [r] = self.m.import_matches([entry()], USER_ID, 334)
    self.assertEqual(r["status"], "saved")
    doc = self.m.db.team_data.insert_one.call_args.args[0]
    self.assertEqual((doc["scouter_id"], doc["client_id"]), (ObjectId(USER_ID), "c1"))
    self.assertNotIn("uploaded_by", doc)

def test_client_id_seen_before_is_already_have(self):
    self.m.db.team_data.find_one.return_value = {"_id": ObjectId()}
    self.assertEqual([r["status"] for r in self.m.import_matches([entry(), entry(_id=str(ObjectId()))], USER_ID, 334)],
                     ["already_have", "already_have"])
    self.m.db.team_data.insert_one.assert_not_called()

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
        [r] = self.m.import_matches([entry(scouter_id=bad)], USER_ID, 334)
        self.assertEqual(r["status"], "rejected", bad)
    self.m.db.team_data.insert_one.assert_not_called()

def test_unknown_and_protected_fields_are_not_trusted(self):
    self.m.import_matches([entry(scouter_team=999, excluded=True, match_key="2026x_qm1", uploaded_by=str(ObjectId()),
                                 origin="venue", fuel_pending=True, hacked="yes")], USER_ID, 334)
    doc = self.m.db.team_data.insert_one.call_args.args[0]
    for field in ("scouter_team", "excluded", "uploaded_by", "origin", "fuel_pending", "hacked"):
        self.assertNotIn(field, doc)
    self.assertEqual(doc["match_key"], "2026nyny_qm12")  # recomputed from event_key + label

def test_duplicate_and_non_dict_and_created_at(self):
    self.m.db.team_data.aggregate.return_value = [{"scouter": {"username": "sam"}}]
    results = self.m.import_matches([entry(), "junk"], USER_ID, 334)
    self.assertEqual([r["status"] for r in results], ["duplicate", "rejected"])
    self.m.db.team_data.aggregate.return_value = []
    self.m.import_matches([entry(created_at="2026-03-01T10:00:00")], USER_ID, 334)
    self.assertEqual(self.m.db.team_data.insert_one.call_args.args[0]["created_at"],
                     datetime(2026, 3, 1, 10, tzinfo=timezone.utc))
```

  Here `form()` uses `"_event_key": "2026nyny"`, so also cover an entry carrying `event_key` instead (as an export file would).
- [ ] **Step 2: Run the tests.** Expected: FAIL (`AttributeError: import_matches`).
- [ ] **Step 3: Implement `import_matches`** per the interface.
- [ ] **Step 4: Run the tests.** Run `tests.test_transfer tests.test_match_day`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Import match entries idempotently with team-checked credit"`.

---

### Task 3: `export_data`

**Files:**
- Modify: `app/scout/scouting_utils.py` (new method)
- Test: `tests/test_transfer.py` (the `ExportTests` class)

**Interfaces:**
- Produces: `ScoutingManager.export_data(self, user_id: str, team_number, now: datetime | None = None) -> dict`. It returns `{"format": "castle-entries", "version": 1, "exported_at": iso, "team": team_number, "users": [...], "matches": [...], "pits": [...]}`, and everything in it is JSON-safe.
  - **matches:** `team_data.aggregate([*self._visible_records(user_id, team_number), {"$match": {"created_at": {"$gte": datetime(now.year, 1, 1, tzinfo=timezone.utc)}}}, {"$project": {"scouter": 0}}])`.
  - **pits:** `pit_scouting.aggregate([*self._visible_records(user_id, team_number), {"$project": {"scouter": 0}}])`.
  - **users:** `users.find({"teamNumber": team_number}, {"_id": 1, "username": 1, "teamNumber": 1})` when there's a team. Otherwise the user's own document with the same projection.
  - **JSON-safe conversion:** a module helper `_jsonable(value)` that works recursively. ObjectId becomes str, and datetime becomes `.isoformat()`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_export_shape_season_filter_and_roster(self):
    oid = ObjectId()
    self.m.db.team_data.aggregate.return_value = [{"_id": oid, "scouter_id": ObjectId(USER_ID),
                                                   "created_at": datetime(2026, 3, 1, tzinfo=timezone.utc)}]
    self.m.db.pit_scouting.aggregate.return_value = []
    self.m.db.users.find.return_value = [{"_id": ObjectId(USER_ID), "username": "tester", "teamNumber": 334}]
    data = self.m.export_data(USER_ID, 334, now=datetime(2026, 11, 11, tzinfo=timezone.utc))
    self.assertEqual((data["format"], data["version"], data["team"]), ("castle-entries", 1, 334))
    self.assertEqual(data["matches"][0]["_id"], str(oid))
    self.assertEqual(data["matches"][0]["created_at"], "2026-03-01T00:00:00+00:00")
    pipeline = self.m.db.team_data.aggregate.call_args.args[0]
    self.assertIn({"$match": {"created_at": {"$gte": datetime(2026, 1, 1, tzinfo=timezone.utc)}}}, pipeline)
    self.assertIn({"$project": {"scouter": 0}}, pipeline)
    self.assertEqual(self.m.db.users.find.call_args.args, ({"teamNumber": 334}, {"_id": 1, "username": 1, "teamNumber": 1}))
    json.dumps(data)  # JSON-safe

def test_export_never_carries_secrets(self):
    # even if a document somehow had them, the user projection is fixed and no joined scouter doc remains
    self.m.db.team_data.aggregate.return_value = []
    self.m.db.pit_scouting.aggregate.return_value = []
    self.m.db.users.find.return_value = []
    self.m.export_data(USER_ID, 334)
    projection = self.m.db.users.find.call_args.args[1]
    self.assertNotIn("password_hash", projection)
    self.assertNotIn("email", projection)
```

- [ ] **Step 2: Run the tests.** Expected: FAIL (`AttributeError: export_data`).
- [ ] **Step 3: Implement `export_data` and `_jsonable`.**
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Export the team's current-season entries, pits and public roster"`.

---

### Task 4: Export and import routes

**Files:**
- Create: `app/scout/routes/transfer.py`
- Modify: `app/scout/routes/__init__.py` (import `transfer`, add it to `__all__`)
- Modify: `app/app.py` (set `MAX_CONTENT_LENGTH = 50 * 1024 * 1024` in the existing `app.config.update(...)`)
- Test: `tests/test_transfer.py` (the `RouteTests` class: a minimal Flask app registering `transfer.export_entries` at `/scouting/export` and `transfer.import_entries` at `/scouting/import`, with `common.scouting_manager` and `transfer.current_user` patched, as `AddRedirectTests` does)

**Interfaces:**
- Consumes: `export_data` (Task 3), `import_matches` (Task 2), and `zero_scored_fuel` from `..match13_fuel`.
- Produces:
  - `export_entries()` handles `GET /scouting/export` with `@login_required`. It returns the JSON with `Content-Disposition: attachment; filename="castle-<team or 'me'>-<YYYY-MM-DD>.json"`.
  - `import_entries()` handles `POST /scouting/import` with `@login_required` and `@limiter.limit("30 per minute")`.
    - **No team:** 403 `{"error": "Join a team to import entries."}`.
    - **Payload source:** a `request.files["file"]` upload is parsed with `json.load`, and a non-JSON file is a 400. Otherwise the JSON body is used; a JSON body over 5 MB is a 413.
    - **Envelope:** it must be a dict with `format == "castle-entries"` and `version == 1`, and `matches` must be a list (or missing). Otherwise 400.
    - **Count cap:** more than 500 `matches` in a JSON body is a 413.
    - **Pits:** a pit entry is `already_have` if `pit_scouting.find_one({"_id": oid})` finds it, otherwise `rejected` (see the pre-decision). The results go under `pit_results`.
    - **Fuel estimates:** for every `saved` result whose entry has zero scored fuel (`zero_scored_fuel(entry)`), call `current_app.extensions["match13_fuel"].enroll(result["id"], {**entry, "_event_key": entry.get("event_key") or entry.get("_event_key")})`. Do it inside try/except, logging the exception, as the add route does.
    - **Response:** `jsonify(results=[...], pit_results=[...], counts={status: n})`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_export_downloads_a_dated_json_file(self):
    self.manager.export_data.return_value = {"format": "castle-entries", "version": 1, "matches": []}
    r = self.client.get("/scouting/export")
    self.assertEqual(r.status_code, 200)
    self.assertRegex(r.headers["Content-Disposition"], r'attachment; filename="castle-334-\d{4}-\d{2}-\d{2}\.json"')

def test_json_import_returns_results_counts_and_enrolls_zero_fuel(self):
    self.manager.import_matches.return_value = [{"key": "c1", "status": "saved", "id": "rid"}, {"key": "c2", "status": "duplicate"}]
    r = self.client.post("/scouting/import", json=envelope([{"client_id": "c1", "event_key": "2026nyny"}, {"client_id": "c2", "auto_fuel": 4}]))
    self.assertEqual(r.json["counts"], {"saved": 1, "duplicate": 1})
    self.service.enroll.assert_called_once()
    self.assertEqual(self.service.enroll.call_args.args[0], "rid")
    self.assertEqual(self.service.enroll.call_args.args[1]["_event_key"], "2026nyny")

def test_file_import(self):
    self.manager.import_matches.return_value = []
    r = self.client.post("/scouting/import", data={"file": (io.BytesIO(json.dumps(envelope([])).encode()), "x.json")},
                         content_type="multipart/form-data")
    self.assertEqual(r.status_code, 200)

def test_bad_payloads_are_400(self):
    for body in [b"{not json", json.dumps({"format": "other", "version": 1}).encode(),
                 json.dumps({"format": "castle-entries", "version": 2}).encode(),
                 json.dumps({"format": "castle-entries", "version": 1, "matches": "x"}).encode()]:
        self.assertEqual(self.client.post("/scouting/import", data=body, content_type="application/json").status_code, 400, body)
    bad_file = {"file": (io.BytesIO(b"nope"), "x.json")}
    self.assertEqual(self.client.post("/scouting/import", data=bad_file, content_type="multipart/form-data").status_code, 400)

def test_too_many_json_entries_is_413(self):
    self.assertEqual(self.client.post("/scouting/import", json=envelope([{}] * 501)).status_code, 413)

def test_pit_entries_outside_venue_mode(self):
    existing = str(ObjectId())
    self.manager.import_matches.return_value = []
    self.manager.db.pit_scouting.find_one.side_effect = lambda q, *a: {"_id": q["_id"]} if str(q["_id"]) == existing else None
    r = self.client.post("/scouting/import", json={**envelope([]), "pits": [{"_id": existing}, {"_id": str(ObjectId())}, {}]})
    self.assertEqual([p["status"] for p in r.json["pit_results"]], ["already_have", "rejected", "rejected"])

def test_teamless_uploader_is_403(self):
    # current_user.teamNumber = None
    self.assertEqual(self.client.post("/scouting/import", json=envelope([])).status_code, 403)
```

- [ ] **Step 2: Run the tests.** Expected: FAIL (ImportError: `transfer`).
- [ ] **Step 3: Implement** `transfer.py`, the `__init__` registration and `MAX_CONTENT_LENGTH`.
- [ ] **Step 4: Run the tests.** Run `tests.test_transfer tests.test_security tests.test_route_logging tests.test_match_day`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Add entry export and import routes"`.

---

### Task 5: List page buttons

**Files:**
- Modify: `app/templates/scouting/list.html`. In the header action group (lines 44-52), before Export CSV, add `<a href="{{ url_for('scouting.export_entries') }}" class="btn btn-secondary">Download all (JSON)</a>` and an **Import file** `<label class="btn btn-secondary">` wrapping `<input type="file" id="importFile" accept=".json,application/json" class="sr-only">`. Below the header, add a `<p id="importStatus" class="help" role="status"></p>`.
- Modify: `app/static/js/scout/list.js`. On the file input's `change`: POST a `FormData` holding the file to `/scouting/import` with `fetch`. CSRF is added by `base.html`'s fetch patch. Then set `#importStatus` to `Imported: N saved, N already had, N duplicates, N rejected` from `counts`, or to the server's `error`. Reset the input.
- Modify: bump `list.js`'s `?v=` in `list.html`.

**Interfaces:** consumes Task 4's routes and response shape.

- [ ] **Step 1: Implement** the template and JS. There's no unit seam in `list.js`; it's verified in Task 6's browser check.
- [ ] **Step 2: Run** `npm test` and `.venv/Scripts/python.exe -m unittest tests.test_transfer tests.test_scouting_pagination -v`. Expected: PASS.
- [ ] **Step 3: Commit:** `git commit -m "Add download and import buttons to the scouting list"`.

---

### Task 6: Browser check and regression

- [ ] **Step 1: Check in a browser.** Use the batch 1 preview approach (`tests.app_harness.start_app()` plus auto-login, served on `:5055`). Point `common.scouting_manager.export_data` and `import_matches` at stubs, or use the real methods over a MagicMock db, and drive the page with playwright-cli:
  1. `/scouting` shows **Download all (JSON)** and **Import file**.
  2. The download returns a `.json` attachment.
  3. Choosing a valid file shows the "Imported: …" summary.
  4. Choosing a bad file shows the error and not a stack trace.
  5. The console has no errors.
- [ ] **Step 2: Full regression.** Run `.venv/Scripts/python.exe -m unittest tests.test_transfer tests.test_match_day tests.test_security tests.test_bug_fixes tests.test_match13_fuel tests.test_scouting_pagination tests.test_scouting_performance tests.test_scout_routes_common tests.test_route_logging tests.test_safe_url tests.test_pit_form -v` and `npm test`. Expected: all OK.
- [ ] **Step 3: Fix anything found.** Write a failing test first in `tests/test_transfer.py`, then fix and commit.
