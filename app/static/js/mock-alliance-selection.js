// Constants
const MAX_ALLIANCES = 8;
const MAX_PICKS_PER_ALLIANCE = 2;
const NOTIFICATION_TIMEOUT = 5000;
const NOTIFICATION_FADE_DURATION = 500;
const MIN_YEAR = 1992;

// State - used to track elements and data
const state = {
    alliances: [],
    availableTeams: [],
    selectedTeams: new Set(),
    isSelectionComplete: false,
    currentPick: { alliance: 0, round: 1, phase: 'captain' },
    eventKey: '',
    allRankings: [],
    selectedTeamForPick: null,
    allEventsList: [],
    draggedTeam: null,
    touchStartPos: null
};

// Cached DOM elements
const dom = {
    yearSelect: null,
    eventSearchInput: null,
    eventDropdownList: null,
    eventDropdownArrow: null,
    eventSelect: null,
    searchEventsBtn: null,
    loadRankingsBtn: null,
    resetBtn: null,
    exportBtn: null,
    teamSearch: null,
    allianceGrid: null,
    availableTeamsList: null,
    statusText: null,
    statusBox: null,
    startBracketBtn: null,
    splitView: null,
    controlButtons: null,
    selectionStatus: null,
    notificationArea: null
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    cacheDOMElements();
    initializeYearSelect();
    setupEventDropdown();
    setupEventListeners();
    loadEvents();
});

// Cache all DOM elements
function cacheDOMElements() {
    dom.yearSelect = document.getElementById('year-select');
    dom.eventSearchInput = document.getElementById('event-search-input');
    dom.eventDropdownList = document.getElementById('event-dropdown-list');
    dom.eventDropdownArrow = document.getElementById('event-dropdown_arrow');
    dom.eventSelect = document.getElementById('event-select');
    dom.searchEventsBtn = document.getElementById('search-events-btn');
    dom.loadRankingsBtn = document.getElementById('load-rankings-btn');
    dom.resetBtn = document.getElementById('reset-btn');
    dom.exportBtn = document.getElementById('export-btn');
    dom.teamSearch = document.getElementById('team-search');
    dom.allianceGrid = document.getElementById('alliance-grid');
    dom.availableTeamsList = document.getElementById('available-teams-list');
    dom.statusText = document.getElementById('status-text');
    dom.statusBox = dom.statusText?.parentElement?.parentElement;
    dom.startBracketBtn = document.getElementById('start-bracket-btn');
    dom.splitView = document.getElementById('split-view');
    dom.controlButtons = document.getElementById('control-buttons');
    dom.selectionStatus = document.getElementById('selection-status');
    dom.notificationArea = document.getElementById('notification-area');
}

// Initialize year select with current year
function initializeYearSelect() {
    if (dom.yearSelect) {
        const currentYear = new Date().getFullYear();
        dom.yearSelect.max = currentYear;
        dom.yearSelect.value = currentYear;
    }
}

// Setup all event listeners
function setupEventListeners() {
    if (dom.yearSelect) {
        dom.yearSelect.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') loadEvents();
        });
    }
    
    if (dom.searchEventsBtn) {
        dom.searchEventsBtn.addEventListener('click', loadEvents);
    }
    
    if (dom.loadRankingsBtn) {
        dom.loadRankingsBtn.addEventListener('click', loadRankings);
    }
    
    if (dom.resetBtn) {
        dom.resetBtn.addEventListener('click', resetSelection);
    }
    
    if (dom.exportBtn) {
        dom.exportBtn.addEventListener('click', exportResults);
    }
    
    if (dom.teamSearch) {
        dom.teamSearch.addEventListener('input', filterTeams);
    }
    
    if (dom.startBracketBtn) {
        dom.startBracketBtn.addEventListener('click', handleStartBracket);
    }

    if (dom.allianceGrid) {
        dom.allianceGrid.addEventListener('click', handleGridClick);
        dom.allianceGrid.addEventListener('dragover', handleDragOver);
        dom.allianceGrid.addEventListener('dragleave', handleDragLeave);
        dom.allianceGrid.addEventListener('drop', handleDrop);
    }
}

function handleGridClick(e) {
    const slot = e.target.closest('.team-slot');
    if (!slot) return;

    const allianceIndex = parseInt(slot.getAttribute('data-alliance'));
    const pickIndex = parseInt(slot.getAttribute('data-pick'));

    if (slot.dataset.action === 'remove') {
        removeTeamFromAlliance(allianceIndex, pickIndex);
    } else if (slot.classList.contains('empty')) {
        handleSlotClick(allianceIndex, pickIndex);
    }
}

// Handle start bracket button click
function handleStartBracket() {
    if (typeof startPlayoffBracket === 'function') {
        startPlayoffBracket();
    } else {
        console.error('startPlayoffBracket function not found');
        showNotification('Error: Bracket script not loaded properly.', 'error');
    }
}

// Notification configuration
const NOTIFICATION_COLORS = {
    success: { bg: 'bg-green-50', text: 'text-green-800', border: 'border-green-200', icon: 'text-green-500' },
    error: { bg: 'bg-red-50', text: 'text-red-800', border: 'border-red-200', icon: 'text-red-500' },
    warning: { bg: 'bg-yellow-50', text: 'text-yellow-800', border: 'border-yellow-200', icon: 'text-yellow-500' },
    info: { bg: 'bg-blue-50', text: 'text-blue-800', border: 'border-blue-200', icon: 'text-blue-500' }
};

const NOTIFICATION_ICONS = {
    success: '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>',
    error: '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>',
    warning: '<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>',
    info: '<path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>'
};

function showNotification(message, type = 'info') {
    if (!dom.notificationArea) return;

    const color = NOTIFICATION_COLORS[type] || NOTIFICATION_COLORS.info;
    const notification = createNotificationElement(message, type, color);
    dom.notificationArea.appendChild(notification);
    
    // Auto-dismiss
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transition = `opacity ${NOTIFICATION_FADE_DURATION}ms`;
        setTimeout(() => notification.remove(), NOTIFICATION_FADE_DURATION);
    }, NOTIFICATION_TIMEOUT);
}

// Create notification DOM element
function createNotificationElement(message, type, color) {
    const notification = document.createElement('div');
    notification.setAttribute('role', 'alert');
    notification.className = `flex items-center p-6 rounded-lg shadow-xl ${color.bg} ${color.text} border-2 ${color.border} mb-4 animate-fade-in`;
    
    const iconSvg = createSVGElement('w-6 h-6 mr-3 flex-shrink-0 ' + color.icon, NOTIFICATION_ICONS[type] || NOTIFICATION_ICONS.info);
    const messageP = document.createElement('p');
    messageP.className = 'text-base font-medium flex-1';
    messageP.textContent = message;
    
    const dismissButton = createDismissButton(color.icon);
    dismissButton.onclick = () => notification.remove();
    
    notification.appendChild(iconSvg);
    notification.appendChild(messageP);
    notification.appendChild(dismissButton);
    
    return notification;
}

// Create SVG element
function createSVGElement(className, innerHTML) {
    const svg = document.createElement('svg');
    svg.className = className;
    svg.setAttribute('fill', 'currentColor');
    svg.setAttribute('viewBox', '0 0 20 20');
    svg.innerHTML = innerHTML;
    return svg;
}

// Create dismiss button
function createDismissButton(iconClass) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `ml-auto -mx-1.5 -my-1.5 rounded-lg p-1.5 inline-flex h-8 w-8 ${iconClass} hover:bg-opacity-20`;
    
    const srSpan = document.createElement('span');
    srSpan.className = 'sr-only';
    srSpan.textContent = 'Dismiss';
    button.appendChild(srSpan);
    
    const closeSvg = createSVGElement('w-5 h-5', '<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>');
    button.appendChild(closeSvg);
    
    return button;
}

function setupEventDropdown() {
    if (!dom.eventSearchInput || !dom.eventDropdownList) return;

    // Filter list on input
    dom.eventSearchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        
        // Clear selection when user types
        if (dom.eventSelect) dom.eventSelect.value = "";
        
        const filtered = state.allEventsList.filter(evt => 
            evt.name.toLowerCase().includes(query)
        );
        renderEventDropdown(filtered);
        dom.eventDropdownList.classList.remove('hidden');
    });

    // Show list on focus
    dom.eventSearchInput.addEventListener('focus', () => {
        if (state.allEventsList.length > 0) {
            const query = dom.eventSearchInput.value.toLowerCase();
            const filtered = query 
                ? state.allEventsList.filter(evt => evt.name.toLowerCase().includes(query)) 
                : state.allEventsList;
            renderEventDropdown(filtered);
            dom.eventDropdownList.classList.remove('hidden');
        }
    });

    // Hide list when clicking outside
    document.addEventListener('click', (e) => {
        if (!dom.eventSearchInput.contains(e.target) && 
            !dom.eventDropdownList.contains(e.target) && 
            !(dom.eventDropdownArrow && dom.eventDropdownArrow.contains(e.target))) {
            dom.eventDropdownList.classList.add('hidden');
        }
    });
    
    // Toggle list on arrow click
    if (dom.eventDropdownArrow) {
        dom.eventDropdownArrow.addEventListener('click', (e) => {
            e.stopPropagation();
            if (dom.eventDropdownList.classList.contains('hidden')) {
                if (state.allEventsList.length > 0 && !dom.eventSearchInput.value) {
                    renderEventDropdown(state.allEventsList);
                }
                dom.eventDropdownList.classList.remove('hidden');
                dom.eventSearchInput.focus();
            } else {
                dom.eventDropdownList.classList.add('hidden');
            }
        });
    }
}

function renderEventDropdown(events) {
    if (!dom.eventDropdownList) return;
    
    dom.eventDropdownList.innerHTML = '';

    if (events.length === 0) {
        const div = document.createElement('div');
        div.className = 'px-4 py-2 text-sm text-gray-500';
        div.textContent = 'No events found';
        dom.eventDropdownList.appendChild(div);
        return;
    }

    const fragment = document.createDocumentFragment();
    events.forEach(evt => {
        const li = document.createElement('li');
        li.className = 'px-4 py-2 hover:bg-blue-100 cursor-pointer text-sm text-gray-700';
        li.textContent = evt.name;
        li.addEventListener('click', () => {
            if (dom.eventSelect) dom.eventSelect.value = evt.key;
            if (dom.eventSearchInput) dom.eventSearchInput.value = evt.name;
            dom.eventDropdownList.classList.add('hidden');
        });
        fragment.appendChild(li);
    });
    
    dom.eventDropdownList.appendChild(fragment);
}

async function loadEvents() {
    if (!dom.yearSelect || !dom.searchEventsBtn) return;
    
    const year = dom.yearSelect.value;
    const currentYear = new Date().getFullYear();
    
    if (!year || year < MIN_YEAR || year > currentYear + 1) {
        showNotification(`Please enter a valid year between ${MIN_YEAR} and ${currentYear}.`, 'warning');
        return;
    }

    setLoadingState(true);
    
    try {
        const response = await fetch(`/api/tba/events?year=${year}&_=${Date.now()}`);
        const events = await response.json();
        
        if (!response.ok || events.error) {
            throw new Error(events.error || 'Failed to fetch events');
        }
        
        state.allEventsList = Object.entries(events)
            .map(([name, data]) => ({ name, key: data.key }))
            .sort((a, b) => a.name.localeCompare(b.name));
        
        if (state.allEventsList.length === 0) {
            if (dom.eventSearchInput) dom.eventSearchInput.placeholder = "No events found";
            showNotification(`No events found for year ${year}. Try a different year.`, 'info');
        } else {
            if (dom.eventSearchInput) {
                dom.eventSearchInput.disabled = false;
                dom.eventSearchInput.placeholder = "Type to search events...";
            }
            showNotification(`Found ${state.allEventsList.length} events for ${year}`, 'success');
        }
    } catch (error) {
        console.error('Error loading events:', error);
        if (dom.eventSearchInput) dom.eventSearchInput.placeholder = "Failed to load events";
        showNotification('Failed to load events. Please try again.', 'error');
    } finally {
        setLoadingState(false);
    }
}

// Set loading state for event search
function setLoadingState(isLoading) {
    if (dom.searchEventsBtn) {
        dom.searchEventsBtn.disabled = isLoading;
        dom.searchEventsBtn.textContent = isLoading ? 'Searching...' : 'Search Events';
    }
    
    if (dom.eventSearchInput) {
        dom.eventSearchInput.disabled = isLoading;
        if (isLoading) {
            dom.eventSearchInput.placeholder = "Loading events...";
            dom.eventSearchInput.value = "";
        }
    }
    
    if (dom.eventSelect && isLoading) {
        dom.eventSelect.value = "";
    }
}

async function loadRankings() {
    if (!dom.eventSelect || !dom.loadRankingsBtn) return;
    
    state.eventKey = dom.eventSelect.value;
    
    if (!state.eventKey) {
        showNotification('Please select an event first.', 'warning');
        return;
    }

    dom.loadRankingsBtn.disabled = true;
    dom.loadRankingsBtn.textContent = 'Loading...';

    try {
        const response = await fetch(`/api/alliance-selection/rankings/${state.eventKey}`);
        const rankings = await response.json();
        
        if (rankings.error) {
            showNotification(rankings.error, 'error');
            return;
        }

        state.allRankings = rankings;
        initializeAlliances(rankings);
        
        // Show UI elements
        [dom.splitView, dom.controlButtons, dom.selectionStatus].forEach(el => {
            if (el) el.classList.remove('hidden');
        });
        
        updateStatus();
    } catch (error) {
        console.error('Error loading rankings:', error);
        showNotification('Failed to load rankings. Please try again.', 'error');
    } finally {
        dom.loadRankingsBtn.disabled = false;
        dom.loadRankingsBtn.textContent = 'Load Rankings';
    }
}

function initializeAlliances(rankings) {
    // Start fresh - only seed 1 is the first captain
    state.alliances = [];
    state.availableTeams = [...rankings];
    state.isSelectionComplete = false;
    state.selectedTeams.clear();
    
    // Alliance 1 with seed 1 as captain
    const firstCaptain = rankings[0];
    state.alliances.push({
        number: 1,
        captain: firstCaptain,
        picks: []
    });
    
    state.selectedTeams.add(firstCaptain.team_number);
    state.currentPick = { alliance: 0, round: 1, phase: 'pick' };

    renderAlliances();
    renderAvailableTeams();
}

// Drag and touch event handlers
function handleTeamClick(team) {
    const prevSelected = state.selectedTeamForPick;
    
    // Toggle selection
    state.selectedTeamForPick = (prevSelected && prevSelected.team_number === team.team_number) 
        ? null 
        : team;

    // Update visual state
    updateTeamSelection(prevSelected, state.selectedTeamForPick);
    renderAlliances();
}

// Update team selection visual state
function updateTeamSelection(prevTeam, newTeam) {
    if (prevTeam) {
        const prevCard = document.getElementById(`team-card-${prevTeam.team_number}`);
        if (prevCard) {
            prevCard.classList.remove('selected-for-pick');
            prevCard.querySelector('.selection-indicator')?.remove();
        }
    }

    if (newTeam) {
        const newCard = document.getElementById(`team-card-${newTeam.team_number}`);
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
}

function handleSlotClick(allianceIndex, pickIndex) {
    if (!state.selectedTeamForPick) return;
    
    const alliance = state.alliances[allianceIndex];
    if (!alliance || alliance.picks[pickIndex]) return;
    
    selectTeam(state.selectedTeamForPick);
    state.selectedTeamForPick = null;
    renderAvailableTeams();
}

function handleTouchStart(e) {
    const team = JSON.parse(e.currentTarget.getAttribute('data-team'));
    state.touchStartPos = {
        x: e.touches[0].clientX,
        y: e.touches[0].clientY
    };
    state.draggedTeam = team;
    e.currentTarget.classList.add('dragging');
}

function handleTouchMove(e) {
    if (!state.draggedTeam) return;
    e.preventDefault();
}

function handleTouchEnd(e) {
    if (!state.draggedTeam) return;
    
    e.currentTarget.classList.remove('dragging');
    
    const touch = e.changedTouches[0];
    const dropTarget = document.elementFromPoint(touch.clientX, touch.clientY);
    
    if (dropTarget && dropTarget.classList.contains('team-slot') && dropTarget.classList.contains('empty')) {
        const allianceIndex = parseInt(dropTarget.getAttribute('data-alliance'));
        const pickIndex = parseInt(dropTarget.getAttribute('data-pick'));
        
        const alliance = state.alliances[allianceIndex];
        if (alliance && !alliance.picks[pickIndex]) {
            selectTeam(state.draggedTeam);
        }
    }
    
    state.draggedTeam = null;
    state.touchStartPos = null;
}

function handleDragStart(e) {
    state.draggedTeam = JSON.parse(e.target.getAttribute('data-team'));
    e.target.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
    state.draggedTeam = null;
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const target = e.target.closest('.team-slot');
    if (target) {
        target.classList.add('drag-over');
    }
}

function handleDragLeave(e) {
    const target = e.target.closest('.team-slot');
    if (target) {
        target.classList.remove('drag-over');
    }
}

function handleDrop(e) {
    e.preventDefault();
    const target = e.target.closest('.team-slot');
    if (target) target.classList.remove('drag-over');
    
    if (!state.draggedTeam || !target) return;
    
    const allianceIndex = parseInt(target.getAttribute('data-alliance'));
    const pickIndex = parseInt(target.getAttribute('data-pick'));
    
    const alliance = state.alliances[allianceIndex];
    if (alliance && !alliance.picks[pickIndex]) {
        selectTeam(state.draggedTeam);
    }
}

function renderAlliances() {
    if (!dom.allianceGrid) return;
    
    dom.allianceGrid.innerHTML = '';

    const allPicksComplete = areAllPicksComplete();

    // Render all alliance slots
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < MAX_ALLIANCES; i++) {
        const alliance = state.alliances[i];
        const isActive = !allPicksComplete && alliance && i === state.currentPick.alliance;
        const card = createAllianceCard(alliance, i, isActive);
        fragment.appendChild(card);
    }
    
    dom.allianceGrid.appendChild(fragment);
}

// Check if all picks are complete
function areAllPicksComplete() {
    const totalPicks = state.alliances.reduce((sum, alliance) => sum + alliance.picks.length, 0);
    return state.isSelectionComplete || 
           (state.alliances.length >= MAX_ALLIANCES && totalPicks >= MAX_ALLIANCES * MAX_PICKS_PER_ALLIANCE);
}

// Create alliance card element
function createAllianceCard(alliance, index, isActive) {
    const card = document.createElement('div');
    card.className = `alliance-card bg-white border-2 rounded-lg p-4 ${
        isActive ? 'active border-blue-500' : 'border-gray-200'
    }`;
    
    if (!alliance) {
        card.innerHTML = createEmptyAllianceHTML(index);
    } else {
        card.innerHTML = createFilledAllianceHTML(alliance, index, isActive);
    }
    
    return card;
}

// Create HTML for empty alliance slot
function createEmptyAllianceHTML(index) {
    const picksHTML = Array(MAX_PICKS_PER_ALLIANCE)
        .fill(0)
        .map((_, j) => `<div class="team-slot empty p-3 rounded mb-2 text-center text-gray-400">Pick ${j + 1}</div>`)
        .join('');
    
    return `
        <div class="flex items-center justify-between mb-3">
            <h3 class="text-lg font-bold text-gray-400">Alliance ${index + 1}</h3>
        </div>
        <div class="team-slot empty p-3 rounded mb-3 text-center text-gray-400">
            Waiting for captain...
        </div>
        ${picksHTML}
    `;
}

// Create HTML for filled alliance slot
function createFilledAllianceHTML(alliance, index, isActive) {
    const picksHTML = Array(MAX_PICKS_PER_ALLIANCE)
        .fill(0)
        .map((_, j) => {
            const pick = alliance.picks[j];
            return pick 
                ? createFilledPickHTML(pick, index, j)
                : createEmptyPickHTML(index, j, isActive && alliance.picks.length === j);
        })
        .join('');

    return `
        <div class="flex items-center justify-between mb-3">
            <h3 class="text-lg font-bold">Alliance ${alliance.number}</h3>
            ${isActive ? '<span class="pick-round-indicator">PICKING</span>' : ''}
        </div>
        <div class="team-slot captain p-3 rounded mb-3">
            <div class="font-semibold text-blue-700">${alliance.captain.team_number}</div>
            <div class="text-xs text-gray-600">${alliance.captain.nickname || ''}</div>
            <div class="text-xs text-blue-600 font-medium mt-1">Captain (Rank ${alliance.captain.rank})</div>
        </div>
        ${picksHTML}
    `;
}

// Create HTML for filled pick slot
function createFilledPickHTML(pick, allianceIndex, pickIndex) {
    return `
        <div class="team-slot filled p-3 rounded mb-2 cursor-pointer hover:bg-red-50 group" 
             data-alliance="${allianceIndex}" 
             data-pick="${pickIndex}"
             data-action="remove">
            <div class="flex justify-between items-center">
                <div class="flex-1">
                    <div class="font-semibold">${pick.team_number}</div>
                    <div class="text-xs text-gray-600">${pick.nickname || ''}</div>
                </div>
                <div class="flex items-center gap-2">
                    <div class="text-xs text-gray-500">Pick ${pickIndex + 1}</div>
                    <svg class="w-4 h-4 text-red-500 opacity-0 group-hover:opacity-100 transition-opacity" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </div>
            </div>
        </div>
    `;
}

// Create HTML for empty pick slot
function createEmptyPickHTML(allianceIndex, pickIndex, isCurrentPick) {
    return `
        <div class="team-slot empty p-3 rounded mb-2 text-center text-gray-400" 
                data-alliance="${allianceIndex}" 
                data-pick="${pickIndex}">
            ${isCurrentPick ? '← Tap or drag team here' : `Pick ${pickIndex + 1}`}
        </div>
    `;
}

function renderAvailableTeams() {
    if (!dom.availableTeamsList || !dom.teamSearch) return;
    
    const searchTerm = dom.teamSearch.value.toLowerCase();
    const fragment = document.createDocumentFragment();

    state.availableTeams.forEach(team => {
        // Skip selected teams
        if (state.selectedTeams.has(team.team_number)) return;
        
        // Filter by search term
        if (!matchesSearch(team, searchTerm)) return;

        const card = createTeamCard(team);
        fragment.appendChild(card);
    });
    
    dom.availableTeamsList.innerHTML = '';
    dom.availableTeamsList.appendChild(fragment);
}

// Check if team matches search term
function matchesSearch(team, searchTerm) {
    if (!searchTerm) return true;
    return team.team_number.toString().includes(searchTerm) ||
           (team.nickname && team.nickname.toLowerCase().includes(searchTerm));
}

// Create team card element
function createTeamCard(team) {
    const isSelectedForPick = state.selectedTeamForPick && 
                             state.selectedTeamForPick.team_number === team.team_number;

    const card = document.createElement('div');
    card.id = `team-card-${team.team_number}`;
    card.className = `team-card bg-white border border-gray-200 rounded-lg p-3 ${
        isSelectedForPick ? 'selected-for-pick' : ''
    }`;
    card.draggable = true;
    card.setAttribute('data-team', JSON.stringify(team));
    
    // Event listeners
    card.addEventListener('dragstart', handleDragStart);
    card.addEventListener('dragend', handleDragEnd);
    card.addEventListener('click', () => handleTeamClick(team));
    card.addEventListener('dblclick', () => {
        if (!state.isSelectionComplete) selectTeam(team);
    });
    card.addEventListener('touchstart', handleTouchStart, { passive: false });
    card.addEventListener('touchmove', handleTouchMove, { passive: false });
    card.addEventListener('touchend', handleTouchEnd, { passive: false });

    card.innerHTML = `
        <div class="font-semibold text-lg">${team.team_number}</div>
        <div class="text-sm text-gray-600 truncate">${team.nickname || 'No name'}</div>
        <div class="text-xs text-gray-500 mt-1">Rank: ${team.rank}</div>
        ${isSelectedForPick ? '<div class="selection-indicator text-xs text-blue-600 font-medium mt-1">SELECTED - Tap slot to place</div>' : ''}
    `;

    return card;
}

function selectTeam(team) {
    const currentAlliance = state.alliances[state.currentPick.alliance];
    if (!currentAlliance) return;
    
    currentAlliance.picks.push(team);
    state.selectedTeams.add(team.team_number);
    
    renderAlliances();
    renderAvailableTeams();
    advancePick();
}

function removeTeamFromAlliance(allianceIndex, pickIndex) {
    const alliance = state.alliances[allianceIndex];
    if (!alliance || !alliance.picks[pickIndex]) return;
    
    const removedTeam = alliance.picks[pickIndex];
    alliance.picks.splice(pickIndex, 1);
    state.selectedTeams.delete(removedTeam.team_number);
    
    // If removing first pick, destroy subsequent alliances
    if (pickIndex === 0 && allianceIndex < state.alliances.length - 1) {
        for (let i = allianceIndex + 1; i < state.alliances.length; i++) {
            const a = state.alliances[i];
            if (a.captain) state.selectedTeams.delete(a.captain.team_number);
            if (a.picks) a.picks.forEach(p => state.selectedTeams.delete(p.team_number));
        }
        state.alliances.splice(allianceIndex + 1);
    }

    recalculatePickPosition();
    renderAlliances();
    renderAvailableTeams();
    updateStatus();
}

function recalculatePickPosition() {
    state.isSelectionComplete = false;

    // Check Round 1
    for (let i = 0; i < state.alliances.length; i++) {
        if (state.alliances[i] && !state.alliances[i].picks[0]) {
            state.currentPick = { alliance: i, round: 1, phase: 'pick' };
            return;
        }
    }
    
    if (state.alliances.length < MAX_ALLIANCES) return;

    // Check Round 2 (reverse order)
    for (let i = state.alliances.length - 1; i >= 0; i--) {
        if (state.alliances[i] && !state.alliances[i].picks[1]) {
            state.currentPick = { alliance: i, round: 2, phase: 'pick' };
            return;
        }
    }
    
    state.currentPick.round = MAX_PICKS_PER_ALLIANCE + 1;
}

function advancePick() {
    if (state.alliances.length < MAX_ALLIANCES) {
        handleCaptainSelection();
    } else {
        handleSnakeDraft();
    }
    updateStatus();
    renderAlliances();
}

function handleCaptainSelection() {
    const nextCaptain = state.availableTeams.find(team => 
        !state.selectedTeams.has(team.team_number)
    );
    
    if (nextCaptain) {
        state.alliances.push({
            number: state.alliances.length + 1,
            captain: nextCaptain,
            picks: []
        });
        state.selectedTeams.add(nextCaptain.team_number);
        state.currentPick.alliance = state.alliances.length - 1;
        state.currentPick.phase = 'pick';
        renderAvailableTeams();
    } else {
        showNotification('No more teams available. Selection complete.', 'info');
        completeSelection();
    }
}

function handleSnakeDraft() {
    const available = state.availableTeams.some(t => !state.selectedTeams.has(t.team_number));
    if (!available) {
        completeSelection();
        return;
    }
    recalculatePickPosition();
    if (state.currentPick.round > MAX_PICKS_PER_ALLIANCE) {
        completeSelection();
    }
}

function updateStatus() {
    if (!dom.statusText || !dom.statusBox || !dom.startBracketBtn) return;
    
    const totalPicks = state.alliances.reduce((sum, a) => sum + a.picks.length, 0);
    const allAlliancesFormed = state.alliances.length >= MAX_ALLIANCES;
    const allPicksComplete = allAlliancesFormed && totalPicks >= MAX_ALLIANCES * MAX_PICKS_PER_ALLIANCE;
    
    if (state.isSelectionComplete || allPicksComplete || state.currentPick.round > MAX_PICKS_PER_ALLIANCE) {
        setStatusComplete();
    } else if (state.alliances.length < MAX_ALLIANCES) {
        setStatusFormingAlliances();
    } else {
        setStatusPicking();
    }
}

// Set status to complete
function setStatusComplete() {
    dom.statusText.textContent = 'Alliance selection complete!';
    dom.statusBox.classList.remove('bg-blue-50', 'border-blue-500');
    dom.statusBox.classList.add('bg-green-50', 'border-green-500');
    dom.statusText.classList.remove('text-blue-800');
    dom.statusText.classList.add('text-green-800');
    dom.startBracketBtn.classList.remove('hidden');
}

// Set status to forming alliances
function setStatusFormingAlliances() {
    const currentAlliance = state.alliances[state.currentPick.alliance];
    if (currentAlliance) {
        dom.statusText.textContent = `Forming alliances (${state.alliances.length}/${MAX_ALLIANCES}) - Alliance ${currentAlliance.number} (Captain: ${currentAlliance.captain.team_number}) is picking...`;
    } else {
        dom.statusText.textContent = 'Processing...';
    }
    dom.statusBox.classList.remove('bg-green-50', 'border-green-500');
    dom.statusBox.classList.add('bg-blue-50', 'border-blue-500');
    dom.statusText.classList.remove('text-green-800');
    dom.statusText.classList.add('text-blue-800');
    dom.startBracketBtn.classList.add('hidden');
}

// Set status to picking
function setStatusPicking() {
    const currentAlliance = state.alliances[state.currentPick.alliance];
    if (currentAlliance) {
        const pickNumber = currentAlliance.picks.length + 1;
        dom.statusText.textContent = `Round ${state.currentPick.round}, Pick ${pickNumber} - Alliance ${currentAlliance.number} (Captain: ${currentAlliance.captain.team_number}) is picking...`;
    }
    dom.statusBox.classList.remove('bg-green-50', 'border-green-500');
    dom.statusBox.classList.add('bg-blue-50', 'border-blue-500');
    dom.statusText.classList.remove('text-green-800');
    dom.statusText.classList.add('text-blue-800');
    dom.startBracketBtn.classList.add('hidden');
}

function completeSelection() {
    state.isSelectionComplete = true;
    state.currentPick.round = 99;
    updateStatus();
    renderAlliances();
}

function resetSelection() {
    if (state.alliances.length === 0) {
        showNotification('No selection to reset. Please load rankings first.', 'warning');
        return;
    }
    
    initializeAlliances(state.allRankings);
    updateStatus();
    showNotification('Alliance selection has been reset.', 'info');
}

function exportResults() {
    if (state.alliances.length === 0) {
        showNotification('No alliances to export. Please complete the selection first.', 'warning');
        return;
    }
    
    const results = {
        event: state.eventKey,
        alliances: state.alliances.map(a => ({
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
    a.download = `alliance-selection-${state.eventKey}-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showNotification('Alliance selection exported successfully!', 'success');
}

function filterTeams() {
    renderAvailableTeams();
}

// Expose state for playoff bracket script
window.getAlliances = () => state.alliances;