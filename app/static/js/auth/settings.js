// Toast notification function
function showNotification(message, type = "info") {
  const notificationArea = document.getElementById("notification-area");
  if (!notificationArea) return;

  const colors = {
    success: {
      bg: "bg-green-50",
      text: "text-green-800",
      border: "border-green-300",
      icon: "text-green-600",
    },
    error: {
      bg: "bg-red-50",
      text: "text-red-800",
      border: "border-red-300",
      icon: "text-red-600",
    },
    warning: {
      bg: "bg-yellow-50",
      text: "text-yellow-800",
      border: "border-yellow-300",
      icon: "text-yellow-600",
    },
    info: {
      bg: "bg-blue-50 dark:bg-blue-900/20",
      text: "text-blue-800",
      border: "border-blue-300",
      icon: "text-blue-600",
    },
  };

  const icons = {
    success:
      '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"></path>',
    error:
      '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>',
    warning:
      '<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>',
    info: '<path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>',
  };

  const color = colors[type] || colors.info;
  const icon = icons[type] || icons.info;

  const notification = document.createElement("div");
  notification.className = `flex items-center p-4 rounded-lg shadow-lg dark:shadow-none ${color.bg} ${color.text} border-2 ${color.border} animate-slide-in`;
  notification.style.cssText =
    "animation: slideIn 0.3s ease-out; min-width: 300px;";

  notification.innerHTML = `
    <svg class="w-6 h-6 mr-3 flex-shrink-0 ${color.icon}" fill="currentColor" viewBox="0 0 20 20">
      ${icon}
    </svg>
    <p class="text-sm font-medium flex-1">${message}</p>
    <button type="button" class="ml-3 -mx-1.5 -my-1.5 rounded-lg p-1.5 inline-flex h-8 w-8 ${color.icon} hover:bg-opacity-20" onclick="this.parentElement.remove()">
      <span class="sr-only">Dismiss</span>
      <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
      </svg>
    </button>
  `;

  notificationArea.appendChild(notification);

  // Auto-dismiss after 5 seconds
  setTimeout(() => {
    notification.style.opacity = "0";
    notification.style.transition = "opacity 300ms";
    setTimeout(() => notification.remove(), 300);
  }, 5000);
}

// Add animation keyframe
const style = document.createElement("style");
style.textContent = `
  @keyframes slideIn {
    from {
      transform: translateX(100%);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
`;
document.head.appendChild(style);

// Handle form submission
document.querySelector("form").addEventListener("submit", function (e) {
  e.preventDefault(); // Prevent default form submission

  // Create FormData object from the form
  const formData = new FormData(this);

  // Submit the form using fetch
  fetch(window.location.href, {
    method: "POST",
    body: formData,
    // Don't set Content-Type header when using FormData - it will set it automatically with boundary
  })
    .then((response) => {
      if (response.redirected) {
        // If the server redirects, follow that redirect
        window.location.href = response.url;
      } else {
        // If not redirected but successful, refresh the page to show updated info
        window.location.reload();
      }
    })
    .catch((error) => {
      console.error("Error submitting form:", error);
      showNotification(
        "An error occurred while saving your changes. Please try again.",
        "error",
      );
    });
});

document
  .getElementById("profile_picture")
  .addEventListener("change", function (e) {
    const file = e.target.files[0];

    // Check file size (6MB = 6 * 1024 * 1024 bytes)
    const maxSize = 6 * 1024 * 1024;
    if (file && file.size > maxSize) {
      showNotification("File size must be less than 6MB", "error");
      this.value = ""; // Clear the file input
      document.getElementById("upload-info").textContent = "";
      return;
    }

    if (file) {
      // Update file name display
      document.getElementById("upload-info").textContent = file.name;

      // Show immediate preview first before compression starts
      const reader = new FileReader();
      reader.onload = function (e) {
        document.querySelector(".profile-preview").src = e.target.result;
      };
      reader.readAsDataURL(file);

      // Then use Compressor.js to compress the image in background
      try {
        new Compressor(file, {
          quality: 0.8, // 0.8 means 80% quality
          maxWidth: 800,
          maxHeight: 800,
          mimeType: "image/jpeg",
          success(result) {
            // Replace the file in the input with the compressed one
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(
              new File([result], file.name, { type: "image/jpeg" }),
            );
            document.getElementById("profile_picture").files =
              dataTransfer.files;
            console.log("Image compressed successfully");
          },
          error(err) {
            console.error("Image compression failed:", err);
            // No need to update preview again since we already did it above
          },
        });
      } catch (err) {
        console.error("Error initializing compressor:", err);
        // The preview is already shown above, so no need for fallback here
      }
    }
  });

let usernameCheckTimeout;
const currentUsername = document.currentScript.dataset.currentUsername;

function checkUsername(username) {
  // Clear any existing timeout
  clearTimeout(usernameCheckTimeout);

  const statusDiv = document.getElementById("username-status");

  // Don't check if username hasn't changed
  if (username === currentUsername) {
    statusDiv.innerHTML = "";
    return;
  }

  // Check username length and characters
  if (username.length < 3) {
    statusDiv.innerHTML =
      '<span class="text-yellow-600">Username must be at least 3 characters long</span>';
    return;
  }

  if (!/^[a-zA-Z0-9_]+$/.test(username)) {
    statusDiv.innerHTML =
      '<span class="text-red-600">Username can only contain letters, numbers, and underscores</span>';
    return;
  }

  // Set a timeout to avoid too many requests
  usernameCheckTimeout = setTimeout(() => {
    statusDiv.innerHTML =
      '<span class="text-blue-600">Checking availability...</span>';

    fetch("/auth/check_username", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify({ username: username }),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.available) {
          statusDiv.innerHTML =
            '<span class="text-green-600">✓ Username is available</span>';
        } else {
          statusDiv.innerHTML =
            '<span class="text-red-600">✗ Username is already taken</span>';
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        statusDiv.innerHTML =
          '<span class="text-red-600">Error checking username availability</span>';
      });
  }, 500); // Wait 500ms after user stops typing before checking
}

function changePassword() {
  const currentPassword = document.getElementById("current_password").value;
  const newPassword = document.getElementById("new_password").value;
  const confirmPassword = document.getElementById(
    "confirm_new_password",
  ).value;

  // Client-side validation
  if (!currentPassword || !newPassword || !confirmPassword) {
    showNotification("All password fields are required", "warning");
    return;
  }

  if (newPassword !== confirmPassword) {
    showNotification("New passwords do not match", "error");
    return;
  }

  if (newPassword.length < 8) {
    showNotification(
      "New password must be at least 8 characters long",
      "error",
    );
    return;
  }

  if (newPassword === currentPassword) {
    showNotification(
      "New password must be different from current password",
      "error",
    );
    return;
  }

  // Send request
  fetch("/auth/change_password", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.success) {
        showNotification(
          data.message || "Password changed successfully",
          "success",
        );
        // Redirect to login if logout is required
        if (data.redirect) {
          setTimeout(() => {
            window.location.href = data.redirect;
          }, 1500);
        } else {
          // Clear the password fields
          document.getElementById("current_password").value = "";
          document.getElementById("new_password").value = "";
          document.getElementById("confirm_new_password").value = "";
        }
      } else {
        showNotification(
          data.message || "Failed to change password",
          "error",
        );
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      showNotification(
        "An error occurred while changing your password",
        "error",
      );
    });
}

function confirmDeleteAccount() {
  if (
    confirm(
      "Are you sure you want to delete your account? This action cannot be undone.",
    )
  ) {
    fetch("/auth/delete_account", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.success) {
          showNotification(
            "Account deleted successfully. Redirecting...",
            "success",
          );
          setTimeout(() => {
            window.location.href = data.redirect;
          }, 1500);
        } else {
          showNotification(
            data.message || "Failed to delete account",
            "error",
          );
        }
      })
      .catch((error) => {
        console.error("Error:", error);
        showNotification(
          "An error occurred while deleting your account",
          "error",
        );
      });
  }
}
