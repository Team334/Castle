# Offline scouting and venue mode (Maneuver batch 4): design

Branch: `feature/offline-qr`, from `main` at 925c3c4 (includes batch 1, #46–#48). Agreed in conversation 2026-11-11.

## Why

The team scouts at venues where **nobody has a signal**: not the scouts' phones, and not the lead's phone. Today Castle needs the network for everything.

- **The scout form won't open offline.** Navigations go to `offline.html` (`app/static/js/service-worker.js:229-238`, `:142-147`).
- **The match schedule comes from the network.** The event, match and team lists come from `/api/tba/*` (`app/static/js/scout/add.js:1-27`).
- **Save is a native POST.** Offline, it fails. Batch 1's draft keeps a copy, but nothing uploads it later.

The scouting lead builds the pick list right before alliance selection, at the venue, so needs the last morning's matches within minutes. The lead uses almost every page: the leaderboard, the match list, auto paths and compare.

## Goals

1. **Offline scouting.** A scout's phone that was set up online beforehand can open the scout form and save entries with no signal. Saved entries wait on the phone and upload automatically when the phone next gets a connection.
2. **QR transfer.** A scout can hand their waiting entries to the lead's laptop by showing an animated QR code. The code uses fountain codes, so frames can be caught in any order and missed ones don't matter. The lead's laptop scans it with its webcam.
3. **Venue laptop.** The lead's laptop runs its own copy of Castle (the same code, a local database).
   - The night before, it loads all of the team's data from castlescouting.com through a file.
   - At the venue, it adds scanned entries.
   - The lead uses the normal pages with no internet.
   - Afterwards, its new entries go back to castlescouting.com, again through a file.
4. **No double counting.** Every path that moves entries is safe to repeat: phone sync, QR, and both file imports. Uploading the same entry twice never creates two records.

## Non-goals

- Offline **pit** scouting, and moving pit photos. Pit *records* (text) are carried to the laptop so the pit pages show them.
- Syncing **edits or deletions** between the laptop and the main server. Only new entries move. An entry edited on the laptop keeps its main-server version when pushed back.
- Wi-Fi, Bluetooth or WebRTC transfer. FIRST event rules are believed to ban team-run Wi-Fi networks at venues; this is unconfirmed.
- Making TBA or Statbotics data available offline: team nicknames, EPA, rankings, mock alliance selection, live match status.
- Rebuilding any stats page in JavaScript (that is approach A, rejected).
- Packaging the laptop setup as a one-click installer. A written guide is enough for now.
- The redesign. New UI uses the current styles.

## Anti-goals (a failure even if it works)

- **Lost entries.** An entry saved on a phone is lost: wiped before the server or the lead confirmed it, or dropped on a retry.
- **Double counting.** The same entry is counted twice after phone sync plus a laptop push.
- **Spoofing.** Any team member can create entries claiming to be from another team's scout, or set fields the add form can't. The old `qrf` branch's import accepted raw documents and had this problem.
- **Wrong user on a shared phone.** Scout B on a shared phone saves offline entries under scout A's account because the cached form still belongs to A.
- **Stats that disagree.** The laptop's pages show different numbers from castlescouting.com for the same records.
- **A broken page.** A page the lead needs crashes on the laptop because TBA can't be reached. `/api/compare` currently does `TBAInterface().get_team(...).get(...)` with no `None` guard (`app/scout/routes/lighthouse.py:70-73`).

## Approaches considered

- **A. Rebuild the stats pages on the lead's phone** (how Maneuver works). The leaderboard, list, compare and auto paths would be rewritten in JS over data stored on the phone. Rejected: four or more pages built twice, and the numbers drift whenever a formula changes on one side.
- **B. The lead's laptop runs its own Castle. ← chosen.** Every page works unchanged, with one copy of the stats logic. Costs: a one-time laptop setup (Python and MongoDB), a file step the night before, and scouts walking to the laptop to be scanned.
- **C. Cache the pages the night before and list new entries separately.** Rejected: the leaderboard would leave out the last morning's matches, which are exactly what picking needs.

## Design

### 1. Entry file format, export and import (server)

**Format.** One JSON format serves everything that moves entries: phone sync, QR and files.

```
{"format": "castle-entries", "version": 1, "exported_at": "...", "team": 334,
 "users":   [{"_id": "...", "username": "...", "teamNumber": 334}],                         // public fields only
 "matches": [{...add-form fields..., "_id"?, "client_id"?, "scouter_id", "created_at", "event_key"?, "match_key"?, "excluded"?}],
 "pits":    [{...pit fields..., "_id", "scouter_id"}]}
```

**Export**, `GET /scouting/export`.
- Login required.
- Downloads `castle-<team>-<YYYY-MM-DD>.json`.
- It contains all **current-season** match records the user can see (`access_match`; *my call:* `created_at` in the current calendar year), the team's pit records, and the public fields of **every member of the user's team**, not only those with records. That way a rookie's first entries are still accepted on the laptop.
- **Never** password hashes or emails. Reuse `SCOUTER_LOOKUP`'s public projection.
- `?scope=venue` exports only records created on this laptop (`origin: "venue"`; see section 4).

**Import**, `POST /scouting/import`.
- Login and a team are required.
- It accepts a JSON body (phone sync, QR) or an uploaded `.json` file (laptop and main-server file import). Use the usual CSRF: the header for JSON, the form field for files.
- Limits: JSON bodies take at most 500 match entries and about 5 MB. File uploads take about 50 MB, with no entry cap. Set `MAX_CONTENT_LENGTH` accordingly.
- Rate-limited like the other write routes.
- It returns per-entry results, `{"results": [{"key": "<client_id or _id>", "status": "saved|already_have|duplicate|rejected", "reason": "..."}]}`, plus counts.

**Import rules for each match entry:**
- **Fields.** Built only through the same field builder as the add form (`add_scouting_data` / `_record_fields`). Unknown fields are ignored, and the trust-boundary validation is the same as add's.
- **Identity.** `event_key` and `match_key` are computed the same way as on add (batch 1). Imported values are not trusted.
- **Already have.** If the entry has an `_id` that already exists, or a `client_id` that already exists, it is `already_have`. Nothing is written.
  - This is what makes every path safe to repeat.
  - Store `client_id` on records created through the add form too (the posted `_draft_id`), so a later sync of the same entry matches.
  - The lookup is unindexed; mark it `shortcut:` (team_data is small).
- **Duplicate.** Batch 1's same-team check applies, so it returns `duplicate`. The excluded rule is unchanged.
- **Who scouted it.** `scouter_id` must be the uploader or a user on the uploader's team. Otherwise the entry is `rejected`.
  - Credit stays with `scouter_id`.
  - When the uploader isn't the scouter, store `uploaded_by: <uploader id>`.
  - *(My call: any member of the scout's team may upload for them. Teammates can already edit each other's entries.)*
- **Keeping `_id`.** An entry carrying an `_id` (from an export file) is inserted with that same `_id`, so a later push back to the main server is recognised.
- **`created_at`.** Kept from the entry when it's a valid ISO time, otherwise set to now.

**Pit entries.** Same `_id` rule (`already_have` if it exists). Fields are built through the existing pit field builder. Never images.

**Venue mode** (`VENUE_MODE=1` in the laptop's `.env`) changes how import behaves.

- **Stub users.** Import creates stub users from the file's `users`, and from a QR payload's `scout` object (`{_id, username, teamNumber}`, which Show QR includes). Stubs are created only when `teamNumber` equals the lead's team. They are public fields only, so stubs can't log in. They exist so the laptop's pages show scout names, the team check above passes, and `UNWIND_SCOUTER` doesn't hide their records. On the main server, unknown users are never created.
- **Exact copies.** Entries that carry an existing-format `_id` from an export file are stored as **exact copies**: the known record fields, including `excluded`, `event_key`, `match_key`, `client_id`, `scouter_id`, `created_at` and fuel values. They aren't rebuilt through the add-form builder, so the laptop's stats match the main server's. *(Builder-check call.)* This applies in venue mode only. On the main server, every entry is rebuilt through the builder.
- **Origin.** Records created on the laptop (scanned or imported without an existing `_id`) get `origin: "venue"`.

### 2. Offline scouting on the phone

**Caching the form.**
- The service worker caches the `/scouting/add` HTML after each successful online load.
- It serves that copy **only** when a navigation to `/scouting/add` fails. Every other navigation keeps today's behaviour, falling back to `offline.html`.
- **Logging out** (and logging in as someone else) must delete the cached form, so a shared phone never serves another user's page. The cached page has the user id and CSRF token baked in.
- Update the resilience test that currently asserts no navigation is ever served from cache. The new rule: only `/scouting/add`, and only after a network failure.

**Caching the schedule.** `add.js` stores the events list and every event's matches it loads in `localStorage`, per user (e.g. `castle:schedule:<user>`), and falls back to that copy when `/api/tba/*` fails.
- Show a small "Ready for offline: <event> (<n> matches)" note once an event's matches are stored.
- Setting a phone up = being online once, opening the add form, and picking the event.

**Typing a match in** *(user's decision)*. The match or the team may not be in the phone's saved schedule: the schedule was published after setup, playoff matches were added at the venue, or the schedule changed. For that, the form offers **"Match not listed? Type it in"**, shown automatically when the chosen event has no saved matches.

- **Match:** a level dropdown (Qual / Semifinal / Final) plus number fields. Semifinals take set and match. This builds the same label the dropdown would (`Qual 12`, `Semifinal 2-1`, `Final 1`), so the server's `tba_match_key` gives the same `match_key` and the duplicate check works.
- **Team number** and **red/blue station** (`red1`..`blue3`), which set `alliance` and `_station`.
- **Event:** still chosen from the saved events list.
- **Next match:** after a typed save, the next-match step adds 1 to the qual number, or the semifinal match number, and keeps the station.
- **Validation:** the team number must be a positive integer, and the label must be one of the three shapes. The server already rejects bad team numbers. A label it can't turn into a key is saved without keys, as in batch 1.

**Saving.**
- Submit sends the form with `fetch` (same URL, same body, so CSRF, flash messages and batch 1's redirect all still work). On a response, it goes to the redirected URL.
- On a **network failure**, or when `navigator.onLine` is false, the entry goes into the phone's **outbox** (`localStorage` `castle:outbox:<user>`). The outbox entry holds the form fields, `client_id` (the draft id), `scouter_id` and `created_at`.
- After queuing, the draft is cleared and the form moves to the next match the same way batch 1's redirect does (using the cached schedule). The scout sees "Saved on this phone · N waiting to upload".
- If storage fails, the draft is kept and an error is shown. Never lose the entry.

**Syncing.**
- When the page loads online, on the `online` event, and every 60 s while the outbox isn't empty, POST the outbox to `/scouting/import` as JSON with `X-CSRFToken` from the page's meta tag.
- Remove entries whose result is `saved`, `already_have` or `duplicate`.
- Keep `rejected` entries and show their reason.
- On 401 or 400 (session expired), keep everything and show "Log in to upload".

**Outbox UI.** The add page and the list page show the waiting count with **Upload now** and **Show QR**.

**Fuel estimates.** *(User: scouts don't count fuel; the AI model, Match13, does it online.)* Import on the main server must sign up entries with zero scored fuel for Match13 estimates, exactly as the add route does (`zero_scored_fuel` → `service.enroll`). That covers both phone sync and file imports.

### 3. QR transfer

**Library.** Reuse the fountain-code encoder and decoder from the `qrf` branch's `app/static/js/qrf.js` (Luby Transform, robust soliton). Do **not** reuse that branch's routes or list-page code. Two fixes are required *(builder-check findings)*:
- **Payload id.** Each frame carries a payload id (e.g. a short hash of the payload). The decoder resets when the id changes, so two scouts' codes never mix.
- **Peeling.** New frames are reduced using chunks already decoded, so decoding finishes in a reasonable number of frames.
- Give it node tests: encode then decode with frames shuffled and about 30% dropped, plus decoding the same payload from two encoders.
- QR drawing (qrcodejs 1.0.0) and scanning (jsQR 1.4.0), both MIT, are **vendored** under `app/static/vendor/` so they work offline. Use `BarcodeDetector` when the browser has it.

**Show QR (scout's phone).**
- It's a panel on the add page, so it works offline with no extra cached page.
- It shows the outbox entries, all of them by default, untickable.
- It encodes `{"format": "castle-entries", "version": 1, "scout": {"_id", "username", "teamNumber"}, "matches": [...]}` (the scout's public fields, from the cached page): gzip (`CompressionStream`), then base64, then fountain frames drawn at about 5–8 frames per second until closed.
- **Sending by QR does not remove entries from the outbox.** The phone still syncs them itself later, and import treats them as `already_have`. The scout can tap "Lead has these" to mark them as handed over, which is shown but changes nothing.
- Guidance from Maneuver: about 10–15 entries per session. The builder picks the frame size.

**Scan (lead's laptop).**
- A new page, `/scouting/scan`, with the webcam view and a progress bar ("x% · N frames").
- When decoding finishes, it POSTs to `/scouting/import` and shows each entry's result (saved / already have / duplicate / rejected + reason).
- Then "Scan next scout".

### 4. Venue laptop

**Setup guide.** A step-by-step guide for a student, `docs/venue-mode.md`, covers:
- installing Python and MongoDB Community;
- cloning the repo and `pip install`;
- `.env` with `MONGO_URI=mongodb://localhost:27017/castle`, `SECRET_KEY`, `VENUE_MODE=1` and no TBA key;
- running the app.

**Login on the laptop.** A CLI command (e.g. `flask venue-user`) creates the lead's login on the laptop: username, password and team number. No password hash ever leaves castlescouting.com.

**Night before.** Start each event from a fresh laptop database. *(Builder-check call.)* This stops records deleted on castlescouting.com from coming back, and stops the laptop drifting from the main server.

1. Run the reset command (e.g. `flask venue-reset`).
   - It deletes the laptop's `team_data` and `pit_scouting`, but **refuses** while records with `origin: "venue"` exist that were never pushed.
   - `--force` overrides it.
   - Track "pushed" with a timestamp set when **Download new entries** runs.
2. On castlescouting.com: list page → **Download all (JSON)**.
3. On the laptop's Castle: list page → **Import file**.

**At the venue.** `/scouting/scan`, and the normal pages.

**After the event.**
1. On the laptop: **Download new entries** (`?scope=venue`). Only entries created on the laptop are exported, so main-server deletions are never undone.
2. On castlescouting.com: **Import file**. Already-present entries are skipped. Phones also sync on their own.

**Fuel not counted yet (laptop).** Match13 needs the internet, so fuel on entries scouted at the venue isn't known on the laptop. Entries imported from castlescouting.com already carry their estimated fuel.

- In venue mode, an entry created on the laptop with zero scored fuel is marked `fuel_pending: true`.
- The fuel averages and totals in the leaderboard, compare and match view **leave out** `fuel_pending` entries. Note that `$avg` over `$ifNull: [..., 0]` would otherwise count them as 0.
- Those entries still count for everything else: climb, defense, matches played.
- The list shows a "Fuel pending" tag on them.
- When pushed to the main server, they go through the normal estimate sign-up and the flag isn't carried over.

**Working without CDNs.** Every third-party script that the pages the lead and scouts use load from a CDN is **vendored** under `app/static/vendor/`, pinned to an exact version and added to the service worker's static assets where phones need it:
- `localforage`: used by `Canvas.js` on add, edit and list, so the offline form crashes without it.
- `chart.js`: the compare page.
- `sortablejs`: auto paths. It's currently loaded as `@latest`.
- `@popperjs/core@2`: `base.html`.

Also add `coloris.js`, `coloris.css` and `scouting.css` to `STATIC_ASSETS`, since the add form needs them.

**Working without TBA.** Pages the lead uses must render with no network.
- Guard `get_team(...)` returning `None` in `/api/compare` (`lighthouse.py:70`).
- Make sure TBA and Statbotics calls fail fast rather than hanging. Check the timeouts in `TBAInterface._get_json` and `api_cache`.
- Name-based team search on compare needs TBA; number search must still work.

**Only in venue mode:** the stub users from section 1, and a banner "Venue mode: local copy, not castlescouting.com" so nobody confuses the two.

## Build order

Each phase is useful on its own:

1. Format, export and import, with the `client_id` and attribution rules.
2. Phone offline: the cached form, cached schedule, outbox and sync.
3. QR: the library, Show QR and Scan.
4. Venue laptop: the CLI user, venue-mode stubs, TBA-offline fixes and the guide.

## Testing

- **Python.** `unittest` with the mocked-Mongo harness. **Never connect to the user's MongoDB.**
- **Import rules:** saved / already_have by `_id` and by `client_id` / duplicate / rejected for a scout from another team; `uploaded_by`; unknown fields ignored; keys recomputed.
- **Export:** never includes hashes or emails.
- **Venue mode:** stubs are created only with `VENUE_MODE`.
- **Limits:** request size and entry count.
- **Compare:** `/api/compare` with TBA returning `None`.
- **Node** (`node --test`, vm-loaded files as in `tests/test_add_flow.js`):
  - outbox add/remove and result handling;
  - schedule cache fallback;
  - the service worker's offline add-page rule and logout clearing;
  - qrf round trip with dropped and shuffled frames.
- **Browser** (playwright-cli against a mocked-Mongo preview, as in batch 1):
  - phone offline with the context set offline: open the form, save 2 entries, see "2 waiting", go online, see them sync;
  - QR send to scan between two pages. A fake camera may be impractical; at minimum, decode frames captured from the Show QR canvas.
- **Manual:** venue setup by following `docs/venue-mode.md` on a clean laptop.

## Left to the builder

- Helper and module names.
- Where the outbox and sync code lives: a new `app/static/js/scout/outbox.js` is the natural home.
- QR frame size and rate.
- The exact panel and page layout, within the current styles.
- Whether file import is a page or a dialog.
- The CLI command's name.
- How the service worker learns about logout (a message from the page, or the logout response).
