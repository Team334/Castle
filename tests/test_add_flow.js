const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function flow() {
  const scope = {Date, Math, JSON};
  vm.runInNewContext(fs.readFileSync('app/static/js/scout/add-flow.js', 'utf8'), scope);
  return scope;
}

function memoryStorage() {
  const items = new Map();
  return {
    items,
    getItem: key => (items.has(key) ? items.get(key) : null),
    setItem: (key, value) => items.set(key, String(value)),
    removeItem: key => items.delete(key),
  };
}

const DAY = 86400000;

test('save, load and remove round-trip per user', () => {
  const f = flow();
  const storage = memoryStorage();
  f.saveDraft(storage, 'userA', 'd1', {team: '254', match: 'Qual 1'}, 1000);
  assert.equal(f.loadDrafts(storage, 'userA', 2000).d1.team, '254');
  assert.equal(f.loadDrafts(storage, 'userA', 2000).d1.savedAt, 1000);
  assert.equal(Object.keys(f.loadDrafts(storage, 'userB', 2000)).length, 0);
  f.removeDraft(storage, 'userA', 'd1');
  assert.equal(Object.keys(f.loadDrafts(storage, 'userA', 2000)).length, 0);
  assert.equal(f.draftKey('userA'), 'castle:scout-drafts:userA');
});

test('drafts older than 24 hours are pruned', () => {
  const f = flow();
  const storage = memoryStorage();
  f.saveDraft(storage, 'u', 'old', {team: '1'}, 0);
  f.saveDraft(storage, 'u', 'new', {team: '2'}, DAY);
  assert.deepEqual(Object.keys(f.loadDrafts(storage, 'u', DAY + 1)), ['new']);
  assert.deepEqual(Object.keys(JSON.parse(storage.getItem(f.draftKey('u')))), ['new']);
});

test('clearing by an old saved id leaves the current drafts', () => {
  const f = flow();
  const storage = memoryStorage();
  const now = Date.now();  // removeDraft prunes against the real clock
  f.saveDraft(storage, 'u', 'old', {}, now - 2);
  f.saveDraft(storage, 'u', 'cur', {}, now - 1);
  f.removeDraft(storage, 'u', 'gone');
  assert.deepEqual(Object.keys(f.loadDrafts(storage, 'u', now)).sort(), ['cur', 'old']);
});

test('starting a new entry keeps the offered draft', () => {
  const f = flow();
  const storage = memoryStorage();
  f.saveDraft(storage, 'u', 'a', {team: '1'}, 1);
  f.saveDraft(storage, 'u', 'b', {team: '2'}, 2);
  const drafts = f.loadDrafts(storage, 'u', 3);
  // Array.from: arrays built inside the vm context have another realm's prototype.
  assert.deepEqual(Array.from(f.otherDrafts(drafts, 'b'), d => d.id), ['a']);
  assert.deepEqual(Array.from(f.otherDrafts(drafts, 'c'), d => d.id), ['b', 'a']);
  assert.equal(f.otherDrafts(drafts, 'c')[0].team, '2');
});

test('storage that throws is ignored', () => {
  const f = flow();
  const broken = {
    getItem() { throw new Error('denied'); },
    setItem() { throw new Error('quota'); },
    removeItem() { throw new Error('denied'); },
  };
  for (const storage of [broken, null]) {
    assert.deepEqual(Object.keys(f.loadDrafts(storage, 'u')), []);
    assert.doesNotThrow(() => f.saveDraft(storage, 'u', 'd', {}));
    assert.doesNotThrow(() => f.removeDraft(storage, 'u', 'd'));
  }
  const garbage = memoryStorage();
  garbage.setItem(f.draftKey('u'), '{not json');
  assert.deepEqual(Object.keys(f.loadDrafts(garbage, 'u')), []);
});

test('next match follows dropdown order', () => {
  const f = flow();
  const values = ['', 'Qual 1', 'Qual 2', 'Semifinal 1-1', 'Final 1'];
  assert.equal(f.nextMatchValue(values, 'Qual 2'), 'Semifinal 1-1');
  assert.equal(f.nextMatchValue(values, 'Final 1'), null);
  assert.equal(f.nextMatchValue(values, 'Qual 99'), null);
});

test('draft ids are unique and URL-safe', () => {
  const f = flow();
  const a = f.newDraftId();
  assert.match(a, /^[A-Za-z0-9-]{1,64}$/);
  assert.notEqual(a, f.newDraftId());
});
