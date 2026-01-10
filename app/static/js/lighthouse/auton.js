// Constants
const API_ENDPOINT = '/api/team_paths';
const MAX_PATHS = 6;
const MAX_PER_ALLIANCE = 3;
const TEAM_COLORS = [
    '#2563eb', // blue
    '#dc2626', // red
    '#059669', // green
    '#7c3aed', // purple
    '#d97706', // amber
    '#db2777'  // pink
];

// State
let canvasField = null;
let selectedPaths = [];
let availablePaths = [];
let currentTeam = null;

// DOM Elements
document.addEventListener('DOMContentLoaded', () => {
    // Initialize elements
    const searchInput = document.getElementById('team-search');
    const searchBtn = document.getElementById('search-btn');
    const resetViewBtn = document.getElementById('reset-view-btn');
    const clearAllBtn = document.getElementById('clear-all-btn');
    const selectedPathsContainer = document.getElementById('selected-paths');
    
    // Initialize canvas
    initCanvas();
    
    // Initialize Sortable.js for drag and drop
    Sortable.create(selectedPathsContainer, {
        animation: 150,
        ghostClass: 'bg-gray-100',
        onEnd: updatePathOrder
    });
    
    // Add event listeners
    searchBtn.addEventListener('click', searchTeam);
    searchInput.addEventListener('keypress', e => {
        if (e.key === 'Enter') {
          searchTeam();
        }
    });
    resetViewBtn.addEventListener('click', () => {
        canvasField.resizeCanvas();
        canvasField.resetView();
        canvasField.redrawCanvas();
        console.log('View reset to origin');
    });
    clearAllBtn.addEventListener('click', clearAllPaths);
});

// Initialize Canvas
function initCanvas() {
    try {
        const container = document.getElementById('canvas-container');
        const canvas = document.getElementById('pathCanvas');
        
        if (!container || !canvas) {
            console.error('Canvas container or canvas element not found');
            return;
        }
        
        console.log('Initializing canvas with container:', container);
        
        // Check if Canvas.js is loaded
        if (typeof Canvas !== 'function') {
            console.error('Canvas class not found! Make sure Canvas.js is loaded properly.');
            return;
        }
        
        // Make sure the canvas is visible and has dimensions
        if (canvas.offsetWidth === 0 || canvas.offsetHeight === 0) {
            console.warn('Canvas has zero dimensions. Check CSS and layout.');
        }
        
        // Create canvas with error handling
        try {
            canvasField = new Canvas({
                canvas: canvas,
                container: container,
                backgroundImage: '/static/images/field-2026.png',
                maxPanDistance: 1000,
                // Add a simple status display function
                showStatus: (message) => {
                    console.log(`Canvas status: ${message}`);
                }
            });
            
            console.log('Canvas initialized successfully');
        } catch (initError) {
            console.error('Failed to initialize Canvas:', initError);
            alert('Failed to initialize drawing canvas. Please reload the page.');
            return;
        }
        
        // Apply initial reset to ensure proper sizing
        try {
            canvasField.resetView();
            console.log('Canvas view reset');
        } catch (resetError) {
            console.error('Error resetting canvas view:', resetError);
        }
        
        // Set to readonly mode
        try {
            canvasField.setReadonly(true);
            console.log('Canvas set to readonly mode');
        } catch (readonlyError) {
            console.error('Error setting canvas to readonly mode:', readonlyError);
        }
        
        // Handle window resize
        window.addEventListener('resize', () => {
            if (canvasField) {
                try {
                    canvasField.resizeCanvas();
                } catch (resizeError) {
                    console.error('Error resizing canvas:', resizeError);
                }
            }
        });
    } catch (error) {
        console.error('Critical error initializing canvas:', error);
        alert('Could not initialize the canvas. Please reload the page.');
    }
}

// Search for a team
async function searchTeam() {
    const teamNumber = document.getElementById('team-search').value.trim();
    const searchBtn = document.getElementById('search-btn');
    
    if (!teamNumber) {
        alert('Please enter a team number');
        return;
    }
    
    try {
        // Show loading state
        searchBtn.innerHTML = '<span class="animate-spin">↻</span>';
        
        const response = await fetch(`${API_ENDPOINT}?team=${teamNumber}`);
        
        // Check if the response is ok
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Server error (${response.status}): ${errorText}`);
        }
        
        let data;
        try {
            data = await response.json();
        } catch (jsonError) {
            throw new Error(`Failed to parse response: ${jsonError.message}`);
        }
        
        console.log('Team data:', data);
        
        // Check if data is valid
        if (!data || typeof data !== 'object') {
            throw new Error('Invalid response format from server');
        }
        
        // Update current team
        currentTeam = {
            number: data.team_number,
            info: data.team_info || {
                nickname: 'Unknown',
                city: '',
                state_prov: '',
                country: ''
            }
        };
        
        // Update available paths
        availablePaths = data.paths || [];
        
        // Update the UI
        updateTeamInfo(data);
        updateAvailablePaths();
        
    } catch (error) {
        console.error('Error searching team:', error);
        alert(`Error: ${error.message}`);
    } finally {
        // Reset button state
        searchBtn.textContent = 'Search';
    }
}

// Update team info in the UI
function updateTeamInfo(data) {
    if (!data) {
        console.error('No data provided to updateTeamInfo');
        return;
    }
    
    const searchResults = document.getElementById('search-results');
    const teamName = document.getElementById('team-name');
    const teamInfo = document.getElementById('team-info');
    
    if (!searchResults || !teamName || !teamInfo) {
        console.error('Required DOM elements not found for team info update');
        return;
    }
    
    const teamNumber = data.team_number || 'Unknown';
    const info = data.team_info || {};
    const nickname = info.nickname || 'Unknown';
    
    // Update team name and info
    teamName.textContent = `Team ${teamNumber} - ${nickname}`;
    
    const location = [
        info.city, 
        info.state_prov, 
        info.country
    ].filter(part => part && part.trim()).join(', ');
    
    teamInfo.textContent = location || 'Location unknown';
    
    // Show the results section
    searchResults.classList.remove('hidden');
}

// Update available paths in the UI
function updateAvailablePaths() {
    const availablePathsContainer = document.getElementById('available-paths');
    const pathCountAvailable = document.getElementById('path-count-available');
    const noPathsMessage = document.getElementById('no-paths-message');
    
    // Clear existing cards (not the no-paths-message)
    Array.from(availablePathsContainer.children).forEach(child => {
        if (child.id !== 'no-paths-message') {
            child.remove();
        }
    });
    
    // Update path count
    pathCountAvailable.textContent = `(${availablePaths.length})`;
    
    // Show/hide no paths message
    if (availablePaths.length === 0) {
        noPathsMessage.classList.remove('hidden');
        return;
    } else {
        noPathsMessage.classList.add('hidden');
    }
    
    // Add each path as a card
    availablePaths.forEach((path, index) => {
        const card = document.createElement('div');
        card.className = 'path-card';
        card.dataset.index = index;
        
        // Alliance color indicator border
        if (path.alliance === 'red' || path.alliance === 'blue') {
            card.classList.add(`border-l-4`);
            card.classList.add(`border-${path.alliance}-500`);
        }
        
        card.innerHTML = `
            <div class="flex justify-between items-start">
                <div>
                    <div class="font-medium">Match ${path.match_number}</div>
                    <div class="text-sm text-gray-600">${path.event_name || path.event_code}</div>
                    <div class="text-xs text-gray-500 mt-1">
                        ${path.alliance ? `<span class="px-2 py-0.5 rounded ${path.alliance === 'red' ? 'bg-red-100 text-red-800' : 'bg-blue-100 text-blue-800'} capitalize">${path.alliance}</span>` : ''}
                        ${path.auto_notes ? `<span class="ml-2">${path.auto_notes}</span>` : ''}
                    </div>
                </div>
                <button class="add-path-btn bg-blue-50 hover:bg-blue-100 text-blue-600 px-2 py-1 rounded text-xs">
                    Add
                </button>
            </div>
        `;
        
        // Add event listener
        card.querySelector('.add-path-btn').addEventListener('click', () => {
            addPathToSelection(index);
        });
        
        availablePathsContainer.appendChild(card);
    });
    
    // If we have many paths, add a scroll hint
    if (availablePaths.length > 2) {
        const scrollHint = document.createElement('div');
        scrollHint.className = 'text-xs text-gray-500 text-center mt-2';
        scrollHint.textContent = 'Scroll to see more paths';
        availablePathsContainer.appendChild(scrollHint);
    }
}

// Add a path to the selected paths
function addPathToSelection(index) {
    if (selectedPaths.length >= MAX_PATHS) {
        alert(`Cannot add more than ${MAX_PATHS} paths`);
        return;
    }
    
    const path = availablePaths[index];
    if (!path) {
      return;
    }
    
    // Check if this path is already selected
    if (selectedPaths.some(p => p.id === path._id)) {
        alert('This path is already selected');
        return;
    }
    
    // Get alliance and check limits
    const alliance = path.alliance || 'unknown';
    const allianceCount = selectedPaths.filter(p => p.alliance === alliance).length;
    
    // Check if we've reached the per-alliance limit
    if (allianceCount >= MAX_PER_ALLIANCE) {
        alert(`Cannot add more than ${MAX_PER_ALLIANCE} teams from the ${alliance} alliance`);
        return;
    }
    
    // Add to selected paths
    const colorIndex = selectedPaths.length;
    const newPath = {
        id: path._id,
        teamNumber: path.team_number,
        teamName: currentTeam?.info?.nickname || '',
        matchNumber: path.match_number,
        eventCode: path.event_code,
        alliance: alliance,
        pathData: path.auto_path,
        notes: path.auto_notes,
        color: TEAM_COLORS[colorIndex % TEAM_COLORS.length]
    };
    
    selectedPaths.push(newPath);
    
    // Update UI
    updateSelectedPaths();
    drawPaths();
}

// Update the selected paths in the UI
function updateSelectedPaths() {
    const selectedPathsContainer = document.getElementById('selected-paths');
    const emptyPrompt = document.getElementById('empty-prompt');
    const pathCount = document.getElementById('path-count');
    
    // Update path count
    pathCount.textContent = selectedPaths.length;
    
    // Show/hide empty prompt
    if (selectedPaths.length === 0) {
        emptyPrompt.classList.remove('hidden');
    } else {
        emptyPrompt.classList.add('hidden');
    }
    
    // Remove all existing path cards
    const existingCards = selectedPathsContainer.querySelectorAll('.selected-path-card');
    existingCards.forEach(card => card.remove());
    
    // Add each selected path as a card
    selectedPaths.forEach((path, index) => {
        const card = document.createElement('div');
        card.className = 'selected-path-card path-card flex items-center';
        card.dataset.id = path.id;
        
        // Add an alliance class for styling
        if (path.alliance === 'red' || path.alliance === 'blue') {
            card.classList.add(`border-l-4`);
            card.classList.add(`border-${path.alliance}-500`);
        }
        
        // Format team name display - include name in parentheses if available
        const teamDisplay = path.teamName 
            ? `Team ${path.teamNumber} (${path.teamName})` 
            : `Team ${path.teamNumber}`;
        
        card.innerHTML = `
            <span class="color-indicator" style="background-color: ${path.color};"></span>
            <div class="flex-1">
                <div class="font-medium">${teamDisplay} - Match ${path.matchNumber}</div>
                <div class="text-sm text-gray-600">
                    ${path.eventCode}
                    ${path.alliance ? 
                        `<span class="ml-2 px-2 py-0.5 text-xs rounded ${path.alliance === 'red' ? 
                            'bg-red-100 text-red-800' : 
                            path.alliance === 'blue' ? 
                                'bg-blue-100 text-blue-800' : 
                                'bg-gray-100 text-gray-800'} capitalize">${path.alliance}</span>` 
                        : ''}
                </div>
            </div>
            <span class="remove-path">&times;</span>
        `;
        
        // Add event listener for removal
        card.querySelector('.remove-path').addEventListener('click', () => {
            removePath(index);
        });
        
        selectedPathsContainer.appendChild(card);
    });
}

// Remove a path from the selection
function removePath(index) {
    if (index >= 0 && index < selectedPaths.length) {
        selectedPaths.splice(index, 1);
        updateSelectedPaths();
        drawPaths();
    }
}

// Update path order after drag and drop
function updatePathOrder(evt) {
    if (evt.oldIndex !== evt.newIndex) {
        const path = selectedPaths.splice(evt.oldIndex, 1)[0];
        selectedPaths.splice(evt.newIndex, 0, path);
        drawPaths();
    }
}

// Draw all selected paths on the canvas
function drawPaths() {
    if (!canvasField) {
        console.error('Canvas not initialized');
        return;
    }
    
    try {
        // Clear the canvas and prepare for drawing all paths
        canvasField.drawingHistory = [];
        canvasField.redrawCanvas();
        
        if (selectedPaths.length === 0) {
            console.log('No paths to draw');
            return;
        }
        
        console.log(`Drawing ${selectedPaths.length} paths`);
        
        // Prepare a combined drawing history for all paths
        let combinedDrawingHistory = [];
        
        // First collect and process all paths
        selectedPaths.forEach((path, pathIndex) => {
            try {
                // Process the path data
                let pathToDraw = path.pathData;
                
                // Skip if no path data
                if (!pathToDraw) {
                    console.warn(`No path data available for path ${pathIndex}`);
                    return;
                }
                
                // Handle string data if needed
                if (typeof pathToDraw === 'string') {
                    try {
                        // Remove any potential HTML entities
                        const sanitizedValue = pathToDraw.trim()
                            .replace(/&quot;/g, '"')
                            .replace(/&#34;/g, '"')
                            .replace(/&#39;/g, "'")
                            .replace(/&amp;/g, '&');
                        
                        // Parse the JSON data
                        pathToDraw = JSON.parse(sanitizedValue);
                    } catch (parseError) {
                        console.error(`Error parsing path data for path ${pathIndex}:`, parseError);
                        return;
                    }
                }
                
                // Ensure pathToDraw is an array
                if (!Array.isArray(pathToDraw)) {
                    console.warn(`Path data is not an array for path ${pathIndex}:`, pathToDraw);
                    return;
                }
                
                // Skip empty paths
                if (pathToDraw.length === 0) {
                    console.warn(`Path data is empty for path ${pathIndex}`);
                    return;
                }
                
                console.log(`Processing path ${pathIndex} with color ${path.color}, ${pathToDraw.length} strokes`);
                
                // Make a deep copy of the path data
                const processedPath = JSON.parse(JSON.stringify(pathToDraw));
                
                // Apply the color to each point in the path
                processedPath.forEach(stroke => {
                    if (Array.isArray(stroke)) {
                        // For freehand strokes
                        stroke.forEach(point => {
                            if (point) {
                                point.color = path.color;
                            }
                        });
                    } else if (stroke && typeof stroke === 'object') {
                        // For shapes
                        stroke.color = path.color;
                    }
                });
                
                // Add the processed path to our combined history
                combinedDrawingHistory = combinedDrawingHistory.concat(processedPath);
                
            } catch (pathError) {
                console.error(`General error processing path ${pathIndex}:`, pathError, path);
            }
        });
        
        // Now draw all paths at once
        try {
            // Temporarily set canvas to not readonly to allow drawing
            canvasField.setReadonly(false);
            
            // Set the drawing history to our combined paths
            canvasField.drawingHistory = combinedDrawingHistory;
            
            // Redraw everything
            canvasField.redrawCanvas();
            
            // Set back to readonly
            canvasField.setReadonly(true);
            
            console.log(`Successfully drew ${combinedDrawingHistory.length} strokes from ${selectedPaths.length} paths`);
        } catch (drawError) {
            console.error('Error drawing combined paths:', drawError);
        }
        
    } catch (error) {
        console.error('Critical error in drawPaths:', error);
    }
}

// Clear all selected paths
function clearAllPaths() {
    if (confirm('Are you sure you want to clear all selected paths?')) {
        selectedPaths = [];
        updateSelectedPaths();
        
        // Clear the canvas directly
        if (canvasField) {
            canvasField.drawingHistory = [];
            canvasField.redrawCanvas();
        }
    }
}
