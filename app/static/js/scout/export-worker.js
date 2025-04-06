// Web worker for CSV export processing
// This handles the potentially expensive operation of creating CSV data
// without blocking the main UI thread

self.onmessage = function(e) {
    const rowData = e.data;
    
    // Create CSV content
    const headers = [
        'Event Code',
        'Match',
        'Team Number',
        'Alliance',
        'Auto Coral (L1/L2/L3/L4)',
        'Auto Algae (Net/Proc)',
        'Teleop Coral (L1/L2/L3/L4)',
        'Teleop Algae (Net/Proc)',
        'Climb',
        'Defense Rating',
        'Mobility Rating',
        'Durability Rating',
        'Notes',
        'Scouter',
    ];

    let csvContent = headers.join(',') + '\n';

    // Process data in chunks to avoid long-running operations
    const CHUNK_SIZE = 50;
    const totalChunks = Math.ceil(rowData.length / CHUNK_SIZE);
    
    for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, rowData.length);
        const chunk = rowData.slice(start, end);
        
        for (const row of chunk) {
            const rowValues = [
                row.eventCode,
                row.match,
                row.teamNumber,
                row.alliance,
                row.autoCoral,
                row.autoAlgae,
                row.teleopCoral,
                row.teleopAlgae,
                row.climb,
                row.defense,
                row.mobility,
                row.durability,
                `"${row.notes}"`,
                row.scouter,
            ];
            
            csvContent += rowValues.join(',') + '\n';
        }
    }
    
    // Return the CSV content back to the main thread
    self.postMessage({
        csvContent: csvContent,
        filename: 'scouting_data.csv'
    });
}; 