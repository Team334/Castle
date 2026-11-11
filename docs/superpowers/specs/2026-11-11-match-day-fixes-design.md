# Match-day fixes (Maneuver batch 1): design

Branch: `feature/maneuver-features` (from `redesign/ui`). Approved in conversation 2026-11-11.

## Why

The team compared Castle with Maneuver (frc-maneuver.com) and wants the features Castle lacks. 36 gaps were found. They split into four batches, built in this order:

1. **Match-day fixes (this doc).**
2. Features that carry over to next season: pit, team stats, all-teams table, TBA check, picklists, predictions, scout dashboard.
3. Features tied to this season's field (2026 fuel, field map, climb detail).
4. Offline capture and transfer: save offline, then backup/import, then QR, then Wi-Fi.

Batch 1 comes first for two reasons. First, record identity is the foundation for 8 later features: match validation, fuel scaling, export/import, QR, Wi-Fi, offline, custom events and predictions. Second, these four fixes stop bad or lost data during matches.

Problems this batch fixes, all in today's code:

- **Duplicates count twice.** If two scouts on one team enter the same robot in the same match, both records count in every average. `add_scouting_data` (`app/scout/scouting_utils.py:148`) inserts with no check. The client check in `app/static/js/scout/add.js:67-80` is commented out.
- **Records can't be joined to TBA.** `event_code` stores the TBA event's display name and `match_number` stores a label such as `Qual 12`. The posted `_event_key` is dropped, and the display name repeats every year.
- **A scout can lose a whole match of counts.** A locked phone, a Back press, a refresh or a failed submit wipes the form. Nothing saves form fields.
- **Scouts re-pick everything after each save.** Save redirects to the list (`app/scout/routes/records.py:72`), so the scout has to choose the event, match and robot again. That is slow, and it causes records filed under the wrong match.
- **Bad matches can't be dropped from stats without deleting them.** Only hard delete exists, and it loses the notes too.

## Goals

- **Store TBA codes.** Every new match record stores `event_key` (e.g. `2026nyny`) and `match_key` (e.g. `2026nyny_qm12`).
- **Block duplicates.** Saving a record is refused when that robot in that match is already recorded by the same team. The error names the scout who recorded it.
- **Recover lost forms.** The add form's contents survive a crash, refresh, Back or failed submit, and are offered back on the next visit. They clear only after the server confirms the save.
- **Jump to the next match.** After a save, the add form reopens with the same event, the next match and the same alliance station already selected.
- **Exclude bad matches.** A record can be marked "Exclude from stats". Excluded records drop out of every average but stay listed and editable.

## Non-goals

- No backfill or migration of existing records, and no writes to the user's MongoDB outside normal app use. Old records simply have no keys. Old duplicates can be excluded by hand.
- No new database index or unique constraint.
- No bulk delete by event, and no automatic exclusion of `Testing Regional` records. That belongs to demo data in a later batch.
- No offline saving. A draft survives an offline submit, but the record isn't queued.
- No visual redesign. Changes use the current styles. The redesign restyles them later.

## Anti-goals (a failure even if it works)

- A draft wiped before the server has confirmed the save.
- A newer in-progress draft cleared by reloading an old "saved" URL.
- A second scout's entry silently replacing the first.
- Records from two different teams blocking each other. Castle is multi-team, and each team sees only its own records (`access_match`).
- Excluded records still counted in a leaderboard, compare, match view or auto-path average.
- A 2027 record matched as a duplicate of a 2026 record.

## Approaches considered

- **Duplicate check.** Chosen: the server checks on save. Rejected: a browser-only pre-check, which is bypassable and racy. Also rejected: a unique Mongo index, which can't express "same scouting team" because the scout's team isn't on the record, and would need a live-DB migration.
- **Identity key.** Chosen: TBA keys. Rejected: event display name plus label, because names repeat yearly and would collide across seasons.
- **Draft storage.** Chosen: browser `localStorage`. Rejected: server drafts, which don't work offline and add a collection.
- **Next match.** Chosen: the redirect URL carries the event, last match and station. Rejected: device storage, because the redirect already has the data and the server can validate it.
- **Bad matches.** Chosen: an `excluded` flag on the record. Rejected: deleting, which loses notes, and a separate collection, which is needless.
- **When a duplicate is found.** The user chose **block**. Rejected: replace (Maneuver's behaviour), which silently loses the first entry. Also rejected: keep both and average, which complicates every stat.

## Design

### 1. Record identity

- **Event key.** On add, take the posted `_event_key`. It is already filled by `add.js:81` from the selected event option's `data-key`. Accept it only if it fully matches `^\d{4}[a-z0-9]+$`. TBA keys and the built-in testing events (`{year}test1..3`) both match. Store it as `event_key`.
- **Match key.** Derive it on the server from the event key plus the posted `match_number` label. `app/scout/match13_fuel.py:38` `match_key()` already parses the labels the form produces (`Qual N` → `qmN`, `Semifinal S-M` → `sfSmM`, `Final N` → `f1mN`), but it is guarded to 2026 events by `EVENT_PATTERN`.
  - Lift the label parsing into a year-agnostic helper, so record identity works next season. A natural home is `app/scout/TBA.py`, since it is about TBA key formats.
  - Keep match13's 2026-only guard by having its `match_key` call the new helper after its own check.
  - Store the result as `match_key`.
- **Missing keys.** If either key is missing or invalid, save the record without the keys and skip the duplicate check. Never reject a record because a key is missing: this branch can't fix the client, and losing a match is worse than a possible duplicate.
- **Display fields unchanged.** `event_code` (display name) and `match_number` (label) are still stored as today. Every existing page reads them.
- **Edit.** The edit page lets users free-type event, match and team.
  - If an edit changes `event_code`, `$unset` both `event_key` and `match_key`.
  - If it changes only `match_number`, `$unset` `match_key`. The record is then unlinked from TBA, never mislinked.
  - Changing only `team_number` keeps both keys.
  - The existing edit duplicate check stays as is.

### 2. Duplicate block (add only)

- **The check.** Before inserting, if `match_key` is set, look for records with the same `match_key` and `team_number` that are not excluded (`excluded != true`). Join each to its scout with the existing `SCOUTER_LOOKUP`, and keep those by the same scouting team:
- **Excluded records don't block.** *(Builder-check call.)* Excluding a record means it doesn't count, so re-scouting that robot in that match must be allowed. Editing over the excluded record would destroy the notes that exclusion exists to keep.
  - If the current user has a `teamNumber`: records whose scout's `teamNumber` equals it.
  - If the current user has no team: records whose `scouter_id` is the current user.
- **When one is found.** Refuse the save. The flash error reads like: `Team 254 in Qual 12 was already scouted by <username>. Edit that entry from the scouting list instead.` Then redirect back to the add form (see section 4), so the draft is offered and the scout can discard it.
- **Return value.** `add_scouting_data` keeps its `(success, message)` return. A duplicate is a `False` with that message.
- **Known race.** Two saves in the same second can both pass. Accepted for this batch; mark it in code with a `shortcut:` comment.

### 3. Draft recovery (add form, browser only)

- **Draft id.** On add-form load, generate a fresh draft id (e.g. `crypto.randomUUID()`, falling back to a timestamp plus random string). Put it in a new hidden field `_draft_id`.
- **Storage shape.** *(Builder-check call.)* Use one `localStorage` key per logged-in user, e.g. `castle:scout-drafts:<user id>`, holding a map of draft id to draft. A per-user key means a scout on a shared tablet is never offered another user's draft. A map means starting a new entry never overwrites an older unsaved one. Put the user id in the page, e.g. a `data-` attribute on the form.
- **Saving.** Save the *current* draft id's entry on `input` and `change` (debounced, about 500 ms), and on `pagehide`. Only events with `event.isTrusted` count, so the URL preselection (section 4) and restore filling fields by code never create or overwrite a draft. Save every named form field, the drawn auto path (the hidden path field after `updatePathData()`), the event key, the match label, the selected team and `savedAt`.
- **Pruning.** On load, drop drafts older than 24 hours.
- **Offering drafts back.** On load, show a small banner for each other draft, newest first: `Unsaved entry: Team 254, Qual 12 (saved 3 min ago)` with **Restore** and **Discard**. There is usually one, rarely more. The banner stays until it is answered, and the scout can start a new entry meanwhile without endangering it.
- **Restore.** Remove the current (fresh) draft. Make the restored draft's id the current id and set `_draft_id` to it. Then re-select the event, wait for its matches to load, select the match, select the team, then fill the other fields and redraw the path.
  - `Canvas` has `loadFromJSON` (`app/static/js/Canvas.js:991`).
  - `initScoutFormCanvas` (`app/static/js/scout/form-canvas.js:428`) returns only `updatePathData`, so expose what restore needs.
- **Clearing.** A draft is removed only when the page loads with `?saved=<id>` and a stored draft has that id. That one entry is removed, and nothing else. Any other `saved` value, such as an old URL reloaded later, leaves every draft alone. **Discard** removes only its own draft.
- **Storage errors.** Wrap every storage access in `try/catch`. If storage is unavailable, the form works exactly as today.

### 4. Next-match flow

- **Station.** On submit, `add.js` also posts a hidden `_station`, the selected robot's alliance plus position (`red1`..`red3`, `blue1`..`blue3`). Position is its order in the match's `red` or `blue` team list (`add.js` team select builder, about line 409).
- **Redirect after a save.** Redirect to `url_for("scouting.add", event=<event_key>, after=<match label>, station=<station>, saved=<draft_id>)`, instead of the list.
  - Pass each value only if it validates: event key per the regex above, station per `^(red|blue)[1-3]$`, draft id per a short `[A-Za-z0-9-]{1,64}` pattern.
  - `after` is the label, length-capped (e.g. 32 chars). It is only compared in JS, never rendered as HTML.
- **Redirect after a failed save** (duplicate or error). Redirect to the add form with `event`, `after` set to the *same* label and the same `station`, but no `saved`. The scout lands on the same match and gets the draft offered.
  - The other failure, invalid auto-path JSON at `records.py:46-50`, also redirects to the add form rather than the list.
  - **Builder's call:** for the failure redirect, a `match=<label>` param that selects the same match, instead of the next one, is cleaner. Either works as long as the scout lands on the failed match.
- **Preselection on add-form load:**
  - Select the event whose option `data-key` equals `event`, and load its matches.
  - Select the match *after* `after` in the dropdown's order (quals by number, then semis by set and match, then finals).
  - Then select the team at `station` in that match.
  - If any step can't be resolved (unknown event, last match, missing station), stop there and leave the rest for the scout.
  - Preselection must fire the same `change` handlers a manual pick fires, so the alliance field and the team list fill in.
- **Order with draft restore.** If a draft is offered and the scout restores it, the draft's selections win over the URL's.
- **Edit and delete** still redirect to the list as today.

### 5. Exclude from stats

- **The checkbox.** The edit page gets a checkbox `excluded`, labeled "Exclude from stats (keeps the record and its notes)". `update_team_data` sets `excluded: bool` from it, in `updated_data`, not in `_record_fields`, so add never sets it. Same permission as editing: the original scout or anyone on that scout's team (`records.py:140-143`).
- **Model.** `TeamData` gains `excluded = data.get('excluded', False)` for the template.
- **Filtering.** Add one shared stage that keeps counted records only, `{"$match": {"excluded": {"$ne": True}}}`. Apply it in every function that feeds an average or a stat:
  - `get_match_alliances`
  - `get_compare_stats`
  - `get_auto_paths`
  - `get_team_leaderboard`

  If any other pipeline averages `team_data`, apply it there too. Grep `team_data.aggregate` in `scouting_utils.py`.
- **Not filtered:**
  - `get_all_scouting_data` (the list). Excluded records show there with an "Excluded" tag.
  - `get_team_records` (search results). These show with the tag too, if they render records.
  - `get_leaderboard_events` (the event filter list).
  - `get_scouter_leaderboard`. The scout did the work.
  - `get_visible_fuel` and the match13 fuel service.
- **Projection.** `get_all_scouting_data` projects `excluded`, so the list can show the tag.

### 6. Cache and assets

- Bump the `?v=` on the changed scripts in `add.html` (and `edit.html` if its script changes).
- Bump the service worker `CACHE_NAME` and `CACHE_VERSION` per the repo's existing convention (`app/static/js/service-worker.js:1,6`). The redesign branch also plans a bump, so expect a trivial merge conflict there.
- If any Tailwind class is new to the codebase, rebuild CSS with `npm run build:css`.

## Testing

Use `unittest` with the existing mocked-Mongo harness (`tests/app_harness.py`: `start_app()`, `logged_in_client()`). Run modules by name with `.venv/Scripts/python.exe -m unittest tests.<module>`, since `discover` fails here. **Never connect to or write to the user's MongoDB.** `.env` may point at a real database.

- **Keys.** Label → key for `Qual 12`, `Semifinal 2-1`, `Final 2`, plus a non-2026 year. An invalid or missing `_event_key` saves without keys and with no duplicate check. match13's `match_key` still rejects non-2026 events.
- **Duplicates.**
  - Same team: blocked with the scout's name.
  - Different team: allowed.
  - User with no team: blocked only against their own record.
  - No `match_key`: no check.
  - An excluded record doesn't block.
- **Redirects.**
  - A successful add redirects to the add form with validated `event`, `after`, `station` and `saved`.
  - Invalid params are dropped.
  - A failed add redirects to the add form without `saved`.
- **Edit.** Changing the event unsets both keys. Changing the match unsets `match_key`. Changing only the team keeps both. The `excluded` checkbox round-trips.
- **Exclusion.** Each of the four stat pipelines contains the excluded-filter stage. Prefer a behavioural check with the mock if the harness allows it.
- **JS.**
  - Draft save, restore and clear-by-matching-id.
  - An old saved URL doesn't clear a new draft.
  - Starting a new entry while an older draft is offered keeps both.
  - Fills done by code (preselect, restore) don't save.
  - Another user's drafts are never offered.
  - Next-match selection order.
  - Cover these with `node --test`, in the style of `tests/test_browser_resilience.js`, where the logic can be pulled into pure functions.
  - Otherwise, check in a browser against the mocked harness with fake TBA data.
- **Fixture update.** `RouteTests` in `tests/test_match13_fuel.py` registers only `scouting.home`. Once add redirects to `scouting.add`, that fixture needs updating.
- **Regression.** Run the existing suites: `test_security`, `test_bug_fixes`, `test_match13_fuel`, `test_scouting_pagination`, `test_scouting_performance`, `test_scout_routes_common`, `test_route_logging`, and `npm test`.

## Left to the builder

- Exact helper names and placement, beyond the match13 split above.
- Banner wording and styling, within the current look.
- Debounce timing.
- How to expose canvas restore from `form-canvas.js`.
- Whether the failed-save redirect uses `after` or `match` (section 4).
- Test file layout.
