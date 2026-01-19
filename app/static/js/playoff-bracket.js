// Depends on mock-alliance-selection.js state

let bracketMatches = {};

function startPlayoffBracket() {
    // Get alliances from main script
    const alliances = window.getAlliances ? window.getAlliances() : [];
    
    if (alliances.length === 0) {
        console.error('No alliances available');
        return;
    }
    
    // Hide start button
    const startBtn = document.getElementById('start-bracket-btn');
    if (startBtn) startBtn.classList.add('hidden');

    const bracketView = document.getElementById('bracket-view');
    if (bracketView) {
        bracketView.classList.remove('hidden');
        bracketView.scrollIntoView({ behavior: 'smooth' });
    }
    
    initializeBracketMatches(alliances);
    renderBracket();
}

function initializeBracketMatches(alliancesData) {
    const safeAlliances = [];
    for(let i=0; i<8; i++) {
        if(alliancesData[i]) {
            safeAlliances.push({
                seed: i+1,
                captain: alliancesData[i].captain,
                picks: alliancesData[i].picks
            });
        } else {
            // Bye team
            safeAlliances.push({
                seed: i+1,
                captain: { team_number: 'BYE', nickname: '' },
                picks: []
            });
        }
    }

    bracketMatches = {}; // Reset

    // Initial Upper Bracket (Round 1) - Standard seeding 1v8, 4v5, 2v7, 3v6
    createMatch('m1', safeAlliances[0], safeAlliances[7], 'Upper Round 1'); // 1 vs 8
    createMatch('m2', safeAlliances[3], safeAlliances[4], 'Upper Round 1'); // 4 vs 5
    createMatch('m3', safeAlliances[1], safeAlliances[6], 'Upper Round 1'); // 2 vs 7
    createMatch('m4', safeAlliances[2], safeAlliances[5], 'Upper Round 1'); // 3 vs 6
    
    // Initialize others
    ['m5', 'm6', 'm7', 'm8', 'm9', 'm10', 'm11', 'm12', 'm13'].forEach(id => {
        bracketMatches[id] = {
            id: id,
            red: null,
            blue: null,
            winner: null,
            label: getMatchLabel(id)
        };
    });
}

function createMatch(id, redAlliance, blueAlliance, label) {
    bracketMatches[id] = {
        id: id,
        red: redAlliance,
        blue: blueAlliance,
        winner: null, 
        label: label
    };
}

function getMatchLabel(id) {
    const labels = {
        m5: 'Lower Round 1', m6: 'Lower Round 1',
        m7: 'Upper Round 2', m8: 'Upper Round 2',
        m9: 'Lower Round 2', m10: 'Lower Round 2',
        m11: 'Upper Semi-Final',
        m12: 'Lower Round 3',
        m13: 'Lower Final'
    };
    return labels[id] || 'Match ' + id.replace('m', '');
}

function renderBracket() {
    // Upper Round 1
    renderMatch('m1', 'upper-round-1');
    renderMatch('m2', 'upper-round-1');
    renderMatch('m3', 'upper-round-1');
    renderMatch('m4', 'upper-round-1');
    
    // Lower Round 1
    renderMatch('m5', 'lower-round-1');
    renderMatch('m6', 'lower-round-1');
    
    // Upper Round 2
    renderMatch('m7', 'upper-round-2');
    renderMatch('m8', 'upper-round-2');
    
    // Lower Round 2
    renderMatch('m9', 'lower-round-2');
    renderMatch('m10', 'lower-round-2');
    
    // Upper Round 3
    renderMatch('m11', 'upper-round-3');
    
    // Lower Round 3
    renderMatch('m12', 'lower-round-3');
    
    // Lower Final
    renderMatch('m13', 'lower-round-4');
    
    // Finals
    if (!bracketMatches['m14']) {
        bracketMatches['m14'] = { id: 'm14', red: null, blue: null, winner: null, label: 'Finals 1' };
    }
    renderMatch('m14', 'finals-round');
}

function renderMatch(matchId, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    // Check if we already rendered this match
    let matchEl = document.getElementById(`match-${matchId}`);
    const match = bracketMatches[matchId];
    
    if (!matchEl) {
        const template = document.getElementById('match-card-template');
        if (!template) return;
        
        matchEl = template.content.cloneNode(true).querySelector('.match-card');
        matchEl.id = `match-${matchId}`;
        
        // Add click handlers: User decides winner
        matchEl.querySelector('.alliance-option.red').addEventListener('click', () => setMatchWinner(matchId, 'red'));
        matchEl.querySelector('.alliance-option.blue').addEventListener('click', () => setMatchWinner(matchId, 'blue'));
        
        container.appendChild(matchEl);
    } 
    
    // Update labels
    const labelEl = matchEl.querySelector('.match-label');
    if(labelEl) labelEl.textContent = match.label;

    const idEl = matchEl.querySelector('.match-id');
    if(idEl) idEl.textContent = matchId.toUpperCase();
    
    const redEl = matchEl.querySelector('.alliance-option.red');
    const blueEl = matchEl.querySelector('.alliance-option.blue');
    
    updateAllianceOption(redEl, match.red, match.winner === 'red', match.winner === 'blue');
    updateAllianceOption(blueEl, match.blue, match.winner === 'blue', match.winner === 'red');
}

function updateAllianceOption(el, allianceData, isWinner, isLoser) {
    const teamEl = el.querySelector('.team-number');
    const seedEl = el.querySelector('.seed-badge');
    const winnerIcon = el.querySelector('.winner-icon');

    el.classList.remove('bg-green-50', 'bg-gray-100', 'opacity-50', 'grayscale', 'border-green-500', 'cursor-not-allowed', 'bg-gray-50');
    el.classList.add('cursor-pointer'); // Default back to pointer

    // Reset icon
    if (winnerIcon) {
        winnerIcon.classList.remove('opacity-100', 'scale-100');
        winnerIcon.classList.add('opacity-0', 'scale-0');
    }

    if (allianceData) {
        teamEl.textContent = allianceData.captain.team_number;
        seedEl.textContent = allianceData.seed;

        if (isWinner) {
            el.classList.add('bg-green-50', 'border-green-500');
            if (winnerIcon) {
                winnerIcon.classList.remove('opacity-0', 'scale-0');
                winnerIcon.classList.add('opacity-100', 'scale-100');
            }
        } else if (isLoser) {
            el.classList.add('bg-gray-100', 'opacity-50', 'grayscale');
        }
    } else {
        teamEl.textContent = 'TBD';
        seedEl.textContent = '?';
        el.classList.remove('cursor-pointer');
        el.classList.add('cursor-not-allowed', 'bg-gray-50');
    }
}

function setMatchWinner(matchId, winnerColor) {
    const match = bracketMatches[matchId];
    if (!match.red || !match.blue) return; 
    
    // If BYE, we can't really "click" it typically, but if we do, logic handles it.
    // In strict auto-mode, BYEs advance immediately. Here user clicks.
    
    if (match.winner === winnerColor) {
        match.winner = null; // Toggle off
    } else {
        match.winner = winnerColor;
    }
    
    propagateBracket(matchId);
    renderBracket();
}

function propagateBracket(sourceMatchId) {
    const source = bracketMatches[sourceMatchId];
    const winner = source.winner ? (source.winner === 'red' ? source.red : source.blue) : null;
    const loser = source.winner ? (source.winner === 'red' ? source.blue : source.red) : null;
    
    // Double Elimination Bracket Mapping (2023+ FRC)
    const flow = {
        // Round 1 Upper
        'm1': { win: { to: 'm8', role: 'red' }, lose: { to: 'm5', role: 'red' } },
        'm2': { win: { to: 'm8', role: 'blue' }, lose: { to: 'm5', role: 'blue' } },
        'm3': { win: { to: 'm7', role: 'red' }, lose: { to: 'm6', role: 'red' } },
        'm4': { win: { to: 'm7', role: 'blue' }, lose: { to: 'm6', role: 'blue' } },
        
        // Round 1 Lower
        'm5': { win: { to: 'm10', role: 'blue' } }, // W5 plays L8
        'm6': { win: { to: 'm9', role: 'blue' } },  // W6 plays L7
        
        // Round 2 Upper
        'm7': { win: { to: 'm11', role: 'red' }, lose: { to: 'm9', role: 'red' } },
        'm8': { win: { to: 'm11', role: 'blue' }, lose: { to: 'm10', role: 'red' } },
        
        // Round 2 Lower
        'm9': { win: { to: 'm12', role: 'red' } },
        'm10': { win: { to: 'm12', role: 'blue' } },
        
        // Round 3 Upper (Semis)
        'm11': { win: { to: 'm14', role: 'red' }, lose: { to: 'm13', role: 'red' } }, 
        
        // Round 3 Lower
        'm12': { win: { to: 'm13', role: 'blue' } },
        
        // Lower Final
        'm13': { win: { to: 'm14', role: 'blue' } } 
    };
    
    const next = flow[sourceMatchId];
    if (!next) return;
    
    if (next.win) updateMatchSlot(next.win.to, next.win.role, winner);
    if (next.lose) updateMatchSlot(next.lose.to, next.lose.role, loser);
}

function updateMatchSlot(matchId, role, teamData) {
    const match = bracketMatches[matchId];
    if (!match) return;
    
    const currentJson = JSON.stringify(match[role]);
    const newJson = JSON.stringify(teamData);
    
    if (currentJson !== newJson) {
        match[role] = teamData;
        match.winner = null; // Reset result if input changes
        propagateBracket(matchId); // Clear downstream
    }
}

// Allow bracket matches for export functionality
window.getBracketMatches = () => bracketMatches;

function exportPlayoffResults() {
    if (!bracketMatches || Object.keys(bracketMatches).length === 0) {
        alert('No playoff matches to export. Please start the playoffs first.');
        return;
    }

    // Get event key and alliances from main script
    const eventKey = window.getAlliances ? (window.getAlliances()[0]?.captain ? 
        document.getElementById('event-select')?.value || 'unknown' : 'unknown') : 'unknown';
    
    const results = {
        event: eventKey,
        timestamp: new Date().toISOString(),
        playoff_matches: Object.entries(bracketMatches).map(([matchId, match]) => ({
            match_id: matchId,
            label: match.label,
            red_alliance: match.red ? {
                seed: match.red.seed,
                captain: match.red.captain.team_number,
                picks: match.red.picks.map(p => p.team_number)
            } : null,
            blue_alliance: match.blue ? {
                seed: match.blue.seed,
                captain: match.blue.captain.team_number,
                picks: match.blue.picks.map(p => p.team_number)
            } : null,
            winner: match.winner,
            winner_alliance: match.winner && match[match.winner] ? {
                seed: match[match.winner].seed,
                captain: match[match.winner].captain.team_number
            } : null
        }))
    };

    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `playoff-results-${eventKey}-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    // Show notification if available
    if (typeof showNotification === 'function') {
        showNotification('Playoff results exported successfully!', 'success');
    } else {
        alert('Playoff results exported successfully!');
    }
}
