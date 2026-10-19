async function loadEventMatches(eventKey, signal) {
  const started = Date.now();
  while (true) {
    signal.throwIfAborted();
    const response = await fetch(`/api/tba/matches/${encodeURIComponent(eventKey)}`, {
      signal, cache: "no-store"
    });
    if (!response.ok) throw new Error("Failed to fetch matches");
    const matches = await response.json();
    if (matches?.error) throw new Error(matches.error);
    if (matches !== null || response.headers.get("X-Scouting-Pending") !== "true") return matches;
    if (Date.now() - started >= 60000) throw new Error("Match loading timed out");
    // Wait in the browser rather than occupying a server request thread.
    await new Promise((resolve, reject) => {
      const abort = () => {
        clearTimeout(timer);
        reject(signal.reason);
      };
      const timer = setTimeout(() => {
        signal.removeEventListener("abort", abort);
        resolve();
      }, 2000);
      signal.addEventListener("abort", abort, {once: true});
      if (signal.aborted) abort();
    });
  }
}

const updateMatchResult = () => {
  const allianceScore = parseInt(allianceScoreInput.value) || 0;
  const opponentScore = parseInt(opponentScoreInput.value) || 0;

  if (allianceScore > opponentScore) {
    matchResultInput.value = "won";
  } else if (allianceScore < opponentScore) {
    matchResultInput.value = "lost";
  } else {
    matchResultInput.value = "tie";
  }
};

document.addEventListener("DOMContentLoaded", function () {
  const { updatePathData } = initScoutFormCanvas({
    updateUIControls,
    resizeOnHome: true,
  });

  // Form submission handling
  const form = document.getElementById("scoutingForm");
  if (form) {
    form.addEventListener("submit", async function (e) {
      e.preventDefault();

      // Update path data before submission
      updatePathData();

      const teamNumber = teamSelect.value;
      const eventCode = eventSelect.value;
      const matchNumber = matchSelect.value;
      const alliance = allianceInput.value;

      if (!teamNumber || !eventCode || !matchNumber || !alliance) {
        alert("Please fill in all required fields");
        return;
      }

      // try {
      //     const response = await fetch(`/scouting/check_team?team=${teamNumber}&event=${eventCode}&match=${matchNumber}`);
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
      form.elements._event_key.value = eventSelect.options[eventSelect.selectedIndex]?.dataset.key || "";
      form.submit();
    });
  }

  // TBA Integration
  const eventSelect = document.getElementById("event_select");
  const matchSelect = document.getElementById("match_select");
  const teamSelect = document.getElementById("team_select");
  const allianceInput = document.getElementById("alliance_color");

  // Create searchable dropdown functionality
  function createSearchableDropdown(selectElement, placeholder) {
    const wrapper = document.createElement("div");
    wrapper.className = "relative";

    // Create search input
    const searchInput = document.createElement("input");
    searchInput.type = "text";
    searchInput.placeholder = `Search ${placeholder}...`;
    searchInput.className = "input";

    // Create dropdown container
    const dropdownContainer = document.createElement("div");
    dropdownContainer.className =
      "absolute z-30 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-zinc-200 bg-white py-1 text-sm shadow-md hidden dark:border-zinc-700 dark:bg-zinc-900";

    // Insert new elements
    selectElement.parentNode.insertBefore(wrapper, selectElement);
    wrapper.appendChild(searchInput);
    wrapper.appendChild(dropdownContainer);
    wrapper.appendChild(selectElement);
    selectElement.style.display = "none";

    // Track options
    let options = [];
    let filteredOptions = [];

    // Update options list
    function updateOptions() {
      options = Array.from(selectElement.options).map((opt) => ({
        value: opt.value,
        text: opt.text,
        dataset: opt.dataset,
        element: opt,
      }));
      filteredOptions = [...options];
    }

    // Render dropdown options
    function renderDropdown() {
      dropdownContainer.innerHTML = "";
      filteredOptions.forEach((opt, index) => {
        if (opt.value === "") {
          return;
        } // Skip placeholder option

        const option = document.createElement("div");
        option.className = "cursor-pointer px-3 py-2.5 text-zinc-700 hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-800";
        option.textContent = opt.text;

        option.addEventListener("click", () => {
          selectElement.value = opt.value;
          searchInput.value = opt.text;
          dropdownContainer.classList.add("hidden");
          // Trigger change event
          selectElement.dispatchEvent(new Event("change"));
        });

        dropdownContainer.appendChild(option);
      });
    }

    // Filter options based on search input
    function filterOptions(searchTerm) {
      searchTerm = searchTerm.toLowerCase();

      // Special handling for finals searches
      if (searchTerm.includes("final")) {
        // Check if searching for a specific finals match like "finals 1"
        const finalsMatchNumber = searchTerm.match(/finals?\s*(\d+)/i);

        if (finalsMatchNumber) {
          // If looking for a specific finals match
          const matchNumber = finalsMatchNumber[1];
          filteredOptions = options.filter(
            (opt) =>
              opt.text.toLowerCase().includes("finals") &&
              !opt.text.toLowerCase().includes("semi") &&
              opt.text.includes(matchNumber),
          );

          if (filteredOptions.length > 0) {
            renderDropdown();
            return;
          }
        }

        // If search contains "final" but not "semi", prioritize finals over semi-finals
        if (searchTerm.includes("final") && !searchTerm.includes("semi")) {
          const finalsOptions = options.filter(
            (opt) =>
              opt.text.toLowerCase().includes("finals") &&
              !opt.text.toLowerCase().includes("semi"),
          );

          if (finalsOptions.length > 0) {
            filteredOptions = finalsOptions;
            renderDropdown();
            return;
          }
        }
      }

      // Normal search behavior for other terms
      filteredOptions = options.filter((opt) =>
        opt.text.toLowerCase().includes(searchTerm),
      );
      renderDropdown();
    }

    // Event listeners
    searchInput.addEventListener("focus", () => {
      updateOptions();
      renderDropdown();
      dropdownContainer.classList.remove("hidden");
    });

    searchInput.addEventListener("input", (e) => {
      filterOptions(e.target.value);
      dropdownContainer.classList.remove("hidden");
    });

    // Close dropdown when clicking outside
    document.addEventListener("click", (e) => {
      if (!wrapper.contains(e.target)) {
        dropdownContainer.classList.add("hidden");
      }
    });

    // Update input when select changes
    selectElement.addEventListener("change", () => {
      const selectedOption = selectElement.options[selectElement.selectedIndex];
      searchInput.value = selectedOption ? selectedOption.text : "";
    });

    return {
      updateOptions,
      clear: () => {
        searchInput.value = "";
        selectElement.value = "";
        dropdownContainer.classList.add("hidden");
      },
    };
  }

  let currentMatches = null;
  const eventMatches = JSON.parse(
    document.getElementById("event_matches").textContent,
  );

  // Create searchable dropdowns
  const eventSearchable = createSearchableDropdown(eventSelect, "Events");
  const matchSearchable = createSearchableDropdown(matchSelect, "Matches");

  const eventStatus = document.createElement("p");
  eventStatus.className = "help";
  eventStatus.setAttribute("role", "status");
  eventSelect.parentElement.appendChild(eventStatus);
  const matchStatus = document.createElement("p");
  matchStatus.className = "help";
  matchStatus.setAttribute("role", "status");
  matchSelect.parentElement.appendChild(matchStatus);
  const eventsController = new AbortController();
  let eventTimer;
  let matchesController;
  window.addEventListener("pagehide", () => {
    clearTimeout(eventTimer);
    eventsController.abort();
    matchesController?.abort();
  });
  window.addEventListener("pageshow", event => {
    if (event.persisted) window.location.reload();
  });
  function populateEvents(events) {
    const existing = new Map([...eventSelect.options].map(option => [option.value, option]));
    Object.entries(events).forEach(([name, data]) => {
      if (!data?.key) return;
      const option = existing.get(name) || document.createElement("option");
      option.value = name;
      option.dataset.key = data.key;
      option.textContent = name;
      if (!existing.has(name)) eventSelect.appendChild(option);
    });
    eventSearchable.updateOptions();
  }
  populateEvents(JSON.parse(document.getElementById("events").textContent));
  const eventsStarted = Date.now();
  async function refreshEvents() {
    try {
      const response = await fetch("/api/tba/events?background=1", {
        signal: eventsController.signal, cache: "no-store"
      });
      if (!response.ok) throw new Error("Events unavailable");
      const events = await response.json();
      if (events.error) throw new Error(events.error);
      populateEvents(events);
      const pending = response.headers.get("X-Scouting-Pending") === "true";
      if (pending && Date.now() - eventsStarted < 60000) {
        eventStatus.textContent = "Loading events…";
        eventTimer = setTimeout(refreshEvents, 2000);
      } else {
        eventStatus.textContent = Object.keys(events).some(name => !name.startsWith("Testing Regional"))
          ? "" : "Event service unavailable. Testing events are still available; reload to retry.";
      }
    } catch (error) {
      if (error.name !== "AbortError") eventStatus.textContent = "Unable to load events. Reload to retry.";
    }
  }
  refreshEvents();

  // Load matches when event is selected
  eventSelect.addEventListener("change", async function () {
    matchesController?.abort();
    const controller = matchesController = new AbortController();
    currentMatches = null;
    matchStatus.textContent = "";
    matchSelect.disabled = false;
    const selectedOption = this.options[this.selectedIndex];
    const selectedEventKey = selectedOption?.dataset.key;
    matchSelect.innerHTML = '<option value="">Select Match</option>';
    matchSearchable.clear();
    teamSelect.innerHTML = '<option value="">Select Team</option>';
    allianceInput.value = "";

    if (!selectedEventKey) {
      return;
    }

    try {
      // Show loading state
      matchSelect.disabled = true;
      matchStatus.textContent = "Loading matches…";
      matchSearchable.clear();

      // Fetch matches for selected event
      const matches = await loadEventMatches(selectedEventKey, controller.signal);
      if (controller.signal.aborted || matchesController !== controller) return;
      if (!matches) {
        matchStatus.textContent = "Match service unavailable. Select the event again to retry.";
        return;
      }

      matchStatus.textContent = Object.keys(matches).length ? "" : "No matches available for this event.";

      currentMatches = matches;
      matchSelect.innerHTML = '<option value="">Select Match</option>';

      // Group matches by competition level
      const groupedMatches = {};
      Object.entries(matches).forEach(([matchKey, match]) => {
        const level = match.comp_level;
        if (!groupedMatches[level]) {
          groupedMatches[level] = [];
        }
        groupedMatches[level].push({ key: matchKey, ...match });
      });

      // Add matches in order: Qualification, Semi-Finals, Finals
      const levels = {
        qm: "Qualification",
        sf: "Semi-Finals",
        f: "Finals",
      };

      Object.entries(levels).forEach(([level, label]) => {
        if (groupedMatches[level]) {
          const group = document.createElement("optgroup");
          group.label = label;

          // Sort matches within each group
          groupedMatches[level]
            .sort((a, b) => {
              if (level === "sf") {
                // Sort by set number first, then match number
                return (
                  a.set_number - b.set_number || a.match_number - b.match_number
                );
              }
              return a.match_number - b.match_number;
            })
            .forEach((match) => {
              const option = document.createElement("option");
              option.value = match.key;

              // Format display text based on match type
              if (level === "qm") {
                option.textContent = `Qual ${match.match_number}`;
              } else if (level === "sf") {
                option.textContent = `Semi-Finals ${match.set_number}-${match.match_number}`;
              } else if (level === "f") {
                option.textContent = `Finals ${match.match_number}`;
              }

              group.appendChild(option);
            });

          matchSelect.appendChild(group);
        }
      });

      // Update match searchable options after populating
      matchSearchable.updateOptions();
      matchSelect.disabled = false;
    } catch (error) {
      if (error.name === "AbortError" || matchesController !== controller) return;
      console.error("Error fetching matches:", error);
      matchStatus.textContent = "Unable to load matches. Select the event again to retry.";
      matchSelect.innerHTML = '<option value="">Error loading matches</option>';
      matchSearchable.clear();
    } finally {
      if (matchesController === controller) {
        matchSelect.disabled = false;
        matchSearchable.updateOptions();
      }
    }
  });

  // Load teams when match is selected
  matchSelect.addEventListener("change", function () {
    const selectedMatch = this.value;
    teamSelect.innerHTML = '<option value="">Select Team</option>';
    allianceInput.value = "";

    if (!selectedMatch || !currentMatches) {
      return;
    }

    const match = currentMatches[selectedMatch];
    if (!match) {
      return;
    }

    // Add red alliance teams
    const redGroup = document.createElement("optgroup");
    redGroup.label = "Red Alliance";
    match.red.forEach((team) => {
      const option = document.createElement("option");
      const teamNumber = team.replace("frc", "");
      option.value = teamNumber;
      option.textContent = `Team ${teamNumber}`;
      option.dataset.alliance = "red";
      redGroup.appendChild(option);
    });
    teamSelect.appendChild(redGroup);

    // Add blue alliance teams
    const blueGroup = document.createElement("optgroup");
    blueGroup.label = "Blue Alliance";
    match.blue.forEach((team) => {
      const option = document.createElement("option");
      const teamNumber = team.replace("frc", "");
      option.value = teamNumber;
      option.textContent = `Team ${teamNumber}`;
      option.dataset.alliance = "blue";
      blueGroup.appendChild(option);
    });
    teamSelect.appendChild(blueGroup);
  });

  // Set alliance color when team is selected
  teamSelect.addEventListener("change", function () {
    const selectedOption = this.options[this.selectedIndex];
    if (selectedOption && selectedOption.dataset.alliance) {
      allianceInput.value = selectedOption.dataset.alliance;

      // Optional: Add visual feedback of selected alliance
      this.classList.remove("border-red-500", "border-blue-500", "dark:border-red-500", "dark:border-blue-500");
      this.classList.add(`border-${selectedOption.dataset.alliance}-500`, `dark:border-${selectedOption.dataset.alliance}-500`);
    } else {
      allianceInput.value = "";
      this.classList.remove("border-red-500", "border-blue-500", "dark:border-red-500", "dark:border-blue-500");
    }
  });

  // Tab switching functionality
  const tabButtons = document.querySelectorAll(".tab-button");
  const tabContents = document.querySelectorAll(".tab-content");

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const { tab } = button.dataset;

      // Update button states
      tabButtons.forEach((btn) => {
        btn.classList.remove("active");
      });
      button.classList.add("active");

      // Update content visibility
      tabContents.forEach((content) => {
        if (content.dataset.tab === tab) {
          content.classList.remove("hidden");
          content.classList.add("active");
        } else {
          content.classList.add("hidden");
          content.classList.remove("active");
        }
      });
    });
  });
});

// Update the updateUIControls method to be more specific
function updateUIControls(color, thickness) {
  if (color) {
    // Update color picker if it exists
    const colorPicker = document.querySelector('input[name="pathColorPicker"]');
    if (colorPicker) {
      colorPicker.value = color;
      // Update Coloris
      Coloris.setInstance("#pathColorPicker", { value: color });
    }
  }

  if (thickness) {
    // Update thickness slider if it exists - be more specific with the selector
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
