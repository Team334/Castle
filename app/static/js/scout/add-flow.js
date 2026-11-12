// Add-form drafts and next-match selection. Pure functions; storage may be null or throw
// (private mode, quota), in which case drafts are silently unavailable.
const DRAFT_MAX_AGE_MS = 86400000;

function draftKey(userId) {
  return "castle:scout-drafts:" + userId;
}

function loadDrafts(storage, userId, now = Date.now()) {
  try {
    const drafts = JSON.parse(storage.getItem(draftKey(userId)) || "{}");
    if (!drafts || typeof drafts !== "object" || Array.isArray(drafts)) return {};
    const kept = {};
    for (const [id, draft] of Object.entries(drafts)) {
      if (draft && now - draft.savedAt <= DRAFT_MAX_AGE_MS) kept[id] = draft;
    }
    if (Object.keys(kept).length !== Object.keys(drafts).length) {
      storage.setItem(draftKey(userId), JSON.stringify(kept));
    }
    return kept;
  } catch {
    return {};
  }
}

function saveDraft(storage, userId, id, draft, now = Date.now()) {
  try {
    const drafts = loadDrafts(storage, userId, now);
    drafts[id] = {...draft, savedAt: now};
    storage.setItem(draftKey(userId), JSON.stringify(drafts));
  } catch {}
}

function removeDraft(storage, userId, id) {
  try {
    const drafts = loadDrafts(storage, userId);
    if (!(id in drafts)) return;
    delete drafts[id];
    storage.setItem(draftKey(userId), JSON.stringify(drafts));
  } catch {}
}

function otherDrafts(drafts, currentId) {
  return Object.entries(drafts)
    .filter(([id]) => id !== currentId)
    .map(([id, draft]) => ({...draft, id}))
    .sort((a, b) => b.savedAt - a.savedAt);
}

function nextMatchValue(values, after) {
  const options = values.filter(Boolean);
  const index = options.indexOf(after);
  return index >= 0 && index + 1 < options.length ? options[index + 1] : null;
}

function newDraftId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
}

// ---- Saved schedule: events and their matches, so the form works with no signal ----
function scheduleKey(userId) {
  return "castle:schedule:" + userId;
}

function loadSchedule(storage, userId) {
  try {
    const saved = JSON.parse(storage.getItem(scheduleKey(userId)) || "{}");
    return {events: saved.events || {}, matches: saved.matches || {}};
  } catch {
    return {events: {}, matches: {}};
  }
}

function writeSchedule(storage, userId, schedule) {
  try {
    storage.setItem(scheduleKey(userId), JSON.stringify(schedule));
  } catch {}
}

function saveScheduleEvents(storage, userId, events) {
  const schedule = loadSchedule(storage, userId);
  for (const [name, data] of Object.entries(events || {})) {
    if (data?.key) schedule.events[name] = {key: data.key};
  }
  writeSchedule(storage, userId, schedule);
}

function saveScheduleMatches(storage, userId, eventKey, matches) {
  const schedule = loadSchedule(storage, userId);
  schedule.matches[eventKey] = matches;
  writeSchedule(storage, userId, schedule);
}

// ---- Typed matches: the same labels the dropdown uses (Qual N, Semifinal S-M, Final N) ----
const LABEL_SHAPES = {qm: /^Qual (\d+)$/, sf: /^Semifinal (\d+)-(\d+)$/, f: /^Final (\d+)$/};

function positiveInt(value) {
  const text = String(value ?? "");
  return /^\d+$/.test(text) && Number(text) > 0 ? Number(text) : null;
}

function typedLabel(level, a, b) {
  const first = positiveInt(a);
  if (!first) return null;
  if (level === "qm") return `Qual ${first}`;
  if (level === "f") return `Final ${first}`;
  const second = positiveInt(b);
  return level === "sf" && second ? `Semifinal ${first}-${second}` : null;
}

function parseLabel(label) {
  for (const [level, shape] of Object.entries(LABEL_SHAPES)) {
    const found = shape.exec(label || "");
    if (found) return {level, a: Number(found[1]), b: found[2] ? Number(found[2]) : null};
  }
  return null;
}

function nextTypedLabel(label) {
  const parsed = parseLabel(label);
  if (!parsed) return null;
  return parsed.level === "sf" ? typedLabel("sf", parsed.a, parsed.b + 1) : typedLabel(parsed.level, parsed.a + 1);
}
