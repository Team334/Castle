// Poll our own saved values; only the shared server scheduler calls Match13.
document.addEventListener('DOMContentLoaded', () => {
    const controller = new AbortController();
    let stopped = false;
    let timer;
    async function refresh() {
        if (stopped) return;
        if (!document.hidden) {
            const rows = [...document.querySelectorAll('[data-fuel-estimate-id]')];
            try {
                for (let offset = 0; offset < rows.length; offset += 100) {
                    const batch = rows.slice(offset, offset + 100);
                    const response = await fetch('/api/fuel_estimates', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ids: batch.map(row => row.dataset.fuelEstimateId)}),
                        signal: controller.signal,
                    });
                    if (!response.ok) throw new Error('Fuel estimates temporarily unavailable');
                    const values = await response.json();
                    for (const row of batch) {
                        const result = values[row.dataset.fuelEstimateId];
                        // A record edited or deleted elsewhere no longer has automatic updates.
                        if (!result) {
                            delete row.dataset.fuelEstimateId;
                            row.hidden = true;
                            continue;
                        }
                        row.dataset.fuelSource = result.estimated ? 'Match13 estimate' : result.active ? 'Awaiting estimate' : 'Scouted';
                        const status = row.querySelector('.fuel-estimate-status');
                        if (status) status.textContent = result.label;
                        if (!result.active) {
                            delete row.dataset.fuelEstimateId;
                            status?.remove();
                        }
                        for (const cell of row.querySelectorAll('[data-fuel-fields]')) {
                            cell.textContent = result.active && cell.dataset.fuelFields === 'ferried_fuel' ? '—'
                                : result.active && !result.estimated ? '…'
                                : cell.dataset.fuelFields.split(',').map(field => result.fuel[field] ?? 0).join('/');
                        }
                    }
                }
            } catch (error) {
                if (error.name === 'AbortError') return;
                // Keep the last displayed numbers during provider/network failures.
            }
        }
        if (!stopped) timer = setTimeout(refresh, 60000);
    }
    timer = setTimeout(refresh, 5000);
    window.addEventListener('pagehide', () => {
        stopped = true;
        clearTimeout(timer);
        controller.abort();
    }, {once: true});
});
