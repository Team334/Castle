document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM content loaded, initializing...');
    initializeSearch();
    initializeAssignmentForm();
    initializeStatusHandlers();
    initializeEditAssignment();
    initializeNotifications();
    initializeAssignmentReminders();
    initializeDevTools();
    const teamData = document.getElementById('teamData');
    if (teamData) {
        currentUserId = teamData.dataset.currentUserId;
    }
    
    // Add direct event listener for notification bell
    const notificationBell = document.getElementById('notificationBell');
    if (notificationBell) {
        console.log('Notification bell found in main init');
        notificationBell.onclick = function(e) {
            console.log('Notification bell clicked from main init');
            e.preventDefault();
            const notificationModal = document.getElementById('notificationModal');
            if (notificationModal) {
                notificationModal.classList.remove('hidden');
                if (typeof checkNotificationPermission === 'function') {
                    checkNotificationPermission();
                }
            } else {
                console.error('Notification modal not found in main init');
            }
            return false;
        };
    } else {
        console.error('Notification bell not found in main init');
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

    try {
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
            window.location.reload();
        } else {
            throw new Error(data.message || 'Failed to create assignment');
        }
    } catch (error) {
        console.error('Error:', error);
        alert(error.message || 'An error occurred while creating the assignment');
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
          document.getElementById('edit_description').value = descriptionCell.textContent.trim();
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

// Add this new function for notifications
function initializeNotifications() {
    console.log('Initializing notifications...');
    
    // Get DOM elements
    const notificationBell = document.getElementById('notificationBell');
    const notificationModal = document.getElementById('notificationModal');
    
    // Only proceed if notification elements exist
    if (!notificationBell || !notificationModal) {
        console.error('Notification elements not found');
        return;
    }
    
    // Don't check subscription on page load - only when the bell is clicked
    notificationBell.addEventListener('click', function(e) {
        e.preventDefault();
        
        // Show modal first
        notificationModal.classList.remove('hidden');
        
        // Then check permission (this only happens after user interaction)
        if (typeof checkNotificationPermission === 'function') {
            checkNotificationPermission();
        }
        
        return false;
    });
    
    // Other notification initialization code...
}

// Add this new function to handle notification UI updates
function updateNotificationUI(data) {
    console.log('Updating notification UI with data:', data);
    
    // Check if notification modal exists
    const notificationModal = document.getElementById('notificationModal');
    if (!notificationModal) {
        console.error('Notification modal not found');
        return;
    }

    // Find or create the status element
    let statusText = document.getElementById('notificationStatus');
    if (!statusText) {
        // Create a status text element if it doesn't exist
        statusText = document.createElement('p');
        statusText.id = 'notificationStatus';
        statusText.className = 'text-sm mb-4';
        notificationModal.querySelector('.modal-content').prepend(statusText);
    }
    
    // Find or update the buttons
    let enableButton = document.getElementById('enableNotifications');
    let disableButton = document.getElementById('disableNotifications');
    
    // Get any existing notification buttons
    const existingButtons = notificationModal.querySelectorAll('button');
    if (existingButtons.length > 0) {
        // Use existing buttons instead of creating new ones
        if (!enableButton) {
            enableButton = Array.from(existingButtons).find(btn => 
                btn.textContent.includes('Enable') || btn.textContent.includes('Subscribe')
            );
            if (enableButton) enableButton.id = 'enableNotifications';
        }
        
        if (!disableButton) {
            disableButton = Array.from(existingButtons).find(btn => 
                btn.textContent.includes('Disable') || btn.textContent.includes('Unsubscribe')
            );
            if (disableButton) disableButton.id = 'disableNotifications';
        }
    }
    
    // Create permission status display if doesn't exist
    let permissionStatus = document.getElementById('permissionStatus');
    if (!permissionStatus) {
        permissionStatus = document.createElement('span');
        permissionStatus.id = 'permissionStatus';
        permissionStatus.className = 'px-2 py-1 rounded text-sm font-bold';
        if (statusText.parentNode) {
            statusText.parentNode.insertBefore(permissionStatus, statusText.nextSibling);
        }
    }
    
    // Update the UI based on notification status
    if (Notification.permission === 'granted' && data.hasSubscription) {
        // Notifications are enabled
        statusText.textContent = 'Notifications are enabled. ';
        statusText.className = 'text-sm text-green-500 mb-4';
        
        // Show/hide appropriate buttons
        if (enableButton) enableButton.style.display = 'none';
        if (disableButton) disableButton.style.display = 'block';
    } else {
        // Notifications are disabled
        statusText.textContent = 'Notifications are disabled. ';
        statusText.className = 'text-sm text-red-500 mb-4';
        
        // Show/hide appropriate buttons
        if (enableButton) enableButton.style.display = 'block';
        if (disableButton) disableButton.style.display = 'none';
    }
    
    // Update permission status display
    if (permissionStatus) {
        permissionStatus.textContent = data.permissionStatus || Notification.permission;
        permissionStatus.className = 'px-2 py-1 rounded text-sm font-bold ml-2';
        
        if (Notification.permission === 'granted') {
            permissionStatus.classList.add('bg-green-100', 'text-green-800');
        } else if (Notification.permission === 'denied') {
            permissionStatus.classList.add('bg-red-100', 'text-red-800');
        } else {
            permissionStatus.classList.add('bg-yellow-100', 'text-yellow-800');
        }
    }
}

// Update checkNotificationPermission to handle the "no subscription" case better
function checkNotificationPermission() {
    console.log('Checking notification permission...');
    
    // Check if we already have permission
    if (Notification.permission === 'granted') {
        // Only make the API call to check subscription if permission is already granted
        fetch('/team/notifications/status')
            .then(response => response.json())
            .then(data => {
                updateNotificationUI(data);
            })
            .catch(error => {
                console.error('Error checking notification status:', error);
                // Don't show error message on page load - just log it
                updateNotificationUI({ hasSubscription: false, permissionStatus: Notification.permission });
            });
    } else {
        // Just update UI to reflect permission status without error message
        updateNotificationUI({ hasSubscription: false, permissionStatus: Notification.permission });
    }
}

// Get service worker registration
async function getServiceWorkerRegistration() {
    console.log('Getting service worker registration');
    try {
        if (!('serviceWorker' in navigator)) {
            console.error('Service Worker not supported in this browser');
            return null;
        }
        
        // Check if service worker is already registered
        const registrations = await navigator.serviceWorker.getRegistrations();
        console.log('Existing service worker registrations:', registrations.length);
        
        if (registrations.length === 0) {
            console.log('No service worker registrations found, attempting to register');
            // Try to register the service worker if not already registered
            try {
                const registration = await navigator.serviceWorker.register('/service-worker.js', {
                    scope: '/'
                });
                console.log('Service worker registered:', registration);
                return registration;
            } catch (regError) {
                console.error('Failed to register service worker:', regError);
                return null;
            }
        }
        
        // Return the first registration or wait for the service worker to be ready
        return await navigator.serviceWorker.ready;
    } catch (error) {
        console.error('Error getting service worker registration:', error);
        return null;
    }
}

// Subscribe to push notifications
async function subscribeToPushNotifications() {
    console.log('Attempting to subscribe to push notifications');
    try {
        const swRegistration = await getServiceWorkerRegistration();
        if (!swRegistration) {
            throw new Error('Service Worker not registered');
        }
        
        // Get the server's public key
        console.log('Fetching VAPID public key');
        const response = await fetch('/team/notifications/vapid-public-key');
        if (!response.ok) {
            throw new Error(`Failed to fetch VAPID key: ${response.status} ${response.statusText}`);
        }
        
        const vapidPublicKey = await response.text();
        console.log('Received VAPID public key length:', vapidPublicKey.length);
        
        if (!vapidPublicKey || vapidPublicKey.trim() === '') {
            throw new Error('No VAPID public key provided by the server');
        }
        
        // Convert the public key to Uint8Array
        try {
            const applicationServerKey = urlBase64ToUint8Array(vapidPublicKey);
            console.log('Converted VAPID key to Uint8Array successfully');
            
            // Check if already subscribed
            const existingSubscription = await swRegistration.pushManager.getSubscription();
            if (existingSubscription) {
                console.log('Already subscribed to push notifications');
                return existingSubscription;
            }
            
            // Subscribe the user
            console.log('Creating push subscription');
            const subscription = await swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });
            
            console.log('Push subscription created successfully');
            
            // Send the subscription to the server
            console.log('Sending subscription to server');
            const saveResponse = await fetch('/team/notifications/subscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    subscription: subscription.toJSON()
                })
            });
            
            if (!saveResponse.ok) {
                const errorText = await saveResponse.text();
                throw new Error(`Failed to save subscription: ${saveResponse.status} ${saveResponse.statusText} - ${errorText}`);
            }
            
            console.log('Subscription saved to server successfully');
            return subscription;
        } catch (keyError) {
            console.error('Error processing VAPID key:', keyError);
            throw new Error(`Error processing VAPID key: ${keyError.message}`);
        }
    } catch (error) {
        console.error('Failed to subscribe to push notifications:', error);
        throw error;
    }
}

// Subscribe to all assignments
async function subscribeToAllAssignments(reminderTime) {
    try {
        const {teamNumber} = document.getElementById('teamData').dataset;
        
        const response = await fetch(`/team/${teamNumber}/notifications/subscribe-all`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                reminderTime
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.message || 'Failed to subscribe to all assignments');
        }
    } catch (error) {
        console.error('Error subscribing to all assignments:', error);
        throw error;
    }
}

// Load user's notification settings
async function loadNotificationSettings() {
    try {
        const {teamNumber} = document.getElementById('teamData').dataset;
        
        const response = await fetch(`/team/${teamNumber}/notifications/settings`);
        const data = await response.json();
        
        if (data.success && data.settings) {
            const { defaultReminderTime, enableAllNotifications } = data.settings;
            
            // Set the values in the form
            if (defaultReminderTime) {
                document.getElementById('defaultReminderTime').value = defaultReminderTime;
            }
            
            if (enableAllNotifications !== undefined) {
                document.getElementById('enableAllNotifications').checked = enableAllNotifications;
            }
        }
    } catch (error) {
        console.error('Error loading notification settings:', error);
    }
}

// Initialize assignment reminder functionality
function initializeAssignmentReminders() {
    const saveReminderBtn = document.getElementById('saveAssignmentReminder');
    if (saveReminderBtn) {
        saveReminderBtn.addEventListener('click', handleSaveAssignmentReminder);
    }
}

// Handle saving assignment reminder
async function handleSaveAssignmentReminder() {
    console.log('Saving assignment reminder...');
    const assignmentId = document.getElementById('reminderAssignmentId').value;
    const reminderTime = document.getElementById('assignmentReminderTime').value;
    
    console.log('Assignment ID:', assignmentId);
    console.log('Reminder time:', reminderTime);
    
    if (!assignmentId || !reminderTime) {
        alert('Missing assignment information');
        return;
    }
    
    try {
        // Convert reminder time to integer
        const reminderTimeInt = parseInt(reminderTime, 10);
        if (isNaN(reminderTimeInt)) {
            throw new Error('Invalid reminder time: must be a number');
        }
        
        console.log('Sending subscription request...');
        
        // Subscribe to the assignment
        const response = await fetch(`/team/assignments/${assignmentId}/subscribe`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                reminderTime: reminderTimeInt
            })
        });
        
        console.log('Subscription response status:', response.status);
        
        // Try to parse the response as JSON
        let data;
        try {
            data = await response.json();
            console.log('Subscription response data:', data);
        } catch (jsonError) {
            console.error('Failed to parse response as JSON:', jsonError);
            const text = await response.text();
            console.log('Response text:', text);
            throw new Error(`Server returned invalid JSON: ${text}`);
        }
        
        if (data.success) {
            console.log('Reminder set successfully');
            alert('Reminder set successfully!');
            document.getElementById('assignmentReminderModal').classList.add('hidden');
        } else {
            console.error('Error setting reminder:', data.message);
            alert('Failed to set reminder: ' + data.message);
        }
    } catch (error) {
        console.error('Error setting reminder:', error);
        alert('Failed to set reminder: ' + error.message);
    }
}

// Subscribe to a specific assignment
async function subscribeToAssignment(assignmentId) {
    try {
        // Check if notifications are supported and permission is granted
        if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) {
            alert('Your browser does not support notifications.');
            return;
        }

        if (Notification.permission !== 'granted') {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
                alert('You need to allow notifications to use this feature.');
                return;
            }
        }

        // Get service worker registration
        const swRegistration = await navigator.serviceWorker.ready;
        
        // Check if push subscription exists
        let subscription = await swRegistration.pushManager.getSubscription();
        if (!subscription) {
            // Get the server's public key
            const response = await fetch('/team/notifications/vapid-public-key');
            const vapidPublicKey = await response.text();
            
            // Convert the public key to Uint8Array
            const applicationServerKey = urlBase64ToUint8Array(vapidPublicKey);
            
            // Subscribe the user
            subscription = await swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });
            
            // Send the subscription to the server
            await fetch('/team/notifications/subscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    subscription: subscription.toJSON()
                })
            });
        }

        // Show the reminder modal
        document.getElementById('reminderAssignmentId').value = assignmentId;
        document.getElementById('assignmentReminderModal').classList.remove('hidden');
        
    } catch (error) {
        console.error('Error preparing assignment subscription:', error);
        alert('Failed to prepare notification: ' + error.message);
    }
}

// Helper function to convert base64 to Uint8Array
function urlBase64ToUint8Array(base64String) {
    try {
        if (!base64String) {
            throw new Error('Empty base64 string provided');
        }
        
        // Clean the base64 string
        const cleanedBase64 = base64String.trim();
        console.log('Base64 string length after trimming:', cleanedBase64.length);
        
        if (cleanedBase64.length === 0) {
            throw new Error('Empty base64 string after trimming');
        }
        
        const padding = '='.repeat((4 - cleanedBase64.length % 4) % 4);
        const base64 = (cleanedBase64 + padding)
            .replace(/-/g, '+')
            .replace(/_/g, '/');
        
        try {
            const rawData = window.atob(base64);
            const outputArray = new Uint8Array(rawData.length);
            
            for (let i = 0; i < rawData.length; ++i) {
                outputArray[i] = rawData.charCodeAt(i);
            }
            return outputArray;
        } catch (atobError) {
            console.error('Error decoding base64:', atobError);
            throw new Error('Invalid base64 string: ' + atobError.message);
        }
    } catch (error) {
        console.error('Error in urlBase64ToUint8Array:', error);
        throw error;
    }
}

// Test notification system
async function testNotificationSystem() {
    try {
        console.log('Testing notification system...');
        
        // First check if the configuration is correct
        const configResponse = await fetch('/team/notifications/test');
        if (!configResponse.ok) {
            console.error('Notification test failed:', configResponse.status, configResponse.statusText);
            return;
        }
        
        const configData = await configResponse.json();
        console.log('Notification system test results:', configData);
        
        // Check if VAPID keys are configured
        if (!configData.has_vapid_key || !configData.has_vapid_private) {
            console.error('VAPID keys are not properly configured:', {
                has_public_key: configData.has_vapid_key,
                has_private_key: configData.has_vapid_private
            });
            alert('Notification system is not properly configured. Please contact the administrator.');
            return;
        }
        
        console.log('VAPID keys are properly configured');
        
        // Now actually send a test notification
        const permission = Notification.permission;
        if (permission !== 'granted') {
            console.warn('Notification permission not granted:', permission);
            const newPermission = await Notification.requestPermission();
            if (newPermission !== 'granted') {
                alert('You must allow notifications to continue.');
                return;
            }
        }
        
        // Check if we have a valid service worker registration
        const swRegistration = await getServiceWorkerRegistration();
        if (!swRegistration) {
            console.error('Service Worker not registered');
            alert('Service Worker not registered. Notifications unavailable.');
            return;
        }
        
        // Check if we have a valid push subscription
        let pushSubscription = await swRegistration.pushManager.getSubscription();
        
        // If no subscription exists, create one automatically
        if (!pushSubscription) {
            console.log('No push subscription found. Creating one now...');
            try {
                pushSubscription = await subscribeToPushNotifications();
                if (!pushSubscription) {
                    alert('Could not create push subscription. Please try enabling notifications first.');
                    return;
                }
                console.log('Successfully created push subscription');
            } catch (subscriptionError) {
                console.error('Failed to create subscription:', subscriptionError);
                alert(`Could not subscribe to notifications: ${subscriptionError.message}`);
                return;
            }
        }
        
        // Send a test notification
        console.log('Sending test notification...');
        const testResponse = await fetch('/team/notifications/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const testResult = await testResponse.json();
        console.log('Test notification result:', testResult);
        
        if (testResult.success) {
            alert('Test notification sent successfully! You should receive it shortly.');
        } else {
            alert(`Failed to send test notification: ${testResult.message}`);
        }
    } catch (error) {
        console.error('Error testing notification system:', error);
        alert(`Error testing notification system: ${error.message}`);
    }
}

// Direct Browser Notification
async function showDirectNotification() {
    console.log('Showing direct browser notification...');
    try {
        // Check if notifications are supported
        if (!('Notification' in window)) {
            alert('This browser does not support desktop notifications');
            return;
        }

        // Check permission
        if (Notification.permission !== 'granted') {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
                alert('Permission not granted for notifications');
                return;
            }
        }

        // Create and show the notification directly
        const notification = new Notification('Test Direct Notification', {
            body: 'This is a direct browser notification (no push)',
            icon: '/static/logo.png',
            timestamp: Date.now()
        });

        // Log when notification is clicked
        notification.onclick = function() {
            console.log('Notification clicked');
            window.focus();
            notification.close();
        };

        console.log('Direct notification created:', notification);
        alert('Direct notification sent! You should see it now.');
    } catch (error) {
        console.error('Error showing direct notification:', error);
        alert(`Error showing notification: ${error.message}`);
    }
}

// Simple Push Notification - streamlined version with minimal checks
async function sendSimplePushNotification() {
    console.log('Sending simple push notification...');
    try {
        // Just make the POST request directly
        const response = await fetch('/team/notifications/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        console.log('Simple push notification response:', response);
        
        if (response.ok) {
            const result = await response.json();
            console.log('Simple push notification result:', result);
            alert('Simple push notification request sent! Check console for details.');
        } else {
            const errorText = await response.text();
            throw new Error(`Server error: ${response.status} ${response.statusText} - ${errorText}`);
        }
    } catch (error) {
        console.error('Error sending simple push notification:', error);
        alert(`Error sending simple push notification: ${error.message}`);
    }
}

// Initialize developer tools
function initializeDevTools() {
    // Only show dev tools in development environment
    const isLocalhost = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
    const devReloadBtn = document.getElementById('devReloadBtn');
    
    if (devReloadBtn && isLocalhost) {
        // Show the button only in development
        devReloadBtn.style.display = 'flex';
        
        // Add event listener
        devReloadBtn.addEventListener('click', clearCacheAndReload);
    }
}

// Function to clear all caches and reload the page
async function clearCacheAndReload() {
    try {
        console.log('Clearing service worker cache...');
        
        // Unregister all service workers
        const registrations = await navigator.serviceWorker.getRegistrations();
        for (let registration of registrations) {
            console.log('Unregistering service worker:', registration.scope);
            await registration.unregister();
        }
        
        // Clear all caches
        const cacheNames = await caches.keys();
        await Promise.all(
            cacheNames.map(cacheName => {
                console.log('Deleting cache:', cacheName);
                return caches.delete(cacheName);
            })
        );
        
        console.log('All caches cleared successfully');
        alert('Cache cleared successfully! Reloading page...');
        
        // Add a timestamp to force reload without cache
        window.location.href = window.location.pathname + '?cache-bust=' + Date.now();
    } catch (error) {
        console.error('Error clearing cache:', error);
        alert('Error clearing cache: ' + error.message);
    }
}

// Update the refreshPushSubscription function to use the resubscribe endpoint
async function refreshPushSubscription() {
    console.log('Refreshing push subscription...');
    try {
        // Unsubscribe from any existing subscription
        const swRegistration = await navigator.serviceWorker.ready;
        const existingSubscription = await swRegistration.pushManager.getSubscription();
        
        if (existingSubscription) {
            console.log('Unsubscribing from existing subscription');
            await existingSubscription.unsubscribe();
        }
        
        // Create a new subscription
        const newSubscription = await subscribeToPushNotifications();
        if (!newSubscription) {
            throw new Error('Failed to create new subscription');
        }
        
        // Send the new subscription to the server using the resubscribe endpoint
        const response = await fetch('/team/notifications/resubscribe', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                subscription: newSubscription.toJSON()
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to register new subscription with server');
        }
        
        console.log('Successfully refreshed push subscription');
        return newSubscription;
    } catch (error) {
        console.error('Error refreshing push subscription:', error);
        throw error;
    }
}

// Add a button to your notification modal to manually refresh
// <button id="refreshSubscriptionBtn" class="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
//   Refresh Notification Subscription
// </button>

// And add this event listener in your initializeNotifications function:
const refreshBtn = document.getElementById('refreshSubscriptionBtn');
if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
        try {
            await refreshPushSubscription();
            alert('Notification subscription refreshed successfully!');
            checkNotificationPermission();
        } catch (error) {
            alert(`Failed to refresh subscription: ${error.message}`);
        }
    });
}