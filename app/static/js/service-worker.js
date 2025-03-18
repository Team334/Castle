const CACHE_NAME = 'castle-app-v4';
const STATIC_CACHE_NAME = 'castle-app-static-v4';
const DYNAMIC_CACHE_NAME = 'castle-app-dynamic-v4';
const PAGE_CACHE_NAME = 'castle-app-pages-v4';

const CACHE_VERSION = '4'; // Increment this when making changes

// Add timestamped version query parameter to bust cache 
const CACHE_TIMESTAMP = new Date().getTime();

const STATIC_ASSETS = [
  '/static/css/global.css',
  '/static/css/index.css',
  '/static/js/Canvas.js',
  '/static/images/field-2025.png',
  '/static/images/default_profile.png',
  '/static/js/notifications.js',
  '/static/logo.png',
  '/static/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/offline.html', // Critical for offline support
];

// Files that should not be cached
const NO_CACHE_URLS = [
  '/auth/login',
  '/auth/register'
];

// Make sure offline page is cached first during installation
const CRITICAL_ASSETS = [
  '/offline.html',
  '/static/logo.png'
];

// Listen for the skipWaiting message from the client
self.addEventListener('message', (event) => {
  if (event.data && event.data.action === 'skipWaiting') {
    console.log('[ServiceWorker] Skip waiting and activate immediately');
    self.skipWaiting();
  }
});

// Periodically check connectivity and inform clients
function checkConnectivityAndNotify() {
  let isOnline = true;
  
  fetch('/static/logo.png?checkOnline=' + Date.now(), { 
    method: 'HEAD',
    cache: 'no-store'
  })
  .then(() => {
    isOnline = true;
  })
  .catch(() => {
    isOnline = false;
  })
  .finally(() => {
    // Notify all clients about offline status
    self.clients.matchAll().then(clients => {
      clients.forEach(client => {
        client.postMessage({
          type: 'OFFLINE_STATUS',
          isOffline: !isOnline
        });
      });
    });
  });
}

// Network status check interval (every 30 seconds)
setInterval(checkConnectivityAndNotify, 30 * 1000);

// Cache any asset or page that's visited
self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Installing new service worker version', CACHE_VERSION);
  event.waitUntil(
    // First cache critical assets
    caches.open(STATIC_CACHE_NAME)
      .then((cache) => {
        console.log('[ServiceWorker] Caching critical assets first');
        return cache.addAll(CRITICAL_ASSETS);
      })
      .then(() => {
        console.log('[ServiceWorker] Critical assets cached successfully');
        // Then cache all other static assets
        return caches.open(STATIC_CACHE_NAME)
          .then((cache) => {
            console.log('[ServiceWorker] Caching remaining static assets');
            
            // Add timestamp to URLs to bust cache
            const timeStampedAssets = STATIC_ASSETS.filter(asset => !CRITICAL_ASSETS.includes(asset))
              .map(url => {
                // Don't add timestamp to images and fonts
                if (url.match(/\.(png|jpg|jpeg|gif|svg|woff|woff2|ttf|otf)$/)) {
                  return url;
                }
                // Add timestamp to CSS, JS, and HTML files
                return url.includes('?') ? `${url}&v=${CACHE_TIMESTAMP}` : `${url}?v=${CACHE_TIMESTAMP}`;
              });
            
            return cache.addAll(timeStampedAssets);
          });
      })
      .then(() => {
        console.log('[ServiceWorker] Installation completed');
        return self.skipWaiting();
      })
  );
});

// Handle fetch errors specifically and notify clients when offline
function handleFetchError(error, request) {
  console.error('[ServiceWorker] Fetch error:', error, request.url);
  
  // Always notify clients that we're offline when a fetch fails
  self.clients.matchAll().then(clients => {
    clients.forEach(client => {
      client.postMessage({
        type: 'OFFLINE_STATUS',
        isOffline: true
      });
    });
  });
  
  // Now handle the error based on the request type
  if (request.headers.get('accept')?.includes('application/json')) {
    return new Response(JSON.stringify({
      error: 'offline',
      message: 'You are offline. This action will be synced when you reconnect.'
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  // For HTML page requests, serve the offline page
  if (request.mode === 'navigate' || 
      (request.headers.get('accept') && 
       request.headers.get('accept').includes('text/html'))) {
    // Double-check that offline.html is in the cache
    return caches.match('/offline.html')
      .then(cachedOfflinePage => {
        if (cachedOfflinePage) {
          return cachedOfflinePage;
        }
        // If offline.html isn't cached (shouldn't happen), create a simple response
        return new Response(
          `<!DOCTYPE html>
           <html>
             <head>
               <title>You're Offline</title>
               <meta name="viewport" content="width=device-width, initial-scale=1">
               <style>
                 body { font-family: sans-serif; text-align: center; padding: 20px; }
                 h1 { color: #3b82f6; }
               </style>
             </head>
             <body>
               <h1>You're Offline</h1>
               <p>Please check your internet connection and try again.</p>
               <button onclick="window.location.reload()">Retry</button>
             </body>
           </html>`,
          { 
            headers: { 'Content-Type': 'text/html' },
            status: 200 
          }
        );
      });
  }
  
  // For image requests, serve a default image
  if (request.url.match(/\.(jpg|jpeg|png|gif|svg)$/)) {
    return caches.match('/static/logo.png');
  }
  
  // For CSS/JS requests
  return new Response('/* Offline content unavailable */', {
    status: 200,
    headers: { 'Content-Type': 'text/css' }
  });
}

self.addEventListener('fetch', (event) => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    // For non-GET requests, try network with graceful offline handling
    event.respondWith(
      fetch(event.request).catch(error => {
        console.log('[ServiceWorker] Non-GET request failed:', event.request.url, error);
        return handleFetchError(error, event.request);
      })
    );
    return;
  }

  const url = new URL(event.request.url);
  
  // Special handling for offline.html - always serve from cache if available
  if (url.pathname === '/offline.html') {
    event.respondWith(
      caches.match('/offline.html')
        .then(cachedResponse => {
          return cachedResponse || fetch(event.request);
        })
        .catch(() => {
          // Fallback if offline.html isn't in the cache
          return new Response(
            `<!DOCTYPE html><html><body><h1>You're Offline</h1><p>Unable to load offline page.</p></body></html>`,
            { headers: { 'Content-Type': 'text/html' } }
          );
        })
    );
    return;
  }
  
  // Don't cache cross-origin requests
  if (url.origin !== self.location.origin) {
    event.respondWith(
      fetch(event.request).catch(error => {
        console.log('[ServiceWorker] Cross-origin fetch failed:', url.href, error);
        return handleFetchError(error, event.request);
      })
    );
    return;
  }

  // Handle navigation requests (HTML pages)
  if (event.request.mode === 'navigate' || 
      (event.request.method === 'GET' && 
       event.request.headers.get('accept') && 
       event.request.headers.get('accept').includes('text/html'))) {
    
    // Skip URLs that shouldn't be cached
    if (NO_CACHE_URLS.some(nocacheUrl => event.request.url.includes(nocacheUrl))) {
      event.respondWith(
        fetch(event.request).catch(() => {
          return handleFetchError(new Error('Network failed'), event.request);
        })
      );
      return;
    }

    // For HTML pages, use cache-first strategy but update cache in background
    event.respondWith(
      caches.match(event.request)
        .then(cachedResponse => {
          // Clone the request because it can only be used once
          const fetchPromise = fetch(event.request.clone())
            .then(networkResponse => {
              if (networkResponse.ok) {
                // Update the cache with the new version
                const responseToCache = networkResponse.clone();
                caches.open(PAGE_CACHE_NAME)
                  .then(cache => {
                    console.log('[ServiceWorker] Caching page:', event.request.url);
                    cache.put(event.request, responseToCache);
                  });
              }
              return networkResponse;
            })
            .catch(error => {
              console.error('[ServiceWorker] Fetch failed:', error);
              // If cache exists, it will be returned by the outer function
              // Otherwise, this will be caught by the outer catch
              throw error;
            });

          // Return cached response if available, otherwise wait for network
          return cachedResponse || fetchPromise;
        })
        .catch(error => {
          // If both cache and network fail, handle gracefully
          return handleFetchError(error, event.request);
        })
    );
    return;
  }

  // For static assets
  if (STATIC_ASSETS.some(asset => event.request.url.includes(asset))) {
    event.respondWith(
      caches.match(event.request)
        .then(cachedResponse => {
          if (cachedResponse) {
            return cachedResponse;
          }
          return fetch(event.request)
            .then(response => {
              // Clone the response
              const responseToCache = response.clone();
              caches.open(STATIC_CACHE_NAME)
                .then(cache => {
                  cache.put(event.request, responseToCache);
                });
              return response;
            })
            .catch(error => {
              console.error('[ServiceWorker] Static fetch failed:', error);
              if (event.request.url.match(/\.(jpg|jpeg|png|gif|svg)$/)) {
                return caches.match('/static/logo.png');
              }
              return new Response('/* Fallback content */', {
                headers: { 'Content-Type': 'text/css' }
              });
            });
        })
    );
    return;
  }

  // For all other GET requests - API calls, JSON, etc.
  event.respondWith(
    caches.match(event.request)
      .then(cachedResponse => {
        if (cachedResponse) {
          // Update the cache in the background
          fetch(event.request)
            .then(networkResponse => {
              caches.open(DYNAMIC_CACHE_NAME)
                .then(cache => {
                  cache.put(event.request, networkResponse.clone());
                });
            })
            .catch(() => {
              // Silent catch - no need to do anything if background update fails
            });
          return cachedResponse;
        }

        // Nothing in cache, try network
        return fetch(event.request)
          .then(networkResponse => {
            // Clone the response
            const responseToCache = networkResponse.clone();
            caches.open(DYNAMIC_CACHE_NAME)
              .then(cache => {
                cache.put(event.request, responseToCache);
              });
            return networkResponse;
          })
          .catch(error => {
            console.error('[ServiceWorker] Fetch failed:', error);
            
            // For API requests that failed, return a valid offline response
            if (event.request.url.includes('/api/') || 
                event.request.headers.get('accept')?.includes('application/json')) {
              return new Response(JSON.stringify({
                error: 'offline',
                message: 'You are offline. This action will be synced when you reconnect.'
              }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
              });
            }
            
            // For other failed requests, try to match a cached response
            return caches.match('/offline.html');
          });
      })
  );
});

// Activate event to clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activating new service worker version', CACHE_VERSION);
  
  event.waitUntil(
    Promise.all([
      // Clear old caches
      caches.keys().then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            // Delete any cache that doesn't match our current version
            if (![STATIC_CACHE_NAME, DYNAMIC_CACHE_NAME, PAGE_CACHE_NAME].includes(cacheName)) {
              console.log('[ServiceWorker] Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      }),
      // Claim clients immediately so the new service worker takes over right away
      self.clients.claim().then(() => {
        console.log('[ServiceWorker] Claimed all clients');
        
        // Notify all clients that the service worker has been updated
        return self.clients.matchAll().then(clients => {
          return Promise.all(clients.map(client => {
            return client.postMessage({
              type: 'SW_UPDATED',
              version: CACHE_VERSION
            });
          }));
        });
      })
    ])
    .then(() => {
      console.log('[ServiceWorker] Activation completed');
    })
  );
});

// Cache for tracking dismissed notifications
const dismissedNotifications = new Set();

self.addEventListener('push', (event) => {
  console.log('[ServiceWorker] Push event received', {
    data: event.data ? 'Has data' : 'No data',
    timestamp: new Date().toISOString()
  });
  
  try {
    if (!event.data) {
      console.warn('[ServiceWorker] Push event has no data');
      return;
    }
    
    // Parse the notification data
    let data;
    try {
      data = event.data.json();
      console.log('[ServiceWorker] Push data received:', {
        data,
        type: typeof data,
        hasTitle: !!data.title,
        hasBody: !!data.body,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      console.error('[ServiceWorker] Failed to parse push data as JSON:', error);
      const text = event.data.text();
      console.log('[ServiceWorker] Push data as text:', text);
      data = { title: 'New Notification', body: text };
    }

    // Check if this notification has been dismissed
    const notificationId = data.data?.assignment_id || 'general';
    if (dismissedNotifications.has(notificationId)) {
      console.log('[ServiceWorker] Notification was previously dismissed:', notificationId);
      return;
    }
    
    // Show the notification
    const title = data.title || 'New Notification';
    const options = {
      body: data.body || 'You have a new notification',
      icon: '/static/images/logo.png',  // Your app logo
      badge: '/static/images/logo.png',  // Small monochrome version of your logo
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
      tag: notificationId,
      renotify: false,
      requireInteraction: false,
      timestamp: data.timestamp || Date.now(),
      silent: false,
      dir: 'auto',
      lang: 'en-US',
      badge: '/static/images/badge.png',
      image: '/static/images/logo.png',
      applicationName: 'Castle',
    };
    
    console.log('[ServiceWorker] Showing notification:', { 
      title, 
      options,
      timestamp: new Date().toISOString()
    });
    
    event.waitUntil(
      self.registration.showNotification(title, options)
        .then(() => {
          console.log('[ServiceWorker] Notification shown successfully');
        })
        .catch(error => {
          console.error('[ServiceWorker] Failed to show notification:', error);
        })
    );
  } catch (error) {
    console.error('[ServiceWorker] Error handling push event:', error);
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

// Function to check if a request/response should skip the cache
function shouldSkipCache(request, response) {
  // Skip if response is an error
  if (!response || response.status !== 200) {
    return true;
  }
  
  // Skip if URL is in the no-cache list
  if (NO_CACHE_URLS.some(nocacheUrl => request.url.includes(nocacheUrl))) {
    return true;
  }
  
  // Skip caching for API responses that indicate errors
  if (response.headers.get('Content-Type')?.includes('application/json')) {
    // We'd need to clone and check the body, but for simplicity
    // we'll assume API responses are cacheable
    return false;
  }
  
  return false;
}
