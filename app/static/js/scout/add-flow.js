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
