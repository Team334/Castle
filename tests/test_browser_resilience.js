const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function serviceWorker(network) {
  const handlers = new Map();
  let cacheReads = 0;
  vm.runInNewContext(fs.readFileSync('app/static/js/service-worker.js', 'utf8'), {
    self: {location: {origin: 'http://localhost:5000'},
      addEventListener: (name, handler) => handlers.set(name, handler)},
    URL, Response, console: {log() {}, warn() {}, error() {}},
    setInterval() {}, fetch: network,
    caches: {match: () => {cacheReads++; return Promise.resolve(new Response('stale'));}},
  });
  return {
    request(path, options = {}) {
      let promise;
      handlers.get('fetch')({request: {
        url: `http://localhost:5000${path}`, method: options.method || 'GET',
        mode: options.mode || 'cors', headers: new Headers(),
      }, respondWith: result => {promise = result;}});
      return promise;
    },
    cacheReads: () => cacheReads,
  };
}

test('API polling and connectivity probes always reach the network', async () => {
  let networkCalls = 0;
  const worker = serviceWorker(async () => {
    networkCalls++;
    return new Response('fresh');
  });
  for (const path of ['/api/tba/events?background=1', '/static/logo.png?checkOnline=123']) {
    assert.equal(await (await worker.request(path)).text(), 'fresh');
  }
  assert.equal(networkCalls, 2);
  assert.equal(worker.cacheReads(), 0);
});

test('authenticated navigation is never served from another session cache', async () => {
  const worker = serviceWorker(async () => new Response('current account'));
  assert.equal(await (await worker.request('/scouting', {mode: 'navigate'})).text(), 'current account');
  assert.equal(worker.cacheReads(), 0);
});

test('failed writes remain failures rather than successful offline responses', async () => {
  const worker = serviceWorker(async () => {throw new Error('disconnected');});
  await assert.rejects(worker.request('/scouting/add', {method: 'POST'}), /disconnected/);
  assert.equal(worker.cacheReads(), 0);
});

function pageFetch(network, online) {
  const source = fs.readFileSync('app/templates/base.html', 'utf8');
  const start = source.indexOf('            const originalFetch =');
  const end = source.indexOf('\n            };', start) + '\n            };'.length;
  const storage = new Map([['offlineMode', 'true']]);
  const scope = {
    window: {fetch: network}, navigator: {onLine: online},
    localStorage: {getItem: key => storage.get(key)},
    document: {body: {classList: {remove() {}, add() {}}}},
    hideOfflineIndicators: () => storage.delete('offlineMode'),
    showOfflineIndicators() {},
    Response, Headers, Request, console: {error() {}},
  };
  vm.runInNewContext(source.slice(start, end), scope);
  return scope.window.fetch;
}

test('online verification uses one unwrapped probe without recursive fetches', async () => {
  let calls = 0;
  const fetch = pageFetch(async () => {calls++; return new Response('ok');}, true);
  await fetch('/api/example');
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls, 2);
});

test('offline JSON accepts plain header objects and reports an error', async () => {
  const fetch = pageFetch(async () => {throw new Error('offline');}, false);
  const response = await fetch('/api/example', {headers: {'Content-Type': 'application/json'}});
  assert.equal(response.status, 503);
  assert.equal((await response.json()).error, 'offline');
});

test('leaving a page propagates AbortError without triggering offline handling', async () => {
  const fetch = pageFetch(async () => {
    const error = new Error('cancelled');
    error.name = 'AbortError';
    throw error;
  }, false);
  await assert.rejects(fetch('/api/example'), error => error.name === 'AbortError');
});

function matchLoader(network, timers = {setTimeout, clearTimeout}) {
  const source = fs.readFileSync('app/static/js/scout/add.js', 'utf8');
  const scope = {fetch: network, Date, ...timers};
  vm.runInNewContext(source.slice(0, source.indexOf('const updateMatchResult')), scope);
  return scope.loadEventMatches;
}

test('match loading polls pending data and uses the completed result', async () => {
  let calls = 0;
  const loader = matchLoader(async () => ++calls === 1
    ? Response.json(null, {headers: {'X-Scouting-Pending': 'true'}})
    : Response.json({'Qual 1': {red: ['frc334']}}),
    {setTimeout: callback => setTimeout(callback, 0), clearTimeout});
  const result = await loader('2026nyny', new AbortController().signal);
  assert.equal(result['Qual 1'].red[0], 'frc334');
  assert.equal(calls, 2);
});

test('changing events or leaving the page cancels a pending match poll', async () => {
  let calls = 0;
  let timerCreated;
  const waiting = new Promise(resolve => {timerCreated = resolve;});
  const loader = matchLoader(async () => {
    calls++;
    return Response.json(null, {headers: {'X-Scouting-Pending': 'true'}});
  }, {setTimeout: callback => {timerCreated(); return setTimeout(callback, 2000);}, clearTimeout});
  const controller = new AbortController();
  const result = loader('2026nyny', controller.signal);
  await waiting;
  controller.abort();
  await assert.rejects(result, error => error.name === 'AbortError');
  assert.equal(calls, 1);
});

test('an unavailable match service stops polling', async () => {
  let calls = 0;
  const loader = matchLoader(async () => {
    calls++;
    return Response.json(null, {headers: {'X-Scouting-Pending': 'false'}});
  });
  assert.equal(await loader('2026nyny', new AbortController().signal), null);
  assert.equal(calls, 1);
});
