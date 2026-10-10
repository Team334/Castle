let filterType;
let searchInput;
let modalCanvas;
let filterTimer;

let listController;
let listGeneration = 0;
let listBusy = false;

async function loadMatches(reset = false) {
    const button = document.getElementById('loadMoreMatches');
    const status = document.getElementById('matchListStatus');
    const container = document.getElementById('teamDataContainer');
    if (!button || (!reset && listBusy)) return;
    listController?.abort();
    const controller = listController = new AbortController();
    const generation = ++listGeneration;
    listBusy = true;
    button.disabled = true;
    status.textContent = 'Loading matches…';
    const url = new URL(button.dataset.url, window.location.origin);
    url.searchParams.set('partial', '1');
    url.searchParams.set('page', reset ? '1' : button.dataset.nextPage);
    url.searchParams.set('search', searchInput.value);
    url.searchParams.set('filter', filterType.value);
    try {
        const response = await fetch(url, {signal: controller.signal});
        if (!response.ok) throw new Error(`Matches HTTP ${response.status}`);
        const result = await response.json();
        if (generation !== listGeneration) return;
        if (result.error || typeof result.html !== 'string') throw new Error('Invalid match response');
        const template = document.createElement('template');
        template.innerHTML = result.html;
        const incoming = template.content.querySelector('#teamDataContainer');
        if (!incoming) throw new Error('Missing match list');
        if (reset) container.replaceChildren();
        for (const section of [...incoming.querySelectorAll('.event-section')]) {
            const existing = [...container.querySelectorAll('.event-section')]
                .find(item => item.dataset.eventCode === section.dataset.eventCode);
            if (existing) existing.querySelector('tbody').append(...section.querySelectorAll('.team-row'));
            else container.append(section);
        }
        button.dataset.nextPage = result.next_page;
        button.hidden = !result.has_more;
        const count = container.querySelectorAll('.team-row').length;
        status.textContent = count ? `Showing ${count} of ${result.total} matches` : 'No matches found.';
        loadTeamStats(container);
    } catch (error) {
        if (error.name !== 'AbortError' && generation === listGeneration) {
            status.textContent = 'Unable to load matches. Please try again.';
            // Retrying a failed search must replace the old result set.
            button.dataset.retryReset = reset ? 'true' : 'false';
            button.hidden = false;
        }
    } finally {
        if (generation === listGeneration) {
            listBusy = false;
            button.disabled = false;
        }
    }
}

const filterRows = () => {
    const button = document.getElementById('loadMoreMatches');
    if (button) delete button.dataset.retryReset;
    loadMatches(true);
};

function showAutoPath(pathData, autoNotes) {
    const modal = document.getElementById('autoPathModal');
    const container = document.getElementById('autoPathContainer');
    const notesElement = document.getElementById('autoNotes');
    const canvas = document.getElementById('autoPath');

    if (!modal || !container || !notesElement || !canvas) {
        console.error('Required elements not found');
        return;
    }

    notesElement.textContent = autoNotes;
    modal.classList.remove('hidden');

    const CanvasField = modalCanvas || (modalCanvas = new Canvas({
        canvas: canvas,
        container: container,
        backgroundImage: '/static/images/field-2026.png',
        maxPanDistance: 1000
    }));
    CanvasField.drawingHistory = [];
    CanvasField.resizeCanvas();

    if (pathData) {
        try {
            let sanitizedValue = pathData;
            if (typeof pathData === 'string') {
                // Remove any potential HTML entities
                sanitizedValue = pathData.trim()
                    .replace(/&quot;/g, '"')
                    .replace(/&#34;/g, '"')
                    .replace(/&#39;/g, "'")
                    .replace(/&amp;/g, '&');
                
                // Convert single quotes to double quotes if needed
                if (sanitizedValue.startsWith("'") && sanitizedValue.endsWith("'")) {
                    sanitizedValue = sanitizedValue.slice(1, -1);
                }
                sanitizedValue = sanitizedValue.replace(/'/g, '"');
                
                // Convert Python boolean values to JSON boolean values
                sanitizedValue = sanitizedValue
                    .replace(/: True/g, ': true')
                    .replace(/: False/g, ': false');
            }

            const parsedData = typeof sanitizedValue === 'string' ? JSON.parse(sanitizedValue) : sanitizedValue;
            if (Array.isArray(parsedData)) {
                CanvasField.drawingHistory = parsedData;
                CanvasField.redrawCanvas();
            }
        } catch (error) {
            console.error('Error loading path data:', error);
        }
    }
    CanvasField.setReadonly(true);
}

function closeAutoPathModal() {
    const modal = document.getElementById('autoPathModal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

function exportToCSV() {
    const headers = [
        'Event Code',
        'Match',
        'Team Number',
        'Alliance',
        'Auto Fuel',
        'Auto Climb',
        'Transition Fuel',
        'Teleop Shifts (1-4)',
        'Endgame Fuel',
        'Climb',
        'Defense Rating',
        'Robot Disabled',
        'Notes',
        'Scouter',
        'Fuel Source',
    ];

    let csvContent = headers.join(',') + '\n';

    // Get all visible rows from all event sections
    const rows = Array.from(document.querySelectorAll('.team-row')).filter(row => !row.hidden);

    rows.forEach(row => {
        const {teamNumber} = row.dataset;
        const alliance = row.cells[2].innerText.trim();
        const match = row.dataset.matchNumber || row.cells[3].innerText.trim();
        
        const autoFuel = row.cells[4].innerText.trim();
        const autoClimb = row.cells[5].innerText.trim();
        const transitionFuel = row.cells[6].innerText.trim();
        const teleopFuel = row.cells[10].innerText.trim();
        const endgameFuel = row.cells[11].innerText.trim();
        const climb = row.cells[12].innerText.trim();
        const defense = row.cells[14].innerText.trim();
        const robotDisabled = row.cells[16].innerText.trim();
        const notes = row.dataset.notes || '';
        const {scouter} = row.dataset;
        const {eventCode} = row.closest('.event-section').dataset;

        const rowData = [
            eventCode,
            match,
            teamNumber,
            alliance,
            autoFuel,
            autoClimb,
            transitionFuel,
            teleopFuel,
            endgameFuel,
            climb,
            defense,
            robotDisabled,
            notes,
            scouter,
            row.dataset.fuelSource || 'Scouted',
        ];

        csvContent += rowData.map(value => '"' + String(value ?? '').replace(/"/g, '""') + '"').join(',') + '\r\n';
    });

    // Create and trigger download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', 'scouting_data.csv');
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.addEventListener('DOMContentLoaded', function() {
    filterType = document.getElementById('filterType');
    searchInput = document.getElementById('searchInput');
    if (searchInput && filterType) {
        searchInput.addEventListener('input', () => {
            clearTimeout(filterTimer);
            listController?.abort();
            listGeneration++;
            const button = document.getElementById('loadMoreMatches');
            if (button) button.disabled = true;
            filterTimer = setTimeout(filterRows, 250);
        });
        filterType.addEventListener('change', () => { clearTimeout(filterTimer); filterRows(); });
    }

    const loadMore = document.getElementById('loadMoreMatches');
    if (loadMore) loadMore.addEventListener('click', () => {
        const reset = loadMore.dataset.retryReset === 'true';
        delete loadMore.dataset.retryReset;
        loadMatches(reset);
    });
    window.addEventListener('pagehide', () => {
        clearTimeout(filterTimer);
        listController?.abort();
    }, {once: true});

    // Add CSV export button listener
    const exportButton = document.getElementById('exportCSV');
    if (exportButton) {
        exportButton.addEventListener('click', exportToCSV);
    }

    const modal = document.getElementById('autoPathModal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeAutoPathModal();
            }
        });
    }

    // Configure Coloris
    if (typeof Coloris === 'function') Coloris({
        theme: 'polaroid',
        themeMode: 'light',
        alpha: false,
        formatToggle: false,
        swatches: [
            '#2563eb', // Default blue
            '#000000',
            '#ffffff',
            '#db4437',
            '#4285f4',
            '#0f9d58',
            '#ffeb3b',
            '#ff7f00'
        ]
    });
});