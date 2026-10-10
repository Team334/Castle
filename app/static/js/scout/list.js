let filterType;
let searchInput;
let eventSections;
let modalCanvas;
let filterTimer;
let searchableSections = [];

const filterRows = () => {
    const searchTerm = searchInput.value.toLowerCase();
    const type = filterType.value;

    searchableSections.forEach(({section, rows}) => {
        let visibleCount = 0;
        rows.forEach(({row, values}) => {
            const visible = (values[type] || '').includes(searchTerm);
            row.hidden = !visible;
            if (visible) visibleCount++;
        });
        section.hidden = visibleCount === 0;
    });
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
    ];

    let csvContent = headers.join(',') + '\n';

    // Get all visible rows from all event sections
    const rows = Array.from(document.querySelectorAll('.team-row')).filter(row => !row.hidden);

    rows.forEach(row => {
        const {teamNumber} = row.dataset;
        const alliance = row.cells[2].innerText.trim();
        const match = row.cells[3].innerText.trim();
        
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
    eventSections = document.querySelectorAll('.event-section');
    searchableSections = [...eventSections].map(section => ({section,
        rows: [...section.querySelectorAll('.team-row')].map(row => ({row, values: {
            team: row.dataset.teamNumber || '',
            match: row.cells[3].textContent.trim().toLowerCase(),
            scouter: (row.dataset.scouter || '').toLowerCase(),
            notes: (row.dataset.notes || '').toLowerCase(),
        }}))
    }));

    if (searchInput && filterType) {
        searchInput.addEventListener('input', () => {
            clearTimeout(filterTimer);
            filterTimer = setTimeout(filterRows, 100);
        });
        filterType.addEventListener('change', filterRows);
    }

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