const CACHE_NAME = 'scouting-app-v1';
const ASSETS_TO_CACHE = [
  '/',
  '/static/css/global.css',
  '/static/css/index.css',
  '/static/js/Canvas.js',
  '/static/images/field-2025.png',
  '/static/images/default_profile.png',
];

console.log('Service worker script loaded');

self.addEventListener('install', (event) => {
  console.log('Service worker installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Cache opened, adding assets');
        return cache.addAll(ASSETS_TO_CACHE);
      })
      .then(() => {
        console.log('Service worker installation complete');
      })
      .catch(error => {
        console.error('Service worker installation failed:', error);
      })
  );
});

self.addEventListener('fetch', (event) => {
  try {
    // Log the request method for debugging
    console.log('Service worker handling fetch:', event.request.method, event.request.url);
    
    // Skip caching for POST requests and other non-GET methods
    if (event.request.method !== 'GET') {
      console.log('Non-GET request detected, passing through to network:', event.request.method, event.request.url);
      // For non-GET requests, just pass through to the network without caching
      event.respondWith(fetch(event.request));
      return;
    }

    event.respondWith(
      caches.match(event.request)
        .then((response) => {
          if (response) {
            console.log('Cache hit for:', event.request.url);
            return response;
          }
          
          console.log('Cache miss for:', event.request.url);
          
          // Clone the request to ensure it's safe to read when returning a response
          const fetchRequest = event.request.clone();
          
          return fetch(fetchRequest)
            .then((response) => {
              // Check if we received a valid response
              if (!response || response.status !== 200 || response.type !== 'basic') {
                return response;
              }
              
              // Clone the response to use it to save and return
              const responseToCache = response.clone();
              
              caches.open(CACHE_NAME)
                .then((cache) => {
                  try {
                    // Double-check that we're not trying to cache a non-GET request
                    if (event.request.method === 'GET') {
                      cache.put(event.request, responseToCache);
                    } else {
                      console.warn('Skipping cache for non-GET request:', event.request.url);
                    }
                  } catch (error) {
                    console.error('Failed to cache response:', error);
                  }
                })
                .catch(error => {
                  console.error('Failed to open cache:', error);
                });
                
              return response;
            })
            .catch(error => {
              console.error('Fetch failed:', error);
              // You could return a custom offline page here
              return new Response('Network request failed', {
                status: 503,
                statusText: 'Service Unavailable',
                headers: new Headers({
                  'Content-Type': 'text/plain'
                })
              });
            });
        })
    );
  } catch (error) {
    console.error('Error in fetch event handler:', error);
    // Fallback to network request
    event.respondWith(fetch(event.request));
  }
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
      icon: '/static/images/default_profile.png',
      badge: '/static/images/default_profile.png',
      data: data.data || {},
      actions: [
        {
          action: 'view',
          title: 'View Assignment'
        },
        {
          action: 'dismiss',
          title: 'Dismiss'
        }
      ],
      vibrate: [100, 50, 100],
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
  event.notification.close();

  if (event.action === 'dismiss') {
    return;
  }

  // Default action is to open the assignment
  const urlToOpen = event.notification.data.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window' })
      .then((clientList) => {
        // Check if there's already a window open
        for (const client of clientList) {
          if (client.url === urlToOpen && 'focus' in client) {
            return client.focus();
          }
        }
        // If no window is open, open a new one
        if (clients.openWindow) {
          return clients.openWindow(urlToOpen);
        }
      })
  );
});

// Handle push subscription change
self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil(
    fetch('/team/notifications/resubscribe', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        oldSubscription: event.oldSubscription ? event.oldSubscription.toJSON() : null,
        newSubscription: event.newSubscription ? event.newSubscription.toJSON() : null
      })
    })
  );
});