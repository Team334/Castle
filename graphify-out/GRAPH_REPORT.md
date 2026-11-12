# Graph Report - Castle  (2026-11-11)

## Corpus Check
- 154 files · ~250,909 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 15 file(s) not represented in the graph (top: .css 8, (none) 3, .service 1)

## Summary
- 1684 nodes · 3554 edges · 91 communities (62 shown, 29 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 395 edges (avg confidence: 0.88)
- Token cost: 774,954 input · 0 output

## Community Hubs (Navigation)
- Redesign Page Contract & PWA Shell
- Auto-Path Drawing Canvas
- Fuel Estimate Service (Match13)
- Import, Duplicate & Venue Tests
- Mock Alliance Selection
- Scout Form (add.js)
- App Factory & Config
- Fuel Apportioning Math
- Auth Models & Shared Manager
- Assignment Push Notifications
- Match Record Model & Stats
- Team Routes
- Team Membership Logic
- Team Compare (Radar)
- Team Assignment Routes
- Repo Tooling & Docs
- TBA Events & Rankings
- QR Fountain Codec & Scan
- Entry Export (JSON)
- Venue Laptop Plan & Design
- Auth Routes
- Import Helpers & Normalising
- Team Manage Page
- User Lookup & Login
- User Profile & Venue CLI
- Notification Wiring
- Add Route Redirects
- Profile Pictures & Pit Lookup
- Nexus API Client
- Canvas & Redesign Plans
- Service Worker & Offline Cache
- Pit Scouting Routes
- Playoff Bracket
- Drafts & Typed Match Helpers
- Offline Badge & Venue Banner
- EPA Team Stats
- PWA Install Prompt
- Fuel Estimate Docs
- Canvas Tests
- Public API Cache
- TBA Event Routes
- Scouting List Page
- Offline Outbox
- Team Roles
- Auto Path Compare Page
- Stress Test Script
- Security Regression Tests
- Notifications UI
- Browser Resilience Tests
- Transfer Route Tests
- Record Access Filter
- Venue CLI Tests
- Compare API Logging
- MongoDB Connection
- QR Transfer Plan
- CSS Build (Tailwind)
- Outbox Tests
- Account Settings Page
- Add-Flow Tests
- Export Routes
- Create Team Form
- QR Codec Tests
- Test Event Data
- Push Subscription Routes
- Alliance Fuel Totals
- Team Leaderboard
- Edit & Delete Records
- Route Logging Tests
- Pagination Tests
- Vercel Config
- Scouter Leaderboard
- Pit List & Match View
- Add Redirect Tests
- Password Rules
- Settings Updates
- Assignment Model
- Pit Form Tests
- Perf Test Fakes
- Route Error Handler
- Fuel Test Fakes
- Contributing Guides
- Team Stats Widget
- Live Match Status
- Fuel Route Tests
- Security Linting Config
- Install Script
- Public Team View
- Feature Request Form
- 500 Page Contract
- Team View Page Contract

## God Nodes (most connected - your core abstractions)
1. `Canvas` - 74 edges
2. `with_mongodb_retry()` - 51 edges
3. `ScoutingManager` - 43 edges
4. `TeamManager` - 36 edges
5. `TBAInterface` - 31 edges
6. `FuelEstimateService` - 31 edges
7. `actor_name()` - 31 edges
8. `ServiceTests` - 27 edges
9. `list.html (Scouting data page)` - 26 edges
10. `Offline scouting and venue mode design (Maneuver batch 4)` - 24 edges

## Surprising Connections (you probably didn't know these)
- `Typed match entry` --references--> `tba_match_key()`  [INFERRED]
  docs/superpowers/specs/2026-11-11-offline-venue-mode-design.md → app/scout/TBA.py
- `POST /scouting/import` --references--> `zero_scored_fuel()`  [INFERRED]
  docs/superpowers/specs/2026-11-11-offline-venue-mode-design.md → app/scout/match13_fuel.py
- `Task 1: qrf.js fountain codec` --references--> `qrfPack()`  [EXTRACTED]
  docs/superpowers/plans/2026-11-11-offline-phase3-qr.md → app/static/js/qrf.js
- `Task 6: add-flow.js draft and next-match helpers` --references--> `nextMatchValue()`  [EXTRACTED]
  docs/superpowers/plans/2026-11-11-match-day-fixes.md → app/static/js/scout/add-flow.js
- `Task 4: Edit unlinks identity and toggles exclusion` --references--> `TeamData`  [EXTRACTED]
  docs/superpowers/plans/2026-11-11-match-day-fixes.md → app/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Venue Mode Offline Scouting Flow** — docs_venue_mode_venue_mode, docs_venue_mode_phone_offline_outbox, docs_venue_mode_animated_qr_transfer, docs_venue_mode_lead_laptop, docs_venue_mode_download_new_entries, app_templates_base_outbox_startup [INFERRED 0.85]
- **Match13 Fuel Estimate Pipeline** — docs_match13_fuel_match13_api, docs_match13_fuel_tba_event_matches, docs_match13_fuel_proportional_allocation, docs_match13_fuel_largest_remainder_rounding, docs_match13_fuel_guarded_fuel_writer [EXTRACTED 1.00]
- **Repository Code Quality and Dependency Tooling** — _github_workflows_bandit_bandit_security_workflow, bandit_bandit_config, _sourcery_sourcery_config, _github_dependabot_dependabot_pip_updates [INFERRED 0.75]
- **Offline QR entry transfer (Show QR on phone, scan on lead laptop)** — app_templates_scouting_add, app_templates_scouting_list, app_static_js_scout_qr_send, app_static_js_qrf, app_static_js_scout_qr_scan, app_templates_scouting_scan_qr_scanner_view [INFERRED 0.85]
- **Match13 automatic fuel estimate display** — app_templates_scouting_add_fuel_estimate_hint, app_templates_scouting_edit_fuel_estimate_notice, app_templates_scouting_match_list_fuel_estimate_placeholder, app_static_js_scout_fuel_estimates, app_scout_routes_records_fuel_estimates [INFERRED 0.85]
- **Venue laptop JSON export/import** — app_templates_scouting_list_download_all_json, app_templates_scouting_list_download_new_entries, app_templates_scouting_list_import_file, app_scout_routes_transfer_export_entries, app_scout_routes_transfer_export_venue_entries [INFERRED 0.85]
- **Idempotent entry transfer paths** — docs_superpowers_specs_2026_11_11_offline_venue_mode_design_outbox_sync, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_qr_transfer, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_download_new_entries, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_post_scouting_import, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_client_id, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_already_have_rule [EXTRACTED 1.00]
- **Venue laptop event lifecycle** — docs_superpowers_specs_2026_11_11_offline_venue_mode_design_flask_venue_reset, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_get_scouting_export, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_post_scouting_import, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_scan_page, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_download_new_entries [EXTRACTED 1.00]
- **Offline scout phone stack** — docs_superpowers_specs_2026_11_11_offline_venue_mode_design_cached_scout_form, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_schedule_cache, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_typed_match_entry, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_outbox, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_outbox_sync, docs_superpowers_specs_2026_11_11_offline_venue_mode_design_vendored_cdn_scripts [INFERRED 0.85]
- **Pages bound to the Canvas.js auto-path canvas contract** — docs_superpowers_specs_2026_11_10_castle_redesign_contract_canvas_auto_path_contract, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_scouting_add, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_scouting_edit, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_scouting_list, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_lighthouse, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_lighthouse_auton [EXTRACTED 1.00]
- **Tables whose JS reads tr/td positions (CSS-only phone cards)** — docs_superpowers_specs_2026_11_10_castle_redesign_contract_table_to_card_css_pattern, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_scouting_match_list, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_scouting_pit_scouting, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_team_manage, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_scouting_leaderboard [EXTRACTED 1.00]
- **Forms that get the sticky full-width save bar** — docs_superpowers_specs_2026_11_10_castle_redesign_contract_sticky_save_bar, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_scouting_add, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_scouting_edit, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_scouting_pit_scouting_add, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_scouting_pit_scouting_edit, docs_superpowers_specs_2026_11_10_castle_redesign_contract_page_team_settings [EXTRACTED 1.00]

## Communities (91 total, 29 thin omitted)

### Community 0 - "Redesign Page Contract & PWA Shell"
Cohesion: 0.05
Nodes (69): background_color, categories, description, display, gcm_sender_id, gcm_user_visible_only, icons, id (+61 more)

### Community 2 - "Fuel Estimate Service (Match13)"
Cohesion: 0.07
Nodes (11): FuelEstimateService, on_blueprint_init(), Collection, fixtures(), ServiceTests, failed_older_save(), newer_save(), manual() (+3 more)

### Community 3 - "Import, Duplicate & Venue Tests"
Cohesion: 0.05
Nodes (13): AddRecordTests, EditTests, ExclusionTests, form(), manager(), entry(), ExportTests, ImportTests (+5 more)

### Community 4 - "Mock Alliance Selection"
Cohesion: 0.08
Nodes (52): advancePick(), areAllPicksComplete(), completeSelection(), createAllianceCard(), createDismissButton(), createEmptyAllianceHTML(), createEmptyPickHTML(), createFilledAllianceHTML() (+44 more)

### Community 5 - "Scout Form (add.js)"
Cohesion: 0.06
Nodes (35): createSearchableDropdown(), filterOptions(), renderDropdown(), updateOptions(), fillFields(), loadEventMatches(), loadMatchesForSelectedEvent(), markDirty() (+27 more)

### Community 7 - "Fuel Apportioning Math"
Cohesion: 0.09
Nodes (12): apportioned(), estimate_fuel(), match_key(), zero_scored_fuel(), import_entries(), _pit_result(), _normalise_entry(), tba_match_key() (+4 more)

### Community 9 - "Assignment Push Notifications"
Cohesion: 0.07
Nodes (3): AssignmentSubscription, NotificationManager, on_blueprint_init()

### Community 10 - "Match Record Model & Stats"
Cohesion: 0.07
Nodes (5): TeamData, _fuel_value(), _percent(), ScoutingManager, Task 3: Fuel-pending out of fuel averages

### Community 11 - "Team Routes"
Cohesion: 0.09
Nodes (11): create(), on_blueprint_init(), team_logo(), update_team_logo(), check_password_strength(), error_response(), get_gridfs(), get_mongodb_instance() (+3 more)

### Community 13 - "Team Compare (Radar)"
Cohesion: 0.11
Nodes (26): compareBtn, comparisonResults, escapeHtml(), getTeamColor(), handleCompare(), handleEnterKey(), showAutoPath(), team1Input (+18 more)

### Community 14 - "Team Assignment Routes"
Cohesion: 0.13
Nodes (16): add_admin(), clear_assignments(), create_assignment(), delete_assignment(), delete_team(), edit_assignment(), get_team_members(), join() (+8 more)

### Community 15 - "Repo Tooling & Docs"
Cohesion: 0.09
Nodes (26): Dependabot Daily pip Updates, Funding Links (BTHS Robotics, BTHS Alumni donate), Issue Template Config (contact links), Assignment Reminder Modal, Lead Laptop Local Castle Copy, Castle (Team 334 Scouting App), .env Configuration (SECRET_KEY, MONGO_URI, TBA_AUTH_KEY, NEXUS_API_KEY, VAPID keys), Install Scripts (install.bat / install.sh) (+18 more)

### Community 16 - "TBA Events & Rankings"
Cohesion: 0.12
Nodes (4): get_alliance_rankings(), get_team_status(), add(), TBAInterface

### Community 17 - "QR Fountain Codec & Scan"
Cohesion: 0.10
Nodes (20): QRF_SOLITON, qrfDecoder(), peel(), qrfEncoder(), qrfHash(), qrfIndices(), qrfPack(), qrfRandom() (+12 more)

### Community 18 - "Entry Export (JSON)"
Cohesion: 0.12
Nodes (7): _jsonable(), Offline Phase 1 (Entry Export and Import) Implementation Plan, Task 2: import_matches, Task 3: export_data, Task 4: Export and import routes, Task 5: List page download and import buttons, Task 4: Scan page on the lead's laptop

### Community 19 - "Venue Laptop Plan & Design"
Cohesion: 0.13
Nodes (7): Offline Phase 4 (Venue Laptop) Implementation Plan, Task 2: Export scope and venue CLI commands, Task 4: Lead's pages work without the internet, Task 5: Venue setup guide, The Blue Alliance (TBA), Offline scouting and venue mode design (Maneuver batch 4), Match13 fuel estimates

### Community 20 - "Auth Routes"
Cohesion: 0.14
Nodes (13): change_password(), check_username(), delete_account(), forgot_password(), login(), logout(), on_blueprint_init(), profile() (+5 more)

### Community 21 - "Import Helpers & Normalising"
Cohesion: 0.13
Nodes (5): _is_checked(), _object_id(), _parse_time(), _record_fields(), Task 1: Venue-mode import

### Community 22 - "Team Manage Page"
Cohesion: 0.13
Nodes (15): clearAllAssignments(), confirmDeleteTeam(), confirmLeaveTeam(), deleteAssignment(), handleAssignmentSubmit(), handleEditAssignmentSubmit(), initializeAssignmentForm(), initializeEditAssignment() (+7 more)

### Community 23 - "User Lookup & Login"
Cohesion: 0.12
Nodes (3): User, _with_object_ids(), ExportScopeTests

### Community 24 - "User Profile & Venue CLI"
Cohesion: 0.13
Nodes (6): UserManager, DatabaseManager, register_venue_commands(), venue_reset(), venue_user(), _venue_only()

### Community 25 - "Notification Wiring"
Cohesion: 0.13
Nodes (3): logged_in_client(), BugFixTests, ScanPageTests

### Community 26 - "Add Route Redirects"
Cohesion: 0.19
Nodes (10): _add_form_url(), Match-Day Fixes Implementation Plan, Task 2: Store keys and block duplicates, Task 3: Return to the add form after save, Task 4: Edit unlinks identity and toggles exclusion, Task 5: Excluded records drop out of stats, Task 6: add-flow.js draft and next-match helpers, Task 7: Wire drafts and preselection into add form (+2 more)

### Community 29 - "Canvas & Redesign Plans"
Cohesion: 0.16
Nodes (5): Task 1: Vendor localforage and align SW caches, Castle redesign page contract (appendix), Castle redesign design, taste-skill website-design kit, Team 334 TechKnights

### Community 30 - "Service Worker & Offline Cache"
Cohesion: 0.15
Nodes (8): CACHE_TIMESTAMP, CRITICAL_ASSETS, dismissedNotifications, STATIC_ASSETS, Offline Phase 2 (Scout Phones Offline) Implementation Plan, Task 2: Service worker caches scout form offline, Task 3: Schedule cache and typed-label helpers, Task 5: Wire offline save into scout form

### Community 31 - "Pit Scouting Routes"
Cohesion: 0.18
Nodes (11): _form_int(), _pit_form(), pit_scouting(), pit_scouting_add(), pit_scouting_delete(), pit_scouting_edit(), pit-scouting-add.html (Add pit data page), Pit scouting form (add) (+3 more)

### Community 32 - "Playoff Bracket"
Cohesion: 0.20
Nodes (16): bracketMatches, createMatch(), getFinalsStatus(), getMatchLabel(), initializeBracketMatches(), propagateBracket(), renderBracket(), renderMatch() (+8 more)

### Community 33 - "Drafts & Typed Match Helpers"
Cohesion: 0.20
Nodes (15): draftKey(), LABEL_SHAPES, loadDrafts(), loadSchedule(), nextMatchValue(), nextTypedLabel(), parseLabel(), positiveInt() (+7 more)

### Community 34 - "Offline Badge & Venue Banner"
Cohesion: 0.18
Nodes (17): Offline Indicator Badge, Venue Mode Banner, checkConnection(), handleOnline(), Offline Fallback Page, startAutoRetryCountdown(), updateConnectionStatus(), Animated QR Code Entry Transfer (Show QR / Scan QR) (+9 more)

### Community 35 - "EPA Team Stats"
Cohesion: 0.20
Nodes (4): get_team_epa(), team_stats_snapshot(), SnapshotTests, response()

### Community 36 - "PWA Install Prompt"
Cohesion: 0.18
Nodes (14): 404 Page Not Found Template, 429 Too Many Requests Template, 500 Server Error Template, Login Form, User Profile Page, Registration Form, Base Layout Template, CSRF Fetch Wrapper (+6 more)

### Community 37 - "Fuel Estimate Docs"
Cohesion: 0.15
Nodes (12): Background Fuel Backfill (250 records/minute, daily rescan), Fuel Estimate Eligibility (seven scored-fuel counts zero or blank), Ferried Fuel, Fuel Source CSV Column, Match13 API, Match13 Ratings (xAuto, xTele, xEnd), MATCH13_STATE_PATH Environment Variable, MATCH_13_API_KEY Environment Variable (+4 more)

### Community 38 - "Canvas Tests"
Cohesion: 0.12
Nodes (7): assert, BOUNDS, devices, fs, SOURCE, test, vm

### Community 40 - "TBA Event Routes"
Cohesion: 0.23
Nodes (5): get_tba_events(), get_tba_matches(), get_team_epa_opr(), live_match_status(), mock_alliance_selection()

### Community 41 - "Scouting List Page"
Cohesion: 0.21
Nodes (9): home(), filterRows(), loadMatches(), list.html (Scouting data page), Auto path modal (scouting data), Import file (Castle JSON), Load more matches pagination (#loadMoreMatches), Match search and filter (team/match/scouter/notes) (+1 more)

### Community 42 - "Offline Outbox"
Cohesion: 0.27
Nodes (15): applyImportResults(), loadOutbox(), OUTBOX_DONE, outboxKey(), pendingEntries(), queueEntry(), renderOutboxBar(), startOutbox() (+7 more)

### Community 44 - "Auto Path Compare Page"
Cohesion: 0.24
Nodes (13): addPathToSelection(), availablePaths, clearAllPaths(), drawPaths(), escapeHtml(), removePath(), searchTeam(), selectedPaths (+5 more)

### Community 45 - "Stress Test Script"
Cohesion: 0.18
Nodes (6): main(), actor(), session(), percentile(), ProcessSampler, StatsCells

### Community 47 - "Notifications UI"
Cohesion: 0.26
Nodes (3): handleReminderClick(), initNotificationUI(), NotificationManager

### Community 48 - "Browser Resilience Tests"
Cohesion: 0.15
Nodes (6): assert, estimatePage(), tick(), fs, test, vm

### Community 49 - "Transfer Route Tests"
Cohesion: 0.22
Nodes (3): envelope(), RouteTests, VenueRouteTests

### Community 52 - "Compare API Logging"
Cohesion: 0.38
Nodes (6): actor_name(), auton(), compare_teams(), get_team_paths(), lighthouse(), search_teams()

### Community 54 - "QR Transfer Plan"
Cohesion: 0.29
Nodes (5): Offline Phase 3 (QR Transfer) Implementation Plan, Task 1: qrf.js fountain codec, Task 2: Vendor qrcode-generator and jsQR, Task 3: Show QR on the scout's phone, qrf branch prototype

### Community 55 - "CSS Build (Tailwind)"
Cohesion: 0.17
Nodes (9): devDependencies, tailwindcss, name, private, scripts, build:css, test, tailwindcss (+1 more)

### Community 56 - "Outbox Tests"
Cohesion: 0.17
Nodes (4): assert, fs, test, vm

### Community 57 - "Account Settings Page"
Cohesion: 0.31
Nodes (9): changePassword(), checkUsername(), confirmDeleteAccount(), error(), showNotification(), style, checkPasswordStrength(), validatePasswords() (+1 more)

### Community 58 - "Add-Flow Tests"
Cohesion: 0.18
Nodes (4): assert, fs, test, vm

### Community 59 - "Export Routes"
Cohesion: 0.27
Nodes (6): _download(), export_entries(), export_venue_entries(), scan_entries(), Download all (JSON) export link, Download new entries (venue export form)

### Community 61 - "QR Codec Tests"
Cohesion: 0.22
Nodes (6): assert, fs, randomBytes(), rng(), test, vm

### Community 62 - "Test Event Data"
Cohesion: 0.36
Nodes (3): _generate_test_matches(), _generate_test_rankings(), _generate_test_teams()

### Community 63 - "Push Subscription Routes"
Cohesion: 0.29
Nodes (3): create_subscription(), delete_subscription(), get_vapid_public_key()

### Community 64 - "Alliance Fuel Totals"
Cohesion: 0.29
Nodes (6): fuel_total(), _alliance_fuel(), _match_team_rows(), matches(), auton.html (Auto path comparison page), Path comparison canvas (#pathCanvas)

### Community 65 - "Team Leaderboard"
Cohesion: 0.39
Nodes (7): leaderboard(), leaderboard.html (Team leaderboard page), changeEvent(), changeRanking(), Rank-by metric selector (#rankingSelect), EPA/event stats cell (leaderboard, data-team-id), EPA/OPR/DPR/CCWM cell (data-team-id, data-event-id)

### Community 66 - "Edit & Delete Records"
Cohesion: 0.36
Nodes (4): delete(), edit(), fuel_estimates(), _user_team()

### Community 69 - "Vercel Config"
Cohesion: 0.25
Nodes (7): builds, standalone, git, deploymentEnabled, ignoreCommand, routes, version

### Community 70 - "Scouter Leaderboard"
Cohesion: 0.33
Nodes (5): scouter_leaderboard(), scouter-leaderboard.html (Scouter leaderboard page), Scouter achievement badges, Scouter leaderboard filter form (auto-submit), Page contract: scouting/scouter-leaderboard.html

### Community 71 - "Pit List & Match View"
Cohesion: 0.38
Nodes (5): matches.html (Match view page), Team number search filter (match view), pit-scouting.html (Pit scouting list page), Pit data table (CSV export hooks), Team number search (pit scouting)

### Community 78 - "Route Error Handler"
Cohesion: 0.40
Nodes (3): handle_route_errors(), decorator(), wrapper()

### Community 80 - "Contributing Guides"
Cohesion: 0.50
Nodes (4): Contributing Guidelines, Git Commit Guidelines, Bug Report Issue Form, Pull Request Template

### Community 81 - "Team Stats Widget"
Cohesion: 0.83
Nodes (4): loadTeamStats(), load(), render(), sortLeaderboard()

### Community 83 - "Live Match Status"
Cohesion: 0.50
Nodes (3): live-match-status.html (Live team schedule page), displayTeamStatus(), loadTeamStatus()

### Community 85 - "Security Linting Config"
Cohesion: 0.67
Nodes (3): Bandit Code Security Workflow, Sourcery Configuration, Bandit Configuration

## Ambiguous Edges - Review These
- `pit-scouting/add.js` → `Pit scouting form (edit)`  [AMBIGUOUS]
  app/templates/scouting/pit-scouting-edit.html · relation: conceptually_related_to
- `Richardson Brand Accelerator wordmark font` → `Kit vs Castle class conflicts (.grid, .card, .btn, .link, .badge, main > section)`  [AMBIGUOUS]
  docs/superpowers/specs/2026-11-10-castle-redesign-contract.md · relation: conceptually_related_to

## Knowledge Gaps
- **30 isolated node(s):** `Git Commit Guidelines`, `Funding Links (BTHS Robotics, BTHS Alumni donate)`, `Bug Report Issue Form`, `Feature Request Issue Form`, `Pull Request Template` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 514 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **29 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `CSRF contract (meta tag, inline fetch wrapper, hidden csrf_token inputs)` connect `Redesign Page Contract & PWA Shell` to `Auth Models & Shared Manager`, `Browser Resilience Tests`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `ScoutingManager` (e.g. with `on_blueprint_init()` and `Team`) actually correct?**
  _`ScoutingManager` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Git Commit Guidelines`, `Funding Links (BTHS Robotics, BTHS Alumni donate)`, `Bug Report Issue Form` to the rest of the system?**
  _30 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Redesign Page Contract & PWA Shell` be split into smaller, more focused modules?**
  _Cohesion score 0.05369369369369369 - nodes in this community are weakly interconnected._
- **Why does `Canvas` connect `Auto-Path Drawing Canvas` to `Canvas & Redesign Plans`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `pit-scouting/add.js` and `Pit scouting form (edit)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Richardson Brand Accelerator wordmark font` and `Kit vs Castle class conflicts (.grid, .card, .btn, .link, .badge, main > section)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._