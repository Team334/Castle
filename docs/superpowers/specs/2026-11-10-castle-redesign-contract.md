# Castle redesign: page contract (appendix)

Generated 2026-11-10 from a read-only inventory of every template, its JS, Flask views and tests, plus an adversarial second pass per page group. Companion to `2026-11-10-castle-redesign-design.md`.

**Rule:** every row under "Hooks" must survive the rebuild exactly as described in "Must keep", or the consumer named in "Used by" breaks. Line numbers are as of commit 93399c8; re-grep before relying on them. "Corrections" override anything above them in the same group.

## Group: shell-auth

### Shared findings
- Every page depends on the component layer in app/static/css/tailwind.input.css:24-142: page-header, page-title, page-subtitle, section-title, card, card-header, card-body, btn, btn-primary/secondary/ghost/danger/sm/lg/icon, label, input, help, checkbox, badge-*, table-wrap, table, link, nav-link, nav-link-active and menu-item. Restyling these classes restyles the whole app at once, including JS-built markup that uses them (the settings.js toasts use 'card'; base.html uses nav-link-active and menu-item). The 48px tap targets can be done here: .btn-icon is p-2 (36px), .btn is py-2 text-sm (36px), .menu-item is py-2 (36px) and .input is py-2 (~42px).
- Dark mode must stay class-based on <html> (tailwind.config.js:6 darkMode 'class'). compare.js:162 reads html.dark and compare.js:238-245 watches the html class attribute to redraw the radar chart; auton.css and mock-alliance-selection.html have hand-written .dark rules. localStorage key 'theme' takes 'dark' or 'light'.
- Keep tailwind.config.js:8, safelist [{pattern: /^(bg|text|border)-(red|blue)-(100|500|800)$/}]: live-match-status assembles alliance color classes at runtime. Tailwind content globs are ./app/templates/**/*.html and ./app/static/js/**/*.js, so any class strings in JS outside app/static/js are purged.
- The service worker serves STATIC_ASSETS cache-first with no version query. After rebuilding the CSS (npm run build:css), bump the four cache names in app/static/js/service-worker.js:1-4 (v14 to v15), or phones keep the old tailwind.css. cache.addAll is atomic, so deleting app/static/css/index.css without removing it from service-worker.js:14 breaks the SW install and offline scouting.
- The new font files in app/static/fonts/ are not cached for offline use. 'Richardson Brand Accelerator.otf' has spaces in its name: quote it in @font-face url() and add it to STATIC_ASSETS URL-encoded ('/static/fonts/Richardson%20Brand%20Accelerator.otf'), because the SW match uses event.request.url.includes(asset). Add '/static/fonts/oxanium-vrb.ttf' too. Fonts are exempt from the ?v= timestamp (service-worker.js:98).
- CSRF: <meta name="csrf-token" content="..."> is regex-scraped by tests/app_harness.py:46, and the base.html inline wrapper is sliced by its exact text in tests/test_browser_resilience.js:253-256 ('Send the CSRF token' comment, '(function () {', '})();'). Every HTML form posting to Flask needs <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"> (team/create.html uses {{ form.csrf_token }}).
- Script-loading contract: base.js and auth/settings.js read document.currentScript.dataset, so they must stay classic scripts, not type=module. base.js touches document.body at parse time (base.js:4), so it must stay in <body>. The CSRF wrapper must run before base.js and before any page script. notifications.js must load before team/manage.js, which uses the global notificationManager.
- Global functions called from inline onclick/onkeyup attributes, which a rebuild must keep or rebind: copyEmail (forgot-password), togglePassword (login), checkUsername / changePassword / confirmDeleteAccount (settings.js), history.back() (error pages).
- The 'hidden' class is the universal show/hide mechanism toggled by JS in this group: .mobile-menu, #userDropdown, #nav-offline-indicator, #mobile-offline-indicator, #installMessage and #assignmentReminderModal. #installPWA is the exception: it uses inline style.display 'none'/'block'.
- Never add a <form> to base.html before the content block: app/static/js/auth/settings.js:79 binds to document.querySelector('form'). Logout is a GET link (app/auth/routes.py:107, GET only); converting it to a POST form would 405 and hijack settings.
- Pages rendered without auth: '/', /auth/login, /auth/register, /auth/forgot-password, /static/*, /service-worker.js (app/app.py:137-143). /offline.html is missing from that allowlist, so an anonymous SW install caches a login redirect as the offline page. This is pre-existing, not a markup issue, but relevant when testing the offline page.
- Error templates (404/429/500) render through base.html from error handlers (app/app.py:100-129), with request.endpoint == None and possibly with MongoDB down. The new top bar must not add DB-dependent context. The 404 handler returns HTTP 200.
- Flash: base.html renders only the LAST flashed message (messages[-1]). Categories in use are 'error' (50 calls plus login_manager.login_message_category='error' at app/app.py:63), 'success' (18) and 'warning' (1). Today 'warning' shows the green success icon.
- Bottom-of-screen collisions on phones: the flash toast (base.html:168, fixed bottom-4 z-50), the base.js update banner (fixed bottom-0 z-50), the settings #notification-area (fixed bottom-4 z-50), the index #installPWA FAB (fixed bottom-6 right-6 z-50) and the sticky save bars in scouting/add.html:441 and edit.html:390 (sticky bottom-0 z-20, using -mx-4 to bleed past main's px-4). The new sticky full-width save bar needs toasts and banners moved above it or to the top.
- Legacy CSS status: global.css is live on every page (counter-group used by scouting add/edit, number spinner hiding, smooth scroll). index.css is dead but referenced in the SW cache list. register.css is dead and referenced nowhere. The base.html inline <style> and the settings.js-injected @keyframes slideIn are live.
- Unused external dependency: base.html:27 loads https://unpkg.com/@popperjs/core@2 (render-blocking, unpinned major version) and nothing in the repo calls Popper or createPopper. Removing it speeds first paint on venue Wi-Fi.
- Pre-existing bugs found during the inventory (not caused by markup, but visible in a rebuild): auth/settings.html never loads compressorjs (settings.js:136 fails silently); the settings save flash is swallowed by the fetch response; profile.html:54 crashes if created_at is None; offline.html:451 deletes its own spinner; push icons /static/images/logo.png and badge.png are missing; notifications.js #testNotificationBtn and /notifications/test are dead.

### Corrections (verified by second pass)
- **Claim:** STATIC_ASSETS: 'Every entry must exist, because cache.addAll is all-or-nothing: one 404 (deleting index.css, for example) fails the install and kills offline mode' (repeated in shared_findings and in the index.css legacy note).
  **Correction:** When Flask serves the app (gunicorn via Castle.service and wsgi.py, or locally), a missing static file does NOT return 404. The app's 404 handler returns 404.html with status 200, so cache.addAll succeeds and silently caches an HTML page under /static/css/index.css. The runtime static branch (service-worker.js:248-256) also caches any response without checking response.ok. A real 404 that fails the install happens only on Vercel, where vercel.json routes /static/(.*) to @vercel/static. Still remove the entry together with the file, but the failure mode under Flask is wrong content, not a broken install.
  **Evidence:** app/app.py:100-102 `return render_template("404.html")` (no status). I probed a minimal Flask app with the same handler shape and app/static as its static folder: GET /static/css/index-deleted.css returned 200 text/html. vercel.json routes /static/(.*) → /app/static/$1. Castle.service ExecStart runs gunicorn wsgi:app.
- **Claim:** base.html is the 'Global shell for 28 templates' / 'content (inside <main>, 28 templates)'.
  **Correction:** 27 templates extend base.html. The 30 .html files include base.html, offline.html and scouting/_match_list.html, none of which extend it. The 28 'block content' occurrences include base.html's own definition.
  **Evidence:** grep -rl extends app/templates gives 27 files, all {% extends "base.html" %}; find app/templates -name '*.html' gives 30.
- **Claim:** block title is 'overridden by 8 templates'.
  **Correction:** 7 templates override it: 404.html, 429.html, 500.html, auth/login.html, auth/register.html, forgot-password.html and scouting/scouter-leaderboard.html. The 8th 'block title' match is base.html:25.
  **Evidence:** grep -rln 'block title' app/templates, excluding base.html.
- **Claim:** 'The test user in tests/app_harness.py:28 has only _id, username and teamNumber, so touching created_at or email would crash /auth/settings and every test.' Also: 'Use only current_user.username, teamNumber and get_id().'
  **Correction:** The harness builds a real User through User.create_from_db, whose __init__ sets email, last_login, created_at and profile_picture_id to None and description to ''. Reading those attributes never crashes; Jinja prints 'None'. What crashes is calling a method on a None value, such as current_user.created_at.strftime(...) or current_user.email.lower(). Templates already use current_user.id (settings.html:38) and current_user.description (settings.html:86) safely.
  **Evidence:** tests/app_harness.py:28; app/models.py:17-27 (User.__init__ uses data.get(...) for every field, description defaulting to '').
- **Claim:** Flash: 'Categories in use are error, success and warning'; 'everything else (success, and warning) gets the green icon'.
  **Correction:** There is also an uncategorized flash, which gets Flask's default category 'message'. It reports an internal error, yet base.html renders it with the green success check. A rebuilt toast that switches on category should treat 'message' and 'warning' explicitly.
  **Evidence:** app/team/routes.py:539 `flash("An internal error has occurred.")`; base.html:170-174 shows red only when category == 'error'.

### Tests touching markup
- tests/app_harness.py:45-46: GET /auth/settings, then regex r'name="csrf-token" content="([^"]+)"'. It needs base.html's meta with exactly that attribute order and quoting, and the settings page must render for a minimal user (username 'tester', teamNumber 334, nothing else; tests/app_harness.py:28). Every test using logged_in_client depends on this: test_security.py, test_bug_fixes.py, test_route_logging.py and others.
- tests/test_browser_resilience.js:252-275: reads app/templates/base.html as text and slices from '(function () {' after the comment 'Send the CSRF token' to the next '})();', then runs it in a VM. It asserts that X-CSRFToken is added only to same-origin non-GET requests and that the caller's Content-Type and X-Requested-With headers are kept.
- tests/test_browser_resilience.js:54-94: slices app/static/js/base.js from '    const originalFetch =' (4-space indent) to '\n    };' and tests the offline fetch wrapper. It needs base.js's fetch wrapper structure, indentation and the globals hideOfflineIndicators/showOfflineIndicators.
- tests/test_browser_resilience.js:6-52: runs app/static/js/service-worker.js in a VM. It checks that /api/ and ?checkOnline go to the network, that navigations are never cache-served, and that failed POSTs reject (service-worker.js:193-197, 229-238).
- tests/test_security.py:59: anonymous GET / (index.html through base.html) must render, and the response must not set Access-Control-Allow-Origin.
- tests/test_bug_fixes.py:26: logged-in GET / must render index.html (no status assert, but a crash goes through the 500 handler).
- tests/test_bug_fixes.py:56 and tests/test_security.py:35-40: post with the CSRF token scraped from base.html, as a header or as the csrf_token form field.
- scripts/stress_test.py:246 (not a unit test): GET / must contain the literal marker '<title>'.

### app/templates/base.html

**Purpose:** Global shell for 28 templates: <head> (CSRF fetch wrapper, theme init, tailwind.css + global.css, head block, PWA meta), sticky header (logo, desktop nav, offline badge, theme toggle, user dropdown or login/sign-up, hamburger + mobile menu), flash toast, <main> content block, footer, inline shell JS, base.js (service worker + offline handling).

**Routes:** Rendered by every page that extends it. Its links: index, scouting.home, scouting.lighthouse, team.manage, team.join, auth.profile(username), auth.settings, auth.logout (GET only, app/auth/routes.py:107), auth.login, auth.register, auth.profile_picture(user_id) (app/auth/routes.py:157). Its fetches: base.js HEAD /static/logo.png?checkOnline=... (base.js:216, 240) and registers /service-worker.js (base.js:53, served by app/app.py:165-173).

**Extends/includes:** Root layout. Blocks: title (default 'Castle', overridden by 8 templates), head (inside <head> AFTER tailwind.css and global.css; used by lighthouse/auton.html:1, lighthouse.html:2, scouting/add.html:1, scouting/edit.html:2, scouting/list.html:1, scouting/live-match-status.html:2, team/settings.html:2), content (inside <main>, 28 templates). No other block names are used anywhere, so a rebuild must keep exactly these three.

**JS:** inline <script> CSRF fetch wrapper (base.html:7-24); inline <script> theme init (base.html:28-34); inline <style> toast keyframes (base.html:65-71); inline <script> mobile menu, flash auto-dismiss, theme toggle, user dropdown (base.html:201-242); https://unpkg.com/@popperjs/core@2 (base.html:27): render-blocking, unpinned, and used by no file in the repo, so it can be dropped; app/static/js/base.js (base.html:245)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `meta[name="csrf-token"]` | other | app/templates/base.html:10; tests/app_harness.py:46 (regex r'name="csrf-token" content="([^"]+)"' on GET /auth/settings) | Keep the literal text <meta name="csrf-token" content="{{ csrf_token() }}">: name first, then exactly one space, then content, with double quotes. It must sit in <head> before the CSRF fetch-wrapper script. If the attributes are reordered, every Python test that uses logged_in_client fails. |
| `inline <script> CSRF fetch wrapper (base.html:7-24)` | structure | tests/test_browser_resilience.js:253-256 (slices the base.html source); every fetch POST/PUT/DELETE in the app | Keep the comment text 'Send the CSRF token', then the IIFE starting '(function () {' (with a space before the parens), ending at the first '})();' after it. Put no other '})();' inside it. It must run in <head> before the head block, any page script and base.js. It adds the X-CSRFToken header only to same-origin requests whose method is not GET, HEAD or OPTIONS, and must keep the caller's other headers. |
| `inline theme-init <script> in <head> (base.html:28-34) + html.dark` | structure | tailwind.config.js:6 (darkMode 'class'); tailwind.input.css:11 (html.dark color-scheme); app/static/js/compare.js:162 and :238-245 (MutationObserver on documentElement 'class' attribute re-renders the radar chart); app/static/css/auton.css:23-129 (.dark rules); app/templates/scouting/mock-alliance-selection.html:257-338 (.dark rules) | Keep the dark class on <html> (document.documentElement), not on body and not a data-theme attribute. Read localStorage.theme ('dark'/'light') and fall back to prefers-color-scheme. Run it synchronously in <head> before first paint. |
| `.theme-toggle` | class | app/templates/base.html:218-223 | Any number of buttons with class theme-toggle. A click toggles html.dark and writes localStorage.theme = 'dark' | 'light'. A rebuild can put a second one in the mobile menu, because querySelectorAll binds them all. |
| `.mobile-menu-button / .mobile-menu` | class | app/templates/base.html:202-204 | Both classes must exist on every page. The code uses document.querySelector (first match) with no null check. If either is missing, the inline script throws and the theme toggle and user dropdown handlers further down the same <script> (base.html:201-242) never bind. A click toggles the 'hidden' class on .mobile-menu. The menu starts with class 'hidden'. |
| `#userDropdownButton / #userDropdown` | id | app/templates/base.html:226-241 | #userDropdown starts with class 'hidden'; a click toggles it and a click outside the button adds it back. The first <svg> inside #userDropdownButton (userDropdownButton.querySelector('svg')) gets an inline style transform: rotate(180deg), so the chevron must be the first and only svg in the button. Use an <img> for the avatar, not an svg. Menu links: Profile (auth.profile), Settings (auth.settings), Log out (auth.logout as a plain GET <a>). The code null-checks these, so they can be omitted for anonymous users. |
| `#nav-offline-indicator` | id | app/static/js/base.js:15-18, 154-157, 172-175 | Starts with class 'hidden'. base.js removes or adds 'hidden' on it. It is currently wrapped in <div class="hidden sm:contents"> (base.html:99), so it shows on desktop only. |
| `#mobile-offline-indicator` | id | app/static/js/base.js:20-23, 160-163, 178-181 | Starts with class 'hidden'; base.js toggles 'hidden'. It currently sits inside the collapsed .mobile-menu (base.html:136). |
| `body.offline` | css-hook | app/static/js/base.js:4, 100, 103, 189, 199, 208, 244, 257 | base.js adds or removes the 'offline' class on <body>. No CSS uses it today, so it is free for the redesign to style an offline state. base.js:4 touches document.body as soon as the script parses, so base.js must stay inside <body>, not in <head>. |
| `script[src*="js/base.js"][data-app-version]` | data-attr | app/static/js/base.js:31 (document.currentScript.dataset.appVersion) | Load it as a classic script (not type=module) with data-app-version="{{ request.args.get('v', '1.0') }}", at the end of <body> after the CSRF wrapper. It wraps window.fetch a second time, for offline handling (base.js:232-276, tested by tests/test_browser_resilience.js:55-57, which slices the text from '    const originalFetch =' to '\n    };'). |
| `.animate-fade-in-up > div (flash toast)` | structure | app/templates/base.html:208-214 (auto-dismiss after 5 s); base.html:176 (onclick="this.parentElement.remove()") | The flash wrapper keeps class animate-fade-in-up, and the toast card is its direct child <div>. The dismiss button is a direct child of that card. Never put animate-fade-in-up on other page elements, or their child divs get removed after 5 s. The keyframes are defined inline at base.html:65-71. Only messages[-1] is rendered. The 'error' category gets the red icon; everything else ('success', and 'warning', used once) gets the green icon. |
| `<title>{% block title %}Castle{% endblock %}</title>` | jinja-context | scripts/stress_test.py:246 (marker '<title>' on GET /); 8 child templates override the title block | Keep a literal <title> tag and the title block. |
| `{% block head %} placement` | structure | lighthouse/auton.html, lighthouse.html, scouting/add.html, scouting/edit.html, scouting/list.html, scouting/live-match-status.html, team/settings.html | The block stays inside <head>, after tailwind.css and global.css, so page CSS (auton.css, scouting.css, coloris.css) overrides them, and page scripts loaded there (localforage, compressorjs) run before body content. The CSRF wrapper must come before it. |
| `request.endpoint / current_user nav logic (base.html:74-77, 87-97, 141-159)` | jinja-context | base.html; 404 handler renders with request.endpoint == None | Keep the None-safety ({% set endpoint = request.endpoint or '' %}). Active states: compare_active for scouting.lighthouse and scouting.auton; scout_active for other scouting.* endpoints; team_active for team.*. Users without current_user.teamNumber see only 'Join a team'. Use only current_user.username, teamNumber and get_id(). The test user in tests/app_harness.py:28 has only _id, username and teamNumber, so touching created_at or email would crash /auth/settings and every test. |
| `<main> horizontal padding px-4 at phone width` | structure | app/templates/scouting/add.html:441 and app/templates/scouting/edit.html:390 (sticky bottom-0 save bars use -mx-4 px-4 to bleed edge to edge, and sm:static) | If the main gutter changes from 16px, those save bars' negative margins must change with it. Stacking order today: header z-40, flash toast z-50, base.js update banner z-50, save bars z-20. |
| `no <form> in base.html before {% block content %}` | structure | app/static/js/auth/settings.js:79 (document.querySelector("form")) | settings.js takes over the first <form> in the document. A search box or a logout form in the header would hijack the profile save. Logout must stay a GET link (auth/routes.py:107 accepts GET only). |
| `link[rel=manifest][href="/static/manifest.json"]` | other | app/app.py:155-163 (custom route with manifest content-type and no-cache) | Keep the href exactly. The theme-color metas (base.html:59-60) need new values for the redesign. |

#### JS-generated markup
- app/static/js/base.js:118-149: creates #update-banner (fixed bottom-0 left-0 right-0 z-50 bg-blue-500 text-white p-4) containing #update-now (bg-white text-blue-500 hover:bg-blue-50) and #update-later (border-white hover:bg-blue-600). It needs restyling, is pinned to the bottom of the screen, and covers sticky save bars and flash toasts.
- app/static/js/base.js:15-23, 152-185: toggles 'hidden' on #nav-offline-indicator and #mobile-offline-indicator, and 'offline' on body.
- base.html:203: toggles 'hidden' on .mobile-menu. base.html:232-238: toggles 'hidden' on #userDropdown and sets an inline style.transform on the chevron svg.
- base.html:208-214: sets inline style opacity:0 and translateY(8px) on the flash card, then removes it after 300 ms.
- base.html:220-221: toggles html.dark and writes localStorage.theme.

#### Hard-coded colours
- app/templates/base.html:59 <meta theme-color #ffffff> for light (new design: #0b5fb0 banner)
- app/templates/base.html:60 <meta theme-color #09090b> for dark (new design: #0b0f17)
- app/static/js/base.js:122,128,131 Tailwind bg-blue-500 / text-blue-500 / hover:bg-blue-50 / hover:bg-blue-600 in the update banner
- app/templates/base.html:121,155 text-red-600 dark:text-red-400 on Log out
- app/templates/base.html:171,173 text-red-500 / text-green-500 on the flash icons

#### Legacy CSS
- app/static/css/global.css (base.html:36, loaded on every page): * {scrollbar-width: thin; scroll-behavior: smooth}, hides number-input spinners, and .counter-group / .counter-decrements / .counter-increments for the scouting counters (used by scouting/add.html and edit.html). Keep it, or move it into tailwind.input.css.
- the inline <style> .animate-fade-in-up at base.html:65-71 (doubles as the flash JS hook)

#### Phone problems at 390px
- The theme toggle and hamburger are .btn.btn-icon (p-2 around a 20px icon), so 36x36px, under 44px (base.html:105, 129; tailwind.input.css:72-74).
- Mobile menu links are .menu-item (px-3 py-2 text-sm), about 36px tall (tailwind.input.css:140-142; base.html:143-158).
- The flash dismiss button is p-1 around a 16px icon, about 24px (base.html:176).
- The offline indicator is invisible on phones. #nav-offline-indicator is wrapped in 'hidden sm:contents' (base.html:99), and #mobile-offline-indicator sits inside the collapsed .mobile-menu (base.html:135-136), so a scout only sees the offline state after opening the hamburger.
- The flash toast (fixed inset-x-4 bottom-4 z-50, base.html:168) and the base.js update banner (fixed bottom-0 z-50) cover the sticky bottom save bars on scouting add/edit (z-20) for 5 s, or until dismissed.
- No primary navigation is visible on phones (nav is 'hidden sm:flex', base.html:88). Every page change needs the hamburger, which has no aria-expanded or aria-controls.
- Footer links are text-sm inline links about 20px tall (base.html:190-196).
- The viewport meta appears twice (base.html:5 and :58), and there is no viewport-fit=cover or safe-area padding even though manifest display is 'fullscreen'. The new blue top bar needs env(safe-area-inset-top) padding in the installed PWA.

#### Redesign notes
Build the new blue (#0b5fb0) or navy top bar while keeping every id and class above. Keep the three inline scripts (CSRF, theme init, shell handlers) in place and in this order. Consider adding aria-expanded to .mobile-menu-button and #userDropdownButton, but keep the 'hidden'-class toggling, or update base.html:202-241 to match. Put a phone-visible offline indicator outside the collapsed menu, but keep the #mobile-offline-indicator id, or update base.js. Move the flash toast to the top under the bar, or above the sticky save bar (bottom offset ~80px), so it never covers the save button. Restyle #update-banner in base.js. Update the theme-color metas and manifest colors. Add @font-face for app/static/fonts/'Richardson Brand Accelerator.otf' (quote the url, since the file name has spaces) and oxanium-vrb.ttf in tailwind.input.css, then run npm run build:css, bump the SW cache names, and add the fonts to STATIC_ASSETS. Popper can be removed. Tailwind only scans ./app/templates/**/*.html and ./app/static/js/**/*.js (tailwind.config.js:5), so class strings in any new JS directory would be purged. No dynamic class names are assembled in this template: 'nav-link-active' is a literal.

### app/templates/index.html

**Purpose:** Landing page: hero (logo, Castle, tagline, CTAs that differ for anonymous and logged-in users), three feature cards, a 'Ready to start' CTA for anonymous users, and a fixed PWA install button.

**Routes:** index() at app/app.py:96-98 (GET /, public in before_request app/app.py:138). Links: auth.register, auth.login, scouting.home, scouting.lighthouse, team.manage.

**Extends/includes:** extends base.html; block content only (no title block, so the title is 'Castle')

**JS:** app/static/js/pwa-install.js (defer)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `#installPWA` | id | app/static/js/pwa-install.js:9, 13, 23-25, 59-61, 68-71, 81-83 | A <button id="installPWA"> present in the DOM before pwa-install.js runs. JS sets an inline style.display of 'none', then 'block' when beforeinstallprompt fires. The inline style overrides the 'hidden' class, and the shown display is block, not flex, so center the icon with padding or text-align, or change the JS. A click calls the install prompt. |
| `#installMessage` | id | app/static/js/pwa-install.js:32-38 | Element starts with class 'hidden'. JS sets textContent, removes 'hidden', and re-adds it after 3 s. |
| `<script defer src=js/pwa-install.js>` | structure | index.html:104 | Load it deferred, after the #installPWA and #installMessage markup. It registers its own DOMContentLoaded listener. |
| `current_user.is_authenticated branches` | jinja-context | index.html:13-30, 82-92 | Anonymous: Get started (auth.register) and Log in (auth.login). Logged in: Scout (scouting.home), Compare (scouting.lighthouse), Team (team.manage). These show even without teamNumber, unlike the nav, which shows Join a team. |
| `page renders for anonymous and logged-in users` | other | tests/test_security.py:59 (anonymous GET /); tests/test_bug_fixes.py:26 (logged-in GET /); scripts/stress_test.py:246 (marker '<title>') | It must render with no context beyond current_user, and with the minimal test user from tests/app_harness.py:28. |

#### JS-generated markup
- app/static/js/pwa-install.js:13, 24, 60, 82: inline style.display on #installPWA
- app/static/js/pwa-install.js:34-37: textContent and the 'hidden' toggle on #installMessage

#### Hard-coded colours
- app/templates/index.html:40, 54, 68 bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400 feature icon chips
- app/templates/index.html:99 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 install FAB

#### Legacy CSS
- app/static/css/index.css is NOT linked by any template. It is dead (all its classes, such as animate-text, hover-lift, feature-card and install-btn-pulse, are unused), but it is listed in service-worker.js:14 STATIC_ASSETS. Delete it only together with that entry, or the service worker install fails.

#### Phone problems at 390px
- The install FAB (fixed bottom-6 right-6 z-50, 48px) overlaps the full-width 'Get started today' button and the footer links at the bottom of the page on a 390px screen, and sits where flash toasts appear.
- The h-28 logo with -my-4 and the mt-6 heading take most of the first screen. The CTA buttons are stacked and 44px tall (btn-lg py-2.5 text-base), which is fine.
- Feature card descriptions are text-sm, which is acceptable. The sm:grid-cols-3 grid stacks to one column on phones, which is fine.

#### Redesign notes
Use the CASTLE wordmark font for the h1 'Castle' and black page titles. The FAB can be restyled freely as long as the id stays and inline display:block works. Consider hiding the FAB once installed (pwa-install.js already handles appinstalled).

### app/templates/404.html

**Purpose:** Not-found page: icon, code, title, Go back (history.back) and Go home.

**Routes:** app/app.py:100-102 errorhandler(404). Note it returns status 200, not 404. Links: index.

**Extends/includes:** extends base.html; blocks title and content

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `button[onclick="history.back()"]` | other | 404.html:19 | Inline onclick that goes back. Keep a Go home link to url_for('index'). |
| `render context` | jinja-context | app/app.py:100-102 | Renders with request.endpoint == None and no extra context, so base.html must stay None-safe. It must not touch the DB. |

#### Hard-coded colours
- 404.html:14 text-blue-600 dark:text-blue-400 on the code number

#### Phone problems at 390px
- Buttons are .btn py-2.5 with text-sm, about 40px tall, under 44px (404.html:19, 22).

#### Redesign notes
Static page; free to rebuild. Use Oxanium for the 404 number. Keep the same structure in 429 and 500.

### app/templates/429.html

**Purpose:** Rate-limit page.

**Routes:** app/app.py:127-129 errorhandler(429) returns status 429. Triggered by the limiter on /auth/register (8/min), /auth/settings (15/min), /auth/change_password (5/min) and others.

**Extends/includes:** extends base.html; blocks title and content

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `button[onclick="history.back()"] + url_for('index')` | other | 429.html:19, 22 | Back and home actions. It must render with no extra context. |

#### Hard-coded colours
- 429.html:14 text-blue-600 dark:text-blue-400

#### Phone problems at 390px
- Buttons are about 40px tall, under 44px (429.html:19, 22).

#### Redesign notes
Same shell as 404. Note: when /auth/change_password returns 429, settings.js expects JSON, gets this HTML page, and response.json() throws, so the user sees the generic 'An error occurred' toast (settings.js:294-300).

### app/templates/500.html

**Purpose:** Server-error page.

**Routes:** app/app.py:104-107 errorhandler(500) and app/app.py:109-117 errorhandler(Exception) for non-HTTP exceptions, status 500.

**Extends/includes:** extends base.html; blocks title and content

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `button[onclick="history.back()"] + url_for('index')` | other | 500.html:20, 23 | It must render even when MongoDB is down. base.html must not add any DB-backed context; load_user already returns None on error (app/app.py:72-78). |

#### Hard-coded colours
- 500.html:15 text-blue-600 dark:text-blue-400

#### Phone problems at 390px
- Buttons are about 40px tall, under 44px (500.html:20, 23).

#### Redesign notes
Keep it dependency-free. Anything new added to base.html (a team badge or event name in the top bar, for example) must not raise when it is rendered from an error handler.

### app/templates/offline.html

**Purpose:** Standalone offline fallback page that the service worker serves for failed navigations. It shows the connection status, auto-retries every 15 s, and offers Back and Try Again.

**Routes:** offline() at app/app.py:175-177 (GET /offline.html). The SW caches it at install (service-worker.js:30, 34-37, 85) and serves it from the cache (service-worker.js:145-149, 200-215). Its JS fetches HEAD /static/logo.png?check=<ts> (offline.html:456). HEAD bypasses the SW cache via the non-GET rule at service-worker.js:194.

**Extends/includes:** NONE. Fully standalone, with inline <style> and <script>. It must not extend base.html or link tailwind.css, fonts or any other asset, because only /offline.html and /static/logo.png are in CRITICAL_ASSETS.

**JS:** inline <script> (offline.html:370-537)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `#status-text` | id | offline.html:372, 432, 439, 464 | A text element; JS sets textContent to 'Reconnected' or 'You are offline'. |
| `#connection-status` | id | offline.html:376, 433-434, 440-441, 465-466 | A pill container. JS sets inline style.backgroundColor and style.color (green or red rgba and hex). |
| `#retry-info` | id | offline.html:373, 435, 442, 467, 487 | A text element; JS sets textContent. |
| `#countdown` | id | offline.html:378, 514, 530 | A text element; JS sets textContent to 'Auto retry in N seconds'. |
| `#retry-button` | id | offline.html:374, 395-397, 451-452, 483-484 | A <button>; click calls checkConnection(true). JS sets textContent and disabled. Existing bug: textContent = 'Checking' deletes the child #loading-spinner. |
| `#back-button` | id | offline.html:375, 400-402 | A <button>; click calls history.back(). |
| `#loading-spinner` | id | offline.html:377, 450, 482 | JS sets style.display between 'inline-block' and 'none'. It currently starts with inline style display:none. |
| `.wifi-slash + @keyframes blink` | css-hook | offline.html:379, 436-437, 443 | The first .wifi-slash element (an SVG <line>) gets style.animation = 'blink 2s infinite' and style.opacity. The page CSS must define @keyframes blink. |
| `localStorage 'offlineMode'` | other | offline.html:534; written by app/static/js/base.js:26, 166, 184 | Reads offlineMode === 'false' (base.js never writes 'false', so this branch is effectively dead). |
| `img[src="/static/logo.png"]` | other | offline.html:318; service-worker.js:36 CRITICAL_ASSETS | Use only /static/logo.png, or add any new image or font to CRITICAL_ASSETS or STATIC_ASSETS. Dark mode currently inverts logo.png through a CSS filter (offline.html:42-44) because logo-dark.png is not cached. |
| `page served at arbitrary URLs; window.location.reload() retry` | (missed, verified) | app/static/js/service-worker.js:141-149 returns the cached /offline.html as the response to ANY failed navigation, so the address bar still shows /scouting/add or similar. The reload at offline.html:418 and :471 re-requests that original URL, and the Back button at :401 uses history.back(). | Every asset and fetch URL inside offline.html must be root-absolute (/static/...), because relative URLs resolve against the failed page's path. Keep retry as location.reload(), not a redirect to / or /offline.html, or the user loses the page they were opening. |

#### JS-generated markup
- offline.html:432-443, 464-469: inline style backgroundColor 'rgba(34, 197, 94, 0.1)' / 'rgba(239, 68, 68, 0.1)' and color '#22c55e' / '#ef4444' on #connection-status, plus the style.animation and opacity on .wifi-slash
- offline.html:450-452, 482-484: #retry-button textContent 'Checking' / 'Try Again' (destroys the spinner child) and the disabled toggle

#### Hard-coded colours
- offline.html:6-7 theme-color #fafafa / #09090b
- offline.html:10-26 :root palette #fafafa #ffffff #e4e4e7 #18181b #71717a #52525b #f4f4f5 #2563eb #1d4ed8 #1e40af #d4d4d8 #3f3f46 rgba(59,130,246,0.6)
- offline.html:28-40 dark palette #09090b #18181b #27272a #f4f4f5 #a1a1aa #d4d4d8 rgba(39,39,42,0.6) #3f3f46 #e4e4e7
- offline.html:183-184 rgba(239,68,68,0.1) and #ef4444 for #connection-status
- offline.html:198 #ffffff and :257-259 rgba(255,255,255,0.3) / white spinner
- offline.html:433-434, 440-441, 465-466 JS inline colors

#### Legacy CSS
- All CSS is inline in this file (offline.html:9-313) and must stay inline.

#### Phone problems at 390px
- The .button padding is 10px plus a 20px line-height plus a 1px border, about 42px tall, under 44px (offline.html:192-211).
- Text is 12-14px: .retry-countdown 12px (offline.html:271) and #connection-status 13px (:177).
- Dark mode follows prefers-color-scheme only and ignores the in-app localStorage.theme override (offline.html:28).

#### Redesign notes
Re-skin it with the new tokens (#eef2f7 body, white card, #0b5fb0; navy #0b0f17 / #141a26 / #1f2838 / #2f7ae0 in dark) as inline CSS variables. Use system fonts, or add the brand fonts to the SW CRITICAL_ASSETS. Consider reading localStorage.theme inline to match the in-app theme. Fix the spinner bug by putting the label in its own span. Pre-existing: /offline.html is NOT in the before_request public allowlist (app/app.py:137-143), so an anonymous visitor's SW install caches a redirect to /auth/login as offline.html.

### app/templates/forgot-password.html

**Purpose:** Static instructions to email an admin, with a click-to-copy email button.

**Routes:** forgot_password() at app/auth/routes.py:58-61 (GET /auth/forgot-password, public in app/app.py:142). Links: auth.login, '/'.

**Extends/includes:** extends base.html; blocks title and content

**JS:** inline <script> copyEmail (forgot-password.html:43-71)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `button[onclick="copyEmail()"]` | other | forgot-password.html:19, 44-70 (global function copyEmail) | copyEmail must stay a global function (inline onclick), or be rebound with addEventListener. |
| `#email-text` | id | forgot-password.html:45 | Its textContent is exactly the address to copy (techrobotics334@gmail.com). Do not add extra text or icons inside it. |
| `#copy-status` | id | forgot-password.html:46-67 | JS sets textContent and swaps the classes text-zinc-500/dark:text-zinc-400 for text-green-600/dark:text-green-400 or text-red-600/dark:text-red-400. If the neutral classes change, update the neutral array at :47. |

#### JS-generated markup
- forgot-password.html:50-67 swaps green, red and neutral text classes on #copy-status

#### Hard-coded colours
- forgot-password.html:51, 56 text-green-600 / dark:text-green-400
- forgot-password.html:61, 66 text-red-600 / dark:text-red-400
- forgot-password.html:22 group-hover:text-blue-600

#### Phone problems at 390px
- #copy-status is text-xs, 12px (forgot-password.html:26).
- The 'Go to the home page' link is text-sm, about 20px tall (forgot-password.html:39).

#### Redesign notes
navigator.clipboard needs HTTPS; the production site is HTTPS. The classes are literal strings, so no safelist is needed.

### app/templates/auth/login.html

**Purpose:** Login form (email or username, password with show/hide, remember me).

**Routes:** login() at app/auth/routes.py:25-55 (GET/POST /auth/login, public in app/app.py:140). POST reads request.form 'login', 'password', 'remember' (bool of any value, :32-34) and redirects to ?next= when it is safe (:45-47). Re-render context: form_data dict (:39 {'login': ...}, :55 {}). Links: auth.forgot_password, auth.register.

**Extends/includes:** extends base.html; blocks title and content

**JS:** inline <script> togglePassword (login.html:72-90)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `form[method=POST] (no action attribute)` | structure | app/auth/routes.py:45 (request.args.get('next')) | POST to the current URL, so the ?next= query string survives. Do not add action="{{ url_for('auth.login') }}", which drops next. |
| `input[name=csrf_token]` | form-field-name | Flask-WTF CSRFProtect (app/app.py:17, 58) | <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"> inside the form. Without it the POST fails and redirects home with 'Your session expired' (app/app.py:119-125). |
| `input[name=login]#login` | form-field-name | app/auth/routes.py:32; login.html:23 value=form_data.get('login','') | name="login", a text input that accepts an email or a username, refilled from form_data. |
| `input[name=password]#password` | form-field-name | app/auth/routes.py:33; login.html:74-78 (togglePassword switches its type) | name="password", id="password". |
| `input[name=remember]#remember` | form-field-name | app/auth/routes.py:34 | A checkbox named remember; any submitted value counts as true. |
| `#eye-icon + onclick="togglePassword()"` | id | login.html:42-43, 73-89 | togglePassword is a global function, and #eye-icon is an <svg> whose innerHTML is replaced with <path> markup. |

#### JS-generated markup
- login.html:79-87 replaces the #eye-icon innerHTML with SVG paths (stroke=currentColor, no colors)

#### Phone problems at 390px
- The 'Remember me' checkbox is 16x16px (.checkbox h-4 w-4) and its label row is about 20px tall (login.html:51-58).
- The 'Forgot password?' and 'Sign up' links are text-sm inline links about 20px tall (login.html:31, 68).

#### Redesign notes
autocomplete="off" on the form (login.html:15) works against password managers; consider autocomplete="username" and "current-password". Keep inputs at 16px or more font size so iOS does not zoom (.input uses text-base and sm:text-sm today).

### app/templates/auth/register.html

**Purpose:** Sign-up form (email, username, password with a strength bar and requirement checks, confirm password).

**Routes:** register() at app/auth/routes.py:64-104 (GET/POST /auth/register, public in app/app.py:141, rate-limited to 8/min). POST reads 'email', 'username', 'password', 'confirm_password'. Re-render context: form_data {email, username}. On success it redirects to auth.login.

**Extends/includes:** extends base.html; blocks title and content

**JS:** inline <script> password strength and validation (register.html:83-143)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `form[method=POST] + input[name=csrf_token]` | form-field-name | app/app.py:58 CSRFProtect | Hidden csrf_token inside the form; POST to the current URL. |
| `input[name=email]#email` | form-field-name | app/auth/routes.py:72; register.html:23 | name="email", refilled from form_data.get('email'). |
| `input[name=username]#username` | form-field-name | app/auth/routes.py:73; register.html:33 | name="username", refilled from form_data.get('username'). |
| `input[name=password]#password` | form-field-name | app/auth/routes.py:74; register.html:85, 132, 140 | name and id both 'password'; input listener. |
| `input[name=confirm_password]#confirm_password` | form-field-name | app/auth/routes.py:75; register.html:86, 91, 133, 141 | name and id both 'confirm_password'. |
| `#register-button` | id | register.html:87, 137 | The submit button; JS toggles its .disabled property. It starts enabled. |
| `.strength-bar` | class | register.html:88, 114-126 | A single element (the first match). JS REPLACES its whole className with 'strength-bar h-full rounded-full transition-all duration-300', then adds w-0, w-1/4 bg-red-500, w-2/4 bg-amber-500, w-3/4 bg-blue-500 or w-full bg-green-500. Any new design classes on it are wiped: style it through its wrapper (.password-strength-meter) or update the reset string. |
| `[data-requirement="length"], [data-requirement="match"] with descendant .check-icon` | data-attr | register.html:92-111 | Exactly these two data-requirement values, matching the keys of the checks object. Each holds one .check-icon descendant. JS adds or removes met, text-green-700 and dark:text-green-400 on the item. On the icon it toggles unmet/met, border-zinc-300, dark:border-zinc-600, bg-green-50, border-green-500, text-green-600, dark:bg-green-500/10 and dark:text-green-400, and sets textContent to '✓' or '•'. |

#### JS-generated markup
- register.html:101-111 toggles the green, zinc, met and unmet classes and the ✓/• text on .requirement-item and .check-icon
- register.html:114-126 resets the .strength-bar className and adds width and color classes (bg-red-500 / bg-amber-500 / bg-blue-500 / bg-green-500)

#### Hard-coded colours
- register.html:102-110 text-green-700, dark:text-green-400, bg-green-50, border-green-500, text-green-600, dark:bg-green-500/10, border-zinc-300, dark:border-zinc-600
- register.html:119-125 bg-red-500, bg-amber-500, bg-blue-500, bg-green-500

#### Legacy CSS
- app/static/css/register.css is NOT linked anywhere (dead). It defines .password-strength-meter, .strength-bar, .very-weak, .weak, .fair, .good and .strong with hex colors #e5e7eb #ff4444 #ffbb33 #ffeb3b #00C851 #007E33 #666. Safe to delete; it is not in the SW STATIC_ASSETS list.

#### Phone problems at 390px
- The requirement check icons are 16px with text-[10px] glyphs (register.html:50, 54), which are hard to read.
- The strength meter is h-1 (4px) (register.html:45).
- The 'Log in' link is text-sm, about 20px tall (register.html:79).

#### Redesign notes
The color classes are literal strings in the template, so Tailwind's scan of templates/**/*.html picks them up. If this script moves to a .js file, keep it under app/static/js/ so the classes are still scanned. Swapping in new token colors means editing these JS class lists.

### app/templates/auth/profile.html

**Purpose:** Public profile: avatar, username, team badge, an Edit button for the user's own profile, the About text, and Activity (member since and last active) and Current team cards.

**Routes:** profile(username) at app/auth/routes.py:146-154 (GET /auth/profile/<username>; requires login through before_request app/app.py:146-147). It redirects home with a flash when the user is not found. Links: auth.profile_picture(user_id=profile_user.id), team.view(team_number), auth.settings.

**Extends/includes:** extends base.html; block content only (title is 'Castle')

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `profile_user (User model, app/models.py:17-30)` | jinja-context | profile.html:7-75 | Uses profile_user.id, .username, .teamNumber, .description (whitespace-pre-line), .created_at.strftime('%B %d, %Y') (:54, which raises if created_at is None), and .last_login (guarded at :58). The Edit button shows only when current_user.id == profile_user.id. |

#### Hard-coded colours
- profile.html:13 badge-blue with hover:bg-blue-100 dark:hover:bg-blue-500/20
- profile.html:75 text-blue-600 group-hover:text-blue-700 dark:text-blue-400

#### Phone problems at 390px
- The 'Team N' badge link is .badge (text-xs py-0.5), about 20px tall (profile.html:13).
- The 'Edit profile' button is .btn py-2 text-sm, about 36px tall (profile.html:19).
- The username h1 uses truncate, so long names are cut off on a 390px screen (profile.html:11).

#### Redesign notes
Use Oxanium for the team number (profile.html:73). Guard created_at (for example, {{ profile_user.created_at.strftime(...) if profile_user.created_at else '—' }}). There is no JS, so the markup is free to change.

### app/templates/auth/settings.html

**Purpose:** Account settings: profile form (photo upload, username with a live availability check, About me), password change via JSON fetch, delete account via JSON fetch, and a toast area.

**Routes:** settings() at app/auth/routes.py:116-143 (GET/POST /auth/settings, 15/min). POST reads request.form['username'] and ['description'] and request.files['profile_picture'] (auth_utils.py:297-325; extensions png, jpg, jpeg, gif per app/utils.py:75). The JS also calls POST /auth/check_username (routes.py:170-195), POST /auth/change_password (routes.py:198-242; requires the X-Requested-With: XMLHttpRequest header, 5/min, returns {success, message, redirect}) and POST /auth/delete_account (routes.py:245-266, returns {success, redirect | message}).

**Extends/includes:** extends base.html; block content only (title is 'Castle'); loads app/static/js/auth/settings.js

**JS:** app/static/js/auth/settings.js

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `#notification-area` | id | app/static/js/auth/settings.js:3, 52 | An empty container where toast cards are appended. It is fixed bottom-right today. |
| `first <form> in the document (the profile form)` | structure | app/static/js/auth/settings.js:79-107 | document.querySelector('form') must resolve to the profile form, so no other <form> may come before it in base.html or this page. Submit is intercepted: fetch POST to window.location.href with new FormData(this), then a reload or a follow of the redirect. The form must contain the hidden csrf_token plus inputs named username, description and profile_picture. Keep the password inputs OUTSIDE this form; they are read by id and must not be submitted by Enter into the profile form. |
| `#profile_picture (input type=file name=profile_picture)` | form-field-name | app/static/js/auth/settings.js:109-161 (change listener; replaces .files through a DataTransfer at :147); app/auth/routes.py:124 | id and name both profile_picture, accept=image/*. It is visually hidden and opened by <label for="profile_picture">, so the label/for pairing must stay. |
| `#upload-info` | id | app/static/js/auth/settings.js:119, 125 | A text element; JS sets textContent to the file name. |
| `.profile-preview` | class | app/static/js/auth/settings.js:130 | The first element with this class must be the avatar <img> (querySelector); JS sets src to a data URL. Do not put this class on the header avatar. |
| `#username[name=username][onkeyup="checkUsername(this.value)"]` | form-field-name | settings.html:72; settings.js:166-220; auth_utils.py:304 | name="username" with the value current_user.username. checkUsername stays a global function, called inline (or rebind with addEventListener('keyup'/'input')). |
| `#username-status` | id | app/static/js/auth/settings.js:170-217 | JS replaces its innerHTML with a colored <span> message. |
| `#description textarea[name=description]` | form-field-name | auth_utils.py:312-313 | name="description". The content is exactly {{ current_user.description }} with no added whitespace or indentation inside the textarea, because the value is saved verbatim. One newline right after the opening tag is fine (the parser strips it). |
| `#current_password, #new_password, #confirm_new_password` | id | app/static/js/auth/settings.js:223-227, 283-285 | Exactly these three ids. They are read and cleared by id, and sent as JSON keys current_password, new_password and confirm_password. |
| `onclick="changePassword()" / onclick="confirmDeleteAccount()"` | other | settings.html:152, 178; settings.js:222, 303 | Global functions. The buttons must be type=button. |
| `script[src*="js/auth/settings.js"][data-current-username]` | data-attr | app/static/js/auth/settings.js:164 | A classic (non-module) script with data-current-username="{{ current_user.username }}", placed AFTER the page markup, because it queries the form and #profile_picture at parse time without waiting for DOMContentLoaded. |
| `GET /auth/settings renders` | other | tests/app_harness.py:45-46 | Must render with the minimal test user (username 'tester', teamNumber 334, no email, description, created_at or profile picture) and include the csrf-token meta from base.html. |

#### JS-generated markup
- app/static/js/auth/settings.js:34-52 showNotification builds a toast card ('card flex items-start gap-3 p-4 shadow-lg animate-slide-in' plus inline animation slideIn) with icon colors text-green-500 / text-red-500 / text-amber-500 / text-blue-500 (:6-19) and an inline dismiss button. The message goes in through innerHTML (:43), including server data.message, so prefer textContent in a rebuild.
- app/static/js/auth/settings.js:62-76 injects a <style> with @keyframes slideIn
- app/static/js/auth/settings.js:180-217 #username-status innerHTML spans: text-amber-600/dark:text-amber-400, text-red-600/dark:text-red-400, text-zinc-500/dark:text-zinc-400, text-green-600/dark:text-green-400
- app/static/js/auth/settings.js:125, 130 #upload-info text and the .profile-preview src

#### Hard-coded colours
- app/static/js/auth/settings.js:8-17 text-green-500 / text-red-500 / text-amber-500 / text-blue-500
- app/static/js/auth/settings.js:181, 187, 194, 208, 211, 217 status span color classes
- settings.html:168 border-red-200 dark:border-red-500/30 danger card

#### Legacy CSS
- 'animate-slide-in' (settings.js:35) is defined only in the dead index.css, so it has no effect. The animation comes from the inline style plus the injected keyframes.

#### Phone problems at 390px
- Buttons are .btn py-2 text-sm, about 36px tall: 'View profile' (settings.html:15), the 'Change photo' label (:43), and Save, Change password and Delete account (:99, :153, :179). All are under 44px.
- .input uses py-2 with text-base, about 42px tall (tailwind.input.css:81).
- #username-status is text-xs and .help is text-xs, 12px (settings.html:58, 74).
- The #notification-area toasts (fixed inset-x-4 bottom-4 z-50) would cover a new sticky bottom save bar.
- The 'Save profile' button sits at the bottom of a card in the middle of the page and is not sticky. The page has three independent actions, so only the profile form fits the new sticky save-bar pattern.

#### Redesign notes
Pre-existing issues the rebuild may fix without changing behaviour: (1) Compressor.js is NOT loaded on this page, so settings.js:136 throws a ReferenceError that is caught and photos upload uncompressed. Add <script src="https://cdnjs.cloudflare.com/ajax/libs/compressorjs/1.2.1/compressor.min.js"> in {% block head %}, as team/settings.html:3 does. (2) The POST is sent by fetch and the flashed 'Settings updated successfully' is consumed by that discarded response (base.html:165 calls get_flashed_messages), so after the reload the user sees no confirmation. Consider showNotification on success. (3) accept=image/* lets an iPhone pick HEIC, which allowed_file rejects silently while the flash still says success. (4) An empty description cannot clear the bio (auth_utils.py:312). If a sticky save bar is added, keep it inside the profile <form> (or use form="..."), and make sure no other form comes first.

### app/static/js/service-worker.js + app/static/manifest.json + app/static/js/notifications.js (PWA shell, no template)

**Purpose:** Offline cache, update flow, connectivity messages, push notifications, install manifest. Its cache list must change whenever the rebuild adds, renames or deletes static files.

**Routes:** /service-worker.js (app/app.py:165-173, Service-Worker-Allowed: /, no-cache; public at app/app.py:139), /static/manifest.json (app/app.py:155-163), /offline.html (app/app.py:175-177). notifications.js calls GET /notifications/vapid-public-key, POST /notifications/subscribe and POST /notifications/unsubscribe (app/notifications/routes.py:38, 45, 98). Its POST /notifications/test route does not exist. The SW notification action calls PUT /team/assignments/<id>/status (CSRF-exempt at app/app.py:94).

**Extends/includes:** service-worker.js is registered by base.js:53. notifications.js is loaded only by app/templates/team/manage.html:560, before team/manage.js, which uses the global notificationManager (manage.js:80).

**JS:** app/static/js/service-worker.js; app/static/js/notifications.js; app/static/js/pwa-install.js; app/static/js/base.js

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `STATIC_ASSETS (service-worker.js:11-31)` | other | service-worker.js:95-105 (install cache.addAll), :241 (cache-first match via event.request.url.includes(asset)) | Every entry must exist, because cache.addAll is all-or-nothing: one 404 (deleting index.css, for example) fails the install and kills offline mode. Add the new fonts URL-encoded, since the check compares against the encoded request URL: '/static/fonts/Richardson%20Brand%20Accelerator.otf' and '/static/fonts/oxanium-vrb.ttf'. Add any new page JS needed offline. |
| `CACHE_NAME / STATIC_CACHE_NAME / DYNAMIC_CACHE_NAME / PAGE_CACHE_NAME (service-worker.js:1-4, 'v14')` | other | service-worker.js:288 (activate deletes other caches) | Bump them when tailwind.css or JS changes. Static assets are served cache-first, and url_for('static') adds no version query, so without a bump returning phones keep the old tailwind.css and the new markup renders unstyled. |
| `CRITICAL_ASSETS ['/offline.html', '/static/logo.png'] (service-worker.js:34-37)` | other | service-worker.js:85, 145, 178, 202, 261 | The offline page and its only image. Any asset offline.html starts to use must be added here. |
| `fetch bypass rules (service-worker.js:193-197) and network-only navigation (:229-238)` | structure | tests/test_browser_resilience.js:6-52 | /api/, /auth/, the ?checkOnline param and non-GET requests always go to the network. Navigations are never served from the cache; they fall back to offline.html. Non-GET failures must reject. |
| `postMessage {type:'OFFLINE_STATUS', isOffline} / {action:'skipWaiting'}` | other | service-worker.js:40-45, 63-69, 120-127 ↔ app/static/js/base.js:97-107, 142 | The message contract between the SW and base.js. |
| `.assignment-reminder-btn[data-assignment-id], #assignmentReminderModal, #reminderAssignmentId, #saveAssignmentReminder, #assignmentReminderTime, #testNotificationBtn` | id | app/static/js/notifications.js:291-295, 299, 313-344; markup in app/templates/team/manage.html:337-342, 523-557; app/static/js/team/manage.js:514-523 | These live in the team/manage group, but notifications.js depends on them. The reminder buttons carry data-assignment-id. The modal toggles 'hidden'. #reminderAssignmentId is an input (its .value is set). #assignmentReminderTime is a <select> with minute values (parseInt). #testNotificationBtn is not used in any template, so that code is dead. |

#### JS-generated markup
- service-worker.js:151-172: inline fallback HTML 'You're Offline' with h1 color #3b82f6 (used only if offline.html is not cached)
- service-worker.js:208-210: minimal offline HTML fallback
- notifications.js:304, 306, 318, 337, 340: alert() dialogs (no markup)

#### Hard-coded colours
- app/static/manifest.json:7 background_color #ffffff (new design: #eef2f7 or #0b5fb0)
- app/static/manifest.json:8 theme_color #3b82f6 (new design: #0b5fb0)
- service-worker.js:159 h1 color #3b82f6

#### Legacy CSS
- service-worker.js:14 keeps the dead /static/css/index.css in the cache list

#### Redesign notes
manifest display is 'fullscreen' (manifest.json:6), so the installed PWA has no status bar. The new top bar should respect safe-area insets. Push notification icon and badge paths /static/images/logo.png and /static/images/badge.png (service-worker.js:360-361, 397-398, 470, 476, 485) do not exist; app/static/images holds only default_logo.png, default_profile.png, field-2025.png and field-2026.png. shouldSkipCache references an undefined NO_CACHE_URLS (service-worker.js:501), but it is never called.

### Other missed hooks (verified)
- `app/templates/base.html:7-24 (CSRF IIFE)` `inline CSRF wrapper, as run in the test sandbox` (used by tests/test_browser_resilience.js:252-260. The sliced IIFE runs in vm.runInNewContext with only {window, document, Request, Headers, URL}. document is mocked as {querySelector: () => ({content: 'tok123'})}, and window has only location.href, location.origin and fetch.): Read the token as document.querySelector(...).content. getAttribute('content'), document.head..., getElementsByName or dataset all throw against the mock. Reach location and fetch only through window.location / window.fetch: a bare location, fetch, self or globalThis is a ReferenceError in the sandbox. Keep the wrapper assigning window.fetch.
- `app/templates/base.html:65-71 (inline .animate-fade-in-up / @keyframes toast-in)` `.animate-fade-in-up, and an element with class "container"` (used by app/static/js/scout/form-canvas.js:16-24, 87-92. showStatus builds a toast with className 'animate-fade-in-up fixed inset-x-4 bottom-4 z-50 ...' and appends it to document.querySelector('.container'). No template that extends base.html has class 'container' today (the only one is offline.html:316), so showStatus currently returns early.): Keep .animate-fade-in-up and its keyframes defined globally (in base.html or tailwind.input.css), because JS-built toasts reuse it. Do not put Tailwind's 'container' class on <main> or any shell wrapper by accident. If you do, these canvas toasts suddenly appear fixed at bottom-4 z-50, on top of the sticky save bar.
- `app/templates/base.html:164 (<main> px-4)` `-mx-4 ... px-4 edge-bleed scroll navs` (used by app/templates/lighthouse.html:96, app/templates/lighthouse/auton.html:23 and app/templates/scouting/leaderboard.html:11. Each is a nav with class '-mx-4 flex gap-2 overflow-x-auto px-4 ... sm:mx-0'.): The inventory lists only the scouting add/edit save bars as depending on the 16px phone gutter. These three horizontally scrolling tool navs also cancel main's px-4 and must change with it.
- `app/templates/auth/login.html:39` `button[type=button][onclick=togglePassword()] inside the login <form>` (used by login.html:15-63. The show/hide button sits inside form[method=POST].): Keep type="button" explicitly. A <button> inside a form defaults to submit, so a rebuilt eye toggle without it submits the login form, often with an empty password. The same applies to any new icon button added inside the register form or the settings profile form.
- `app/templates/auth/settings.html:32` `form[method=POST][enctype=multipart/form-data]` (used by app/auth/routes.py:124 (request.files.get('profile_picture')); this is the native fallback when app/static/js/auth/settings.js:79 does not bind (for example when the script loads before the markup and querySelector('form') returns null)): Keep method="POST" and enctype="multipart/form-data" on the profile form. Without enctype, a native submit sends no file and the photo silently does not change.
- `app/templates/auth/profile.html:35-41` `p.whitespace-pre-line with {%- if -%} / {%- else -%} / {%- endif -%}` (used by profile.html:35. whitespace-pre-line keeps newline characters, and the dash whitespace control is what strips the template's own newlines and indentation around the description.): Keep the {%- -%} trimming, or put {{ profile_user.description }} directly against the tags. Otherwise every bio renders with an empty first line and trailing blank space.
- `app/templates/base.html:245 (base.js) → app/templates/team/manage.html:560` `service worker registration that notifications.js depends on` (used by app/static/js/notifications.js:76-80 awaits navigator.serviceWorker.ready ('Instead of registering a new service worker, get the existing registration'). That promise resolves only because base.js:50-56 registers /service-worker.js on window load. initNotificationUI, which binds .assignment-reminder-btn and #saveAssignmentReminder, runs only after init resolves (notifications.js:276-286).): base.js, with its SW registration, must still load on every page that loads notifications.js. If it does not, ready never resolves and the reminder save handler never binds.

### Other missed items (verified)
- Settings success toast would lie. UserManager.update_user_settings returns a tuple: (False, 'Username is already taken'), (success, message), or (True, ...) (app/auth/auth_utils.py:297-334). routes.py:126-134 tests `if success:` on that tuple, which is always truthy, so the server always flashes 'Settings updated successfully', even when the username is taken. The inventory suggests calling showNotification on success; that would repeat the false success unless the route is fixed first.
- Hardcoded old page colors in the Tailwind base layer, not listed: app/static/css/tailwind.input.css:16 `body { @apply bg-zinc-50 ... dark:bg-zinc-950 }` (new: #eef2f7 / #0b0f17) and :20 `:focus-visible ... ring-blue-500/60 ring-offset-white dark:ring-offset-zinc-950`. The focus-ring offset color must match the new body and surface colors, or a white or zinc halo shows around focused controls on the navy background.
- theme-color metas (base.html:59-60) are keyed on prefers-color-scheme only, and the in-app toggle (base.html:218-222) never updates them. With the new blue (#0b5fb0) and navy (#0b0f17) bars, a user who forces dark mode on a light-mode phone gets mismatched browser and status-bar chrome, unless the toggle also rewrites meta[name=theme-color].
- compare.js:237-245 MutationObserver watches every attribute change on <html> and redraws the radar chart on any 'class' mutation, not only dark. A rebuild that toggles other classes on <html>, such as a scroll lock for a drawer menu (overflow-hidden), triggers a chart rebuild on each toggle. Put those classes on <body> instead.
- Cascade order: global.css (base.html:36) loads after tailwind.css (base.html:26) and is unlayered, so any class rule added there beats Tailwind utilities of equal specificity, including .hidden. All show/hide in this group toggles the 'hidden' class (.mobile-menu, #userDropdown, #nav-offline-indicator, #mobile-offline-indicator, #installMessage), so a new display:flex rule in global.css, or any rule with an ID selector, on those elements makes them stuck visible.
- The service worker precaches CSS and JS under ?v=<timestamp> keys (service-worker.js:95-105), but the fetch handler calls caches.match(event.request) without ignoreSearch (:243). The precached tailwind.css and JS copies are never served; those files only become cache-first after one online load under the new worker (put at :252-255). Adding new page JS to STATIC_ASSETS does not by itself make it available offline. Fonts and images are precached without ?v (:98), so the new .otf and .ttf entries will match.
- Header logo on the new blue bar: base.html:82-83 swaps logo.png (black-ink line art, verified visually) for logo-dark.png (white) only under html.dark. On a #0b5fb0 light-mode bar the black logo has poor contrast, so the header needs the white logo in both modes. The swap is driven by dark:hidden/dark:block, so change it deliberately. logo-dark.png is not in STATIC_ASSETS.
- Do not rename or move app/static/logo.png. CI copies it into the desktop wrapper (.github/workflows/build-linux.yml:42 and build-flatpak.yml:58 run `cp app/static/logo.png standalone/src/castle/resources/logo.png`), and it is the only image in the service worker's CRITICAL_ASSETS (service-worker.js:34-37).
- On Vercel, the custom /static/manifest.json route (app/app.py:155-163, manifest content-type and no-cache) never runs, because vercel.json sends /static/(.*) to @vercel/static. Manifest color changes may be cached there and are served with the default content-type.
- The flash auto-dismiss (base.html:207-215) binds on DOMContentLoaded and only covers flash elements that exist at that moment. It works today because the inline script sits at the end of <body>. Moving it into an async or type=module script that can run after DOMContentLoaded means flashes never auto-dismiss.

## Group: scout-form

### Shared findings
- CANVAS OPTION MISMATCH: form-canvas.js:15 passes `externalUpdateUIControls`, but Canvas.js:33 reads `options.updateUIControls`. So add.js:495-517 and edit.js:126-155 updateUIControls never run. The live code is the Canvas fallback at Canvas.js:2029-2060, which needs #pathColorPicker, its .clr-field ancestor and button, #pathThickness and #pathThicknessValue.
- CANVAS TOASTS ARE SILENT: form-canvas.js:17 appends showStatus toasts to document.querySelector('.container'). No .container exists in base.html or the forms (only offline.html:316 has one), so 'Path saved', 'View reset', 'Existing path loaded' and similar never show. Adding a `.container` class anywhere in the new layout will suddenly make them render inside that element.
- HARD DEPENDENCY CHAIN: Canvas.js:112 calls `localforage.createInstance` from an unversioned jsdelivr gh URL (add.html:2, edit.html:3). The service worker does not cache cross-origin requests (service-worker.js:217-225). If the CDN fails at a venue, the Canvas constructor throws inside initScoutFormCanvas (add.js:43 / edit.js:3, first statement of DOMContentLoaded). That kills event loading, tabs and the JS submit, so the form natively posts without _event_key or auto_path. Self-hosting or pinning localforage is behaviour-preserving and recommended. Coloris is required as a global before form-canvas.js:144.
- SERVICE WORKER STALENESS: STATIC_ASSETS (service-worker.js:11-31) are cache-first (241-260) and include /static/css/tailwind.css, global.css, Canvas.js, scout/add.js, scout/form-canvas.js, scout/fuel-input.js and images/field-2026.png. tailwind.css, Canvas.js and form-canvas.js load without a ?v query. After the rebuild, bump CACHE_NAME/STATIC_CACHE_NAME/DYNAMIC/PAGE (v14) and CACHE_VERSION, or scouting phones will run old JS and CSS against new markup. edit.js, coloris.js/.css and scouting.css are not in the list. Add the new fonts (static/fonts/Richardson Brand Accelerator.otf, oxanium-vrb.ttf) to STATIC_ASSETS if they should work offline.
- SERVER FIELD SEMANTICS (scouting_utils.py:71-114, 149-175, 288-375): herd_balls and ferrying_did must post the exact string 'true' (_is_checked). auto_climb and climb_success are bool(any value). Fuel, climb_level, defense_rating, herd_rating and ferrying_rating go through int(). On add, blank FUEL_FIELDS become 0 (records.py:55-57). On edit, a blank number makes the whole update fail. robot_disabled values must be exactly None/Partially/Full. event_code is the event DISPLAY NAME, match_number is the TBA label ('Qual N', 'Semifinal S-M', 'Final N', from TBA.py:100-107) parsed by match13_fuel.py:38-49, and _event_key is the TBA key.
- EXISTING SERVER QUIRKS a markup rebuild must not 'fix' silently: auto_climb is not saved on edit (updated_data at scouting_utils.py:359-365 omits it). response_to_defense_rating is posted by add but never stored (_record_fields has no key; _match_list.html:125 shows it). The edit route validates 'auto_path_coords' (records.py:152), a field that is never posted, so edited auto_path is stored as a raw string while add stores a list. On edit, the red alliance radio is disabled (edit.html:77-78) and red records rely on the server default 'red' (scouting_utils.py:354).
- TAILWIND PURGE/SAFELIST: content globs are ./app/templates/**/*.html and ./app/static/js/**/*.js (tailwind.config.js:5). The safelist (tailwind.config.js:8) covers only (bg|text|border)-(red|blue)-(100|500|800) with no dark: variants. add.js:459 builds `border-${alliance}-500` and `dark:border-${alliance}-500` at runtime and survives only because add.js:458/462 contain the literals. JS toggles .active (tabs, tools, fill, readonly) and .hidden (tabs, herd/ferry groups, dropdown list, #loadFile); their styles come from [&.active]: arbitrary variants in Jinja-set strings (add.html:37-39,178; edit.html:33-36,183). Run npm run build:css after the rebuild.
- .hidden TOGGLING: tab contents, #herd_rating_group, #ferrying_rating_group and the JS dropdown list are hidden with Tailwind's `hidden` class. Do not give them responsive display utilities (sm:block, md:grid, etc.), because those win over .hidden at breakpoints and would show every tab at once.
- GLOBAL CLASS/ID COLLISIONS: add.js:467-468 and edit.js:103-104 use document-wide querySelectorAll('.tab-button' / '.tab-content'). add.js reads #events and #event_matches. base.html:208 deletes children of any `.animate-fade-in-up` after 5s. The new base layout must not reuse these.
- KEYBOARD HIJACK (existing): Canvas.js:1695-1782 binds window keydown with no input-target guard. Ctrl+A/C/X/V/Z/Y/P/R/L/H/S/F and Backspace/Delete (when strokes are selected) call preventDefault even while typing in notes textareas. form-canvas.js:345-426 guards only INPUT/TEXTAREA (not SELECT or contenteditable). Any new text-entry control inherits this.
- CANVAS SIZING: Canvas.js:185-199 sizes the canvas only from #autoPathContainer at construction, on window resize (1048) and on DPR change (138-146). There is no ResizeObserver, and CanvasField is not exposed, so the canvas cannot live in a container that is hidden or collapsed at load. Every window resize (including the mobile URL bar) resets zoom and pan.
- Z-INDEX STACK over the forms: base header sticky z-40 (base.html:79), flash toast fixed bottom z-50 (base.html:168), SW update banner fixed bottom-0 z-50 (base.js:121-122), JS dropdown z-30 (add.js:106), sticky save bar z-20 (add.html:441, edit.html:390), Coloris picker z-index 1000 on body (coloris.css:6). The new sticky full-width save bar must not be covered by the toast or banner, and must respect safe-area-inset-bottom.
- COLORIS: auto-binds `[data-coloris]` (coloris.js:16,1023-1024), wraps the field in div.clr-field with a pointer-events:none button (coloris.css:325-383), and appends #clr-picker with named inputs (clr-color-value, clr-hue-slider, clr-alpha-slider, clr-format) to body. Keep the picker parent as body so these never post. The theme is hard-set to light polaroid (form-canvas.js:145-146); 'auto' follows prefers-color-scheme, not the html.dark class toggle.
- SHARED FILES: Canvas.js and coloris.js/css are also used by lighthouse.html (3-5,247), lighthouse/auton.html (9,274) and scouting/list.html (2-7,91). compare.js and list.js also use an #autoPathContainer. Restyling Canvas colours or Coloris affects those pages too. fuel-estimates.js and list.js in static/js/scout/ belong to the list page, not add/edit. fuel-input.js is add-only.
- TBA/JS DATA FLOW (add): server-rendered events (records.py:35), then background refresh via /api/tba/events?background=1 polled every 2s for up to 60s while X-Scouting-Pending is true (add.js:278-300). Matches come from /api/tba/matches/<key> with the same polling (add.js:1-27). pageshow with persisted=true forces a reload (add.js:262-264). Status text goes into the generated <p role=status> elements.
- CSRF: both forms rely on the hidden csrf_token input. The fetch wrapper in base.html:7-23 adds X-CSRFToken for JS POSTs. A missing token redirects to index with 'session expired' (app.py:120-125) and the scouting data is lost.

### Corrections (verified by second pass)
- **Claim:** edit.html Jinja context: 'There is no id field, so the form must keep posting to its own URL.'
  **Correction:** TeamData does have an id: `self.id = str(data.get('_id'))`. The rebuild could use action="{{ url_for('scouting.edit', id=team_data.id) }}". Posting to its own URL (no action) still works, but it is not forced.
  **Evidence:** app/models.py:58; get_team_data builds TeamData from the Mongo document that includes _id (app/scout/scouting_utils.py:265,282)
- **Claim:** edit hook input#event_code: 'If it is made editable, form-canvas.js would rewrite the value in uppercase, changing record identity and breaking match13 event mapping.'
  **Correction:** Uppercasing would change record identity (update_team_data compares event_code exactly, triggering the duplicate and alliance checks, and other pages group by the exact string). It would not break match13 event mapping: _event() casefolds both the stored display name and the TBA catalog name before matching.
  **Evidence:** app/scout/match13_fuel.py:172-175 (`normalized = ' '.join(event.casefold().split())` compared with casefolded item['name']); app/scout/scouting_utils.py:315-319
- **Claim:** add.html purpose 'a 20-button toolbar' and phone_problems 'That is 20 icon-only buttons wrapping into about 3 rows'
  **Correction:** The role=toolbar holds 19 icon-only buttons: 8 tools, undo/redo (2), view/flip/rotate (5), save/load/readonly (3) and clear (1), plus the hidden #loadFile input. #fillToggle is a separate text button in the stroke-controls row.
  **Evidence:** app/templates/scouting/add.html:100-173 (toolbar), :176-180 (#fillToggle outside the toolbar); edit.html:105-178 identical (diffed)
- **Claim:** tests/test_security.py:22-36: form field csrf_token is accepted and its absence is rejected (applies to both forms' hidden csrf input)
  **Correction:** Those tests only POST to /team/334/leave and /notifications/subscribe. No test sends the csrf_token form field to /scouting/add or /scouting/edit. test_route_logging sends the X-CSRFToken header instead, and test_match13_fuel's RouteTests uses a bare Flask app with no CSRFProtect, so the hidden csrf input in both forms is untested.
  **Evidence:** tests/test_security.py:25,35,39-40; tests/test_route_logging.py:68; tests/test_match13_fuel.py:453-456
- **Claim:** SHARED FILES: 'Canvas.js and coloris.js/css are also used by lighthouse.html (3-5,247), lighthouse/auton.html (9,274) and scouting/list.html (2-7,91)'
  **Correction:** lighthouse/auton.html loads only localforage (9) and Canvas.js (274), not Coloris. A Coloris restyle affects lighthouse.html and scouting/list.html only. scouting.css is loaded by add/edit only.
  **Evidence:** grep: auton.html:9 localforage, :274 Canvas.js, with no coloris reference; lighthouse.html:4-5 and list.html:5,7 load coloris
- **Claim:** SERVICE WORKER STALENESS: 'bump CACHE_NAME/STATIC_CACHE_NAME/DYNAMIC/PAGE (v14) and CACHE_VERSION'
  **Correction:** The names are already v14 and CACHE_VERSION is already '15', so the bump must go to v15 and '16'. activate deletes only caches whose names differ from the current STATIC/DYNAMIC/PAGE names. Bumping CACHE_VERSION alone keeps the stale cache-first tailwind.css, global.css, Canvas.js and form-canvas.js.
  **Evidence:** app/static/js/service-worker.js:1-6, :288, :241-247

### Tests touching markup
- tests/test_browser_resilience.js:94-99 matchLoader: reads app/static/js/scout/add.js and runs `source.slice(0, source.indexOf('const updateMatchResult'))` in a vm with only fetch/Date/timers. loadEventMatches must stay the first top-level code in add.js, must not touch document, and the literal `const updateMatchResult` (dead code at add.js:29-40) must remain after it. Removing it makes indexOf -1 and pulls the DOMContentLoaded code into the vm, which fails.
- tests/test_browser_resilience.js:101-135: loadEventMatches contract (polls while X-Scouting-Pending is true, returns null when not pending, abort rejects with AbortError).
- tests/test_browser_resilience.js:137-175: fuel-input.js must expose global trackFuelInput(form), use form.querySelectorAll() and field.name to skip 'ferried_fuel', use document.getElementById('fuelEstimateHint'), and listen for input/change. Hint text must match /uses automatic Match13/ (zero or blank) and /saved as entered/ (nonzero). Top-level code may only use document.getElementById and document.addEventListener.
- tests/test_browser_resilience.js:48-52: a POST to /scouting/add through the service worker must reject when offline (never served from cache).
- tests/test_match13_fuel.py:450-482: POST /scouting/add with form field names team_number, auto_fuel, ferried_fuel, teleop_shift_4_fuel, _fuel_entered. Blank FUEL_FIELDS must be stored as 0 and nonzero scored fuel must skip enroll. tests/test_match13_fuel.py:125 uses _event_key, event_code as display name, match_number 'Qual 4' and alliance.
- tests/test_route_logging.py:86-89: POST /scouting/add and /scouting/edit/<id> with team_number, event_code, match_number and notes. render_template is patched (test_route_logging.py:54), so templates are not rendered.
- tests/test_security.py:22-36: form field `csrf_token` is accepted and its absence is rejected (applies to both forms' hidden csrf input).
- GAP: no test renders scouting/add.html or scouting/edit.html, and no test checks their ids or classes; template or JS-hook regressions would go undetected. A Jinja render smoke test or a Playwright check (.playwright/cli.config.json was added in commit 93399c8) is recommended before the rebuild.

### app/templates/scouting/add.html

**Purpose:** New match-scouting form. You pick event, match and team from searchable or native selects filled from TBA data, and alliance is derived from the team. It has an auto-path drawing canvas with a 20-button toolbar and a Coloris colour picker, 5 period tabs (Auto/Teleop/Endgame/Defense/Other) of fuel counters, checkboxes, sliders and notes, and a sticky Cancel/Save bar. The form is submitted through JS (updatePathData, then form.submit()).

**Routes:** GET+POST /scouting/add, view records.add (app/scout/routes/records.py:27-72), endpoint scouting.add. GET renders with events=tba.get_current_events(...) and event_matches={} (records.py:33-39). POST: request.form.to_dict() (41); auto_path json.loads, and invalid JSON flashes an error and redirects (43-52, so the record is dropped); zero_scored_fuel (54, match13_fuel.py:33); blank FUEL_FIELDS are set to 0 (55-57); then ScoutingManager.add_scouting_data (scouting_utils.py:149-175 + _record_fields 75-114); then match13 enroll (records.py:59-64, match13_fuel.py:196 using _event_key at :157); then redirect to scouting.home. JS fetches GET /api/tba/events?background=1 (add.js:281, events.py:15-34, reads the X-Scouting-Pending header) and GET /api/tba/matches/<event_key> (add.js:5, events.py:37-49, match keys built in TBA.py:97-115). Back and Cancel go to url_for('scouting.home'). Linked from list.html:49.

**Extends/includes:** extends base.html; blocks head and content; defines macros step() and counter() and Jinja vars tab_class/tool_class/group_class inline (add.html:13-39). No includes.

**JS:** templates/base.html:7-23 inline fetch wrapper (adds X-CSRFToken), :28-33 theme, :201-240 flash auto-dismiss, mobile menu, theme toggle, user menu; static/js/base.js (SW registration, update banner, offline indicators); https://cdn.jsdelivr.net/gh/localforage/localforage/dist/localforage.min.js (unversioned, add.html:2); static/js/coloris.js (add.html:7); static/js/scout/fuel-input.js?v=11 (add.html:448); static/js/Canvas.js (add.html:449); static/js/scout/form-canvas.js (add.html:450); static/js/scout/add.js?v=11 (add.html:451); inline handlers: add.html:14 (counter step onclick), 370, 401 (onchange toggle rating groups), 385, 416 (oninput value echo)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `script#events[type=application/json]` | id | app/static/js/scout/add.js:277 | A <script type="application/json" id="events"> whose textContent is {{ events | tojson | safe }} (dict of event display name to {key,start_date}). The id 'events' must be unique on the page, so the base layout must not reuse it. |
| `script#event_matches[type=application/json]` | id | app/static/js/scout/add.js:238-240 | Must exist and hold valid JSON ({{ event_matches|tojson|safe }}, currently {}). JSON.parse(null.textContent) would throw before the dropdowns are built and kill event loading. The value itself is unused. |
| `form#scoutingForm[method=POST]` | id | add.js:49-83 (submit listener: preventDefault, updatePathData, required check + alert, sets _event_key, form.submit()); fuel-input.js:23-24 (trackFuelInput); records.py:27-72 | A <form id="scoutingForm" method="POST"> with no action, so it posts back to /scouting/add. Every named field below must be a descendant, including those inside hidden tabs. Native constraint validation runs before the submit listener. Keep autocomplete=off. |
| `input[name=csrf_token]` | form-field-name | app/app.py:17,58 CSRFProtect; app.py:120-125 csrf_error; tests/test_security.py:22-36 | Hidden <input name="csrf_token" value="{{ csrf_token() }}"> inside the form. Without it the POST is rejected and redirected to index with 'session expired', and the scouting record is lost. |
| `input[name=_event_key]` | form-field-name | add.js:81 form.elements._event_key; match13_fuel.py:157; tests/test_match13_fuel.py:125 | Hidden input named exactly _event_key inside #scoutingForm. JS fills it from the selected event option's data-key (the TBA key, e.g. 2026nyny) on submit, which lets fuel estimates resolve the event. |
| `select#event_select[name=event_code][required]` | id | add.js:87,243 (createSearchableDropdown 93-113: inserts div.relative before it, moves the select inside, sets style.display=none), 249 (status <p role=status> appended to select.parentElement), 265-276 (populateEvents adds <option value=NAME data-key=KEY>), 303-407 (change loads matches), 81 (selectedIndex .dataset.key); scouting_utils.py:159; match13_fuel.py:157 | Must be a real <select> (uses .options, .selectedIndex, option.dataset.key) with a first <option value=""> placeholder, which renderDropdown skips. Posted value is the event DISPLAY NAME, not the key. JS hides it and replaces it visually with a text input + absolute list, so its wrapper div must be position-able and must not clip overflow. The parent ends up being the JS wrapper, and the status <p> is appended there. |
| `select#match_select[name=match_number][required]` | id | add.js:88,244,252-253,308-407 (innerHTML reset, optgroups 'Qualification'/'Semi-Finals'/'Finals', disabled toggled 308/322/394/403), 410 change listener; scouting_utils.py:160; match13_fuel.py:38-49 match_key parses 'Qual N' / 'Semifinal S-M' / 'Final N' | <select> that supports <optgroup>, with a placeholder option. Option value = TBA-derived key ('Qual 4', 'Semifinal 1-2', 'Final 1' from TBA.py:100-107) and is posted as match_number. Option text differs ('Qual 4', 'Semi-Finals 1-2', 'Finals 1'), and the search filter (add.js:155-200) matches on the text. Hidden by the searchable-dropdown wrapper like event_select. |
| `select#team_select[name=team_number][required]` | id | add.js:89,313,412-449 (innerHTML reset, optgroups 'Red Alliance'/'Blue Alliance', option data-alliance), 452-464 change listener (sets #alliance_color, toggles classes border-red-500/border-blue-500/dark:border-red-500/dark:border-blue-500 on the select itself), 57-65 submit check; scouting_utils.py:153 | Stays a visible native <select> (not wrapped). Option value = digits only. The select element must accept the JS-added alliance border classes, and its default border must come from a lower-precedence layer (currently the .input component) so the border-red/blue-500 utility wins. |
| `input#alliance_color[type=hidden][name=alliance]` | form-field-name | add.js:90,314,413,455,461 and 60-65 (submit alert if empty); scouting_utils.py:161 (default 'red') | Hidden input id=alliance_color name=alliance inside the form. Its value is 'red' or 'blue' and is set only by JS. |
| `#selectTool #penTool #rectangleTool #circleTool #lineTool #arrowTool #hexagonTool #starTool` | id | app/static/js/scout/form-canvas.js:162-191 (click -> CanvasField.setTool), 174-182 and 345-426 (Ctrl shortcuts toggle .active) | All 8 ids must exist (getElementById(...).addEventListener on null throws and aborts the rest of init, including add.js). They must be <button type="button">. JS toggles the .active class exclusively among them, so the styling for .active must exist. #penTool must start with class active because Canvas.js:94 defaults to pen. Do not put the toggled state only in aria attributes, because JS sets only .active. |
| `#undoPath #redoPath #clearPath #savePath #loadPath #goHome #flipHorizontal #flipVertical #rotateCw #rotateCcw #readonlyToggle` | id | form-canvas.js:232-317 (clearPath uses confirm(); savePath creates a temp <a download> on body 255-269; goHome calls resizeCanvas only when resizeOnHome, which add.js:45 sets true; readonlyToggle toggles .active at 316) | All 11 ids must exist as <button type="button">, since a null lookup throws. #readonlyToggle needs the .active style. |
| `input#loadFile[type=file]` | id | form-canvas.js:272-278 (click proxied from #loadPath), 319-342 (FileReader, resets value) | <input type="file" id="loadFile" accept=".json"> kept hidden (class hidden), with no name attribute (otherwise a filename string would be posted). |
| `input#pathColorPicker[data-coloris]` | data-attr | form-canvas.js:144-159 (Coloris() auto-binds [data-coloris] and wraps it, coloris.js:452-482, in div.clr-field + <button>), 194-198 (change -> setColor); Canvas.js:2035-2046 (live updateUIControls fallback: sets value, .closest('.clr-field').style.color, the .clr-field button backgroundColor); app/static/css/scouting.css:3-14 (.clr-field button left:0.625rem, #pathColorPicker padding-left 2.25rem); add.js:498-503 (dead selector input[name=pathColorPicker]) | A text <input> with id=pathColorPicker and the data-coloris attribute, NO name (it must not post). Its parent must tolerate Coloris inserting an inline-block div.clr-field wrapper with an absolutely positioned <button> before the input. Initial value #2563eb (matches form-canvas.js:95). Keep scouting.css or an equivalent for the swatch position and padding. |
| `button#fillToggle` | id | form-canvas.js:211-218 (textContent replaced with 'Fill: On'/'Fill: Off', classList.toggle('active')), 419-422 (Ctrl+F clicks it) | A <button type=button> whose ENTIRE content is replaced by text, so any icon or child markup is wiped on first click. It needs an .active style. Initial text 'Fill: Off'. |
| `input#pathThickness[type=range] + span#pathThicknessValue` | id | form-canvas.js:201-208; Canvas.js:2050-2056 (fallback sync on selection); add.js:508-515 / edit.js:146-153 (dead) | A range input with min=1, max=20, value=3, no name. The span's textContent is overwritten with the number. |
| `div#autoPathContainer > canvas#autoPath` | structure | form-canvas.js:13-14,116-141,229; Canvas.js:170-196 (sizes canvas from container.getBoundingClientRect() * DPR and sets inline style width/height), 1051 (wheel on container, preventDefault), 569 (pointer mapping via canvas rect), 1415-1660 (touch handlers preventDefault single-finger), 1048 (window resize -> resizeCanvas+resetView) | The container must have a definite height (currently aspect-[16/9], sm:h-[420px]), no padding, and overflow hidden. The canvas must be its only sized child. The container must be VISIBLE when the page loads: do not put it inside a hidden tab, collapsed accordion or display:none step, because the canvas is sized once (0x0 if hidden) and CanvasField is not exposed so nothing can re-measure it on reveal. Avoid CSS transform or zoom on ancestors, which would break pointer mapping. |
| `input#autoPathData[type=hidden][name=auto_path]` | form-field-name | form-canvas.js:221-226 (value = JSON.stringify(drawingHistory)); add.js:55 (on submit); records.py:43-52 (json.loads; invalid input flashes an error and the record is not saved) | Hidden input id=autoPathData name=auto_path inside the form, empty initially. |
| `textarea#auto_notes[name=auto_notes], #defense_notes, #defense_response_notes, #notes` | form-field-name | scouting_utils.py:97,98,110,113 | Field names auto_notes, defense_notes, defense_response_notes and notes. The ids are used by <label for>. |
| `p#fuelEstimateHint` | id | app/static/js/scout/fuel-input.js:5-20 (textContent replaced on load and on every fuel input/change); tests/test_browser_resilience.js:137-175 | A text-only element with id fuelEstimateHint (children would be wiped). JS overwrites the template text immediately. |
| `.counter-group > .counter-decrements > button + input[type=number][name$=_fuel] + .counter-increments > button` | structure | inline onclick in step macro add.html:14 (this.closest('.counter-group').querySelector('input'), stepUp/stepDown(n), dispatchEvent(new Event('change'))); app/static/css/global.css:20-95 (row layout, and below 640px stacks via order 1/2/3 with 52px buttons); fuel-input.js:3-4,13-16 (input[name$="_fuel"] minus ferried_fuel, listens input+change) | The number input must be the FIRST <input> inside .counter-group, and buttons must be direct children of .counter-decrements/.counter-increments (global.css uses '> button'). Inputs stay type=number with min=0 (stepDown clamps), value="" with placeholder (blank means estimate-eligible and is coerced to 0 server-side). Any replacement stepper must still dispatch change or input on the input. Buttons stay type=button. Names: auto_fuel, transition_fuel, teleop_shift_1_fuel, teleop_shift_2_fuel, teleop_shift_3_fuel, teleop_shift_4_fuel, ferried_fuel, endgame_fuel (match13_fuel.py:23-29, scouting_utils.py:81-88). Steps -10/-5/-1/+1/+5/+10, except ferried_fuel which has big=false (+/-1 only). |
| `.tab-button[data-tab] / .tab-content[data-tab] (auto, teleop, endgame, defense, other)` | class | add.js:467-491 (document-wide querySelectorAll; button gets .active; contents toggle .hidden and .active by matching dataset.tab) | Both classes plus matching data-tab values. Initial state: the auto button and auto content have .active and the others have .hidden. Buttons are type=button. Toggled contents must not carry responsive display utilities (sm:block, md:flex, etc.), which would override .hidden at breakpoints. No other element on the page, including the new base layout, may use .tab-button or .tab-content. The .active style is currently the [&.active]: arbitrary variants in tab_class (add.html:37). If the rebuild adds role=tab/aria-selected, JS does not maintain them. |
| `input[type=checkbox][name=auto_climb][value=true]` | form-field-name | scouting_utils.py:162 bool(data.get('auto_climb')) | Name auto_climb. Keep value="true". |
| `select#climb_level[name=climb_level]` | form-field-name | scouting_utils.py:91 int() | Option values exactly 0, 1, 2, 3 (None/Level 1-3). |
| `input[type=checkbox][name=climb_success]` | form-field-name | scouting_utils.py:93 bool() | Name climb_success (currently no value attribute, so it posts 'on'; any value works). |
| `input#defense_rating[type=range][name=defense_rating]` | form-field-name | scouting_utils.py:96 int() | Range min=0, max=5, value=0, where 0 means N/A. It must always post an integer. |
| `input#response_to_defense_rating[name=response_to_defense_rating]` | form-field-name | posted but ignored by _record_fields (scouting_utils.py:75-114); displayed in _match_list.html:125; models.py:82 | Dead field server-side. It can be kept as is, but it is not on edit.html. |
| `select#robot_disabled[name=robot_disabled]` | form-field-name | scouting_utils.py:106; templates/scouting/leaderboard.html:251-252; _match_list.html:42,127; static/js/compare.js:134 | Option values exactly 'None', 'Partially', 'Full' (case-sensitive). |
| `input#herd_balls[type=checkbox][name=herd_balls][value=true] -> div#herd_rating_group.hidden -> input#herd_rating[name=herd_rating] + span#herd_rating_val` | form-field-name | inline onchange add.html:370 (toggles #herd_rating_group .hidden); inline oninput add.html:385 (writes #herd_rating_val textContent); scouting_utils.py:71-72,77,101-102 (_is_checked requires value == 'true') | value="true" is MANDATORY: the default 'on' would be stored as False. #herd_rating_group starts with .hidden and has no responsive display classes. herd_rating is a range with min=1, max=10, value=5, and the span shows the value. |
| `input#ferrying_did[value=true] -> div#ferrying_rating_group.hidden -> input#ferrying_rating + span#ferrying_rating_val` | form-field-name | inline onchange add.html:401; inline oninput add.html:416; scouting_utils.py:78,103-104 | Same contract as herd: value="true" is mandatory, the group toggles .hidden, and the range is 1-10 with default 5. |
| `button[type=submit] in sticky action bar` | structure | add.js:51-83 (submit event) | The submit button must be inside the form (or use form=scoutingForm) so the submit event fires and updatePathData and _event_key run. No name is needed (form.submit() drops it anyway). |
| `scripts: head localforage CDN + coloris.css + coloris.js + scouting.css; tail fuel-input.js?v=11, Canvas.js, form-canvas.js, add.js?v=11` | other | Canvas.js:112 (global localforage, throws if missing); form-canvas.js:12,144 (globals Canvas, Coloris); add.js:43 (global initScoutFormCanvas, first statement of the DOMContentLoaded handler) | Load order and globals must stay intact. If the Canvas constructor throws (for example the localforage CDN fails), the whole add.js init dies: no event list, no tabs, and no JS submit (native submit without _event_key or auto_path). |
| `.container (absent)` | class | form-canvas.js:17 showStatus appends toasts to document.querySelector('.container') | No .container exists today, so canvas toasts ('Path saved', 'View reset', ...) are silently dropped. Adding a .container class anywhere (for example Tailwind container on <main>) will suddenly make them render inside that element. Decide deliberately. |
| `.animate-fade-in-up` | class | templates/base.html:70 (keyframes), 208 (removes '.animate-fade-in-up > div' after 5s) | Never put this class on form content: its child divs would be deleted 5s after load. |
| `Jinja context: events, event_matches, csrf_token(), url_for('scouting.home')` | jinja-context | records.py:37-39 | Only these context variables are available. There is no team_data on add. |

#### JS-generated markup
- add.js:93-113 searchable dropdown: div.relative wrapper, input.input search, list div 'absolute z-30 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-zinc-200 bg-white py-1 text-sm shadow-md hidden dark:border-zinc-700 dark:bg-zinc-900'; select hidden via inline style.display='none'
- add.js:131-151 option rows: div 'cursor-pointer px-3 py-2.5 text-zinc-700 hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-800'; list shown/hidden via the .hidden class (145, 206, 211, 217, 232)
- add.js:246-253 two <p class="help" role="status"> status lines appended next to event and match; messages at 290, 293-294, 297, 307, 323, 330, 334, 398
- add.js:265-276 event <option value=name data-key=key>; 311, 313, 337, 399, 412 select innerHTML resets ('Select Match', 'Select Team', 'Error loading matches')
- add.js:356-390 match <optgroup> Qualification/Semi-Finals/Finals and option text 'Qual N' / 'Semi-Finals S-M' / 'Finals N'
- add.js:425-448 team <optgroup> 'Red Alliance'/'Blue Alliance' and options 'Team N' with data-alliance
- add.js:458-463 alliance colour on #team_select: classes border-red-500/border-blue-500 and dark:border-red-500/dark:border-blue-500 (built as `border-${alliance}-500`)
- add.js:470-491 tab state: .active on .tab-button, .hidden/.active on .tab-content
- form-canvas.js:16-94 status toast markup (fixed bottom card, text-green-500 check icon, close button) appended to .container (no-op today)
- form-canvas.js:174-182 .active on tool buttons; 216-217 #fillToggle text and .active; 316 #readonlyToggle .active; 260-265 temporary <a download>
- Canvas.js:195-196 inline canvas style width/height; cursor changes at 796, 1097, 1109, 1121, 1177, 1220, 1310 and others; 2039-2045 inline color/backgroundColor on .clr-field and its button
- coloris.js:466-482 wraps [data-coloris] in div.clr-field + button; 967-1008 builds #clr-picker (inputs named clr-color-value, clr-hue-slider, clr-alpha-slider, clr-format) appended to body; 99 class 'clr-picker clr-polaroid clr-light'
- base.js:118-150 #update-banner (fixed bottom-0 bg-blue-500 z-50) over the form

#### Hard-coded colours
- app/templates/scouting/add.html:177 #pathColorPicker value="#2563eb"
- app/static/js/scout/form-canvas.js:95 initialColor '#2563eb'; :149-158 Coloris swatches #2563eb #000000 #ffffff #db4437 #4285f4 #0f9d58 #ffeb3b #ff7f00; :146 themeMode 'light'; :34 toast icon text-green-500
- app/static/js/Canvas.js:9-12 context alpha:false + :430 fillStyle '#ffffff' (canvas always paints white, even in dark mode); :80 GRID_COLOR #e0e0e0; :81 AXIS_COLOR #a0a0a0; :84 default stroke #000000; :260, :501, :540, :911, :2351 selection #0066ff; :282, :949 inner highlight #ffffff; :2350 resize-handle fill #ffffff
- app/templates/scouting/add.html:190 canvas frame bg-white ring-zinc-200 (white in dark mode too)
- app/static/js/scout/add.js:458-462 alliance border-red-500 / border-blue-500 (+dark:)
- app/static/js/scout/add.js:106,139 dropdown zinc/white palette
- app/templates/scouting/add.html:38 tool active bg-blue-50/text-blue-700 (dark blue-500/15, blue-300); :169 clear hover red-50/red-600 (dark red-500/10, red-400); :178 fill active border-blue-600/bg-blue-50/text-blue-700
- accent-blue-600 on checkboxes and ranges: add.html:183, 241, 279, 300, 329, 369, 384, 400, 415
- app/templates/scouting/add.html:441 sticky bar bg-zinc-50/95, dark:bg-zinc-950/95
- app/static/css/coloris.css:8, 41, 115, 118, 146-150, 187-188, 238-250, 262-263, 380, 394, 416-434, 467, 473 (vendor picker colours, light/dark/polaroid)
- app/static/js/base.js:122 update banner bg-blue-500

#### Legacy CSS
- app/static/css/coloris.css (vendor Coloris, 576 lines, loaded add.html:3-6)
- app/static/css/scouting.css (14 lines: .clr-field button position, #pathColorPicker padding-left; loaded add.html:8-11)
- app/static/css/global.css (via base.html:36: .counter-group layout and mobile stacking 19-95, hidden number spinners 7-17, thin scrollbars)
- app/static/css/tailwind.css built from tailwind.input.css (components .card/.card-header/.card-body/.btn*/.input/.label/.help/.checkbox/.page-*/.section-title)
- templates/base.html:70 inline .animate-fade-in-up keyframes

#### Phone problems at 390px
- add.html:37 tab buttons are min-h-[40px] with text-[13px] in a grid-cols-5 bar (223), giving about 62px-wide, 40px-tall targets with 13px labels (below the 44/48px target).
- add.html:38 tool_class is h-10 on phone; the select-tool group is grid-cols-8 w-full (101), so each icon button is about 38x40px at 390px; the other groups are w-10 h-10 (40x40). That is 20 icon-only buttons wrapping into about 3 rows, all under 44px.
- add.html:178 #fillToggle uses .btn (py-2 text-sm, about 36px tall); add.html:46 Back is .btn-secondary at about 38px; sticky bar .btn-lg (443) is about 44px, under the 48px target.
- add.html:183 thickness slider is h-2 with a native thumb of about 16px; add.html:300, 329, 384, 415 defense, response, herd and ferry sliders are also h-2. The N/A..5 tick labels (302-304, 331-333) are text-xs in justify-between and do not line up with thumb stops.
- add.html:190 canvas container is aspect-[16/9] below sm: at 390px the card-body is about 326px wide, so the drawing area is about 326x183px and the 800x400 field is drawn at roughly 0.37 scale, which is very cramped for drawing paths. Canvas.js:1048 resets zoom and pan on every window resize (mobile URL-bar show/hide).
- add.html:177 + coloris.css:1-15,520-523 the Coloris picker is 200px wide with 22px swatches, always light theme (form-canvas.js:146), and absolutely positioned on body.
- add.html:72,78 required selects are hidden via inline display:none by add.js:113. An empty event or match makes the browser block submit with 'invalid form control is not focusable' and no visible message (the add.js alert at 63 never runs).
- add.js:105-106,139 the custom event/match list is max-h-60, with option rows py-2.5 text-sm (about 40px); it replaces the native mobile picker and can sit under the on-screen keyboard.
- tailwind.input.css:80-82 .input is py-2 (about 42px tall) for selects, text inputs and the colour field.
- Help and hint text is text-xs (12px): add.html:96, 194, 217-220, 302, 331, 389, 420, plus the JS status lines add.js:247/251 (.help).
- global.css:58-95 counters stack into 3 rows below 640px (52px buttons, fine), but each counter is about 180px tall, so the Teleop tab (6 counters, 252-257) needs over 1000px of scrolling. The counter <label class=label> (add.html:19) has no for and does not wrap the input.
- add.html:441 sticky bar uses -mx-4/px-4, tied to <main> px-4 (base.html:164); changing the page gutter without updating it causes horizontal overflow. There is no env(safe-area-inset-bottom) padding. The z-20 bar is covered by the flash toast (base.html:168, fixed bottom-4 z-50) and the SW update banner (base.js:122, fixed bottom-0 z-50).
- add.html:96 the pan/zoom hint is hidden on phone, and add.html:194 the phone hint is text-xs. Canvas touchstart preventDefault (Canvas.js:1420) means a one-finger swipe on the full-width canvas cannot scroll the page.

#### Redesign notes
Keep every id, name and value above verbatim; the server contract is the field-name list and the exact option values. Keep the canvas container visible and fixed-size at load. A bigger phone canvas is fine (for example aspect-[2/1] or a min-h), but it must be a definite size. On phones, the sticky full-width save bar must still sit inside the form, or the button must use form="scoutingForm". Account for safe-area insets and the z-50 toast/update banner. Counters can be restyled (Oxanium numbers), but keep .counter-group/.counter-decrements/.counter-increments, or rewrite global.css and the inline onclick together; the input must stay first and must still fire change. Restyle the JS-built searchable dropdown and status lines in add.js and the toast in form-canvas.js, which hardcode zinc/white/blue Tailwind classes. Classes assembled or toggled at runtime that must survive Tailwind purge: border-red-500, border-blue-500, dark:border-red-500, dark:border-blue-500 (present literally at add.js:458/462; the safelist at tailwind.config.js:8 does NOT cover dark: variants), hidden, active (styled through the [&.active]: variants in the Jinja class strings add.html:37-39, 178). Any new .active styling must live in a scanned file (templates/**/*.html or static/js/**/*.js) or in tailwind.input.css. The alliance red/blue must stay distinct from the new brand blue #0b5fb0. Coloris stays light (themeMode 'light') unless form-canvas.js is changed to follow html.dark ('auto' follows prefers-color-scheme, not the class toggle). The canvas background is painted #ffffff by Canvas.js and cannot follow the theme without JS changes; the field image is drawn on top.

### app/templates/scouting/edit.html

**Purpose:** Edit an existing match-scouting record. Event, match and team are read-only inputs and alliance is a radio pair. The same auto-path canvas and toolbar are prefilled from the saved path. The same 5 tabs are prefilled from team_data. Submitted via edit.js (updatePathData, then form.submit()).

**Routes:** GET+POST /scouting/edit/<id>, view records.edit (app/scout/routes/records.py:126-177), endpoint scouting.edit, linked from _match_list.html:161,167. GET: team_data = scouting_manager.get_team_data (TeamData, models.py:57-106) plus team_data.fuel_estimate from match13 statuses (records.py:170-173). POST: request.form.to_dict() + last_edited_by/at (146-149); a check on 'auto_path_coords', a field that is never posted (152-157); then FuelEstimateService.manual_update (match13_fuel.py:249) wrapping ScoutingManager.update_team_data (scouting_utils.py:288-375, requires team_number/event_code/match_number at 292-294, alliance default 'red' at 354, updated_data at 359-365 = identity + alliance + _record_fields). On failure it flashes 'Unable to update data' and re-renders with the ORIGINAL team_data (edits lost). The form posts to its own URL (no action). Back and Cancel go to scouting.home.

**Extends/includes:** extends base.html; blocks head and content; macros step() and counter(name,label,value,...) and Jinja vars tab_class/tool_class/group_class/readonly_class (edit.html:9-36). No includes. Duplicates most of add.html, so a rebuild could share a macro or partial, but the add/edit differences (value prefill vs placeholder, readonly match fields, radio alliance, no fuelEstimateHint, no response_to_defense_rating, no fuel-input.js) must be kept.

**JS:** templates/base.html inline scripts (CSRF fetch wrapper 7-23, theme 28-33, flash/menus/theme 201-240); static/js/base.js; https://cdn.jsdelivr.net/gh/localforage/localforage/dist/localforage.min.js (edit.html:3, unversioned); static/js/coloris.js (edit.html:5); static/js/Canvas.js (edit.html:397); static/js/scout/form-canvas.js (edit.html:398); static/js/scout/edit.js (edit.html:399); inline handlers edit.html:10 (counter steps), 338, 359 (group toggles), 347, 368 (value echo)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `form#scoutingForm[method=POST]` | id | app/static/js/scout/edit.js:71-99 (submit: preventDefault, updatePathData, form.submit()); records.py:145-168 | <form id="scoutingForm" method="POST"> with no action (posts to /scouting/edit/<id>). All named fields, including those in hidden tabs, must be descendants. fuel-input.js is NOT loaded here. |
| `input[name=csrf_token]` | form-field-name | app/app.py:17,58,120-125 | Hidden csrf_token input inside the form. |
| `input#event_code[name=event_code][readonly].uppercase` | form-field-name | form-canvas.js:4-9 (input[name=event_code] uppercases its value on input); scouting_utils.py:293,315-338 (identity change triggers the duplicate and alliance-size checks) | Must stay readonly with value {{ team_data.event_code }} (the event display name). The uppercase class is visual only. If it is made editable, form-canvas.js would rewrite the value in uppercase, changing record identity and breaking match13 event mapping. |
| `input#match_number[name=match_number][readonly]` | form-field-name | scouting_utils.py:294,315-338; match13_fuel.py:38-49 | Read-only text input with value {{ team_data.match_number }} (e.g. 'Qual 4'). Required by update_team_data. |
| `input#team_number[name=team_number][type=number][readonly]` | form-field-name | scouting_utils.py:292 int(); edit.html:41 subtitle | Read-only, min=1, value {{ team_data.team_number }}. A missing or non-int value fails the update. |
| `fieldset > label.relative > input.peer.sr-only[type=radio][name=alliance] + span (red is disabled, blue is enabled)` | form-field-name | scouting_utils.py:354-357 (alliance default 'red'; the alliance-size check blocks a switch into a full alliance) | Posted result must be preserved. A blue record posts 'blue'. A red record posts nothing, because the red radio is disabled (edit.html:77-78), and the server defaults to 'red'. Blue is NOT disabled (85-86), so a scouter can switch red to blue but not back. Styling uses peer-checked: on the sibling span, so the input must stay the preceding sibling of the styled span. Checked state comes from team_data.alliance. |
| `Toolbar ids: #selectTool #penTool #rectangleTool #circleTool #lineTool #arrowTool #hexagonTool #starTool #undoPath #redoPath #goHome #flipHorizontal #flipVertical #rotateCw #rotateCcw #savePath #loadPath #readonlyToggle #loadFile #clearPath #fillToggle #pathColorPicker[data-coloris] #pathThickness #pathThicknessValue` | id | form-canvas.js:162-342 (same as add); Canvas.js:2029-2060 (live fallback updateUIControls); scouting.css:3-14; edit.js:126-155 (dead updateUIControls: Canvas.js:33 reads options.updateUIControls but form-canvas.js:15 passes externalUpdateUIControls) | Identical contract to add.html. All must exist; buttons are type=button; .active styles are needed; #penTool starts .active; #fillToggle is text-only; #pathColorPicker has no name and starts at #2563eb; #loadFile has no name. goHome here does NOT call resizeCanvas (resizeOnHome is false by default). |
| `div#autoPathContainer > canvas#autoPath` | structure | form-canvas.js:13-14,116-141,229; Canvas.js:170-196,569,1048,1051,1415-1660 | A definite-size, visible-at-load container with no padding, as on add. The existing path is drawn in onCanvasReady right after construction (edit.js:6-67), so a 0x0 canvas at load also breaks the prefilled path. |
| `input#autoPathData[type=hidden][name=auto_path] value="{{ team_data.auto_path }}"` | jinja-context | edit.js:7-66 (reads value, decodes &quot;/&#34;/&#39;/&amp;, strips wrapping quotes, replaces ' with ", converts ': True/False' to true/false, JSON.parse, must be an Array, sets CanvasField.drawingHistory, calls showStatus); form-canvas.js:221-226 (rewritten on submit); records.py:146 stores it as a raw string on edit | Keep id, name and the value expression as is (autoescaped Python repr of a list, or a JSON string for previously edited records). Switching to |tojson still parses, but changes which strings survive the quote replacement, so test with saved data first. |
| `Counter macro (edit.html:9-32) .counter-group structure with value="{{ value }}"` | structure | inline onclick edit.html:10; global.css:20-95; scouting_utils.py:81-88 int(data.get(...)) with no blank coercion on edit | Same DOM contract as add. Inputs are prefilled: auto_fuel, transition_fuel (or 0), teleop_shift_1..4_fuel, ferried_fuel (or 0), endgame_fuel. A blank or 'None' value posts '' and int('') makes update_team_data return False ('Unable to update data', edits lost), so keep the prefilled values and do not add value="" or placeholder-only semantics. |
| `.tab-button[data-tab] / .tab-content[data-tab]` | class | edit.js:103-121 (document-wide; .active on buttons; adds .hidden to every content, then removes it from document.querySelector(`.tab-content[data-tab="${tabName}"]`); throws if missing) | Every tab button needs a matching .tab-content with the same data-tab. Initial state: auto is active and visible, the others are .hidden. No responsive display utilities on the contents. edit.js does not toggle .active on contents. Classes must not be reused elsewhere on the page. |
| `input[type=checkbox][name=auto_climb][value=true] {% if team_data.auto_climb %}checked` | form-field-name | update_team_data (scouting_utils.py:359-365) does NOT include auto_climb | Keep it, but note that changes are not saved on edit (existing server bug). |
| `select#climb_level option selected by team_data.climb_level == 0..3` | jinja-context | scouting_utils.py:91 | Values 0-3, selected by integer comparison. |
| `input[name=climb_success] checked from team_data.climb_success` | form-field-name | scouting_utils.py:93 | Name climb_success. The unchecked state must post nothing (stored as False). |
| `input#defense_rating[type=range] value="{{ team_data.defense_rating }}"` | form-field-name | scouting_utils.py:96 | Range 0-5. There is no response_to_defense_rating on edit. |
| `textarea #auto_notes #defense_notes #defense_response_notes #notes (content = team_data.*)` | form-field-name | scouting_utils.py:97-98,110,113 | Names unchanged. The prefilled content goes between the textarea tags with autoescaping. |
| `select#robot_disabled options None/Partially/Full selected from team_data.robot_disabled` | form-field-name | scouting_utils.py:106; leaderboard.html:251-252; _match_list.html:42,127; compare.js:134 | Exact values. |
| `#herd_balls[value=true] (checked from team_data.herd_balls) -> #herd_rating_group (hidden unless herd_balls) -> #herd_rating (value team_data.herd_rating or 5) + #herd_rating_val` | form-field-name | inline onchange edit.html:338, inline oninput edit.html:347; scouting_utils.py:71-72,77,101-102 | value="true" is mandatory. The group's initial .hidden comes from Jinja and is toggled by the inline handler. The range is 1-10. |
| `#ferrying_did[value=true] -> #ferrying_rating_group -> #ferrying_rating + #ferrying_rating_val` | form-field-name | inline edit.html:359, 368; scouting_utils.py:78,103-104 | Same as herd. |
| `Scoring hint <p> (edit.html:216-220) shown only if team_data.fuel_estimate` | jinja-context | records.py:170-172 (service.statuses([id]).get(id), dict with label) | Server-rendered only. It has no id, and fuel-input.js is not loaded on edit, so do not add id=fuelEstimateHint plus fuel-input.js without intending the add-page wording. |
| `Jinja context team_data.*` | jinja-context | records.py:157,173; models.py:57-106 | Attributes used: team_number, event_code, match_number, alliance, auto_path, auto_notes, fuel_estimate.label, auto_fuel, auto_climb, transition_fuel, teleop_shift_1_fuel..teleop_shift_4_fuel, ferried_fuel, endgame_fuel, climb_level, climb_success, defense_rating, defense_notes, defense_response_notes, robot_disabled, herd_balls, herd_rating, ferrying_did, ferrying_rating, notes. There is no id field, so the form must keep posting to its own URL. |
| `scripts: head localforage CDN + coloris.css + coloris.js + scouting.css; tail Canvas.js, form-canvas.js, edit.js (no ?v)` | other | Canvas.js:112; form-canvas.js:12,144; edit.js:3 | Same globals and order as add. edit.js is not in the SW STATIC_ASSETS list, but Canvas.js and form-canvas.js are cache-first there. |
| `.container (absent) / .animate-fade-in-up` | class | form-canvas.js:17; base.html:208 | Same caveats as add. edit.js relies on showStatus for 'Existing path loaded' and error messages, which are currently invisible. |

#### JS-generated markup
- edit.js:42-64 sets CanvasField.drawingHistory and calls showStatus('Existing path loaded' / 'Invalid path data format' / 'Error loading existing path'); the toast is dropped because there is no .container
- edit.js:106-121 tab state (.active on buttons, .hidden on contents)
- form-canvas.js:16-94 toast markup; 174-182, 216-217, 316 .active and text toggles; 260-265 temporary <a download>
- Canvas.js:195-196 inline canvas size and cursor styles; 2039-2045 .clr-field inline colours
- coloris.js:466-482 .clr-field wrapper; 967-1008 #clr-picker appended to body
- base.js:118-150 update banner

#### Hard-coded colours
- app/templates/scouting/edit.html:182 #pathColorPicker value="#2563eb"
- app/templates/scouting/edit.html:79-80 red alliance pill peer-checked:border-red-500, text-red-700, dark:text-red-400, dot bg-red-500; :87-88 blue pill border-blue-500, text-blue-700, dark:text-blue-400, dot bg-blue-500
- app/templates/scouting/edit.html:36 readonly_class bg-zinc-50/text-zinc-600 (dark bg-zinc-800/50)
- app/templates/scouting/edit.html:195 canvas frame bg-white ring-zinc-200
- app/templates/scouting/edit.html:34 tool active blue-50/blue-700; :174 clear hover red; :183 fill active blue
- accent-blue-600: edit.html:188, 237, 274, 293, 336, 346, 357, 367
- app/static/js/scout/form-canvas.js:95, 146, 149-158, 34 (as on add)
- app/static/js/Canvas.js:80, 81, 84, 260, 282, 430, 501, 540, 911, 949, 2350, 2351 (as on add)
- app/static/css/coloris.css vendor colours (as on add)
- app/templates/scouting/edit.html:390 sticky bar bg-zinc-50/95, dark:bg-zinc-950/95

#### Legacy CSS
- app/static/css/coloris.css (edit.html:4)
- app/static/css/scouting.css (edit.html:6)
- app/static/css/global.css (via base: .counter-group, number spinners)
- app/static/css/tailwind.css (components)
- templates/base.html:70 inline .animate-fade-in-up

#### Phone problems at 390px
- edit.html:79,87 alliance pills are h-[38px] text-sm (under 44px). The red radio is disabled, so tapping it does nothing.
- edit.html:33 tab bar is min-h-[40px] with text-[13px] in grid-cols-5 (223).
- edit.html:34,106 toolbar: 8-col grid of about 38x40px icon buttons plus 12 more 40x40 buttons wrapping into about 3 rows.
- edit.html:183 Fill button about 36px; 188 thickness range h-2; 182 colour field w-32 with the 22px Coloris swatches.
- edit.html:195 canvas aspect-[16/9] gives about 326x183px on a 390px phone, which is cramped for redrawing a path.
- edit.html:287-296, 344-349, 365-370 sliders are h-2 with text-xs tick labels that do not align with the thumb stops.
- edit.html:57 Match card is fine on phone (1 column), but the 4 read-only inputs are about 42px tall and look editable apart from the bg tint.
- edit.html:390 sticky save bar: same -mx-4 gutter coupling, no safe-area inset, and covered by the z-50 flash toast or SW update banner. btn-lg is about 44px.
- global.css:58-95 counters stack to about 180px each, so the Teleop tab is over 1000px tall.
- Text-xs help text at edit.html:101, 199, 217-219, 294, 350, 371.

#### Redesign notes
Keep read-only identity fields readonly (not disabled, since disabled inputs do not post and update_team_data then fails). Preserve the alliance radio posting behaviour exactly, including red being disabled, or change it only together with a server review. Keep the counters prefilled. If the add and edit forms are merged into a shared macro, keep edit's value="{{ value }}" (no placeholder) and add's value="" plus placeholder. Same purge and safelist needs as add: [&.active]: variants in tab_class/tool_class (edit.html:33-34), peer-checked:/dark:peer-checked: variants on the alliance pills (79, 87), and the hidden class emitted by Jinja on herd/ferry groups (341, 362).

### Other missed hooks (verified)
- `app/templates/base.html (consumed by app/templates/scouting/add.html:1-12 and edit.html:2-7)` `{% block head %} (Jinja block name) plus the script order coloris.js before add.js/edit.js` (used by base.html:37 defines `{% block head %}{% endblock %}` after tailwind.css (26) and global.css (36). add.html:1-12 and edit.html:2-7 put the localforage CDN, coloris.css, coloris.js and scouting.css in that block. coloris.js:1267 registers DOMReady(init) when the script runs. form-canvas.js:144 then calls Coloris({...}), which goes coloris.js:1245-1251 -> configure -> :93-99 `picker.className = ...`.): The rebuilt base.html must still define a block named exactly `head` inside <head>. If it renames or drops the block, Jinja silently ignores the child block: no error and no failing test. localforage and Coloris would then never load, Canvas.js:112 throws, and add.js/edit.js init dies. coloris.js must also run before add.js/edit.js. If it is moved after them at the end of body, add.js's DOMContentLoaded handler runs first, configure() runs before init() has created `picker`, it throws at coloris.js:99, and initScoutFormCanvas aborts (no tabs, no event list, no JS submit).
- `app/templates/scouting/add.html:177, app/templates/scouting/edit.html:182` `#pathColorPicker parent element (must NOT already be .clr-field) / div.clr-field > button + input` (used by coloris.js:466-482 wrapColorField skips wrapping when field.parentNode already has class clr-field, so no swatch <button> is created. coloris.js:489-495 updateColorPreview only recolours when event.target.parentNode is .clr-field. coloris.js:1136-1143 `.clr-field button` click calls event.target.nextElementSibling.dispatchEvent(click). Canvas.js:2039-2044 uses closest('.clr-field').querySelector('button').): Do not hand-author a `.clr-field` wrapper (or any element with class clr-field) around the colour input in the new markup. Coloris must insert it, and the input must stay its direct child, right after the generated button. A pre-made .clr-field leaves no swatch button: the colour preview never shows and the Canvas fallback finds no button. Any wrapper Coloris has not created must sit outside the inserted .clr-field.
- `app/templates/scouting/add.html:70-81` `#event_select / #match_select must not be descendants of a <label>` (used by add.js:109-112 inserts div.relative (search input, option list, select) into the select's current parent. add.js:142-148 option-div click adds .hidden to the list. add.js:203-207 search-input focus removes .hidden.): Keep the labels as siblings that use for= (as today), not as wrappers. If the select sits inside a <label> without for=, the generated search input becomes that label's first labelable descendant. Tapping an option div inside the label then activates the label, which refocuses the search input, and the focus handler reopens the list right after a choice. Also keep every ancestor of the wrapper free of overflow:hidden/auto (for example .card overflow-hidden for rounded corners), or the absolute z-30 list is clipped.
- `app/templates/base.html:6` `<meta name="csrf-token" content="..."> (attribute order name then content, double quotes)` (used by base.html:10 querySelector('meta[name="csrf-token"]').content (the fetch wrapper). tests/app_harness.py:45-46 renders /auth/settings and regexes `name="csrf-token" content="([^"]+)"`. logged_in_client is used by tests/test_route_logging.py:26 (which POSTs /scouting/add and /scouting/edit/<id> at :86-89), test_security.py:20 and test_bug_fixes.py:25,31,54.): Keep the meta tag with name before content, in double quotes. Otherwise re.search returns None, .group(1) raises, and the only tests that exercise the add/edit POST routes through the real app all error.

### Other missed items (verified)
- CSS precedence trap: global.css loads after tailwind.css (base.html:26 then :36) with equal specificity. `.counter-group{display:flex}` (global.css:20-25) and `.counter-group .counter-decrements/.counter-increments{display:flex}` (27-31) therefore beat Tailwind `hidden`/`grid`/`block` on those elements. The counter input has `width:auto !important` (52) and `width:100% !important` on phones (74), and the step buttons have `margin-left/right:0 !important` (36-37), so Tailwind w-*/mx-* utilities on them are silently ignored. Similarly, scouting.css:12-14 `#pathColorPicker{padding-left:2.25rem}` (ID specificity) overrides any pl-*/px-* utility on the colour input.
- Adding a `.container` makes canvas toasts very noisy, not just visible: Canvas.js:131 runs autoSave every 30 s, and :1885 calls showStatus('Auto-saved') each time. 'Undo successful' (731), 'Redo successful' (784), 'Selection copied' and others also toast. The toast (form-canvas.js:22-58) uses the class animate-fade-in-up, whose keyframes exist only in base.html:65-71, and its close button is created without type="button" (form-canvas.js:55-58).
- Phone: Coloris focusInput defaults to true (coloris.js:29), and form-canvas.js:144-159 does not override it. openPicker (coloris.js:353-356) focuses #clr-color-value, so every open raises the soft keyboard over the 200px picker. #pathColorPicker is itself type=text (add.html:177, edit.html:182), so tapping it also focuses a text field.
- Phone: implicit submission. Both forms have a submit button inside them (add.html:443, edit.html:392). Pressing Enter/Go in a fuel counter number input (add.html:28, edit.html:24), in #pathColorPicker, or in the JS-generated search inputs (add.js:98-101) fires the submit event, and add.js:51-83 / edit.js:73-99 then call form.submit(). The record is saved before the other tabs are filled in. On add with an empty event or match, it instead fails silently on the display:none required select.
- Phone/a11y: <label for="event_select"> and <label for="match_select"> (add.html:71,77) point at selects that add.js:113 hides with display:none. The visible search inputs that add.js:98-101 creates have no id, name or aria-label (placeholder only), so tapping the label does nothing and screen readers get no label.
- Phone: inputs must stay at 16px or larger below sm, or iOS Safari zooms on focus. .input is text-base sm:text-sm (tailwind.input.css:81), the JS search inputs reuse .input (add.js:101), and the counter inputs are 1.125rem on phones (global.css:78). A design that uses 13-14px form text breaks this.
- Coloris positions its body-level absolute picker from window.scrollY and document coordinates (coloris.js:374-438, parent 'body' -> container undefined at :82-84). If the new layout uses an app shell where <main> (not the window) scrolls, for example a fixed banner with an overflow-y-auto body, the picker opens offset and stays put while the content scrolls.
- Test touching base.html markup: tests/test_browser_resilience.js:252-275 (npm test) reads app/templates/base.html as text. It slices from the literal '(function () {' after the comment 'Send the CSRF token' to the first '})();', then runs that snippet. Rewording the comment or changing the IIFE shape breaks `npm test`.

## Group: lists-pit-team

### Shared findings
- [hidden] attribute is broken on anything with a component or utility display class. In app/static/css/tailwind.css the preflight rule '[hidden]:where(:not([hidden=until-found])){display:none}' (byte ~4698, base layer) is emitted before '.btn{display:inline-flex}' (~8712, components) and before every display utility, at equal specificity. So #loadMoreMatches (list.html:84) never actually hides today, and any tr.team-row given a display utility for phone cards would not hide when fuel-estimates.js:25 sets row.hidden=true. The rebuild should add '[hidden]{display:none !important}' in @layer base (or equivalent) and test both cases.
- The 'hidden' CLASS is the toggle mechanism for every modal and panel in this group (#autoPathModal, live-status #loadingIndicator/#noDataMessage/#resultsContainer/#eventInfoBanner/#upcomingMatchesContainer/#previousMatchesContainer/#teamRanking, manage #createAssignmentModal/#editAssignmentModal/#assignmentReminderModal, .description-preview/.description-full). .hidden beats non-responsive display utilities only by emit order (.hidden at ~23264 after .flex/.grid/.block/.inline-flex), and LOSES to responsive ones (sm:flex, md:grid). Never put responsive display classes on these elements.
- Inline style display toggles: matches.html:135 sets 'block' (would override a flex/grid card), while pit-scouting/list.js:153 and team/manage.js:29,46 set ''/'none' (safe).
- Table-structure dependencies forbid naive table-to-div card rebuilds: scout/list.js row.cells[2..16] + innerText for CSV and 'tbody' append (list.js:40,160-170); pit-scouting/list.js 'tbody tr' and td:nth-child(1..7) (22-85,142-148); team/manage.js row.children[0..2], td:nth-child(1..4), closest('tr'), tr[data-assignment-id], getElementsByTagName('td') (25-27,42-44,155-157,330,346-350); team-stats.js closest('tbody') (33). Do 'cards on phones' with CSS on the existing table elements (a media query turning tr/td into block/grid, labels via td::before{content:attr(data-label)}, which innerText and textContent ignore), or rewrite the JS to data attributes in the same change.
- textContent overwrites: fuel-estimates.js:30,36-37 replaces content of .fuel-estimate-status and [data-fuel-fields]. team-stats.js:30-31 replaces .epa-value/.opr-value/.dpr-value/.ccwm-value (label text 'EPA: ' lives inside the value). manage.js:185-186 replaces .status-badge text AND className. Don't nest icons, labels or number-font spans inside these. Put the Oxanium number font class on the element itself (status-badge classes get wiped, so style it via .badge component CSS).
- CSRF: every POST form needs hidden input name=csrf_token (CSRFProtect app/app.py:17,58). JS writes rely on base.html:6 <meta name="csrf-token"> and the inline fetch wrapper base.html:7-23, which adds X-CSRFToken to same-origin non-GET fetches (team/manage.js, team-stats.js, fuel-estimates.js). /team/assignments/<id>/status is CSRF-exempt (app/app.py:94). The base.html rebuild must keep that snippet verbatim in shape: tests/test_browser_resilience.js:252-275 slices it out by the markers 'Send the CSRF token', '(function () {' and '})();', and tests/app_harness.py:45-46 regex-scrapes name="csrf-token" content="...".
- Inline event handlers call globals, so these scripts must remain classic (non-module) scripts exposing: showAutoPath, closeAutoPathModal (scout/list.js); toggleDescription (manage.html inline); confirmDeleteTeam, confirmLeaveTeam, updateAdminStatus, clearAllAssignments, openEditAssignmentModal, deleteAssignment, updateAssignmentStatus (team/manage.js); handleLogoChange (settings.html inline); notificationManager (notifications.js, used by manage.js:80). If the rebuild switches to addEventListener with data attributes, change the template and JS together.
- Script placement and order: list.html needs localforage (head; Canvas.js:112) -> team-stats.js -> Canvas.js -> scout/list.js -> scout/fuel-estimates.js. manage.html needs notifications.js before team/manage.js. pit-scouting/add.js, create.html and settings.html inline scripts run at parse time and must come after their forms. settings.html needs compressorjs in {% block head %}, and list.html and live-match-status.html also use {% block head %}, so the rebuilt base.html must keep a head block after the stylesheets.
- Service worker precache (app/static/js/service-worker.js:11-31) lists /static/css/tailwind.css, global.css, index.css, js/Canvas.js, js/team-stats.js, js/scout/list.js, js/scout/fuel-estimates.js, js/notifications.js, js/base.js and images/field-2026.png. Install uses cache.addAll (atomic, :85,104), so renaming or deleting any of these breaks SW install. Bump CACHE_NAME/CACHE_VERSION (:1-6) when restyling. New fonts ('Richardson Brand Accelerator.otf' has spaces, so URL-encode or quote it in @font-face; oxanium-vrb.ttf) skip the SW timestamp (:98) if added to STATIC_ASSETS. app/static/fonts exists but nothing references the fonts yet.
- Tailwind: content globs are only ./app/templates/**/*.html and ./app/static/js/**/*.js (tailwind.config.js:6). Every dynamic class in this group is currently a complete literal (Jinja ternaries in _match_list.html:42,68,127, matches.html:45,87, manage.html:271,308-315, pit chip {% set %} strings, JS literals in live-match-status.html:266-323 and manage.js:170-172,472), so no new safelist is needed. The existing safelist /^(bg|text|border)-(red|blue)-(100|500|800)$/ (tailwind.config.js:7) claims live-status assembles alliance classes, but nothing does today (allianceColor at live-match-status.html:313 is unused). Keep or drop it. Add a safelist if the rebuild builds names like `badge-${alliance}` or 'bg-{{ side }}-...'. Class strings moved into Python (forms.py render_kw) would NOT be scanned. gray maps to zinc, but literal class NAMES are selected by JS (pit list.js:41 '.text-sm.text-gray-500', :28 '.text-lg', :34 '.rounded-full').
- Current component sizes (tailwind.input.css:51-82) versus the 48px tap target: .btn about 38px (py-2 + 20px line + border), .btn-sm about 30px, .btn-icon about 36px, .btn-lg 44px, .input about 42px, the status select (py-1.5) about 38px. Only the pit chips (min-h-[44px]) come close. Labels and help text throughout are text-xs (12px). All tables force whitespace-nowrap via '.table :where(tbody td)' (tailwind.input.css:120-122); manage/pit override it with (!)whitespace-normal.
- Page gutter coupling: base.html:164 main uses px-4. The horizontal nav scrollers in list.html:56, matches.html:17 and pit-scouting.html:21 use '-mx-4 px-4 sm:mx-0 sm:px-0' to bleed edge to edge. Change them together with the new 16px gutter.
- Hardcoded alliance colors to tokenize: live-match-status.html:10 #ef4444 / :14 #3b82f6 (inline <style> stripes), badge-red/badge-blue (_match_list.html:68, matches.html:45, live-match-status.html:323), bg-red-50/60 vs bg-blue-50/60 tints (matches.html:87). Canvas.js colors (#e0e0e0, #a0a0a0, #000000, #0066ff, #ffffff fill at :430,2350) keep the auto-path canvas white in dark mode.
- Legacy CSS in use by this group: app/static/css/global.css on every page via base.html:36 (number-spinner hiding :7-17 affects all number inputs here; .counter-group unused by these pages), app/static/css/coloris.css on list.html only (no consumer there), and the inline <style> in live-match-status.html:3-16. scouting.css, auton.css, index.css and register.css are not used by these templates.
- Pre-existing bugs the rebuild should fix or at least not mask: (1) Load more button never hides (see the [hidden] note). (2) Pit CSV headers and columns don't match (pit-scouting/list.js:2-17 vs the current columns; scouter always blank; exports rows hidden by search). (3) #shooter_other_box is referenced but missing on pit add/edit (TypeError on tap). (4) pit add.js doesn't apply the initial disabled state and the edit page doesn't load it. (5) Description limits: create (maxlength 100, server 500) and settings (maxlength 500 but JS truncates to 100). (6) live-match-status renders value='None' without ?team= and the no-JS submit uses the wrong param name. (7) list.html's stray </div> after {% endblock %} leaves the content <div> unclosed. (8) manage edit modal converts the due date with toISOString (UTC shift) and parses '%Y-%m-%d %I:%M %p' with new Date (unreliable outside Chrome). (9) #memberSearchInput option cloning drops selections. (10) Pit list shows Edit to non-owners, whom pit.py:109 rejects. (11) Reminder Save is wired only after a successful push init. (12) manage.html status <form> action points at a PUT-only route (never submitted).
- Partial/JSON contract for match list pagination and search: GET /scouting?partial=1&page&search&filter returns {html,total,has_more,next_page} (records.py:94-96) or 503 {error} (records.py:102-103). The html must contain #teamDataContainer > .event-section[data-event-code] > ... tbody > tr.team-row. scout/list.js:34-47 depends on exactly that, and anything else inside the partial is discarded on AJAX loads (an empty state inside the container would vanish after a search).
- No markup-level browser tests (Playwright config only at .playwright/cli.config.json, no specs). The only JS tests are tests/test_browser_resilience.js (node --test via package.json 'test'). Python tests mostly patch render_template, except tests/test_bug_fixes.py:23-28, which renders matches.html and base.html for real.

### Corrections (verified by second pass)
- **Claim:** pit-scouting.html: 'Scouter identity is shown only when scouter_team == current_user.teamNumber.'
  **Correction:** The scouter's name is shown in both branches. Only the avatar, profile link and 'Team N' line depend on that check. The else branch prints {{ data.scouter_name or "Anonymous Scout" }}. That differs from _match_list.html, which prints a literal 'Anonymous' in its else branch. Don't 'unify' the two pages without deciding which behaviour is intended.
  **Evidence:** app/templates/scouting/pit-scouting.html:121 (same-team check), :137-143 (else branch prints scouter_name at :142); compare app/templates/scouting/_match_list.html:149-155
- **Claim:** team/settings.html route reads "request.form['description'] (stripped)".
  **Correction:** It reads request.form.get('description', '').strip() and always writes it into updates. If the description field is missing from the submitted form (for example a rebuilt logo-only form, or a save bar outside the form without form=), the save succeeds and silently erases the team description to ''. Nothing errors.
  **Evidence:** app/team/routes.py:555-559
- **Claim:** tests/test_bug_fixes.py:23-28 renders matches.html through create_app, 'so the template must render with an empty list'.
  **Correction:** The test never checks the response. It only asserts that stop_notification_service was not called. A template error in matches.html is caught by app.errorhandler(Exception), which returns 500.html, and the test still passes. test_route_logging patches render_template. So no test protects matches.html rendering.
  **Evidence:** tests/test_bug_fixes.py:23-28 (only stop.assert_not_called()); app/app.py handle_exception returns render_template('500.html'), 500; tests/test_route_logging.py setUp patches app.scout.routes.records.render_template
- **Claim:** tests/test_browser_resilience.js:178-250 'Locks in the _match_list.html contract: rows found via [data-fuel-estimate-id] ..., row.querySelector('.fuel-estimate-status') ..., row.querySelectorAll('[data-fuel-fields]')'.
  **Correction:** The fake DOM ignores selectors. document.querySelectorAll returns [row] for any selector, row.querySelector returns the status object for any selector, and row.querySelectorAll returns the cells for any selector. Selector or markup changes in _match_list.html or fuel-estimates.js are NOT caught. Only these are pinned: the dataset keys (fuelEstimateId, fuelFields, fuelSource), the textContent writes, status.remove() and row.hidden.
  **Evidence:** tests/test_browser_resilience.js:181-185
- **Claim:** Safelist /^(bg|text|border)-(red|blue)-(100|500|800)$/: 'nothing does today [assemble alliance classes] ... Keep or drop it.'
  **Correction:** app/static/js/scout/add.js:459 builds `border-${alliance}-500` and `dark:border-${alliance}-500` at runtime. Those classes stay in the build today only because add.js:458/462 also spell all four out as literals in classList.remove(...), and the safelist (no variants) covers the plain border ones. Dropping the safelist is safe only while those literals stay. The bg-*-100 / text-*-800 entries have no dynamic user.
  **Evidence:** app/static/js/scout/add.js:458-462; tailwind.config.js:8; built CSS contains .border-red-500 and .dark\:border-red-500:is(.dark *)
- **Claim:** settings.html: 'compressorjs 1.2.1 must load before a file is chosen (the head block in base must remain).'
  **Correction:** It is an optional dependency. If Compressor is missing, the ReferenceError is caught inside handleLogoChange, the preview still shows, and the original (uncompressed) file is submitted. Dropping it doesn't break the upload. It only removes client-side resizing and JPEG re-encoding.
  **Evidence:** app/templates/team/settings.html:104-110 (preview before compression), :113-134 (new Compressor inside try/catch)

### Tests touching markup
- tests/test_browser_resilience.js:178-250: drives app/static/js/scout/fuel-estimates.js against a fake row. Locks in the _match_list.html contract: rows found via [data-fuel-estimate-id] with dataset.fuelEstimateId, row.querySelector('.fuel-estimate-status') with textContent/remove(), row.querySelectorAll('[data-fuel-fields]') with dataset.fuelFields 'auto_fuel'/'ferried_fuel' and textContent ('8', '35', '…'), row.dataset.fuelSource 'Match13 estimate'/'Scouted', and row.hidden=true for deleted records.
- tests/test_browser_resilience.js:252-275: extracts the CSRF fetch wrapper from app/templates/base.html source by the markers 'Send the CSRF token', '(function () {' and '})();', then asserts X-CSRFToken is added to same-origin writes such as '/team/1/leave' and '/team/assignments/1/edit' (used by team/manage.js and the scouting list scripts). The base.html rebuild must keep that inline IIFE and comment.
- tests/app_harness.py:45-46: logged_in_client() regex-scrapes name="csrf-token" content="([^"]+)" from the rendered /auth/settings page (base.html:6 meta). Used by test_bug_fixes, test_security and test_route_logging.
- tests/test_scouting_pagination.py:52-67: GET /scouting?partial=1&page=N must return JSON with has_more/next_page (page size 20) and 503 on failure. render_template is mocked to '<div id="teamDataContainer"></div>', mirroring the root id scout/list.js:34 requires in the _match_list.html partial.
- tests/test_pit_form.py:29-51: pit add/edit field names team_number, driver_years, fuel_count_bps, has_auto ('true'), auto_routes, auto_notes. Blank numbers become 0. Auto details are ignored unless has_auto=='true'. A missing team_number on edit is handled (render_template mocked, so this tests form-field names, not markup).
- tests/test_route_logging.py:74-101: GET /scouting/pit and /scouting/matches (records/pit render_template patched) and POST /scouting/pit/add and /scouting/pit/edit/<id> with form fields team_number and notes. Responses must be < 500 and logs must not include form contents.
- tests/test_bug_fixes.py:23-28: GET /scouting/matches through create_app with real templates (matches.html + base.html, matches=[] from mocked Mongo), so the template must render with an empty list for a logged-in user. :30-42 POST /team/334/assignments with the JSON shape team/manage.js sends.
- tests/test_security.py:22-29,31-41,43-48,50-53: POST /team/334/leave without a token gets 302 and with form field csrf_token succeeds (the hidden field name must stay 'csrf_token'). PUT /team/assignments/<id>/status accepts only JSON (manage.js updateAssignmentStatus). GET on /scouting/delete/<id>, /scouting/pit/delete/<id> and /team/334/leave must return 405 (delete actions must stay POST forms).

### app/templates/scouting/list.html

**Purpose:** Match scouting records page: header actions (Export CSV, Add match), scouting tools nav, server-side search (text + filter select), includes the paginated _match_list partial, 'Load more' pager with live status line, and the Auto path canvas modal.

**Routes:** scouting.home GET /scouting and /scouting/list (app/scout/routes/records.py:75-104) renders list.html with team_data, team, total, has_more (error path records.py:104 passes team_data=[], total=0, has_more=False and NO team). AJAX: GET /scouting?partial=1&page=N&search=..&filter=team|match|scouter|notes returns JSON {html: rendered _match_list.html, total, has_more, next_page} (records.py:94-96) or 503 {error} (records.py:102-103); filter map app/scout/scouting_utils.py:227-235. Scripts also hit POST /api/team_epa_opr (app/scout/routes/events.py:151, via team-stats.js) and POST /api/fuel_estimates (records.py:107-123, via fuel-estimates.js). Links: scouting.add, scouting.pit_scouting, scouting.matches, scouting.leaderboard, scouting.scouter_leaderboard, scouting.lighthouse, scouting.auton, scouting.live_match_status, scouting.mock_alliance_selection.

**Extends/includes:** extends base.html; uses {% block head %} (localforage CDN script, coloris.css, coloris.js) and {% block content %}; {% include 'scouting/_match_list.html' %} at list.html:80

**JS:** app/static/js/team-stats.js (v=11); app/static/js/Canvas.js; app/static/js/scout/list.js (v=11); app/static/js/scout/fuel-estimates.js (v=11); app/static/js/coloris.js (head; configured at scout/list.js:251-266 but no color input exists on this page); https://cdn.jsdelivr.net/gh/localforage/localforage/dist/localforage.min.js (head, unpinned, required by Canvas.js:112); app/static/js/base.js and the base.html inline CSRF fetch wrapper (base.html:7-23)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `#autoPathModal` | id | app/static/js/scout/list.js:70,81,128-131,241-247 | Outermost overlay element of the modal. Opened by classList.remove('hidden'), closed by classList.add('hidden') (uses the hidden CLASS). Backdrop close checks e.target === modal, so the overlay itself must be the click target with the dialog card as a child. It currently carries 'flex hidden'; .hidden only wins because it is emitted after .flex in tailwind.css. Never add a responsive display class (sm:flex etc.) to it. |
| `#autoPathContainer` | id | app/static/js/scout/list.js:71,85; app/static/js/Canvas.js:170,187 | Wrapper div passed to Canvas as the container. Canvas sizes itself from container.getBoundingClientRect(), so it needs an explicit non-zero height (currently h-[400px]) and must already be visible when resizeCanvas runs (list.js un-hides the modal first at line 81). Must contain canvas#autoPath. |
| `canvas#autoPath` | id | app/static/js/scout/list.js:73,84 | Must stay a <canvas> element inside #autoPathContainer. Canvas.js draws the field image /static/images/field-2026.png and the path in read-only mode. |
| `#autoNotes` | id | app/static/js/scout/list.js:72,80 | Element whose textContent is set to the auto notes. Any element works, but no child markup survives. |
| `onclick="closeAutoPathModal()"` | other | app/templates/scouting/list.html:18 -> app/static/js/scout/list.js:127 | Close button calls the global function closeAutoPathModal. list.js must stay a classic (non-module) script. |
| `#exportCSV` | id | app/static/js/scout/list.js:236-239 | Button. A click runs exportToCSV, which reads the loaded .team-row rows (see _match_list contract). |
| `#searchInput` | id | app/static/js/scout/list.js:211-220,24 | Text input. 'input' fires a 250 ms debounce, then loadMatches(true). Its value is sent as the 'search' query param. Must exist together with #filterType or no listeners are bound. |
| `#filterType` | id | app/static/js/scout/list.js:210,221,25; app/scout/scouting_utils.py:227-231 | <select> whose option values are exactly team | match | scouter | notes (server field map). Its 'change' event triggers a reload. The value is sent as the 'filter' param. |
| `#matchListStatus` | id | app/static/js/scout/list.js:12,20,46,50 | Live status text node (role=status aria-live=polite). JS replaces its textContent with 'Loading matches…', 'Showing N of T matches', 'No matches found.' or an error message. Initial Jinja text uses team_data|length and total. Must live OUTSIDE #teamDataContainer, which gets replaceChildren() on search. |
| `#loadMoreMatches` | id | app/static/js/scout/list.js:11,19,21,23,43-44,52-53,58,65,217-218,224-229 | <button> with data-url="{{ url_for('scouting.home') }}" and data-next-page="2". JS rewrites dataset.nextPage, writes and deletes dataset.retryReset, toggles the .disabled property, and sets the hidden ATTRIBUTE (button.hidden) plus initial {% if not has_more %}hidden{% endif %}. Current bug: .btn (display:inline-flex, components layer) beats preflight [hidden] (base layer), so the button never actually hides. The rebuild must make [hidden] win (e.g. [hidden]{display:none!important}) or switch to class toggling in list.js. |
| `{% include 'scouting/_match_list.html' %}` | structure | app/static/js/scout/list.js:13 | The partial (and so #teamDataContainer) must render inside the page on first load, and the pager/status must sit outside it. |
| `script order: localforage (head) -> team-stats.js -> Canvas.js -> scout/list.js -> scout/fuel-estimates.js` | structure | app/static/js/Canvas.js:112 (localforage.createInstance); app/static/js/scout/list.js:47 (global loadTeamStats), :83 (global Canvas) | localforage must load before any Canvas is constructed. team-stats.js defines the global loadTeamStats that list.js calls after every AJAX page. Canvas must be global before the first showAutoPath call. All of them are classic scripts and precached by the service worker (service-worker.js:15-21). |
| `Jinja context team_data / total / has_more / team` | jinja-context | app/scout/routes/records.py:97-98,104 | Status text uses team_data|length and total, the pager uses has_more, and the partial uses team (may be undefined on the error path, so keep the 'team and team.is_admin(...)' guard). |
| `#searchInput, #filterType and #matchListStatus are needed by Load more, not just by search` | (missed, verified) | app/static/js/scout/list.js:18-25. listBusy=true and button.disabled=true run at :18-19. status.textContent (:20) and searchInput.value / filterType.value (:24-25) are read with no null check, and the try/finally only starts at :26. | All three must exist whenever #loadMoreMatches exists. If any one is missing, the first Load more click throws before the try/finally, so listBusy stays true and the button stays disabled for good. The inventory only says the search listeners are skipped. |

#### JS-generated markup
- app/static/js/scout/list.js:32-41 parses result.html into a <template>, then moves .event-section nodes into #teamDataContainer or appends .team-row nodes into an existing section's tbody.
- app/static/js/scout/list.js:20,46,50 rewrite #matchListStatus text. :44,53 toggle the hidden attribute on #loadMoreMatches. :81,130 toggle the hidden class on #autoPathModal.
- app/static/js/scout/list.js:83-124 builds the Canvas field drawing (Canvas.js paints its own colors).
- app/static/js/scout/list.js:197-206 creates a temporary <a download> for the CSV.

#### Hard-coded colours
- app/static/js/scout/list.js:257-264 Coloris swatches '#2563eb','#000000','#ffffff','#db4437','#4285f4','#0f9d58','#ffeb3b','#ff7f00' (dead on this page)
- app/static/js/scout/list.js:86 backgroundImage '/static/images/field-2026.png'
- app/static/js/Canvas.js:80 GRID '#e0e0e0', :81 AXIS '#a0a0a0', :84 default stroke '#000000', :260,501,540,911,2351 strokeStyle '#0066ff', :282,949 strokeStyle '#ffffff', :430,2350 fillStyle '#ffffff' (canvas stays white in dark mode)

#### Legacy CSS
- app/static/css/coloris.css (list.html:3-6, head block; no consumer on this page)
- app/static/css/global.css (base.html:36; hides number spinners and defines .counter-group, not used here)

#### Phone problems at 390px
- Header actions Export CSV / Add match are .btn (py-2 + text-sm, about 38px tall), below 44px (list.html:45-52).
- Tools nav (list.html:56-65): 8 .btn-sm pills about 30px tall with 12px text in a horizontal scroll strip. The '-mx-4 px-4' bleed depends on base.html main px-4.
- Search input and filter select are .input, about 42px tall, under the 48px target (list.html:70-77).
- Auto path modal (list.html:11-37): the overlay is 'flex items-center overflow-y-auto'. When the card (header + 400px canvas + notes, about 560px) is taller than the viewport (landscape phones, small iPhones with toolbars), the top is clipped and can't be scrolled to. The close button is .btn-icon (about 36px). The hint text describes Shift+drag and the mouse wheel, which don't apply on touch.
- Load more button is .btn (about 38px).
- Malformed markup: '{% endblock %}' at list.html:94 sits before the closing '</div>' at :95, so that tag is discarded (outside any block) and the <div> opened at :9 is never closed.

#### Redesign notes
Keep every id above. Fix the [hidden] vs .btn conflict globally so #loadMoreMatches hides, and verify that a has_more=False render really hides it. Keep #matchListStatus and #loadMoreMatches outside #teamDataContainer. coloris.css/coloris.js can be dropped here (list.js guards with typeof Coloris). localforage cannot be dropped while Canvas.js is used. If you give the modal role=dialog or aria-modal, keep it as the outer overlay element that receives the backdrop click. Fix the stray </div> after {% endblock %}. If the nav pills become 48px chips, keep them as <a> links to the same endpoints. Service worker precaches Canvas.js, team-stats.js, scout/list.js, scout/fuel-estimates.js and field-2026.png. Renaming any of them breaks SW install (cache.addAll is atomic), so bump the cache names in service-worker.js:1-6.

### app/templates/scouting/_match_list.html

**Purpose:** Partial that groups match records by event code into <section> blocks, each holding one table of records (20 columns: team, live EPA/OPR/DPR/CCWM, alliance, match + fuel-estimate label, fuel phases, ratings, climb, auto path button, defense, disabled badge, notes, scouter, edit/delete). Rendered inside list.html and returned as JSON html for pagination/search.

**Routes:** Included by scouting/list.html; rendered standalone by records.py:95 (render_template('scouting/_match_list.html', team_data=..., team=...)) for ?partial=1. Row forms POST to scouting.delete /scouting/delete/<id> (records.py:180-216); Edit links to scouting.edit /scouting/edit/<id> (records.py:126); links to auth.profile, auth.profile_picture, team.view.

**Extends/includes:** included by scouting/list.html:80; also rendered standalone for the JSON partial

**JS:** app/static/js/scout/list.js; app/static/js/scout/fuel-estimates.js; app/static/js/team-stats.js

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `{% set event_groups %} grouping (lines 1-4)` | jinja-context | app/templates/scouting/_match_list.html:1-8 | Records grouped by data.event_code in first-seen order, one section per event. team_data rows need: team_number, event_code, notes, robot_disabled, scouter_name, match_number, fuel_estimate{label,estimated}, _id, alliance, auto_fuel, auto_climb, transition_fuel, ferried_fuel, herd_rating, ferrying_rating, teleop_shift_1..4_fuel, endgame_fuel, climb_success, climb_level, auto_path, auto_notes, device_type, defense_rating, response_to_defense_rating, scouter_id, scouter_team. Also needs current_user, csrf_token() and team. |
| `#teamDataContainer` | id | app/static/js/scout/list.js:13,34,36,45; tests/test_scouting_pagination.py:58 | Must be the root element of the partial. JS reads ONLY this element from the JSON html, and only its .event-section children are transferred. Any empty state, heading or wrapper placed elsewhere (or inside it but not as an .event-section) is dropped on AJAX loads. On reset the container is emptied with replaceChildren(). |
| `section.event-section[data-event-code]` | class | app/static/js/scout/list.js:37-41,173 | One per event, a direct descendant of #teamDataContainer, with data-event-code=event code. Sections from later pages with the same event code are merged by dataset.eventCode. CSV gets the event code via row.closest('.event-section').dataset.eventCode, so rows must be descendants of their section. |
| `.event-section tbody` | structure | app/static/js/scout/list.js:40 | existing.querySelector('tbody').append(...rows): every section needs a row container that is the FIRST tbody inside it, and new page rows are appended there. A switch to div cards needs a matching change in list.js:40. |
| `tr.team-row (HTMLTableRowElement)` | class | app/static/js/scout/list.js:40,45,156,160-173; app/static/js/scout/fuel-estimates.js:25 | Rows must be real <tr> elements (list.js uses row.cells[i]) with class team-row. fuel-estimates.js sets row.hidden=true for deleted records and CSV filters !row.hidden, so rows must not carry display utilities (flex/grid/block) that would override the [hidden] preflight rule. For phone cards, change display via a CSS media query on tr/td, not utility classes on the row, and keep [hidden] winning. |
| `td column order (cells[0..19])` | structure | app/static/js/scout/list.js:160-170 (comment at _match_list.html:6) | Exact order: 0 Team, 1 EPA/event stats, 2 Alliance, 3 Match, 4 Auto fuel, 5 Auto climb, 6 Transition fuel, 7 Ferried fuel, 8 Herding, 9 Ferrying, 10 Teleop shifts 1-4, 11 Endgame fuel, 12 Climb, 13 Auto path, 14 Defense, 15 Response to defense, 16 Robot disabled, 17 Notes, 18 Scouter, 19 Actions. CSV reads innerText of cells 2,3(fallback),4,5,6,10,11,12,14,16, so their VISIBLE text is exported: 'Red'/'Blue', count, '✓'/'None', 'a/b/c/d' or '…', '✓ L2'/'✗ L2', 'n/5', 'Full'/'Partially'/'None'. Visible labels added inside these cells for phone cards would leak into the CSV. Use td::before{content:attr(data-label)} (pseudo content is not in innerText) or move the CSV to data attributes. |
| `tr[data-team-number][data-match-number][data-notes][data-scouter][data-fuel-source]` | data-attr | app/static/js/scout/list.js:159,161,171,172,190; app/static/js/scout/fuel-estimates.js:28 | data-team-number (CSV team), data-match-number (CSV match), data-notes (CSV notes), data-scouter (CSV scouter), and data-fuel-source with exactly 'Match13 estimate' | 'Awaiting estimate' | 'Scouted' (JS rewrites it). data-event-code and data-robot-disabled on the tr are currently unused. |
| `tr[data-fuel-estimate-id]` | data-attr | app/static/js/scout/fuel-estimates.js:9,15,21,24,32; tests/test_browser_resilience.js:183-217 | Rendered only when data.fuel_estimate, with value data._id. The poller collects [data-fuel-estimate-id] (any element works, but it must be the element that contains .fuel-estimate-status and [data-fuel-fields] and that can be hidden). JS deletes the attribute when the estimate is inactive or the record is gone. |
| `.fuel-estimate-status` | class | app/static/js/scout/fuel-estimates.js:29-33 | Span inside the row (currently in the Match cell). JS replaces its textContent with result.label and calls .remove() when inactive. Keep it text-only. |
| `[data-fuel-fields]` | data-attr | app/static/js/scout/fuel-estimates.js:35-37; tests/test_browser_resilience.js:182,209-226 | Cells with values 'auto_fuel', 'transition_fuel', 'ferried_fuel', 'teleop_shift_1_fuel,teleop_shift_2_fuel,teleop_shift_3_fuel,teleop_shift_4_fuel', 'endgame_fuel'. JS overwrites textContent (values joined with '/', '…' while awaiting, ferried never '…'), so the element must hold ONLY the value: no icons, labels or nested styled spans. Put number-font classes on the element itself. |
| `td.team-stats-cell[data-team-id][data-event-id] > .epa-value .opr-value .dpr-value .ccwm-value` | class | app/static/js/team-stats.js:3-12,25-34 | Cell class team-stats-cell with data-team-id=team_number and data-event-id=event_code. JS writes data-stats-started and data-metric-value. Child elements .epa-value/.opr-value/.dpr-value/.ccwm-value get textContent 'EPA: 12.3' / 'EPA: Loading…' / 'EPA: N/A', which removes the .loading-spinner children. The label text lives inside the value element. team-stats.js reads closest('tbody')?.dataset.metricSort (leaderboard only), so never put data-metric-sort on these tbodies. Shared with app/templates/scouting/leaderboard.html. |
| `onclick='showAutoPath({{ data.auto_path|tojson|safe }}, {{ data.auto_notes|default("")|tojson|safe }})'` | other | app/templates/scouting/_match_list.html:114 -> app/static/js/scout/list.js:69 | The attribute must stay single-quoted because tojson emits double quotes and escapes ' as '. showAutoPath must stay a global function. Button label 'View' plus ' (M)' when device_type=='mobile'. |
| `form[method=POST][action=scouting.delete] > input[name=csrf_token]` | form-field-name | app/scout/routes/records.py:180-216; app/app.py:58 (CSRFProtect); tests/test_security.py:52-53 | POST form with hidden csrf_token and an onsubmit confirm(). Permission branches: own record (Edit + Delete), same team (Edit, plus Delete only if team.is_admin), otherwise 'No access'. Edit is a GET link to scouting.edit(id=data._id). |
| `badge conditionals` | jinja-context | app/templates/scouting/_match_list.html:42,68,127 | Row tint when robot_disabled and != 'None'. Alliance badge 'badge-red' if alliance=='red' else 'badge-blue'. Disabled badge Full -> badge-red, Partially -> badge-amber, else badge-gray. All are full class literals, so Tailwind's scanner sees them. Keep any replacement classes as literals. |
| `Values of td.team-stats-cell[data-team-id][data-event-id] (_match_list.html:57-58)` | (missed, verified) | app/static/js/team-stats.js:8-13,65-72,87-90; app/scout/routes/events.py:165-178; tests/test_scouting_performance.py:251-256 (invalid payloads must return 400) | data-team-id must be a bare integer from 1 to 999999. data-event-id must be a string of at most 200 characters, or absent. Every cell on the page goes in ONE POST, and a single bad value makes the server return 400 for the whole batch, so every EPA/OPR/DPR/CCWM on the page shows 'N/A'. The visible team cell is guarded ({% if data.team_number %} at :53) but the attribute at :57 is not, so a missing team_number renders data-team-id="None". Formatted values like 'Team 334' would break it the same way. |
| `Value of tr[data-fuel-estimate-id] (_match_list.html:50)` | (missed, verified) | app/static/js/scout/fuel-estimates.js:11-18,41-44; app/scout/routes/records.py:112-113 | Must be the bare 24-hex ObjectId string. Ids are sent in batches of up to 100, and one invalid id gets a 400 for the batch. fuel-estimates.js swallows the error, so none of the up-to-100 rows in that batch ever refresh. There is no visible error. |

#### JS-generated markup
- app/static/js/scout/fuel-estimates.js:28-38: rewrites data-fuel-source, .fuel-estimate-status text (or removes it), [data-fuel-fields] textContent, and sets row.hidden=true on deleted records.
- app/static/js/team-stats.js:25-34: replaces .epa-value/.opr-value/.dpr-value/.ccwm-value textContent and sets data-metric-value.
- app/static/js/scout/list.js:37-41: moves server-rendered sections and rows between documents.

#### Hard-coded colours
- _match_list.html:42 row tint bg-amber-50/70 dark:bg-amber-500/5 for disabled robots
- _match_list.html:61-64 spinner border-zinc-300 border-t-transparent
- _match_list.html:68 alliance badge-red / badge-blue
- _match_list.html:73 fuel estimate text-blue-600 dark:text-blue-400
- _match_list.html:82,105 success text-green-600 dark:text-green-400; :84,107,121 text-zinc-400
- _match_list.html:127 badge-red / badge-amber / badge-gray
- _match_list.html:142 hover:text-blue-600; :164,174 delete text-red-600 dark:text-red-400

#### Phone problems at 390px
- 20-column table and every td is whitespace-nowrap (.table :where(tbody td), tailwind.input.css:120-122), so each event table is about 2000px wide and phones only get sideways scrolling inside .table-wrap.
- EPA/event stats cell is a 2x2 grid of 12px (text-xs) values with 10px spinners (lines 60-65).
- Edit/Delete are .btn-sm (about 30px tall). 'No access' is text-xs. Scouter avatar is 24px and the profile/team links are tiny tap targets.
- Notes cell is 'max-w-xs truncate' with the text only in a title tooltip, so it is unreadable on touch (no hover).
- Fuel-estimate label is text-xs. Herding/Ferrying/Defense show as bare 'n/10' 'n/5' text with no labels once the table header scrolls away.
- Row hover highlight is hover-only (no touch equivalent).

#### Redesign notes
Safest phone 'cards' approach: keep <table>/<tbody>/<tr class=team-row>/<td> in the same order and restyle with a max-sm media query (tr/td display:block or grid via CSS on .table, labels via td::before{content:attr(data-label)}). That keeps row.cells, tbody append, innerText CSV and [hidden] working. Don't put Tailwind display utilities on tr.team-row. Keep #teamDataContainer as the partial root. Any empty-state should live outside it (list.js only transfers .event-section) or be driven from #matchListStatus. Keep [data-fuel-fields], .fuel-estimate-status and .epa-value etc. as text-only leaf elements (apply the Oxanium number font to them directly). Keep the single-quoted onclick or replace it with a data-attribute plus a delegated listener (also update list.js). Delete forms need csrf_token. No dynamic Tailwind class assembly here, so no safelist needed unless the rebuild adds some.

### app/templates/scouting/matches.html

**Purpose:** Match view: one card per recorded match with red and blue alliance panels listing scouted teams (climb badges, fuel and ferried totals, estimate label) and alliance phase totals, plus client-side team-number search.

**Routes:** scouting.matches GET /scouting/matches (app/scout/routes/records.py:241-267), context matches = [{event_code, match_number, red_teams/blue_teams:[{number, fuel_estimate{label,estimated}, ferried_fuel, fuel_total, climb_level, climb_success, auto_climb}], red_fuel/blue_fuel:{auto, transition, teleop, endgame, total}}] (matches=[] on error). Links: scouting.live_match_status, scouting.home, scouting.pit_scouting, scouting.leaderboard.

**Extends/includes:** extends base.html (content block only); inline <script> at matches.html:119-139

**JS:** inline <script> matches.html:119-139

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `#teamSearchInput` | id | app/templates/scouting/matches.html:121,128-137 | Text input (inputmode=numeric). Script calls addEventListener on it without a null check, so a missing id throws. |
| `[data-match-card]` | data-attr | app/templates/scouting/matches.html:122,135 | One element per match containing all of that match's [data-team-number] elements. The script sets card.style.display = 'block' or 'none'. If the rebuilt card is flex or grid, the inline 'block' overrides it as soon as the user types. Either keep the card display:block or change line 135 to use '' instead of 'block'. |
| `[data-team-number]` | data-attr | app/templates/scouting/matches.html:124-125,132 | Descendants of the card whose dataset.teamNumber is the bare team number, matched by substring includes(). |
| `{% for match in matches %}...{% else %} empty state` | jinja-context | app/scout/routes/records.py:262,267; tests/test_bug_fixes.py:23-28 | Must render with matches=[] (the test renders the real template through create_app) and with the fields listed in routes. fuel_estimate shows '…' when present and not estimated. |

#### JS-generated markup
- matches.html:135 sets inline style display 'block'/'none' on [data-match-card]

#### Hard-coded colours
- matches.html:45 alliance badge-red / badge-blue
- matches.html:59 badge-blue (Auto climb); :62 badge-green / :64 badge-gray (climb)
- matches.html:67 text-blue-600 dark:text-blue-400 (estimate label)
- matches.html:87 alliance tint 'bg-red-50/60 dark:bg-red-500/5' vs 'bg-blue-50/60 dark:bg-blue-500/5' (complete literals in a Jinja ternary)

#### Phone problems at 390px
- Alliance totals dl is 'grid grid-cols-4' with no breakpoint (matches.html:87): about 75px per column at 390px with 12px labels like 'Transition'.
- Team row puts name, 1-2 badges and a two-value dl (gap-5) in one flex row (lines 54-78). Badges wrap and the 12px dt labels are tiny.
- Nav is .btn-sm (about 30px) and the header 'Live team schedule' button is .btn (about 38px), both under 44px.
- No pagination: every recorded match renders at once, so the page gets very long on a phone at an event.
- Search input .input is about 42px tall.

#### Redesign notes
Keep data-match-card on the element that is shown or hidden, and data-team-number on per-team elements inside it. If cards become flex/grid, change the search to restore '' (and preferably use the hidden attribute with a working [hidden] rule). Alliance colors are Jinja ternaries of full class names, so they're safe for the Tailwind scanner. If the rebuild assembles 'bg-{{ side }}-...', add a safelist. Consider pagination or collapsing for phones, but keep the existing context keys.

### app/templates/scouting/live-match-status.html

**Purpose:** Live team schedule: enter a team number and fetch TBA ranking, record and previous/upcoming matches for the team's current event. Everything below the form is built by the inline JS.

**Routes:** scouting.live_match_status GET /scouting/live-match-status?team=&event= (app/scout/routes/events.py:52-61), context team_number, event_code (event_code unused). JS: GET /api/tba/team-status?team=N (events.py:64-105) -> {status:{qual:{ranking:{rank}}}, matches:{previous:[{match_name,time,alliance,score:{red,blue}}], upcoming:[{match_name,time,alliance}]}, event:{key,name}}. Link scouting.home.

**Extends/includes:** extends base.html; {% block head %} holds an inline <style> (lines 3-16); inline <script> lines 113-341

**JS:** inline <script> live-match-status.html:113-341

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `form#teamStatusForm` | id | live-match-status.html:117,140-152 | Form whose submit is preventDefault-ed. JS reads #teamNumber, fetches, and pushState-s ?team=N. Without JS it would GET ?teamNumber=N, which the route ignores (it reads 'team'). |
| `input#teamNumber` | id | live-match-status.html:116,135,142 | Number input. Value comes from the ?team= URL param on load (line 135) and is read on submit. value="{{ team_number }}" renders the string 'None' when there is no param (use team_number or ''). |
| `#eventInfoBanner / #eventName` | id | live-match-status.html:127-128,159,170-171 | Banner toggled with the 'hidden' CLASS. #eventName textContent = data.event.name. |
| `#loadingIndicator, #noDataMessage, #resultsContainer` | id | live-match-status.html:118-120,156-158,175,179,181,338 | Each starts with the 'hidden' class, toggled via classList. Don't add responsive display utilities (sm:block etc.), because they would beat .hidden. |
| `#teamRanking / #rankingDetails` | id | live-match-status.html:121-122,226-251,245 | #rankingDetails innerHTML is replaced with 3 stat tiles, or with one 'col-span-3' empty tile, so the container is expected to be a 3-column grid. #teamRanking gets classList.remove('hidden'). |
| `#upcomingMatchesContainer / #upcomingMatches, #previousMatchesContainer / #previousMatches` | id | live-match-status.html:123-126,256,295,298,300,305,329,332,334 | Containers toggled with the 'hidden' class. Inner lists are cleared (innerHTML='') and filled with appendChild'ed div.match-item rows. |
| `.match-item.red-alliance / .match-item.blue-alliance` | css-hook | live-match-status.html:4-15 (inline <style>), :263,284,312,316 | JS sets className 'match-item red-alliance|blue-alliance px-4 py-3 sm:px-5'. The stripe colors come only from the inline <style>, scoped to '#previousMatches .match-item...' and '#upcomingMatches .match-item...' (the id selectors beat the divide-* border color). Keep the ids, or move the stripe CSS and keep its specificity above divide-zinc-*. |
| `escapeHtml + template literals` | other | live-match-status.html:185-192,226-327 | All interpolated API values pass through escapeHtml. Keep that when restyling the template strings. |

#### JS-generated markup
- live-match-status.html:226-243 ranking tiles (border-zinc-200 rounded-lg p-3, text-xs labels, text-xl tabular-nums values, TBA '.link')
- live-match-status.html:247-251 'No ranking information' tile (col-span-3 bg-zinc-50)
- live-match-status.html:283-293 previous match rows with resultClass from :266,274-279
- live-match-status.html:315-327 upcoming match rows with badge-red/badge-blue alliance badge

#### Hard-coded colours
- live-match-status.html:10 border-left-color #ef4444 (red alliance stripe)
- live-match-status.html:14 border-left-color #3b82f6 (blue alliance stripe)
- live-match-status.html:50-56 info banner border-blue-200 bg-blue-50 text-blue-800 / dark:...blue-500
- live-match-status.html:266,274-279 result text-zinc-500 / font-semibold text-green-700 dark:text-green-400 / text-red-600 dark:text-red-400 / text-amber-600 dark:text-amber-400
- live-match-status.html:323 badge-red / badge-blue

#### Legacy CSS
- inline <style> block in {% block head %} live-match-status.html:3-16 (.match-item border-left stripes)

#### Phone problems at 390px
- 'View status' submit is py-2.5 (about 42px) and 'Back to scouting' is .btn (about 38px), both under 44/48px.
- Match rows show the time in 12px (text-xs). The result score is text-sm and colored only by text color.
- Ranking tiles use grid-cols-3 with no breakpoint (about 100px each at 390px). OK for numbers, but the header label is shortened to 'TBA' via sm:hidden/hidden sm:inline.
- No auto-refresh: 'live' status needs a manual re-submit at events.

#### Redesign notes
All dynamic class strings are complete literals in a template file (scanned by Tailwind). The safelist in tailwind.config.js:7 (/^(bg|text|border)-(red|blue)-(100|500|800)$/) claims this page assembles alliance classes dynamically, but nothing currently does (allianceColor at :313 is unused). If the rebuild switches to something like `bg-${alliance}-500`, extend the safelist. Move the stripe colors into design tokens (red/blue alliance) for dark mode. Keep every id listed. Keep the 'hidden' class toggling or switch all of the JS together. Consider renaming the input to name='team' so a no-JS GET works.

### app/templates/scouting/pit-scouting.html

**Purpose:** Pit scouting list: team table with drive badges, BPS, shooter/intake/hopper notes, programming/auto summary, driver experience, scouter, edit/delete actions, plus team-number search and CSV export.

**Routes:** scouting.pit_scouting GET /scouting/pit (app/scout/routes/pit.py:60-74), context pit_data (list of Mongo dicts, [] on error). Row links: scouting.pit_scouting_edit GET /scouting/pit/edit/<entry_id> (pit.py:101); delete POST scouting.pit_scouting_delete /scouting/pit/delete/<entry_id> (pit.py:132-141, CSRF). Header link scouting.pit_scouting_add. Nav: scouting.home, matches, leaderboard, scouter_leaderboard.

**Extends/includes:** extends base.html; loads app/static/js/pit-scouting/list.js

**JS:** app/static/js/pit-scouting/list.js

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `#exportCSV` | id | app/static/js/pit-scouting/list.js:136-139 | Button. A click runs exportToCSV. |
| `#teamSearchInput` | id | app/static/js/pit-scouting/list.js:141,144-159 | Text input. addEventListener is called without a null check (throws if missing). |
| `tbody tr` | structure | app/static/js/pit-scouting/list.js:22,142 | Every <tr> in ANY tbody on the page is treated as a pit row, for both CSV and search. Don't put empty-state or other rows inside a tbody. Search sets row.style.display to ''/'none', so rows must be <tr> or a selector change is needed. |
| `td:first-child (team number)` | structure | app/static/js/pit-scouting/list.js:148-156 | First cell textContent must contain the team number (substring match). |
| `td:nth-child(1) .text-lg` | css-hook | app/static/js/pit-scouting/list.js:27-29 (comment pit-scouting.html:35) | Element with the literal class 'text-lg' holding the team number in column 1. Without it, querySelector returns null and the row is skipped in the CSV via the catch. |
| `td:nth-child(2) .rounded-full and .text-sm.text-gray-500` | css-hook | app/static/js/pit-scouting/list.js:32-42 | Drive-type badges must carry the literal class 'rounded-full' (text joined with '/'). The swerve-modules element must carry BOTH literal classes 'text-sm' and 'text-gray-500' (gray maps to zinc in tailwind.config.js, but the class NAME is what's selected). |
| `td:nth-child(3..7) by position` | structure | app/static/js/pit-scouting/list.js:45-85 | CSV reads columns 3-7 positionally. It is ALREADY wrong: headers say Motor Count / Motor Types / Dimensions / Programming Language / Has Auto / ... but the columns are BPS, Shooter, Intake, Hopper, Programming. The regexes look for 'Programming Language:', '✅', 'Preferred Start:' and 'Auton Notes:', which are never rendered, and the scouter is read from column 7 (Programming), so it comes out blank. Hidden (searched-out) rows are exported too. A rebuild should rewrite this export (data-* attributes per row) rather than preserve the broken mapping. If the JS is not touched, the column order Team, Drive, BPS, Shooter, Intake, Hopper, Programming, Driver, Scouter, Actions must stay. |
| `form POST pit_scouting_delete > input[name=csrf_token]` | form-field-name | app/scout/routes/pit.py:132-141; tests/test_security.py:52-53 | POST form with hidden csrf_token and an onsubmit confirm(). GET must not be used (route is POST-only and the test asserts 405 on GET). |
| `pit_data row fields` | jinja-context | app/scout/routes/pit.py:65-70 | team_number, drive_type.{swerve,tank,other}, swerve_modules, fuel_count_bps, shooter_type, shooter_notes, intake_notes, hopper_notes, programming_language (no longer collected, shows '—'), autonomous_capabilities.{has_auto,num_routes,preferred_start,notes}, driver_experience.{years,notes}, scouter_team, scouter_id, scouter_name, _id. 'notes' (additional notes) is collected but never displayed. Scouter identity is shown only when scouter_team == current_user.teamNumber. |

#### JS-generated markup
- app/static/js/pit-scouting/list.js:153 sets row.style.display '' / 'none'
- app/static/js/pit-scouting/list.js:124-132 builds a temporary <a download='pit_scouting_data.csv'>

#### Hard-coded colours
- pit-scouting.html:61 badge-blue (Swerve), :64,67 badge-gray
- pit-scouting.html:95 auto Yes text-green-700 dark:text-green-400
- pit-scouting.html:149 delete text-red-600 dark:text-red-400

#### Phone problems at 390px
- 10-column table with min-w-[10rem]/[9rem]x4/[13rem] columns (pit-scouting.html:77-114), about 1250px wide, so phones scroll sideways inside .table-wrap.
- Programming/Auto details are a 12px (text-xs) dl. Driver notes are text-xs.
- Edit/Delete are .btn-sm (about 30px). Header Export CSV / Add pit data are .btn (about 38px). Nav pills .btn-sm about 30px.
- Long free-text notes squeezed into 9rem columns.
- Edit is shown for every row, but pit.py:109 only allows the original scouter. Teammates tapping Edit get bounced with a flash error.

#### Redesign notes
If tables become cards on phones, keep tr/td (CSS-only card transform) or rewrite pit-scouting/list.js. Recommended: rewrite the CSV export to read data-* attributes and match the current columns. Then the .text-lg / .rounded-full / .text-sm.text-gray-500 hooks can go, but only if list.js changes in the same commit. Consider showing Edit/Delete only when data.scouter_id == current_user.id, matching the server check. Keep the delete form's csrf_token.

### app/templates/scouting/pit-scouting-add.html

**Purpose:** Add pit scouting entry: one long POST form (team, drive base chips, mechanisms, shooter type chips, autonomous yes/no chips + details, driver experience, notes).

**Routes:** scouting.pit_scouting_add GET/POST /scouting/pit/add (app/scout/routes/pit.py:77-98). The form posts to the same URL (no action attribute) and is parsed by _pit_form (pit.py:19-57). Success redirects to scouting.pit_scouting. Failure re-renders a blank form (entered data is lost).

**Extends/includes:** extends base.html; loads app/static/js/pit-scouting/add.js at the end of the content block

**JS:** app/static/js/pit-scouting/add.js; inline onchange/onclick on shooter 'Other' radio (pit-scouting-add.html:92-93)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `input[name=csrf_token]` | form-field-name | app/app.py:58 CSRFProtect; pit-scouting-add.html:20 | Hidden input value=csrf_token() inside the form. |
| `team_number` | form-field-name | app/scout/routes/pit.py:24; tests/test_pit_form.py:30,45; tests/test_route_logging.py:90-91 | Required number input. The server does int(form['team_number']), so a missing or disabled field raises and is caught as an error. |
| `drive_type (checkbox x2, values 'swerve','tank'), drive_type_other` | form-field-name | app/scout/routes/pit.py:27-31 | Same name on both checkboxes (form.getlist). Values are lowercase 'swerve'/'tank'. drive_type_other is free text. |
| `swerve_modules, fuel_count_bps` | form-field-name | app/scout/routes/pit.py:32,35; tests/test_pit_form.py:30-37 | fuel_count_bps blank -> 0 (via _form_int). |
| `shooter_type (radio: single,double,turret,multi,other)` | form-field-name | app/scout/routes/pit.py:36 | Lowercase values. Stored as a string and shown capitalized in the list. |
| `shooter_notes, hopper_notes, intake_notes, driver_years, driver_notes, notes` | form-field-name | app/scout/routes/pit.py:37-56; tests/test_pit_form.py:30 | Exact names. driver_years blank -> 0. |
| `has_auto (radio values 'false' default-checked / 'true')` | form-field-name | app/scout/routes/pit.py:22; app/static/js/pit-scouting/add.js:25-29; tests/test_pit_form.py:30,44-47 | Server checks == 'true'. add.js binds 'change' on every [name="has_auto"] and calls toggleAutoFields(value === 'true'). |
| `[name=auto_routes], [name=auto_preferred_start], [name=auto_notes]` | form-field-name | app/static/js/pit-scouting/add.js:2-11; app/scout/routes/pit.py:44-46 | JS sets .disabled and clears the value when 'No auto' is chosen (disabled styling comes from 'disabled:opacity-60' in the {% set field %} classes). The server ignores them unless has_auto=true. |
| `chip structure: label.relative > input.peer.sr-only + div.{{ chip }}` | structure | pit-scouting-add.html:3,44-50,81-97,131-144 (Tailwind peer-checked:/peer-focus-visible: variants) | The radio/checkbox must be a PRECEDING SIBLING of the styled element inside the same <label> so peer-checked styling and tap-to-toggle work. The input stays in the form (sr-only, not display:none) so it submits and is keyboard-focusable. |
| `#shooter_other_box (missing)` | id | pit-scouting-add.html:92-93 inline onchange/onclick | The 'Other' shooter radio runs document.getElementById('shooter_other_box').classList..., but no such element exists, so every tap throws a TypeError (the radio still checks). The rebuild should either add the box (an 'other shooter' input would also need a server field) or drop the handlers. |
| `<script src=pit-scouting/add.js> after the form` | structure | app/static/js/pit-scouting/add.js:25 | add.js queries [name="has_auto"] at parse time (no DOMContentLoaded), so the script tag must come after the form markup. It does not apply the initial state ('No auto' is pre-checked but the auto fields start enabled). toggleScoringFields (add.js:14-22) is dead code. |
| `ids pit-team-number, pit-swerve-modules, pit-fuel-bps, pit-shooter-notes, pit-hopper-notes, pit-intake-notes, pit-auto-routes, pit-auto-start, pit-auto-notes, pit-driver-years, pit-driver-notes` | id | label[for] in the same template only | Only label/for associations. Keep labels associated (accessibility). |

#### JS-generated markup
- app/static/js/pit-scouting/add.js:6-9 toggles .disabled and clears values on the auto fields

#### Hard-coded colours
- pit-scouting-add.html:3 chip classes: peer-checked:border-blue-600 peer-checked:bg-blue-50 peer-checked:text-blue-700, dark:peer-checked:border-blue-500 dark:peer-checked:bg-blue-500/10 dark:peer-checked:text-blue-300, peer-focus-visible:ring-blue-500/60

#### Legacy CSS
- app/static/css/global.css:7-17 (hides number input spinners; affects team_number, fuel_count_bps, auto_routes, driver_years)

#### Phone problems at 390px
- Text and number fields are .input (py-2 + 16px text, about 42px tall), under the 48px target.
- Save/Cancel (btn-lg, 44px) sit only at the very bottom of a 6-card form: no sticky save bar, so long scrolls are needed at competition.
- Shooter chips are grid-cols-3 for 5 options (ragged second row). Drive chips are grid-cols-2.
- 'Back to list' header button is .btn (about 38px).
- Section titles and help text are small (text-xs help).

#### Redesign notes
Keep every field name and value exactly as listed (pit.py and tests/test_pit_form.py depend on them). A sticky save bar must stay INSIDE the <form> (or use form="<id>" on the button) so submit still posts. Keep the peer-sibling chip structure or reimplement checked styling with :has(). Initialize toggleAutoFields on load and include add.js on the edit page too (or the equivalent). Fix the missing #shooter_other_box handlers. Class strings inside {% set chip %}/{% set field %} are scanned by Tailwind because they sit in the template text. Moving them into Python would need a content-glob change.

### app/templates/scouting/pit-scouting-edit.html

**Purpose:** Edit an existing pit scouting entry. Same form as add, pre-filled from the entry, with a read-only team number.

**Routes:** scouting.pit_scouting_edit GET/POST /scouting/pit/edit/<entry_id> (app/scout/routes/pit.py:101-129), context entry (Mongo dict). Only the original scouter may edit (pit.py:109). The form posts to the same URL. Success redirects to scouting.pit_scouting.

**Extends/includes:** extends base.html (does NOT load pit-scouting/add.js)

**JS:** inline onchange/onclick on shooter 'Other' radio (pit-scouting-edit.html:98-99)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `input[name=csrf_token]` | form-field-name | app/app.py:58; pit-scouting-edit.html:20 | Hidden csrf_token inside the form. |
| `input[name=team_number][readonly]` | form-field-name | app/scout/routes/pit.py:24,115; tests/test_pit_form.py:32,49-51 | Must stay readonly, NOT disabled: disabled inputs aren't submitted and the server requires form['team_number'] (KeyError is caught as an error and no update happens). Value entry.team_number. |
| `same field names as add: drive_type, drive_type_other, swerve_modules, fuel_count_bps, shooter_type, shooter_notes, hopper_notes, intake_notes, has_auto, auto_routes, auto_preferred_start, auto_notes, driver_years, driver_notes, notes` | form-field-name | app/scout/routes/pit.py:19-57,115 | Same names and values as the add form. Prefill expressions: entry.drive_type.get(type) checked, entry.drive_type.get('other',''), entry.shooter_type == stype checked, entry.autonomous_capabilities.get('has_auto') for the true/false radios, .get('num_routes',0) / .get('preferred_start','') / .get('notes',''), entry.driver_experience.get('years',0) / .get('notes',''), entry.notes, entry.fuel_count_bps or 0, entry.shooter_notes/hopper_notes/intake_notes or ''. |
| `chip structure label > input.peer.sr-only + div` | structure | pit-scouting-edit.html:3,45-52,85-103,137-152 | Same peer-sibling requirement as the add page. |
| `#shooter_other_box (missing)` | id | pit-scouting-edit.html:98-99 | Same broken inline handler as the add page (throws on tap). |

#### Hard-coded colours
- pit-scouting-edit.html:3 chip blue peer-checked classes (same as the add page)
- pit-scouting-edit.html:30 readonly bg-zinc-50 text-zinc-500 dark:bg-zinc-800/60 dark:text-zinc-400

#### Legacy CSS
- app/static/css/global.css:7-17 (number spinners hidden)

#### Phone problems at 390px
- Same as the add page: inputs about 42px, the save button only at the bottom (btn-lg 44px, not sticky), 'Back to list' about 38px.
- Read-only team number is styled only by a gray background (bg-zinc-50 text-zinc-500), which is easy to mistake for an editable field.
- The auto detail fields are never disabled when 'No auto' is selected (add.js isn't loaded), unlike the add page.

#### Redesign notes
Share one form macro between add and edit to avoid drift, but keep the readonly (not disabled) team_number on edit. Keep the sticky save bar inside the form. The 'Save changes' and 'Cancel' (link to scouting.pit_scouting) semantics stay.

### app/templates/team/create.html

**Purpose:** Create-team form (WTForms CreateTeamForm): team number, name, description with character counter, optional logo upload.

**Routes:** team.create GET/POST /team/create (app/team/routes.py:65-123), context form (CreateTeamForm, app/team/forms.py:11-62). Redirects to team.manage if the user already has a team. Link: team.join.

**Extends/includes:** extends base.html; inline <script> create.html:98-114

**JS:** inline <script> create.html:98-114

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `form[method=POST][enctype=multipart/form-data]` | structure | app/team/routes.py:75-99 | POST to the same URL with multipart enctype (logo upload via form.logo.data). |
| `{{ form.csrf_token }}` | form-field-name | app/team/forms.py:12-13 (Meta csrf=True) | Renders hidden input name/id csrf_token. Must stay inside the form. |
| `form.team_number / form.team_name / form.description / form.logo (names+ids team_number, team_name, description, logo)` | form-field-name | app/team/forms.py:15-50; app/team/routes.py:80-106; label for= in create.html:17,37,52,71 | Render through the WTForms field callables (they emit name and id). Validation: team_number 1-19999, team_name 1-100 chars, description up to 500, logo jpg/png up to 2MB (FileAllowed rejects '.jpeg'). Keep the per-field {% for error in form.X.errors %} blocks. The oninput digit-strip, pattern, min and max attributes are passed as render kwargs. |
| `textarea[name="description"], input[name="team_number"], #char-count` | structure | create.html:99-113 | The inline script runs at parse time (no DOMContentLoaded), so it must stay after the form. #char-count textContent is updated on input. The JS truncates the description at 100 chars and clamps team_number to 19999. Note: maxlength=100 and the JS 100-char cap conflict with the server limit of 500, and #char-count starts at 0 even when re-rendered with a value. |

#### JS-generated markup
- create.html:101 sets #char-count text

#### Hard-coded colours
- create.html:20,40,55 error state border-red-500 focus:border-red-500 focus:ring-red-500/20 dark:border-red-500; :29,45,64,78 text-red-600 dark:text-red-400; :73 file: button zinc classes

#### Legacy CSS
- app/static/css/global.css:7-17 (team_number spinner hidden)

#### Phone problems at 390px
- File input button (file:py-2) is about 36px. The char counter and help text are 12px.
- Submit is py-2.5 (about 42px), under the 48px target.
- Error messages are text-xs.

#### Redesign notes
Field classes are passed as Jinja strings into the WTForms callables in the template, so Tailwind still scans them. Don't move them into forms.py render_kw (not in tailwind content globs). Keep the multipart enctype. Decide the description limit (100 vs 500) consistently with the settings page.

### app/templates/team/join.html

**Purpose:** Join a team with a join code.

**Routes:** team.join GET/POST /team/join (app/team/routes.py:32-63). Reads request.form['join_code'], flashes and redirects. Redirects to team.manage if the user is already on a team. Link team.create. manage.js redirects here after leave/delete (manage.js:260,288).

**Extends/includes:** extends base.html

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `input[name=csrf_token]` | form-field-name | app/app.py:58 | Hidden csrf_token inside the POST form. |
| `input#join_code[name=join_code]` | form-field-name | app/team/routes.py:40 | Text input named join_code, required. The form posts to the same URL (no action). |

#### Phone problems at 390px
- Input and button are py-2.5 (about 42px), under the 48px target. Otherwise single-column and phone-friendly.

#### Redesign notes
Trivial contract: POST form with csrf_token + join_code. Keep autocapitalize=characters, autocomplete=off and spellcheck=false.

### app/templates/team/manage.html

**Purpose:** Team dashboard: logo/name header with settings and delete/leave actions, description (see more/less), join code (admins), members table with search and admin/remove actions, assignments table with search, per-user status select, reminder bell, admin edit/delete/clear, and three modals (new assignment, edit assignment, reminder).

**Routes:** team.manage GET /team/, /team/manage, /team/manage/<int:team_number> (app/team/routes.py:275-325), context team, current_user, team_members, user_dict, assignments (current user's first), is_admin. JS endpoints via fetch with X-Requested-With (CSRF header added by the base.html fetch wrapper): POST /team/<n>/assignments JSON {title,description,assigned_to[],assigned_to_names[],due_date} (routes.py:203-229); PUT /team/assignments/<id>/status {status} (routes.py:232-247, CSRF-exempt app/app.py:94); PUT /team/assignments/<id>/edit (routes.py:418-437); DELETE /team/assignments/<id>/delete (routes.py:263-272); POST /team/<n>/assignments/clear (routes.py:354-375); POST /team/<n>/delete (routes.py:379-395); POST /team/<n>/leave (routes.py:126-147); POST /team/<n>/admin/add and /admin/remove {user_id} (routes.py:162-200). HTML form POST team.remove_user /team/<n>/user/<id>/remove (routes.py:328-350). notifications.js -> /notifications/* push subscription. Links: team.settings, team.team_logo, auth.profile, auth.profile_picture.

**Extends/includes:** extends base.html; loads app/static/js/notifications.js then app/static/js/team/manage.js; inline <script> manage.html:562-591

**JS:** app/static/js/notifications.js; app/static/js/team/manage.js; inline <script> manage.html:562-591 (toggleDescription, member option filter); inline onclick handlers manage.html:33,41,61,66,170,201,243,247,280,285,328,342,349,353,447,509,548

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `#teamData[data-team-number][data-current-user-id]` | data-attr | app/static/js/team/manage.js:8-11,74,220,247,275,299 | Hidden element carrying data-team-number={{ team.team_number }} and data-current-user-id. It builds every fetch URL. If it's missing, the create, clear, delete-team, leave and admin actions all throw. |
| `onclick=confirmDeleteTeam() / confirmLeaveTeam()` | other | manage.html:33,41 -> manage.js:242-296 | Global functions. Delete is shown when team.is_owner(current_user.id). Leave is shown when current_user.id in team.users. After success the page goes to /team/join. |
| `.description-container > .description-preview + .description-full` | class | manage.html:563-570 (toggleDescription); app/static/js/team/manage.js:358-368 | toggleDescription(button) finds button.closest('.description-container') and toggles the 'hidden' CLASS on .description-preview and .description-full (the full one starts with 'hidden'). openEditAssignmentModal reads descriptionFull.childNodes[0].textContent (else descriptionPreview.childNodes[0]): the description TEXT must be the FIRST child node of .description-full/.description-preview. Wrapping it in an element or putting anything before it would make Edit blank the description. Used for both the team description (:56-71) and assignment descriptions (:276-287). |
| `#memberSearch` | id | app/static/js/team/manage.js:16,19-34 | Text input. Filters .member-row elements. |
| `tr.member-row (children[0..2])` | class | app/static/js/team/manage.js:22-31 | Row search reads row.children[0], [1], [2] textContent (username cell, email cell, role cell) and sets row.style.display ''/'none'. Keep the column order Username, Email, Role(, Actions). The mobile duplicates of the role badge and email inside cell 0 (sm:hidden) are fine because textContent ignores CSS. |
| `onclick=updateAdminStatus('{{ member.get_id() }}','add'|'remove')` | other | manage.html:170,201 -> manage.js:298-326 | Global function. Shown only when the current user is the owner. |
| `form POST team.remove_user > input[name=csrf_token]` | form-field-name | app/team/routes.py:328-350 | Classic POST form with csrf_token and an onsubmit confirm(). Admin only. |
| `#assignmentSearch` | id | app/static/js/team/manage.js:17,36-51 | Text input. Filters .assignment-row elements by td:first-child, td:nth-child(2), td:nth-child(3) textContent and sets style.display. |
| `tr.assignment-row[data-assignment-id]` | class | app/static/js/team/manage.js:39-48,330,346-350,461-465,515-518; app/static/js/notifications.js:291 | Must be <tr> elements: openEditAssignmentModal queries tr[data-assignment-id="id"] and reads row.getElementsByTagName('td') [0] title, [1] description, [2] assigned-to, [3] due date. updateStatusBadge uses closest('tr') and td:nth-child(4). Column order: Title, Description, Assigned to, Due date, Status, Actions. The title cell must contain ONLY the title (textContent.trim() fills the edit form). Assigned-to textContent is split on ',' and matched against option text, so it may contain only comma-separated usernames. Due date cell text must be the strftime('%Y-%m-%d %I:%M %p') value parsed by new Date(), or 'No due date'. Note: the edit modal fills edit_due_date via toISOString(), which shifts it to UTC (pre-existing bug), and Firefox/Safari may not parse that format. The 'No assignments found' row has no assignment-row class (keep it that way). |
| `.status-badge` | class | app/static/js/team/manage.js:156,185-186,461-465 | Status badge span. JS replaces textContent ('In progress', 'Completed (late)', ...) and OVERWRITES className with 'badge status-badge badge-green|badge-amber|badge-gray|badge-red' on page load for rows that have a status select, and after each status change. Any extra classes put on this span are wiped, so style via the .badge* component classes. |
| `select[name=status] onchange=updateAssignmentStatus(this,'id')` | form-field-name | app/static/js/team/manage.js:63-70,127-151,462 | Rendered only when current_user is in assignment.assigned_to. Option values are pending|in_progress|completed. A click stores data-previous-value for rollback. The PUT goes to /team/assignments/<id>/status. The wrapping <form action=update_assignment_status method=POST> is never submitted (that route is PUT-only). |
| `button.assignment-reminder-btn[title="Set reminder for this assignment"][data-assignment-id]` | class | app/static/js/team/manage.js:515-522; app/static/js/notifications.js:291-296,315; manage.html:342 | manage.js finds the bell by its EXACT title attribute inside .assignment-row. notifications.js binds click by .assignment-reminder-btn and reads dataset.assignmentId. The inline onclick also un-hides #assignmentReminderModal and sets #reminderAssignmentId. |
| `onclick=openEditAssignmentModal('id') / deleteAssignment('id') / clearAllAssignments()` | other | manage.html:243,349,353 -> manage.js:189-240,328-416 | Global functions. Edit/Delete render under {% if is_admin %}, Clear all under team.is_admin(...). |
| `#createAssignmentModal` | id | manage.html:247,447; app/static/js/team/manage.js:99,122 | Overlay toggled with the 'hidden' CLASS (inline onclicks and JS). No responsive display classes. |
| `form#createAssignmentForm with #title, #description, #assigned_to (select multiple name=assigned_to), #due_date (datetime-local)` | id | app/static/js/team/manage.js:56-59,87-96,113 | JS reads these ids directly (not form names) and posts JSON. #assigned_to options: value=member.get_id(), text=username (assigned_to_names comes from option.text). Submit is preventDefault-ed. The form's action attribute is unused. tests/test_bug_fixes.py:30-42 covers the JSON endpoint. |
| `#memberSearchInput` | id | manage.html:573-589 | Filters #assigned_to by cloning the original <option>s (the clone drops the current selection state, a pre-existing bug). Both ids must exist at DOMContentLoaded or the inline script throws. |
| `#editAssignmentModal / form#editAssignmentForm / #edit_assignment_id / #edit_title / #edit_description / #edit_assigned_to / #edit_due_date` | id | app/static/js/team/manage.js:336-410,418-450,455-458; manage.html:509 | Modal toggled with the 'hidden' class. The submit handler reads these ids and PUTs JSON to /team/assignments/<id>/edit. #edit_assigned_to option text must equal the usernames shown in the Assigned-to cell. |
| `#assignmentReminderModal / #reminderAssignmentId / #assignmentReminderTime / #saveAssignmentReminder` | id | app/static/js/notifications.js:323-339; manage.html:342,548 | Modal toggled with the 'hidden' class. #assignmentReminderTime is a select of minute values (5..10080, default 1440). Save's onclick is assigned only when notifications.js initialized successfully (otherwise Save does nothing, pre-existing). |
| `script order notifications.js -> team/manage.js` | structure | app/static/js/team/manage.js:80 (global notificationManager) | handleAssignmentSubmit calls notificationManager.subscribeToPushNotifications(), defined in notifications.js. Both are classic scripts with global functions used by inline handlers. |
| `Jinja role grouping members_by_role + team.is_admin/is_owner/owner_id/admins/users, user_dict, is_admin` | jinja-context | app/team/routes.py:300-325 | Owner/admin/member ordering and the permission conditions for each action. Assignment fields: id, title, description, assigned_to (list of str ids), due_date (datetime, strftime), status. Current user's rows get the bg-blue-50/70 tint. |

#### JS-generated markup
- app/static/js/team/manage.js:154-187 updateStatusBadge rewrites .status-badge text and className (badge-red when late)
- app/static/js/team/manage.js:469-510 createAssignmentRow builds a <tr> with classes (dead code, never called; relies on the implicit global currentUserId)
- app/static/js/team/manage.js:29,46 row.style.display toggles
- app/static/js/team/manage.js:519-522 adds data-assignment-id and the assignment-reminder-btn class to reminder bells
- manage.html:568-569 toggles the hidden class on description preview/full
- manage.html:581-588 rebuilds #assigned_to options
- app/static/js/notifications.js:327,338 show/hide the reminder modal

#### Hard-coded colours
- manage.html:34,42,212,244,354 destructive text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-500/10
- manage.html:137,143 badge-blue (Owner); :159,165 badge-green (Admin); :190,196 badge-gray (Member)
- manage.html:271 current-user row tint bg-blue-50/70 dark:bg-blue-500/10
- manage.html:295 current user name text-blue-600 dark:text-blue-400
- manage.html:308-315 status badge-green / badge-amber / badge-gray
- app/static/js/team/manage.js:170-172 statusClasses badge-red / badge-green / badge-amber / badge-gray
- app/static/js/team/manage.js:472 bg-blue-50/70 dark:bg-blue-500/10; :504 text-zinc-500

#### Phone problems at 390px
- Assignments table has 6 columns with a min-w-[14rem] description and nowrap cells, about 900px wide, so phones scroll sideways (manage.html:257-370).
- Status select is '.input w-auto py-1.5' (about 38px). The reminder bell is .btn-icon (about 36px). Edit/Delete/Make admin/Remove admin/Remove are .btn-sm (about 30px).
- Header actions (Team settings, Delete/Leave team) and modal footer buttons are .btn (about 38px).
- Assign-to is a native <select multiple size=6> with help text 'Hold Ctrl/Cmd to select multiple members', which doesn't apply on phones. The phone multi-select picker plus #memberSearchInput cloning loses selections.
- Modals don't close on backdrop tap or Escape and have no role=dialog/aria-modal. On phones they scroll as one long overlay.
- h1 team name is 'truncate', so long names get cut off. Join code is text-lg font-mono tracking-widest.
- Search inputs are .input (about 42px).

#### Redesign notes
Highest-risk page for a table-to-card conversion: manage.js uses tr/td positions in 5 places. Either keep <table> markup and do CSS-only cards with data-label ::before (no visible label text inside the title, assigned-to or due-date cells), or rewrite manage.js to use data attributes (data-title, data-description, data-assigned-ids, data-due-iso). The latter also fixes the UTC shift and parse problems. Keep description text as the first text node, or switch to a data attribute. Keep every modal and panel toggled by the 'hidden' class without responsive display utilities. Keep the exact reminder button title text or update manage.js:515. All JS class strings are complete literals inside app/static/js (in the Tailwind content glob), so no safelist is needed.

### app/templates/team/settings.html

**Purpose:** Admin team settings: change logo (client-side compressed with Compressor.js, with preview) and description.

**Routes:** team.settings GET /team/<int:team_number>/settings (app/team/routes.py:494-506, admins only, else redirect to team.manage), context team. The form POSTs multipart to team.update_team_info /team/<n>/update_team_info (routes.py:509-567): request.files['team_logo'] (allowed_file PNG/JPG/JPEG, stored in GridFS) and request.form['description'] (stripped). Redirects to team.manage with a flash. Link team.manage.

**Extends/includes:** extends base.html; {% block head %} loads https://cdnjs.cloudflare.com/ajax/libs/compressorjs/1.2.1/compressor.min.js; inline <script> settings.html:91-146

**JS:** https://cdnjs.cloudflare.com/ajax/libs/compressorjs/1.2.1/compressor.min.js; inline <script> settings.html:91-146

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `form#teamSettingsForm[method=POST][enctype=multipart/form-data][action=update_team_info]` | structure | app/team/routes.py:509-567 | Multipart POST with a hidden csrf_token. The id is not used by JS. |
| `input#team_logo[name=team_logo][type=file] onchange=handleLogoChange(this)` | form-field-name | app/team/routes.py:525-551; settings.html:92-136 | Name team_logo (the server reads request.files['team_logo']). It is visually hidden (class 'hidden') inside a <label class='btn'>, so tapping the label opens the picker. handleLogoChange must stay global. It replaces input.files with the compressed JPEG via DataTransfer and enforces a 6MB limit with alert(). |
| `img#team-logo-preview` | id | settings.html:93,108 | <img> whose src is replaced with a FileReader data URL. |
| `textarea#description[name=description] + #char-count` | form-field-name | app/team/routes.py:555; settings.html:138-145 | Name description. The inline script selects textarea[name="description"] at parse time (script must come after it), updates #char-count and truncates at 100 chars. That conflicts with maxlength=500 and the server, which accepts any length (pre-existing). Initial #char-count = team.description|length. |
| `Compressor global (head block)` | other | settings.html:114 | compressorjs 1.2.1 must load before a file is chosen (the head block in base must remain). |

#### JS-generated markup
- settings.html:108 sets #team-logo-preview src
- settings.html:140 sets #char-count text

#### Phone problems at 390px
- 'Choose file' label button and Save are .btn (about 38px). Save is full width only on mobile.
- Help text is 12px (text-xs). The 'Recommended size...' line wraps long.
- Page header 'Back to team' button is .btn (about 38px).

#### Redesign notes
Keep field names team_logo and description, the multipart enctype and csrf_token. Keep the file input reachable through its label (a hidden input is fine because the label is clickable). Fix the 100 vs 500 description limit consistently with create.html. A sticky save bar must stay inside the form.

### app/templates/team/view.html

**Purpose:** Public team profile: logo, number and name, member badge, link to the dashboard for members, description, member grid linking to profiles.

**Routes:** team.view GET /team/view/<int:team_number> (app/team/routes.py:440-462, public, no login_required), context team, team_members, is_member. Linked from scouting/_match_list.html:145 (scouter team). Redirects to index if the team isn't found.

**Extends/includes:** extends base.html

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `Jinja context team / team_members / is_member` | jinja-context | app/team/routes.py:457-462 | team.team_number, team.team_name, team.description; member.username and member.id (url_for auth.profile(username) and auth.profile_picture(user_id=member.id)). The dashboard link to team.manage(team_number) shows only when is_member. Must also render for anonymous users (current_user may be anonymous). |

#### Hard-coded colours
- view.html:15 badge-green (Team member)

#### Phone problems at 390px
- h1 'page-title truncate' (view.html:11) cuts off long team names on a 390px screen.
- Member grid is fine (single column). The 'Go to team dashboard' button is .btn (about 38px).

#### Redesign notes
No JS hooks. Keep the url_for targets and the public (anonymous) rendering. Let the team name wrap instead of truncating on phones.

### Other missed hooks (verified)
- `app/templates/team/manage.html (team/manage.js fetches)` `Request header 'X-Requested-With: XMLHttpRequest'` (used by app/static/js/team/manage.js:105,135,198,226,254,282,309,435; app/team/routes.py:136,338,365,387 (leave, remove_user, clear, delete return JSON only when the header is present); app/app.py:119-125 (the CSRF error handler returns JSON only for is_json or XHR)): Without the header these routes flash and 302 to an HTML page, so manage.js's response.json() throws and the user gets a generic alert. clearAllAssignments (manage.js:223-228) sends no JSON body, so on a CSRF failure this header is the only thing that gets a JSON answer back. Keep it on every manage.js fetch, including in a rewrite.

### Other missed items (verified)
- JS-generated markup missed on list.html: coloris.js (loaded in {% block head %} at list.html:7) appends div#clr-picker.clr-picker to document.body on DOM ready. It holds a text input, two range sliders and a radio fieldset (coloris.js:967-1008, DOMReady(init) at the end of the file). The only thing hiding it is coloris.css '.clr-picker{display:none}' (coloris.css:1-2). Remove coloris.js and coloris.css together. Dropping only the CSS while keeping the script shows an unstyled picker at the bottom of the page.
- Pit list: Delete is shown on every row, not just Edit. delete_pit_scouting matches on scouter_id only (app/scout/scouting_utils.py:806-809), so a teammate tapping Delete gets 'Error deleting pit scouting data' (pit.py:138-140). The inventory flags only Edit. Gate both on data.scouter_id == current_user.id (pit-scouting.html:148-149).
- records.py:99-103 calls flash('Unable to fetch scouting data...') before it checks partial=1. A failed AJAX search or Load more therefore queues a toast that appears on the next full page load, long after the in-page #matchListStatus error.
- Phone, sticky save bar: base.html:168 renders flash toasts as 'fixed inset-x-4 bottom-4 z-50', and base.js:120-122 adds an update banner as 'fixed bottom-0 left-0 right-0 ... z-50' (hardcoded bg-blue-500). Both sit exactly where a sticky full-width bottom save bar would go on pit add/edit, team settings and team create. After a failed pit save, the error toast covers the save button. Give the save bar and toasts a defined stacking order and offset.
- Phone, team logo upload: settings.html:53 accept="image/*" lets phones pick HEIC or WebP files. Compressor re-encodes to JPEG but keeps the original filename (settings.html:122 new File([result], file.name, ...)). The server checks the extension against {'png','jpg','jpeg','gif'} (app/utils.py:75,225-227; routes.py:528-551), so it flashes 'Invalid file type'. The inventory's 'PNG/JPG/JPEG' also omits gif. create.html's FileAllowed(['jpg','png']) (forms.py:45) has no accept attribute at all, so phone pickers offer any file.
- Auto path canvas sizing: Canvas.resizeCanvas measures container.getBoundingClientRect() and writes the canvas size as inline px (Canvas.js:185-196). list.js:81,90 calls it synchronously right after removing 'hidden'. Any open animation on the modal or card that uses transform: scale() or animated height/opacity-with-size would be measured mid-animation, leaving the canvas undersized until a window resize. It also won't follow container size changes that aren't window resizes (e.g. aspect-ratio or vh-based heights inside a transitioning modal). Keep the modal's open state instant, or call resizeCanvas after transitionend.
- Phone hint text for the auto path modal: in read-only mode Canvas ignores one-finger touches and handles two-finger pan/pinch with preventDefault (Canvas.js:1415-1420, 1517-1522). Replacement copy for list.html:28-30 should say 'two-finger drag/pinch', not just drop the Shift+drag/wheel hint. One-finger drags on the canvas scroll the overlay.

## Group: analysis

### Shared findings
- Tailwind: tailwind.config.js:5 content = ['./app/templates/**/*.html', './app/static/js/**/*.js']. Every JS-generated class in this group is a literal string (ternaries pick whole names such as 'badge-red'), so no new safelist entries are needed. The existing safelist (tailwind.config.js:8) is only for live-status red/blue. Keep the JS glob, and keep new state classes as literals, never built like `bg-${x}-50`.
- JS-generated markup reuses component classes from app/static/css/tailwind.input.css: .card, .card-header, .card-body, .section-title (compare.js:422-429), .table (compare.js:465, also styles the raw tbody rows), .badge plus .badge-red/.badge-blue/.badge-gray (compare.js:278, auton.js:308, :430-436), .btn .btn-secondary .btn-sm (auton.js:313), .link (compare.js:304, :491). Renaming or removing these component classes breaks the look of JS-rendered content; restyle them in place.
- The 'hidden' utility is toggled on elements that also carry a display utility: #autoPathModal 'flex hidden' (lighthouse.html:220), #split-view 'grid hidden' (mock:89), #control-buttons 'flex hidden' (mock:123). This relies on Tailwind emitting .hidden after .flex/.grid. If the rebuild uses custom display classes, make sure 'hidden' still wins (or toggle display differently in JS).
- Dark mode must stay the 'dark' class on <html>: base.html:29-32 sets it and :220-221 toggles it. compare.js:162 reads it and compare.js:237-246 observes it to re-theme the radar chart. auton.css and the mock inline <style> use '.dark ...' selectors.
- Service worker (app/static/js/service-worker.js:11-29, :240-268) serves tailwind.css, global.css, Canvas.js and team-stats.js cache-first. Any rebuild that changes them must bump STATIC_CACHE_NAME and CACHE_VERSION (service-worker.js:1-6), or phones at competition keep the old CSS and JS. compare.js, auton.js, mock-alliance-selection.js, playoff-bracket.js and auton.css are not precached (they go to the network).
- Unpinned third-party scripts that are hard dependencies: localforage from cdn.jsdelivr.net/gh/... master (lighthouse.html:3, auton.html:9; required by Canvas.js:112 at construction), Sortable 'sortablejs@latest' (auton.html:8; without it auton.js:45 throws and no button listeners are attached), Chart.js 'npm/chart.js' with no version (lighthouse.html:248). Popper '@2' in base. Pin exact versions in the rebuild.
- Canvas.js contract (used by lighthouse modal and auton): the container needs an explicit non-zero height and must be displayed when new Canvas() runs (Canvas.js:170-196 uses getBoundingClientRect); wheel zoom binds on the container (Canvas.js:1051); read-only touch supports only a two-finger pan (Canvas.js:1416-1418); colours are hardcoded and not dark-aware (Canvas.js:80-84, '#0066ff', '#ffffff'); the field image is /static/images/field-2026.png. compare.js builds a new Canvas on every modal open, so listeners pile up (existing leak).
- Shared script: app/static/js/team-stats.js serves the leaderboard (tbody[data-metric-sort] sorting) and scouting/list.html:89 plus _match_list.html:56-64 via scout/list.js:47 loadTeamStats(container). Changing its selectors (.team-stats-cell, data-team-id, data-event-id, .{epa,opr,dpr,ccwm}-value) affects both pages.
- Numbers font (Oxanium): compare.js stat targets are value-only spans (good). team-stats.js writes 'EPA: 12.3' as one text node, so the label and number cannot be styled separately without changing team-stats.js:30-31. Rank cells are rewritten by team-stats.js:50.
- Team colour mapping is duplicated: lighthouse.html:154-160 dot classes (bg-blue-600/amber-500/teal-500) must equal compare.js:327 getTeamColor; auton.js:13-20 TEAM_COLORS. Alliance red/blue appears as badge-red/badge-blue (compare.js:278, auton.js:308/:430-436) and as bracket bars/badges (mock:194-210). Update them together when moving blue to #0b5fb0 (light) or #2f7ae0 (dark).
- Legacy CSS in use: app/static/css/auton.css (auton page only, hex colours), the inline <style> in mock-alliance-selection.html:226-373, global.css (all pages; hides number spinners, sets scrollbar-width). Unused on these pages: coloris.css/coloris.js on lighthouse.html:4-5. Missing file: css/styles.css (auton.html:3-6, 404).
- Dead code that is safe to drop: radar.js (targets the nonexistent #radar-chart-combined; updateRadarCharts is never called); compare.js:250-257 resize handler (window.radarChart is undefined because radarChart is a top-level let); leaderboard.html:298-304 [data-progress-value] onload; lighthouse.html:165-170 #auto-path-team{n}-container (wiped by compare.js:421); #team-cards-container and #team{n}-stats ids (no JS reads them); auton.css .drag-handle and .path-card.selected (never applied).
- Existing behaviour bugs a rebuild should not make worse and may fix deliberately: auton Sortable indices are offset by #empty-prompt inside #selected-paths (auton.js:463-469), and removePath indices go stale after a drag (auton.js:445); mock createSVGElement creates non-SVG elements, so notification icons and the dismiss X are invisible (mock-alliance-selection.js:203-210); TBA nicknames go into innerHTML unescaped (mock-alliance-selection.js:648, :664, :745); compare card order follows numeric team order, not input order (Object.entries on integer keys); empty-row colspans are wrong (leaderboard 17 vs 16 columns, scouter 6 vs 5).
- Endpoints and links: url_for names scouting.leaderboard, scouting.scouter_leaderboard, scouting.lighthouse, scouting.auton and scouting.mock_alliance_selection are linked from base.html:75,91,144 (compare_active covers lighthouse and auton), index.html:24, scouting/list.html:59-64, matches.html:20, pit-scouting.html:24-25, and cross-linked from these pages' own nav strips. All five pages use the same horizontally scrolling btn-sm nav pattern (about 30px tap targets).
- Inline handlers that need global functions: leaderboard.html:24/:42 (changeEvent, changeRanking), lighthouse.html:224 (closeAutoPathModal), mock-alliance-selection.html:136 (exportPlayoffResults). Keep the functions global or replace the handlers with listeners. No CSP is involved.
- Script placement: compare.js does top-level getElementById and addEventListener at parse time (compare.js:15-28), so it must stay after the markup (end of the content block) or be deferred. auton.js, mock-alliance-selection.js and team-stats.js use DOMContentLoaded. playoff-bracket.js depends on mock-alliance-selection.js globals.

### Corrections (verified by second pass)
- **Claim:** Read-only touch on Canvas allows only a two-finger pan and has no pinch zoom (lighthouse and auton phone_problems; shared Canvas.js contract citing Canvas.js:1416-1418)
  **Correction:** A two-finger touchmove both pans and pinch-zooms: scale is multiplied by 1.01 or 0.99 as the finger distance changes, clamped to 0.1-10. In read-only mode only single-finger touches are ignored, and those pass through to page scroll. The on-screen hint text is still desktop-only.
  **Evidence:** app/static/js/Canvas.js:1517-1541 (lastDistance / zoomFactor = delta > 0 ? 1.01 : 0.99; this.scale *= zoomFactor)
- **Claim:** Passing draggable:'.selected-path-card' to Sortable fixes the auton reorder index offset
  **Correction:** Sortable's evt.oldIndex and evt.newIndex count every element sibling, whatever the draggable option says; only evt.oldDraggableIndex and evt.newDraggableIndex are filtered. The fix is either to move #empty-prompt out of #selected-paths, or to set draggable and switch updatePathOrder to the *DraggableIndex properties.
  **Evidence:** app/static/js/lighthouse/auton.js:465-466 use evt.oldIndex/evt.newIndex; #empty-prompt is the first child at auton.html:262-265. Sortable's README defines oldDraggableIndex as 'only counting draggable elements', separate from oldIndex. (Library semantics from that README; there is no local copy of Sortable to check against.)
- **Claim:** The 'Picking' indicator shrinks to 0.65rem under 1024px (mock-alliance-selection.html:343-348)
  **Correction:** That media query is dead. The unconditional .pick-round-indicator rule comes after it with the same specificity, so the indicator is 0.75rem with 0.5rem padding at every width.
  **Evidence:** app/templates/scouting/mock-alliance-selection.html:343-348 (@media) followed by :350-357 (.pick-round-indicator {font-size:0.75rem; padding:0.125rem 0.5rem})
- **Claim:** A non-table element makes [...body.rows] throw, and the catch at team-stats.js:87-91 then turns every metric into N/A
  **Correction:** sortLeaderboard only selects tbody elements, so body.rows always exists and cannot throw here. A div with data-metric-sort is silently ignored (no sorting, no error), and rows that are not <tr> children are simply not reordered. Even if it did throw, the catch only re-renders cells that are still pending; completed cells keep their values because their keys are deleted at :81-83, before sortLeaderboard runs at :84.
  **Evidence:** app/static/js/team-stats.js:36 querySelectorAll('tbody[data-metric-sort]'), :81-84, :90
- **Claim:** /api/compare stats include robot_disabled, and #team{n}-robot-disabled gets 'Full: a, Partial: b' or 'Never disabled'
  **Correction:** get_compare_stats returns robot_disabled_list, not robot_disabled. compare.js reads stats.robot_disabled, which never exists, so the card always shows 'Never disabled' (an existing bug). A rebuild should not be tested against the Full/Partial output; fixing it means compare.js:131 has to read robot_disabled_list.
  **Evidence:** app/scout/scouting_utils.py:497 "robot_disabled_list": {"$push": "$robot_disabled"}; app/static/js/compare.js:131 teamData.stats?.robot_disabled
- **Claim:** All five pages use the same horizontally scrolling btn-sm nav pattern (about 30px tap targets)
  **Correction:** Only leaderboard, lighthouse and auton use the overflow-x-auto btn-sm strip. Scouter-leaderboard has a single .btn 'Back to scouting' (about 36px) in 'flex items-center gap-2'. The mock page nav is 'flex gap-2' with two btn-sm links and no overflow-x-auto.
  **Evidence:** app/templates/scouting/scouter-leaderboard.html:13-19; app/templates/scouting/mock-alliance-selection.html:9-12; versus leaderboard.html:11, lighthouse.html:96, auton.html:23
- **Claim:** Fix the mock notification icons by making createSVGElement use createElementNS
  **Correction:** That fix is incomplete. createSVGElement also does svg.className = className. On a real SVGElement, className is a read-only SVGAnimatedString, so in this non-strict script the assignment is silently dropped and the icon renders with no h-5 w-5 sizing (the default 300x150 box), which breaks the toast layout. It must also switch to setAttribute('class', className).
  **Evidence:** app/static/js/mock-alliance-selection.js:203-210 (svg.className = className at :205); used by :187 and :223
- **Claim:** .loading-spinner is also used by offline.html
  **Correction:** offline.html uses id="loading-spinner" with class "loading". The .loading-spinner class appears only in leaderboard.html and _match_list.html.
  **Evidence:** app/templates/offline.html:364, :377

### Tests touching markup
- None of the tests assert on HTML, selectors or markup of these five templates.
- tests/test_route_logging.py:56 patches app.scout.routes.leaderboards.render_template to return 'ok'. :76-77 request /leaderboard and /scouter-leaderboard and assert only on log lines ('Fetched leaderboard: 1 teams', 'Fetched scouter leaderboard: 1 scouters'), so template changes cannot break them. Template-variable renames in leaderboards.py would not be caught either.
- tests/test_route_logging.py:78 and :80 hit the JSON APIs /api/compare?team1=1&team2=2 and /api/team_paths?team=334 that compare.js and auton.js consume (log assertions only; the JSON shape is not asserted).
- tests/test_scouting_performance.py:122-156 and :256 exercise POST /api/team_epa_opr (the {teams:[{team_number,event_code}], year} contract and the 400 on bad input) that team-stats.js:65-72 consumes.
- tests/test_browser_resilience.js:6-50 run app/static/js/service-worker.js in a VM (navigation is never cached; API polling goes to the network). The cache-first STATIC_ASSETS list (tailwind.css, team-stats.js, Canvas.js) is not asserted, but the cache-bump requirement stems from it.
- No Playwright or browser specs exist: the latest commit only adds .playwright/cli.config.json. A rebuild of these pages has no automated UI coverage, so manual or e2e checks are needed for: leaderboard EPA sort and rank renumbering, lighthouse compare plus modal canvas, auton search/add/reorder/remove/clear, and the mock selection draft (tap, drag, touch), complete, bracket and both exports.

### app/templates/scouting/leaderboard.html

**Purpose:** Team leaderboard: one row per team with scouted averages (fuel by phase, climb %, defense/herd/ferrying ratings, disabled counts) plus EPA/OPR/DPR/CCWM loaded asynchronously from TBA/Statbotics; event filter and rank-by selector.

**Routes:** GET /leaderboard -> scouting.leaderboard (app/scout/routes/leaderboards.py:17-49, login_required). Reads query args sort (default 'fuel') and event (default 'all') at leaderboards.py:21-22; TBA metric sorts (epa/opr/dpr/ccwm, leaderboards.py:14) are pre-sorted server-side (31-42). Context: teams, current_sort, events (list of {_id, event_name, count} from scouting_utils.py:568-578), selected_event. Fetches: team-stats.js:65 POST /api/team_epa_opr (app/scout/routes/events.py:151-179) with {teams:[{team_number,event_code|null}]}, polled every 2s up to 90s. Navigation: inline changeRanking/changeEvent set window.location to url_for('scouting.leaderboard')?sort=..&event=.. (leaderboard.html:286-296).

**Extends/includes:** extends base.html; only block content (no title block, so tab title is 'Castle'). Loads app/static/js/team-stats.js at leaderboard.html:307.

**JS:** inline <script> leaderboard.html:285-306 (changeRanking, changeEvent globals; dead window.onload for [data-progress-value]); app/static/js/team-stats.js (shared with scouting/list.html:89 via scout/list.js:47 loadTeamStats(container) and scouting/_match_list.html:56-64)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `#eventSelect` | id | leaderboard.html:24 (onchange=changeEvent(this.value)), leaderboard.html:288 (getElementById('eventSelect').value in changeRanking) | A <select id="eventSelect"> whose change navigates immediately (no submit button). Option values: 'all' plus each event._id; selected when equal to selected_event. Label text may use event.event_name. |
| `#rankingSelect` | id | leaderboard.html:42 (onchange=changeRanking(this.value)), leaderboard.html:294 | A <select id="rankingSelect"> with option values exactly: fuel, auto_fuel, ferried_fuel, auto_climb, climb, climb_l1, climb_l2, climb_l3, epa, opr, dpr, ccwm, defense, herd_rating, ferrying_rating (these must match LEADERBOARD_SORT_FIELDS in app/scout/scouting_utils.py:40-52 plus TBA_METRICS in leaderboards.py:14). Selected option = current_sort. |
| `changeRanking / changeEvent (global functions)` | other | leaderboard.html:286-296 called by inline onchange at :24 and :42 | Both must stay global (or be replaced by equivalent listeners) and build ?sort=<encoded>&event=<encoded> against url_for('scouting.leaderboard'); query param names sort and event are read by leaderboards.py:21-22. |
| `tbody[data-metric-sort]` | data-attr | app/static/js/team-stats.js:36-37 (querySelectorAll('tbody[data-metric-sort]')), team-stats.js:33 (cell.closest('tbody')?.dataset.metricSort) | A real <tbody data-metric-sort="{{ current_sort }}"> inside a real <table>. The .team-stats-cell elements must be descendants of this tbody. If it is a div or the attribute is lost, EPA/OPR/DPR/CCWM sorting stops. |
| `tbody.rows / <tr> rows` | structure | team-stats.js:39 ([...body.rows]), team-stats.js:48 (body.append(...rows)) | Each team must be one <tr> that is a direct child of that tbody (HTMLTableSectionElement.rows is table-only; a non-table element makes [...undefined] throw, which the catch at team-stats.js:87-91 turns into N/A for every metric). Rows are physically reordered by JS for epa/opr/dpr/ccwm, so any per-team phone card markup outside the row would not be reordered. |
| `tr > td:first-child (row.cells[0]) rank cell` | structure | team-stats.js:49-51 (row.cells[0].textContent = index + 1) | The first <td> of each row must be the rank and contain only the rank text. JS overwrites its textContent after re-sorting, so any badge/span markup inside it is wiped. Style the td itself, and keep the rank as cell 0 even in a phone card layout. |
| `.team-stats-cell[data-team-id][data-event-id]` | class | team-stats.js:3 (querySelectorAll), :8-12 (dataset.teamId/eventId build the request and the key `${team}_${event}` or `${team}`), :42 (row.querySelector('.team-stats-cell')?.dataset.metricValue) | Exactly one element with class team-stats-cell per row. data-team-id = team.team_number. data-event-id = selected_event, or '' when 'all' (leaderboard.html:168). JS writes data-stats-started and data-metric-value onto it, so do not reuse those attribute names. |
| `.epa-value .opr-value .dpr-value .ccwm-value` | class | team-stats.js:27 (cell.querySelector(`.${metric}-value`)), team-stats.js:30-31 (textContent = 'EPA: 12.3' | 'EPA: Loading…' | 'EPA: N/A') | Four elements inside .team-stats-cell with exactly these classes. Their whole textContent (label and value, plus the spinner) is replaced, so a separate number span for the Oxanium font would be wiped unless team-stats.js changes. Also used by _match_list.html:61-64. |
| `.loading-spinner` | css-hook | leaderboard.html:171-174 (placeholder only; removed by the textContent replacement at team-stats.js:30); also offline.html and _match_list.html:61-64 | Optional placeholder inside each *-value span. Not queried by JS on this page. |
| `hl / hl_th Jinja class strings` | jinja-context | leaderboard.html:2-3, applied at :104-150 (th) and :171-174, :182-270 (td/spans) | Highlighting of the active sort column. The classes are literal strings in the template, so Tailwind scans them. Keep the conditional mapping current_sort -> column (epa/opr/dpr/ccwm -> EPA cell; climb, climb_l1-3 -> Climb stats; and so on). |
| `Jinja team fields` | jinja-context | leaderboard.html:157-272 | teams[*]: team_number, matches_played, auto_fuel, auto_climb_pct, transition_fuel, ferried_fuel, teleop_fuel_total, endgame_fuel, total_fuel, defense_rating, herd_count, herd_rating, ferrying_count, ferrying_rating, robot_disabled_list (counts of 'Full' and 'Partially'), climb_l1_pct, climb_l2_pct, climb_l3_pct, climb_success_rate. The "%.1f"|format filters assume numbers. Keep the {% else %} empty state. |
| `script include js/team-stats.js` | other | leaderboard.html:307; team-stats.js:96 (DOMContentLoaded) and :97-99 (pageshow persisted -> reload) | Must load on this page. Placement is flexible because of DOMContentLoaded. The file is cache-first in the service worker (service-worker.js:16), so a change to it needs a cache bump. |
| `[data-progress-value]` | data-attr | leaderboard.html:299-304 (window.onload sets style.width) | Dead: no element carries it. Safe to drop, together with the window.onload assignment. |
| `tbody[data-metric-sort] must contain only team <tr> rows` | (missed, verified) | team-stats.js:39-51 sorts every row in body.rows, re-appends them, and writes index+1 into row.cells[0] of each one | Do not put auxiliary rows (phone-only detail or expand rows, group headers, spacer rows) inside this tbody. On EPA/OPR/DPR/CCWM sorts they would be moved to the bottom (or the top for DPR, where the missing value is read as Infinity), given a rank number, and would shift every real rank. Put extra rows in a separate tbody without data-metric-sort, or keep detail inside the team row's cells. |

#### JS-generated markup
- team-stats.js:30-31 sets textContent of .epa/.opr/.dpr/.ccwm-value to 'EPA: x.x', 'Loading…' or 'N/A'; the spinner and any inner markup disappear
- team-stats.js:48-51 reorders <tr> rows and rewrites the rank cell text for TBA metric sorts

#### Hard-coded colours
- leaderboard.html:2 hl = 'font-semibold !text-blue-600 dark:!text-blue-400' (sorted-column accent; must move to new blue #0b5fb0/#2f7ae0)
- leaderboard.html:171-174 spinner border-zinc-300
- leaderboard.html:256-260 badge-red/badge-amber/badge-gray/badge-green for disabled status (tailwind.input.css:94-108)

#### Legacy CSS
- None page-specific. Uses Tailwind component classes from app/static/css/tailwind.input.css: page-header, page-title, page-subtitle, label, input, help, table-wrap, table, badge, badge-red/amber/gray/green, btn btn-secondary btn-sm.
- app/static/css/global.css (loaded for every page by base.html:36).

#### Phone problems at 390px
- 16-column table (leaderboard.html:100-154) inside .table-wrap overflow-x-auto. Every td and th is whitespace-nowrap (tailwind.input.css:117-122), so the table is roughly 1800-2000px wide at 390px and needs heavy horizontal scrolling. The rank and team columns are not sticky, so you lose which team a row is.
- EPA cell uses a fixed grid-cols-[6.25rem_6.75rem] (leaderboard.html:170), so that cell alone is about 13rem wide.
- Header sublabels and stat grids are text-xs (12px); Climb stats is a 2x2 grid of 12px text (266-271).
- Scouting-tools nav buttons are btn-sm (px-2.5 py-1.5 text-xs, about 30px tall), under 44px, in a horizontally scrolling strip (leaderboard.html:11-16) with no scroll affordance.
- Selects are .input (py-2 text-base, about 42px), slightly under 44-48px.
- Empty-state colspan=17 but there are 16 columns (leaderboard.html:276).
- There is no card layout. A card rebuild must keep the <table>/<tbody>/<tr>/cells[0] structure that team-stats.js depends on (see hooks).

#### Redesign notes
Keep a real <table> with <tbody data-metric-sort>. For phones, turn rows into cards with CSS (display:block or grid on tr/td, labels via a data-label attribute and ::before) rather than separate div markup. Otherwise generalize team-stats.js sortLeaderboard: today it only reorders tbody.rows and rewrites cells[0], and it is shared with list.html/_match_list.html. The rank must stay the first td and be plain text. The Oxanium number font can go on whole cells or spans; for the EPA spans, the label text is part of the JS-written string. Filters navigate on change (no submit), so a sticky save bar is not needed here. Drop the dead data-progress-value window.onload. Fix colspan. All class names are Jinja literals (hl/hl_th, badge-*), so no safelist is needed. Add a {% block title %}. The service worker caches team-stats.js and tailwind.css cache-first, so bump STATIC_CACHE_NAME/CACHE_VERSION (service-worker.js:1-6).

### app/templates/scouting/scouter-leaderboard.html

**Purpose:** Scouter leaderboard: filters (sort, event, scouter team), three achievement cards (most dedicated, team spirit, data collector) and a ranked table of scouts with matches scouted and unique teams.

**Routes:** GET /scouter-leaderboard -> scouting.scouter_leaderboard (app/scout/routes/leaderboards.py:52-86, login_required). Query args sort (match_count|unique_teams, mapped by SCOUTER_SORT_FIELDS scouting_utils.py:53-56), event, team. Context: scouters (list of {_id, username, teamNumber, match_count, unique_teams_count}), current_sort, events (list of event-code strings), selected_event, teams (list of team numbers), selected_team. Images: GET auth.profile_picture(user_id).

**Extends/includes:** extends base.html; block title 'Scouter Leaderboard' and block content.

**JS:** inline <script> scouter-leaderboard.html:177-184 (auto-submit #leaderboardForm on any select change)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `form#leaderboardForm` | id | scouter-leaderboard.html:179 (querySelectorAll('#leaderboardForm select')) and :181 (getElementById('leaderboardForm').submit()) | A <form id="leaderboardForm" method="GET" action="{{ url_for('scouting.scouter_leaderboard') }}">. All three filter controls must be <select> descendants of it. There is no submit button, so the change-to-submit listener is the only way filters apply (or add a visible submit as well). |
| `select[name=sort]#sort` | form-field-name | leaderboards.py:56 request.args.get('sort') | name="sort", values match_count and unique_teams, selected = current_sort. |
| `select[name=event]#event` | form-field-name | leaderboards.py:57 request.args.get('event') | name="event", first option value 'all', then each event string. selected when selected_event == event. |
| `select[name=team]#team` | form-field-name | leaderboards.py:58 request.args.get('team') | name="team", first option 'all', then team numbers. The selected comparison is string-to-string (selected_team|string == team|string) at scouter-leaderboard.html:52. |
| `achievement Jinja logic` | jinja-context | scouter-leaderboard.html:60-123 (namespace max_team_scouts 78-83, max_teams_scout 101-107) | Keep the computations: Most dedicated = scouters[0]; Team spirit = scouters sharing the first teamNumber; Data collector = max unique_teams_count. Guards: {% if scouters %} and |length checks. |
| `img src=url_for('auth.profile_picture', user_id=...)` | jinja-context | scouter-leaderboard.html:68 and :150 | Avatar URLs use scouter._id. Keep alt="" (decorative). |
| `table rows loop.index rank badges` | jinja-context | scouter-leaderboard.html:139-163 | Rank 1 = badge-blue, ranks 2-3 = badge-gray, others plain text. No JS reads the table. |
| `inline auto-submit script (scouter-leaderboard.html:177-184) placement, and no control named or with id 'submit' inside #leaderboardForm` | (missed, verified) | scouter-leaderboard.html:179 runs querySelectorAll('#leaderboardForm select') at parse time, not on DOMContentLoaded; :181 calls form.submit() | The script must come after the form markup, or be wrapped in DOMContentLoaded. A control with name or id 'submit' in the form would shadow form.submit() and throw a TypeError. Any new <select> added to the form also auto-submits. |

#### Hard-coded colours
- scouter-leaderboard.html:143 rank-1 badge-blue (accent)
- scouter-leaderboard.html:68 ring-zinc-200/700 avatar ring; :86,:109 bg-zinc-100 icon circles

#### Legacy CSS
- None page-specific; Tailwind components (page-header, section-title, card, card-body, label, input, table-wrap, table, badge, badge-blue/gray, btn btn-secondary). global.css via base.

#### Phone problems at 390px
- The 5-column table (Rank w-16, Scout with avatar, Team badge, 'Matches scouted', 'Unique teams' as nowrap headers) is about 480-520px wide at 390px, so it scrolls horizontally inside .table-wrap and long usernames are not truncated. It should become cards.
- Empty-state colspan=6 but there are 5 columns (scouter-leaderboard.html:167).
- The 'Back to scouting' .btn is about 36px tall (py-2 text-sm), under 44px.
- Selects stack in 1 column (fine) but are about 42px tall.

#### Redesign notes
This page has no JS markup dependency other than the form auto-submit. Keep the form id/method/action and the select names. A table-to-card conversion is free here. Keep the achievements logic and the image endpoint. Fix colspan.

### app/templates/lighthouse.html

**Purpose:** Team comparison: enter 2-3 team numbers, then JS fetches /api/compare and fills per-team stat cards, a Chart.js radar chart, an 'Auto paths' card (latest 5 paths per team), a raw-data table, and a modal that draws an auto path on a read-only field canvas.

**Routes:** GET /lighthouse -> scouting.lighthouse (app/scout/routes/lighthouse.py:16-20, login_required, no template context). Fetch: compare.js:49 GET /api/compare?team1=&team2=[&team3=] (lighthouse.py:30-94). Returns json_util dumps of {"<team>": {team_number, nickname, city, state_prov, country, stats{avg_*_fuel, climb_success_rate, climb_level_N_count, matches_played, defense_rating, defense_notes[], robot_disabled}, normalized_stats{auto_scoring, teleop_scoring, endgame_scoring, climb_level, climb_rating, defense_rating}, matches[]}} or {error}. Modal canvas loads /static/images/field-2026.png (compare.js:346). Active-nav: base.html:75 compare_active for scouting.lighthouse and scouting.auton.

**Extends/includes:** extends base.html. Block head (lighthouse.html:2-6) loads localforage from an unpinned GitHub CDN, plus css/coloris.css and js/coloris.js (unused on this page). Macros stat_row (9-14) and team_card (16-86) are defined inside block content.

**JS:** https://cdn.jsdelivr.net/gh/localforage/localforage/dist/localforage.min.js (head, lighthouse.html:3; required by Canvas.js:112); app/static/js/coloris.js (lighthouse.html:5; unused); app/static/js/Canvas.js (lighthouse.html:247); https://cdn.jsdelivr.net/npm/chart.js (defer, unpinned, lighthouse.html:248); app/static/js/compare.js (lighthouse.html:249; runs top-level DOM lookups at parse time); app/static/js/radar.js (lighthouse.html:250; dead code, see notes)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `#team1-input #team2-input #team3-input` | id | compare.js:15-17 (top-level getElementById at parse time), :26-28 (keypress Enter -> handleCompare), :37-39 (.value.trim()) | Three inputs with these ids that exist before compare.js executes (the script tag must come after this markup and must not be in <head> without defer). Teams 1 and 2 are required (alert at compare.js:41-44). type=number, inputmode=numeric. |
| `#compare-btn` | id | compare.js:18, :25 (addEventListener('click', handleCompare) at top level) | Must exist at parse time. If it is missing, compare.js throws on line 25 and the whole page is dead. type=button (it is not in a form). |
| `#comparison-results` | id | compare.js:19, :60 (classList.remove('hidden')) | Results wrapper that starts with class 'hidden' and contains the cards, auto paths, chart and raw table. |
| `#team1-info #team2-info #team3-info` | id | compare.js:85-92 (getElementById(`team${n}-info`), classList.remove('hidden')), compare.js:144-148 (team3 gets 'hidden' when fewer than 3 teams) | Three card roots. The 'hidden' class is toggled by JS. team3 starts hidden (team_card(3,...,True) at lighthouse.html:160). Card N is filled in Object.entries order, which JS orders numerically by team number (integer-like keys), not input order. |
| `#team{n}-header #team{n}-number-name #team{n}-location` | id | compare.js:95-98 (textContent) | Elements per card (n=1..3) for 'Team 334', the nickname and the city/state/country. There are no null checks: a missing id throws and aborts the update (caught at compare.js:62-65, which shows an alert). |
| `#team{n}-auto-fuel #team{n}-transition-fuel #team{n}-ferried-fuel #team{n}-teleop-s1..s4 #team{n}-endgame-fuel #team{n}-climb-success` | id | compare.js:103-115 (textContent = number.toFixed(2) or toFixed(1)); generated by stat_row macro lighthouse.html:12 | Value-only <span id> elements (the suffixes ' avg' and '%' sit outside the span in the template, lighthouse.html:12). All 10 ids per card must exist; no null checks. |
| `#team{n}-preferred-climb #team{n}-defense #team{n}-defense-notes #team{n}-robot-disabled` | id | compare.js:121, :124, :128, :140 (textContent) | preferred-climb gets 'L1: x% | L2: y% | L3: z%'; defense gets 'x.x/5'; defense-notes gets the first note or 'No defense notes available'; robot-disabled gets 'Full: a, Partial: b' or 'Never disabled'. All required. |
| `#radarChart` | id | compare.js:153 (getElementById), :194 (new Chart(canvas.getContext('2d'), {type:'radar', maintainAspectRatio:false})) | A <canvas id="radarChart"> whose parent has an explicit height (lighthouse.html:179 h-[360px] sm:h-[480px]), because maintainAspectRatio is false. |
| `#raw-data-tbody and its thead` | structure | compare.js:260-321 (tbody.innerHTML='' then appends <tr class='tabular-nums'> with 13 <td>) | A <tbody id="raw-data-tbody"> inside a <table>. The thead column order (lighthouse.html:194-208) must match the generated td order: Team, Alliance, Match, Auto fuel, Transition fuel, Ferried fuel, Teleop shifts 1-4, Endgame fuel, Climb, Auto path, Defense, Notes, Scouter. A phone card version means rewriting compare.js:272-316. |
| `#auto-paths-container` | id | compare.js:414-434 (innerHTML replaced with a .card; then autoPathsContainer.querySelector('.grid')) | Container id must exist. Its static children #auto-path-team1/2/3-container (lighthouse.html:165-170) are wiped (dead markup). The generated markup must keep an element with class 'grid' (compare.js:429/434) or the selector must change to #auto-paths-grid. |
| `.auto-path-button` | class | compare.js:304, :317 (raw table 'View'), :491, :499 (auto paths table 'View path') | Generated <button type=button class='link auto-path-button'>. Click listeners are attached by querySelector on each row. These are text links about 20px tall. |
| `#autoPathModal` | id | compare.js:332, :340 (remove 'hidden'), :394-396 (add 'hidden'), :402-408 (click where e.target === modal closes) | The modal root is the full-viewport backdrop and the card is its child (a backdrop click closes only when the root itself is clicked). 'hidden' is toggled on an element that also has 'flex' (lighthouse.html:220), which relies on .hidden coming after .flex in Tailwind output. The id is also used on scouting/list.html with scout/list.js (a separate page). |
| `closeAutoPathModal() global` | other | lighthouse.html:224 inline onclick; defined compare.js:393-398 | The close button calls the global function. Keep the function global or wire a listener. |
| `#autoPathContainer` | id | compare.js:333, :345 (Canvas container); Canvas.js:170-196 (getBoundingClientRect sizing), Canvas.js:1051 (wheel zoom on container) | Must have an explicit non-zero height (h-[400px], lighthouse.html:232) and be displayed BEFORE new Canvas() runs (compare.js:340 un-hides, then :343 constructs). A modal open animation or <dialog> that delays display gives a 0-size canvas. overflow-hidden. |
| `#modalAutoPathCanvas` | id | compare.js:344 | A <canvas> inside #autoPathContainer (h-full w-full); Canvas.js sets its pixel size and style width/height. |
| `#modalAutoNotes` | id | compare.js:334, :388-390 (textContent) | Text element for the auto notes. |
| `html.dark` | other | compare.js:162 (classList.contains('dark')), compare.js:237-246 (MutationObserver on documentElement attributes, redraws the chart on class change) | Dark mode must stay a 'dark' class on <html> (tailwind darkMode 'class', base.html:29-32, 220-221) so the chart re-themes. |
| `script order: localforage -> Canvas.js -> compare.js; Chart global` | other | Canvas.js:112 (localforage.createInstance in the constructor), compare.js:343 (new Canvas), compare.js:194 (Chart) | localforage must be loaded before any Canvas is constructed. Canvas.js must load before a path is viewed. Chart.js may be deferred because it is only used after a click. compare.js must run after the DOM above it exists. |
| `team colour dots bg-blue-600 / bg-amber-500 / bg-teal-500` | jinja-context | lighthouse.html:154,157,160 (team_card dot param) mirrored by compare.js:325-329 getTeamColor ['#2563eb','#f59e0b','#14b8a6'] (radar datasets and auto-path headers) | Card N dot colour must equal getTeamColor(N-1). Change both together when moving to the new palette. |
| `compare.js must execute before DOMContentLoaded` | (missed, verified) | compare.js:401-410 attaches the #autoPathModal backdrop-click listener inside a DOMContentLoaded handler | Load compare.js as a classic script at the end of the content block, or with defer or type=module. If it is loaded async or injected late, the backdrop-click close is never wired. |

#### JS-generated markup
- compare.js:92, :147 toggle 'hidden' on #team{n}-info; :60 on #comparison-results
- compare.js:95-140 textContent of every stat id (numbers; Oxanium can go on these value-only spans)
- compare.js:162-166 chart theme colours by html.dark; :170-192 datasets with borderColor/backgroundColor `${color}33` (needs 6-digit hex)
- compare.js:259-321 raw data rows (innerHTML; classes tabular-nums, font-semibold !text-zinc-900 dark:!text-zinc-100, badge badge-red/badge-blue for alliance, link auto-path-button, text-zinc-400 'None', max-w-xs truncate notes)
- compare.js:412-513 Auto paths card (card, card-header, section-title, card-body grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3 #auto-paths-grid; per-team h4 with inline style dot `background:${getTeamColor(index)}` at :442; dashed empty box :460; .table inside 'overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800' wrapper :505-507; '!whitespace-normal' notes cell :495)
- compare.js:331-391 showAutoPath constructs a new Canvas on every open (adds window resize/keydown and container wheel listeners each time; old instances also redraw on wheel)
- radar.js:38-141 createRadarChart/updateRadarCharts target canvas 'radar-chart-combined' which does not exist and is never called (dead code)

#### Hard-coded colours
- compare.js:163-166 textColor '#a1a1aa'/'#52525b', gridColor '#27272a'/'#e4e4e7', angleLineColor '#3f3f46'/'#d4d4d8', pointBorderColor '#18181b'/'#fff' (dark/light)
- compare.js:184 backgroundColor `${color}33` alpha suffix
- compare.js:327 team colours ['#2563eb','#f59e0b','#14b8a6']
- compare.js:442 inline style background:${getTeamColor(index)}
- compare.js:278 alliance badge-red / badge-blue
- radar.js:13 'rgba(0, 0, 0, 0.1)'; radar.js:52-79 rgba(37,99,235,..), rgb(245,158,11), '#fff' (dead code)
- lighthouse.html:154-160 dot classes bg-blue-600 / bg-amber-500 / bg-teal-500
- lighthouse.html:220 modal backdrop bg-zinc-950/50
- Canvas.js:80-81 grid '#e0e0e0', axis '#a0a0a0'; :84 default stroke '#000000'; :260,:501,:540,:911,:2351 '#0066ff' selection; :282,:430,:949,:2350 '#ffffff' (not dark-aware)

#### Legacy CSS
- app/static/css/coloris.css (loaded at lighthouse.html:4 but unused; no data-coloris input on this page)
- global.css via base

#### Phone problems at 390px
- Raw scouting data table has 13 nowrap columns (lighthouse.html:194-208) plus notes 'max-w-xs truncate' (compare.js:310). At 390px it scrolls horizontally for well over 1000px and long notes cannot be read.
- Auto paths tables (compare.js:464-509) sit in an overflow-x-auto wrapper; 'View path' is a text link about 20px tall (under 44px).
- The raw-table 'View' button (compare.js:304) is a small text link.
- The modal close button is btn btn-ghost btn-icon (p-2 + 20px icon, about 36px, lighthouse.html:224), under 44px. There is no Escape key handling and no role=dialog or focus management.
- The modal canvas is a fixed 400px tall inside a p-4 backdrop; the landscape field image is letterboxed at 358px width. The hint 'Shift+drag or middle mouse / scroll wheel' (lighthouse.html:235-237) is desktop-only: read-only touch allows only two-finger pan (Canvas.js:1416-1418) and there is no pinch zoom.
- The radar chart (360px tall) has 6 point labels at the default 12px font that crowd at 358px width. The resize handler meant to shrink fonts is dead (compare.js:250-257 reads window.radarChart, which is undefined because radarChart is a top-level let).
- Nav buttons are btn-sm (about 30px tall) in a horizontal scroll strip (lighthouse.html:96-102).
- Errors are shown with alert() (compare.js:42,55,64).

#### Redesign notes
Keep every id listed. compare.js writes through getElementById without null checks, so dropping one id breaks the whole comparison. Keep the stat_row value-only spans so Oxanium can target numbers. Card order follows numeric team order (Object.entries on integer keys), not the Team 1/2/3 inputs, so do not tie input labels to dot colours. If the raw table becomes cards on phones, rewrite compare.js updateRawDataTable and the thead together. Keep the modal pattern: un-hide, then construct Canvas, with a fixed-height container. Move chart colours to the new tokens (dark: #0b0f17/#141a26/#1f2838, blue #2f7ae0) in compare.js:163-166 and getTeamColor plus the dot classes. Remove the unused coloris assets, dead radar.js and the dead #auto-path-team{n}-container divs if desired. Pin Chart.js and localforage versions. No runtime-concatenated Tailwind classes: all are literal strings in compare.js, which Tailwind content scans (tailwind.config.js:5).

### app/templates/lighthouse/auton.html

**Purpose:** Auto path comparison: search a team, list its scouted autonomous paths, add up to 6 (max 3 per alliance) onto one read-only field canvas with per-path colours; reorder by drag (Sortable), remove, clear, and reset/flip/rotate the field view.

**Routes:** GET /lighthouse/auton -> scouting.auton (app/scout/routes/lighthouse.py:23-27, login_required, no context). Fetch: auton.js:192 GET /api/team_paths?team=<n> (lighthouse.py:150-185) -> {team_number, team_info{nickname, city, state_prov, country}, paths:[{_id, team_number, match_number, event_code, event_name, alliance, auto_path, auto_notes}]}. The canvas loads /static/images/field-2026.png (auton.js:131).

**Extends/includes:** extends base.html. Block head (auton.html:1-14) contains a <title> tag (duplicate, ignored because base.html:25 comes first), a link to css/styles.css (file does not exist, 404), Sortable from cdn.jsdelivr.net/npm/sortablejs@latest (unpinned), localforage from a GitHub CDN (unpinned), and css/auton.css.

**JS:** https://cdn.jsdelivr.net/npm/sortablejs@latest/Sortable.min.js (auton.html:8); https://cdn.jsdelivr.net/gh/localforage/localforage/dist/localforage.min.js (auton.html:9); app/static/js/Canvas.js (auton.html:274); app/static/js/lighthouse/auton.js (auton.html:275; wires everything in DOMContentLoaded)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `Sortable global` | other | auton.js:45-49 (Sortable.create(#selected-paths, {animation:150, ghostClass:'opacity-50', onEnd:updatePathOrder})) | Sortable must be loaded before DOMContentLoaded. If it is missing, line 45 throws inside the DOMContentLoaded handler before the search, reset, clear, flip and rotate listeners (lines 52-97) are attached, and the page is dead. Pin a version. |
| `localforage global` | other | Canvas.js:112 (localforage.createInstance in the constructor called at auton.js:128) | Must load before Canvas is constructed, otherwise initCanvas catches the error and shows an alert (auton.js:140-143). |
| `#team-search` | id | auton.js:31, :53-57 (keypress Enter -> searchTeam), :180 (.value.trim()) | Text input (inputmode numeric) for the team number. |
| `#search-btn` | id | auton.js:32, :52 (click), :181, :190 (innerHTML = spinner span 'border-white/40 border-t-white'), :236 (textContent = 'Search') | A button whose content is fully replaced with a spinner and then the plain text 'Search', so any icon inside is lost after the first search. The spinner colour assumes a primary (filled) button. |
| `#search-results` | id | auton.js:247, :270 (classList.remove('hidden')) | Wrapper that starts with 'hidden' and contains #team-name, #team-info, #path-count-available and #available-paths. |
| `#team-name #team-info` | id | auton.js:248-249, :261 (textContent 'Team N - Nickname'), :267 (location or 'Location unknown') | Text targets; required (the function returns early if either is missing). |
| `#path-count-available` | id | auton.js:276, :287 (textContent '(n)') | Count element. |
| `#available-paths > #no-paths-message` | structure | auton.js:275, :280-284 (removes every child except id 'no-paths-message'), :291/:294 (toggle 'hidden' on the message), :324 (appendChild cards), :329-332 (scroll hint) | #no-paths-message must be a direct child of #available-paths. Any other static child placed inside #available-paths is deleted on every search. The container scrolls (max-h-80 overflow-y-auto). |
| `.path-card / .add-path-btn / data-index` | class | auton.js:300-301 (card.className='path-card', dataset.index), :313 and :320 (querySelector('.add-path-btn') click -> addPathToSelection(index)); styled by auton.css:2-34 | Generated available-path cards. Their styling lives only in auton.css (or must be ported). .path-card.selected exists in CSS but JS never sets it. |
| `#canvas-container` | id | auton.js:103, :129 (Canvas container); Canvas.js:170-196 (getBoundingClientRect), Canvas.js:1051 (wheel zoom) | Must have an explicit non-zero height at DOMContentLoaded (inline style height:400px at auton.html:103) plus position relative and overflow hidden. The canvas resizes to the container on window resize (auton.js:163-171). |
| `#pathCanvas` | id | auton.js:104, :129 | A <canvas> absolutely filling #canvas-container (auton.html:105-108). |
| `#reset-view-btn #flip-horizontal-btn #flip-vertical-btn #rotate-cw-btn #rotate-ccw-btn #clear-all-btn` | id | auton.js:33-38, :58-63, :64, :67-97 | Six buttons with these ids. reset-view calls resizeCanvas, resetView and redrawCanvas; clear-all asks confirm() then empties the selection (auton.js:601-612). Keep aria-labels. |
| `.tool-btn .tool-btn-danger` | css-hook | auton.css:87-131 (40x40 buttons, danger colour) | Styling only (not JS). Port it to new tokens and enlarge to 48px. |
| `#path-count` | id | auton.js:393, :396 (textContent = selectedPaths.length) | Count span (shown as n/6). |
| `#selected-paths (Sortable container) > #empty-prompt + .selected-path-card` | structure | auton.js:39, :45 (Sortable root), :391, :406-409 (removes .selected-path-card children), :449 (appends cards), :463-469 updatePathOrder(evt.oldIndex/newIndex) | The Sortable root must contain the selected cards as direct children. #empty-prompt is currently also a direct child and comes first, so Sortable's evt.oldIndex/newIndex are offset by 1 relative to selectedPaths (an existing reorder bug). Moving #empty-prompt out of #selected-paths, or passing draggable:'.selected-path-card', fixes that deliberately. The .draggable-container class gives the dashed drop zone (auton.css:35-43). |
| `#empty-prompt` | id | auton.js:392, :400/:402 (toggle 'hidden') | Empty-state element whose 'hidden' class is toggled. |
| `.selected-path-card[data-id] .color-indicator .remove-path` | class | auton.js:406-407 (querySelectorAll('.selected-path-card')), :414-415, :423 (inline style background-color: path.color), :441 and :445 (span.remove-path click -> removePath(index)); auton.css:48-86 | Generated selected cards. The remove control is a <span role=button> with no tabindex, 28px, keyboard-inaccessible. removePath uses the index captured at render time; after a drag the cards are not re-rendered, so the indices go stale (existing bug). |
| `opacity-50 (Sortable ghostClass)` | class | auton.js:47 | A Tailwind class applied by Sortable while dragging. It is a literal in a JS file, so content scanning covers it. |

#### JS-generated markup
- auton.js:190 search button spinner innerHTML ('inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white')
- auton.js:299-317 available path card: 'path-card' plus inner 'text-sm font-medium', alliance badge 'badge badge-red|badge-blue|badge-gray capitalize' (:308), 'truncate text-xs text-zinc-500 dark:text-zinc-400' event name, auto notes 'mt-1 text-xs text-zinc-600 dark:text-zinc-300', add button 'add-path-btn btn btn-secondary btn-sm'
- auton.js:329-332 scroll hint 'mt-2 text-center text-xs text-zinc-400 dark:text-zinc-500'
- auton.js:413-442 selected card 'selected-path-card path-card flex items-center' with span.color-indicator inline background-color, 'break-words text-sm font-medium' title, event code plus badge (badge-red/blue/gray), span.remove-path '×'
- auton.js:472-598 drawPaths overwrites each stroke's colour with path.color (TEAM_COLORS)

#### Hard-coded colours
- auton.js:13-20 TEAM_COLORS ['#2563eb','#f59e0b','#14b8a6','#8b5cf6','#ec4899','#65a30d'] (path stroke colours plus colour dots)
- auton.js:423 inline style background-color from TEAM_COLORS
- auton.js:308, :430-436 alliance badge-red / badge-blue
- auton.css:3,7,8,16,17,20,21,24-26,29-30,33,36,42,67,71-72,75-76,93-95,101-102,105-107,110-111,121,124,127,130 hex/rgba colours (zinc-200/300/700/900, blue-600 #2563eb, blue-50 #eff6ff, red-600 #dc2626, red-50 #fef2f2, #3b82f61a, #ef44441a)
- auton.html:227 divider bg-zinc-200 dark:bg-zinc-800
- Canvas.js:80-81, :84, '#0066ff', '#ffffff' (field grid, axis and selection colours; not dark-aware)

#### Legacy CSS
- app/static/css/auton.css (whole file: .path-card, .path-card.selected, .dark .path-card, .draggable-container, .drag-handle (unused), .selected-path-card, .remove-path, .color-indicator, .tool-btn, .tool-btn-danger, all with hex colours and .dark selectors)
- app/static/css/styles.css referenced at auton.html:3-6 but missing (404)
- global.css via base

#### Phone problems at 390px
- Tool buttons are 40x40px (auton.css:88-89), under 44/48.
- The remove control '×' is 28x28px (auton.css:61-62) and is a span with no tabindex.
- 'Add' buttons are btn-sm (about 30px tall, auton.js:313).
- Canvas container is fixed at 400px tall (auton.html:103); at 358px content width the landscape field is letterboxed with wasted vertical space. The pan/zoom hint is desktop-only: touch allows only a two-finger pan in read-only mode (Canvas.js:1416-1418), with no pinch-zoom.
- Drag-to-reorder with Sortable on touch competes with page scroll, and reorder indices are off by one because #empty-prompt sits in the container.
- The available-paths list is a nested scroll area (max-h-80) inside the page scroll.
- Nav buttons are btn-sm (about 30px tall) in a horizontal scroll strip (auton.html:23-28).
- Errors and limits use alert()/confirm() (auton.js:142,174,184,233,339,350,362,602).

#### Redesign notes
Keep all ids. Keep #no-paths-message as a direct child of #available-paths and keep #selected-paths as the Sortable root holding .selected-path-card children. Consider moving #empty-prompt out of it, which fixes the index offset. Port auton.css into Tailwind components (path-card, selected-path-card, remove-path as a real <button> of at least 44px, color-indicator, tool-btn at 48px, draggable-container) because JS emits these class names. Remove the dead styles.css link and the duplicate <title> (use block title). Pin Sortable and localforage. The container needs an explicit height before DOMContentLoaded; consider an aspect-ratio box. TEAM_COLORS should match the new palette but stay distinct from the alliance red/blue.

### app/templates/scouting/mock-alliance-selection.html

**Purpose:** Mock FRC alliance selection: pick a year, search TBA events, load rankings; then simulate captain selection and a serpentine draft into 8 alliances (tap or drag teams into slots, remove picks), export JSON, then run a clickable 16-match double-elimination playoff bracket with export.

**Routes:** GET /scouting/mock-alliance-selection -> scouting.mock_alliance_selection (app/scout/routes/events.py:108-114, login_required, limiter 30/min, no context). Fetches: mock-alliance-selection.js:327 GET /api/tba/events?year=&_=<ts> (events.py:15-34) -> {"<event name>": {key,...}} or {error}; mock-alliance-selection.js:391 GET /api/alliance-selection/rankings/<event_key> (events.py:117-148; alnum key only) -> [{rank, team_number, team_key, nickname, city, state_prov, ...}] or {error}. Exports are client-side Blob downloads (mock-alliance-selection.js:951-959, playoff-bracket.js:387-395).

**Extends/includes:** extends base.html; block content only (no title block). Contains an inline <style> block (226-373) and a <template id="match-card-template"> (184-223).

**JS:** app/static/js/mock-alliance-selection.js (mock-alliance-selection.html:374; DOMContentLoaded init; exposes window.getAlliances and global showNotification); app/static/js/playoff-bracket.js (mock-alliance-selection.html:375; globals startPlayoffBracket, exportPlayoffResults, window.getBracketMatches)

#### Hooks

| Selector | Kind | Used by | Must keep |
|---|---|---|---|
| `#year-select` | id | mock-alliance-selection.js:57, :79-85 (sets max and value to the current year), :90-92 (Enter -> loadEvents), :316 (value) | A number input. JS fills in the current year on load and validates 1992 to current year + 1. |
| `#search-events-btn` | id | mock-alliance-selection.js:62, :95-97 (click loadEvents), :314, :359-362 (disabled plus textContent 'Searching...' / 'Search events') | A button whose text is replaced while loading (an icon would be lost). |
| `#event-search-input` | id | mock-alliance-selection.js:58, :230-265 (input/focus listeners, outside-click contains()), :276, :304, :339-350 (placeholder, disabled), :364-369 | A text input that starts disabled; JS enables it after events load. Typing filters the list and clears #event-select. |
| `#event-dropdown_arrow (underscore)` | id | mock-alliance-selection.js:60, :262 (contains for outside click), :268-281 (click toggles list, stopPropagation) | Exact id with an underscore. Clickable toggle; currently a div. It can become a button but must keep the id. |
| `#event-select (hidden input)` | id | mock-alliance-selection.js:61, :237, :303, :373, :378-380 (value = selected event key used by loadRankings), playoff-bracket.js:361 (value used in the export filename/event) | <input type="hidden" id="event-select"> holding the TBA event key (not the name). |
| `#event-dropdown-list` | id | mock-alliance-selection.js:59, :243, :254, :261-263, :271-278 (toggle 'hidden'), :284-310 (innerHTML cleared, li children appended with click handlers) | A <ul> listbox, absolutely positioned under the input, that starts 'hidden'; JS fills it with <li> items (or a 'No events found' div). |
| `#load-rankings-btn` | id | mock-alliance-selection.js:63, :99-101, :378, :387-388, :412-413 (disabled, textContent 'Loading...' / 'Load rankings') | A button whose text is replaced while loading. |
| `#selection-status` | id | mock-alliance-selection.js:74, :403-405 (remove 'hidden') | Status wrapper that starts hidden. |
| `#status-text and its grandparent status box` | structure | mock-alliance-selection.js:69-70 (dom.statusBox = statusText.parentElement.parentElement), :872-907 (toggle classes on statusBox and statusText) | #status-text must sit exactly two element levels below the coloured box (now p > div.min-w-0 > div.rounded-lg.border). JS swaps on the box: bg-blue-50, border-blue-200, dark:bg-blue-500/10, dark:border-blue-500/30 <-> bg-green-50, border-green-200, dark:bg-green-500/10, dark:border-green-500/30. On the text: text-blue-800, dark:text-blue-300 <-> text-green-800, dark:text-green-300. The box must also carry 'border' for the border colour to show. The id 'status-text' also exists on offline.html (separate page). |
| `#notification-area` | id | mock-alliance-selection.js:75, :166-178 (appends role=alert toasts and auto-removes after 5s), playoff-bracket.js:398 (via showNotification) | Container for notifications. 'empty:mb-0' never applies because the template has whitespace and a comment inside. The id also exists on auth/settings.html (separate page). |
| `#split-view` | id | mock-alliance-selection.js:72, :403-405 (remove 'hidden') | Starts with 'grid hidden', which relies on .hidden winning over .grid in Tailwind order. |
| `#alliance-grid` | id | mock-alliance-selection.js:67, :119-124 (click/dragover/dragleave/drop delegated listeners), :568-585 (innerHTML replaced with 8 .alliance-card) | Delegation root for slot clicks and HTML5 drops. Its content is fully JS-rendered. |
| `.team-slot[data-alliance][data-pick] (.empty/.filled/.captain, data-action=remove)` | data-attr | mock-alliance-selection.js:128-138 (closest('.team-slot'), data-alliance and data-pick parseInt, dataset.action==='remove' -> remove, classList 'empty' -> place), :509-514 (touch drop: elementFromPoint must itself have classes team-slot AND empty), :539-559 (drag-over class) | Generated in JS (:612, :619, :643, :657-660, :680-682). For touch drop, an empty slot must have no element children: elementFromPoint returns the deepest element and the check at :511 is classList.contains, not closest(), so wrapping the slot text in a span breaks touch drag. Class drag-over is toggled during desktop drag. |
| `#available-teams-list` | id | mock-alliance-selection.js:68, :689-706 (innerHTML replaced with .team-card elements) | A grid container for the team cards (scrolling). |
| `.team-card#team-card-{n}[data-team][draggable]` | class | mock-alliance-selection.js:456-470 (getElementById(`team-card-${n}`), toggle 'selected-for-pick', append/remove .selection-indicator), :489 and :526 (JSON.parse(data-team)), :495/:506 and :527/:532 (toggle 'dragging'), :722-738 (id, classes, draggable=true, listeners click/dblclick/dragstart/dragend/touchstart/touchmove/touchend) | Generated by JS. The touchmove listener calls preventDefault (:498-501) and CSS sets touch-action:none (inline style :274), so these cards cannot scroll the list. .declined is styled but never set by JS. |
| `#team-search` | id | mock-alliance-selection.js:66, :111-113 (input -> filterTeams), :689-691 (value used for filtering) | Filter input (same id string as on auton.html, but a different page). |
| `#control-buttons` | id | mock-alliance-selection.js:73, :403-405 (remove 'hidden') | Starts with 'flex hidden'. |
| `#reset-btn #export-btn` | id | mock-alliance-selection.js:64-65, :103-109 | Click -> resetSelection / exportResults. |
| `#start-bracket-btn` | id | mock-alliance-selection.js:71, :115-117 (click -> startPlayoffBracket), :878/:893/:907 (toggle 'hidden'), playoff-bracket.js:15-16 (add 'hidden') | Starts with 'hidden'; shown when selection completes. |
| `#export-playoff-btn onclick=exportPlayoffResults()` | other | mock-alliance-selection.html:136 inline onclick; defined in playoff-bracket.js:353 | Global function call from inline onclick; playoff-bracket.js must load (as a classic script). |
| `#bracket-view` | id | playoff-bracket.js:18-22 (remove 'hidden', scrollIntoView) | Bracket section that starts hidden. |
| `#upper-round-1 #upper-round-2 #upper-round-3 #finals-round #lower-round-1 #lower-round-2 #lower-round-3 #lower-round-4` | id | playoff-bracket.js:94-125 (renderMatch(matchId, containerId) appends match cards) | All eight round containers. Matches go m1-m4 -> upper-round-1, m7-m8 -> upper-round-2, m11 -> upper-round-3, m14-m16 -> finals-round, m5-m6 -> lower-round-1, m9-m10 -> lower-round-2, m12 -> lower-round-3, m13 -> lower-round-4. |
| `template#match-card-template > .match-card` | structure | playoff-bracket.js:175-185 (template.content.cloneNode(true).querySelector('.match-card'), id = `match-${matchId}`) | A <template> whose content has a root element with class match-card. JS assigns ids match-m1..match-m16; match-m16 gets 'opacity-50 pointer-events-none grayscale' when no tiebreaker is needed (playoff-bracket.js:128-139). The card must be overflow-visible because the champion crown sits at -top-2 -right-2. |
| `.match-label .match-id` | class | playoff-bracket.js:189-193 (textContent label and 'M1') | Inside .match-card. |
| `.alliance-option.red / .alliance-option.blue` | class | playoff-bracket.js:182-183 (click -> setMatchWinner), :195-196, :212-266 (class toggles) | Exactly one of each per card, each with both classes (alliance-option plus red or blue). Each must be position:relative (for the absolute crown and the colour bar) and must have a 'border' (border-transparent) so the border-green-500/40 winner state shows. JS toggles: bg-green-50, border-green-500/40, dark:bg-green-500/10, opacity-50, grayscale, cursor-not-allowed, cursor-pointer, bg-zinc-50, dark:bg-zinc-800/40, ring-2, ring-amber-400, ring-offset-2, ring-offset-white, dark:ring-offset-zinc-900. |
| `.team-number .alliance-teams .seed-badge .winner-icon (inside each .alliance-option)` | class | playoff-bracket.js:207-210, :232-233 (team-number 'Alliance N' or 'TBD'; seed-badge N or '?'), :240 (alliance-teams 'a, b, c'), :216-219 and :245-247 (winner-icon opacity-0/opacity-100, scale-0/scale-100) | All four inside each option. winner-icon must start with opacity-0 scale-0 and have transform/transition. |
| `.champion-crown` | class | playoff-bracket.js:221-229, :254-255 | Created by JS inside .alliance-option (absolute -right-2 -top-2, scale-0/scale-100). |
| `cross-script globals` | other | playoff-bracket.js:7 (window.getAlliances from mock-alliance-selection.js:969), :398 (showNotification), mock-alliance-selection.js:143-144 (typeof startPlayoffBracket) | Both files are classic scripts in the same global scope. mock-alliance-selection.js loads first, then playoff-bracket.js (either before DOMContentLoaded, or at least before the first click). |
| `#team-search (needed to render the list, not only to filter)` | (missed, verified) | mock-alliance-selection.js:689 renderAvailableTeams() returns early when dom.teamSearch is null | Without an element with id team-search, #available-teams-list never renders any team cards, so the draft cannot be done at all. |
| `#start-bracket-btn is required by the status banner` | (missed, verified) | mock-alliance-selection.js:856 updateStatus() returns early unless statusText, statusBox AND startBracketBtn all exist | Renaming or removing #start-bracket-btn also stops the #status-text banner from updating. |

#### JS-generated markup
- mock-alliance-selection.js:182-200 notifications: 'flex items-center gap-3 rounded-lg border py-3 pl-1 pr-4 ... mb-2 animate-fade-in' with NOTIFICATION_COLORS (:152-157: bg-green-50/red-50/amber-50/blue-50, text-*-800, border-*-200 plus dark variants). BUG: createSVGElement (:203-210) uses document.createElement('svg') without a namespace, so the icon and the dismiss 'x' never render and the dismiss button (:216, h-7 w-7) shows up empty.
- mock-alliance-selection.js:289-307 event dropdown items ('cursor-pointer rounded-md px-3 py-2 text-sm text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800') and an empty-state div
- mock-alliance-selection.js:595-686 alliance cards: 'alliance-card rounded-lg border p-3' + 'active border-blue-600 dark:border-blue-500' | 'border-zinc-200 dark:border-zinc-800'; team-slot variants; 'pick-round-indicator' 'Picking' pill; current empty pick 'text-blue-600 dark:text-blue-400 animate-pulse' 'Tap or drag a team here'; red hover-x svg 'text-red-500 opacity-0 group-hover:opacity-100'. Nicknames are inserted with innerHTML unescaped (:648, :664).
- mock-alliance-selection.js:717-750 team cards ('team-card min-w-0 rounded-lg border border-zinc-200 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900' + 'selected-for-pick'); nickname unescaped (:745); .selection-indicator 'mt-1 text-xs font-medium text-blue-600 dark:text-blue-400' (:469, :746)
- mock-alliance-selection.js:872-907 status box and text colour class swaps (blue <-> green)
- playoff-bracket.js:212-266 alliance-option state classes, winner icon, crown ('champion-crown pointer-events-none absolute -right-2 -top-2 z-20 scale-0 transform text-amber-500 transition-transform duration-300 dark:text-amber-400'), champion ring classes
- playoff-bracket.js:131/:138 match-m16 disabled classes 'opacity-50 pointer-events-none grayscale'

#### Hard-coded colours
- mock-alliance-selection.html:232-233 .alliance-card.active #2563eb, rgba(37,99,235,0.15)
- mock-alliance-selection.html:243, :248-249, :253-254, :258, :262-263, :267-268 team-slot borders/backgrounds (#d4d4d8, #e4e4e7, #fff, #bfdbfe, #eff6ff, #3f3f46, #18181b, rgba(59,130,246,..))
- mock-alliance-selection.html:283, :287, :293, :297, :305-307, :311-313 team-card hover/declined/selected (#a1a1aa, #52525b, #fef2f2, rgba(239,68,68,0.1), #eff6ff, #2563eb, #3b82f6)
- mock-alliance-selection.html:318-319, :324-325, :329-330, :334-335, :339-340 drag-over/hover/remove-hover (rgba(59,130,246,0.1), #3b82f6, #fafafa, #a1a1aa, rgba(39,39,42,0.6), #52525b, #fca5a5, #fef2f2, rgba(239,68,68,..))
- mock-alliance-selection.html:354-355 .pick-round-indicator background #2563eb, color white
- mock-alliance-selection.html:194, :209 alliance colour bars bg-red-500 / bg-blue-500; :195, :210 red/blue seed badges (bg-red-50 text-red-700 ring-red-600/20, bg-blue-50 ...); :202, :217 winner icon text-green-600 dark:text-green-400; :71, :78 status box blue-50/blue-200/blue-800
- mock-alliance-selection.js:152-157 NOTIFICATION_COLORS (green/red/amber/blue Tailwind literals); :597 active border-blue-600; :680 text-blue-600; :469, :746 text-blue-600
- playoff-bracket.js:224 text-amber-500 crown; :244 green winner; :256 ring-amber-400 champion ring

#### Legacy CSS
- Inline <style> in mock-alliance-selection.html:226-373: .alliance-card(.active), .team-slot(.empty/.filled/.captain/.drag-over/[data-action=remove]:hover), .team-card(:hover/.declined/.dragging/.selected-for-pick), .pick-round-indicator (+ @media max-width 1024px), .animate-fade-in with @keyframes fadeIn, plus .dark variants. All hex/rgba.
- global.css via base (hides number spinners on #year-select)

#### Phone problems at 390px
- The bracket is min-w-[1200px] (mock-alliance-selection.html:147) inside overflow-x-auto, so at 390px it needs about 900px of horizontal panning. Match cards are w-64 with text-[10px] labels (:188, :200), and the alliance-option rows are about 40px tall (p-2 + h-6 badge), under 44-48px.
- The split view stacks on phones: #alliance-grid is its own max-h-[600px] scroll area (:96) holding 8 alliance cards, and #available-teams-list a max-h-[500px] scroll area (:115) below it. Drag-and-drop between them is impractical because they are not on screen together, and tap-select then tap-slot requires scrolling between two nested scrollers.
- Team cards set touch-action:none (inline style :274) and preventDefault on touchmove (mock-alliance-selection.js:498-501), so swiping on the team grid cannot scroll the list or the page.
- The event dropdown arrow is a small div (about 26px wide, :46); the notification dismiss button is 28px and renders empty (SVG namespace bug).
- Control buttons are .btn (about 36px tall) and the nav buttons are btn-sm (about 30px).
- The available-teams grid is grid-cols-2 at phone width with truncated nicknames (fine), but the 'Picking' indicator shrinks to 0.65rem under 1024px (:343-348).
- Uses alert() in playoff-bracket.js:355, :401.

#### Redesign notes
All alliance, slot, team-card and bracket markup is built in JS, so restyling means editing mock-alliance-selection.js and playoff-bracket.js plus moving the inline <style> into Tailwind components with the new tokens. Keep these exactly: #status-text two levels inside the box whose classes are swapped (or update the toggle lists); every 'hidden' start state; template#match-card-template and its inner class names; .alliance-option.red/.blue with relative + border; empty .team-slot with only a text node (touch drop); data-alliance, data-pick and data-action attributes; the #event-dropdown_arrow underscore id; the hidden #event-select. For phones, consider a sticky 'current pick' panel and a 'place in current pick' action, plus a vertical or stacked bracket. Fix createSVGElement to use createElementNS. Escape nicknames. All classes are literal strings in JS files covered by tailwind content globs, so no safelist is needed, but any new colour tokens used here must also be literal.

### Other missed hooks (verified)
- `app/templates/base.html (every page in this group extends it)` `meta[name=csrf-token] + the CSRF fetch-wrapper IIFE in <head> (base.html:6-24)` (used by team-stats.js:65-69 POSTs to /api/team_epa_opr with only a Content-Type header. CSRFProtect is global (app/app.py:17, :41 WTF_CSRF_ENABLED=True), and only update_assignment_status is exempt (app.py:94). tests/test_browser_resilience.js:252-275 cuts the IIFE out of base.html by searching for the comment text 'Send the CSRF token', then '(function () {' and '})();'.): Keep the csrf-token meta and the window.fetch wrapper in <head>, before any page script. Without them the leaderboard metrics POST fails CSRF and every EPA/OPR/DPR/CCWM shows N/A. Keep the marker comment and the IIFE shape, or update the test together with the markup.

### Other missed items (verified)
- Legacy CSS beats Tailwind utilities. auton.css is linked in block head, which renders after tailwind.css (base.html:26 then :37), and the mock inline <style> sits in <body>, also after tailwind.css. Their rules have the same specificity as utilities, so they win. Adding h-12 w-12 to .tool-btn does nothing while auton.css:88-89 (width/height 40px) is loaded. The same applies to .team-slot min-height and border (mock-alliance-selection.html:236-269), .path-card padding and colours (auton.css:2-34), and the '.dark .x' rules. Delete or port the legacy rules instead of layering utilities on top.
- Phone problem: Canvas pan and zoom reset on every window resize. Canvas.js:1048 binds a window resize listener, and resizeCanvas() always calls resetView() (Canvas.js:197-199). auton.js:163-171 adds a second resize listener. On phones the URL bar showing or hiding during page scroll fires resize, so pinch-zoom and pan on both the auton canvas and the lighthouse modal snap back. A layout change that resizes the container (for example a sticky bar appearing) does the same.
- compare.js:237-246 observes every class change on <html> and destroys and recreates the radar chart. If the rebuild puts a scroll-lock class (for example overflow-hidden) on <html> while the auto-path modal is open, the chart is rebuilt on every open and close. Lock scroll on <body> or with a style or data attribute instead.
- Mock draft placement ignores the slot that is tapped or dropped on. selectTeam (mock-alliance-selection.js:752-762) always pushes onto state.alliances[state.currentPick.alliance]. The slot click, touch-drop and HTML5-drop paths (:477-486, :511-519, :552-566) use data-alliance/data-pick only as a guard (the alliance exists and that pick index is empty). Any free pick slot of any formed alliance therefore places the team into the current picking alliance. A phone 'Place in current pick' button calling selectTeam(state.selectedTeamForPick) behaves the same as today; do not design per-slot targeting.
- playoff-bracket.js:21 calls #bracket-view.scrollIntoView({behavior:'smooth'}). The sticky header (base.html:79, sticky top-0 z-40), and the new banner top bar, cover the bracket heading. Give #bracket-view a scroll-margin-top.
- Hardcoded colour not in the inventory: the champion ring offset 'ring-offset-white' / 'dark:ring-offset-zinc-900' (playoff-bracket.js:256-258) must match the new card surface (white, and #141a26 in dark) or a zinc-900 gap ring shows around the champion option.
- compare.js:2 and auton.js:2 both declare a top-level `const API_ENDPOINT` (and both define escapeHtml) in classic scripts. They can never load on the same page: the second throws a redeclaration SyntaxError. This matters if the rebuild merges team comparison and path comparison into one tabbed page. mock-alliance-selection.js also claims the global names `state` and `dom`.
- New design fonts and the service worker: STATIC_ASSETS (service-worker.js:11-30) is matched with event.request.url.includes(asset) (service-worker.js:241) and lists no fonts. The Richardson and Oxanium files would go network-only and fail offline at competition. 'Richardson Brand Accelerator.otf' has spaces, so request.url carries %20; a STATIC_ASSETS entry written with literal spaces would never match. Add the encoded path, or rename the file.
- Test touching shared markup: tests/test_browser_resilience.js:252-275 parses app/templates/base.html as text. Rebuilding the base layout that these pages extend can break `npm test` (package.json "test") if the 'Send the CSRF token' comment or the IIFE delimiters change.

## Kit fit (taste-skill 2.5.1)

Recommendation: use the kit in two different ways. (1) On logged-in app pages, load no kit file. Tailwind stays the one system, and we port the kit's tokens and rules into tailwind.config.js and tailwind.input.css: the spacing, type and radius scales, 48px controls, the form recipe, the focus ring, the one-card recipe, tabular numbers, the press and hover timings and the access rules. Loading system.css or system.js there would break behaviour. Its `.grid > *{grid-column:1/-1}` collapses all 37 Tailwind `grid` layouts in 17 templates. It makes any `main > section` exactly 100svh tall with 120px top padding. Every `.link` gains a → arrow, every `.card` lifts on hover and the offline `.badge` turns into a solid blue pill. system.js would take over any `form.form`, outline in red any scouting text with [brackets] in it, and switch lazy images to eager. (2) The public landing page `/` can be a real tasteskill build of kind software. It needs its own shell (kit CSS only, no tailwind.css), runs on the Flask dev server and is gated with `gate.mjs --start http://127.0.0.1:5000/`. The route `/` is public (castle app/app.py:139), so the headless checker sees the logged-out version. The kit has no class-based dark mode, so Castle's palette goes in as `--p-*` overrides on `:root` and `html.dark`. I ran `start.mjs brand` for both themes from the scratchpad; its output is in branding_tokens. Biggest offline issues: (a) start.mjs prints render-blocking Google Fonts links, and the service worker never caches cross-origin requests. (b) The service worker answers any uncached same-origin request it fails to fetch with a text/css fallback, so kit ES modules fail to load offline. (c) The Richardson font file name has spaces, which defeats the service worker's `url.includes()` match. Path roots used below: <kit> = C:/Users/Eric/.claude/plugins/cache/taste-skill/taste-skill/2.5.1/skills/taste-skill and <castle> = C:/Users/Eric/Documents/GitHub/Castle. No project file was edited. The only command I ran was start.mjs brand, from the scratchpad; it writes nothing (start.mjs:463-467 records history only for `css`, and only `deal` arms the gate: start.mjs:208-212).

### Ports into Tailwind on app pages
- **Spacing scale and rhythm** (<kit>/assets/system.css:57-58, 61-64; <kit>/references/system.md:14-15): Port it, do not load it. The kit's spacing tokens are --s-1 to --s-10 = 4, 8, 12, 16, 24, 32, 48, 64, 96, 128. It wants 48px from heading to content (32 on a phone) and 24px between cards (12 on a phone). Tailwind's default spacing is already on a 4px base (p-1=4px ... p-32=128px), so limit page markup to 1, 2, 3, 4, 6, 8, 12, 16, 24 and 32. Ignore the kit's section rhythm tokens (--padt, --padb, --nav), which only exist for one-section-per-screen.
- **Type scale and minimum text size** (<kit>/assets/system.css:66-78; <kit>/references/system.md:43-64; <kit>/references/layout-v4.md:267-271; <castle>/app/static/css/tailwind.input.css:81, 83-85, 92, 117-118): Add Tailwind fontSize tokens: label 13px/500, small 14, body 16, lead 18-20, card title 18-20, h3 24-28, and page titles on the kit's h2 scale clamp(30-48px), not the 72px h1. Text people read is 16px with line height 1.5-1.8, nothing goes under 13px, labels are in sentence case and never in tracked caps. This means replacing Castle's 12px text-xs in .help, .badge and table heads with 13px. Keep inputs at 16px on desktop too: drop `sm:text-sm` from .input, which also stops iOS zoom on focus.
- **Radius scale** (<kit>/assets/system.css:81, 93-95; <kit>/references/system.md:90-93; <kit>/references/cards.md:35): Take the 'soft' set into tailwind.config theme.extend.borderRadius: controls 8px, panels 12px, cards 20px (18 on a phone). One radius family for the whole app.
- **Buttons: one pair, 48px, step and press** (<kit>/assets/system.css:427-442, 461, 472-480; <kit>/assets/motion/motion.css:34-56; <kit>/references/motion.md:51-64, 73; <kit>/references/system.md:94-102; <castle>/app/static/css/tailwind.input.css:51-74): Keep Castle's own class names (.btn, .btn-primary, .btn-secondary in @layer components) and take the kit's rules. There is one filled primary per view (#0b5fb0 light, #2f7ae0 dark) and one secondary look. Height is 48px; the kit's own 48px value is data-buttons="block" (system.css:442). Labels are 16px/500 with 24px side padding, full width on phones, and say a verb plus an object. Press: translateY(1px) scale(.985) over 90ms. Hover, only for a fine pointer: 1px up, 150ms in and 120ms out, with the colour stepping 14% toward the ink. Wrap these in motion-safe: and @media (hover:hover) and (pointer:fine). .btn-sm and .btn-icon must also reach a 48px hit area.
- **Focus ring** (<kit>/assets/system.css:200; <kit>/references/motion.md:82; <kit>/references/system.md:206-208; <castle>/app/static/css/tailwind.input.css:19-21): Use a 2px ring in the action colour, offset 2px, with no transition. Castle already has ring-2 with ring-offset-2; recolour it to brand blue and drop the 60% alpha so it reaches 3:1. Add scroll-padding-top equal to the sticky header height and scroll-padding-bottom equal to the save bar height, so a focused field is never hidden under either. The kit's own scroll-padding-top:0 is a marketing rule; do not copy it.
- **Form recipe (labels, sizes, errors, status, honest success)** (<kit>/references/system.md:163-193; <kit>/assets/starter.html:453-469; <kit>/assets/system.js:249-308 (reference implementation only); <kit>/assets/system.css:1238-1259; <castle>/app/static/css/global.css:48-56): Every form follows it. Each field has a visible <label for> above it, and a placeholder never stands in for it. Fields are 48px with 16px text. Use the right type, autocomplete and inputmode (inputmode="numeric" on the scouting counters). Validate on submit, not while typing. Each failed field gets aria-invalid="true" and a `<p id>` reason under it, linked by aria-describedby, that names the field and what to type; the first failed field takes focus. One `role="status"` line under the save button says Sending / Saved / Not saved. Typed values survive a failure, and 'Saved' only appears after the server answered. Write this into Castle's own JS (scout/add.js and similar). Do NOT add class="form" or load system.js: it sets noValidate and adds its own submit listener and fetch.
- **Sticky full-width save bar** (<kit>/assets/system.css:1261-1290; <kit>/references/system.md:37, 126-136; <kit>/assets/system.js:344-384 (do not use)): Copy the CSS pattern of the kit's phone action bar, not its JS. The kit's bar is fixed at the foot with 48px buttons, height calc(64px + env(safe-area-inset-bottom)), a 1px top hairline on the page ground, and every section pads by --bar so content is never hidden under it. A hidden bar is inert. For Castle: a sticky (or fixed) full-width bar with the form padded by its height. The kit's own ban on sticky elements is a marketing rule. Do not reuse actionbar() from system.js: it hides the bar until a hero button scrolls away.
- **Lists, tables to cards on phones, tabular numbers** (<kit>/assets/system.css:1224-1235; <kit>/references/system.md:150-152; <castle>/app/static/css/tailwind.input.css:110-128): Use the kit's .rows pattern as the phone version of each table row: a card whose cells become name-left / value-right lines (a dl of dt and dd), with 16px text, tabular-nums on the values, a 1px rule closing each line and none above the first. At 640px and up keep Castle's .table-wrap with overflow-x. The same pattern fits team stats, match lists and the leaderboard.
- **One card recipe** (<kit>/references/cards.md:23-44, 46-55; <kit>/references/sections.md:62-63; <kit>/references/motion.md:79-80; <castle>/app/static/css/tailwind.input.css:40-48): Cards are a surface one step off the ground (#fff on #eef2f7; #141a26 on #0b0f17) with a 1px border at 8-14% of the ink (#1f2838 in dark). No blurred shadow at rest, so remove shadow-sm from .card. Radius 20 (18 on a phone), padding 24 on a phone and 32 from 1024px. Never put text in a box inside a box (two boxes deep at most). Card text is 16px in the ink, not small grey. Lift on hover only for cards that are links; Castle's 146 .card uses are mostly not links, so they stay still.
- **Dashboard numbers** (<kit>/assets/system.css:195-196; <kit>/references/system.md:62-64): Follow the kit's .t-stat idea: a big number in the display face with tabular-nums, one step under the h2 (38px desktop, 28px phone), and one size per kind of figure across the app. For Castle, use a Tailwind `font-num` family (Oxanium) with tabular-nums on scores, EPA and counts, so figures don't jitter while they update.
- **Colour discipline and contrast** (<kit>/references/system.md:49-54, 66-86): The interface stays 90-95% neutral. Brand blue only marks the primary button, focus, links, the current nav item and selected states. Ink text at 7:1, muted at 4.5:1 or better, at most 3:1 for 24px+ grey halves. Alliance red and blue and the status badges stay, but at 13px or larger.
- **Accessibility rules** (<kit>/references/system.md:17-20, 195-210; <kit>/assets/system.css:1320-1324; <castle>/app/templates/base.html:90-95, 129): Add a skip link as the first item of the header. Give .mobile-menu-button aria-expanded, which it lacks today. Put aria-current="page" next to nav-link-active. Headings step down one level at a time, no tabindex above 0, every icon-only button is named, and every picture has alt.
- **Phone menu behaviour** (<kit>/assets/system.js:72-114; <kit>/references/system.md:123-126; <castle>/app/templates/base.html:129-161, 201-204): Port the behaviour into base.html's own mobile menu: 48-56px rows, close on Escape, close after a link tap, close again at the desktop breakpoint, keep aria-expanded in sync. Do not import the kit's .nav markup or script.
- **Motion budget** (<kit>/references/motion.md:49-64, 209-235; <kit>/assets/system.css:90; <castle>/app/static/css/index.css:61-63, 105-119, 129-141): Animate only transform, opacity and colour, over 120-240ms with the ease cubic-bezier(.2,.8,.2,1). Under reduced motion, colours still change but nothing moves. Nothing reveals on scroll. While rebuilding, drop index.css's scroll and float animations (.animate-on-scroll, .animate-float, .animate-gradient-text, .feature-card lift on unlinked cards).
- **Performance rules** (<kit>/references/perf.md:13-30, 42-45): Every <img> gets width and height (profile pictures included). Images below the fold are lazy, the first screen is eager. At most four font files, two preloaded, font-display: swap. No layout shift from late fonts or numbers.
- **Tabs (only if a page needs them)** (<kit>/assets/system.js:116-149; <kit>/references/motion.md:78): Copy the ARIA pattern: role tablist, tab and tabpanel, arrow keys between tabs, a click only (never timed), and fixed-height panels. Castle has no tablists today; write a small Castle version rather than loading system.js.

### Marketing-only (landing page only, never app pages)
- **One section per screen (100svh sections, --padt 120/96, .g2, footer.closing as a screen):** App pages are task flows of any length: forms, long tables, match lists. Forcing sections to 1 or 2 screens with 120px top padding would push content off screen or leave empty space. The selector is element-based (`main > :is(section,.section)`), so it would also hit any <section> that is a direct child of <main>. Source: <kit>/SKILL.md:36-39; <kit>/references/layout-v4.md:22-41, 87-89; <kit>/assets/system.css:221-276.
- **Heroes: deal.mjs, heroes.json, hero-*.html, layout.css, layout.js:** They exist to persuade on a first screen. An app page needs a page header and the task. layout.js also statically imports ui/ui.js (41KB) on every page that loads it. Source: <kit>/references/layout-v4.md:98-185; <kit>/assets/layout/deal.mjs; <kit>/assets/layout/layout.js:29.
- **Hero entrance (data-enter plus the m-enter head script):** It hides the h1 and the lines after it for up to 700ms and re-masks words on every load. On app pages that means every navigation and every scout reload would blink the page title. Source: <kit>/references/motion.md:91-126; <kit>/assets/motion/motion.css:268-279; <kit>/assets/motion/motion.js:331-389.
- **Dealt moments, shader effects, scenes, CSS grounds, objects, WebGL, card loops, counts, pause buttons:** These are award-site decoration. They cost GPU, battery and bytes on phones with bad arena Wi-Fi, and carry no data. Source: <kit>/SKILL.md:51-54, 143, 147-153; <kit>/references/motion.md:128-185; <kit>/references/perf.md:24-25, 40.
- **Photographs and stand-ins (photos.mjs), real-brand icons (icons.mjs):** They fill marketing sections; app pages show live data. Source: <kit>/SKILL.md:144-145; <kit>/references/sections.md:633-634.
- **Feature cards with lit panels, UI fragments (assets/ui), diagram cards:** They depict a product's UI for a sales page. Castle's pages are the real UI. Source: <kit>/references/cards.md:46-150; <kit>/references/sections.md:621-628.
- **Copy rules beyond labels and buttons (h1 names the category, one hard fact, 60-80 words a screen, banned word lists, copy-lint):** These are marketing copy rules. App microcopy only needs the label, button, error and sentence-case parts (copy.md:46-49, 101-104). Source: <kit>/references/copy.md:34-56, 72-95, 184-193.
- **Fixed opaque header with 'nothing else sticky', mega menus (.nav__menu), the phone sheet at under 1024px:** It conflicts with Castle's sticky header (base.html:79) and the planned sticky save bar. The menu needs 1024px of width; Castle has 3-4 destinations and switches at 640px. Source: <kit>/references/system.md:104-136; <kit>/references/layout-v4.md:29-31, 95-96; <kit>/assets/system.css:639-779.
- **system.js extras: guards, pictures, hours/openNow, peek, faq, tone, visuals, actionbar:** This is QA and decoration scaffolding for generated marketing pages. guards() would red-outline any scouting note or team text containing [brackets], the word 'placeholder' or a .example address. pictures() forces every lazy image to load. actionbar() keys off a hero button. Source: <kit>/assets/system.js:151-247, 311-384, 405-547, 549-577.
- **House rule 9 (addresses, phones), credits line, share tags with share.jpg, the canonical-domain rule:** These are public-page concerns. They only matter for the landing page's head and footer. Source: <kit>/SKILL.md:55-56; <kit>/references/system.md:212-226; <kit>/references/copy.md:133-171.
- **The deal (palette, pairing, nav/footer/close one-liner) and the finish gate:** Both are built to judge a whole marketing page. App pages fail hero-fold, one-section, moment-none and hero-enter by design. Never arm the gate on an app route. Source: <kit>/SKILL.md:196-228, 278-289; <kit>/references/gate.md:32-68.

### Conflicts
- **.grid: the kit's 12-column grid forces every child to span the full row** (<kit>/assets/system.css:205-206 sets `.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));column-gap;row-gap}` and `.grid > *{grid-column:1/-1}`. Castle uses Tailwind's `grid` utility 37 times in 17 templates, e.g. index.html:37 `grid gap-4 sm:grid-cols-3`, plus compare.js:429. Tailwind never sets grid-column on children, so every sm:grid-cols-N layout would collapse to one column.) → Never load system.css on a page that uses Tailwind grids. Choose one system per page: app pages get Tailwind only, the landing page gets the kit only.
- **Element selector `main > section` becomes a full-screen box** (<kit>/assets/system.css:221-225 (and 245-276 for tablet and phone) gives any direct <section> child of <main> height calc(var(--h,1)*100svh) and padding 120px top / 72px bottom. index.html's three <section>s are direct children of base.html's <main> (index.html:5, 35, 83; base.html:164). 13 templates contain <section>; most are nested in a div today, but a rebuild could make them direct children.) → Load the kit only in the landing shell. On app pages there is no system.css, so no element-level layout rules.
- **.card: same name, different component, plus a hover lift on every card** (Kit .card is display:flex column, gap 8px, padding 16px, radius 20 (system.css:494-511). motion.css:157-169 lifts every .card that is not .m-nolift 2px on hover and adds a shadow. Castle's .card (tailwind.input.css:40-42) is used 146 times in templates, as the user dropdown (base.html:117), the flash toast (base.html:169) and in compare.js:422-423. Tailwind 3.4.17's output has no native @layer (grep count 0), so whichever stylesheet loads last wins property by property. Kit after Tailwind also overrides utilities such as p-1 on the dropdown.) → Do not co-load. If both ever have to share a page, every non-link Castle card needs .m-nolift and the kit must load before tailwind.css. Better: keep Castle's .card and port the kit's card rules into it (no rest shadow, 1px line, radius 20).
- **.btn base class: fixed 44px height, font and transforms** (Kit .btn sets height:var(--btn-h) (44px), padding 0 24px, font 500 16px/1, nowrap (system.css:427-431), plus `.btn:active{transform}` (461) and motion.css:34-56 (position:relative, transition, a 1px hover step). Castle's .btn, .btn-sm and .btn-icon are padding-based (tailwind.input.css:51-74), with 125 uses. The modifiers differ (.btn--primary vs .btn-primary) but the base .btn collides, so the theme toggle `.btn btn-ghost btn-icon` (base.html:105) would become a 44px-tall, 24px-padded button.) → Castle keeps its own .btn in @layer components and sets min-height 48px itself. Never link system.css or motion.css on app pages.
- **.link gains an arrow and an animated underline** (system.css:482-487 adds `text-decoration: underline` and `.link::after{content:"\2192"}`. motion.css:86-103 replaces the underline with a drawn gradient line. Castle's .link (tailwind.input.css:131-133) is used 20 times in templates and is built in compare.js:304, 491.) → One system per page. On the landing page use the kit's .link as intended.
- **.badge turns into a filled action-colour pill** (system.css:867-868 gives .badge the action colour as background, 24px tall, radius 999. Castle's .badge and its colour variants (tailwind.input.css:91-108) have 30 uses, including the offline indicator `badge badge-amber` (base.html:99, 136), which base.js shows and hides by id (base.js:15-23, 152-185).) → Do not co-load. On the landing page, if the offline indicator stays in the header, style it with page CSS under the same ids.
- **.group and .container** (system.css:239 sets `.group{display:flex;flex-direction:column;min-height:0}`. Tailwind's `group` (used for group-hover) appears in auth/profile.html:70, forgot-password.html:19, mock-alliance-selection.html:37, 193, 208 and mock-alliance-selection.js:657. system.css:204 makes .container an alias of .wrap; Tailwind has its own .container.) → Not an issue if system.css is never on app pages. Avoid `group` and `container` on the kit landing page.
- **Reset and base clashes with Tailwind preflight** (system.css:163-200: (1) h1-h4 get the display font, kit sizes (h2 30-48px, h3 24-28px), letter-spacing -0.025em, hyphens:auto and text-wrap:balance, while preflight sets h1-h6 to font-size:inherit. (2) body background, colour and font fight Castle's base (tailwind.input.css:15-17). (3) `img, svg, video, canvas{max-width:100%}` also caps svg and canvas, unlike preflight; Canvas.js sizes its canvas from getBoundingClientRect (Canvas.js:187-195), so a mismatch would change coordinates. (4) `[hidden]{display:none!important}` beats inline display on elements with the hidden attribute. (5) A kit :focus-visible outline on top of Castle's ring (tailwind.input.css:19-21) gives a double ring. (6) html sets scroll-behavior:auto against global.css:2-5 `*{scroll-behavior:smooth}`.) → One system per page. If a stylesheet is ever wrapped with `@import url(...) layer(kit)` to keep the kit file unedited, note that unlayered Tailwind preflight then beats every kit base rule (headings collapse to inherit). So the landing page must not load tailwind.css at all.
- **Global reduced-motion kill switch** (system.css:1309-1313 sets `animation-duration:.001ms !important; transition-duration:.001ms !important` on everything except data-m-loop. That would also shorten Castle's toast-in (base.html:65-70) and any JS that waits on transitions.) → Only on the landing page, where that is intended.
- **motion.css restyles generic elements** (motion.css:86-104 gives `p a:not([class])` and `.footer ul a` a drawn underline. motion.css:188-196 restyles `.field input` focus. motion.css:157-169 lifts every .card.) → Do not load it on app pages. Castle writes its own small hover and press layer in Tailwind.
- **Script hooks: system.js, motion.js and base.html's inline script** (system.js nav() binds the first `.nav` (72-114). forms() takes over any `form.form` with noValidate, its own validation and an optional fetch (249-308). tabs() binds every [role=tablist] (116-149). guards() outlines any text matching `\[...\]` or 'placeholder' (549-577). motion.js adds document-wide click listeners for .loop-pause and .m-switch (motion.js:251-268) and binds `.nav` (36-55). Separately, base.html:202 calls `document.querySelector('.mobile-menu-button').addEventListener` with no null check. A shell without that button throws there, and the flash auto-dismiss, theme toggle and user menu (base.html:207-241) never run.) → App pages load no kit JS. The landing shell must keep a .theme-toggle button and its own toggle script. If it reuses base.html's inline script, guard it with `?.`.
- **Custom property names** (The kit uses short global names (--bg, --ink, --line, --card, --action, --muted, --h, --w, --x, --y) on :root and on elements (system.css:9-90, 137-158). offline.html defines its own --bg (offline.html:9-12); it is standalone and never loaded with the kit.) → Prefix Castle's tokens --c-* in tailwind.input.css. On the landing page, map the kit's --p-* values to them.
- **Editing the kit to prefix or scope it is blocked by the gate** (gate.md:42-45 and gate.mjs:356-367: any file under an `assets/` path that differs from the kit copy is a hard kit-edited FAIL that cannot be waived.) → Do not prefix the kit. Scope by loading: kit files only in landing_base.html, Tailwind everywhere else.

### Landing page plan
Kind and metas. Castle is an app for FRC teams, which is row 1 of the kind table (page type software, site-kind software, kind software; <kit>/SKILL.md:66-68). The landing shell sets `<html lang="en" data-type="software" data-radius="soft" data-buttons="<dealt>" data-motion>` plus `<meta name="page-type" content="software">` and `<meta name="site-kind" content="software">`. There is no page-kind meta (that is for places only). Source: <kit>/SKILL.md:60-64; <kit>/assets/starter.html:10, 36-37.

Shell. Today index.html extends base.html, which has a Tailwind-padded `<main class="mx-auto max-w-7xl px-4 py-6">`, a sticky blurred header and a non-closing footer (<castle>/app/templates/base.html:79, 164, 188), and base.html has no blocks to swap them. The kit needs `header.nav` fixed, a full-width `main id="top"`, `main > section` children and `footer.closing` (<kit>/references/layout-v4.md:29-31). Recommended:
- Add a `landing_base.html` that loads only the kit CSS. It keeps base.html's theme head script (base.html:28-34), the manifest and icons (39-42), and base.js as a classic script with data-app-version (base.html:245; base.js:31 reads document.currentScript, which is null in a module).
- Keep the CSRF IIFE literally in base.html. tests/test_browser_resilience.js:252-260 extracts it from that file by its comment text.
- Make index.html choose its layout: `{% extends "base.html" if current_user.is_authenticated else "landing_base.html" %}`. Logged-in users keep today's Scout/Compare/Team home with no Python change (app.py:97-98). That variant shows 3 hero actions, over the kit's limit of 2 (copy.md:50), but the gate never sees it because headless Chrome is logged out.
- Keep the ids #installPWA and #installMessage and the pwa-install.js tag (index.html:32, 95-104; pwa-install.js:9-37).
- Add page CSS `.hidden{display:none}`. pwa-install.js toggles Tailwind's `hidden` class, and system.css only hides the [hidden] attribute (system.css:173).
- Give #installPWA, #update-banner (base.js:120-135) and any flash toast their own landing styles, since tailwind.css is absent.
- Copy the kit unchanged into <castle>/app/static/assets/, NOT the repo-root assets/ folder (which holds mongodb.png and video.mp4). Link the files with url_for('static', filename='assets/system.css') and so on. Keep the folder layout, because system.js imports effects/, ui/ and moments/ relative to its own URL (system.js:65, 470-471, 580).

Commands, run from <castle> (the deal arms the gate in the folder it runs in; SKILL.md:207-208):
1. Arm the gate first. A Jinja file is not a page a browser can open (`{% extends %}`, url_for), so name the dev server: start Flask on 127.0.0.1:5000 (e.g. `python wsgi.py`), then run `node <kit>/scripts/gate.mjs --start http://127.0.0.1:5000/ --kind software --category "Scouting app for FRC teams" --primary "Create an account"`. Only localhost, 127.0.0.1, [::1], *.localhost or *.test URLs are accepted (gate.mjs:108; gate.md:14-18; SKILL.md:171-177).
2. Deal the hero: `node <kit>/assets/layout/deal.mjs --type software --has ui --history .taste-skill/layout-history.json`. Add `photo` to --has only if the team has real photographs of scouts in the stands. Add `film` only if <castle>/assets/video.mp4 (5.6MB) is a usable product clip.
3. Colours: Castle has its own, so use `brand` instead of `deal`/`css` (SKILL.md:202, 224): `node <kit>/scripts/start.mjs brand --page software --bg "#eef2f7" --surface "#ffffff" --ink "<ink>" --accent "#0b5fb0" --type <software pairing> --radius soft`, then run it again with the dark colours for html.dark (see branding_tokens). brand needs a Google pairing id (start.mjs:438-445); replace its font link and --font-* lines with self-hosted faces. brand never arms the gate (gate.md:22), which is why step 1 comes first.
4. Moment: `node <kit>/scripts/moments.mjs pick --page software --count 1 --fits section,statement --contexts 0 --history .taste-skill/history.json` (moments.md:45-47). The gate treats moment-none and hero-enter as FAILs (gate.md:66-68).
5. Dealt parts: run the software one-liner for nav, footer, close, rhythm, buttons and mark (SKILL.md:204, 210). Castle's own logo replaces the dealt mark (sections.md:111). For the blue banner use `nav--tone` (allowed on tech; system.css:807) with a header-scoped override, because brand sets --p-inv-bg to the ink colour, not blue.

Page plan: the software plan (sections.md:118-133) is nav, hero, app-frame, two feature sections, FAQ, footer.closing.
- Hero h1 names the category for the buyer, e.g. 'Scouting app for FRC teams'. Today's h1 'Castle' (index.html:8) would fail copy-headline.
- One hard fact on the first screen (copy.md:36-41).
- The app-frame shows Castle's real scouting form or compare view as live HTML, which is the kit's preferred software picture (cards.md:76-85).
- Every section 1 or 2 screens, with data-enter on the hero.
- Buttons are a verb plus an object, e.g. 'Create an account'; 'Get started' (index.html:15) is a bare command the kit rejects (copy.md:46-49, 78). 'Log in' as the plain second word (system.md:116-118).
- Links to /auth/register and /auth/login are fine, because they land on real pages (copy.md:179).
- Keep the m-enter head line after the stylesheets (motion.md:106-110) and the skip link (system.md:17-20).

Checking:
- Each check script runs one headless Chrome, in the foreground, with a 10-minute timeout (SKILL.md:250-257).
- With a URL target the gate runs consistency.mjs and check.mjs against the server (gate.mjs:28-29), and copy-lint on the rendered.html that consistency saves (gate.mjs:386-394; gate.md:53-61).
- It also scans <castle>/app for kit-edited files and checker-gaming code. sourceFiles covers src, app, pages, components, lib and public (gate.mjs:734 and sourceFiles). Castle's JS has no webdriver or HeadlessChrome tests today.
- Manual step-6 tools: pass `--url http://127.0.0.1:5000/` to check.mjs and shoot.mjs. Run copy-lint on a saved render, e.g. `curl http://127.0.0.1:5000/ > .taste-skill/render.html`, then `node <kit>/scripts/copy-lint.mjs .taste-skill/render.html --kind software`.
- Then `node <kit>/scripts/gate.mjs` until `GATE: PASS`/`OPEN`, at most 3 rounds (SKILL.md:274-282).
- The gate only ever sees light mode. Headless Chrome has no localStorage.theme and no dark preference (base.html:29), so shoot dark mode by hand.

Static-render alternative: render `/` with Flask's test client into a file inside <castle>/app, then `--start app/<file>.html --root app` so `/static/...` resolves. Expect link and broken-request findings: /auth/*, /offline.html and /service-worker.js are Flask routes (app.py:165-177), not files, so the gate's static server returns 404s. Prefer the dev server.

Housekeeping:
- Arming creates <castle>/.taste-skill/ (build.json, gate.json, history); shots/ appears too. Neither is in .gitignore yet; add both.
- Once the skill is invoked, its Stop hook runs the gate on every stop of the main session until PASS, OPEN or `gate.mjs --done "<user's words>"` (SKILL.md:14-19; gate.md:84-105, 203-205).
- Never edit a copied kit file. kit-edited is a hard FAIL that cannot be waived (gate.md:42-45; gate.mjs:356-367).

### Branding tokens
The kit has no dark mode switch of its own. It has no prefers-color-scheme or .dark rules in system.css, cards.css, layout.css or motion.css. A 'dark page' is simply a palette whose --p-bg is dark; system.js tone() reads that once at load and sets <html data-tone> (system.js:510-517). Everything else derives from the --p-* tokens: --bg, --ink, --card, --action and --line are var(--p-*) on :root (system.css:137-158). So class-based dark mode works by redefining the --p-* tokens on html.dark. The selector `html.dark` (0,1,1) outranks `:root` (0,1,0), and the derived tokens re-resolve on the same element. base.html's head script already adds .dark before first paint (base.html:28-34).

Light block, from my scratchpad run of `start.mjs brand --page software --bg "#eef2f7" --surface "#ffffff" --ink "#0f172a" --accent "#0b5fb0" --type geist --radius soft`. The ink #0f172a is my placeholder; the team should choose its near-black. Paste it as printed in a <style> after the kit links:
:root{--p-bg:#eef2f7;--p-surface:#ffffff;--p-ink:#0f172a;--p-muted:#616979;--p-accent:#0b5fb0;--p-accent-ink:#eef2f7;--p-action:#0b5fb0;--p-action-ink:#eef2f7;--p-inv-bg:#0f172a;--p-inv-surface:#1b2436;--p-inv-ink:#eef2f7;--p-inv-muted:#9097a3;--p-inv-accent:#eef2f7;--p-inv-accent-ink:#0f172a;--p-inv-action:#eef2f7;--p-inv-action-ink:#0f172a}

Dark block, from `brand --bg "#0b0f17" --surface "#141a26" --ink "#e6ebf3" --accent "#2f7ae0"`, placed under html.dark:
html.dark{--p-bg:#0b0f17;--p-surface:#141a26;--p-ink:#e6ebf3;--p-muted:#81868f;--p-accent:#2f7ae0;--p-accent-ink:#0b0f17;--p-action:#2f7ae0;--p-action-ink:#0b0f17;--p-inv-bg:#e6ebf3;--p-inv-surface:#d4d9e1;--p-inv-ink:#0b0f17;--p-inv-muted:#545861;--p-inv-accent:#2f7ae0;--p-inv-accent-ink:#0b0f17;--p-inv-action:#2f7ae0;--p-inv-action-ink:#0b0f17;color-scheme:dark}

How the generator decides (start.mjs:166-186):
- It picks accent-ink as the ground colour whenever that reaches 4.5:1, so light buttons get #eef2f7 text rather than pure white.
- White on #2f7ae0 is about 4.2:1, so dark-mode buttons are given near-black #0b0f17 text. If the team wants white labels in dark mode, the button blue must darken to about #2a6fcf or below.
- Cards: --card is --p-surface on :root (system.css:139), which gives white cards in light and #141a26 in dark, both as specified.
- Borders: --line is 11% of the ink (system.css:152-153), not #1f2838. Set `html.dark{--line:#1f2838}` in page CSS to match the spec.
- Radius: soft (system.css:94). Button height: data-buttons=\"block\" gives 48px (system.css:442).

Blue banner top bar: the nav paints --bg (system.css:639-642), and .nav--tone repaints it with the --p-inv-* tokens (system.css:807-810). brand sets --p-inv-bg to the ink colour, so .nav--tone gives a near-black bar, not blue. Use a header-scoped page rule: `header.nav{--bg:#0b5fb0;--ink:#ffffff;--muted:#d6e4f5;--line:transparent;--action:#ffffff;--action-ink:#0b5fb0}` and `html.dark header.nav{--bg:#141a26;--line:#1f2838;--action:#2f7ae0;--action-ink:#0b0f17}`. Use logo-dark.png on the blue bar in both themes, since base.html swaps logos with dark:hidden (base.html:82-83).

Fonts: brand prints a Google Fonts link and --font-display/--font-text stacks (start.mjs:291-307, 321). Replace both with self-hosted faces:
- `@font-face{font-family:\"Castle Display\";src:url(/static/fonts/richardson-brand-accelerator.woff2) format(\"woff2\");font-display:swap}`
- `@font-face{font-family:\"Castle Num\";src:url(/static/fonts/oxanium.woff2) format(\"woff2\");font-weight:200 800;font-display:swap}`. The 'vrb' file name suggests a variable font; check its weight axis.
- Then `--font-display:\"Castle Display\", system-ui, sans-serif` and `--font-text:system-ui, sans-serif`.

Two cautions on fonts:
- system.css puts --font-display on every h1-h4 (system.css:179-186). If the wordmark face is caps-only or condensed, keep it for h1 and h2 page titles only, and override h3 with page CSS (cards already use the text face: system.css:499).
- The kit discourages the system font (layout-v4.md:258-260) and asks to keep the printed :root block (SKILL.md:224). For an offline PWA, self-hosted local fonts are the right departure. Note it on plan line 2.

Tailwind side (app pages), the same palette in one place:
- In tailwind.input.css @layer base: `:root{--c-bg:238 242 247;--c-surface:255 255 255;--c-ink:15 23 42;--c-line:...;--c-brand:11 95 176}` and `html.dark{--c-bg:11 15 23;--c-surface:20 26 38;--c-line:31 40 56;--c-brand:47 122 224}`.
- In tailwind.config.js theme.extend: colors {canvas:'rgb(var(--c-bg) / <alpha-value>)', surface, ink, line, brand}, fontFamily {display:['\"Castle Display\"', ...], num:['\"Castle Num\"', ...]}. Keep darkMode:'class' (tailwind.config.js:6). Existing dark: variants keep working while pages are rebuilt.
- body becomes `bg-canvas text-ink` (tailwind.input.css:15-17).

Theme colour:
- base.html:59-60 picks theme-color by media query, which ignores the class toggle. Update the meta in the toggle handler (base.html:218-223) to #0b5fb0 in light (to match the banner) and #0b0f17 or #141a26 in dark.
- Update manifest.json theme_color (#3b82f6) and background_color (#ffffff) to #0b5fb0 and #eef2f7.
- The kit's own rule is theme-color = --p-bg (system.md:224); the banner colour is the better fit for a PWA status bar.

Stale data-tone: tone() runs once, so after a toggle <html data-tone> is stale. That only matters for .footer--dark and .frame--cta/.footer--statement (system.css:564, 914). Either avoid those classes, or set dataset.tone in the toggle handler.

### system.js / motion behaviour
system.js (<kit>/assets/system.js) is a module with no globals that runs init() on DOMContentLoaded (system.js:584-601). In order:
- tone() (510-517): writes <html data-tone> from --p-bg, once.
- nav() (72-114): needs `.nav` containing `.nav__toggle`, `.nav__links`, `.nav__item`, `.nav__link` and optional `.nav__menu`. It toggles `.nav.is-open` and `body.nav-locked` (overflow hidden, system.css:752), swaps the toggle's SVG and aria-expanded, and inserts `.nav__expand` buttons for sub-menus. Escape closes the sheet or blurs focus inside the nav. A link tap closes the sheet, and the sheet closes at ≥1024px. The bar itself hides its links below 1024px (system.css:713-715).
- tabs() (116-149): every [role=tablist] with [role=tab][aria-controls].
- faq() (151-160): forces .faq details open.
- hours() and openNow() (181-247): dl.hours[data-tz] and [data-open-now].
- forms() (249-308): every form.form gets noValidate, validation on submit, aria-invalid, .field__error and a status line. It fetch()es to data-endpoint with Accept: application/json, calls form.reset() and shows data-sent. Without a data-endpoint it lets the native submit go through.
- peek() (311-343): [data-peek].
- actionbar() (344-384): `body > nav.actionbar`, driven by IntersectionObservers on the hero's .btn--primary.
- pictures() (522-547): after load, switches every img[loading=lazy] to eager, and red-outlines broken images (html[data-broken]).
- guards() (549-577): walks all text nodes and red-outlines bracketed text, 'placeholder' and .example addresses.
- visuals() (464-508): imports effects/fx.js and ui/ui.js only when [data-fx], [data-ui] or [data-glow] exist.
- moments() (578-582): imports moments/moments.js only when [data-moment] exists.
- Finally it sets html[data-ready=1].

motion.js (<kit>/assets/motion/motion.js) is a module. At load it adds document-wide click listeners for .loop-pause and .m-switch (251-268). init() (392-400) returns early when html[data-motion=off] (393), otherwise sets data-motion=\"\" and runs:
- enter() (331-389): `.hero[data-enter]` plus html.m-enter from the head line. It masks the h1 words, animates them, then restores the original nodes and adds .is-entered. It skips under reduced motion and in HeadlessChrome (shot(), line 32).
- nav() (36-55): `.nav .nav__links .nav__item`; adds .m-menu-open.
- tabs() (57-98): `.tabs[role=tablist]` or `.m-tabs`; adds a sliding .m-tab-ind.
- counts() (124-196): [data-m-count].
- loops() (237-249): [data-m-loop].
motion.css applies the hover and press layer to every .btn, .card, .link, `p a:not([class])`, `.footer ul a` and `.field input` as soon as it is linked (motion.css:1-6, 34-196), and holds the hero's words at opacity 0 during the 700ms m-enter window (motion.css:268-279). layout.js statically imports ../ui/ui.js (layout.js:29), so it always loads 41KB of ui.js.

Overlap with Castle's base.js (<castle>/app/static/js/base.js) and base.html's inline scripts:
- Theme toggle: Castle only (base.html:218-223 toggles html.dark and localStorage.theme). The kit has none. tone() doesn't follow the toggle, so data-tone goes stale.
- Mobile menu: both have one. Castle's is .mobile-menu-button / .mobile-menu with the hidden class (base.html:129-161, 201-204). The kit's is .nav__toggle / .nav.is-open. Never use both. If the shell drops .mobile-menu-button, base.html:202 throws and kills the rest of that script (flash auto-dismiss 207-215, theme toggle 218-223, user menu 226-241).
- User dropdown: Castle only (base.html:225-241, #userDropdownButton/#userDropdown). The kit's hover mega menus (.nav__menu, system.css:693-704) are unrelated.
- Flash: Castle's fixed role=status toast (base.html:165-183). The kit has no toast; its 'nothing else fixed' shell rule (layout-v4.md:29-31) would flag it on the landing page only when a flash is showing.
- CSRF: base.html:7-24 wraps window.fetch and adds X-CSRFToken to same-origin writes, and a test pins that code in base.html (tests/test_browser_resilience.js:252-275). system.js's form fetch would pass through it and through base.js's offline wrapper (base.js:232-276), which synthesises a 503 JSON response offline because system.js sends Accept: application/json. system.js would then show 'Not sent', which is acceptable, but its form.reset() and missing redirect/flash handling don't fit Castle's server-rendered POSTs. Never put class=\"form\" or data-endpoint on Castle forms.
- Offline indicator: base.js finds #nav-offline-indicator and #mobile-offline-indicator by id with null checks (base.js:14-27, 151-185). Any new header, landing included, must keep both ids to keep the feature. Without them base.js still runs safely.
- Service worker registration, update banner and fetch wrapper: base.js only (29-277). The update banner is built with Tailwind classes (base.js:122-135), so on a Tailwind-free landing page it is unstyled unless page CSS styles #update-banner. base.js must stay a classic script because it reads document.currentScript.dataset.appVersion (base.js:31).
- No two scripts own the same element, as long as the kit's script set only runs on the landing page.

### Weight and offline
Kit file sizes, in uncompressed bytes:
- Stylesheets: system.css 104,274; ui/cards.css 22,439; motion/motion.css 26,038; layout/layout.css 46,058; backgrounds/backgrounds.css 43,022; icons/icon.css 14,157; ui/base.css 16,378.
- Scripts: system.js 36,350; motion/motion.js 23,731; layout/layout.js 15,410, which pulls ui/ui.js 41,138; moments/moments.js 6,210 plus lib.js 10,957 plus the dealt moment; effects/fx.js 42,396, only with [data-fx].
- Castle: tailwind.css 62,490; fonts Richardson .otf 8,976 and oxanium-vrb.ttf 43,112.

What that means on the landing page:
- The six stylesheets start.mjs prints (start.mjs:321-327) add up to about 256KB. perf.mjs measures transfer bytes (perf.mjs:60, 264) and FAILs CSS above 250 KiB (perf.md:17). Flask's dev server does not compress, so the full set alone FAILs locally, and with tailwind.css (about 318KB) it fails clearly. Production on Vercel static (vercel.json) is compressed.
- On the landing page, link only system.css, motion.css and layout.css (plus cards.css only if feature cards with panels are used). Drop backgrounds.css, since Castle has no CSS grounds, and icon.css, since there are no brand icons. Never ship tailwind.css on that page.
- Scripts come to about 130KB, under the 450KB WARN.

External requests:
- start.mjs brand and css print preconnects plus a render-blocking `<link rel=stylesheet href=https://fonts.googleapis.com/...>` (start.mjs:305-307). Every hero demo file loads Google Fonts too (e.g. hero-split.html:10-11).
- base.html already loads Popper from unpkg as a render-blocking head script (base.html:27).
- The service worker never caches cross-origin requests: it fetches them and falls back to handleFetchError (service-worker.js:217-226, 181-185). In an arena with weak Wi-Fi, a render-blocking Google Fonts CSS request stalls first paint until it times out, and the fonts are never available offline.
- Use no Google Fonts. Self-host both Castle fonts as woff2 with font-display:swap, preload them (perf.md:42), and move Popper to /static or defer it.

Service worker implications (<castle>/app/static/js/service-worker.js):
1. Only URLs listed in STATIC_ASSETS are cache-first (lines 11-31, 240-270). Everything else same-origin is network-only (272-274) and offline gets handleFetchError, which answers JS and CSS with a 200 `text/css` body (lines 181-185, 258-266). Kit scripts are ES modules, so an uncached system.js, motion.js or layout.js fails offline on a MIME error. A failed static import in layout.js (ui/ui.js) kills layout.js entirely. Every kit file the landing page loads, including dynamic imports (ui/ui.js, moments/moments.js, moments/lib.js, moments/<id>/moment.js), must be added to STATIC_ASSETS, with cache names and CACHE_VERSION bumped (lines 1-6).
2. The install step precaches CSS and JS under `?v=<timestamp>` URLs (lines 94-103), but the fetch handler uses caches.match(event.request) without ignoreSearch (line 243). Precached CSS and JS therefore never match the plain URL and only get cached after the first online fetch (248-255). This is an existing bug that kit files would inherit; fix with `caches.match(req, {ignoreSearch:true})` or by precaching the exact URLs.
3. Fonts and images are precached without the timestamp (line 98). But the match is `event.request.url.includes(asset)` (line 241), and the browser requests `Richardson%20Brand%20Accelerator.otf`, so a STATIC_ASSETS entry with spaces never matches. Rename the file, e.g. richardson-brand-accelerator.woff2.
4. HTML navigations are never cached (228-237); offline they get /offline.html (140-149). offline.html is standalone with inline styles (offline.html:1-12+), so it needs its own rebrand using only cached assets (fonts in STATIC_ASSETS, no CDN).
5. The tests pin service-worker behaviour: API calls are network-only, navigation never uses another session's cache, failed writes stay failures (tests/test_browser_resilience.js:29-53). Adding assets must not change those paths.

Other offline costs:
- system.js pictures() switches all lazy images to eager after load (system.js:522-547), which costs bandwidth on bad Wi-Fi. That is another reason not to load system.js on app pages.
- WebGL: zero contexts if the landing page avoids data-fx and deals a moment without WebGL (pass --contexts 0 to moments.mjs).
- The hero entrance holds the hero's words at opacity 0 for up to 700ms, until motion.js runs or the safety mark passes (motion.css:268-279; starter.html:60). On a slow network the words then fade in by CSS, so nothing stays hidden.

### Risks
- Loading system.css or motion.css on any Tailwind page silently breaks layouts: Tailwind grids collapse (system.css:205-206), `main > section` becomes 100svh (221-225), and .card, .btn, .link and .badge change look and hover (system.css:427-511, 482-487, 867; motion.css:157-169). Treat 'never on app pages' as a hard rule.
- Removing or renaming `.mobile-menu-button` without a null guard makes base.html:202 throw, which silently disables the flash auto-dismiss, the theme toggle and the user menu (base.html:207-241).
- Moving the CSRF IIFE out of base.html breaks tests/test_browser_resilience.js:252-260, which extracts it from that file by text.
- base.js must stay a classic script: as a module, document.currentScript is null and base.js:31 throws before service worker registration.
- On a Tailwind-free landing page, Tailwind's `hidden` class no longer hides #installPWA and #installMessage (index.html:32, 99; pwa-install.js:35-37), and the update banner built with Tailwind classes (base.js:122-135) is unstyled. Page CSS has to cover them.
- Offline, kit ES modules not listed in STATIC_ASSETS get a text/css fallback (service-worker.js:181-185, 258-266) and fail to load. A failed static import kills layout.js (layout.js:29).
- The Google Fonts links start.mjs prints (start.mjs:305-307) are render-blocking and never cached by the service worker (service-worker.js:217-226). At arenas this stalls first paint. Self-host the fonts.
- The service worker's `url.includes(asset)` match fails for 'Richardson Brand Accelerator.otf' because of percent-encoded spaces (service-worker.js:241). Rename the font file.
- Existing service worker bug: CSS and JS precached with ?v=timestamp never match plain requests (service-worker.js:94-103 vs 243), so 'precached' assets aren't actually available offline until fetched once online.
- The gate only checks light mode (headless Chrome has no localStorage.theme; base.html:29), so dark-mode contrast must be checked by hand.
- start.mjs brand gives dark-mode buttons near-black text on #2f7ae0, because white is only about 4.2:1 (start.mjs:171, 182-183). The team must accept that or darken the blue.
- If the Richardson wordmark face is caps-only, putting it on --font-display applies it to every h1-h4 (system.css:179-186), against the kit's no-caps rule (system.md:58-59). Limit it to page titles.
- Arming the gate creates <castle>/.taste-skill/ (and shots/), and neither is in .gitignore. Once the skill is invoked, its Stop hook blocks the main session until PASS, OPEN or `gate.mjs --done` (SKILL.md:14-19; gate.md:84-105).
- Editing any copied kit file to fix a conflict is a hard kit-edited FAIL that cannot be waived (gate.md:42-45). Fix conflicts by where files are loaded, never by changing them.
- The landing page's logged-in variant shows three hero actions (index.html:21-29) against the kit's limit of two (copy.md:50). The gate never sees it because headless Chrome is logged out, so keep that variant on the app shell via conditional extends.
- The kit's 'nothing else fixed or sticky' shell rule (layout-v4.md:29-31) conflicts with the install FAB, flash toast and update banner. They are hidden by default, but when shown on a 390px phone they may trip collide or tap-size in manual checks.
- system.css's global reduced-motion rule (system.css:1309-1313) and motion.css's `p a:not([class])` rule (motion.css:86-95) reach Castle markup on any page that loads them. One more reason to keep the kit isolated.
