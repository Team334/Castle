// Metric requests return immediately. Poll only unfinished, unique team/event pairs.
function loadTeamStats(root = document) {
  const cells = [...root.querySelectorAll('.team-stats-cell')].filter(cell => !cell.dataset.statsStarted);
  for (const cell of cells) cell.dataset.statsStarted = 'true';
  if (!cells.length) return;
  const metrics = ['epa', 'opr', 'dpr', 'ccwm'];
  const pairs = new Map();
  const keyFor = cell => cell.dataset.eventId
    ? `${cell.dataset.teamId}_${cell.dataset.eventId}` : cell.dataset.teamId;
  for (const cell of cells) {
    pairs.set(keyFor(cell), {team_number: cell.dataset.teamId,
                            event_code: cell.dataset.eventId || null});
  }
  const controller = new AbortController();
  let timer;
  let stopped = false;
  const stop = () => {
    stopped = true;
    clearTimeout(timer);
    controller.abort();
    window.removeEventListener('pagehide', stop);
  };
  window.addEventListener('pagehide', stop, {once: true});
  const started = Date.now();
  function render(cell, data) {
    for (const metric of metrics) {
      const element = cell.querySelector(`.${metric}-value`);
      if (!element) continue;
      const value = data[metric];
      element.textContent = `${metric.toUpperCase()}: ${Number.isFinite(value)
        ? value.toFixed(1) : data.pending ? 'Loading…' : 'N/A'}`;
    }
    cell.dataset.metricValue = data[cell.closest('tbody')?.dataset.metricSort];
  }
  function sortLeaderboard() {
    for (const body of document.querySelectorAll('tbody[data-metric-sort]')) {
      const metric = body.dataset.metricSort;
      if (!metrics.includes(metric)) continue;
      const rows = [...body.rows];
      rows.sort((a, b) => {
        const read = row => {
          const value = row.querySelector('.team-stats-cell')?.dataset.metricValue;
          return value && value !== 'null' && value !== 'undefined'
            ? Number(value) : metric === 'dpr' ? Infinity : -Infinity;
        };
        return (metric === 'dpr' ? read(a) - read(b) : read(b) - read(a)) || 0;
      });
      body.append(...rows);
      rows.forEach((row, index) => {
        if (row.cells[0]) row.cells[0].textContent = index + 1;
      });
    }
  }
  async function load() {
    if (stopped) return;
    const connected = new Set(cells.filter(cell => cell.isConnected).map(keyFor));
    for (const key of pairs.keys()) {
      if (!connected.has(key)) pairs.delete(key);
    }
    if (!pairs.size) {
      window.removeEventListener('pagehide', stop);
      return;
    }
    try {
      const response = await fetch('/api/team_epa_opr', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({teams: [...pairs.values()]}),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`Metrics HTTP ${response.status}`);
      const results = await response.json();
      if (results.error) throw new Error(results.error);
      const timedOut = Date.now() - started >= 90000;
      for (const cell of cells) {
        const key = keyFor(cell);
        if (!pairs.has(key)) continue;
        const data = results[key] || {};
        if (timedOut) data.pending = false;
        render(cell, data);
      }
      for (const key of pairs.keys()) {
        if (!results[key]?.pending || timedOut) pairs.delete(key);
      }
      sortLeaderboard();
      if (pairs.size && !stopped) timer = setTimeout(load, 2000);
      else window.removeEventListener('pagehide', stop);
    } catch (error) {
      if (error.name === 'AbortError') return;
      console.warn('Scouting metrics unavailable:', error);
      for (const cell of cells) if (pairs.has(keyFor(cell))) render(cell, {});
      window.removeEventListener('pagehide', stop);
    }
  }
  load();
}
document.addEventListener('DOMContentLoaded', () => loadTeamStats());
window.addEventListener('pageshow', event => {
  if (event.persisted) window.location.reload();
});
