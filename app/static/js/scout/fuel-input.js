// Ferried fuel is independent. Zero scored counts qualify for estimates.
function trackFuelInput(form) {
    const fields = [...form.querySelectorAll('input[name$="_fuel"]')]
        .filter(field => field.name !== 'ferried_fuel');
    const hint = document.getElementById('fuelEstimateHint');
    const automaticHint = 'When all scored-fuel counts are zero or blank, Castle uses automatic Match13 estimates when results become available. Ferried fuel is saved separately.';
    function entered() {
        const manual = fields.some(field => Number(field.value) !== 0);
        if (hint) hint.textContent = manual
            ? 'Your scored-fuel counts will be saved as entered. Automatic estimates are off while any scored count is nonzero. Ferried fuel is saved separately.'
            : automaticHint;
    }
    for (const field of fields) {
        field.addEventListener('input', entered);
        field.addEventListener('change', entered);
    }
    form.addEventListener('reset', () => {
        if (hint) hint.textContent = automaticHint;
    });
    entered();
}
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('scoutingForm');
    if (form) trackFuelInput(form);
});
