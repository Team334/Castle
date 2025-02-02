document.addEventListener('DOMContentLoaded', function() {
    // Auto-capitalize event code
    const eventCodeInput = document.querySelector('input[name="event_code"]');
    eventCodeInput.addEventListener('input', function(e) {
        this.value = this.value.toUpperCase();
    });

    // Calculate total points in real-time
    const updateTotal = () => {
        const coralPoints = [1, 2, 3, 4].reduce((sum, level) => {
            return sum + (parseInt(document.querySelector(`input[name="coral_level${level}"]`).value) || 0) * level;
        }, 0);
        
        const algaeNet = (parseInt(document.querySelector('input[name="algae_net"]').value) || 0) * 2;
        const algaeProcessor = (parseInt(document.querySelector('input[name="algae_processor"]').value) || 0) * 3;
        const humanPlayerPoints = (parseInt(document.querySelector('input[name="human_player"]').value) || 0) * 2;
        
        const climbType = document.querySelector('select[name="climb_type"]').value;
        const climbSuccess = document.querySelector('input[name="climb_success"]').checked;
        let climbPoints = 0;
        if (climbSuccess) {
            switch(climbType) {
                case 'shallow': climbPoints = 3; break;
                case 'deep': climbPoints = 5; break;
                case 'park': climbPoints = 1; break;
            }
        }
        
        const total = coralPoints + algaeNet + algaeProcessor + humanPlayerPoints + climbPoints;
        document.getElementById('totalPoints').textContent = total;
    };

    // Add event listeners for all scoring inputs
    document.querySelectorAll('input[type="number"], input[type="checkbox"], select[name="climb_type"]')
        .forEach(input => input.addEventListener('input', updateTotal));

    // Initialize total
    updateTotal();

    // Add form submission handler with team check
    const form = document.getElementById('scoutingForm');
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const teamNumber = form.querySelector('input[name="team_number"]').value;
        const eventCode = form.querySelector('input[name="event_code"]').value;
        const matchNumber = form.querySelector('input[name="match_number"]').value;
        const currentId = '{{ team_data._id }}';

        // Check if team already exists in this match (excluding current entry)
        try {
            const response = await fetch(`/scouting/check_team?team=${teamNumber}&event=${eventCode}&match=${matchNumber}&current_id=${currentId}`);
            const data = await response.json();
            
            if (data.exists) {
                alert(`Team ${teamNumber} already exists in match ${matchNumber} for event ${eventCode}`);
                return;
            }
            
            // If team doesn't exist or it's the same entry, submit the form
            form.submit();
        } catch (error) {
            console.error('Error checking team:', error);
            // If check fails, allow form submission
            form.submit();
        }
    });
});

const canvas = document.getElementById('autoPath');
const ctx = canvas.getContext('2d');
let isDrawing = false;
let lastX = 0;
let lastY = 0;
let bgImage = null;
let pathHistory = [];
let currentPath = [];

function resizeCanvas() {
    const container = canvas.parentElement;
    const containerWidth = container.clientWidth;
    const containerHeight = container.clientHeight;
    
    canvas.style.width = containerWidth + 'px';
    canvas.style.height = containerHeight + 'px';
    
    canvas.width = containerWidth * window.devicePixelRatio;
    canvas.height = containerHeight * window.devicePixelRatio;
    
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
}

function drawBackground() {
    if (!bgImage || !bgImage.complete) {
      return;
    }
    
    const canvasWidth = canvas.width;
    const canvasHeight = canvas.height;
    
    ctx.clearRect(0, 0, canvasWidth, canvasHeight);
    
    // Draw background image to fill entire canvas
    ctx.drawImage(bgImage, 0, 0, canvasWidth, canvasHeight);
    
    const existingPathData = document.getElementById('autoPathData').value;
    if (existingPathData && existingPathData.trim() !== '') {
        const pathImage = new Image();
        pathImage.onload = () => {
            ctx.clearRect(0, 0, canvasWidth, canvasHeight);
            // Draw path image to fill entire canvas
            ctx.drawImage(pathImage, 0, 0, canvasWidth, canvasHeight);
        };
        pathImage.src = existingPathData;
    }
}

function getPointerPosition(e) {
    const rect = canvas.getBoundingClientRect();
    return {
        x: (e.clientX - rect.left) * (canvas.width / rect.width) / window.devicePixelRatio,
        y: (e.clientY - rect.top) * (canvas.height / rect.height) / window.devicePixelRatio
    };
}

canvas.addEventListener('mousedown', startDrawing);
canvas.addEventListener('mousemove', draw);
canvas.addEventListener('mouseup', stopDrawing);
canvas.addEventListener('mouseout', stopDrawing);

function startDrawing(e) {
    e.preventDefault();
    isDrawing = true;
    const pos = getPointerPosition(e);
    lastX = pos.x;
    lastY = pos.y;
    currentPath = [];
    currentPath.push({ x: lastX, y: lastY });
}

function draw(e) {
    e.preventDefault();
    if (!isDrawing) {
      return;
    }
    
    const pos = getPointerPosition(e);
    
    // Draw the current line segment
    ctx.beginPath();
    ctx.strokeStyle = '#FF0000';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.moveTo(lastX, lastY);
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();
    
    // Save the point
    currentPath.push({ x: pos.x, y: pos.y });
    lastX = pos.x;
    lastY = pos.y;
    
    // Update the hidden input with the current canvas state
    document.getElementById('autoPathData').value = canvas.toDataURL();
}

function stopDrawing() {
    if (isDrawing) {
        isDrawing = false;
        if (currentPath.length > 1) {
            pathHistory.push(currentPath);
        }
        currentPath = [];
    }
}

function undoLastPath() {
    if (pathHistory.length > 0) {
        pathHistory.pop();
        drawBackground();
    }
}

function redrawPaths() {
    ctx.strokeStyle = '#FF0000';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    
    // Draw all completed paths
    pathHistory.forEach(path => {
        if (path.length > 1) {
            ctx.beginPath();
            ctx.moveTo(path[0].x, path[0].y);
            for (let i = 1; i < path.length; i++) {
                ctx.lineTo(path[i].x, path[i].y);
            }
            ctx.stroke();
        }
    });
    
    // Draw current path if it exists
    if (currentPath.length > 1) {
        ctx.beginPath();
        ctx.moveTo(currentPath[0].x, currentPath[0].y);
        for (let i = 1; i < currentPath.length; i++) {
            ctx.lineTo(currentPath[i].x, currentPath[i].y);
        }
        ctx.stroke();
    }
    
    // Update the hidden input
    document.getElementById('autoPathData').value = canvas.toDataURL();
}

function clearCanvas() {
    pathHistory = [];
    drawBackground();
    document.getElementById('autoPathData').value = '';
}

// Initialize
window.addEventListener('load', () => {
    bgImage = new Image();
    bgImage.onload = () => {
        resizeCanvas();
        drawBackground();
    };
    bgImage.src = "/static/images/field-2025.png";
});

// Update the resize event handler
window.addEventListener('resize', () => {
    resizeCanvas();
    drawBackground();
});