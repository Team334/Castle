// A blank field means unobserved. Once touched, the whole record stays manual.
function trackFuelInput(form) {
    const fields = [...form.querySelectorAll('input[name$="_fuel"]')];
    const marker = form.elements._fuel_entered;
    const hint = document.getElementById('fuelEstimateHint');
    if (!marker) return;
    function entered() {
        marker.value = 'true';
        if (hint) hint.textContent = 'Your fuel counts will be saved as entered. Automatic estimates are off for this record.';
    }
    for (const field of fields) {
        field.addEventListener('input', entered);
        field.addEventListener('change', entered);
    }
    form.addEventListener('reset', () => {
        if (hint) hint.textContent = 'Leave every fuel count blank to use automatic Match13 estimates when results become available. Entering any fuel count, including zero, keeps all your fuel counts as entered.';
    });
}
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('scoutingForm');
    if (form) trackFuelInput(form);
});
