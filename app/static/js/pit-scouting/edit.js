function toggleAutoFields(enabled) {
    const fields = ['auto_routes', 'auto_preferred_start', 'auto_notes'];
    fields.forEach(field => {
        const element = document.querySelector(`[name="${field}"]`);
        if (element) {
            element.disabled = !enabled;
            if (!enabled) {
                element.value = '';
            }
        }
    });
}

function toggleScoringFields(type, enabled) {
    const notesField = document.querySelector(`[name="${type}_scoring_notes"]`);
    if (notesField) {
        notesField.disabled = !enabled;
        if (!enabled) {
            notesField.value = '';
        }
    }
}

// function toggleClimberFields(enabled) {
//     const fields = ['climber_type', 'climber_notes'];
//     fields.forEach(field => {
//         const element = document.querySelector(`[name="${field}"]`);
//         if (element) {
//             element.disabled = !enabled;
//             if (!enabled) {
//                 if (element.tagName === 'SELECT') {
//                     element.value = '';
//                 } else {
//                     element.value = '';
//                 }
//             }
//         }
//     });
// }

// Add event listeners
document.querySelectorAll('[name="has_auto"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
        toggleAutoFields(e.target.value === 'true');
    });
});

// ['coral', 'algae'].forEach(type => {
//     document.querySelectorAll(`[name="${type}_scoring_enabled"]`).forEach(radio => {
//         radio.addEventListener('change', (e) => {
//             toggleScoringFields(type, e.target.value === 'true');
//         });
//     });
// });

// document.querySelector('[name="has_climber"]').addEventListener('change', (e) => {
//     toggleClimberFields(e.target.checked);
// });

// // Initialize fields on page load
// toggleAutoFields(document.querySelector('[name="has_auto"][value="true"]').checked);
// ['coral', 'algae'].forEach(type => {
//     toggleScoringFields(type, document.querySelector(`[name="${type}_scoring_enabled"][value="true"]`).checked);
// });
// toggleClimberFields(document.querySelector('[name="has_climber"]').checked);