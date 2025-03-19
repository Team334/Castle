/**
 * Push Notification Manager
 * Handles push notification subscriptions, permissions, and UI
 */

class NotificationManager {
    constructor() {
        this.swRegistration = null;
        this.vapidPublicKey = null;
        this.isSubscribed = false;
        this.initialized = false;
        this.subscriptionInfo = null;
        console.log('[NotificationManager] Initialized');
    }

    /**
     * Initialize the notification manager
     */
    async init() {
        try {
            console.log('[NotificationManager] Starting initialization');
            
            // Check if service workers are supported
            if (!('serviceWorker' in navigator)) {
                console.warn('[NotificationManager] Service workers are not supported by this browser');
                return false;
            }
            console.log('[NotificationManager] Service workers are supported');

            // Check if PushManager is supported
            if (!('PushManager' in window)) {
                console.warn('[NotificationManager] Push notifications are not supported by this browser');
                return false;
            }
            console.log('[NotificationManager] Push Manager is supported');

            // Get VAPID public key from server
            await this.getVapidPublicKey();
            console.log('[NotificationManager] Got VAPID public key:', this.vapidPublicKey ? 'Yes' : 'No');

            // Register service worker
            await this.registerServiceWorker();
            console.log('[NotificationManager] Service worker registered:', this.swRegistration ? 'Yes' : 'No');

            // Check if already subscribed
            await this.checkSubscription();
            console.log('[NotificationManager] Subscription status:', this.isSubscribed ? 'Subscribed' : 'Not subscribed');

            this.initialized = true;
            console.log('[NotificationManager] Initialization complete');
            return true;
        } catch (error) {
            console.error('[NotificationManager] Error during initialization:', error);
            return false;
        }
    }

    /**
     * Get VAPID public key from server
     */
    async getVapidPublicKey() {
        try {
            const response = await fetch('/notifications/vapid-public-key');
            const data = await response.json();
            this.vapidPublicKey = data.publicKey;
            return this.vapidPublicKey;
        } catch (error) {
            console.error('Error fetching VAPID public key:', error);
            throw error;
        }
    }

    /**
     * Register service worker
     */
    async registerServiceWorker() {
        try {
            // Instead of registering a new service worker, get the existing registration
            this.swRegistration = await navigator.serviceWorker.ready;
            console.log('Using existing service worker registration');
            return this.swRegistration;
        } catch (error) {
            console.error('Error getting service worker registration:', error);
            throw error;
        }
    }

    /**
     * Check if we already have an active subscription
     */
    async checkSubscription() {
        try {
            if (!this.swRegistration) {
                return false;
            }

            const subscription = await this.swRegistration.pushManager.getSubscription();
            this.isSubscribed = subscription !== null;
            this.subscriptionInfo = subscription;

            console.log('User is ' + (this.isSubscribed ? 'subscribed' : 'not subscribed'));
            return this.isSubscribed;
        } catch (error) {
            console.error('Error checking subscription:', error);
            throw error;
        }
    }

    /**
     * Convert URL base64 to Uint8Array
     * (Required for the Web Push API)
     */
    urlB64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding)
            .replace(/\-/g, '+')
            .replace(/_/g, '/');

        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);

        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    /**
     * Subscribe to push notifications
     */
    async subscribeToPushNotifications(assignmentId = null, reminderTime = 1440) {
        try {
            console.log('[NotificationManager] Starting subscription process');
            
            if (!this.initialized) {
                console.log('[NotificationManager] Not initialized, initializing now');
                await this.init();
            }

            // Request permission if not granted
            const permission = await this.requestNotificationPermission();
            console.log('[NotificationManager] Notification permission status:', permission);
            
            if (permission !== 'granted') {
                throw new Error('Notification permission denied');
            }

            // Always try to get a fresh subscription
            if (this.subscriptionInfo) {
                console.log('[NotificationManager] Unsubscribing from existing subscription');
                try {
                    await this.subscriptionInfo.unsubscribe();
                } catch (error) {
                    console.warn('[NotificationManager] Error unsubscribing from old subscription:', error);
                }
                this.subscriptionInfo = null;
            }

            // Get new subscription
            console.log('[NotificationManager] Creating new push subscription');
            const applicationServerKey = this.urlB64ToUint8Array(this.vapidPublicKey);
            this.subscriptionInfo = await this.swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });
            this.isSubscribed = true;
            console.log('[NotificationManager] Successfully created push subscription');

            // Send subscription to server
            console.log('[NotificationManager] Sending subscription to server');
            const response = await fetch('/notifications/subscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    subscription: this.subscriptionInfo.toJSON(),
                    assignment_id: assignmentId,
                    reminder_time: reminderTime
                })
            });

            const result = await response.json();
            console.log('[NotificationManager] Server response:', result);
            
            if (!result.success) {
                throw new Error(result.message || 'Failed to subscribe on server');
            }

            return result;
        } catch (error) {
            console.error('[NotificationManager] Error subscribing to push notifications:', error);
            throw error;
        }
    }

    /**
     * Unsubscribe from push notifications
     */
    async unsubscribeFromPushNotifications(assignmentId = null) {
        try {
            if (!this.isSubscribed || !this.subscriptionInfo) {
                return { success: true, message: 'Not subscribed' };
            }

            // Unsubscribe from push manager
            await this.subscriptionInfo.unsubscribe();
            this.isSubscribed = false;

            // Remove subscription from server
            const response = await fetch('/notifications/unsubscribe', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    assignment_id: assignmentId
                })
            });

            return await response.json();
        } catch (error) {
            console.error('Error unsubscribing from push notifications:', error);
            throw error;
        }
    }

    /**
     * Request notification permission
     */
    async requestNotificationPermission() {
        if (!("Notification" in window)) {
            throw new Error('Notifications not supported');
        }

        if (Notification.permission === 'denied') {
            throw new Error('Notification permission was denied');
        }

        if (Notification.permission === 'granted') {
            return 'granted';
        }

        // Request permission
        return await Notification.requestPermission();
    }

    /**
     * Send a test notification
     */
    async sendTestNotification() {
        try {
            if (!this.isSubscribed) {
                await this.subscribeToPushNotifications();
            }

            const response = await fetch('/notifications/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            return await response.json();
        } catch (error) {
            console.error('Error sending test notification:', error);
            throw error;
        }
    }
}

// Initialize global notification manager
const notificationManager = new NotificationManager();

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize notification manager
    notificationManager.init().then(success => {
        if (success) {
            console.log('Notification manager initialized successfully');
            
            // Initialize UI elements if they exist
            initNotificationUI();
        }
    });
});

// Initialize notification UI elements
function initNotificationUI() {
    // Find assignment reminder buttons
    const reminderButtons = document.querySelectorAll('.assignment-reminder-btn');
    if (reminderButtons.length > 0) {
        reminderButtons.forEach(button => {
            button.addEventListener('click', handleReminderClick);
        });
    }

    // Find test notification button
    const testButton = document.getElementById('testNotificationBtn');
    if (testButton) {
        testButton.addEventListener('click', async () => {
            try {
                const result = await notificationManager.sendTestNotification();
                alert(result.message);
            } catch (error) {
                alert('Error sending test notification: ' + error.message);
            }
        });
    }
}

// Handle reminder button click
async function handleReminderClick(e) {
    const button = e.currentTarget;
    const {assignmentId} = button.dataset;
    
    if (!assignmentId) {
        alert('No assignment ID found');
        return;
    }
    
    // Show assignment reminder modal
    const modal = document.getElementById('assignmentReminderModal');
    if (modal) {
        // Set assignment ID in the modal
        document.getElementById('reminderAssignmentId').value = assignmentId;
        modal.classList.remove('hidden');
        
        // Handle save button
        const saveButton = document.getElementById('saveAssignmentReminder');
        if (saveButton) {
            saveButton.onclick = async () => {
                const reminderTime = parseInt(document.getElementById('assignmentReminderTime').value, 10);
                
                try {
                    const result = await notificationManager.subscribeToPushNotifications(assignmentId, reminderTime);
                    alert(result.message);
                    modal.classList.add('hidden');
                } catch (error) {
                    alert('Error setting reminder: ' + error.message);
                }
            };
        }
    }
} 