// Outbox: match entries saved on this phone with no signal, waiting to upload to /scouting/import.
// Pure functions take the storage (may be null or throw) and fetch, so they run in node tests;
// startOutbox wires them to the page. Uploads are safe to repeat: the server skips entries it has.
const OUTBOX_BATCH = 500;
const OUTBOX_DONE = new Set(["saved", "already_have", "duplicate"]);

function outboxKey(userId) {
  return "castle:outbox:" + userId;
}

function loadOutbox(storage, userId) {
  try {
    const saved = JSON.parse(storage.getItem(outboxKey(userId)) || "{}");
    return saved && typeof saved === "object" && !Array.isArray(saved) ? saved : {};
  } catch {
    return {};
  }
}

function writeOutbox(storage, userId, entries) {
  storage.setItem(outboxKey(userId), JSON.stringify(entries));
}

function queueEntry(storage, userId, entry) {
  if (!entry?.client_id) return false;
  try {
    const entries = loadOutbox(storage, userId);
    entries[entry.client_id] = entry;
    writeOutbox(storage, userId, entries);
    return true;
  } catch {
    return false;
  }
}

function pendingEntries(storage, userId) {
  return Object.values(loadOutbox(storage, userId))
    .sort((a, b) => String(a.created_at).localeCompare(String(b.created_at)));
}

function applyImportResults(storage, userId, results) {
  const entries = loadOutbox(storage, userId);
  let removed = 0;
  let rejected = 0;
  for (const result of results || []) {
    if (!(result?.key in entries)) continue;
    if (OUTBOX_DONE.has(result.status)) {
      delete entries[result.key];
      removed++;
    } else if (result.status === "rejected") {
      entries[result.key].rejected = result.reason || "rejected";
      rejected++;
    }
  }
  try {
    writeOutbox(storage, userId, entries);
  } catch {}
  return {removed, rejected};
}

async function syncOutbox(storage, userId, fetchFn) {
  const pending = pendingEntries(storage, userId);
  if (!pending.length) return {status: "empty", removed: 0, rejected: 0, left: 0};
  let response;
  try {
    response = await fetchFn("/scouting/import", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({format: "castle-entries", version: 1, matches: pending.slice(0, OUTBOX_BATCH)}),
    });
  } catch {
    return {status: "offline", removed: 0, rejected: 0, left: pending.length};
  }
  // An expired session is redirected to the login page (HTML) rather than answering with JSON.
  const isJson = (response.headers.get("Content-Type") || "").includes("application/json");
  if (response.redirected || !isJson) return {status: "login", removed: 0, rejected: 0, left: pending.length};
  if (!response.ok) return {status: "error", removed: 0, rejected: 0, left: pending.length};
  const body = await response.json().catch(() => ({}));
  const {removed, rejected} = applyImportResults(storage, userId, body.results);
  return {status: "done", removed, rejected, left: pendingEntries(storage, userId).length};
}

// Browser only: sync on load, when the connection returns, and every 60 s while entries wait.
function startOutbox({storage, userId, render = () => {}}) {
  if (!userId) return null;
  let last = null;
  let running = false;
  const count = () => pendingEntries(storage, userId).length;
  async function syncNow() {
    if (running) return last;
    running = true;
    try {
      last = await syncOutbox(storage, userId, (url, options) => fetch(url, options));
    } finally {
      running = false;
      render(count(), last);
    }
    return last;
  }
  window.addEventListener("online", syncNow);
  setInterval(() => count() && syncNow(), 60000);
  render(count(), last);
  if (count()) syncNow();
  window.castleOutbox = {syncNow, count, refresh: () => render(count(), last)};
  return window.castleOutbox;
}
