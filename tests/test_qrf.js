const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

function codec() {
  const scope = {TextEncoder, TextDecoder, CompressionStream, DecompressionStream, Response, Blob, Uint8Array,
                 Uint8ClampedArray, Math, JSON, btoa, atob, Array, Object, String, Number, Error};
  vm.runInNewContext(fs.readFileSync('app/static/js/qrf.js', 'utf8'), scope);
  return scope;
}

// Deterministic random for tests (mulberry32).
function rng(seed) {
  return () => {
    seed |= 0; seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function randomBytes(n, seed) {
  const r = rng(seed);
  return Uint8Array.from({length: n}, () => Math.floor(r() * 256));
}

const same = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);

test('systematic frames decode in order', () => {
  const q = codec();
  const data = randomBytes(3000, 1);
  const enc = q.qrfEncoder(data);
  const dec = q.qrfDecoder();
  let done = false;
  for (let n = 0; n < enc.K; n++) done = dec.add(enc.frame(n));
  assert.equal(done, true);
  assert.ok(same(Array.from(dec.result()), Array.from(data)));
});

test('decodes with frames shuffled and 30% dropped', () => {
  const q = codec();
  const data = randomBytes(3000, 2);
  const enc = q.qrfEncoder(data);
  const r = rng(7);
  const frames = Array.from({length: 3 * enc.K}, (_, n) => enc.frame(n)).filter(() => r() >= 0.3);
  for (let i = frames.length - 1; i > 0; i--) {
    const j = Math.floor(r() * (i + 1));
    [frames[i], frames[j]] = [frames[j], frames[i]];
  }
  const dec = q.qrfDecoder();
  let used = 0;
  let done = false;
  for (const frame of frames) {
    used++;
    if ((done = dec.add(frame))) break;
  }
  assert.equal(done, true, `not complete after ${used} frames (K=${enc.K})`);
  assert.ok(same(Array.from(dec.result()), Array.from(data)));
});

test('payloads never mix', () => {
  const q = codec();
  const first = q.qrfEncoder(randomBytes(1500, 3));
  const second = q.qrfEncoder(randomBytes(1500, 4));
  assert.notEqual(first.payloadId, second.payloadId);
  const dec = q.qrfDecoder();
  dec.add(first.frame(0));
  dec.add(first.frame(1));
  let done = false;
  for (let n = 0; n < second.K && !done; n++) done = dec.add(second.frame(n));
  assert.equal(done, true);
  assert.equal(dec.payloadId, second.payloadId);
  assert.ok(same(Array.from(dec.result()), Array.from(randomBytes(1500, 4))));
});

test('late frames are reduced by solved chunks', () => {
  const q = codec();
  const data = randomBytes(2000, 5);
  const enc = q.qrfEncoder(data);
  const dec = q.qrfDecoder();
  for (let n = 0; n < enc.K - 1; n++) dec.add(enc.frame(n));
  const last = enc.K - 1;
  let done = false;
  for (let n = enc.K; n < enc.K + 400 && !done; n++) {
    if (Array.from(q.qrfIndices(enc.K, n)).includes(last)) done = dec.add(enc.frame(n));
  }
  assert.equal(done, true);
  assert.ok(same(Array.from(dec.result()), Array.from(data)));
});

test('malformed frames are ignored', () => {
  const q = codec();
  const dec = q.qrfDecoder();
  const good = q.qrfEncoder(randomBytes(500, 6)).frame(0).split('|');
  for (const bad of ['', 'hello', 'CQ1|x', [...good.slice(0, 5), '%%%not base64%%%'].join('|'),
                     [good[0], good[1], '99', ...good.slice(3)].join('|'), [...good, 'extra'].join('|')]) {
    assert.doesNotThrow(() => assert.equal(dec.add(bad), false, bad));
  }
});

test('unicode round trip through pack and unpack', async () => {
  const q = codec();
  const payload = {notes: 'défense 🚀', matches: [{team_number: '254'}]};
  assert.deepEqual(JSON.parse(JSON.stringify(await q.qrfUnpack(await q.qrfPack(payload)))), payload);
});

test('frames stay small', () => {
  const q = codec();
  const enc = q.qrfEncoder(randomBytes(5000, 8));
  for (let n = 0; n < 3 * enc.K; n++) assert.ok(enc.frame(n).length <= 320, `frame ${n}: ${enc.frame(n).length}`);
});

test('frames carry no chunk list; both sides derive it from the frame number', () => {
  const q = codec();
  const enc = q.qrfEncoder(randomBytes(3000, 10));
  assert.equal(enc.frame(0).split('|').length, 6);
  assert.deepEqual(Array.from(q.qrfIndices(enc.K, 3)), [3]);
  for (let n = enc.K; n < enc.K + 50; n++) {
    const indices = Array.from(q.qrfIndices(enc.K, n));
    assert.ok(indices.length >= 2 && new Set(indices).size === indices.length, `frame ${n}`);
  }
});

test('a single-chunk payload works', () => {
  const q = codec();
  const data = randomBytes(50, 9);
  const enc = q.qrfEncoder(data);
  assert.equal(enc.K, 1);
  const dec = q.qrfDecoder();
  assert.equal(dec.add(enc.frame(5)), true);
  assert.ok(same(Array.from(dec.result()), Array.from(data)));
});

test('vendored QR libraries draw and read back a frame', () => {
  const scope = {TextEncoder, TextDecoder, Uint8Array, Uint8ClampedArray, Math, JSON, btoa, atob, Array, Object,
                 String, Number, Error, Int32Array, Uint16Array, Float32Array, Map, Set};
  scope.window = scope;
  vm.runInNewContext(fs.readFileSync('app/static/js/qrf.js', 'utf8'), scope);
  vm.runInNewContext(fs.readFileSync('app/static/vendor/qrcode-generator-1.4.4.js', 'utf8'), scope);
  vm.runInNewContext(fs.readFileSync('app/static/vendor/jsQR-1.4.0.js', 'utf8'), scope);
  const frame = scope.qrfEncoder(randomBytes(2000, 11)).frame(20);
  const qr = scope.qrcode(0, 'L');
  qr.addData(frame);
  qr.make();
  const modules = qr.getModuleCount();
  const scale = 4, quiet = 4, size = (modules + 2 * quiet) * scale;
  const pixels = new Uint8ClampedArray(size * size * 4).fill(255);
  for (let r = 0; r < modules; r++) {
    for (let c = 0; c < modules; c++) {
      if (!qr.isDark(r, c)) continue;
      for (let y = 0; y < scale; y++) {
        for (let x = 0; x < scale; x++) {
          const offset = (((r + quiet) * scale + y) * size + (c + quiet) * scale + x) * 4;
          pixels[offset] = pixels[offset + 1] = pixels[offset + 2] = 0;
        }
      }
    }
  }
  assert.equal(scope.jsQR(pixels, size, size).data, frame);
});
