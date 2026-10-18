// Single DOMContentLoaded event handler
document.addEventListener("DOMContentLoaded", function () {
  const { updatePathData } = initScoutFormCanvas({
    updateUIControls,
    // Load existing path data if available
    onCanvasReady(CanvasField) {
      const pathDataInput = document.getElementById("autoPathData");
      if (pathDataInput && pathDataInput.value) {
        try {
          let sanitizedValue = pathDataInput.value.trim();

          // Remove any potential HTML entities
          sanitizedValue = sanitizedValue
            .replace(/&quot;/g, '"')
            .replace(/&#34;/g, '"')
            .replace(/&#39;/g, "'")
            .replace(/&amp;/g, "&");

          // Check if the value is actually JSON
          if (
            sanitizedValue &&
            sanitizedValue !== "None" &&
            sanitizedValue !== "null"
          ) {
            // Try to fix common JSON formatting issues
            if (sanitizedValue.startsWith("'") && sanitizedValue.endsWith("'")) {
              sanitizedValue = sanitizedValue.slice(1, -1);
            }

            // Convert single quotes to double quotes
            sanitizedValue = sanitizedValue.replace(/'/g, '"');

            // Convert Python boolean values to JSON boolean values
            sanitizedValue = sanitizedValue
              .replace(/: True/g, ": true")
              .replace(/: False/g, ": false");

            try {
              const pathData = JSON.parse(sanitizedValue);

              if (Array.isArray(pathData)) {
                CanvasField.drawingHistory = pathData;
                CanvasField.redrawCanvas();
                CanvasField.showStatus("Existing path loaded");
              } else {
                CanvasField.drawingHistory = [];
                CanvasField.redrawCanvas();
                CanvasField.showStatus("Invalid path data format");
              }
            } catch (error) {
              console.error("Error loading existing path:", error);
              CanvasField.drawingHistory = [];
              CanvasField.redrawCanvas();
              CanvasField.showStatus("Error loading existing path");
            }
          } else {
            CanvasField.drawingHistory = [];
            CanvasField.redrawCanvas();
          }
        } catch (error) {
          console.error("Error loading existing path:", error);
          CanvasField.drawingHistory = [];
          CanvasField.redrawCanvas();
          CanvasField.showStatus("Error loading existing path");
        }
      }
    },
  });

  // Form submission handling
  const form = document.getElementById("scoutingForm");
  if (form) {
    form.addEventListener("submit", async function (e) {
      e.preventDefault();

      // Update path data before submission
      updatePathData();

      // const teamNumber = form.querySelector('input[name="team_number"]').value;
      // const eventCode = form.querySelector('input[name="event_code"]').value;
      // const matchNumber = form.querySelector('input[name="match_number"]').value;
      // const currentId = form.querySelector('input[name="current_id"]')?.value;

      // try {
      //     const response = await fetch(`/scouting/check_team?team=${teamNumber}&event=${eventCode}&match=${matchNumber}&current_id=${currentId}`);
      //     const data = await response.json();

      //     if (data.exists) {
      //         alert(`Team ${teamNumber} already exists in match ${matchNumber} for event ${eventCode}`);
      //         return;
      //     }

      //     form.submit();
      // } catch (error) {
      //     console.error('Error checking team:', error);
      //     form.submit();
      // }
      form.submit();
    });
  }

  // Tab switching functionality
  const tabButtons = document.querySelectorAll(".tab-button");
  const tabContents = document.querySelectorAll(".tab-content");

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      // Remove active class from all buttons and contents
      tabButtons.forEach((btn) => {
        btn.classList.remove("active", "border-blue-500", "text-blue-600");
        btn.classList.add("border-transparent", "text-gray-500");
      });
      tabContents.forEach((content) => content.classList.add("hidden"));

      // Add active class to clicked button and show corresponding content
      button.classList.add("active", "border-blue-500", "text-blue-600");
      button.classList.remove("border-transparent", "text-gray-500");
      const tabName = button.getAttribute("data-tab");
      const activeContent = document.querySelector(
        `.tab-content[data-tab="${tabName}"]`,
      );
      activeContent.classList.remove("hidden");
    });
  });
});

// Add the updateUIControls function at the end of the file
function updateUIControls(color, thickness) {
  if (color) {
    // Update color picker if it exists
    const colorPicker = document.getElementById("pathColorPicker");
    if (colorPicker) {
      colorPicker.value = color;
      // Update Coloris field and button
      const clrField = colorPicker.closest(".clr-field");
      if (clrField) {
        clrField.style.color = color;
        const button = clrField.querySelector("button");
        if (button) {
          button.style.backgroundColor = color;
        }
      }
    }
  }

  if (thickness) {
    // Update thickness slider if it exists
    const thicknessSlider = document.getElementById("pathThickness");
    const thicknessDisplay = document.getElementById("pathThicknessValue");
    if (thicknessSlider) {
      thicknessSlider.value = thickness;
      if (thicknessDisplay) {
        thicknessDisplay.textContent = thickness;
      }
    }
  }
}
