# Offline Phase 3 (QR Transfer) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A scout taps **Show QR** to show their waiting entries as an animated fountain-code QR. The lead's laptop opens `/scouting/scan`, catches the frames with its webcam in any order (missed frames don't matter) and imports the entries through phase 1's `/scouting/import`.

**Architecture:**
- `app/static/js/qrf.js` is a self-contained, node-testable Luby Transform fountain codec, rewritten from the `qrf` branch prototype. It works on bytes. `pack` and `unpack` wrap the bytes with JSON and gzip (`CompressionStream`).
- QR drawing and reading use vendored `qrcode-generator` and `jsQR`, with `BarcodeDetector` used when the browser has it.
- `qr-send.js` (the Show QR panel) and `qr-scan.js` (the scan page) are thin DOM layers over `qrf.js`.

**Tech Stack:** vanilla JS, `CompressionStream`/`DecompressionStream`, `getUserMedia`, `node --test` with `vm`, Flask + Jinja.

**Spec:** `docs/superpowers/specs/2026-11-11-offline-venue-mode-design.md`, section 3.

## Global Constraints

- **Frame format:** one ASCII line per frame, `CQ1|<payloadId>|<K>|<byteLength>|<blockId>|<i,j,...>|<base64 chunk>`.
  - `payloadId` is 8 hex characters from a 32-bit FNV-1a hash of the packed bytes.
  - `K` is the chunk count. Blocks `0..K-1` are the plain chunks (systematic). Later blocks XOR 2 or more **distinct** chunks, chosen from the robust soliton distribution with a PRNG seeded from `blockId`.
- **Chunk size:** 180 bytes, so frames stay around 300 characters. Draw at error-correction level L. Frames show at 6 per second.
- **Payload:** `{"format": "castle-entries", "version": 1, "scout": {"_id", "username", "teamNumber"}, "matches": [...]}`, then JSON, then gzip. `matches` are the outbox entries unchanged.
- **Decoder:**
  - It resets when `payloadId` changes.
  - It ignores malformed frames.
  - It reduces each new block by chunks already solved, then peels.
  - Its progress is `solved / K`.
- **Vendored files**, pinned and kept with their license headers:
  - `app/static/vendor/qrcode-generator-1.4.4.js`, from `https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.js`, MIT;
  - `app/static/vendor/jsQR-1.4.0.js`, from `https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js`, Apache-2.0.
- **Service worker:** add `qrf.js`, `qr-send.js` and the two vendor files to `STATIC_ASSETS`. The scan page is online-only on the main server and local on the laptop, so it isn't cached.
- Never connect to the user's MongoDB.
- Commit trailers as before. Do not push.

## Review Focus

1. **Two scouts' codes in front of the camera.** The decoder must never mix them (Task 1 `payloads never mix`).
2. **A frame whose chunks are partly solved already.** It must still help decoding (Task 1 `late frames are reduced by solved chunks`).
3. **Non-ASCII in notes**, such as emoji or accents, must round-trip (Task 1 `unicode round trip`).
4. **A camera that's unavailable or refused.** The scan page shows a clear message, not a blank video (Task 4 browser check, item 4).
5. **Scanning the same scout twice.** The second import reports `already have`, not duplicates (Task 4 browser check, item 3).

---

### Task 1: The `qrf.js` fountain codec

**Files:**
- Create: `app/static/js/qrf.js`. Use top-level function declarations only, so it loads in `vm` and as a browser global.
- Create: `tests/test_qrf.js`, and add it to `package.json`'s `test` script.

**Interfaces:**
- `qrfEncoder(bytes: Uint8Array, chunkSize = 180) -> {payloadId, K, frame(blockId) -> string}`.
  - `frame(n)` for `n < K` is plain chunk `n`.
  - For `n >= K`, it's an XOR of `d` distinct chunks (`d >= 2`, capped at `K`), with `d` sampled from the robust soliton distribution (`c = 0.1`, `delta = 0.5`).
  - When `K === 1`, every frame is chunk 0.
- `qrfDecoder() -> {add(frame) -> boolean /* true when complete */, progress() -> {solved, total}, payloadId, result() -> Uint8Array}`.
- `qrfHash(bytes) -> string` (8 hex characters).
- `async qrfPack(object) -> Uint8Array`: JSON, then gzip via `CompressionStream('gzip')`.
- `async qrfUnpack(bytes) -> object`: the inverse.

- [ ] **Step 1: Write the failing tests** in `tests/test_qrf.js`. Load `qrf.js` with `vm.runInNewContext(src, {TextEncoder, TextDecoder, CompressionStream, DecompressionStream, Response, Blob, Uint8Array, Math, JSON, btoa, atob})`.
  - `systematic frames decode in order`: 3000 random bytes; frames `0..K-1`; complete, and the result is byte-equal.
  - `decodes with frames shuffled and 30% dropped`: take frames `0..3K`, drop 30% at random (seeded), shuffle. Feed them until complete, and it's byte-equal, within `3K` frames.
  - `payloads never mix`: interleave the frames of two payloads. After the switch, the decoder resets and completes with the second payload only.
  - `late frames are reduced by solved chunks`: feed chunks `0..K-2` plain, then only a non-systematic frame containing chunk `K-1`. It completes.
  - `malformed frames are ignored`: `''`, `'hello'`, `'CQ1|x'` and a frame whose base64 is corrupt all return false and don't throw.
  - `unicode round trip`: `qrfUnpack(await qrfPack({notes: 'défense 🚀'}))` deep-equals the input.
  - `frames stay small`: every frame is 320 characters or fewer with the default chunk size.
- [ ] **Step 2: Run the tests.** Run `npm test`. Expected: FAIL (ENOENT for `qrf.js`).
- [ ] **Step 3: Implement `qrf.js`.** Keep the prototype's robust soliton calculation, and fix the four prototype bugs listed in Global Constraints.
- [ ] **Step 4: Run the tests.** Run `npm test`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Add a fountain-code QR codec for moving entries offline"`.

---

### Task 2: Vendor the QR draw and scan libraries

**Files:**
- Create: the two vendor files (see Global Constraints). Check each one's header names the expected library and version.
- Modify: `app/static/js/service-worker.js` (`STATIC_ASSETS`).
- Test: `tests/test_qrf.js`: `vendored QR libraries draw and read back a frame`.
  - Load both files in one `vm` context.
  - Build a QR for a real `qrfEncoder` frame at type 0, level L, with `qrcode(0, 'L')`, `addData` and `make`.
  - Rasterise its modules into an RGBA `Uint8ClampedArray` at 4 px per module with a 4-module quiet zone.
  - `jsQR(data, w, h).data` equals the frame.

- [ ] **Step 1: Write the failing test.**
- [ ] **Step 2: Run the tests.** Run `npm test`. Expected: FAIL (ENOENT for the vendor files).
- [ ] **Step 3: Implement.** Download the two files with `curl -fsSL`, and add all four assets to `STATIC_ASSETS`.
- [ ] **Step 4: Run the tests.** Run `npm test`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Vendor qrcode-generator and jsQR"`.

---

### Task 3: Show QR on the scout's phone

**Files:**
- Modify: `app/templates/base.html`. Add `data-username` and `data-team` (the current user's `username` and `teamNumber`) on `<body>`, next to `data-user-id`.
- Create: `app/static/js/scout/qr-send.js`. It defines a global `showOutboxQR()`.
  - It opens a full-screen panel built in JS, using existing `card` and `btn` classes plus a white box for the QR.
  - It packs `{format, version: 1, scout: {_id, username, teamNumber}, matches: pendingEntries(...)}`.
  - It draws `frame(n)` for `n = 0, 1, 2, …` at 6 per second onto a `<canvas>` with `qrcode-generator`. Size the canvas to the screen's shorter side.
  - It shows "N entries · frame n".
  - Its buttons: **Lead has these** sets `handed_at` (an ISO time) on those outbox entries and closes; **Close** just closes. The interval always stops on close.
- Modify: `app/static/js/scout/outbox.js` (`renderOutboxBar`).
  - When `typeof showOutboxQR === 'function'`, add a **Show QR** button.
  - When some entries have `handed_at`, the text adds "(M given to the lead)".
  - Leave the outbox logic unchanged: handed entries still sync.
- Modify: `add.html` and `list.html`. Load `vendor/qrcode-generator-1.4.4.js`, `js/qrf.js` and `js/scout/qr-send.js`.
- Test: the `tests/test_outbox.js` logic is unchanged. Task 5's browser check covers this task.

- [ ] **Step 1: Implement.**
- [ ] **Step 2: Run** `npm test` and the full Python suite. Expected: PASS.
- [ ] **Step 3: Commit:** `git commit -m "Show waiting entries as an animated QR code"`.

---

### Task 4: The scan page on the lead's laptop

**Files:**
- Modify: `app/scout/routes/transfer.py`. Add `GET /scouting/scan` (`@login_required`) that renders `scouting/scan.html`.
- Create: `app/templates/scouting/scan.html`. It has:
  - a page header ("Scan entries");
  - `<video id="scanVideo" playsinline muted>`;
  - a hidden `<canvas>`;
  - a progress bar and text ("Waiting for a QR…", "42% · 18 frames");
  - `#scanMessage` (role=status);
  - a results list `#scanResults`;
  - a **Scan next scout** button.
  It loads `vendor/jsQR-1.4.0.js`, `js/qrf.js` and `js/scout/qr-scan.js`.
- Create: `app/static/js/scout/qr-scan.js`.
  - **Start:** `getUserMedia({video: {facingMode: 'environment'}})`. On failure, `#scanMessage` says "Camera unavailable: <reason>. Allow camera access, or use a laptop with a webcam."
  - **Reading frames:** each animation frame, read a QR. Use `BarcodeDetector` when `'BarcodeDetector' in window`, otherwise draw the video to the canvas and use `jsQR`. Pass each result to a global `handleScanFrame(text)`.
  - **`handleScanFrame`:** feeds `qrfDecoder`, updates progress, and when complete:
    - `qrfUnpack`;
    - POST to `/scouting/import` with `{format, version, scout, matches}`;
    - render one line per result, e.g. `Team 254 · Qual 12 — saved` (use the entry's `team_number` and `match_number`, looked up by `key`/`client_id`), plus the counts;
    - stop decoding until **Scan next scout**, which resets the decoder.
  - On a non-OK or non-JSON response, show the server's `error`, or "Import failed (status)".
- Modify: `app/templates/scouting/list.html`. Add a "Scan QR" link in the tools nav (line 56).
- Test: `tests/test_transfer.py`, class `ScanPageTests`. With the harness `start_app()` and `logged_in_client`, `GET /scouting/scan` is 200, contains `id="scanVideo"`, and its scripts include `jsQR-1.4.0.js`.

- [ ] **Step 1: Write the failing test.**
- [ ] **Step 2: Run the test.** Run `.venv/Scripts/python.exe -m unittest tests.test_transfer -v`. Expected: FAIL (404).
- [ ] **Step 3: Implement** the route, template and JS.
- [ ] **Step 4: Run the tests.** Run `tests.test_transfer` and `npm test`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "Add the QR scan page for the lead's laptop"`.

---

### Task 5: Browser check and regression

- [ ] **Step 1: Check in a browser** (mocked-Mongo preview, playwright-cli):
  1. **Show QR:** queue 3 entries offline (as in the phase 2 check), then tap **Show QR**.
     - The panel animates: the frame counter rises.
     - Decoding the canvas pixels in the page with `jsQR` gives a `CQ1|` frame.
     - Collect those decoded strings over about 3 s.
  2. **Scan:** open `/scouting/scan` and feed the collected frames to `handleScanFrame` in shuffled order. The import POST carries the 3 entries and `scout`, and the results list shows 3 lines.
  3. **Scan again:** "Scan next scout", then feed the same frames. The results say "already have".
  4. **No camera:** with camera permission denied (no fake camera), the scan page shows the "Camera unavailable" message.
  5. **Lead has these:** the outbox bar shows "(3 given to the lead)", and the entries are still queued.
- [ ] **Step 2: Full regression.** Run every `tests/test_*.py` module and `npm test`. Expected: all OK.
- [ ] **Step 3: Fix anything found** with a failing test first, then commit.
