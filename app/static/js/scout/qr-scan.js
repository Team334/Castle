// Scan page (lead's laptop): read a scout's animated QR (qrf.js) with the camera, then import the
// entries through /scouting/import. Uses BarcodeDetector where the browser has it, else jsQR.
let scanDecoder = qrfDecoder();
let scanFrames = 0;
let scanBusy = false;

function scanSetProgress() {
  const {solved, total} = scanDecoder.progress();
  const percent = total ? Math.floor((solved / total) * 100) : 0;
  document.getElementById("scanBar").style.width = `${percent}%`;
  document.getElementById("scanProgress").textContent = total
    ? `${percent}% · ${scanFrames} frames` : "Waiting for a QR…";
}

function scanShowResults(payload, response, body) {
  const message = document.getElementById("scanMessage");
  const list = document.getElementById("scanResults");
  list.replaceChildren();
  if (!response.ok || !body.results) {
    message.textContent = body.error || `Import failed (${response.status}).`;
    return;
  }
  const byKey = new Map((payload.matches || []).map(entry => [entry.client_id, entry]));
  const words = {saved: "saved", already_have: "already have", duplicate: "duplicate", rejected: "not accepted"};
  for (const result of body.results) {
    const entry = byKey.get(result.key) || {};
    const item = document.createElement("li");
    item.textContent = `Team ${entry.team_number || "?"} · ${entry.match_number || "?"}: ${words[result.status] || result.status}` +
      (result.reason ? ` (${result.reason})` : "");
    list.append(item);
  }
  const counts = body.counts || {};
  const who = payload.scout?.username ? ` from ${payload.scout.username}` : "";
  message.textContent = `Done${who}: ${counts.saved || 0} saved, ${counts.already_have || 0} already here, ` +
    `${counts.duplicate || 0} duplicates, ${counts.rejected || 0} not accepted.`;
}

async function scanImport() {
  scanBusy = true;
  const message = document.getElementById("scanMessage");
  message.textContent = "Got everything, importing…";
  let payload;
  try {
    payload = await qrfUnpack(scanDecoder.result());
  } catch {
    message.textContent = "That QR didn't hold Castle entries. Scan next scout to try again.";
    document.getElementById("scanNext").classList.remove("hidden");
    return;
  }
  try {
    const response = await fetch("/scouting/import", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({format: "castle-entries", version: 1, scout: payload.scout, matches: payload.matches || []}),
    });
    const isJson = (response.headers.get("Content-Type") || "").includes("application/json");
    scanShowResults(payload, response, isJson ? await response.json() : {error: "Log in again, then scan this scout again."});
  } catch {
    message.textContent = "Couldn't reach Castle on this laptop. Check it's running, then scan this scout again.";
  }
  document.getElementById("scanNext").classList.remove("hidden");
}

// One decoded QR text. Global so a test can feed frames without a camera.
function handleScanFrame(text) {
  if (scanBusy || !text) return;
  scanFrames++;
  const done = scanDecoder.add(text);
  scanSetProgress();
  if (done) scanImport();
}

function scanReset() {
  scanDecoder = qrfDecoder();
  scanFrames = 0;
  scanBusy = false;
  document.getElementById("scanMessage").textContent = "";
  document.getElementById("scanResults").replaceChildren();
  document.getElementById("scanNext").classList.add("hidden");
  scanSetProgress();
}

async function scanStart() {
  const video = document.getElementById("scanVideo");
  const canvas = document.getElementById("scanCanvas");
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: "environment"}, audio: false});
  } catch (error) {
    document.getElementById("scanMessage").textContent =
      `Camera unavailable: ${error.message || error.name}. Allow camera access, or use a laptop with a webcam.`;
    return;
  }
  video.srcObject = stream;
  await video.play().catch(() => {});
  window.addEventListener("pagehide", () => stream.getTracks().forEach(track => track.stop()), {once: true});
  const detector = "BarcodeDetector" in window ? new BarcodeDetector({formats: ["qr_code"]}) : null;
  const context = canvas.getContext("2d", {willReadFrequently: true});
  async function tick() {
    if (!scanBusy && video.readyState >= 2) {
      try {
        if (detector) {
          for (const code of await detector.detect(video)) handleScanFrame(code.rawValue);
        } else {
          canvas.width = video.videoWidth;
          canvas.height = video.videoHeight;
          context.drawImage(video, 0, 0);
          const found = jsQR(context.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height,
                             {inversionAttempts: "dontInvert"});
          if (found) handleScanFrame(found.data);
        }
      } catch {}
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("scanNext").addEventListener("click", scanReset);
  scanSetProgress();
  scanStart();
});
