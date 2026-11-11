# Match-Day Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** New match records store TBA event and match keys. Same-team duplicates are blocked. The add form survives crashes and jumps to the next match. Records can be excluded from stats.

**Architecture:** The server work lives in the existing layers:
- key parsing in `TBA.py`
- identity, the duplicate check and exclusion in `ScoutingManager` (`scouting_utils.py`)
- redirects in the `add` route

Browser-side draft and next-match logic is pure functions in a new `add-flow.js`, unit-tested with `node:vm`. The DOM wiring lives in `add.js`.

**Tech Stack:** Flask, pymongo aggregation pipelines, Jinja, vanilla JS, `unittest`, `node --test`.

**Spec:** `docs/superpowers/specs/2026-11-11-match-day-fixes-design.md`. Read it first; this plan argues from it.

## Global Constraints

- **Never connect to or write to the user's MongoDB.** Tests use mocks only (`tests/app_harness.py`, or a `ScoutingManager` built with `__new__` and a `MagicMock` db).
- Python tests: `.venv/Scripts/python.exe -m unittest tests.<module> -v`. `discover` does not work here, and pytest is not installed.
- JS tests: `npm test`.
- No backfill, no migration, no new index, no unique constraint.
- Display fields `event_code` (event name) and `match_number` (label like `Qual 12`) keep being stored exactly as today.
- Event key regex: `\d{4}[a-z0-9]+` (full match). Station: `(red|blue)[1-3]`. Draft id: `[A-Za-z0-9-]{1,64}`. Match labels in redirect URLs are capped at 32 characters.
- A missing or invalid key never rejects a record. The record saves without keys and without a duplicate check.
- Drafts live under `localStorage` key `castle:scout-drafts:<user id>` and are pruned after 24 hours (`86400000` ms).
- Use existing CSS component classes (`card`, `btn`, `btn-primary`, `btn-secondary`, `badge`, `badge-gray`). If you introduce a Tailwind class not used anywhere yet, run `npm run build:css`.
- Commit messages end with a blank line and then `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Do not push.

## Review Focus

1. **Phone locked mid-match.** `pagehide` may not fire, but the draft must still be saved. Save on `visibilitychange` to `hidden` too (Task 7 browser check, item 4).
2. **Storage unavailable.** In private mode `localStorage` can throw on access or on write. The form must work exactly as today, with no uncaught errors (Task 6 test `storage that throws is ignored`).
3. **Edit without an identity change.** Mongo rejects an empty `$unset`, so the update must not contain an `$unset` key at all (Task 4 test `test_edit_without_identity_change_sends_no_unset`).
4. **Counter taps.** The `+`/`−` step buttons fire a synthetic `change` event (`isTrusted` false), but the tap itself is a trusted `click`. Counter taps must still mark the draft dirty and save it (Task 7 browser check, item 3).
5. **Tampered redirect params.** Values such as `_station=../x`, a 500-character label or `_event_key=javascript:` must be dropped or capped before reaching the redirect URL. The label is only ever compared in JS, never rendered (Task 3 test `test_invalid_redirect_params_are_dropped`).

---

### Task 1: Year-agnostic TBA match key helper

**Files:**
- Modify: `app/scout/TBA.py` (add a module-level helper near the imports)
- Modify: `app/scout/match13_fuel.py:38-49` (`match_key` delegates to it)
- Test: `tests/test_match_day.py` (new)

**Interfaces:**
- Produces: `EVENT_KEY_PATTERN = re.compile(r"\d{4}[a-z0-9]+\Z")` and `tba_match_key(event_key: str, label: str) -> str | None` in `app/scout/TBA.py`.
- `match13_fuel.match_key(event, label)` keeps its signature and its 2026-only guard.

- [ ] **Step 1: Write the failing tests** in a new `tests/test_match_day.py`, class `MatchKeyTests`:

```python
from app.scout.TBA import tba_match_key
from app.scout.match13_fuel import match_key

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
```

- [ ] **Step 2: Run the tests.** Run: `.venv/Scripts/python.exe -m unittest tests.test_match_day -v`. Expected: an ImportError for `tba_match_key`.
- [ ] **Step 3: Implement `tba_match_key`** in `TBA.py`. Move the body of the label parsing out of `match13_fuel.match_key`: the passthrough regex plus the three `(pattern, suffix)` pairs. Guard with `EVENT_KEY_PATTERN` instead of the 2026 pattern. Then `match13_fuel.match_key` becomes `return tba_match_key(event, label) if EVENT_PATTERN.fullmatch(event) else None`, importing from `.TBA`.
- [ ] **Step 4: Run the tests.** Run `tests.test_match_day` and `tests.test_match13_fuel`. Expected: all PASS.
- [ ] **Step 5: Commit:** `git add app/scout/TBA.py app/scout/match13_fuel.py tests/test_match_day.py` then `git commit -m "Add year-agnostic TBA match key helper"` (with trailer).

---

### Task 2: Store keys and block same-team duplicates on add

**Files:**
- Modify: `app/scout/scouting_utils.py:148-175` (`add_scouting_data`)
- Test: `tests/test_match_day.py` (class `AddRecordTests`)

**Interfaces:**
- Consumes: `tba_match_key`, `EVENT_KEY_PATTERN` (Task 1).
- Produces: `add_scouting_data(self, data: dict, scouter_id: str, team_number=None) -> tuple[bool, str]`.
  - `team_number` is the *scout's* team, possibly `None`.
  - On success it returns `(True, inserted_id)`.
  - On a duplicate it returns `(False, "Team {robot} in {label} was already scouted by {username}. Edit that entry from the scouting list instead.")`.
- Produces: stored documents gain `event_key` and `match_key`, but only when both are valid.

- [ ] **Step 1: Write the failing tests.** Build the manager as `m = ScoutingManager.__new__(ScoutingManager); m.db = MagicMock()`. Use a helper `form(**kw)` that returns `{"team_number": "254", "event_code": "NYC Regional", "match_number": "Qual 12", "_event_key": "2026nyny", **kw}`.

```python
def test_valid_keys_are_stored(self):
    m.db.team_data.aggregate.return_value = []
    ok, _ = m.add_scouting_data(form(), USER_ID, 334)
    doc = m.db.team_data.insert_one.call_args.args[0]
    self.assertTrue(ok)
    self.assertEqual((doc["event_key"], doc["match_key"]), ("2026nyny", "2026nyny_qm12"))
    self.assertEqual((doc["event_code"], doc["match_number"]), ("NYC Regional", "Qual 12"))

def test_missing_or_invalid_event_key_saves_without_keys_or_check(self):
    for bad in ["", "javascript:", None]:
        m.db.reset_mock()
        ok, _ = m.add_scouting_data(form(_event_key=bad), USER_ID, 334)
        doc = m.db.team_data.insert_one.call_args.args[0]
        self.assertTrue(ok)
        self.assertNotIn("match_key", doc)
        m.db.team_data.aggregate.assert_not_called()

def test_same_team_duplicate_is_blocked_with_scout_name(self):
    m.db.team_data.aggregate.return_value = [{"scouter": {"username": "sam"}}]
    ok, msg = m.add_scouting_data(form(), USER_ID, 334)
    self.assertFalse(ok)
    self.assertEqual(msg, "Team 254 in Qual 12 was already scouted by sam. Edit that entry from the scouting list instead.")
    m.db.team_data.insert_one.assert_not_called()

def test_duplicate_query_scopes_to_team_and_skips_excluded(self):
    m.db.team_data.aggregate.return_value = []
    m.add_scouting_data(form(), USER_ID, 334)
    pipeline = m.db.team_data.aggregate.call_args.args[0]
    self.assertEqual(pipeline[0]["$match"], {"match_key": "2026nyny_qm12", "team_number": 254, "excluded": {"$ne": True}})
    self.assertIn({"$match": {"scouter.teamNumber": 334}}, pipeline)

def test_teamless_scout_is_checked_against_own_records_only(self):
    m.db.team_data.aggregate.return_value = []
    m.add_scouting_data(form(), USER_ID, None)
    self.assertIn({"$match": {"scouter_id": ObjectId(USER_ID)}}, m.db.team_data.aggregate.call_args.args[0])
```

- [ ] **Step 2: Run the tests.** Run `tests.test_match_day`. Expected: the 5 new tests FAIL (there is no `event_key` in the doc, and `aggregate` is never called).
- [ ] **Step 3: Implement it in `add_scouting_data`.**
  - Read `_event_key` with `str(data.get("_event_key") or "")`.
  - When it matches `EVENT_KEY_PATTERN` and `tba_match_key(...)` returns a key, set both keys on `team_data`.
  - If a key was set, run the pipeline asserted above: first `$match`, `SCOUTER_LOOKUP`, `UNWIND_SCOUTER`, the scope `$match`, `{"$limit": 1}`. Return the duplicate message on a hit.
  - Add a `# shortcut: check-then-insert can race when two scouts save in the same second; a unique index needs the scout's team on the record` comment.
  - Pass the `team_number` keyword at the only caller, `records.py` `add` (`team_number=current_user.teamNumber`).
- [ ] **Step 4: Run the tests.** Run `tests.test_match_day tests.test_match13_fuel`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Store TBA keys on new match records and block same-team duplicates"`.

---

### Task 3: Add route returns to the add form (next match on success, same match on failure)

**Files:**
- Modify: `app/scout/routes/records.py:27-72` (`add`)
- Modify: `tests/test_match13_fuel.py:456` (give the add rule `endpoint='scouting.add'`)
- Test: `tests/test_match_day.py` (class `AddRedirectTests`, using the same minimal Flask fixture as `RouteTests` in `tests/test_match13_fuel.py:451-465`; register `scouting.add` for GET and POST)

**Interfaces:**
- Consumes: `EVENT_KEY_PATTERN` (Task 1), `add_scouting_data(..., team_number=)` (Task 2).
- Produces: query params on the add page that Task 7 reads:
  - `event` (event key)
  - `after` (last saved label, success only)
  - `match` (label to reselect, failure only)
  - `station`
  - `saved` (draft id, success only)
- Produces: helper `_add_form_url(data: dict, saved: bool) -> str` in `records.py`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_success_redirects_to_next_match_with_validated_params(self):
    # manager.add_scouting_data.return_value = (True, oid)
    r = post({"_event_key": "2026nyny", "match_number": "Qual 12", "_station": "red2", "_draft_id": "abc-123", **base})
    q = parse_qs(urlparse(r.location).query)
    self.assertEqual(urlparse(r.location).path, "/scouting/add")
    self.assertEqual(q, {"event": ["2026nyny"], "after": ["Qual 12"], "station": ["red2"], "saved": ["abc-123"]})

def test_failure_redirects_to_same_match_without_saved(self):
    # manager.add_scouting_data.return_value = (False, "dup")
    q = parse_qs(urlparse(post({... same ...}).location).query)
    self.assertEqual(q, {"event": ["2026nyny"], "match": ["Qual 12"], "station": ["red2"]})

def test_invalid_redirect_params_are_dropped(self):
    q = parse_qs(urlparse(post({"_event_key": "javascript:", "match_number": "x" * 500,
                                "_station": "../x", "_draft_id": "a b<"}).location).query)
    self.assertNotIn("event", q); self.assertNotIn("station", q); self.assertNotIn("saved", q)
    self.assertEqual(q["after"], ["x" * 32])

def test_bad_auto_path_json_returns_to_add_form(self):
    r = post({"auto_path": "{not json", "_event_key": "2026nyny", "match_number": "Qual 1"})
    self.assertEqual(urlparse(r.location).path, "/scouting/add")
```

- [ ] **Step 2: Run the tests.** Run `tests.test_match_day`. Expected: FAIL, because the redirect goes to `/scouting`.
- [ ] **Step 3: Implement `_add_form_url`.**
  - Build `url_for("scouting.add", **params)` and include each param only when it validates per Global Constraints.
  - The label is `str(...)[:32]`, under `after` when `saved` is true and under `match` otherwise.
  - Use it for the success redirect, the failure redirect and the invalid-auto-path redirect. Keep the existing flash messages.
  - Update the `test_match13_fuel.py` fixture endpoint.
- [ ] **Step 4: Run the tests.** Run `tests.test_match_day tests.test_match13_fuel tests.test_security tests.test_route_logging`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Return to the add form for the next match after saving"`.

---

### Task 4: Edit unlinks changed identity and toggles exclusion

**Files:**
- Modify: `app/scout/scouting_utils.py:288-375` (`update_team_data`)
- Modify: `app/models.py:56-96` (`TeamData.__init__`: add `self.excluded: bool = data.get('excluded', False)`)
- Modify: `app/templates/scouting/edit.html` (a checkbox before the submit row at about line 390, styled like the `auto_climb` checkbox at line 237)
- Test: `tests/test_match_day.py` (class `EditTests`)

**Interfaces:**
- Produces: the stored field `excluded: bool`, which is written only by edit.
- The checkbox: `name="excluded" value="true"`, labelled `Exclude from stats (keeps the record and its notes)`, and checked when `team_data.excluded`.

- [ ] **Step 1: Write the failing tests.** Start from an existing doc `{"_id": oid, "event_code": "A", "match_number": "Qual 1", "team_number": 334, "alliance": "red", "event_key": "2026a", "match_key": "2026a_qm1"}` returned by `m.db.team_data.find_one`. Use `payload(**kw)` = the same identity plus `alliance: "red"`.

```python
def test_event_change_unsets_both_keys(self):
    m.update_team_data(str(oid), payload(event_code="B"), USER_ID)
    self.assertEqual(m.db.team_data.update_one.call_args.args[1]["$unset"], {"event_key": "", "match_key": ""})

def test_match_change_unsets_match_key_only(self):
    m.update_team_data(str(oid), payload(match_number="Qual 2"), USER_ID)
    self.assertEqual(m.db.team_data.update_one.call_args.args[1]["$unset"], {"match_key": ""})

def test_edit_without_identity_change_sends_no_unset(self):
    for change in [{}, {"team_number": "335"}]:
        m.update_team_data(str(oid), payload(**change), USER_ID)
        self.assertNotIn("$unset", m.db.team_data.update_one.call_args.args[1])

def test_excluded_checkbox_round_trips(self):
    m.update_team_data(str(oid), payload(excluded="true"), USER_ID)
    self.assertIs(m.db.team_data.update_one.call_args.args[1]["$set"]["excluded"], True)
    m.update_team_data(str(oid), payload(), USER_ID)
    self.assertIs(m.db.team_data.update_one.call_args.args[1]["$set"]["excluded"], False)
```

- [ ] **Step 2: Run the tests.** Expected: FAIL (`KeyError: '$unset'` / `'excluded'`).
- [ ] **Step 3: Implement the changes in `update_team_data`.**
  - Put `"excluded": _is_checked(data.get("excluded"))` into `updated_data`.
  - Build `unset` from the comparison with `existing_data`.
  - Pass `{"$set": updated_data, **({"$unset": unset} if unset else {})}`.
  - Add the model field and the checkbox.
- [ ] **Step 4: Run the tests.** Run `tests.test_match_day tests.test_bug_fixes`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Unlink edited match identity and add exclude-from-stats toggle"`.

---

### Task 5: Excluded records drop out of stats and are tagged in the list

**Files:**
- Modify: `app/scout/scouting_utils.py`. Add a module constant `COUNTED = {"$match": {"excluded": {"$ne": True}}}` next to `UNWIND_SCOUTER` (line 20). Prepend it in `get_match_alliances` (429), `get_compare_stats` (463), `get_auto_paths` (544) and `get_team_leaderboard` (580). Add `"excluded": 1` to the `get_all_scouting_data` projection (around line 219).
- Modify: `app/templates/scouting/_match_list.html:68`. After the alliance badge, add `{% if data.excluded %}<span class="badge badge-gray">Excluded</span>{% endif %}`.
- Test: `tests/test_match_day.py` (class `ExclusionTests`)

**Interfaces:**
- Produces: `COUNTED` (importable).

Leave `get_all_scouting_data`, `get_team_records`, `get_leaderboard_events`, `get_scouter_leaderboard` and `get_visible_fuel` unfiltered, per the spec.

- [ ] **Step 1: Write the failing tests:**

```python
def test_stat_pipelines_skip_excluded_records(self):
    m.db.team_data.aggregate.return_value = []
    calls = [lambda: m.get_match_alliances(USER_ID, 334), lambda: m.get_compare_stats(254, USER_ID, 334),
             lambda: m.get_auto_paths(254, USER_ID, 334), lambda: m.get_team_leaderboard(USER_ID, 334)]
    for call in calls:
        m.db.reset_mock(); m.db.team_data.aggregate.return_value = []
        call()
        self.assertIn(COUNTED, m.db.team_data.aggregate.call_args.args[0])

def test_list_and_scouter_counts_keep_excluded_records(self):
    m.get_scouter_leaderboard()
    self.assertNotIn(COUNTED, m.db.team_data.aggregate.call_args.args[0])
    m.get_all_scouting_data(334, USER_ID, page=1)
    pipeline = m.db.team_data.aggregate.call_args.args[0]
    self.assertNotIn(COUNTED, pipeline)
    self.assertEqual(next(s for s in pipeline if "$project" in s)["$project"]["excluded"], 1)
```

- [ ] **Step 2: Run the tests.** Expected: FAIL (ImportError `COUNTED`).
- [ ] **Step 3: Implement.** Add the constant, the 4 prepends, the projection and the badge.
- [ ] **Step 4: Run the tests.** Run `tests.test_match_day tests.test_scouting_pagination tests.test_scouting_performance tests.test_scout_routes_common`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Leave excluded records out of stats and tag them in the list"`.

---

### Task 6: Draft storage and next-match logic as pure functions

**Files:**
- Create: `app/static/js/scout/add-flow.js`. Use plain `function` declarations, so they are globals in the browser and on the `vm` context.
- Create: `tests/test_add_flow.js` (`node:test` + `node:vm`, in the style of `tests/test_browser_resilience.js:95-100`)
- Modify: `package.json`. Set the `"test"` script to `node --test tests/test_browser_resilience.js tests/test_add_flow.js`.

**Interfaces:** each takes `storage`, which may be `null` or may throw; none of them throws.
- `draftKey(userId) -> string` returns `"castle:scout-drafts:" + userId`.
- `loadDrafts(storage, userId, now = Date.now()) -> object` returns a map `{[id]: draft}`. It drops drafts whose `savedAt` is older than `86400000` ms and writes back if it pruned. On any error it returns `{}`.
- `saveDraft(storage, userId, id, draft, now = Date.now()) -> void` stores `{...draft, savedAt: now}` under `id`.
- `removeDraft(storage, userId, id) -> void`.
- `otherDrafts(drafts, currentId) -> Array<{id, ...draft}>` returns the other drafts, newest `savedAt` first.
- `nextMatchValue(values, after) -> string | null` takes `values` in dropdown order (empty strings ignored) and returns the value after `after`. It returns `null` when `after` is last or missing.
- `newDraftId() -> string` uses `crypto.randomUUID()` when it exists, otherwise `Date.now().toString(36) + "-" + Math.random().toString(36).slice(2)`.
- The draft shape (Task 7 fills it): `{fields: {[name]: string|boolean}, event_key, match, team, savedAt}`.

- [ ] **Step 1: Write the failing tests** in `tests/test_add_flow.js`. Load the file with `vm.runInNewContext(src, scope)`, where `scope = {Date, Math, JSON}`. Use a `Map`-backed fake storage with `getItem`, `setItem` and `removeItem`.
  - `save, load and remove round-trip per user`: user A's draft is not returned for user B.
  - `drafts older than 24 hours are pruned`: save at `now`, load at `now + 86400001`, and expect `{}` with the storage entry rewritten.
  - `clearing by an old saved id leaves the current draft`: save `old` and `cur`, call `removeDraft(..., "gone")`, and both remain.
  - `starting a new entry keeps the offered draft`: save `a` at t1 and `b` at t2. `otherDrafts(load, "b")` returns `[a]`, and `otherDrafts(load, "c")` returns `[b, a]`.
  - `storage that throws is ignored`: every method of the storage throws, `loadDrafts` returns `{}`, and `saveDraft` and `removeDraft` don't throw. With `storage = null`, the same holds.
  - `next match follows dropdown order`: `nextMatchValue(["", "Qual 1", "Qual 2", "Semifinal 1-1", "Final 1"], "Qual 2")` gives `"Semifinal 1-1"`. `"Final 1"` gives `null`, and `"Qual 99"` gives `null`.
- [ ] **Step 2: Run the tests.** Run `npm test`. Expected: the `test_add_flow.js` tests FAIL (ENOENT for `add-flow.js`).
- [ ] **Step 3: Implement `add-flow.js`.**
- [ ] **Step 4: Run the tests.** Run `npm test`. Expected: all PASS, including the existing resilience tests.
- [ ] **Step 5: Commit:** `git commit -m "Add draft storage and next-match helpers for the add form"`.

---

### Task 7: Wire drafts, station and preselection into the add form

**Files:**
- Modify: `app/templates/scouting/add.html`.
  - On the form (line 59), add `data-user-id="{{ current_user.get_id() }}"`.
  - Add hidden inputs `_draft_id` and `_station` beside `_event_key` (line 62).
  - Above the form, add `<div id="draftBanner" class="space-y-2"></div>`.
  - Load `add-flow.js?v=1` before `add.js`, and bump `add.js` to `v='12'` (line 451).
- Modify: `app/static/js/scout/add.js`.
- Modify: `app/static/js/service-worker.js`.
  - `CACHE_NAME` `'castle-app-v14'` → `'castle-app-v15'`.
  - `CACHE_VERSION` `'15'` → `'16'`.
  - Add `'/static/js/scout/add-flow.js'` to `STATIC_ASSETS` next to `add.js`.

**Interfaces:**
- Consumes: the Task 6 functions, and the Task 3 URL params (`event`, `after`, `match`, `station`, `saved`).
- Produces: the posted `_station` (e.g. `red2`, from the selected team option's alliance plus its 1-based position among that alliance's options) and `_draft_id`.

These are the decisions the implementer can't make alone:
- **Storage handle.** Get one handle with `try { localStorage } catch { null }`.
- **Load order:**
  1. If `saved` is in the URL, `removeDraft(saved)`.
  2. Make a fresh id with `newDraftId()` and put it in `_draft_id`.
  3. Render a banner item for each `otherDrafts(loadDrafts(...), currentId)`. Build the text with `textContent` only, in the form `Unsaved entry: Team 254, Qual 12 (saved 3 min ago)`, with Restore and Discard buttons.
  4. Run URL preselection.
- **Await match loading.** Extract the `eventSelect` `change` listener body (`add.js:303`) into `async function loadMatchesForSelectedEvent()`. Keep the listener calling it. Preselect and restore `await` it.
- **Preselection:**
  - Find the event option whose `dataset.key === event`, set the select value, then `await loadMatchesForSelectedEvent()`. The searchable input syncs on a dispatched `change`, so dispatch one, and guard against a double load.
  - Pick the label: `match` if present, else `nextMatchValue(matchSelect option values, after)`. Set it and dispatch `change`.
  - Pick the team option at `station`. Set it and dispatch `change`.
  - Stop quietly at the first step that doesn't resolve.
- **Dirty tracking and saving:**
  - On the form, listen to `input`, `change`, `click` and `pointerup`. If `e.isTrusted`, set `dirty = true` and debounce a save by 500 ms.
  - On `pagehide`, and on `visibilitychange` to `hidden`, save immediately if `dirty`.
  - A save calls `updatePathData()`, then `saveDraft(currentId, {fields, event_key, match, team})`.
  - `fields`: every named form element except `csrf_token`, `_draft_id`, `_event_key` and `_station`. Checkboxes are stored as booleans and radios as the checked value.
- **Restore:**
  - `removeDraft(currentId)`. Set `currentId` to the restored id and update `_draft_id`. Remove that draft's banner item.
  - Select the event, await the matches, then select the match and the team as in preselection.
  - Fill the remaining fields, dispatching `change` on each so dependent UI updates.
  - Set `CanvasField.drawingHistory = JSON.parse(fields.auto_path || "[]")`, then `CanvasField.redrawCanvas()` and `updatePathData()`. Capture `CanvasField` through the `onCanvasReady` option of `initScoutFormCanvas`, as `edit.js:6` does.
  - A restore wins over URL preselection.
- **Discard** calls `removeDraft(id)` and removes the banner item.
- **Submit.** Before `form.submit()` (`add.js:82`), set `_station`. `_draft_id` is already set.

- [ ] **Step 1: Implement the template, `add.js` and service-worker changes** above.
- [ ] **Step 2: Run the tests.** Run `npm test` and `.venv/Scripts/python.exe -m unittest tests.test_match_day tests.test_match13_fuel tests.test_security -v`. Expected: PASS.
- [ ] **Step 3: Commit:** `git commit -m "Recover drafts and preselect the next match on the add form"`.

---

### Task 8: Browser check and full regression

**Files:**
- Create (scratchpad only, not committed): a preview script.
  - It calls `tests.app_harness.start_app()`.
  - It adds a `before_request` that logs in `USER_ID` with `flask_login.login_user`.
  - It points `common.scouting_manager.db` at a `MagicMock` whose `team_data.insert_one` returns an id and whose `aggregate` returns `[]`.
  - It runs `app.run(port=5055)`.
  - With no `TBA_AUTH_KEY`, the add page offers the `Testing Regional` events with generated matches.

- [ ] **Step 1: Drive `http://localhost:5055/scouting/add`** in a real browser (Playwright, as configured in `.playwright/`) and verify each item:
  1. Choose `Testing Regional #1`, `Qual 1` and the second red team, then save. You land on the add form with `Qual 2` and the second red team preselected, and no draft banner.
  2. Type a note, then reload. The banner offers `Qual …`. Restore fills the note, event, match and team. Discard removes it.
  3. Tap a counter `+` only, then reload. The banner is offered (a counter tap marks the draft dirty).
  4. Type a note, then fire `visibilitychange` (hidden). The draft is in `localStorage`.
  5. Open `/scouting/add?saved=nonexistent` with a draft present. The draft is still offered.
  6. With the DevTools `localStorage` access throwing (override `Storage.prototype.getItem` to throw), the form still saves, and there are no console errors.
- [ ] **Step 2: Full regression.** Run `.venv/Scripts/python.exe -m unittest tests.test_match_day tests.test_security tests.test_bug_fixes tests.test_match13_fuel tests.test_scouting_pagination tests.test_scouting_performance tests.test_scout_routes_common tests.test_route_logging tests.test_safe_url tests.test_pit_form -v` and `npm test`. Expected: everything OK.
- [ ] **Step 3: Fix anything found** with a failing test first, in the owning task's test file, then commit.
