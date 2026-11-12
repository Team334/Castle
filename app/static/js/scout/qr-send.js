// Show QR: the scout's waiting entries (outbox.js) as an animated fountain-code QR (qrf.js) that the
// lead's laptop scans at /scouting/scan. Works offline. Entries stay queued: the phone still uploads
// them itself later, and the server skips the ones it already has.
const QR_FRAMES_PER_SECOND = 6;

function drawQrFrame(canvas, text, size) {
  const qr = qrcode(0, "L");
  qr.addData(text);
  qr.make();
  const modules = qr.getModuleCount() + 8;  // 4-module quiet zone on each side
  const scale = Math.max(2, Math.floor(size / modules));
  canvas.width = canvas.height = modules * scale;
  const context = canvas.getContext("2d");
  context.fillStyle = "#fff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#000";
  for (let row = 0; row < modules - 8; row++) {
    for (let col = 0; col < modules - 8; col++) {
      if (qr.isDark(row, col)) context.fillRect((col + 4) * scale, (row + 4) * scale, scale, scale);
    }
  }
}

async function showOutboxQR() {
  let storage = null;
  try {
    storage = window.localStorage;
  } catch {}
  const me = document.body.dataset;
  const entries = pendingEntries(storage, me.userId);
  if (!entries.length) return;
  const bytes = await qrfPack({
    format: "castle-entries", version: 1,
    scout: {_id: me.userId, username: me.username, teamNumber: Number(me.team) || null},
    matches: entries,
  });
  const encoder = qrfEncoder(bytes);

  const panel = document.createElement("div");
  panel.className = "fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-modal", "true");
  panel.setAttribute("aria-label", "Show these entries to the lead");
  const card = document.createElement("div");
  card.className = "card w-full max-w-md";
  const body = document.createElement("div");
  body.className = "card-body space-y-3 text-center";
  const canvas = document.createElement("canvas");
  canvas.id = "qrCanvas";
  canvas.className = "mx-auto block rounded-lg";
  canvas.setAttribute("aria-label", "Animated QR code");
  const info = document.createElement("p");
  info.className = "help";
  const actions = document.createElement("div");
  actions.className = "flex justify-center gap-2";
  const handed = document.createElement("button");
  handed.type = "button";
  handed.className = "btn btn-primary";
  handed.textContent = "Lead has these";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "btn btn-secondary";
  close.textContent = "Close";
  actions.append(handed, close);
  body.append(canvas, info, actions);
  card.append(body);
  panel.append(card);
  document.body.append(panel);

  const size = Math.min(480, Math.min(window.innerWidth, window.innerHeight) - 96);
  let frame = 0;
  const show = () => {
    drawQrFrame(canvas, encoder.frame(frame), size);
    info.textContent = `${entries.length} ${entries.length === 1 ? "entry" : "entries"} · frame ${frame + 1}. ` +
      "Hold the screen up to the lead's camera until it says done.";
    frame++;
  };
  show();
  const timer = setInterval(show, 1000 / QR_FRAMES_PER_SECOND);

  function finish() {
    clearInterval(timer);
    document.removeEventListener("keydown", onKey);
    panel.remove();
    window.castleOutbox?.refresh();
  }
  function onKey(event) {
    if (event.key === "Escape") finish();
  }
  document.addEventListener("keydown", onKey);
  close.addEventListener("click", finish);
  handed.addEventListener("click", () => {
    const at = new Date().toISOString();
    for (const entry of entries) queueEntry(storage, me.userId, {...entry, handed_at: at});
    finish();
  });
  close.focus();
}
