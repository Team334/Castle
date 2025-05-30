const updateMatchResult = () => {
    const allianceScore = parseInt(allianceScoreInput.value) || 0;
    const opponentScore = parseInt(opponentScoreInput.value) || 0;
    
    if (allianceScore > opponentScore) {
        matchResultInput.value = 'won';
    } else if (allianceScore < opponentScore) {
        matchResultInput.value = 'lost';
    } else {
        matchResultInput.value = 'tie';
    }
};

document.addEventListener('DOMContentLoaded', function() {
    // Event code input handling
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
        CanvasField.resizeCanvas();
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
            
            const teamNumber = teamSelect.value;
            const eventCode = eventSelect.value;
            const matchNumber = matchSelect.value;
            const alliance = allianceInput.value;

            if (!teamNumber || !eventCode || !matchNumber || !alliance) {
                alert('Please fill in all required fields');
                return;
            }

            // try {
            //     const response = await fetch(`/scouting/check_team?team=${teamNumber}&event=${eventCode}&match=${matchNumber}`);
            //     const data = await response.json();
                
            //     if (data.exists) {
            //         alert(`Team ${teamNumber} already exists in match ${matchNumber} for event ${eventCode}`);
            //         return;
            //     }
                
            //     form.submit();
            // } catch (error) {
            //     console.error('Error checking team:', error);
            //     form.submit();
            // }
            form.submit();
        });
    }

    // TBA Integration
    const eventSelect = document.getElementById('event_select');
    const matchSelect = document.getElementById('match_select');
    const teamSelect = document.getElementById('team_select');
    const allianceInput = document.getElementById('alliance_color');

    // Create searchable dropdown functionality
    function createSearchableDropdown(selectElement, placeholder) {
        const wrapper = document.createElement('div');
        wrapper.className = 'relative';
        
        // Create search input
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = `Search ${placeholder}...`;
        searchInput.className = 'w-full px-4 py-2 rounded-md border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-blue-500';
        
        // Create dropdown container
        const dropdownContainer = document.createElement('div');
        dropdownContainer.className = 'absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-auto hidden';
        
        // Insert new elements
        selectElement.parentNode.insertBefore(wrapper, selectElement);
        wrapper.appendChild(searchInput);
        wrapper.appendChild(dropdownContainer);
        wrapper.appendChild(selectElement);
        selectElement.style.display = 'none';
        
        // Track options
        let options = [];
        let filteredOptions = [];
        
        // Update options list
        function updateOptions() {
            options = Array.from(selectElement.options).map(opt => ({
                value: opt.value,
                text: opt.text,
                dataset: opt.dataset,
                element: opt
            }));
            filteredOptions = [...options];
        }
        
        // Render dropdown options
        function renderDropdown() {
            dropdownContainer.innerHTML = '';
            filteredOptions.forEach((opt, index) => {
                if (opt.value === '') {
                  return;
                } // Skip placeholder option
                
                const option = document.createElement('div');
                option.className = 'px-4 py-2 cursor-pointer hover:bg-gray-100';
                option.textContent = opt.text;
                
                option.addEventListener('click', () => {
                    selectElement.value = opt.value;
                    searchInput.value = opt.text;
                    dropdownContainer.classList.add('hidden');
                    // Trigger change event
                    selectElement.dispatchEvent(new Event('change'));
                });
                
                dropdownContainer.appendChild(option);
            });
        }
        
        // Filter options based on search input
        function filterOptions(searchTerm) {
            searchTerm = searchTerm.toLowerCase();
            
            // Special handling for finals searches
            if (searchTerm.includes('final')) {
                // Check if searching for a specific finals match like "finals 1"
                const finalsMatchNumber = searchTerm.match(/finals?\s*(\d+)/i);
                
                if (finalsMatchNumber) {
                    // If looking for a specific finals match
                    const matchNumber = finalsMatchNumber[1];
                    filteredOptions = options.filter(opt => 
                        opt.text.toLowerCase().includes('finals') && 
                        !opt.text.toLowerCase().includes('semi') && 
                        opt.text.includes(matchNumber)
                    );
                    
                    if (filteredOptions.length > 0) {
                        renderDropdown();
                        return;
                    }
                }
                
                // If search contains "final" but not "semi", prioritize finals over semi-finals
                if (searchTerm.includes('final') && !searchTerm.includes('semi')) {
                    const finalsOptions = options.filter(opt => 
                        opt.text.toLowerCase().includes('finals') && 
                        !opt.text.toLowerCase().includes('semi')
                    );
                    
                    if (finalsOptions.length > 0) {
                        filteredOptions = finalsOptions;
                        renderDropdown();
                        return;
                    }
                }
            }
            
            // Normal search behavior for other terms
            filteredOptions = options.filter(opt => 
                opt.text.toLowerCase().includes(searchTerm)
            );
            renderDropdown();
        }
        
        // Event listeners
        searchInput.addEventListener('focus', () => {
            updateOptions();
            renderDropdown();
            dropdownContainer.classList.remove('hidden');
        });
        
        searchInput.addEventListener('input', (e) => {
            filterOptions(e.target.value);
            dropdownContainer.classList.remove('hidden');
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!wrapper.contains(e.target)) {
                dropdownContainer.classList.add('hidden');
            }
        });
        
        // Update input when select changes
        selectElement.addEventListener('change', () => {
            const selectedOption = selectElement.options[selectElement.selectedIndex];
            searchInput.value = selectedOption ? selectedOption.text : '';
        });
        
        return {
            updateOptions,
            clear: () => {
                searchInput.value = '';
                selectElement.value = '';
                dropdownContainer.classList.add('hidden');
            }
        };
    }

    let currentMatches = null;
    const eventMatches = JSON.parse(document.getElementById('event_matches').textContent);

    // Create searchable dropdowns
    const eventSearchable = createSearchableDropdown(eventSelect, 'Events');
    const matchSearchable = createSearchableDropdown(matchSelect, 'Matches');

    // Load events from server-side data
    const events = JSON.parse(document.getElementById('events').textContent);
    
    // Use Object.entries to maintain server-side ordering
    Object.entries(events).forEach(([name, data]) => {
        const option = document.createElement('option');
        option.value = name;  // Use event name as value for the server
        option.dataset.key = data.key;  // Store TBA key in dataset for API calls
        option.textContent = name;  // Name already includes the time indicator
        eventSelect.appendChild(option);
    });
    
    // Update event searchable options after populating
    eventSearchable.updateOptions();

    // Load matches when event is selected
    eventSelect.addEventListener('change', async function() {
        const selectedOption = this.options[this.selectedIndex];
        const selectedEventKey = selectedOption?.dataset.key;
        matchSelect.innerHTML = '<option value="">Select Match</option>';
        matchSearchable.clear();
        teamSelect.innerHTML = '<option value="">Select Team</option>';
        allianceInput.value = '';

        if (!selectedEventKey) {
            return;
        }

        try {
            // Show loading state
            matchSelect.disabled = true;
            matchSearchable.clear();

            // Fetch matches for selected event
            const response = await fetch(`/api/tba/matches/${selectedEventKey}`);
            if (!response.ok) {
                throw new Error('Failed to fetch matches');
            }

            const matches = await response.json();
            if (!matches) {
                return;
            }

            currentMatches = matches;
            matchSelect.innerHTML = '<option value="">Select Match</option>';
            
            // Group matches by competition level
            const groupedMatches = {};
            Object.entries(matches).forEach(([matchKey, match]) => {
                const level = match.comp_level;
                if (!groupedMatches[level]) {
                    groupedMatches[level] = [];
                }
                groupedMatches[level].push({ key: matchKey, ...match });
            });

            // Add matches in order: Qualification, Semi-Finals, Finals
            const levels = {
                'qm': 'Qualification',
                'sf': 'Semi-Finals',
                'f': 'Finals'
            };

            Object.entries(levels).forEach(([level, label]) => {
                if (groupedMatches[level]) {
                    const group = document.createElement('optgroup');
                    group.label = label;

                    // Sort matches within each group
                    groupedMatches[level]
                        .sort((a, b) => {
                            if (level === 'sf') {
                                // Sort by set number first, then match number
                                return (a.set_number - b.set_number) || (a.match_number - b.match_number);
                            }
                            return a.match_number - b.match_number;
                        })
                        .forEach(match => {
                            const option = document.createElement('option');
                            option.value = match.key;
                            
                            // Format display text based on match type
                            if (level === 'qm') {
                                option.textContent = `Qual ${match.match_number}`;
                            } else if (level === 'sf') {
                                option.textContent = `Semi-Finals ${match.set_number}`;
                            } else if (level === 'f') {
                                option.textContent = `Finals ${match.match_number}`;
                            }
                            
                            group.appendChild(option);
                        });

                    matchSelect.appendChild(group);
                }
            });
            
            // Update match searchable options after populating
            matchSearchable.updateOptions();
            matchSelect.disabled = false;
        } catch (error) {
            console.error('Error fetching matches:', error);
            matchSelect.innerHTML = '<option value="">Error loading matches</option>';
            matchSearchable.clear();
        }
    });

    // Load teams when match is selected
    matchSelect.addEventListener('change', function() {
        const selectedMatch = this.value;
        teamSelect.innerHTML = '<option value="">Select Team</option>';
        allianceInput.value = '';

        if (!selectedMatch || !currentMatches) {
          return;
        }

        const match = currentMatches[selectedMatch];
        if (!match) {
          return;
        }

        // Add red alliance teams
        const redGroup = document.createElement('optgroup');
        redGroup.label = 'Red Alliance';
        match.red.forEach(team => {
            const option = document.createElement('option');
            const teamNumber = team.replace('frc', '');
            option.value = teamNumber;
            option.textContent = `Team ${teamNumber}`;
            option.dataset.alliance = 'red';
            redGroup.appendChild(option);
        });
        teamSelect.appendChild(redGroup);

        // Add blue alliance teams
        const blueGroup = document.createElement('optgroup');
        blueGroup.label = 'Blue Alliance';
        match.blue.forEach(team => {
            const option = document.createElement('option');
            const teamNumber = team.replace('frc', '');
            option.value = teamNumber;
            option.textContent = `Team ${teamNumber}`;
            option.dataset.alliance = 'blue';
            blueGroup.appendChild(option);
        });
        teamSelect.appendChild(blueGroup);
    });

    // Set alliance color when team is selected
    teamSelect.addEventListener('change', function() {
        const selectedOption = this.options[this.selectedIndex];
        if (selectedOption && selectedOption.dataset.alliance) {
            allianceInput.value = selectedOption.dataset.alliance;
            
            // Optional: Add visual feedback of selected alliance
            this.classList.remove('border-red-500', 'border-blue-500');
            this.classList.add(`border-${selectedOption.dataset.alliance}-500`);
        } else {
            allianceInput.value = '';
            this.classList.remove('border-red-500', 'border-blue-500');
        }
    });

    // Tab switching functionality
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const {tab} = button.dataset;
            
            // Update button states
            tabButtons.forEach(btn => {
                btn.classList.remove('border-blue-500', 'text-blue-600');
                btn.classList.add('border-transparent', 'text-gray-500');
            });
            button.classList.remove('border-transparent', 'text-gray-500');
            button.classList.add('border-blue-500', 'text-blue-600');
            
            // Update content visibility
            tabContents.forEach(content => {
                if (content.dataset.tab === tab) {
                    content.classList.remove('hidden');
                    content.classList.add('active');
                } else {
                    content.classList.add('hidden');
                    content.classList.remove('active');
                }
            });
        });
    });
});

// Update the updateUIControls method to be more specific
function updateUIControls(color, thickness) {
    if (color) {
        // Update color picker if it exists
        const colorPicker = document.querySelector('input[name="pathColorPicker"]');
        if (colorPicker) {
            colorPicker.value = color;
            // Update Coloris
            Coloris.setInstance('#pathColorPicker', { value: color });
        }
    }

    if (thickness) {
        // Update thickness slider if it exists - be more specific with the selector
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