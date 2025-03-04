const CACHE_NAME = 'scouting-app-v1';
const STATIC_CACHE_NAME = 'scouting-app-static-v1';
const DYNAMIC_CACHE_NAME = 'scouting-app-dynamic-v1';

const STATIC_ASSETS = [
  '/static/css/global.css',
  '/static/css/index.css',
  '/static/js/Canvas.js',
  '/static/images/field-2025.png',
  '/static/images/default_profile.png',
  '/static/js/notifications.js',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
  );
});

self.addEventListener('fetch', (event) => {
  const {request} = event;

  // Handle static assets (cache-first strategy)
  if (STATIC_ASSETS.some(asset => request.url.includes(asset))) {
    event.respondWith(
      caches.match(request)
        .then(cachedResponse => {
          return cachedResponse || fetch(request).then(response => {
            return caches.open(STATIC_CACHE_NAME)
              .then(cache => {
                cache.put(request, response.clone());
                return response;
              });
          });
        })
    );
    return;
  }

  // For API requests and dynamic content (network-first strategy)
  if (request.method === 'GET') {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Clone the response before caching it
          const responseToCache = response.clone();
          
          caches.open(DYNAMIC_CACHE_NAME)
            .then(cache => {
              cache.put(request, responseToCache);
            });
            
          return response;
        })
        .catch(() => {
          // If network fails, try to get from cache
          return caches.match(request);
        })
    );
    return;
  }

  // For other requests (POST, PUT, DELETE), don't cache
  event.respondWith(fetch(request));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    Promise.all([
      // Clear old caches
      caches.keys().then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (![STATIC_CACHE_NAME, DYNAMIC_CACHE_NAME].includes(cacheName)) {
              return caches.delete(cacheName);
            }
          })
        );
      }),
      // Claim clients immediately
      clients.claim()
    ])
  );
});

// Cache for tracking dismissed notifications
const dismissedNotifications = new Set();

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

    // Check if this notification has been dismissed
    const notificationId = data.data?.assignment_id || 'general';
    if (dismissedNotifications.has(notificationId)) {
      console.log('Notification was previously dismissed:', notificationId);
      return;
    }
    
    // Show the notification
    const title = data.title || 'New Notification';
    const options = {
      body: data.body || 'You have a new notification',
      icon: '/static/images/logo.png',
      badge: '/static/images/default_profile.png',
      data: {
        ...data.data || {},
        notificationId: notificationId
      },
      actions: data.data?.type === 'new_assignment' ? [
        {
          action: 'view',
          title: 'View Assignment'
        },
        {
          action: 'dismiss',
          title: 'Dismiss'
        }
      ] : [
        {
          action: 'view',
          title: 'View'
        },
        {
          action: 'complete',
          title: 'Marked as Complete'
        },
        {
          action: 'dismiss',
          title: 'Dismiss'
        }
      ],
      vibrate: [100, 50, 100],
      tag: notificationId,  // Use consistent tag for grouping
      renotify: false,  // Don't notify again for the same tag
      requireInteraction: false,  // Notification stays until user interacts with it
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
  
  const {notificationId} = event.notification.data;
  
  // Close the notification
  event.notification.close();
  
  // Add to dismissed set for ALL actions
  dismissedNotifications.add(notificationId);
  
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
