// Check offline status immediately when script runs (before any events)
(function checkOfflineStatus() {
    if (!navigator.onLine || localStorage.getItem('offlineMode') === 'true') {
        document.body.classList.add('offline');
        // We'll call showOfflineIndicators as soon as DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', showOfflineIndicatorsImmediately);
        } else {
            showOfflineIndicatorsImmediately();
        }
    }
})();

function showOfflineIndicatorsImmediately() {
    const navOfflineIndicator = document.getElementById('nav-offline-indicator');
    if (navOfflineIndicator) {
        navOfflineIndicator.classList.remove('hidden');
    }

    const mobileOfflineIndicator = document.getElementById('mobile-offline-indicator');
    if (mobileOfflineIndicator) {
        mobileOfflineIndicator.classList.remove('hidden');
    }

    // Store offline state in localStorage to persist across page changes
    localStorage.setItem('offlineMode', 'true');
}

if ('serviceWorker' in navigator) {
    // Track the current version of content
    const APP_VERSION = document.currentScript.dataset.appVersion;

    // Store the current version in localStorage
    if (!localStorage.getItem('appVersion') || 
        localStorage.getItem('appVersion') !== APP_VERSION) {
        // Version changed, clear caches
        if ('caches' in window) {
            caches.keys().then(cacheNames => {
                return Promise.all(
                    cacheNames.map(cacheName => {
                        return caches.delete(cacheName);
                    })
                );
            });
        }
        localStorage.setItem('appVersion', APP_VERSION);
    }

    let reloadForUpdate = false;
    window.addEventListener('load', () => {
        const registerServiceWorker = async () => {
            try {
                const registration = await navigator.serviceWorker.register('/service-worker.js', {
                    scope: '/',
                    updateViaCache: 'none' // Don't use cached service worker
                });

                console.log('ServiceWorker registration successful with scope: ', registration.scope);

                // Check if there's an updated service worker waiting
                if (registration.waiting) {
                    console.log('New service worker is waiting to activate');
                    notifyUserOfUpdate(registration.waiting);
                }

                // Listen for new service worker installation
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    console.log('Service Worker update found!');

                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            console.log('New content is available; please refresh.');
                            notifyUserOfUpdate(newWorker);
                        }
                    });
                });

                // Force update check every 5 minutes if the tab remains open
                setInterval(() => {
                    registration.update();
                    console.log('Checking for service worker updates...');
                }, 5 * 60 * 1000);

                // Check for updates immediately
                setTimeout(() => {
                    registration.update();
                }, 3000);

                // Listen for controller change (new service worker took over)
                navigator.serviceWorker.addEventListener('controllerchange', () => {
                    // Background updates must not discard an unfinished scouting form.
                    if (reloadForUpdate) window.location.reload();
                });

                // Listen for messages from the service worker
                navigator.serviceWorker.addEventListener('message', event => {
                    if (event.data && event.data.type === 'OFFLINE_STATUS') {
                        if (event.data.isOffline) {
                            document.body.classList.add('offline');
                            showOfflineIndicators();
                        } else {
                            document.body.classList.remove('offline');
                            hideOfflineIndicators();
                        }
                    }
                });

            } catch (error) {
                console.error('ServiceWorker registration failed: ', error);
            }
        };

        registerServiceWorker();
    });

    // Function to notify the user about an update
    function notifyUserOfUpdate(worker) {
        if (document.getElementById('update-banner')) return;
        const updateBanner = document.createElement('div');
        updateBanner.id = 'update-banner';
        updateBanner.classList.add('fixed', 'bottom-0', 'left-0', 'right-0', 'bg-blue-500', 'text-white', 'p-4', 'flex', 'justify-between', 'items-center', 'z-50');
        updateBanner.innerHTML = `
            <div>
                <strong>Update Available!</strong> Refresh to see the latest version.
            </div>
            <div class="flex space-x-2">
                <button id="update-now" class="bg-white text-blue-500 px-4 py-2 rounded hover:bg-blue-50 transition-colors">
                    Update Now
                </button>
                <button id="update-later" class="text-white border border-white px-4 py-2 rounded hover:bg-blue-600 transition-colors">
                    Later
                </button>
            </div>
        `;

        document.body.appendChild(updateBanner);

        document.getElementById('update-now').addEventListener('click', () => {
            reloadForUpdate = true;
            if (worker.state === 'activated') window.location.reload();
            else worker.postMessage({ action: 'skipWaiting' });
            updateBanner.remove();
        });

        document.getElementById('update-later').addEventListener('click', () => {
            updateBanner.remove();
        });
    }

    // Function to show offline indicators
    function showOfflineIndicators() {
        // Show offline indicators in top navigation
        const navOfflineIndicator = document.getElementById('nav-offline-indicator');
        if (navOfflineIndicator) {
            navOfflineIndicator.classList.remove('hidden');
        }

        // Show mobile offline indicator
        const mobileOfflineIndicator = document.getElementById('mobile-offline-indicator');
        if (mobileOfflineIndicator) {
            mobileOfflineIndicator.classList.remove('hidden');
        }

        // Store offline state in localStorage to persist across page changes
        localStorage.setItem('offlineMode', 'true');
    }

    // Function to hide offline indicators
    function hideOfflineIndicators() {
        // Hide offline indicators in top navigation
        const navOfflineIndicator = document.getElementById('nav-offline-indicator');
        if (navOfflineIndicator) {
            navOfflineIndicator.classList.add('hidden');
        }

        // Hide mobile offline indicator
        const mobileOfflineIndicator = document.getElementById('mobile-offline-indicator');
        if (mobileOfflineIndicator) {
            mobileOfflineIndicator.classList.add('hidden');
        }

        // Remove offline state from localStorage
        localStorage.removeItem('offlineMode');
    }

    // Add offline/online detection
    window.addEventListener('online', () => {
        document.body.classList.remove('offline');
        hideOfflineIndicators();

        // Sync any pending requests and check for updates
        navigator.serviceWorker.ready.then(registration => {
            registration.update();
        });
    });

    window.addEventListener('offline', () => {
        document.body.classList.add('offline');
        showOfflineIndicators();
    });

    // The following check runs on every page load, including refreshes and navigation
    // It's redundant with the IIFE at the top but provides a fallback
    document.addEventListener('DOMContentLoaded', () => {
        // Double-check offline status from localStorage and network state
        if (localStorage.getItem('offlineMode') === 'true' || !navigator.onLine) {
            document.body.classList.add('offline');
            showOfflineIndicators();
        }

        // Also double-check online status to handle case where connection was restored
        // but localStorage wasn't properly cleared
        if (navigator.onLine && localStorage.getItem('offlineMode') === 'true') {
            // Verify online status by making a tiny request
            fetch('/static/logo.png?checkOnline=' + Date.now(), { 
                method: 'HEAD',
                cache: 'no-store'
            })
            .then(() => {
                // If fetch succeeds, we're definitely online
                hideOfflineIndicators();
            })
            .catch(() => {
                // If fetch fails, we're probably still offline
                showOfflineIndicators();
            });
        }
    });

    // Add offline support to fetch requests
    const originalFetch = window.fetch.bind(window);
    let onlineProbe = null;
    window.fetch = function(input, init) {
        return originalFetch(input, init)
            .then(response => {
                // If a successful response, we must be online
                if (response.ok && !onlineProbe &&
                    localStorage.getItem('offlineMode') === 'true') {
                    onlineProbe = originalFetch('/static/logo.png?checkOnline=' + Date.now(), {
                        method: 'HEAD', cache: 'no-store'
                    }).then(probe => {
                        if (probe.ok) {
                            document.body.classList.remove('offline');
                            hideOfflineIndicators();
                        }
                    }).catch(() => {}).finally(() => { onlineProbe = null; });
                }
                return response;
            })
            .catch(error => {
                if (error.name === 'AbortError') throw error;
                console.error('Fetch error:', error);

                if (!navigator.onLine) {
                    // Ensure the offline indicator is shown
                    document.body.classList.add('offline');
                    showOfflineIndicators();

                    // For JSON requests, return a valid offline response
                    const headers = new Headers(init?.headers || (input instanceof Request ? input.headers : undefined));
                    if (headers.get('Accept')?.includes('application/json') ||
                        headers.get('Content-Type')?.includes('application/json')) {
                        return new Response(JSON.stringify({
                            error: 'offline',
                            message: 'You are offline. Please retry this action when you reconnect.'
                        }), {
                            status: 503,
                            headers: { 'Content-Type': 'application/json' }
                        });
                    }
                }

                throw error;
            });
    };
}
