let filterType;
let searchInput;
let eventSections;

// Function to handle page changes for pagination
function changePage(page) {
    document.getElementById('currentPage').value = page;
    document.getElementById('filterForm').submit();
}

// Set the event code filter
function setEventCode(eventCode) {
    document.getElementById('eventCode').value = eventCode;
    document.getElementById('currentPage').value = 1; // Reset to page 1 when changing event
    document.getElementById('filterForm').submit();
}

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
        backgroundImage: '/static/images/field-2025.png',
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
    // Show loading indicator
    const exportButton = document.getElementById('exportCSV');
    const originalText = exportButton.innerHTML;
    exportButton.innerHTML = `<svg class="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg> Exporting...`;
    exportButton.disabled = true;

    // Use web worker for CSV generation to prevent UI freezing
    const worker = new Worker('/static/js/scout/export-worker.js');
    
    worker.onmessage = function(e) {
        const {csvContent, filename} = e.data;
        
        // Create and trigger download
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Reset button
        exportButton.innerHTML = originalText;
        exportButton.disabled = false;
    };
    
    // Get all relevant data
    const rows = Array.from(document.querySelectorAll('.team-row'));
    const rowData = rows.map(row => {
        return {
            teamNumber: row.dataset.teamNumber,
            alliance: row.querySelector('td:nth-child(2) span').textContent.trim(),
            match: row.querySelector('td:nth-child(3)').textContent.trim(),
            autoCoral: row.querySelector('td:nth-child(4)').textContent.trim(),
            autoAlgae: row.querySelector('td:nth-child(5)').textContent.trim(),
            teleopCoral: row.querySelector('td:nth-child(6)').textContent.trim(),
            teleopAlgae: row.querySelector('td:nth-child(7)').textContent.trim(),
            climb: row.querySelector('td:nth-child(8)').textContent.trim(),
            defense: row.querySelector('td:nth-child(10)').textContent.trim(),
            mobility: row.querySelector('td:nth-child(11) span').textContent.trim(),
            durability: row.querySelector('td:nth-child(12) span').textContent.trim(),
            notes: (row.dataset.notes || '').replace(/,/g, ';').replace(/\n/g, ' '),
            scouter: row.dataset.scouter,
            eventCode: row.closest('.event-section').dataset.eventCode
        };
    });
    
    worker.postMessage(rowData);
}

// Setup lazy loading for images
function setupLazyLoading() {
    if ('IntersectionObserver' in window) {
        const imgObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    const src = img.dataset.src;
                    if (src) {
                        img.src = src;
                        img.removeAttribute('data-src');
                    }
                    observer.unobserve(img);
                }
            });
        });

        // Find all images with data-src attribute
        document.querySelectorAll('img[data-src]').forEach(img => {
            imgObserver.observe(img);
        });
    } else {
        // Fallback for browsers without IntersectionObserver
        document.querySelectorAll('img[data-src]').forEach(img => {
            img.src = img.dataset.src;
        });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    filterType = document.getElementById('filterType');
    searchInput = document.getElementById('searchInput');
    
    // Setup event listeners for direct form submission on input change
    if (searchInput) {
        // Add debounce for search input
        let debounceTimer;
        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                document.getElementById('currentPage').value = 1; // Reset to page 1
                document.getElementById('filterForm').submit();
            }, 300); // 300ms debounce
        });
    }
    
    if (filterType) {
        filterType.addEventListener('change', function() {
            document.getElementById('currentPage').value = 1; // Reset to page 1
            document.getElementById('filterForm').submit();
        });
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

    // Setup tooltips for mobility and durability ratings
    const ratingSpans = document.querySelectorAll('span[title]');
    ratingSpans.forEach(span => {
        if (span.title && span.title.trim() !== '') {
            span.classList.add('cursor-help');
        }
    });

    // Initialize Coloris
    if (typeof Coloris !== 'undefined') {
        Coloris.init();
    }
    
    // Set up lazy loading for images
    setupLazyLoading();
});