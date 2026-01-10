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

// Add event listeners
document.querySelectorAll('[name="has_auto"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
        toggleAutoFields(e.target.value === 'true');
    });
});
