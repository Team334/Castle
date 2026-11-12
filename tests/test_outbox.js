const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function outbox() {
  const scope = {Date, Math, JSON};
  vm.runInNewContext(fs.readFileSync('app/static/js/scout/outbox.js', 'utf8'), scope);
  return scope;
}

function memoryStorage() {
  const items = new Map();
  return {
    getItem: key => (items.has(key) ? items.get(key) : null),
    setItem: (key, value) => items.set(key, String(value)),
    removeItem: key => items.delete(key),
  };
}

const entry = (id, minute = 0) => ({client_id: id, scouter_id: 'u', created_at: `2026-11-11T10:${String(minute).padStart(2, '0')}:00Z`});

function jsonResponse(body, init = {}) {
  return {ok: (init.status || 200) < 400, status: init.status || 200, redirected: !!init.redirected,
          headers: new Headers({'Content-Type': init.type || 'application/json'}), json: async () => body};
}

test('queue and load per user', () => {
  const o = outbox();
  const storage = memoryStorage();
  assert.equal(o.queueEntry(storage, 'u', entry('a')), true);
  assert.equal(o.queueEntry(storage, 'u', {scouter_id: 'u'}), false);
  assert.deepEqual(Object.keys(o.loadOutbox(storage, 'u')), ['a']);
  assert.deepEqual(Object.keys(o.loadOutbox(storage, 'other')), []);
  assert.equal(o.outboxKey('u'), 'castle:outbox:u');
  const broken = {getItem() { throw new Error('x'); }, setItem() { throw new Error('quota'); }};
  assert.equal(o.queueEntry(broken, 'u', entry('b')), false);
  assert.equal(o.queueEntry(null, 'u', entry('b')), false);
  assert.deepEqual(Object.keys(o.loadOutbox(broken, 'u')), []);
});

test('pending entries are oldest first', () => {
  const o = outbox();
  const storage = memoryStorage();
  o.queueEntry(storage, 'u', entry('late', 30));
  o.queueEntry(storage, 'u', entry('early', 5));
  assert.deepEqual(Array.from(o.pendingEntries(storage, 'u'), e => e.client_id), ['early', 'late']);
});

test('outbox sync posts the import envelope, at most 500 at a time', async () => {
  const o = outbox();
  const storage = memoryStorage();
  for (let i = 0; i < 501; i++) o.queueEntry(storage, 'u', entry(`e${i}`));
  let sent;
  await o.syncOutbox(storage, 'u', async (url, options) => {
    sent = {url, options, body: JSON.parse(options.body)};
    return jsonResponse({results: []});
  });
  assert.equal(sent.url, '/scouting/import');
  assert.equal(sent.options.method, 'POST');
  assert.equal(new Headers(sent.options.headers).get('Content-Type'), 'application/json');
  assert.equal(sent.body.format, 'castle-entries');
  assert.equal(sent.body.version, 1);
  assert.equal(sent.body.matches.length, 500);
});

test('outbox sync drops saved, already_have and duplicate, keeps rejected with reason', async () => {
  const o = outbox();
  const storage = memoryStorage();
  for (const id of ['s', 'h', 'd', 'r']) o.queueEntry(storage, 'u', entry(id));
  const result = await o.syncOutbox(storage, 'u', async () => jsonResponse({results: [
    {key: 's', status: 'saved', id: 'x'}, {key: 'h', status: 'already_have'},
    {key: 'd', status: 'duplicate', reason: 'dup'}, {key: 'r', status: 'rejected', reason: 'scout is not on your team'}]}));
  assert.equal(result.status, 'done');
  assert.equal(result.removed, 3);
  assert.equal(result.rejected, 1);
  assert.equal(result.left, 1);
  const left = o.loadOutbox(storage, 'u');
  assert.deepEqual(Object.keys(left), ['r']);
  assert.equal(left.r.rejected, 'scout is not on your team');
});

test('login redirect keeps the outbox', async () => {
  const o = outbox();
  const storage = memoryStorage();
  o.queueEntry(storage, 'u', entry('a'));
  const result = await o.syncOutbox(storage, 'u', async () => jsonResponse(null, {redirected: true, type: 'text/html'}));
  assert.equal(result.status, 'login');
  assert.deepEqual(Object.keys(o.loadOutbox(storage, 'u')), ['a']);
});

test('network failure and server errors keep the outbox', async () => {
  const o = outbox();
  const storage = memoryStorage();
  o.queueEntry(storage, 'u', entry('a'));
  assert.equal((await o.syncOutbox(storage, 'u', async () => { throw new TypeError('Failed to fetch'); })).status, 'offline');
  assert.equal((await o.syncOutbox(storage, 'u', async () => jsonResponse({error: 'x'}, {status: 500}))).status, 'error');
  assert.deepEqual(Object.keys(o.loadOutbox(storage, 'u')), ['a']);
  assert.equal((await o.syncOutbox(memoryStorage(), 'u', async () => { throw new Error('unused'); })).status, 'empty');
});
