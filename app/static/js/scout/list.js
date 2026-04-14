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
                case 'notes':
                    // Combine all note fields for searching
                    searchValue = (
                        (row.dataset.notes || '') + ' ' +
                        (row.dataset.mobilityNotes || '') + ' ' +
                        (row.dataset.durabilityNotes || '')
                    ).toLowerCase();
                    break;
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
        backgroundImage: '/static/images/field-2026.png',
        maxPanDistance: 1000
    });

    if (pathData) {
        fetch('/scouting/api/autopath/' + pathData)
            .then(r => r.json())
            .then(data => {
                if (data.success && data.auto_path) {
                    try {
                        let parsedData = data.auto_path;
                        
                        // Handle the case where the Python backend gave us an array with a JSON string inside
                        if (Array.isArray(parsedData) && typeof parsedData[0] === 'string') {
                            parsedData = parsedData[0];
                        }
                        
                        if (typeof parsedData === 'string') {
                            // Remove any potential HTML entities
                            parsedData = parsedData.trim()
                                .replace(/&quot;/g, '"')
                                .replace(/&#34;/g, '"')
                                .replace(/&#39;/g, "'")
                                .replace(/&amp;/g, '&');

                            // Convert single quotes to double quotes if needed
                            if (parsedData.startsWith("'") && parsedData.endsWith("'")) {
                                parsedData = parsedData.slice(1, -1);
                            }
                            parsedData = parsedData.replace(/'/g, '"');

                            // Convert Python boolean values to JSON boolean values
                            parsedData = parsedData
                                .replace(/: True/g, ': true')
                                .replace(/: False/g, ': false');

                            parsedData = JSON.parse(parsedData);
                        }

                        if (typeof parsedData === 'string') {
                            parsedData = JSON.parse(parsedData);
                        }

                        if (Array.isArray(parsedData)) {
                            CanvasField.drawingHistory = parsedData;
                            CanvasField.redrawCanvas();
                        }
                    } catch (error) {
                        console.error('Error loading path data:', error);
                    }
                }
            })
            .catch(error => console.error('Error fetching path data:', error));
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
    const rows = Array.from(document.querySelectorAll('.team-row')).filter(row => row.style.display !== 'none');

    rows.forEach(row => {
        const {teamNumber} = row.dataset;
        const alliance = row.querySelector('td:nth-child(2) span').textContent.trim();
        const match = row.querySelector('td:nth-child(3)').textContent.trim();
        
        const autoFuel = row.querySelector('td:nth-child(4)').textContent.trim();
        const autoClimb = row.querySelector('td:nth-child(5)').textContent.trim();
        const transitionFuel = row.querySelector('td:nth-child(6)').textContent.trim();
        const teleopFuel = row.querySelector('td:nth-child(8)').textContent.trim();
        const endgameFuel = row.querySelector('td:nth-child(9)').textContent.trim();
        const climb = row.querySelector('td:nth-child(10)').textContent.trim();
        const defense = row.querySelector('td:nth-child(12)').textContent.trim();
        const robotDisabled = row.querySelector('td:nth-child(13) span').textContent.trim();
        const notes = (row.dataset.notes || '').replace(/,/g, ';').replace(/\n/g, ' ');
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
            `"${notes}"`,
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

    // Configure Coloris
    Coloris({
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
