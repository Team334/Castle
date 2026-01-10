// Initialize the radar charts
let team1RadarChart = null;
let team2RadarChart = null;
let combinedRadarChart = null;

const radarConfig = {
    scales: {
        r: {
            beginAtZero: true,
            min: 0,
            max: 10,
            grid: {
                color: 'rgba(0, 0, 0, 0.1)'
            },
            ticks: {
                stepSize: 2
            }
        }
    },
    plugins: {
        legend: {
            display: false
        }
    }
};

// Config for combined chart (includes legend)
const combinedRadarConfig = {
    ...radarConfig,
    plugins: {
        legend: {
            display: true,
            position: 'bottom'
        }
    }
};

function createRadarChart(canvasId, data, isCombo = false) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    const chartData = {
        labels: [
            'Auto Scoring',
            'Teleop Scoring',
            'Climb Success',
            'Defense Rating',
        ],
        datasets: isCombo ? [
            {
                label: `Team ${data[0].team}`,
                data: data[0].values,
                backgroundColor: 'rgba(54, 162, 235, 0.2)',
                borderColor: 'rgb(54, 162, 235)',
                borderWidth: 2,
                pointBackgroundColor: 'rgb(54, 162, 235)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgb(54, 162, 235)'
            },
            {
                label: `Team ${data[1].team}`,
                data: data[1].values,
                backgroundColor: 'rgba(255, 99, 132, 0.2)',
                borderColor: 'rgb(255, 99, 132)',
                borderWidth: 2,
                pointBackgroundColor: 'rgb(255, 99, 132)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgb(255, 99, 132)'
            }
        ] : [{
            data: data.values,
            backgroundColor: 'rgba(54, 162, 235, 0.2)',
            borderColor: 'rgb(54, 162, 235)',
            borderWidth: 2,
            pointBackgroundColor: 'rgb(54, 162, 235)',
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: 'rgb(54, 162, 235)'
        }]
    };

    return new Chart(ctx, {
        type: 'radar',
        data: chartData,
        options: isCombo ? combinedRadarConfig : radarConfig
    });
}

function calculateConsistency(matchData) {
    if (matchData.length === 0) {
        return 0;
    }
    if (matchData.length === 1) {
        return 10;
    }
    
    const scores = matchData.map(m => m.total_points);
    const mean = scores.reduce((a, b) => a + b) / scores.length;
    const variance = scores.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / scores.length;
    const stdDev = Math.sqrt(variance);
    
    const consistency = 10 - normalizeValue(stdDev, 0, 20, 10);
    return Math.max(0, Math.min(10, consistency));
}

function normalizeValue(value, min, max, scale) {
    return ((value - min) / (max - min)) * scale;
}

function updateRadarCharts(teamsData) {
    const processedData = [];

    // Calculate radar chart data for each team
    for (const [teamNum, teamData] of Object.entries(teamsData)) {
        const {stats} = teamData;
        
        // Create normalized values for each metric
        const radarData = {
            team: teamNum,
            values: [
                // Auto scoring (Fuel)
                stats.auto_scoring || 0,
                // Teleop scoring (Fuel)
                stats.teleop_scoring || 0,
                // Climb success rate
                (stats.climb_rating || 0) * 10,
                // Defense rating
                (stats.defense_rating || 0) * 2
            ]
        };

        processedData.push(radarData);
    }

    // Update combined chart
    if (combinedRadarChart) {
        combinedRadarChart.destroy();
    }
    combinedRadarChart = createRadarChart('radar-chart-combined', processedData, true);
}

// Export the updateRadarCharts function
window.updateRadarCharts = updateRadarCharts;