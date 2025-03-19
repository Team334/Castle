/**
 * PWA Installation Handler
 * Manages the installation prompt for Progressive Web App
 */

(function() {
  // Use a closure to avoid global variables
  let deferredPrompt;
  const installButton = document.getElementById('installPWA');

  // Hide the install button initially
  if (installButton) {
    installButton.style.display = 'none';
  }

  // Listen for the beforeinstallprompt event
  window.addEventListener('beforeinstallprompt', (e) => {
    console.log('👋 Install prompt is available');
    // Store the event for later use
    deferredPrompt = e;
    
    // Show the install button if it exists
    if (installButton) {
      installButton.style.display = 'block';
    }
  });

  // Function to trigger the installation prompt
  function installPWA() {
    if (!deferredPrompt) {
      console.log('❌ Install prompt not available');
      const message = document.getElementById('installMessage');
      if (message) {
        message.textContent = 'This app is either already installed or cannot be installed on this device/browser.';
        message.classList.remove('hidden');
        setTimeout(() => {
          message.classList.add('hidden');
        }, 3000);
      }
      return;
    }
    
    console.log('🚀 Showing install prompt');
    // Show the installation prompt
    deferredPrompt.prompt();
    
    // Wait for the user to respond to the prompt
    deferredPrompt.userChoice.then((choiceResult) => {
      if (choiceResult.outcome === 'accepted') {
        console.log('✅ User accepted the install prompt');
      } else {
        console.log('❌ User dismissed the install prompt');
      }
      
      // Clear the deferred prompt
      deferredPrompt = null;
      
      // Hide the install button as it's no longer needed
      if (installButton) {
        installButton.style.display = 'none';
      }
    });
  }

  // Add click event to the install button if it exists
  document.addEventListener('DOMContentLoaded', () => {
    console.log('🔍 Checking for install button');
    const installButton = document.getElementById('installPWA');
    if (installButton) {
      console.log('✅ Install button found, adding click event');
      installButton.addEventListener('click', installPWA);
    } else {
      console.log('❌ Install button not found');
    }
  });

  // Check if the PWA is already installed
  window.addEventListener('appinstalled', (e) => {
    console.log('🎉 PWA was installed');
    // Hide the install button as it's no longer needed
    if (installButton) {
      installButton.style.display = 'none';
    }
  });
})(); 