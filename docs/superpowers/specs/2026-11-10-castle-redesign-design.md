# Castle redesign: design

Date: 2026-11-10
Status: approved by the team, 2026-11-10
Appendix: [`2026-11-10-castle-redesign-contract.md`](2026-11-10-castle-redesign-contract.md). It lists every hook each page must keep, verified page by page.

## 1. Intent

Team 334 does not like how Castle looks after the October restyle (commits 69c4a2f to 2ae7b64). They gave three reasons, in their own words:

- **"Too cramped on the phone."** Scouters use Castle on phones in the stands at competitions. That is the main use.
- **"The color and UI don't look that clean and smooth."** Today's look is a neutral zinc grey with Tailwind blue and the system font. It reads as a generic template.
- **"Tailor to our team logo theme."** That means two logos. The Castle logo is black and white: a shield, a castle and the CASTLE wordmark (`app/static/logo.png`). The Team 334 TechKnights logo is a royal-blue gear (bthsrobotics.com/logo.png).

The look was chosen in the visual companion (mockups in `.superpowers/brainstorm/20273-1794266383/content/colors-v2.html`):

- **Light mode is "Banner".** A Team 334 blue top bar, a cool light page, white cards, black page titles in the CASTLE wordmark font, and grey subtitles. The team asked for black titles because white text on the blue was too bright.
- **Dark mode is "Night Watch".** Navy-black, steel-grey surfaces, bright 334 blue.
- **Match list on phones:** each match is a card showing Auto, Teleop and Climb. Approved.

They chose **approach C**: rebuild every page with fresh markup, using the taste-skill website-design kit.

## 2. Who uses it

- **Scouters (primary).** On phones in the stands, often one-handed, on bad arena Wi-Fi, and sometimes offline (Castle is a PWA with a service worker). Their key flows: the match scouting form (`scouting/add.html`), pit scouting, and the match list.
- **Strategy and drive team.** On laptops and tablets: leaderboards, team compare (lighthouse), auton paths, mock alliance selection, live match status.
- **Visitors and other FRC teams.** They land on `/` logged out.

## 3. Goals

1. One look across all 30 templates in both themes, matching the approved mockups.
2. Phone-first layouts with these rules:
   - 48px tap targets
   - 16px body and input text, and no text under 13px
   - 16px page gutters
   - no horizontal page scroll at 320px
   - a sticky full-width save bar on forms
   - tables become cards under 640px
3. Motion that feels smooth: buttons step on hover and press on tap, and links and linked cards answer the pointer. All of it uses the kit's timings and respects reduced motion.
4. The landing page (`/`, logged out) becomes a real taste-skill page that reaches `GATE: PASS` or `GATE: OPEN`.
5. Nothing breaks: scouting, the CSV export, the path canvas, offline mode, notifications and team management all behave exactly as before.

## 4. Non-goals

- No changes to routes, the database, Python form handling or features. The only Python change allowed is choosing a template for `/` (section 8).
- Known server quirks stay as they are, for example `auto_climb` not being saved on edit (listed in the appendix, scout-form group).
- Other pre-existing bugs are out of scope unless section 11 names them.
- No new third-party libraries on app pages.

## 5. Anti-goals

The redesign has failed, even if it looks right, if any of these happen:

- A scouter loses a match entry, or a form posts different field names or values.
- Phones keep the old CSS after deploy because the service worker cache was not bumped.
- Any kit CSS or JS loads on an app page. Section 6 explains why that silently breaks layouts.
- A render-blocking external font or CDN request is added. At an arena that stalls first paint.
- The CSV export, the canvas, or the paginated match list gets different DOM than its JS expects.

## 6. Approaches considered

| | Approach | Trade-off |
|---|---|---|
| A | Swap the colors at the root (remap Tailwind `gray`/`blue` in config), then fix phone layouts page by page | Smallest change and lowest risk, but the markup stays as it is and `zinc-900` would mean navy |
| B | Rename colors by role (`bg-surface`, `text-muted`) everywhere | Clean names; about 900 class edits across 30 templates and 10 JS files |
| **C (chosen)** | Rebuild every page with fresh markup on the website-design kit | Biggest change and best result; needs the hook contract to stay safe |

**What C means in practice (my call; recon forced it).** The kit cannot be loaded on Tailwind pages:

- Its `.grid > *{grid-column:1/-1}` collapses all 37 Tailwind grid layouts.
- `main > section` becomes a 100svh screen.
- `.btn`, `.card`, `.link` and `.badge` collide with Castle's classes.
- `system.js` takes over forms and makes lazy images eager.

C is therefore built in two ways:

- **Landing page (`/` logged out):** a real kit build in its own shell. It loads kit files only, no `tailwind.css`, and passes the kit's finish gate.
- **App pages (everything else):** fresh markup in Tailwind, the one system there. The kit's *rules* are ported into Castle's Tailwind tokens and components: spacing, type scale, radius, 48px controls, the form recipe, the card recipe, tabular numbers, hover and press timings, and the accessibility rules. No kit file loads.

Because every page is rewritten anyway, the new markup uses role names (`bg-canvas`, `bg-surface`, `text-muted`, `border-line`, `bg-brand`). This is B's benefit at no extra cost.

## 7. Visual system

### 7.1 Palette

These are Tailwind colors backed by CSS variables, defined once in `tailwind.input.css` on `:root` and `html.dark`, as `rgb(var(--c-x) / <alpha-value>)`.

| Token | Light (Banner) | Dark (Night Watch) | Use |
|---|---|---|---|
| `canvas` | `#eef2f7` | `#0b0f17` | page background |
| `surface` | `#ffffff` | `#141a26` | cards, inputs, menus |
| `surface-2` | `#f2f5f9` | `#1a2130` | stat tiles inside cards, table heads, hover rows |
| `line` | `#e3e8ef` | `#1f2838` | 1px borders and dividers |
| `ink` | `#0f1a2a` | `#e8ecf3` | text, page titles |
| `muted` | `#5b6675` | `#8b95a7` | subtitles, labels, help |
| `brand` | `#0b5fb0` | `#2a6fcf` | filled buttons, active states; white text passes (6.41 and 4.91) |
| `brand-ink` | `#0b5fb0` | `#5b9bf0` | blue text and links on surfaces (dark `#2f7ae0` fails at 4.13) |
| `brand-soft` | `#e6eef8` | `#1d2638` | tinted buttons (counter −), selected chips |
| `bar` | `#0b5fb0` | `#0b0f17` + bottom `line` | top bar |
| `alliance-red` / `-soft` | `#c22f2f` / `#fde8e8` | `#ff7b7b` / `#3a1719` | red alliance text and tint |
| `alliance-blue` / `-soft` | `#0b5fb0` / `#e3eefb` | `#7fb2f5` / `#13284a` | blue alliance text and tint |
| `success`, `warning`, `danger` | from Tailwind green-700, amber-700, red-600 | green-400, amber-400, red-400 | badges, toasts; builder checks 4.5:1 |

The contrast ratios in this table were computed on 2026-11-10; every listed text-on-ground pair is at least 4.5:1. The dark button blue (`#2a6fcf`) is slightly darker than the mockup's `#2f7ae0` so white labels pass AA. That is my call.

`theme-color`: `#0b5fb0` in light and `#0b0f17` in dark. The value is set in the theme toggle handler, because today's media-query metas ignore the class toggle. `manifest.json` gets `theme_color #0b5fb0` and `background_color #eef2f7`.

### 7.2 Type

- **Page titles:** the CASTLE wordmark face, `font-display` ("Richardson Brand Accelerator"). It is caps-style, so use it only for page titles (h1) and the brand mark, never for h2 to h4 or body text. Size `clamp(28px, 6vw, 40px)`.
- **Numbers:** Oxanium, `font-num`. Used for counters, stat values, match and team numbers, and leaderboard values, with `tabular-nums`. Where JS overwrites a text node, put `font-num` on the element JS writes into (appendix, lists-pit-team group).
- **Everything else:** the system UI stack.
  - Body and inputs 16px; labels 14px/500; help and badges at least 13px.
  - Section labels (Auto, Teleop, Endgame) are 12–13px, bold, uppercase and tracked, as in the approved mockup. Mockup approval beats the kit's no-caps rule. That is my call.
- **Font files:** rename only `Richardson Brand Accelerator.otf` to `castle-display.otf`, because the service worker matches with `url.includes()` against the percent-encoded request and the spaces break that match. Nothing else references it. Keep `oxanium-vrb.ttf` as named, because `app/team/team_utils.py:678-679` opens it by path to draw default team logos. Self-host both with `font-display: swap`, preload both in `base.html`, and add both to `STATIC_ASSETS`. No Google Fonts.

### 7.3 Shape, spacing, motion

- **Radius:** controls 12px; cards 20px (18 on phones); pills full.
- **Spacing:** Tailwind steps 1, 2, 3, 4, 6, 8, 12, 16 only. 24px between cards on desktop and 12px on phones. 16px gutters on phones, 24 on tablet, `max-w-7xl` on desktop.
- **Elevation:** light-mode cards get a soft shadow (`0 2px 10px rgb(15 26 42 / .07)`) and no border. Dark-mode cards get a 1px `line` border and no shadow. Both follow the mockup.
- **Motion:**
  - Press: `translateY(1px) scale(.985)` over 90ms.
  - Hover (fine pointers only): lift 1px over 150ms in and 120ms out, with the color stepping darker.
  - Linked cards lift 2px. Focus ring is 2px `brand`, offset 2px, with no transition.
  - Everything sits inside `motion-safe:`/`@media (hover:hover) and (pointer:fine)`.
  - No scroll animations on app pages.

### 7.4 Components (`tailwind.input.css` `@layer components`)

Keep the existing class names, because JS-built markup uses `.card`, `.card-header`, `.card-body`, `.section-title`, `.table`, `.badge-*`, `.btn*` and `.link` (appendix, analysis group). Restyle them and add new ones.

- `.page-header`, `.page-title` (display font), `.page-subtitle` (muted).
- `.card` / `.card-header` / `.card-body` as in 7.3.
- `.btn` sizes:
  - Every `.btn` is at least 48px tall, radius 12, 16px/600 type.
  - `.btn-sm` looks smaller but keeps a 44px hit area through padding or a pseudo-element.
  - `.btn-icon` is 48×48.
- `.btn` variants:
  - `-primary` is `brand`; `-secondary` is a surface with a line border; `-ghost`; `-danger`.
  - One filled primary per view.
- `.input`, `.label`, `.help`, `.checkbox`:
  - 48px fields at 16px on every width. Drop `sm:text-sm`, which stops iOS zoom on focus.
  - Errors: `aria-invalid` plus a `<p id>` under the field, linked by `aria-describedby`.
- `.badge` with variants gray, blue, red, green and amber, at 13px.
- `.counter` (new): replaces `global.css` `.counter-group`.
  - Top line: the label on the left and the value on the right (`font-num`, 24px).
  - Under it: one full-width row holding the step buttons that counter has today, in equal columns, 48px tall. Most fuel counters have six (−10, −5, −1, +1, +5, +10); ferried fuel has −1 and +1 only. At 320px six columns are still 44px wide.
  - Minus buttons are `brand-soft`, plus buttons are `brand`.
  - No step is removed: dropping the bulk steps would change how scouters count (section 4). The mockup showed a simplified − and + pair.
  - Keep every input `name`, id and step value the scouting JS uses (appendix, scout-form group).
- `.chips` (new): a three-up summary row of Match, Team and Alliance at the top of scouting forms.
- `.savebar` (new):
  - Sticky at the bottom, full width, 64px plus the safe-area inset, on the `canvas` ground with a top hairline.
  - The form gets bottom padding equal to its height, and `scroll-padding-bottom` is set so a focused field is never hidden behind it.
  - It holds the form's one primary button plus a `role="status"` line.
  - Forms keep their native POST. The server redirects with a flash, and the submit path, body encoding and field rules stay untouched. The status line says "Saving…" on submit. "Saved" is the success toast on the page the redirect lands on.
  - **Offline guard (new, small):** if `navigator.onLine === false` when Save is tapped, block the submit, keep every typed value, and show "You're offline. Not saved yet: tap Save again when you're back online." Today an offline save shows a browser error page and the entry is lost on Back. This adds a few lines to `scout/add.js`, `scout/edit.js` and the pit add/edit scripts, before their existing submit code.
- `.table-wrap` / `.table`: the desktop table.
- `.table-cards` (new): the phone card view of the **same `<table>` markup**.
  - Under 640px, `thead` is visually hidden.
  - Each `tr` becomes a card and each `td` a row showing a `data-label` name on the left and the value on the right.
  - The DOM is unchanged, so `row.cells[n]`, `td:nth-child(n)`, `closest('tr')`, `tbody tr` and the CSV export keep working.
  - Drop `whitespace-nowrap` inside cards.
  - This is how "tables become cards" is built everywhere (my call; the contract forbids replacing tables with divs).
- `.nav-link`, `.menu-item`, `.link`: restyled.
- `.toast-host` (new): one fixed bottom stack for the flash toast, the service worker update banner and `#notification-area`. It sits above `.savebar` when one is present, using `--savebar-h`, so nothing overlaps on phones.

The `hidden` class must keep winning over display classes, because JS toggles it on elements that also carry `flex` or `grid` (appendix, analysis and lists groups):

- Never give a JS-toggled element a responsive display utility (`sm:block`, `md:grid`).
- Never write a custom display class later in the cascade than `.hidden`.

## 8. Page shells

### 8.1 `base.html` (app shell)

- **Top bar:**
  - Light: a `bar` blue band with the white Castle mark (`logo-dark.png`) and the CASTLE wordmark in white.
  - Dark: a `#0b0f17` band with a bottom `line`.
  - Desktop: nav links on the bar, with active and hover states, plus the theme toggle and user menu.
  - Phone: the brand mark plus a 48px menu button that opens a full-screen sheet.
  - Keep `.mobile-menu-button`, `.mobile-menu`, `#userDropdown`, the offline indicators (`#nav-offline-indicator`, `#mobile-offline-indicator`), and every other id and class listed in the appendix (shell-auth group). `base.html:202` throws without a null guard if the menu button is renamed, which silently kills the theme toggle, the flash and the user menu.
- **Keep exactly:**
  - the CSRF meta and the inline CSRF fetch IIFE, text included, because `tests/test_browser_resilience.js:252-260` slices it by its comment text;
  - the theme head script and localStorage key `theme`;
  - `.dark` on `<html>`;
  - `base.js` as a classic script in `<body>` with `data-app-version`;
  - script order (CSRF wrapper first);
  - never adding a `<form>` before the content block (`auth/settings.js:79`);
  - no new database-dependent context, because error pages render through `base.html` with the database possibly down.
- **Remove** the unused render-blocking Popper `<script>` (nothing calls it). Preload the two fonts.
- **`main`:** `px-4 sm:px-6`, `max-w-7xl`, vertical rhythm 24px on phones and 32px on desktop. Update the edge-bleed scrollers (`-mx-4 px-4`) in `list.html`, `matches.html` and `pit-scouting.html` together with the gutter.
- **Footer:** one quiet line, as today.
- **Flash:** render through `.toast-host`.
  - Icons and colors by category: `error` gets danger, `success` gets success, and `warning` gets warning.
  - The uncategorized `message` category maps to neutral info, not the green success check.
  - Still only the last message (`messages[-1]`).

### 8.2 Landing page (`/`)

- `index.html` picks its parent template: `{% extends "base.html" if current_user.is_authenticated else "landing_base.html" %}`. This needs no Python change. If Jinja's conditional extends proves awkward, the fallback is to choose the template in the view (`app.py:97-98`); that is the builder's call.
- **Logged in:** a Castle home page on the app shell. It's a page title, a short greeting, and three large 48px+ action cards (Scout, Compare, Team) with icons. Each card is a linked card that lifts 2px.
- **Logged out:** a new `landing_base.html` that loads only kit files, copied unchanged into `app/static/assets/` (not the repo-root `assets/`).
  - Follow the taste-skill SKILL.md run: kind `software`, `data-type="software"`, `page-type` and `site-kind` metas.
  - Colors come from `start.mjs brand`, run once for light and once for dark; paste the dark output under `html.dark`.
  - Self-hosted fonts replace its Google Fonts link.
  - The blue top bar comes from a header-scoped override (`header.nav{--bg:#0b5fb0;...}`). `.nav--tone` would paint it near-black.
  - Deal the hero with `--has ui`. Deal one moment with `--contexts 0`, and the software one-liner for nav, footer, close, rhythm and buttons. Castle's logo replaces the dealt mark.
  - Page plan: the kit's software plan. Nav, a hero, one `app-frame` showing Castle's real scouting form as live HTML, two feature sections, FAQ, footer.
  - Copy follows the kit's rules. The h1 names the category ("Scouting app for FRC teams"), there's one hard fact on the first screen, and buttons are a verb plus an object ("Create an account", "Log in").
  - **Claims are limited to what the repo proves.** Allowed: open source under the MIT license (`LICENSE`), with a link to github.com/team334/Castle; installable and usable offline; match scouting with auto-path drawing; pit scouting; leaderboards; team comparison; mock alliance selection; built by Team 334. Not allowed without the team's word: "free", who can see whose data, usage numbers, supported seasons. The FAQ only answers questions these facts cover.
  - No photographs and no Team 334 gear logo: neither is in the repo. The hero is dealt with `--has ui` only.
  - `og:url` and the canonical domain stay as `base.html` has them today.
  - Keep `#installPWA`, `#installMessage` and `pwa-install.js`. Page CSS adds `.hidden{display:none}`, because `pwa-install.js` toggles the class and `tailwind.css` is absent.
  - Keep the theme head script, the manifest and icons, `base.js` (classic), and a `.theme-toggle`. The update banner gets page CSS.
  - Link only `system.css`, `motion.css`, `layout.css` (plus `cards.css` if used) and the JS the dealt parts need.
  - Kit files are **not** added to `STATIC_ASSETS`. `/` is a navigation, which the worker never serves from cache; offline it always shows `offline.html`, so the landing page never loads offline. Precaching them would make every scouter download about 350KB on each cache bump, and each entry is one more way to break the atomic install.
  - **App launches skip the marketing page:** `manifest.json` `start_url` becomes `/auth/login`. The login route already redirects logged-in users to `/` (`app/auth/routes.py:28-29`), so a signed-in scouter opens straight into the app home, and a signed-out one lands on Log in. No Python change. The landing page's kit nav still gets `env(safe-area-inset-top)` padding, for browsers that show it fullscreen.
  - Gate it on the fake-data preview server (section 12), logged out: `gate.mjs --start http://127.0.0.1:5000/ --kind software --category "Scouting app for FRC teams" --primary "Create an account"`. Never edit a copied kit file (a hard, unwaivable FAIL). The gate sees light mode only, so shoot dark mode by hand.
  - Add `.taste-skill/`, `shots/` and `.superpowers/` to `.gitignore`.

### 8.3 `offline.html`

This page is standalone with inline styles. Rebrand it with inline CSS in the new palette and both themes. It may use only assets that are in `STATIC_ASSETS` (the fonts are allowed).

## 9. Pages

Each page is rebuilt with the components above. Every hook in the appendix is kept.

| Group | Pages | What changes |
|---|---|---|
| Shell, auth | `base`, `index`, `404`, `429`, `500`, `offline`, `forgot-password`, `auth/login`, `register`, `profile`, `settings` | Shell as in 8.1. Auth pages: one centered card at most 440px wide, 48px fields, full-width primary button on phones. Keep the global handlers (`togglePassword`, `copyEmail`, `checkUsername`, `changePassword`, `confirmDeleteAccount`). Error pages: a big title in the display font, one action. |
| Scout form | `scouting/add`, `scouting/edit` | **Top card.** On add, the Event, Match and Team pickers stay as they are (same elements, ids and searchable-dropdown JS), restyled as one compact card, with the alliance shown as a badge once a team is picked. On edit, the read-only event, match and team inputs are styled as the mockup's chips, and the alliance radio pair is kept with its posting rules. Keep the existing tab names and tab markup (`.tab-button`/`.tab-content` with `hidden`). `.counter` rows (7.4). Selects and ratings at 48px. Save in `.savebar`. **Auto-path canvas toolbar:** the Draw tools (8 tools plus undo and redo) stay visible and wrap, each 44px+. The View and File buttons (reset, flip, rotate, save, load, read-only, clear) move into a native `<details>` "More tools" disclosure, so every button stays in the DOM with its id, `type=button` and `.active` styling. Keep `#autoPathContainer` visible with a fixed non-zero height when `new Canvas()` runs. Don't add a `.container` class anywhere (it would suddenly show the canvas toasts in odd places). |
| Lists, pit, team | `scouting/list`, `_match_list`, `matches`, `live-match-status`, `pit-scouting`, `pit-scouting-add`, `pit-scouting-edit`, `team/create`, `join`, `manage`, `settings`, `view` | Match list on phones: `.table-cards` with a per-table layout. The card shows the match and team on top, the alliance badge, three tiles (Auto fuel, Teleop, Climb) and Edit/Delete. The other cells are hidden until a "More" button in the actions cell sets `data-expanded` on its `tr`; then they show as label/value lines. That toggle is a few new lines in `scout/list.js`. The Teleop tile shows the cell's existing text (shifts as "a/b/c/d"), not a sum, because the CSV export reads that cell's text and `fuel-estimates.js` overwrites it. The same pattern (key cells, then More) applies to the 16-column leaderboard and the 10-column pit table. Cell order and count are untouched everywhere, so the CSV export is unchanged. Keep the partial JSON contract (`#teamDataContainer > .event-section[data-event-code] … tbody > tr.team-row`). Live status: alliance stripes use the tokens. Pit add and edit get the same form recipe and `.savebar`. Team manage: the member and assignment tables use `.table-cards`, and its modals become full-screen sheets on phones. |
| Analysis | `leaderboard`, `scouter-leaderboard`, `lighthouse`, `lighthouse/auton`, `mock-alliance-selection` | Leaderboards: `.table-cards` on phones, rank and value in `font-num`. Lighthouse and compare: the radar chart and team colors read CSS variables at draw time, and the existing `html.dark` observer re-themes them. Update the duplicated team color maps together (`lighthouse.html:154-160`, `compare.js:327`, `auton.js:13-20`). Auton and mock: move hand-written `.dark` CSS (`auton.css`, mock inline `<style>`) onto the tokens. |

JS that builds markup or sets colors gets the same restyle: `compare.js`, `auton.js`, `team/manage.js`, `mock-alliance-selection.js`, `playoff-bracket.js`, `scout/add.js`, `base.js` (update banner), `auth/settings.js`. Keep every dynamic class a full literal string (Tailwind purge), and keep the safelist for live-status alliance classes. The canvas (`Canvas.js`) stays white with its current stroke colors in both themes; that is my call, because paths are drawn on a field image.

## 10. Service worker and deploy

- Bump `CACHE_NAME`, `STATIC_CACHE_NAME`, `DYNAMIC_CACHE_NAME` and `PAGE_CACHE_NAME` from v14 to v15, and `CACHE_VERSION` from '15' to '16'. Bump them again in any later commit that changes a precached file before release.
- Update `STATIC_ASSETS`: the two fonts (one renamed), and removal of any deleted file. Kit files stay out (8.2). Install uses atomic `cache.addAll`, so a stale entry breaks offline mode.
  - The dead `index.css` and `register.css` may be deleted, but only together with their `STATIC_ASSETS` entries.
- **Version every CSS and JS URL the redesign changes** with the team's existing `?v=` habit, including `tailwind.css?v=16` in `base.html` (today it has none).
  - After a deploy, the *old* worker keeps serving its cached plain `tailwind.css` to the new HTML until the new worker installs. With a new query string the old worker's exact-URL `caches.match` misses and fetches fresh, so the first page after deploy is never unstyled.
  - The precache mismatch (CSS and JS precached under `?v=<timestamp>` and never matched) stays as it is: it's pre-existing, and switching to `ignoreSearch` would end the `?v=` habit. Assets are cached on their first online load, as today.
  - `tests/test_browser_resilience.js:29-53` pins the worker's API, navigation and write behavior and must still pass.
- Rebuild `tailwind.css` (`npm run build:css`) and commit it, as today.

## 11. Bugs fixed on the way

The rebuild touches these anyway, so it fixes them. Everything else in the appendix's pre-existing-bug lists stays out of scope.

- `#loadMoreMatches` never hides: preflight's `[hidden]` loses to `.btn{display:inline-flex}`. Fix it with the `hidden` class or a `[hidden]{display:none !important}` base rule.
- Flash icons: `warning` and `message` show the green success icon.
- An offline Save loses the entry (the guard in 7.4).

Out of scope, but recommended next: self-host or pin the unversioned CDN scripts. That means `localforage` (jsdelivr `@master`, render-blocking in the head of the scouting form, list, lighthouse and auton pages; if it fails at a venue, `Canvas.js:112` throws and the form posts without `_event_key`/`auto_path`), `sortablejs@latest` and the unpinned `chart.js`.

## 12. Verification

- `npm test` (node) and the Python tests (`.venv/Scripts/python.exe -m pytest tests`) pass.
- `npm run build:css` succeeds, and the built CSS contains every dynamic class (grep for the alliance and status literals).
- **Preview server with fake data.** The team's MongoDB is never written to. `tests/app_harness.py` is a test-client helper with empty mocked collections, so lists and leaderboards would render empty. Add a small dev-only script under `tests/` that starts the real app on 127.0.0.1 with the same mocks, a logged-in session, seeded in-memory matches, pit entries, team members and assignments, and canned TBA responses. It is not product code and never runs in production. The taste-skill gate runs against the same server, logged out.
- Screenshots of every page at 390, 768 and 1440, in light and dark, taken from that preview server with the Playwright CLI (`.playwright/cli.config.json`, Edge). Each set is read against this checklist:
  - nothing overflows at 320;
  - tap targets are 44px+;
  - text is at least 13px;
  - no overlap between the save bar, toasts and banners;
  - titles in the display font, numbers in Oxanium.
- Landing page: the taste-skill gate reaches `GATE: PASS` or `OPEN`, plus a manual dark-mode screenshot.
- Manual walkthrough on a phone-sized viewport:
  - add a match: counters (every step button), canvas draw, save, then the success toast shows on the list page;
  - tap Save with the network off: the submit is blocked, the offline message shows, and every typed value is still there;
  - edit a match;
  - the match list loads more, searches and exports CSV, and the column order matches;
  - pit add;
  - team manage: assign, change status, modals;
  - leaderboard sort;
  - lighthouse compare with a dark toggle redrawing the radar;
  - offline reload shows cached CSS and fonts.

## 13. Left to the builder

- Exact spacing within the rules above, icon choice (keep today's inline SVG set), and copy on app pages beyond labels.
- The order of page groups. The shell and components come first, because everything depends on them.
- How screenshots are scripted.
- How to split the work into commits. Assume `main` deploys to the live site: all work happens on a new branch, nothing is pushed or merged without the team saying so, and each page group is safe to ship on its own (its own cache and `?v=` bump, no half-restyled shared component).

## 14. Calls I made (please check)

1. Kit files load only on the landing page. App pages port the kit's rules into Tailwind (section 6).
2. Tables become cards through CSS on the same `<table>` markup, not by replacing them (7.4).
3. The dark-mode button blue is `#2a6fcf`, and dark-mode blue text is `#5b9bf0`, so both pass contrast (7.1).
4. Section labels stay uppercase and tracked, as in your approved mockup, even though the kit prefers sentence case (7.2).
5. The wordmark font is used for page titles and the brand only (7.2).
6. The path canvas stays white in dark mode (9).
7. The logged-in home page stays an app page; only the logged-out `/` is a kit marketing page (8.2).
8. Three small bugs get fixed along the way, including a new offline-save guard (7.4, 11).
9. Forms keep their native POST; "Saved" is the success toast after the redirect (7.4).
10. The installed app opens at `/auth/login`, so scouters never land on the marketing page (8.2).
11. Kit files stay out of the offline precache, and changed assets get `?v=` bumps instead of an `ignoreSearch` change (8.2, 10).
12. On the scouting form, the pickers stay as they are, and the canvas toolbar's View and File tools move into "More tools" (9).
13. `oxanium-vrb.ttf` keeps its name, because the team-logo generator opens it by path (7.2).
14. Counters keep every step button they have today, in one full-width row under the label (7.4).
15. Phone cards for the match list, leaderboard and pit table show the key cells, with the rest behind "More" (9).
16. The landing page only claims what the repo proves, with no photos and no gear logo (8.2).
17. Screenshots and click-throughs use a fake-data preview server; your MongoDB is never written to (12).
18. Work stays on a new branch, unpushed, with each page group shippable on its own (13).

## 15. Not part of this design

- **The `standalone/` wrapper.** It was a 37-line Toga WebView that opened castlescouting.com, plus six CI workflows that built it for Android, iOS, Linux, Flatpak, macOS and Windows. The team decided to remove it, because the PWA already covers install, offline and push. It is removed on its own branch (`chore/remove-standalone`), separately from this redesign, which neither depends on it nor tests inside it.
- **A security pass over the app.** Requested separately; runs on its own.
