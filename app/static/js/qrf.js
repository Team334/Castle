// QR fountain codes (Luby Transform) for moving entries between devices with no network.
// A payload is split into K chunks. Frame n < K carries chunk n; later frames XOR a few distinct chunks
// chosen from the robust soliton distribution with a PRNG seeded by the frame number, so a scanner
// can catch frames in any order and still rebuild the payload after missing some.
// Frame text: CQ1|<payloadId>|<K>|<byteLength>|<frameNumber>|<base64 block>
// Rewritten from the team's `qrf` prototype: distinct chunk choices, a payload id so two scouts'
// codes never mix, blocks reduced by already-solved chunks on arrival, and smaller frames.
const QRF_CHUNK = 180;
const QRF_SOLITON = {};

function qrfHash(bytes) {
  let hash = 0x811c9dc5;  // 32-bit FNV-1a
  for (const byte of bytes) hash = Math.imul(hash ^ byte, 0x01000193) >>> 0;
  return hash.toString(16).padStart(8, "0");
}

function qrfRandom(seed) {  // mulberry32
  return () => {
    seed = seed + 0x6D2B79F5 | 0;
    let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

// Cumulative robust soliton distribution over degrees 1..K (c = 0.1, delta = 0.5).
function qrfSolitonCdf(K) {
  if (QRF_SOLITON[K]) return QRF_SOLITON[K];
  const c = 0.1, delta = 0.5;
  const R = c * Math.log(K / delta) * Math.sqrt(K);
  const M = Math.max(1, Math.floor(K / R));
  const weights = [0];
  for (let i = 1; i <= K; i++) {
    const ideal = i === 1 ? 1 / K : 1 / (i * (i - 1));
    const robust = i < M ? R / (i * K) : i === M ? R * Math.log(R / delta) / K : 0;
    weights.push(ideal + Math.max(0, robust));
  }
  const total = weights.reduce((sum, w) => sum + w, 0);
  const cdf = [0];
  for (let i = 1; i <= K; i++) cdf.push(cdf[i - 1] + weights[i] / total);
  return (QRF_SOLITON[K] = cdf);
}

// Which chunks frame n combines; the encoder and decoder both derive this, so frames don't carry it.
function qrfIndices(K, n) {
  if (n < K) return [n];
  if (K === 1) return [0];
  const random = qrfRandom(Math.imul(n, 2654435761) ^ K);
  const cdf = qrfSolitonCdf(K);
  const u = random();
  let degree = 1;
  while (degree < K && u >= cdf[degree]) degree++;
  degree = Math.min(K, Math.max(2, degree));
  const chosen = new Set();
  while (chosen.size < degree) chosen.add(Math.floor(random() * K));
  return [...chosen].sort((a, b) => a - b);
}

function qrfToBase64(bytes) {
  return btoa(String.fromCharCode(...bytes));
}

function qrfFromBase64(text) {
  return Uint8Array.from(atob(text), ch => ch.charCodeAt(0));
}

function qrfXor(target, source) {
  for (let i = 0; i < target.length; i++) target[i] ^= source[i];
}

function qrfEncoder(bytes, chunkSize = QRF_CHUNK) {
  const K = Math.max(1, Math.ceil(bytes.length / chunkSize));
  const chunks = Array.from({length: K}, (_, i) => {
    const chunk = new Uint8Array(chunkSize);
    chunk.set(bytes.subarray(i * chunkSize, (i + 1) * chunkSize));
    return chunk;
  });
  const payloadId = qrfHash(bytes);
  return {
    payloadId,
    K,
    frame(n) {
      const block = new Uint8Array(chunkSize);
      for (const i of qrfIndices(K, n)) qrfXor(block, chunks[i]);
      return ["CQ1", payloadId, K, bytes.length, n, qrfToBase64(block)].join("|");
    },
  };
}

function qrfDecoder() {
  let state = null;

  function reset(payloadId, K, length, size) {
    state = {payloadId, K, length, size, solved: new Array(K).fill(null), pending: [], seen: new Set()};
  }

  function complete() {
    return !!state && state.solved.every(Boolean);
  }

  function peel() {
    let progress = true;
    while (progress) {
      progress = false;
      for (const block of state.pending) {
        if (block.indices.length !== 1) continue;
        const index = block.indices[0];
        state.pending = state.pending.filter(other => other !== block);
        if (!state.solved[index]) {
          state.solved[index] = block.data;
          for (const other of state.pending) {
            if (other.indices.includes(index)) {
              qrfXor(other.data, block.data);
              other.indices = other.indices.filter(i => i !== index);
            }
          }
        }
        progress = true;
        break;
      }
    }
  }

  return {
    get payloadId() {
      return state?.payloadId ?? null;
    },
    add(frame) {
      try {
        const parts = String(frame).split("|");
        if (parts.length !== 6 || parts[0] !== "CQ1" || !/^[0-9a-f]{8}$/.test(parts[1])) return false;
        const [K, length, n] = parts.slice(2, 5).map(Number);
        if (![K, length, n].every(Number.isInteger) || K < 1 || length < 1 || n < 0) return false;
        const data = qrfFromBase64(parts[5]);
        const size = data.length;
        if (!size || K * size < length || (K - 1) * size >= length) return false;
        if (parts[1] !== state?.payloadId) reset(parts[1], K, length, size);
        else if (K !== state.K || length !== state.length || size !== state.size) return false;
        if (state.seen.has(n)) return complete();
        state.seen.add(n);
        let indices = qrfIndices(K, n);
        for (const i of indices) if (state.solved[i]) qrfXor(data, state.solved[i]);
        indices = indices.filter(i => !state.solved[i]);
        if (indices.length) {
          state.pending.push({indices, data});
          peel();
        }
        return complete();
      } catch {
        return false;
      }
    },
    progress() {
      return {solved: state ? state.solved.filter(Boolean).length : 0, total: state ? state.K : 0};
    },
    result() {
      if (!complete()) throw new Error("QR payload incomplete");
      const out = new Uint8Array(state.K * state.size);
      state.solved.forEach((chunk, i) => out.set(chunk, i * state.size));
      return out.slice(0, state.length);
    },
  };
}

async function qrfPack(object) {
  const stream = new Blob([JSON.stringify(object)]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function qrfUnpack(bytes) {
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(stream).text());
}
