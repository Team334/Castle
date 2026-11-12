# Offline Phase 2 (Scout Phones Offline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A scout's phone that was set up online beforehand can open the scout form, pick a match (from the saved schedule, or typed in), and save with no signal. Saved entries wait in an outbox and upload themselves through phase 1's `/scouting/import` when a connection returns.

**Architecture:**
- **Service worker.** It caches the `/scouting/add` HTML and serves it only when that navigation fails. It clears that copy when the user logs out.
- **`add.js`.**
  - Saves every schedule it loads, and falls back to the saved copy.
  - Submits with `fetch`. On a network failure it queues the entry and moves to the next match through batch 1's redirect URL, which the cached page then serves.
- **Pure helpers, tested in node:**
  - schedule, typed-label and next-label helpers in `add-flow.js`;
  - outbox storage and sync in a new `outbox.js`.
- `localforage` is vendored, because the add page's canvas needs it offline.

**Tech Stack:** a service worker, `localStorage`, `fetch`, vanilla JS, `node --test` with `vm`, `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-11-offline-venue-mode-design.md`, section 2. From section 4 ("Working without CDNs") it also takes the `localforage` vendoring and the `STATIC_ASSETS` additions, because phones need them now. Chart.js and Sortable stay in phase 4.

## Global Constraints

- **Never connect to the user's MongoDB.** Python tests use the mocked harness. JS tests use `vm` with fake storage, fake fetch and a fake service-worker scope, as in `tests/test_browser_resilience.js:6-27`.
- **Storage keys:**
  - `castle:schedule:<userId>` holds `{events: {name: {key}}, matches: {eventKey: <matches object>}}`.
  - `castle:outbox:<userId>` holds `{<client_id>: entry}`.
- **Outbox entries** use phase 1's import format:
  - fields: `event_code`, `match_number`, `team_number`, `alliance`, `event_key`, `client_id`, `scouter_id`, `created_at` (ISO), plus every other form field;
  - sent as `{"format": "castle-entries", "version": 1, "matches": [...]}`, at most 500 per request;
  - results with status `saved`, `already_have` or `duplicate` are removed, and `rejected` ones stay with their `reason`.
- **Labels:**
  - typed matches are exactly `Qual N`, `Semifinal S-M` or `Final N`, with positive integers;
  - stations are `red1`..`blue3`.
- **Service worker:** all four cache names move to `-v15` and `CACHE_VERSION` to `'17'`. The cached form lives in `PAGE_CACHE_NAME` under the key `/scouting/add`.
- Every storage access is wrapped in try/catch. A failure to queue keeps the draft and shows an error, and never navigates away.
- Use existing CSS component classes. If a Tailwind class isn't used anywhere yet, run `npm run build:css`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push.

## Review Focus

1. **A wrong signal ("lie-fi").** The POST reached the server but the response was lost, so the entry is queued and also saved. A later sync must report `already_have`, not create a second record. Phase 1's `client_id` handles this, and Task 4 `outbox sync drops already_have` pins it.
2. **The session expires before sync.** `/scouting/import` redirects to the login page HTML. The outbox must keep everything and report "log in" (Task 4 `login redirect keeps the outbox`).
3. **A shared phone after logout.** The cached form must be gone after `/auth/logout` (Task 2 `logout clears the cached form`).
4. **The cached form while online.** It must never be served when the network works (Task 2 `online navigation is network only`).
5. **Storage is full or blocked when queueing.** The draft stays, an error shows, and the page doesn't navigate (Task 5 browser check, item 5).

---

### Task 1: Vendor `localforage`, drop the unused Popper tag, align the service-worker caches

**Files:**
- Create: `app/static/vendor/localforage-1.10.0.min.js`, downloaded from `https://cdn.jsdelivr.net/npm/localforage@1.10.0/dist/localforage.min.js`. Keep its license header.
- Modify: in every template that loads `https://cdn.jsdelivr.net/gh/localforage/localforage/dist/localforage.min.js` (`add.html`, `edit.html`, `list.html`, `lighthouse.html`, `lighthouse/auton.html`), use `{{ url_for('static', filename='vendor/localforage-1.10.0.min.js') }}` instead.
- Modify: `app/templates/base.html:27`. Delete the `@popperjs/core@2` script; nothing references `Popper` or `createPopper`.
- Modify: `app/static/js/service-worker.js`.
  - Change all four cache names to `-v15`, and `CACHE_VERSION` to `'17'`.
  - Add `/static/vendor/localforage-1.10.0.min.js`, `/static/js/coloris.js`, `/static/css/coloris.css` and `/static/css/scouting.css` to `STATIC_ASSETS`.
- Test: `tests/test_browser_resilience.js` (new tests at the end).

- [ ] **Step 1: Write the failing tests:**

```js
test('cache names share one version', () => {
  const src = fs.readFileSync('app/static/js/service-worker.js', 'utf8');
  const versions = [...src.matchAll(/'castle-app-(?:static-|dynamic-|pages-)?v(\d+)'/g)].map(m => m[1]);
  assert.equal(versions.length, 4);
  assert.equal(new Set(versions).size, 1);
});

test('the scout form loads no CDN scripts', () => {
  for (const page of ['add', 'edit', 'list']) {
    const html = fs.readFileSync(`app/templates/scouting/${page}.html`, 'utf8');
    assert.doesNotMatch(html, /<script[^>]+src="https?:/, page);
  }
  assert.doesNotMatch(fs.readFileSync('app/templates/base.html', 'utf8'), /popperjs/);
});
```

- [ ] **Step 2: Run the tests.** Run: `npm test`. Expected: both FAIL (versions `14,14,14,15`; CDN script on add).
- [ ] **Step 3: Implement.** Download the file with `curl -fsSL <url> -o app/static/vendor/localforage-1.10.0.min.js` and check it starts with the localforage header. Then edit the templates and the service worker.
- [ ] **Step 4: Run the tests.** Run `npm test` and `.venv/Scripts/python.exe -m unittest tests.test_security tests.test_bug_fixes`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Vendor localforage, drop unused Popper, align service worker caches"`.

---

### Task 2: The service worker serves the cached scout form offline and forgets it on logout

**Files:**
- Modify: `app/static/js/service-worker.js`, in the fetch handler (around line 188).
- Modify: `tests/test_browser_resilience.js`.
  - Extend the `serviceWorker()` harness: `caches.match` and `caches.open(name).put/match/delete` backed by a `Map`, plus `waitUntil` on the fetch event.
  - Keep existing tests passing.
  - Rename and adjust `authenticated navigation is never served from another session cache` to the rule below.

**Interfaces:**
- Behaviour, placed before the `/auth/` pass-through:
  - When `url.pathname === '/auth/logout'`, call `event.waitUntil(caches.open(PAGE_CACHE_NAME).then(c => c.delete('/scouting/add')))`, then pass the request through to the network as now.
- In the navigation branch, for `url.pathname === '/scouting/add'` only:
  - Go to the network first.
  - On a response with `ok` true **and** `new URL(response.url).pathname === '/scouting/add'` (that is, not redirected to login), `put` a clone under the key `'/scouting/add'`.
  - On a network error, serve `caches.open(PAGE_CACHE_NAME).match('/scouting/add')`, falling back to the existing `handleFetchError` when nothing is cached.
- All other navigations are unchanged: network only, then `handleFetchError`.

- [ ] **Step 1: Write the failing tests:**
  - `online navigation is network only`: with the network working, `/scouting` and `/scouting/add` return the network body, and no cached page is read.
  - `scout form is served from cache only when offline`: navigate to `/scouting/add?event=x` online with body `'form v1'`, then go offline. Navigating to `/scouting/add?after=Qual%201` returns `'form v1'`, and `/scouting/list` offline doesn't return the form.
  - `login redirects are not cached as the form`: the network response has `url` `http://localhost:5000/auth/login`. Offline, the form isn't served.
  - `logout clears the cached form`: cache it, request `/auth/logout`, await `waitUntil`, go offline. The form isn't served.
- [ ] **Step 2: Run the tests.** Run `npm test`. Expected: the 4 new tests FAIL.
- [ ] **Step 3: Implement** the behaviour above.
- [ ] **Step 4: Run the tests.** Run `npm test`. Expected: all PASS.
- [ ] **Step 5: Commit:** `git commit -m "Serve the cached scout form offline and clear it on logout"`.

---

### Task 3: Schedule cache and typed-label helpers

**Files:**
- Modify: `app/static/js/scout/add-flow.js` (new function declarations at the end).
- Test: `tests/test_add_flow.js`.

**Interfaces** (pure; storage may be null or may throw):
- `loadSchedule(storage, userId) -> {events: {}, matches: {}}`
- `saveScheduleEvents(storage, userId, events) -> void`. It merges `{name: {key}}`, keeping only `key`.
- `saveScheduleMatches(storage, userId, eventKey, matches) -> void`. It stores the matches object exactly as `/api/tba/matches` returned it.
- `typedLabel(level, a, b) -> string | null`.
  - Level `"qm"` with a gives `"Qual a"`. Level `"sf"` with a and b gives `"Semifinal a-b"`. Level `"f"` with a gives `"Final a"`.
  - It returns null unless every number used is a positive integer.
- `parseLabel(label) -> {level, a, b} | null`. This is the inverse for those three shapes.
- `nextTypedLabel(label) -> string | null`. `Qual 12` gives `Qual 13`, `Semifinal 2-1` gives `Semifinal 2-2`, `Final 1` gives `Final 2`, and anything else gives null.

- [ ] **Step 1: Write the failing tests:**
  - **Schedule round trip per user:** two events merged across saves; matches stored per event key; user B sees nothing.
  - **Storage that throws** is ignored by all three schedule helpers.
  - **`typedLabel`:**
    - `typedLabel('qm', 12)` gives `'Qual 12'`.
    - `('sf', 2, 1)` gives `'Semifinal 2-1'`.
    - `('f', 1)` gives `'Final 1'`.
    - Each of `('qm', 0)`, `('qm', 1.5)`, `('sf', 2)`, `('x', 1)` and `('qm', '3a')` gives null.
  - **`parseLabel`** inverts `typedLabel` for the three shapes, and `parseLabel('Practice 1')` is null.
  - **`nextTypedLabel`:** the three cases above, and `nextTypedLabel('junk')` is null.
- [ ] **Step 2: Run the tests.** Run `npm test`. Expected: FAIL (`loadSchedule is not a function`).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests.** Run `npm test`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Add schedule cache and typed match label helpers"`.

---

### Task 4: The outbox

**Files:**
- Create: `app/static/js/scout/outbox.js`. Use function declarations, as in `add-flow.js`.
- Create: `tests/test_outbox.js`, and add it to `package.json`'s `test` script.

**Interfaces:**
- `outboxKey(userId) -> "castle:outbox:" + userId`
- `loadOutbox(storage, userId) -> {[client_id]: entry}`. It returns `{}` on any error.
- `queueEntry(storage, userId, entry) -> boolean`. It stores under `entry.client_id` and returns `false` if storage throws or there's no `client_id`.
- `pendingEntries(storage, userId) -> entry[]`, sorted oldest `created_at` first.
- `applyImportResults(storage, userId, results) -> {removed, rejected}`. It removes entries whose result `key` matches with status `saved`, `already_have` or `duplicate`. For `rejected` results, it sets `entry.rejected = reason` and keeps the entry.
- `async syncOutbox(storage, userId, fetchFn) -> {status: "empty"|"done"|"offline"|"login"|"error", removed, rejected, left}`:
  - If nothing is pending, return `empty`.
  - Otherwise POST `/scouting/import` with header `Content-Type: application/json` and body `{format: "castle-entries", version: 1, matches: <first 500 pending>}`.
  - If `fetchFn` throws, return `offline`.
  - A response with `redirected` true, or a non-JSON `content-type`, means `login`.
  - A non-2xx response means `error`.
  - Otherwise `applyImportResults` and return `done`.
  - CSRF comes from `base.html`'s fetch patch. The function takes `fetchFn` so tests can inject it.
- `startOutbox({storage, userId, render})`, in the browser only, not unit-tested:
  - It calls `render(count, lastResult)` now and after every change.
  - It syncs on load, on `online`, and every 60 s while entries are pending.
  - It exposes `window.castleOutbox = {syncNow, count}` for the "Upload now" button.

- [ ] **Step 1: Write the failing tests** in `tests/test_outbox.js`:
  - **Queue and load per user:** `queueEntry` with no `client_id` returns false, and throwing storage returns false.
  - **`pendingEntries`** is ordered by `created_at`.
  - **`outbox sync posts the import envelope`:** check the fake fetch's URL, method and body shape, and that at most 500 entries are sent when 501 are queued.
  - **`outbox sync drops saved, already_have and duplicate, keeps rejected with reason`.**
  - **`login redirect keeps the outbox`:** the response has `redirected: true` and content type `text/html`, giving status `login` and leaving the entries untouched.
  - **`network failure keeps the outbox`:** fetch throws, giving `offline`.
  - A 500 gives `error`, and the entries are kept.
- [ ] **Step 2: Run the tests.** Run `npm test`. Expected: FAIL (ENOENT for `outbox.js`).
- [ ] **Step 3: Implement `outbox.js`.**
- [ ] **Step 4: Run the tests.** Run `npm test`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Add the offline outbox with idempotent sync"`.

---

### Task 5: Wire up the scout form (offline save, schedule fallback, type-in, outbox bar)

**Files:**
- Modify: `app/templates/base.html`. Add `data-user-id="{{ current_user.get_id() if current_user.is_authenticated else '' }}"` on `<body>`. Load `outbox.js` for authenticated users, and start it on every page (it does nothing while the outbox is empty).
- Modify: `app/templates/scouting/add.html` and `list.html`. Add an outbox bar: `<div id="outboxBar" class="... empty:hidden" role="status">`. It's rendered by `startOutbox`: "N waiting to upload · Upload now", plus the rejected reasons and a "Log in to upload" link on `login`.
- Modify: `app/templates/scouting/add.html`. Add a typed-match panel, hidden by default:
  - a link "Match not listed? Type it in";
  - a level `<select>` with `qm`, `sf` and `f`;
  - number inputs a and b, with b only for `sf`;
  - a team number input;
  - a station `<select>` with `red1`..`blue3`;
  - none of these inputs have `name` attributes.
- Modify: `app/static/js/scout/add.js`.
  - **Events:** call `populateEvents(loadSchedule(...).events)` at startup, and `saveScheduleEvents` after every successful `refreshEvents`.
  - **Matches:** in `loadMatchesForSelectedEvent`, call `saveScheduleMatches` after a successful load. When the fetch fails, use the saved `matches[eventKey]` if it's there, with the status "Offline: using the saved schedule". When there's no saved copy, show the typed-match link automatically.
  - **Typed match → the existing form:** "Use typed match" builds the label with `typedLabel`. It adds and selects an option `<option value=label>label (typed)</option>` in `#match_select`, then an option for the team with `data-alliance` from the station in `#team_select`, and dispatches `change`. In typed mode, submit sets `_station` from the station select, overriding `stationOf`.
  - **Preselection:** when `after` isn't in the schedule (or there's no schedule), open the typed panel with `parseLabel(nextTypedLabel(after))` and the station prefilled. When `match` isn't in the schedule, open it with `parseLabel(match)`. Restore does the same when `draft.match` isn't in the options.
  - **Submit:**
    - Replace `form.submit()`, which is still inside batch 1's `try/finally`, with `fetch(form.action || location.pathname, {method: 'POST', body: new FormData(form)})`. If there's a response, `location.assign(response.url)`.
    - If fetch throws, or `navigator.onLine === false` before sending, **queue instead**. Build the entry from `readFields()` plus `event_code`, `match_number`, `team_number`, `alliance`, `event_key` (the selected option's key), `client_id` (`_draft_id`), `scouter_id` (`userId`) and `created_at` (`new Date().toISOString()`), then call `queueEntry`.
    - If that returns true, navigate to the same URL batch 1's server would build: `/scouting/add?event=<key>&after=<label>&station=<station>&saved=<draft id>`. The cached form serves it offline. If it returns false, keep the draft and alert "Couldn't save on this phone — storage is full or blocked. Your entry is still in the form."
  - Load `outbox.js` before `add.js` and bump `add.js`'s `?v=`. Add `outbox.js` to `STATIC_ASSETS`.
- Rebuild CSS if any new class is used.

- [ ] **Step 1: Implement** the above. There's no unit seam for the DOM wiring; the logic it calls is tested in Tasks 3 and 4.
- [ ] **Step 2: Run** `npm test` and the full Python suite (`.venv/Scripts/python.exe -m unittest` with every `tests.test_*` module). Expected: PASS.
- [ ] **Step 3: Check in a browser.** Use the mocked-Mongo preview from phase 1, with `common.scouting_manager.db.team_data.find_one.return_value = None` and `aggregate` returning `[]`, and drive it with playwright-cli `run-code` and `page.context().setOffline(...)`:
  1. **Online:** open `/scouting/add` and pick `Testing Regional #1`. The schedule is saved and the form cached.
  2. **Offline:**
     - Reload `/scouting/add`; the cached form opens.
     - Pick `Qual 1` / red2 from the saved schedule and save. You land on `Qual 2` / red2, and the bar says "1 waiting".
     - Save another; it says "2 waiting".
  3. **Offline typed:** type `Qual 99`, team `254`, `blue1` and save. You land on the typed panel prefilled `Qual 100` / `blue1`.
  4. **Back online:** the bar syncs and empties. The import POST body carries 3 entries with `client_id` and `scouter_id`.
  5. **Offline with `Storage.prototype.setItem` throwing:** save shows the alert, stays on the page, and keeps the fields.
  6. **Log out, then go offline:** `/scouting/add` shows the offline page, not the form.
- [ ] **Step 4: Commit:** `git commit -m "Save scout entries offline, queue and sync them, type in unlisted matches"`.

---

### Task 6: Regression

- [ ] **Step 1: Run the full suites.** Run every Python test module (`ls tests/test_*.py`) and `npm test`. Expected: all OK.
- [ ] **Step 2: Fix anything found.** Write a failing test first, then fix and commit.
