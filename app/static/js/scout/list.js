let filterType;
let searchInput;
let eventSections;

const filterRows = () => {
    const searchTerm = searchInput.value.toLowerCase();
    const type = filterType.value;

    Array.from(eventSections).forEach(section => {
        const rows = Array.from(section.querySelectorAll('.team-row'));
        
        rows.forEach(row => {
            let searchValue = '';
            switch(type) {
                case 'team':
                    searchValue = row.dataset.teamNumber;
                    break;
                case 'match':
                    searchValue = row.querySelector('td:nth-child(3)').textContent;
                    break;
                case 'scouter':
                    searchValue = row.dataset.scouter.toLowerCase();
                    break;
                // TODO: 2026
                // case 'notes':
                //     // Combine all note fields for searching
                //     searchValue = (
                //         (row.dataset.notes || '') + ' ' +
                //         (row.dataset.mobilityNotes || '') + ' ' +
                //         (row.dataset.durabilityNotes || '')
                //     ).toLowerCase();
                //     break;
            }

            row.style.display = searchValue.includes(searchTerm) ? '' : 'none';
        });

        const visibleRows = Array.from(section.querySelectorAll('.team-row')).filter(row => row.style.display !== 'none');
        section.style.display = visibleRows.length > 0 ? '' : 'none';
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

    const CanvasField = new Canvas({
        canvas: canvas,
        container: container,
        backgroundImage: '/static/images/field-2025.png', // Update: 2026 field image
        maxPanDistance: 1000
    });

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
        // TODO: 2026
        'Scouter',
    ];

    let csvContent = headers.join(',') + '\n';

    // Get all visible rows from all event sections
    const rows = Array.from(document.querySelectorAll('.team-row')).filter(row => row.style.display !== 'none');

    rows.forEach(row => {
        const {teamNumber} = row.dataset;
        const alliance = row.querySelector('td:nth-child(2) span').textContent.trim();
        const match = row.querySelector('td:nth-child(3)').textContent.trim();
        // TODO: 2026

        const {scouter} = row.dataset;
        const {eventCode} = row.closest('.event-section').dataset;

        const rowData = [
            eventCode,
            match,
            teamNumber,
            alliance,
            // TODO: 2026
            scouter,
        ];

        csvContent += rowData.join(',') + '\n';
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
}

document.addEventListener('DOMContentLoaded', function() {
    filterType = document.getElementById('filterType');
    searchInput = document.getElementById('searchInput');
    eventSections = document.querySelectorAll('.event-section');

    if (searchInput && filterType) {
        searchInput.addEventListener('input', filterRows);
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

    // Add tooltips or popovers for mobility and durability ratings
    const mobilityRatings = document.querySelectorAll('.md\\:table-cell span[title]');
    mobilityRatings.forEach(span => {
        if (span.title && span.title.trim() !== '') {
            span.classList.add('cursor-help');
        }
    });

    // Initialize Coloris
    Coloris.init();
});