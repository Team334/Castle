// Main initialization
document.addEventListener('DOMContentLoaded', function() {
    initializeSearch();
    initializeAssignmentForm();
    initializeStatusHandlers();
    initializeEditAssignment();
    initializeNotificationHandlers();
    const teamData = document.getElementById('teamData');
    if (teamData) {
        currentUserId = teamData.dataset.currentUserId;
    }
});

// Initialize search functionality
const initializeSearch = () => {
    const memberSearch = document.getElementById('memberSearch');
    const assignmentSearch = document.getElementById('assignmentSearch');

    if (memberSearch) {
        memberSearch.addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase();
            const memberRows = document.querySelectorAll('.member-row');

            memberRows.forEach(row => {
                const username = row.children[0]?.textContent?.toLowerCase() || '';
                const email = row.children[1]?.textContent?.toLowerCase() || '';
                const role = row.children[2]?.textContent?.toLowerCase() || '';

                row.style.display = (username.includes(searchTerm) || 
                                   email.includes(searchTerm) || 
                                   role.includes(searchTerm)) ? '' : 'none';
            });
        });
    }

    if (assignmentSearch) {
        assignmentSearch.addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase();
            const assignmentRows = document.querySelectorAll('.assignment-row');

            assignmentRows.forEach(row => {
                const title = row.querySelector('td:first-child').textContent.toLowerCase();
                const description = row.querySelector('td:nth-child(2)').textContent.toLowerCase();
                const assignedTo = row.querySelector('td:nth-child(3)').textContent.toLowerCase();

                row.style.display = (title.includes(searchTerm) || 
                                   description.includes(searchTerm) || 
                                   assignedTo.includes(searchTerm)) ? '' : 'none';
            });
        });
    }
};

// Initialize assignment form
const initializeAssignmentForm = () => {
    const form = document.getElementById('createAssignmentForm');
    if (form) {
        form.addEventListener('submit', handleAssignmentSubmit);
    }
};

// Initialize status handlers
const initializeStatusHandlers = () => {
    const statusSelects = document.querySelectorAll('select[name="status"]');
    statusSelects.forEach(select => {
        select.addEventListener('click', function() {
            this.setAttribute('data-previous-value', this.value);
        });
    });
};

// Handle assignment form submission
async function handleAssignmentSubmit(e) {
    const {teamNumber} = document.getElementById('teamData').dataset;
    e.preventDefault();
    
    try {
        // Ensure we have an active notification subscription
        try {
            await notificationManager.subscribeToPushNotifications();
        } catch (error) {
            console.warn('Could not subscribe to notifications:', error);
            // Continue with assignment creation even if notification subscription fails
        }
        
        // Get the selected users' names
        const assignedToSelect = document.getElementById('assigned_to');
        const assignedToNames = Array.from(assignedToSelect.selectedOptions).map(option => option.text);
        
        const formData = {
            title: document.getElementById('title').value,
            description: document.getElementById('description').value,
            assigned_to: Array.from(document.getElementById('assigned_to').selectedOptions).map(option => option.value),
            assigned_to_names: assignedToNames,
            due_date: document.getElementById('due_date').value,
        };

        // Close modal first
        document.getElementById('createAssignmentModal').classList.add('hidden');
        
        const response = await fetch(`/team/${teamNumber}/assignments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(formData)
        });

        const data = await response.json();
        if (data.success) {
            // Clear form
            document.getElementById('createAssignmentForm').reset();
            window.location.reload()
        } else {
            throw new Error(data.message || 'Failed to create assignment');
        }
    } catch (error) {
        console.error('Error:', error);
        alert(error.message || 'An error occurred while creating the assignment');
        // Reopen modal on error
        document.getElementById('createAssignmentModal').classList.remove('hidden');
    }
}

// Handle assignment status updates
async function updateAssignmentStatus(selectElement, assignmentId) {
    const newStatus = selectElement.value;
    const previousValue = selectElement.getAttribute('data-previous-value');
    
    try {
        const response = await fetch(`/team/assignments/${assignmentId}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ status: newStatus })
        });

        if (!response.ok) {
            throw new Error('Failed to update status');
        }
        
        updateStatusBadge(selectElement, newStatus);
    } catch (error) {
        console.error('Error:', error);
        selectElement.value = previousValue;
        alert('Failed to update status');
    }
}

// Helper functions
function updateStatusBadge(selectElement, newStatus) {
    const row = selectElement.closest('tr');
    const statusCell = row.querySelector('.status-badge');
    const dueDateCell = row.querySelector('td:nth-child(4)');
    
    // Sanitize inputs
    const sanitizedStatus = String(newStatus).replace(/[<>]/g, '');
    const dueDateText = dueDateCell ? dueDateCell.textContent : '';
    
    let isLate = false;
    if (dueDateText && dueDateText !== 'No due date') {
        const dueDate = new Date(dueDateText);
        isLate = dueDate < new Date();
    }
    
    const statusClasses = {
        'completed': isLate ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800',
        'in_progress': isLate ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800',
        'pending': isLate ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-800'
    };
    
    let statusText = '';
    if (isLate) {
        statusText = sanitizedStatus === 'in_progress' ? 'In Progress (Late)' : 
                    sanitizedStatus === 'completed' ? 'Completed (Late)' : 
                    'Pending (Late)';
    } else {
        statusText = sanitizedStatus === 'in_progress' ? 'In Progress' : 
                    sanitizedStatus.charAt(0).toUpperCase() + sanitizedStatus.slice(1);
    }
    
    statusCell.textContent = statusText;
    statusCell.className = `px-2 inline-flex text-xs leading-5 font-semibold rounded-full status-badge ${statusClasses[sanitizedStatus] || statusClasses['pending']}`;
}

async function deleteAssignment(assignmentId) {
    if (!confirm('Are you sure you want to delete this assignment?')) {
        return;
    }

    try {
        const response = await fetch(`/team/assignments/${assignmentId}/delete`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        const data = await response.json();
        if (data.success) {
            window.location.reload();
        } else {
            throw new Error(data.message || 'Failed to delete assignment');
        }
    } catch (error) {
        console.error('Error:', error);
        alert(error.message || 'An error occurred while deleting the assignment');
    }
}

async function clearAllAssignments() {
    if (!confirm('Are you sure you want to clear all assignments? This action cannot be undone.')) {
        return;
    }

    const {teamNumber} = document.getElementById('teamData').dataset;

    try {
        const response = await fetch(`/team/${teamNumber}/assignments/clear`, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        const data = await response.json();
        if (data.success) {
            window.location.reload();
        } else {
            alert(data.message || 'Failed to clear assignments');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while clearing assignments');
    }
}

async function confirmDeleteTeam() {
    if (!confirm('Are you sure you want to delete this team? This action cannot be undone.')) {
        return;
    }

    const {teamNumber} = document.getElementById('teamData').dataset;

    try {
        const response = await fetch(`/team/${teamNumber}/delete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        const data = await response.json();
        if (data.success) {
            window.location.href = '/team/join';
        } else {
            throw new Error(data.message || 'Failed to delete team');
        }
    } catch (error) {
        console.error('Error:', error);
        alert(error.message || 'An error occurred while deleting the team');
    }
}

async function confirmLeaveTeam() {
    if (!confirm('Are you sure you want to leave this team?')) {
        return;
    }

    const {teamNumber} = document.getElementById('teamData').dataset;

    try {
        const response = await fetch(`/team/${teamNumber}/leave`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        const data = await response.json();
        if (data.success) {
            window.location.href = '/team/join';
        } else {
            throw new Error(data.message || 'Failed to leave team');
        }
    } catch (error) {
        console.error('Error:', error);
        alert(error.message || 'An error occurred while leaving the team');
    }
}

async function updateAdminStatus(userId, action) {
    const {teamNumber} = document.getElementById('teamData').dataset;
    const url = action === 'add' 
        ? `/team/${teamNumber}/admin/add`
        : `/team/${teamNumber}/admin/remove`;
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ user_id: userId })
        });

        const data = await response.json();
        
        if (data.success) {
            // Reload the page to reflect changes
            window.location.reload();
        } else {
            alert(data.message || 'Failed to update admin status');
        }
    } catch (error) {
        console.error('Error updating admin status:', error);
        alert('Failed to update admin status');
    }
}

function openEditAssignmentModal(assignmentId) {
    try {
        const row = document.querySelector(`tr[data-assignment-id="${assignmentId}"]`);
        if (!row) {
            console.error('Row not found for assignment:', assignmentId);
            return;
        }

        const modal = document.getElementById('editAssignmentModal');
        if (!modal) {
            console.error('Edit modal not found');
            return;
        }

        // Fill the form with current values
        document.getElementById('edit_assignment_id').value = assignmentId;
        
        // Get the cells by their position
        const cells = row.getElementsByTagName('td');
        const titleCell = cells[0];
        const descriptionCell = cells[1];
        const assignedToCell = cells[2];
        const dueDateCell = cells[3];

        if (titleCell) {
          document.getElementById('edit_title').value = titleCell.textContent.trim();
        }
        if (descriptionCell) {
          // Extract the description text properly
          let descriptionText = '';
          const descriptionPreview = descriptionCell.querySelector('.description-preview');
          const descriptionFull = descriptionCell.querySelector('.description-full');
          
          if (descriptionFull) {
            // Get the text content of the full description, excluding the button
            const fullTextContent = descriptionFull.childNodes[0].textContent.trim();
            descriptionText = fullTextContent;
          } else if (descriptionPreview) {
            // If no full description, get the preview text
            const previewText = descriptionPreview.childNodes[0].textContent.trim();
            descriptionText = previewText;
          } else {
            // Fallback to the cell's text content
            descriptionText = descriptionCell.textContent.trim()
              .replace('See more', '')
              .replace('See less', '')
              .trim();
          }
          
          document.getElementById('edit_description').value = descriptionText;
        }

        // Handle assigned users
        if (assignedToCell) {
            const assignedUsers = assignedToCell.textContent
                .split(',')
                .map(u => u.trim());

            const selectElement = document.getElementById('edit_assigned_to');
            if (selectElement) {
                Array.from(selectElement.options).forEach(option => {
                    option.selected = assignedUsers.includes(option.text.trim());
                });
            }
        }

        // Handle due date
        if (dueDateCell) {
            const dueDateText = dueDateCell.textContent.trim();
            if (dueDateText && dueDateText !== 'No due date') {
                const dueDate = new Date(dueDateText);
                if (!isNaN(dueDate.getTime())) {
                    // Format the date to the required format for datetime-local input
                    const formattedDate = dueDate.toISOString().slice(0, 16);
                    document.getElementById('edit_due_date').value = formattedDate;
                }
            } else {
                document.getElementById('edit_due_date').value = '';
            }
        }

        // Show the modal
        modal.classList.remove('hidden');
        
    } catch (error) {
        console.error('Error opening edit modal:', error);
        alert('Error opening edit modal');
    }
}

async function handleEditAssignmentSubmit(e) {
    e.preventDefault();
    
    const assignmentId = document.getElementById('edit_assignment_id').value;
    const formData = {
        title: document.getElementById('edit_title').value,
        description: document.getElementById('edit_description').value,
        assigned_to: Array.from(document.getElementById('edit_assigned_to').selectedOptions).map(option => option.value),
        assigned_to_names: Array.from(document.getElementById('edit_assigned_to').selectedOptions).map(option => option.text),
        due_date: document.getElementById('edit_due_date').value
    };

    try {
        const response = await fetch(`/team/assignments/${assignmentId}/edit`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify(formData)
        });

        const data = await response.json();
        if (data.success) {
            window.location.reload();
        } else {
            throw new Error(data.message || 'Failed to update assignment');
        }
    } catch (error) {
        console.error('Error:', error);
        alert(error.message || 'An error occurred while updating the assignment');
    }
}

// Add this new function
function initializeEditAssignment() {
    // Initialize edit form submit handler
    const editForm = document.getElementById('editAssignmentForm');
    if (editForm) {
        editForm.addEventListener('submit', handleEditAssignmentSubmit);
    }

    // Check for late assignments on page load
    document.querySelectorAll('.assignment-row').forEach(row => {
        const statusSelect = row.querySelector('select[name="status"]');
        if (statusSelect) {
            updateStatusBadge(statusSelect, statusSelect.value);
        }
    });
}

function createAssignmentRow(assignment) {
    const isCurrentUserAssigned = assignment.assigned_to.includes(currentUserId);
    const row = document.createElement('tr');
    row.className = `assignment-row ${isCurrentUserAssigned ? 'bg-blue-50' : ''} hover:bg-gray-50`;
    
    const formattedDate = assignment.due_date ? 
        new Date(assignment.due_date).toLocaleString() : 
        'No due date';

    const cells = [
        { text: assignment.title, class: 'px-6 py-4 whitespace-nowrap' },
        { text: assignment.description, class: 'px-6 py-4 whitespace-normal' },
        { text: assignment.assigned_to_names.join(', '), class: 'px-6 py-4 whitespace-nowrap' },
        { text: formattedDate, class: 'px-6 py-4 whitespace-nowrap' }
    ];

    cells.forEach(cellData => {
        const td = document.createElement('td');
        td.className = cellData.class;
        td.textContent = cellData.text;
        row.appendChild(td);
    });

    // Status cell
    const statusTd = document.createElement('td');
    statusTd.className = 'px-6 py-4 whitespace-nowrap';
    const statusSpan = document.createElement('span');
    statusSpan.className = 'px-2 inline-flex text-xs leading-5 font-semibold rounded-full status-badge bg-gray-100 text-gray-800';
    statusSpan.textContent = 'Pending (Offline)';
    statusTd.appendChild(statusSpan);
    row.appendChild(statusTd);

    const actionTd = document.createElement('td');
    actionTd.className = 'px-6 py-4 whitespace-nowrap text-sm';
    const actionSpan = document.createElement('span');
    actionSpan.className = 'text-gray-500';
    actionSpan.textContent = 'Pending sync...';
    actionTd.appendChild(actionSpan);
    row.appendChild(actionTd);
    
    return row;
}

// Initialize notification handlers
function initializeNotificationHandlers() {
    // Add data-assignment-id to all reminder bell icons
    const reminderBells = document.querySelectorAll('.assignment-row button[title="Set reminder for this assignment"]');
    reminderBells.forEach(bell => {
        const row = bell.closest('.assignment-row');
        const {assignmentId} = row.dataset;
        
        // Add assignment ID to the button and add assignment-reminder-btn class
        bell.setAttribute('data-assignment-id', assignmentId);
        bell.classList.add('assignment-reminder-btn');
    });
}