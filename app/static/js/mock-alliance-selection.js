let alliances = [];
let availableTeams = [];
let selectedTeams = new Set();
const MAX_ALLIANCES = 8;
const MAX_PICKS_PER_ALLIANCE = 2;
let isSelectionComplete = false;
let currentPick = { alliance: 0, round: 1, phase: 'captain' }; // phase: 'captain' or 'pick'
let eventKey = '';
let allRankings = [];
let selectedTeamForPick = null; // For mobile: track which team is selected to pick
let allEventsList = []; // Store fetched events for searchable dropdown

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const yearSelect = document.getElementById('year-select');
    if (yearSelect) {
        const currentYear = new Date().getFullYear();
        yearSelect.max = currentYear;
        yearSelect.value = currentYear;
    }
    setupEventDropdown();
    loadEvents();
    
    const startBracketBtn = document.getElementById('start-bracket-btn');
    if (startBracketBtn) {
        startBracketBtn.addEventListener('click', () => {
            if (typeof startPlayoffBracket === 'function') {
                startPlayoffBracket();
            } else {
                console.error('startPlayoffBracket function not found');
                showNotification('Error: Bracket script not loaded properly.', 'error');
            }
        });
    }
});

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

function setupEventDropdown() {
    const searchInput = document.getElementById('event-search-input');
    const dropdownList = document.getElementById('event-dropdown-list');
    const dropdownArrow = document.getElementById('event-dropdown_arrow');
    const hiddenInput = document.getElementById('event-select');

    if (!searchInput || !dropdownList) return;

    // Filter list on input
    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        
        // Clear selection when user types to force them to re-select
        if (hiddenInput) hiddenInput.value = "";
        
        const filtered = allEventsList.filter(evt => evt.name.toLowerCase().includes(query));
        renderEventDropdown(filtered);
        dropdownList.classList.remove('hidden');
    });

    // Show list on focus
    searchInput.addEventListener('focus', () => {
        if (allEventsList.length > 0) {
            const query = searchInput.value.toLowerCase();
            const filtered = query ? allEventsList.filter(evt => evt.name.toLowerCase().includes(query)) : allEventsList;
            renderEventDropdown(filtered);
            dropdownList.classList.remove('hidden');
        }
    });

    // Hide list when clicking outside
    document.addEventListener('click', (e) => {
        // If clicking inside the search component, do nothing
        if (searchInput.contains(e.target) || dropdownList.contains(e.target) || (dropdownArrow && dropdownArrow.contains(e.target))) {
            return;
        }
        // Otherwise hide
        dropdownList.classList.add('hidden');
    });
    
    // Toggle list on arrow click
    if (dropdownArrow) {
        dropdownArrow.addEventListener('click', (e) => {
           e.stopPropagation(); // Prevent document click from immediately hiding it
           if (dropdownList.classList.contains('hidden')) {
               // If about to show, render full list if input is empty
               if (allEventsList.length > 0 && !searchInput.value) {
                   renderEventDropdown(allEventsList);
               }
               dropdownList.classList.remove('hidden');
               searchInput.focus();
           } else {
               dropdownList.classList.add('hidden');
           }
        });
    }
}

function renderEventDropdown(events) {
    const list = document.getElementById('event-dropdown-list');
    list.innerHTML = '';

    if (events.length === 0) {
        const div = document.createElement('div');
        div.className = 'px-4 py-2 text-sm text-gray-500';
        div.textContent = 'No events found';
        list.appendChild(div);
        return;
    }

    events.forEach(evt => {
        const li = document.createElement('li');
        li.className = 'px-4 py-2 hover:bg-blue-100 cursor-pointer text-sm text-gray-700';
        li.textContent = evt.name;
        li.addEventListener('click', () => {
            document.getElementById('event-select').value = evt.key; 
            document.getElementById('event-search-input').value = evt.name; 
            list.classList.add('hidden');
        });
        list.appendChild(li);
    });
}

async function loadEvents() {
    const year = document.getElementById('year-select').value;
    // Elements
    const searchInput = document.getElementById('event-search-input');
    const hiddenInput = document.getElementById('event-select');
    const searchBtn = document.getElementById('search-events-btn');
    
    const currentYear = new Date().getFullYear();
    // Allow up to current year + 1 just in case
    if (!year || year < 1992 || year > currentYear + 1) {
        showNotification(`Please enter a valid year between 1992 and ${currentYear}.`, 'warning');
        return;
    }

    // Disable controls and show loading state
    searchBtn.disabled = true;
    searchBtn.textContent = 'Searching...';
    
    if (searchInput) {
        searchInput.disabled = true;
        searchInput.placeholder = "Loading events...";
        searchInput.value = "";
    }
    if (hiddenInput) hiddenInput.value = "";
    
    try {
        const response = await fetch(`/api/tba/events?year=${year}&_=${new Date().getTime()}`);
        const events = await response.json();
        
        if (!response.ok || events.error) {
            throw new Error(events.error || 'Failed to fetch events');
        }
        
        allEventsList = []; // Clear current list
        
        if (Object.keys(events).length === 0) {
            if (searchInput) searchInput.placeholder = "No events found";
            showNotification(`No events found for year ${year}. Try a different year.`, 'info');
            return;
        }
        
        for (const [name, data] of Object.entries(events)) {
            allEventsList.push({ name: name, key: data.key });
        }
        
        // Sort events alphabetically
        allEventsList.sort((a, b) => a.name.localeCompare(b.name));
        
        if (searchInput) {
            searchInput.disabled = false;
            searchInput.placeholder = "Type to search events...";
        }
        
        showNotification(`Found ${allEventsList.length} events for ${year}`, 'success');
    } catch (error) {
        console.error('Error loading events:', error);
        if (searchInput) searchInput.placeholder = "Failed to load events";
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
    isSelectionComplete = false;
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
    const prevSelected = selectedTeamForPick;
    
    if (selectedTeamForPick && selectedTeamForPick.team_number === team.team_number) {
        // Deselect if clicking the same team
        selectedTeamForPick = null;
    } else {
        selectedTeamForPick = team;
    }

    // Visual Updates
    if (prevSelected) {
        const prevCard = document.getElementById(`team-card-${prevSelected.team_number}`);
        if (prevCard) {
            prevCard.classList.remove('selected-for-pick');
            const indicator = prevCard.querySelector('.selection-indicator');
            if (indicator) indicator.remove();
        }
    }

    if (selectedTeamForPick) {
        const newCard = document.getElementById(`team-card-${selectedTeamForPick.team_number}`);
        if (newCard) {
            newCard.classList.add('selected-for-pick');
            if (!newCard.querySelector('.selection-indicator')) {
                const ind = document.createElement('div');
                ind.className = 'selection-indicator text-xs text-blue-600 font-medium mt-1';
                ind.textContent = 'SELECTED - Tap slot to place';
                newCard.appendChild(ind);
            }
        }
    }
    
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
    const allPicksComplete = isSelectionComplete || (alliances.length >= MAX_ALLIANCES && totalPicks >= MAX_ALLIANCES * MAX_PICKS_PER_ALLIANCE);

    // Always render MAX_ALLIANCES alliance slots
    for (let i = 0; i < MAX_ALLIANCES; i++) {
        const alliance = alliances[i];
        const isActive = !allPicksComplete && alliance && i === currentPick.alliance;
        const card = document.createElement('div');
        card.className = `alliance-card bg-white border-2 rounded-lg p-4 ${isActive ? 'active border-blue-500' : 'border-gray-200'}`;
        
        if (!alliance) {
            // Empty alliance slot waiting for captain
            let picksPlaceholders = '';
            for (let j = 0; j < MAX_PICKS_PER_ALLIANCE; j++) {
                picksPlaceholders += `
                <div class="team-slot empty p-3 rounded mb-2 text-center text-gray-400">
                    Pick ${j + 1}
                </div>`;
            }
            
            card.innerHTML = `
                <div class="flex items-center justify-between mb-3">
                    <h3 class="text-lg font-bold text-gray-400">Alliance ${i + 1}</h3>
                </div>
                <div class="team-slot empty p-3 rounded mb-3 text-center text-gray-400">
                    Waiting for captain...
                </div>
                ${picksPlaceholders}
            `;
        } else {
            let picksHtml = '';
            
            for (let j = 0; j < MAX_PICKS_PER_ALLIANCE; j++) {
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
    
    // Optimization: Use DocumentFragment to batch DOM updates
    const fragment = document.createDocumentFragment();

    availableTeams.forEach(team => {
        const isSelected = selectedTeams.has(team.team_number);
        const isSelectedForPick = selectedTeamForPick && selectedTeamForPick.team_number === team.team_number;

        // Hide selected teams from the list entirely
        if (isSelected) return;

        const matchesSearch = !searchTerm || 
            team.team_number.toString().includes(searchTerm) ||
            (team.nickname && team.nickname.toLowerCase().includes(searchTerm));

        if (!matchesSearch) return;

        const card = document.createElement('div');
        card.id = `team-card-${team.team_number}`;
        card.className = `team-card bg-white border border-gray-200 rounded-lg p-3 ${
            isSelectedForPick ? 'selected-for-pick' : ''
        }`;
        card.draggable = true;
        
        card.setAttribute('data-team', JSON.stringify(team));
        card.addEventListener('dragstart', handleDragStart);
        card.addEventListener('dragend', handleDragEnd);
        card.addEventListener('click', () => handleTeamClick(team));
        card.addEventListener('dblclick', () => {
            if (!isSelectionComplete) selectTeam(team);
        });
        
        // Touch events for mobile
        card.addEventListener('touchstart', handleTouchStart, { passive: false });
        card.addEventListener('touchmove', handleTouchMove, { passive: false });
        card.addEventListener('touchend', handleTouchEnd, { passive: false });

        card.innerHTML = `
            <div class="font-semibold text-lg">${team.team_number}</div>
            <div class="text-sm text-gray-600 truncate">${team.nickname || 'No name'}</div>
            <div class="text-xs text-gray-500 mt-1">Rank: ${team.rank}</div>
            ${isSelectedForPick ? '<div class="selection-indicator text-xs text-blue-600 font-medium mt-1">SELECTED - Tap slot to place</div>' : ''}
        `;

        fragment.appendChild(card);
    });
    
    list.innerHTML = '';
    list.appendChild(fragment);
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
    if (alliance && alliance.picks[pickIndex]) {
        const removedTeam = alliance.picks[pickIndex];
        
        alliance.picks.splice(pickIndex, 1);
        selectedTeams.delete(removedTeam.team_number);
        
        // If we remove a 1st round pick (index 0), and subsequent alliances exist,
        // we must destroy them because the captain selection chain is invalidated.
        // This resets proper flow where picking -> creates next alliance.
        if (pickIndex === 0 && allianceIndex < alliances.length - 1) {
             for (let i = allianceIndex + 1; i < alliances.length; i++) {
                 const a = alliances[i];
                 // Remove captain from selected
                 if (a.captain) {
                    selectedTeams.delete(a.captain.team_number);
                 }
                 // Remove picks from selected
                 if (a.picks) {
                     a.picks.forEach(p => {
                         if (p) {
                             selectedTeams.delete(p.team_number);
                         }
                     });
                 }
             }
             // Truncate alliances array to remove destroyed alliances
             alliances.splice(allianceIndex + 1);
        }

        // Recalculate using state-based logic
        recalculatePickPosition();
        
        renderAlliances();
        renderAvailableTeams();
        updateStatus();
    }
}

function recalculatePickPosition() {
    isSelectionComplete = false;

    // Check Round 1 (Picks 1)
    for (let i = 0; i < alliances.length; i++) {
        // Safe check for alliance existence
        if (alliances[i] && !alliances[i].picks[0]) {
            currentPick.alliance = i;
            currentPick.round = 1;
            currentPick.phase = 'pick';
            return;
        }
    }
    
    if (alliances.length < MAX_ALLIANCES) {
        return; // Waiting for next captain creation
    }

    // Check Round 2 (Picks 2) - Reverse order
    for (let i = alliances.length - 1; i >= 0; i--) {
        if (alliances[i] && !alliances[i].picks[1]) {
            currentPick.alliance = i;
            currentPick.round = 2;
            currentPick.phase = 'pick';
            return;
        }
    }
    
    // Complete
    currentPick.round = MAX_PICKS_PER_ALLIANCE + 1;
}

function advancePick() {
    if (alliances.length < MAX_ALLIANCES) {
        handleCaptainSelection();
    } else {
        handleSnakeDraft();
    }
    updateStatus();
    renderAlliances();
}

function handleCaptainSelection() {
    const nextCaptain = availableTeams.find(team => 
        !selectedTeams.has(team.team_number)
    );
    
    if (nextCaptain) {
        alliances.push({
            number: alliances.length + 1,
            captain: nextCaptain,
            picks: []
        });
        selectedTeams.add(nextCaptain.team_number);
        currentPick.alliance = alliances.length - 1;
        currentPick.phase = 'pick';
        renderAvailableTeams();
    } else {
        showNotification('No more teams available. Selection complete.', 'info');
        completeSelection();
    }
}

function handleSnakeDraft() {
    // Check if we have teams left
    const available = availableTeams.some(t => !selectedTeams.has(t.team_number));
    if (!available) {
        completeSelection();
        return;
    }
    recalculatePickPosition();
    if (currentPick.round > MAX_PICKS_PER_ALLIANCE) {
        completeSelection();
    }
}

function updateStatus() {
    const statusText = document.getElementById('status-text');
    const statusBox = statusText.parentElement.parentElement;
    const startBracketBtn = document.getElementById('start-bracket-btn');
    
    let totalPicks = 0;
    alliances.forEach(alliance => {
        totalPicks += alliance.picks.length;
    });
    
    const allAlliancesFormed = alliances.length >= MAX_ALLIANCES;
    const allPicksComplete = allAlliancesFormed && totalPicks >= MAX_ALLIANCES * MAX_PICKS_PER_ALLIANCE;
    
    if (isSelectionComplete || allPicksComplete || currentPick.round > MAX_PICKS_PER_ALLIANCE) {
        statusText.textContent = 'Alliance selection complete!';
        statusBox.classList.remove('bg-blue-50', 'border-blue-500');
        statusBox.classList.add('bg-green-50', 'border-green-500');
        statusText.classList.remove('text-blue-800');
        statusText.classList.add('text-green-800');
        
        if (startBracketBtn) startBracketBtn.classList.remove('hidden');
    } else if (alliances.length < MAX_ALLIANCES) {
        const currentAlliance = alliances[currentPick.alliance];
        if (currentAlliance) {
             statusText.textContent = `Forming alliances (${alliances.length}/${MAX_ALLIANCES}) - Alliance ${currentAlliance.number} (Captain: ${currentAlliance.captain.team_number}) is picking...`;
        } else {
             statusText.textContent = `Processing...`;
        }
        statusBox.classList.remove('bg-green-50', 'border-green-500');
        statusBox.classList.add('bg-blue-50', 'border-blue-500');
        statusText.classList.remove('text-green-800');
        statusText.classList.add('text-blue-800');
        if (startBracketBtn) startBracketBtn.classList.add('hidden');
    } else {
        const currentAlliance = alliances[currentPick.alliance];
        if (currentAlliance) {
            const pickNumber = currentAlliance.picks.length + 1;
            statusText.textContent = `Round ${currentPick.round}, Pick ${pickNumber} - Alliance ${currentAlliance.number} (Captain: ${currentAlliance.captain.team_number}) is picking...`;
        }
        statusBox.classList.remove('bg-green-50', 'border-green-500');
        statusBox.classList.add('bg-blue-50', 'border-blue-500');
        statusText.classList.remove('text-green-800');
        statusText.classList.add('text-blue-800');
        if (startBracketBtn) startBracketBtn.classList.add('hidden');
    }
}

function completeSelection() {
    isSelectionComplete = true;
    currentPick.round = 99;
    updateStatus();
    renderAlliances();
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