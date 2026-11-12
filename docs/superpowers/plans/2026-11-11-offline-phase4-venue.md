# Offline Phase 4 (Venue Laptop) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The lead's laptop runs Castle in venue mode against a local MongoDB.
- The night before, it loads the team's export file as exact copies.
- At the venue, it takes scanned entries, marked as created on the laptop with fuel pending.
- Its normal pages work with no internet, and "fuel pending" entries stay out of the fuel averages.
- It pushes back only its own entries.
- Two CLI commands create the lead's login and reset the laptop between events.

**Architecture:**
- `app.config["VENUE_MODE"]` comes from the environment variable `VENUE_MODE=1`.
- `ScoutingManager.import_matches` gains a `venue` switch.
- New manager methods handle stub users and venue pits. `export_data` gains a `scope`.
- A new `app/venue.py` registers the `flask venue-user` and `flask venue-reset` commands.
- Fuel averages use one helper that skips `fuel_pending` records.
- The pages the lead uses stop depending on CDNs and on TBA answering.

**Spec:** `docs/superpowers/specs/2026-11-11-offline-venue-mode-design.md`, covering section 1's venue-mode rules and section 4 in full.

## Global Constraints

- **Never connect to the user's MongoDB.** Tests use `manager()` (`tests/test_match_day.py`), the harness, or `app.test_cli_runner()` on a harness app.
- **Venue mode is off unless `VENUE_MODE=1`.** With it off, nothing in this phase changes behaviour on the main server.
- **Exact copies (venue only).** An entry with a valid `_id` that isn't on the laptop is inserted with that `_id` and only these fields:
  - **Identity:** `team_number` (int), `event_code`, `match_number`, `alliance`, `event_key`, `match_key`.
  - **Scouting data:** every key `_record_fields` produces, plus `auto_climb`.
  - **Status:** `excluded`, `client_id`.
  - **Metadata:** `scouter_id` (ObjectId), `created_at` (datetime), `uploaded_by` (ObjectId).
- **Records created on the laptop** (venue mode, no existing-format `_id`) get:
  - `origin: "venue"`;
  - `venue_at: <now UTC>`;
  - `fuel_pending: True` when `zero_scored_fuel(entry)`.
- **Stub users** have exactly `{_id, username, teamNumber, venue_stub: True}`. They're created only when `teamNumber == the lead's team` and the `_id` isn't on the laptop already. `User.check_password` returns False when there's no `password_hash`.
- **Push tracking.** `venue_meta` holds one document, `{_id: "push", at: <UTC datetime>}`. The `GET /scouting/export?scope=venue` export updates it.
- **`venue-reset`** refuses while any `origin: "venue"` record has `venue_at > push.at`, or exists when no push is recorded. `--force` overrides that. A reset deletes every document in `team_data` and `pit_scouting` and in `venue_meta`. It leaves users.
- **Vendored files:**
  - `app/static/vendor/chart-4.4.1.umd.min.js`, from `https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js`, MIT;
  - `app/static/vendor/Sortable-1.15.2.min.js`, from `https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js`, MIT.
- Commit trailers as before. Do not push.

## Review Focus

1. **The night-before import loads a record the laptop already has**, such as a second import of the same file. It's `already_have`, and nothing is overwritten (Task 1 `exact copies are not overwritten`).
2. **A QR entry from a scout who isn't in the export**, like a rookie. A stub is created from `scout` and the entry is saved (Task 1 `rookie from qr payload`).
3. **A stub user's name typed at login** must fail cleanly, without a 500 (Task 2 `stub users cannot log in`).
4. **A team whose venue entries are all fuel-pending** shows no fuel average rather than 0 (Task 3 `fuel averages skip pending`).
5. **Compare with TBA unreachable** still returns the team's stats (Task 4 `compare without tba`).

---

### Task 1: Venue-mode import

**Files:**
- Modify: `app/app.py`. Add `VENUE_MODE=os.getenv("VENUE_MODE") == "1"` to the config.
- Modify: `app/scout/scouting_utils.py`.
  - `_insert_record(..., extra: dict | None = None)` merges `extra` into the document.
  - Change the signature to `import_matches(self, entries, uploader_id, uploader_team, venue: bool = False)`.
  - Add `ensure_stub_users(self, users: list, team) -> int`.
  - Add `import_pits_venue(self, pits: list) -> list[dict]`.
- Modify: `app/scout/routes/transfer.py`. When `current_app.config.get("VENUE_MODE")`:
  - create stubs from `payload["users"]` plus `payload["scout"]` before importing;
  - pass `venue=True`;
  - use `import_pits_venue` for pits;
  - skip the Match13 enroll (there's no internet).
- Test: `tests/test_transfer.py`, class `VenueImportTests`.

**Behaviour of `import_matches(venue=True)`:**
- **Existence:** a plain `team_data.find_one({"$or": seen})` over the whole laptop DB, since the laptop is the lead's own machine. A hit is `already_have`.
- **Valid `_id`, not present:** an exact copy (Global Constraints), status `saved`. The scout check still applies (uploader or same team), so stubs must exist first.
- **Anything else:** builds through `_insert_record` with `extra={"origin": "venue", "venue_at": now, **({"fuel_pending": True} if zero_scored_fuel(entry) else {})}`.

**Behaviour of `import_pits_venue`:** each pit with a valid `_id` that isn't present is inserted as-is, with `_id` and `scouter_id` as ObjectIds and datetimes parsed. Pits already present are `already_have`. Invalid ones are `rejected`.

- [ ] **Step 1: Write the failing tests:**
  - `exact copies keep id and protected fields`: an entry with `_id`, `excluded: True`, `match_key`, `event_key`, `client_id` and `auto_fuel: 7` (with `scouter_id` the uploader) is stored with the same `_id` (ObjectId), `excluded` True, and the given keys. A `hacked` field is dropped.
  - `exact copies are not overwritten`: `find_one` returns a doc, so the status is `already_have` and `insert_one` isn't called.
  - `venue-created records are marked`: an entry without `_id` and with empty fuel gets `origin` `"venue"`, a `venue_at` datetime and `fuel_pending` True. An entry with `auto_fuel: 3` has no `fuel_pending`.
  - `rookie from qr payload`: route level, with `VENUE_MODE` True. Post `{scout: {_id: R, username: "rookie", teamNumber: 334}, matches: [{scouter_id: R, ...}]}`. A stub is inserted for R, and the import is called with `venue=True`. A `scout` from team 999 creates no stub.
  - `main server ignores venue fields`: with `VENUE_MODE` False, `scout` and `users` create nothing, and `import_matches` is called without `venue=True`.
- [ ] **Step 2: Run the tests.** Run `.venv/Scripts/python.exe -m unittest tests.test_transfer -v`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Run `tests.test_transfer tests.test_match_day`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Venue-mode import: exact copies, stub scouts, laptop-created entries marked"`.

---

### Task 2: Export scope, the CLI commands and stub logins

**Files:**
- Modify: `app/scout/scouting_utils.py`. Change the signature to `export_data(self, user_id, team_number, now=None, scope="all")`. With `scope == "venue"`, add `{"$match": {"origin": "venue"}}` and leave out the season filter.
- Modify: `app/scout/routes/transfer.py`. `GET /scouting/export?scope=venue` is allowed only in venue mode (a 404 otherwise). It passes the scope and upserts `venue_meta` `{_id: "push"}` with `at = now`.
- Modify: `app/models.py`. `check_password` returns False when `password_hash` is falsy.
- Create: `app/venue.py` with `register_venue_commands(app)`, called from `create_app`. It defines:
  - `flask venue-user --username U --password P --team N`, which calls the auth module's `UserManager.create_user(f"{U}@venue.local", U, P, N)` and prints the result;
  - `flask venue-reset [--force]`, which follows the reset rule in Global Constraints and prints the counts deleted, or why it refused.
  - Both refuse unless `VENUE_MODE` is on: "Venue commands only run with VENUE_MODE=1 (they delete data)."
- Test: `tests/test_venue.py` (new). Use the harness `start_app()` with `app.config["VENUE_MODE"] = True` and `app.test_cli_runner()`, patch `app.venue` to see `common.scouting_manager`, and check the MagicMock db calls.

- [ ] **Step 1: Write the failing tests:**
  - `venue export scope`: `export_data(..., scope="venue")`'s pipeline contains `{"$match": {"origin": "venue"}}` and no `created_at` filter.
  - `venue export records the push and is venue only`: the route with `VENUE_MODE` True upserts `venue_meta`. With it False, `?scope=venue` is a 404.
  - `reset refuses unpushed venue entries`: `venue_meta.find_one` returns `{at: T}`, and `team_data.count_documents({"origin": "venue", "venue_at": {"$gt": T}})` returns 2. The command exits with a non-zero code and "2 entries", and `delete_many` isn't called. With `--force`, it deletes `team_data`, `pit_scouting` and `venue_meta`.
  - `reset refuses outside venue mode`.
  - `venue-user creates a login`: `UserManager.create_user` is patched, and its call args are as above.
  - `stub users cannot log in`: `User.create_from_db({"_id": ObjectId(), "username": "s"}).check_password("x")` is False.
- [ ] **Step 2: Run the tests.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Run `tests.test_venue tests.test_transfer tests.test_security`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Add venue export scope, venue-user and venue-reset commands"`.

---

### Task 3: Leave fuel-pending entries out of fuel averages

**Files:**
- Modify: `app/scout/scouting_utils.py`.
  - Add `_fuel_value(field) -> {"$cond": [{"$eq": ["$fuel_pending", True]}, None, {"$ifNull": ["$" + field, 0]}]}`.
  - Use `{"$avg": _fuel_value(f)}` for every `{"$avg": {"$ifNull": ["$<fuel>", 0]}}`, in `get_compare_stats` (about lines 628-636) and `get_team_leaderboard` (about lines 748-760). `$avg` skips nulls.
  - Project `fuel_pending` in `get_all_scouting_data`.
- Modify: `app/templates/scouting/_match_list.html`. Add `{% if data.fuel_pending %}<span class="badge badge-amber">Fuel pending</span>{% endif %}` next to the Excluded badge.
- Test: `tests/test_transfer.py` or a new `tests/test_venue.py`, class `FuelPendingTests`:
  - `fuel averages skip pending`: in the compare and leaderboard pipelines, every fuel `$avg` is the `$cond` form (assert on the `$group` stage). No `{"$avg": {"$ifNull": ["$auto_fuel", 0]}}` remains.
  - The list projection includes `fuel_pending`.

- [ ] **Steps 1–5:** failing test, run (FAIL), implement, run (`tests.test_venue tests.test_match_day tests.test_scouting_performance`, PASS), commit `"Leave fuel-pending entries out of fuel averages"`.

---

### Task 4: The lead's pages work without the internet

**Files:**
- Modify: `app/scout/routes/lighthouse.py:70`. Use `team_info = TBAInterface().get_team(team_key) or {}`.
- Create: the two vendor files. Modify `app/templates/lighthouse.html` (Chart.js) and `app/templates/lighthouse/auton.html` (Sortable) to load them.
- Modify: `app/templates/base.html`. When `config.VENUE_MODE`, show a banner under the header: "Venue mode: this is a local copy of Castle on this laptop, not castlescouting.com."
- Test:
  - `tests/test_venue.py`, `compare without tba`: with `TBAInterface.get_team` returning None and stats present, `/api/compare?team1=254&team2=1678` is 200 and holds both teams.
  - `tests/test_browser_resilience.js`: `lead pages load no CDN scripts`, the same assertion as the scout-form test, for `lighthouse.html` and `lighthouse/auton.html`.
  - `tests/test_venue.py`, `venue banner only in venue mode`.

- [ ] **Steps 1–5:** failing tests, run (FAIL), implement (with `curl -fsSL` for the vendor files), run (PASS), commit `"Make the lead's pages work offline on the venue laptop"`.

---

### Task 5: The setup guide, browser check and regression

**Files:**
- Create: `docs/venue-mode.md`, a step-by-step guide for a student:
  1. **What venue mode is**, and when to use it.
  2. **One-time laptop setup on Windows:**
     - install Python 3.12+ and MongoDB Community Server (the service starts on boot);
     - `git clone`, `python -m venv .venv`, `.venv\Scripts\pip install -r requirements.txt`;
     - a `.env` with `MONGO_URI=mongodb://localhost:27017/castle`, a random `SECRET_KEY` and `VENUE_MODE=1`, with no TBA key.
  3. `flask --app app.app venue-user --username … --password … --team 334`.
  4. **Running it:** `flask --app app.app run --port 5000`, then open `http://localhost:5000`. Camera access works on localhost.
  5. **Night before:** `venue-reset`; then on castlescouting.com, **Download all (JSON)**; then on the laptop, **Import file**.
  6. **Scouts' phones:** while online, open the scout form and pick the event, so the form and schedule are saved. "Show QR" when the lead asks.
  7. **At the venue:** "Scan QR"; the leaderboard, compare and auto paths. "Fuel pending" means the AI fuel count happens after upload.
  8. **After the event:** the laptop's **Download new entries** (link `/scouting/export?scope=venue`, shown on the list page only in venue mode); then **Import file** on castlescouting.com; then `venue-reset`.
  9. **Troubleshooting:** the camera is blocked; the phone shows the offline page (it wasn't set up online); "Log in to upload".
- Modify: `app/templates/scouting/list.html`. Add a **Download new entries** link when `config.VENUE_MODE`.
- [ ] **Step 1: Write** the guide and the link.
- [ ] **Step 2: Check in a browser.** Use a preview with `VENUE_MODE=1` (mocked Mongo):
  - the banner shows;
  - list shows **Download new entries**;
  - `/scouting/scan` loads;
  - compare and auto paths load with no CDN requests (check that the request log has no `cdn.jsdelivr.net`).
- [ ] **Step 3: Full regression.** Run every `tests/test_*.py` module and `npm test`. Expected: all OK.
- [ ] **Step 4: Commit:** `git commit -m "Add the venue laptop guide"`.
