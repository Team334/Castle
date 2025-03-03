const CACHE_NAME = 'scouting-app-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/static/css/global.css',
  '/static/css/index.css',
  '/static/js/Canvas.js',
  '/static/images/field-2025.png',
  '/static/images/default_profile.png',
  '/static/js/notifications.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(ASSETS_TO_CACHE))
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        if (response) {
          return response;
        }
        return fetch(event.request)
          .then((response) => {
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }
            const responseToCache = response.clone();
            caches.open(CACHE_NAME)
              .then((cache) => {
                cache.put(event.request, responseToCache);
              });
            return response;
          });
      })
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Handle push events (notifications)
self.addEventListener('push', (event) => {
  console.log('Push event received');
  
  try {
    if (!event.data) {
      console.warn('Push event has no data');
      return;
    }
    
    // Parse the notification data
    let data;
    try {
      data = event.data.json();
      console.log('Push data received:', data);
    } catch (error) {
      console.error('Failed to parse push data as JSON:', error);
      const text = event.data.text();
      console.log('Push data as text:', text);
      data = { title: 'New Notification', body: text };
    }
    
    // Show the notification
    const title = data.title || 'New Notification';
    const options = {
      body: data.body || 'You have a new notification',
      icon: '/static/images/logo.png',
      badge: '/static/images/default_profile.png',
      data: data.data || {},
      actions: [
        {
          action: 'view',
          title: 'View'
        },
        {
          action: 'complete',
          title: 'Complete'
        },
        {
          action: 'dismiss',
          title: 'Dismiss'
        }
      ],
      vibrate: [100, 50, 100],
      tag: data.data?.assignment_id || 'general',  // Group by assignment ID
      renotify: true,  // Notify even if replacing an existing notification
      requireInteraction: true,  // Notification stays until user interacts with it
      timestamp: data.timestamp || Date.now()
    };
    
    console.log('Showing notification:', { title, options });
    
    event.waitUntil(
      self.registration.showNotification(title, options)
        .then(() => {
          console.log('Notification shown successfully');
        })
        .catch(error => {
          console.error('Failed to show notification:', error);
        })
    );
  } catch (error) {
    console.error('Error handling push event:', error);
  }
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
  console.log('Notification click received', event);
  
  // Close the notification
  event.notification.close();
  
  // Handle action buttons
  const url = event.notification.data.url || '/team/manage';
  const assignmentId = event.notification.data.assignment_id;
  
  // Default action (clicking the notification body) or View action
  if (!event.action || event.action === 'view') {
    // Open or focus on the application window
    event.waitUntil(
      clients.matchAll({ type: 'window', includeUncontrolled: true })
        .then((clientList) => {
          // Check if there's already a window/tab open with the target URL
          for (const client of clientList) {
            if (client.url.includes(url) && 'focus' in client) {
              return client.focus();
            }
          }
          // If no existing window/tab, open a new one
          return clients.openWindow(url);
        })
    );
  } 
  // Complete action - mark the assignment as completed
  else if (event.action === 'complete' && assignmentId) {
    event.waitUntil(
      fetch(`/team/assignments/${assignmentId}/status`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: 'completed' })
      })
      .then(response => {
        if (response.ok) {
          // Show a confirmation notification
          return self.registration.showNotification('Assignment Completed', {
            body: 'The assignment has been marked as completed',
            icon: '/static/images/logo.png',
            tag: 'status-update-' + assignmentId
          });
        } else {
          return self.registration.showNotification('Action Failed', {
            body: 'Could not mark assignment as completed. Please try again.',
            icon: '/static/images/logo.png',
            tag: 'status-update-error-' + assignmentId
          });
        }
      })
      .catch(error => {
        console.error('Error updating status:', error);
        return self.registration.showNotification('Network Error', {
          body: 'Could not connect to the server. Please try again later.',
          icon: '/static/images/logo.png',
          tag: 'network-error'
        });
      })
    );
  }
});
