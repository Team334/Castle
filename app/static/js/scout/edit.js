// Single DOMContentLoaded event handler
document.addEventListener('DOMContentLoaded', function() {
    // Auto-capitalize event code
    const eventCodeInput = document.querySelector('input[name="event_code"]');
    if (eventCodeInput) {
        eventCodeInput.addEventListener('input', function(e) {
            this.value = this.value.toUpperCase();
        });
    }

    // Initialize CanvasField helper
    const CanvasField = new Canvas({
        canvas: document.getElementById('autoPath'),
        container: document.getElementById('autoPathContainer'),
        externalUpdateUIControls: updateUIControls,
        showStatus: (message) => {
            const flashContainer = document.querySelector('.container');
            if (!flashContainer) {
              return;
            }

            const messageDiv = document.createElement('div');
            messageDiv.className = 'fixed bottom-6 left-1/2 -translate-x-1/2 sm:left-auto sm:right-6 sm:-translate-x-0 z-50 w-[90%] sm:w-full max-w-xl min-h-[60px] sm:min-h-[80px] mx-auto sm:mx-0 animate-fade-in-up';
            
            const innerDiv = document.createElement('div');
            innerDiv.className = 'flex items-center p-6 rounded-lg shadow-xl bg-green-50 text-green-800 border-2 border-green-200';
            
            const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            icon.setAttribute('class', 'w-6 h-6 mr-3 flex-shrink-0');
            icon.setAttribute('fill', 'currentColor');
            icon.setAttribute('viewBox', '0 0 20 20');
            
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('fill-rule', 'evenodd');
            path.setAttribute('d', 'M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z');
            path.setAttribute('clip-rule', 'evenodd');
            
            icon.appendChild(path);
            
            const text = document.createElement('p');
            text.className = 'text-base font-medium';
            text.textContent = message;
            
            const closeButton = document.createElement('button');
            closeButton.className = 'ml-auto -mx-1.5 -my-1.5 rounded-lg p-1.5 inline-flex h-8 w-8 text-green-500 hover:bg-green-100';
            closeButton.onclick = () => messageDiv.remove();
            
            const closeIcon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            closeIcon.setAttribute('class', 'w-5 h-5');
            closeIcon.setAttribute('fill', 'currentColor');
            closeIcon.setAttribute('viewBox', '0 0 20 20');
            
            const closePath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            closePath.setAttribute('fill-rule', 'evenodd');
            closePath.setAttribute('d', 'M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z');
            closePath.setAttribute('clip-rule', 'evenodd');
            
            closeIcon.appendChild(closePath);
            closeButton.appendChild(closeIcon);
            
            innerDiv.appendChild(icon);
            innerDiv.appendChild(text);
            innerDiv.appendChild(closeButton);
            messageDiv.appendChild(innerDiv);
            
            flashContainer.appendChild(messageDiv);
            
            setTimeout(() => {
                if (messageDiv.parentNode === flashContainer) {
                    messageDiv.remove();
                }
            }, 3000);
        },
        initialColor: '#2563eb',
        initialThickness: 3,
        maxPanDistance: 1000,
        backgroundImage: '/static/images/field-2025.png',
        readonly: false
    });

    // Verify background image loading
    const testImage = new Image();
    testImage.onload = () => {
        console.log('Background image loaded successfully');
    };
    testImage.onerror = () => {
        console.error('Failed to load background image');
        CanvasField.showStatus('Error loading field image');
    };
    testImage.src = '/static/images/field-2025.png';

    // Load existing path data if available
    const pathDataInput = document.getElementById('autoPathData');
    if (pathDataInput && pathDataInput.value) {
        try {
            let sanitizedValue = pathDataInput.value.trim();
            
            // Remove any potential HTML entities
            sanitizedValue = sanitizedValue.replace(/&quot;/g, '"')
                                         .replace(/&#34;/g, '"')
                                         .replace(/&#39;/g, "'")
                                         .replace(/&amp;/g, '&');
            
            // Check if the value is actually JSON
            if (sanitizedValue && sanitizedValue !== "None" && sanitizedValue !== "null") {
                // Try to fix common JSON formatting issues
                if (sanitizedValue.startsWith("'") && sanitizedValue.endsWith("'")) {
                    sanitizedValue = sanitizedValue.slice(1, -1);
                }
                
                // Convert single quotes to double quotes
                sanitizedValue = sanitizedValue.replace(/'/g, '"');
                
                // Convert Python boolean values to JSON boolean values
                sanitizedValue = sanitizedValue.replace(/: True/g, ': true')
                                             .replace(/: False/g, ': false');
                
                try {
                    const pathData = JSON.parse(sanitizedValue);
                    
                    if (Array.isArray(pathData)) {
                        CanvasField.drawingHistory = pathData;
                        CanvasField.redrawCanvas();
                        CanvasField.showStatus('Existing path loaded');
                    } else {
                        CanvasField.drawingHistory = [];
                        CanvasField.redrawCanvas();
                        CanvasField.showStatus('Invalid path data format');
                    }
                } catch (error) {
                    console.error('Error loading existing path:', error);
                    CanvasField.drawingHistory = [];
                    CanvasField.redrawCanvas();
                    CanvasField.showStatus('Error loading existing path');
                }
            } else {
                CanvasField.drawingHistory = [];
                CanvasField.redrawCanvas();
            }
        } catch (error) {
            console.error('Error loading existing path:', error);
            CanvasField.drawingHistory = [];
            CanvasField.redrawCanvas();
            CanvasField.showStatus('Error loading existing path');
        }
    }

    // Prevent page scrolling when using mouse wheel on canvas
    const canvas = document.getElementById('autoPath');
    canvas.addEventListener('wheel', (e) => {
        if (e.target === canvas && CanvasField.isPanning) {
            e.preventDefault();
        }
    }, { passive: false });

    // Prevent page scrolling when middle mouse button is pressed
    canvas.addEventListener('mousedown', (e) => {
        if (e.button === 1 && e.target === canvas) { // Middle mouse button
            e.preventDefault();
            CanvasField.startPanning(e);
        }
    });

    // Add mouseup handler for panning
    canvas.addEventListener('mouseup', (e) => {
        if (e.button === 1 && e.target === canvas) {
            CanvasField.stopPanning();
        }
    });

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

    // Tool buttons
    const toolButtons = {
        select: document.getElementById('selectTool'),
        pen: document.getElementById('penTool'),
        rectangle: document.getElementById('rectangleTool'),
        circle: document.getElementById('circleTool'),
        line: document.getElementById('lineTool'),
        arrow: document.getElementById('arrowTool'),
        hexagon: document.getElementById('hexagonTool'),
        star: document.getElementById('starTool')
    };

    // Function to update active tool button
    function updateActiveToolButton(activeTool) {
        Object.entries(toolButtons).forEach(([tool, button]) => {
            if (tool === activeTool) {
                button.classList.add('active');
            } else {
                button.classList.remove('active');
            }
        });
    }

    // Add tool button event listeners
    Object.entries(toolButtons).forEach(([tool, button]) => {
        button.addEventListener('click', (e) => {
            e.preventDefault(); // Prevent form submission
            CanvasField.setTool(tool);
            updateActiveToolButton(tool);
        });
    });

    // Color picker
    document.getElementById('pathColorPicker').addEventListener('change', function(e) {
        CanvasField.setColor(this.value);
    });
    
    // Thickness control
    const thicknessSlider = document.getElementById('pathThickness');
    const thicknessValue = document.getElementById('pathThicknessValue');
    
    thicknessSlider.addEventListener('input', function() {
        const {value} = this;
        thicknessValue.textContent = value;
        CanvasField.setThickness(parseInt(value));
    });

    // Fill toggle button
    const fillToggleBtn = document.getElementById('fillToggle');
    fillToggleBtn.addEventListener('click', function(e) {
        e.preventDefault(); // Prevent form submission
        const newFillState = !CanvasField.isFilled;
        CanvasField.setFill(newFillState);
        this.textContent = `Fill: ${newFillState ? 'On' : 'Off'}`;
        this.classList.toggle('bg-blue-800', newFillState);
    });

    // Function to update hidden path data
    function updatePathData() {
        const pathData = document.getElementById('autoPathData');
        if (pathData) {
            pathData.value = JSON.stringify(CanvasField.drawingHistory);
        }
    }

    // Add mouseup listener to update path data after drawing
    canvas.addEventListener('mouseup', updatePathData);
    
    // Undo button
    document.getElementById('undoPath').addEventListener('click', (e) => {
        e.preventDefault(); // Prevent form submission
        CanvasField.undo();
        updatePathData();
    });
    
    // Redo button
    document.getElementById('redoPath').addEventListener('click', (e) => {
        e.preventDefault(); // Prevent form submission
        CanvasField.redo();
        updatePathData();
    });
    
    // Clear button
    document.getElementById('clearPath').addEventListener('click', (e) => {
        e.preventDefault(); // Prevent form submission
        if (confirm('Are you sure you want to clear the path?')) {
            CanvasField.clear();
            updatePathData();
        }
    });

    // Save button
    document.getElementById('savePath').addEventListener('click', (e) => {
        e.preventDefault(); // Prevent form submission
        const jsonString = JSON.stringify(CanvasField.drawingHistory);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `autopath-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        CanvasField.showStatus('Path saved');
    });

    // Load button and file input
    const loadBtn = document.getElementById('loadPath');
    const loadFile = document.getElementById('loadFile');

    loadBtn.addEventListener('click', (e) => {
        e.preventDefault(); // Prevent form submission
        loadFile.click();
    });

    // Reset view button
    document.getElementById('goHome').addEventListener('click', (e) => {
        e.preventDefault();
        CanvasField.resetView();
        CanvasField.redrawCanvas();
        CanvasField.showStatus('View reset to origin');
    });

    // Readonly toggle button
    const readonlyToggle = document.getElementById('readonlyToggle');
    readonlyToggle.addEventListener('click', (e) => {
        e.preventDefault();
        const newState = !CanvasField.readonly;
        CanvasField.setReadonly(newState);
        readonlyToggle.classList.toggle('bg-blue-800', newState);
        readonlyToggle.classList.toggle('text-white', newState);
    });

    loadFile.addEventListener('change', (e) => {
        if (e.target.files.length === 0) {
          return;
        }

        const file = e.target.files[0];
        const reader = new FileReader();

        reader.onload = function(event) {
            try {
                const pathData = JSON.parse(event.target.result);
                CanvasField.drawingHistory = pathData;
                CanvasField.redrawCanvas();
                updatePathData();
                CanvasField.showStatus('Path loaded');
            } catch (error) {
                console.error('Error loading path:', error);
                CanvasField.showStatus('Error loading path');
            }
        };

        reader.readAsText(file);
        e.target.value = null; // Reset file input
    });

    // Add keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
          return;
        }

        if (e.ctrlKey) {
            switch (e.key.toLowerCase()) {
                case 'a':
                    e.preventDefault();
                    e.stopPropagation();
                    CanvasField.setTool('select');
                    updateActiveToolButton('select');
                    break;
                case 'p':
                    e.preventDefault();
                    e.stopPropagation();
                    CanvasField.setTool('pen');
                    updateActiveToolButton('pen');
                    break;
                case 'r':
                    e.preventDefault();
                    e.stopPropagation();
                    CanvasField.setTool('rectangle');
                    updateActiveToolButton('rectangle');
                    break;
                case 'c':
                    e.preventDefault();
                    e.stopPropagation();
                    CanvasField.setTool('circle');
                    updateActiveToolButton('circle');
                    break;
                case 'l':
                    e.preventDefault();
                    e.stopPropagation();
                    CanvasField.setTool('line');
                    updateActiveToolButton('line');
                    break;
                case 'h':
                    e.preventDefault();
                    e.stopPropagation();
                    CanvasField.setTool('hexagon');
                    updateActiveToolButton('hexagon');
                    break;
                case 'w':
                    e.preventDefault();
                    e.stopPropagation();
                    CanvasField.setTool('arrow');
                    updateActiveToolButton('arrow');
                    break;
                case 's':
                    if (!e.shiftKey) {
                        e.preventDefault();
                        e.stopPropagation();
                        CanvasField.setTool('star');
                        updateActiveToolButton('star');
                    }
                    break;
                case 'z':
                    e.preventDefault();
                    e.stopPropagation();
                    if (e.shiftKey) {
                                            CanvasField.redo();
                                        }
                    else if (!e.repeat) {  // Only trigger once when key is first pressed
                                                CanvasField.undo();
                                            }
                    updatePathData();
                    break;
                case 'y':
                    e.preventDefault();
                    e.stopPropagation();
                    CanvasField.redo();
                    updatePathData();
                    break;
                case 'f':
                    e.preventDefault();
                    e.stopPropagation();
                    fillToggleBtn.click();
                    break;
            }
        }
    });

    // Form submission handling
    const form = document.getElementById('scoutingForm');
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Update path data before submission
            updatePathData();
            
            const teamNumber = form.querySelector('input[name="team_number"]').value;
            const eventCode = form.querySelector('input[name="event_code"]').value;
            const matchNumber = form.querySelector('input[name="match_number"]').value;
            const currentId = form.querySelector('input[name="current_id"]')?.value;

            try {
                const response = await fetch(`/scouting/check_team?team=${teamNumber}&event=${eventCode}&match=${matchNumber}&current_id=${currentId}`);
                const data = await response.json();
                
                if (data.exists) {
                    alert(`Team ${teamNumber} already exists in match ${matchNumber} for event ${eventCode}`);
                    return;
                }
                
                form.submit();
            } catch (error) {
                console.error('Error checking team:', error);
                form.submit();
            }
        });
    }
});

// Add the updateUIControls function at the end of the file
function updateUIControls(color, thickness) {
    if (color) {
        // Update color picker if it exists
        const colorPicker = document.getElementById('pathColorPicker');
        if (colorPicker) {
            colorPicker.value = color;
            // Update Coloris field and button
            const clrField = colorPicker.closest('.clr-field');
            if (clrField) {
                clrField.style.color = color;
                const button = clrField.querySelector('button');
                if (button) {
                    button.style.backgroundColor = color;
                }
            }
        }
    }

    if (thickness) {
        // Update thickness slider if it exists
        const thicknessSlider = document.getElementById('pathThickness');
        const thicknessDisplay = document.getElementById('pathThicknessValue');
        if (thicknessSlider) {
            thicknessSlider.value = thickness;
            if (thicknessDisplay) {
                thicknessDisplay.textContent = thickness;
            }
        }
    }
}