let alliances = [];
let availableTeams = [];
let declinedTeams = new Set();
let selectedTeams = new Set();
let currentPick = { alliance: 0, round: 1, phase: 'captain' }; // phase: 'captain' or 'pick'
let eventKey = '';
let allRankings = [];
let selectedTeamForPick = null; // For mobile: track which team is selected to pick

// Initialize
document.getElementById('year-select').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        loadEvents();
    }
});
document.getElementById('search-events-btn').addEventListener('click', loadEvents);
document.getElementById('load-rankings-btn').addEventListener('click', loadRankings);
document.getElementById('reset-btn').addEventListener('click', resetSelection);
document.getElementById('export-btn').addEventListener('click', exportResults);
document.getElementById('team-search').addEventListener('input', filterTeams);

// Load events when page loads with default year
// User can click "Search Events" to load them

function showNotification(message, type = 'info') {
    const notificationArea = document.getElementById('notification-area');

    const colors = {
        success: { bg: 'bg-green-50', text: 'text-green-800', border: 'border-green-200', icon: 'text-green-500' },
        error: { bg: 'bg-red-50', text: 'text-red-800', border: 'border-red-200', icon: 'text-red-500' },
        warning: { bg: 'bg-yellow-50', text: 'text-yellow-800', border: 'border-yellow-200', icon: 'text-yellow-500' },
        info: { bg: 'bg-blue-50', text: 'text-blue-800', border: 'border-blue-200', icon: 'text-blue-500' }
    };
    
    const color = colors[type] || colors.info;
    
    const icons = {
        success: '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>',
        error: '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>',
        warning: '<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>',
        info: '<path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>'
    };
    
    const notification = document.createElement('div');
    notification.setAttribute('role', 'alert');
    notification.className = `flex items-center p-6 rounded-lg shadow-xl ${color.bg} ${color.text} border-2 ${color.border} mb-4 animate-fade-in`;
    // Icon svg
    const iconSvg = document.createElement('svg');
    iconSvg.className = `w-6 h-6 mr-3 flex-shrink-0 ${color.icon}`;
    iconSvg.setAttribute('fill', 'currentColor');
    iconSvg.setAttribute('viewBox', '0 0 20 20');
    iconSvg.innerHTML = icons[type] || icons.info;

    // Message text
    const messageP = document.createElement('p');
    messageP.className = 'text-base font-medium flex-1';
    messageP.textContent = message;

    // Dismiss button
    const dismissButton = document.createElement('button');
    dismissButton.type = 'button';
    dismissButton.onclick = function() { this.parentElement.remove(); };
    dismissButton.className = `ml-auto -mx-1.5 -my-1.5 rounded-lg p-1.5 inline-flex h-8 w-8 ${color.icon} hover:bg-opacity-20`;

    const srSpan = document.createElement('span');
    srSpan.className = 'sr-only';
    srSpan.textContent = 'Dismiss';
    dismissButton.appendChild(srSpan);

    const buttonSvg = document.createElement('svg');
    buttonSvg.className = 'w-5 h-5';
    buttonSvg.setAttribute('fill', 'currentColor');
    buttonSvg.setAttribute('viewBox', '0 0 20 20');
    buttonSvg.innerHTML = '<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>';
    dismissButton.appendChild(buttonSvg);

    // Assemble notification
    notification.appendChild(iconSvg);
    notification.appendChild(messageP);
    notification.appendChild(dismissButton);
    
    notificationArea.appendChild(notification);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transition = 'opacity 0.5s';
        setTimeout(() => notification.remove(), 500);
    }, 5000);
}

async function loadEvents() {
    const year = document.getElementById('year-select').value;
    const eventSelect = document.getElementById('event-select');
    const searchBtn = document.getElementById('search-events-btn');
    
    if (!year || year < 1992 || year > 2025) {
        showNotification('Please enter a valid year between 1992 and 2025.', 'warning');
        eventSelect.innerHTML = '<option value="">Search for events first...</option>';
        eventSelect.disabled = true;
        return;
    }
    
    // Disable controls and show loading state
    searchBtn.disabled = true;
    searchBtn.textContent = 'Searching...';
    eventSelect.disabled = true;
    eventSelect.innerHTML = '<option value="">Loading events...</option>';
    
    try {
        const response = await fetch(`/api/tba/events?year=${year}`);
        const events = await response.json();
        
        eventSelect.innerHTML = '<option value="">Select an event / regional...</option>';
        
        if (Object.keys(events).length === 0) {
            eventSelect.innerHTML = '<option value="">No events found for this year</option>';
            showNotification(`No events found for year ${year}. Try a different year.`, 'info');
            return;
        }
        
        for (const [name, data] of Object.entries(events)) {
            const option = document.createElement('option');
            option.value = data.key;
            option.textContent = name;
            eventSelect.appendChild(option);
        }
        
        // Enable event select after loading
        eventSelect.disabled = false;
        showNotification(`Found ${Object.keys(events).length} events for ${year}`, 'success');
    } catch (error) {
        console.error('Error loading events:', error);
        eventSelect.innerHTML = '<option value="">Failed to load events</option>';
        showNotification('Failed to load events. Please try again.', 'error');
    } finally {
        searchBtn.disabled = false;
        searchBtn.textContent = 'Search Events';
    }
}

async function loadRankings() {
    eventKey = document.getElementById('event-select').value;
    
    if (!eventKey) {
        showNotification('Please select an event first.', 'warning');
        return;
    }

    const loadBtn = document.getElementById('load-rankings-btn');
    loadBtn.disabled = true;
    loadBtn.textContent = 'Loading...';

    try {
        const response = await fetch(`/api/alliance-selection/rankings/${eventKey}`);
        const rankings = await response.json();
        
        if (rankings.error) {
            showNotification(rankings.error, 'error');
            return;
        }

        allRankings = rankings;
        initializeAlliances(rankings);
        
        // Show UI elements
        document.getElementById('split-view').classList.remove('hidden');
        document.getElementById('control-buttons').classList.remove('hidden');
        document.getElementById('selection-status').classList.remove('hidden');
        
        updateStatus();
    } catch (error) {
        console.error('Error loading rankings:', error);
        showNotification('Failed to load rankings. Please try again.', 'error');
    } finally {
        loadBtn.disabled = false;
        loadBtn.textContent = 'Load Rankings';
    }
}

function initializeAlliances(rankings) {
    // Start fresh - only seed 1 is the first captain
    alliances = [];
    availableTeams = [...rankings];
    declinedTeams.clear();
    selectedTeams.clear();
    
    // Alliance 1 with seed 1 as captain
    const firstCaptain = rankings[0];
    alliances.push({
        number: 1,
        captain: firstCaptain,
        picks: []
    });
    
    selectedTeams.add(firstCaptain.team_number);
    currentPick = { alliance: 0, round: 1, phase: 'pick' }; // Start with Alliance 1's first pick

    renderAlliances();
    renderAvailableTeams();
}

// Drag and touch event handlers
let draggedTeam = null;
let touchStartPos = null;

function handleTeamClick(team) {
    // For mobile/tablet - select team first, then click on slot
    if (selectedTeamForPick && selectedTeamForPick.team_number === team.team_number) {
        // Deselect if clicking the same team
        selectedTeamForPick = null;
    } else {
        selectedTeamForPick = team;
    }
    renderAvailableTeams();
    renderAlliances();
}

function handleSlotClick(allianceIndex, pickIndex) {
    if (!selectedTeamForPick) return;
    
    const alliance = alliances[allianceIndex];
    if (!alliance || alliance.picks[pickIndex]) return; // Alliance doesn't exist or slot filled
    
    // Place the selected team
    selectTeam(selectedTeamForPick);
    selectedTeamForPick = null;
    renderAvailableTeams();
}

function handleTouchStart(e) {
    const team = JSON.parse(e.currentTarget.getAttribute('data-team'));
    touchStartPos = {
        x: e.touches[0].clientX,
        y: e.touches[0].clientY
    };
    draggedTeam = team;
    e.currentTarget.classList.add('dragging');
}

function handleTouchMove(e) {
    if (!draggedTeam) return;
    e.preventDefault(); // Prevent scrolling while dragging
}

function handleTouchEnd(e) {
    if (!draggedTeam) return;
    
    e.currentTarget.classList.remove('dragging');
    
    const touch = e.changedTouches[0];
    const dropTarget = document.elementFromPoint(touch.clientX, touch.clientY);
    
    if (dropTarget && dropTarget.classList.contains('team-slot') && dropTarget.classList.contains('empty')) {
        const allianceIndex = parseInt(dropTarget.getAttribute('data-alliance'));
        const pickIndex = parseInt(dropTarget.getAttribute('data-pick'));
        
        const alliance = alliances[allianceIndex];
        if (alliance && !alliance.picks[pickIndex]) {
            selectTeam(draggedTeam);
        }
    }
    
    draggedTeam = null;
    touchStartPos = null;
}

function handleDragStart(e) {
    draggedTeam = JSON.parse(e.target.getAttribute('data-team'));
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
    draggedTeam = null;
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    e.currentTarget.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.currentTarget.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
    
    if (!draggedTeam) return;
    
    const allianceIndex = parseInt(e.currentTarget.getAttribute('data-alliance'));
    const pickIndex = parseInt(e.currentTarget.getAttribute('data-pick'));
    
    // Check if this slot is already filled
    const alliance = alliances[allianceIndex];
    if (alliance && alliance.picks[pickIndex]) {
        return; // Slot already filled
    }
    
    // Add team to the alliance
    selectTeam(draggedTeam);
}

function renderAlliances() {
    const grid = document.getElementById('alliance-grid');
    grid.innerHTML = '';

    // Check if all picks are complete
    let totalPicks = 0;
    alliances.forEach(alliance => {
        totalPicks += alliance.picks.length;
    });
    const allPicksComplete = alliances.length >= 8 && totalPicks >= 16;

    // Always render 8 alliance slots
    for (let i = 0; i < 8; i++) {
        const alliance = alliances[i];
        const isActive = !allPicksComplete && alliance && i === currentPick.alliance;
        const card = document.createElement('div');
        card.className = `alliance-card bg-white border-2 rounded-lg p-4 ${isActive ? 'active border-blue-500' : 'border-gray-200'}`;
        
        if (!alliance) {
            // Empty alliance slot waiting for captain
            card.innerHTML = `
                <div class="flex items-center justify-between mb-3">
                    <h3 class="text-lg font-bold text-gray-400">Alliance ${i + 1}</h3>
                </div>
                <div class="team-slot empty p-3 rounded mb-3 text-center text-gray-400">
                    Waiting for captain...
                </div>
                <div class="team-slot empty p-3 rounded mb-2 text-center text-gray-400">
                    Pick 1
                </div>
                <div class="team-slot empty p-3 rounded mb-2 text-center text-gray-400">
                    Pick 2
                </div>
            `;
        } else {
            let picksHtml = '';
            const maxPicks = 2; // Each alliance gets 2 picks after captain
            
            for (let j = 0; j < maxPicks; j++) {
                const pick = alliance.picks[j];
                if (pick) {
                    picksHtml += `
                        <div class="team-slot filled p-3 rounded mb-2 cursor-pointer hover:bg-red-50 group" onclick="removeTeamFromAlliance(${i}, ${j})">
                            <div class="flex justify-between items-center">
                                <div class="flex-1">
                                    <div class="font-semibold">${pick.team_number}</div>
                                    <div class="text-xs text-gray-600">${pick.nickname || ''}</div>
                                </div>
                                <div class="flex items-center gap-2">
                                    <div class="text-xs text-gray-500">Pick ${j + 1}</div>
                                    <svg class="w-4 h-4 text-red-500 opacity-0 group-hover:opacity-100 transition-opacity" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                                    </svg>
                                </div>
                            </div>
                        </div>
                    `;
                } else {
                    picksHtml += `
                        <div class="team-slot empty p-3 rounded mb-2 text-center text-gray-400" 
                                data-alliance="${i}" 
                                data-pick="${j}"
                                onclick="handleSlotClick(${i}, ${j})"
                                ondrop="handleDrop(event)" 
                                ondragover="handleDragOver(event)"
                                ondragleave="handleDragLeave(event)">
                            ${isActive && alliance.picks.length === j ? '← Tap or drag team here' : `Pick ${j + 1}`}
                        </div>
                    `;
                }
            }

            card.innerHTML = `
                <div class="flex items-center justify-between mb-3">
                    <h3 class="text-lg font-bold">Alliance ${alliance.number}</h3>
                    ${isActive ? '<span class="pick-round-indicator">PICKING</span>' : ''}
                </div>
                <div class="team-slot captain p-3 rounded mb-3">
                    <div class="font-semibold text-blue-700">${alliance.captain.team_number}</div>
                    <div class="text-xs text-gray-600">${alliance.captain.nickname || ''}</div>
                    <div class="text-xs text-blue-600 font-medium mt-1">Captain (Rank ${alliance.captain.rank})</div>
                </div>
                ${picksHtml}
            `;
        }

        grid.appendChild(card);
    }
}

function renderAvailableTeams() {
    const list = document.getElementById('available-teams-list');
    const searchTerm = document.getElementById('team-search').value.toLowerCase();
    
    list.innerHTML = '';

    availableTeams.forEach(team => {
        const isDeclined = declinedTeams.has(team.team_number);
        const isSelected = selectedTeams.has(team.team_number);
        const isSelectedForPick = selectedTeamForPick && selectedTeamForPick.team_number === team.team_number;

        // Hide selected teams from the list entirely
        if (isSelected) return;

        const matchesSearch = !searchTerm || 
            team.team_number.toString().includes(searchTerm) ||
            (team.nickname && team.nickname.toLowerCase().includes(searchTerm));

        if (!matchesSearch) return;

        const card = document.createElement('div');
        card.className = `team-card bg-white border border-gray-200 rounded-lg p-3 ${
            isDeclined ? 'declined' : isSelectedForPick ? 'selected-for-pick' : ''
        }`;
        card.draggable = !isDeclined;
        
        if (!isDeclined) {
            card.setAttribute('data-team', JSON.stringify(team));
            card.addEventListener('dragstart', handleDragStart);
            card.addEventListener('dragend', handleDragEnd);
            card.addEventListener('click', () => handleTeamClick(team));
            
            // Touch events for mobile
            card.addEventListener('touchstart', handleTouchStart, { passive: false });
            card.addEventListener('touchmove', handleTouchMove, { passive: false });
            card.addEventListener('touchend', handleTouchEnd, { passive: false });
        }

        card.innerHTML = `
            <div class="font-semibold text-lg">${team.team_number}</div>
            <div class="text-sm text-gray-600 truncate">${team.nickname || 'No name'}</div>
            <div class="text-xs text-gray-500 mt-1">Rank: ${team.rank}</div>
            ${isDeclined ? '<div class="text-xs text-red-600 font-medium mt-1">DECLINED</div>' : ''}
            ${isSelectedForPick ? '<div class="text-xs text-blue-600 font-medium mt-1">SELECTED - Tap slot to place</div>' : ''}
        `;

        list.appendChild(card);
    });
}

let draggedTeam = null;
let touchStartPos = null;

function handleTeamClick(team) {
    // For mobile/tablet - select team first, then click on slot
    if (selectedTeamForPick && selectedTeamForPick.team_number === team.team_number) {
        // Deselect if clicking the same team
        selectedTeamForPick = null;
    } else {
        selectedTeamForPick = team;
    }
    renderAvailableTeams();
    renderAlliances();
}

function handleSlotClick(allianceIndex, pickIndex) {
    if (!selectedTeamForPick) return;
    
    const alliance = alliances[allianceIndex];
    if (!alliance || alliance.picks[pickIndex]) return; // Alliance doesn't exist or slot filled
    
    // Place the selected team
    selectTeam(selectedTeamForPick);
    selectedTeamForPick = null;
    renderAvailableTeams();
}

function handleTouchStart(e) {
    const team = JSON.parse(e.currentTarget.getAttribute('data-team'));
    touchStartPos = {
        x: e.touches[0].clientX,
        y: e.touches[0].clientY
    };
    draggedTeam = team;
    e.currentTarget.classList.add('dragging');
}

function handleTouchMove(e) {
    if (!draggedTeam) return;
    e.preventDefault(); // Prevent scrolling while dragging
}

function handleTouchEnd(e) {
    if (!draggedTeam) return;
    
    e.currentTarget.classList.remove('dragging');
    
    const touch = e.changedTouches[0];
    const dropTarget = document.elementFromPoint(touch.clientX, touch.clientY);
    
    if (dropTarget && dropTarget.classList.contains('team-slot') && dropTarget.classList.contains('empty')) {
        const allianceIndex = parseInt(dropTarget.getAttribute('data-alliance'));
        const pickIndex = parseInt(dropTarget.getAttribute('data-pick'));
        
        const alliance = alliances[allianceIndex];
        if (alliance && !alliance.picks[pickIndex]) {
            selectTeam(draggedTeam);
        }
    }
    
    draggedTeam = null;
    touchStartPos = null;
}

function handleDragStart(e) {
    draggedTeam = JSON.parse(e.target.getAttribute('data-team'));
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
    draggedTeam = null;
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    e.currentTarget.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.currentTarget.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('drag-over');
    
    if (!draggedTeam) return;
    
    const allianceIndex = parseInt(e.currentTarget.getAttribute('data-alliance'));
    const pickIndex = parseInt(e.currentTarget.getAttribute('data-pick'));
    
    // Check if this slot is already filled
    const alliance = alliances[allianceIndex];
    if (alliance && alliance.picks[pickIndex]) {
        return; // Slot already filled
    }
    
    // Add team to the alliance
    selectTeam(draggedTeam);
}

function selectTeam(team) {
    const currentAlliance = alliances[currentPick.alliance];
    
    // Add team to alliance directly
    currentAlliance.picks.push(team);
    selectedTeams.add(team.team_number);
    
    renderAlliances();
    renderAvailableTeams();
    advancePick();
}

function removeTeamFromAlliance(allianceIndex, pickIndex) {
    const alliance = alliances[allianceIndex];
    const removedTeam = alliance.picks[pickIndex];
    
    if (!removedTeam) return;
    
    // Remove from alliance
    alliance.picks.splice(pickIndex, 1);
    
    // Remove from selected teams
    selectedTeams.delete(removedTeam.team_number);
    
    // Remove from declined teams if it was there
    declinedTeams.delete(removedTeam.team_number);
    
    // Recalculate current pick position based on how many picks have been made
    recalculatePickPosition();
    
    renderAlliances();
    renderAvailableTeams();
    updateStatus();
}

function recalculatePickPosition() {
    // Count total picks made across all alliances
    let totalPicks = 0;
    alliances.forEach(alliance => {
        totalPicks += alliance.picks.length;
    });
    
    // If we haven't formed 8 alliances yet
    if (alliances.length < 8) {
        currentPick.alliance = alliances.length - 1;
        currentPick.round = 1;
        currentPick.phase = 'pick';
        return;
    }
    
    // Otherwise, figure out which alliance should be picking based on snake draft
    // Round 1: alliances 0-7 (forward)
    // Round 2: alliances 7-0 (backward)
    
    if (totalPicks < 8) {
        // Round 1 picks
        currentPick.round = 1;
        currentPick.alliance = totalPicks;
    } else {
        // Round 2 picks
        currentPick.round = 2;
        const round2Picks = totalPicks - 8;
        currentPick.alliance = 7 - round2Picks;
    }
    
    // If all picks are done, mark as complete
    if (totalPicks >= 16) {
        currentPick.round = 3; // Signals completion
    }
}

function advancePick() {
    // Check if we're still forming alliances (need 8 captains total)
    if (alliances.length < 8) {
        // Find next captain - highest ranked team that hasn't been selected or declined
        const nextCaptain = availableTeams.find(team => 
            !selectedTeams.has(team.team_number) && 
            !declinedTeams.has(team.team_number)
        );
        
        if (nextCaptain) {
            // Create new alliance with this captain
            alliances.push({
                number: alliances.length + 1,
                captain: nextCaptain,
                picks: []
            });
            selectedTeams.add(nextCaptain.team_number);
            currentPick.alliance = alliances.length - 1;
            currentPick.phase = 'pick';
            
            // Re-render to remove captain from available teams
            renderAvailableTeams();
        } else {
            showNotification('Not enough teams available to form 8 alliances. Some teams may have declined.', 'error');
            completeSelection();
            return;
        }
    } else {
        // All 8 alliances formed, now do the snake draft picks
        const maxPicks = 2; // Each alliance gets 2 picks after captain
        
        // Check if current alliance has completed their picks for this round
        const currentAlliance = alliances[currentPick.alliance];
        const picksInRound = currentAlliance.picks.filter((_, idx) => {
            if (currentPick.round === 1) return idx === 0;
            if (currentPick.round === 2) return idx === 1;
            return false;
        }).length;
        
        // Move to next alliance if current one has made their pick
        if (picksInRound > 0) {
            // Snake draft order
            if (currentPick.round % 2 === 1) {
                // Odd rounds: go forward (1, 2, 3, ... 8)
                if (currentPick.alliance < 7) {
                    currentPick.alliance++;
                } else {
                    // Reached alliance 8, move to next round
                    currentPick.round++;
                    // Don't increment alliance - stay at 7 (8th alliance) for reverse order
                }
            } else {
                // Even rounds: go backward (8, 7, 6, ... 1)
                if (currentPick.alliance > 0) {
                    currentPick.alliance--;
                } else {
                    // Reached alliance 1, move to next round
                    currentPick.round++;
                    // Don't increment alliance - stay at 0 (1st alliance) for forward order
                }
            }
        }

        // Check if selection is complete
        if (currentPick.round > maxPicks) {
            completeSelection();
            return;
        }
    }

    updateStatus();
    renderAlliances();
}

function updateStatus() {
    const statusText = document.getElementById('status-text');
    const statusBox = statusText.parentElement.parentElement;
    
    // Count total picks to determine completion
    let totalPicks = 0;
    alliances.forEach(alliance => {
        totalPicks += alliance.picks.length;
    });
    
    const allAlliancesFormed = alliances.length >= 8;
    const allPicksComplete = allAlliancesFormed && totalPicks >= 16;
    
    if (allPicksComplete || currentPick.round > 2) {
        statusText.textContent = 'Alliance selection complete!';
        statusBox.classList.remove('bg-blue-50', 'border-blue-500');
        statusBox.classList.add('bg-green-50', 'border-green-500');
        statusText.classList.remove('text-blue-800');
        statusText.classList.add('text-green-800');
    } else if (alliances.length < 8) {
        const currentAlliance = alliances[currentPick.alliance];
        statusText.textContent = `Forming alliances (${alliances.length}/8) - Alliance ${currentAlliance.number} (Captain: ${currentAlliance.captain.team_number}) is picking...`;
        statusBox.classList.remove('bg-green-50', 'border-green-500');
        statusBox.classList.add('bg-blue-50', 'border-blue-500');
        statusText.classList.remove('text-green-800');
        statusText.classList.add('text-blue-800');
    } else {
        const currentAlliance = alliances[currentPick.alliance];
        const pickNumber = currentAlliance.picks.length + 1;
        statusText.textContent = `Round ${currentPick.round}, Pick ${pickNumber} - Alliance ${currentAlliance.number} (Captain: ${currentAlliance.captain.team_number}) is picking...`;
        statusBox.classList.remove('bg-green-50', 'border-green-500');
        statusBox.classList.add('bg-blue-50', 'border-blue-500');
        statusText.classList.remove('text-green-800');
        statusText.classList.add('text-blue-800');
    }
}

function completeSelection() {
    updateStatus();
}

function resetSelection() {
    if (alliances.length === 0) {
        showNotification('No selection to reset. Please load rankings first.', 'warning');
        return;
    }
    
    initializeAlliances(allRankings);
    updateStatus();
    showNotification('Alliance selection has been reset.', 'info');
}

function exportResults() {
    if (alliances.length === 0) {
        showNotification('No alliances to export. Please complete the selection first.', 'warning');
        return;
    }
    
    const results = {
        event: eventKey,
        alliances: alliances.map(a => ({
            alliance_number: a.number,
            captain: {
                team_number: a.captain.team_number,
                nickname: a.captain.nickname,
                rank: a.captain.rank
            },
            picks: a.picks.map(p => ({
                team_number: p.team_number,
                nickname: p.nickname,
                rank: p.rank
            }))
        })),
        declined_teams: Array.from(declinedTeams)
    };

    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `alliance-selection-${eventKey}-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showNotification('Alliance selection exported successfully!', 'success');
}

function filterTeams() {
    renderAvailableTeams();
}