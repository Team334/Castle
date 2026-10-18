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
  const source = fs.readFileSync('app/static/js/base.js', 'utf8');
  const start = source.indexOf('    const originalFetch =');
  const end = source.indexOf('\n    };', start) + '\n    };'.length;
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

function fuelForm() {
  const listeners = new Map();
  const fields = ['auto_fuel', 'ferried_fuel'].map(name => ({name, value: '',
    addEventListener: (event, handler) => listeners.set(name + ':' + event, handler)}));
  const hint = {textContent: ''};
  const form = {elements: {_fuel_entered: {value: 'false'}}, querySelectorAll: () => fields,
    addEventListener: (event, handler) => listeners.set(event, handler)};
  const scope = {document: {getElementById: () => hint, addEventListener() {}}};
  vm.runInNewContext(fs.readFileSync('app/static/js/scout/fuel-input.js', 'utf8'), scope);
  scope.trackFuelInput(form);
  return {form, fields, hint, fire: name => listeners.get(name)?.()};
}

test('untouched blank fuel fields stay eligible for estimates', () => {
  const {form, fields} = fuelForm();
  assert.equal(form.elements._fuel_entered.value, 'false');
  assert.ok(fields.every(field => field.value === ''));
});

test('zero or cleared scored fuel stays eligible and nonzero counts are manual', () => {
  const {form, fields, fire, hint} = fuelForm();
  fields[0].value = '0';
  fire('auto_fuel:input');
  assert.match(hint.textContent, /uses automatic Match13/);
  fields[0].value = '8';
  fire('auto_fuel:input');
  assert.match(hint.textContent, /saved as entered/);
  fields[0].value = '';
  fire('auto_fuel:input');
  assert.match(hint.textContent, /uses automatic Match13/);
});

test('ferried fuel does not block estimates', () => {
  const {fields, hint, fire} = fuelForm();
  fields[1].value = '53';
  fire('ferried_fuel:change');
  assert.match(hint.textContent, /uses automatic Match13/);
});

function estimatePage(network) {
  const timers = new Map(), events = new Map();
  let timerId = 0;
  const status = {textContent: 'Waiting for fuel estimate', remove() {this.removed = true;}};
  const cells = ['auto_fuel', 'ferried_fuel'].map(field => ({dataset: {fuelFields: field}, textContent: '…'}));
  const row = {dataset: {fuelEstimateId: 'new-record'}, querySelector: () => status, querySelectorAll: () => cells};
  const document = {hidden: false, querySelectorAll: () => row.dataset.fuelEstimateId ? [row] : [],
    addEventListener: (event, callback) => events.set(event, callback)};
  const scope = {document, window: {addEventListener: (event, callback) => events.set(event, callback)},
    fetch: network, AbortController,
    setTimeout: callback => {timers.set(++timerId, callback); return timerId;},
    clearTimeout: id => timers.delete(id)};
  vm.runInNewContext(fs.readFileSync('app/static/js/scout/fuel-estimates.js', 'utf8'), scope);
  events.get('DOMContentLoaded')();
  async function tick() {
    const [id, callback] = timers.entries().next().value;
    timers.delete(id);
    await callback();
  }
  return {row, status, cells, document, timers, tick, leave: () => events.get('pagehide')()};
}

test('estimate polling refreshes counts and a manual edit removes the estimate label', async () => {
  let edited = false;
  const page = estimatePage(async (path, options) => {
    assert.equal(path, '/api/fuel_estimates');
    assert.deepEqual(JSON.parse(options.body).ids, ['new-record']);
    return Response.json({'new-record': {active: !edited, estimated: !edited,
      label: edited ? 'Scouted' : 'Estimated · Match13', fuel: {auto_fuel: edited ? 9 : 8, ferried_fuel: 35}}});
  });
  await page.tick();
  assert.equal(page.cells[0].textContent, '8');
  assert.equal(page.cells[1].textContent, '35');
  assert.equal(page.row.dataset.fuelSource, 'Match13 estimate');
  edited = true;
  await page.tick();
  assert.equal(page.cells[0].textContent, '9');
  assert.equal(page.cells[1].textContent, '35');
  assert.equal(page.row.dataset.fuelSource, 'Scouted');
  assert.equal(page.row.dataset.fuelEstimateId, undefined);
  assert.equal(page.status.removed, true);
});

test('pending scored estimates still display observed ferried fuel', async () => {
  const page = estimatePage(async () => Response.json({'new-record': {
    active: true, estimated: false, label: 'Waiting for fuel estimate', fuel: {auto_fuel: 0, ferried_fuel: 41}}}));
  await page.tick();
  assert.equal(page.cells[0].textContent, '…');
  assert.equal(page.cells[1].textContent, '41');
});

test('hidden estimate pages skip requests and leaving cancels the refresh timer', async () => {
  let calls = 0;
  const page = estimatePage(async () => {calls++; return Response.json({});});
  page.document.hidden = true;
  await page.tick();
  assert.equal(calls, 0);
  page.leave();
  assert.equal(page.timers.size, 0);
});

test('a polling failure preserves displayed values but deleted records are hidden', async () => {
  let failed = true;
  const page = estimatePage(async () => failed ? new Response('', {status: 503}) : Response.json({}));
  page.cells[0].textContent = '8';
  await page.tick();
  assert.equal(page.cells[0].textContent, '8');
  assert.equal(page.row.hidden, undefined);
  failed = false;
  await page.tick();
  assert.equal(page.row.hidden, true);
  assert.equal(page.row.dataset.fuelEstimateId, undefined);
});

function csrfFetch(calls) {
  const source = fs.readFileSync('app/templates/base.html', 'utf8');
  const start = source.indexOf('(function () {', source.indexOf('Send the CSRF token'));
  const end = source.indexOf('})();', start) + '})();'.length;
  const window = {location: {href: 'https://castle.test/scouting', origin: 'https://castle.test'},
    fetch: async (input, init) => {calls.push({input, init}); return new Response('ok');}};
  const document = {querySelector: () => ({content: 'tok123'})};
  vm.runInNewContext(source.slice(start, end), {window, document, Request, Headers, URL});
  return window.fetch;
}

test('CSRF token is added only to same-origin writes', async () => {
  const calls = [];
  const fetch = csrfFetch(calls);
  await fetch('/api/fuel_estimates', {method: 'post', headers: {'Content-Type': 'application/json'}});
  await fetch('/team/1/leave', {method: 'POST', headers: new Headers({'X-Requested-With': 'XMLHttpRequest'})});
  await fetch(new Request('https://castle.test/team/assignments/1/edit', {method: 'PUT'}));
  await fetch('/api/tba/events');
  await fetch('https://api.statbotics.io/v3/team', {method: 'POST'});
  const token = call => call.init && call.init.headers ? new Headers(call.init.headers).get('X-CSRFToken') : null;
  assert.deepEqual(calls.map(token), ['tok123', 'tok123', 'tok123', null, null]);
  assert.equal(new Headers(calls[0].init.headers).get('Content-Type'), 'application/json');
  assert.equal(new Headers(calls[1].init.headers).get('X-Requested-With'), 'XMLHttpRequest');
});
