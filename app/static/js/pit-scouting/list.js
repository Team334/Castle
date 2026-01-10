function exportToCSV() {
    const headers = [
        'Team Number',
        'Drive Type',
        'Swerve Modules',
        'Motor Count',
        'Motor Types',
        'Dimensions (L x W x H)',
        'Programming Language',
        'Has Auto',
        'Auto Routes',
        'Preferred Start',
        'Auto Notes',
        'Driver Experience',
        'Driver Notes',
        'Scouter'
    ];

    let csvContent = headers.join(',') + '\n';

    // Get all rows from the table
    const rows = Array.from(document.querySelectorAll('tbody tr'));

    rows.forEach(row => {
        try {
            // Team Number
            const teamNumber = row.querySelector('td:nth-child(1) .text-lg').textContent.trim();
            
            // Drive Type & Swerve Modules
            const driveTypeCell = row.querySelector('td:nth-child(2)');
            const driveTypes = Array.from(driveTypeCell.querySelectorAll('.rounded-full'))
                .map(span => span.textContent.trim())
                .filter(text => text !== '')
                .join('/');
            const swerveModules = driveTypeCell.querySelector('.text-sm.text-gray-500')?.textContent.trim() || '';

            // Motors
            const motorCell = row.querySelector('td:nth-child(3)');
            const motorText = motorCell.textContent.trim();
            const motorParts = motorText.split('/').map(part => part.trim());
            const motorCount = motorParts[0].split(' ')[0];
            const motorTypes = motorParts.slice(1).join('/');

            // Dimensions
            const dimensions = row.querySelector('td:nth-child(4)').textContent.trim();
            const hasClimber = !climberCell.textContent.includes('🗙');
            let climberType = '', climberNotes = '';
            if (hasClimber) {
                const climberText = climberCell.textContent.trim();
                if (climberText.includes(' - ')) {
                    [climberType, climberNotes] = climberText.split(' - ').map(s => s.trim());
                } else {
                    climberType = climberText;
                }
            }

            // Programming & Auto
            const progCell = row.querySelector('td:nth-child(8)');
            const progText = progCell.textContent.trim();
            const programmingLang = (progText.match(/Programming Language: (.+?)(?:\n|$)/) || ['', ''])[1].trim();
            const hasAuto = progText.includes('✅');
            const autoRoutes = (progText.match(/(\d+) routes/) || ['', ''])[1];
            const preferredStart = (progText.match(/Preferred Start: (.+?)(?:\n|$)/) || ['', ''])[1];
            const autoNotes = (progText.match(/Auton Notes: (.+?)(?:\n|$)/) || ['', ''])[1];

            // Driver Experience
            const driverCell = row.querySelector('td:nth-child(9)');
            const driverText = driverCell.textContent.trim();
            let driverExp = '', driverNotes = '';
            if (driverText.includes(' - ')) {
                [driverExp, driverNotes] = driverText.split(' - ').map(s => s.trim());
            }

            // Scouter
            const scouterCell = row.querySelector('td:nth-child(10)');
            let scouterName = '';
            const scouterLink = scouterCell.querySelector('a');
            if (scouterLink) {
                scouterName = scouterLink.textContent.trim();
            }

            // Escape and format fields that might contain commas or quotes
            const escapeField = (field) => {
                if (!field) {
                  return '';
                }
                const escaped = field.replace(/"/g, '""');
                return field.includes(',') || field.includes('"') || field.includes('\n') 
                    ? `"${escaped}"` 
                    : escaped;
            };

            const rowData = [
                escapeField(teamNumber),
                escapeField(driveTypes),
                escapeField(swerveModules),
                escapeField(motorCount),
                escapeField(motorTypes),
                escapeField(dimensions),
                // escapeField(coralScoring),
                // escapeField(algaeScoring),
                hasClimber ? 'Yes' : 'No',
                // escapeField(climberType),
                // escapeField(climberNotes),
                escapeField(programmingLang),
                hasAuto ? 'Yes' : 'No',
                escapeField(autoRoutes),
                escapeField(preferredStart),
                escapeField(autoNotes),
                escapeField(driverExp),
                escapeField(driverNotes),
                escapeField(scouterName)
            ];

            csvContent += rowData.join(',') + '\n';
        } catch (error) {
            console.error('Error processing row:', error);
        }
    });

    // Create and trigger download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', 'pit_scouting_data.csv');
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

document.addEventListener('DOMContentLoaded', function() {
    const exportButton = document.getElementById('exportCSV');
    if (exportButton) {
        exportButton.addEventListener('click', exportToCSV);
    }

    const searchInput = document.getElementById('teamSearchInput');
    const tableRows = document.querySelectorAll('tbody tr');
    
    searchInput.addEventListener('input', function() {
        const searchTerm = searchInput.value.trim();
        
        tableRows.forEach(row => {
            const teamNumberCell = row.querySelector('td:first-child');
            if (teamNumberCell) {
                const teamNumberText = teamNumberCell.textContent.trim();
                
                // Show/hide the row based on whether the team number contains the search term
                row.style.display = searchTerm === '' || teamNumberText.includes(searchTerm) ? '' : 'none';
            }
        });
    });
}); 