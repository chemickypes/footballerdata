# Splash / Auth Flow Redesign & Nav Restyle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a branded splash screen, split the "first access" experience into an independent personal-identity gate (with a new "Bentornato" returning-user screen) decoupled from the Asta Live PIN gate, and restyle the 9-tab navigation (sidebar + bottom nav) into square "game mode tile" buttons — all within the existing vanilla HTML/CSS/JS `web/app.py` template on branch `ui-glowup`.

**Architecture:** Three additive, independently-testable front-end changes layered onto the existing `init()` boot sequence in `web/app.py`'s inline `<script>`: (1) a new full-screen splash overlay shown for a fixed timer before any gate runs; (2) a new "Bentornato" panel that becomes the default early-return branch of `maybeStartIdentityGate()` when a profile is already stored, leaving the existing `#splashIdentityGate` untouched as the "no profile yet" branch; (3) a CSS-only restyle of `.sidebar-nav-btn` and `.nav-item` (no rename of the 9 tab ids/labels/icons already in place). No backend/Python change, no new files beyond CSS/JS already inline in `web/app.py`.

**Tech Stack:** Vanilla HTML/CSS/JS embedded in `web/app.py` (Flask `HTML_TEMPLATE` string), Font Awesome (already loaded), existing Officina Vittoriana CSS custom properties (`--officina-gold`, `--officina-ink`, `--officina-brass-dark`, `--officina-shadow`, `--maestro-z`).

## Global Constraints

- Work happens on branch `ui-glowup`, worktree `/Users/a409835/Documents/myProjects/fantaofficina/.worktrees/ui-glowup` — do NOT touch `main`.
- No new frontend framework or build step — everything stays inline vanilla HTML/CSS/JS in `web/app.py`.
- No new localStorage keys beyond what's specified in each task — reuse `fanta_active_profile_id`, `fanta_session_auth`, `fanta_maestro_intro_done` exactly as named.
- No emoji anywhere in new UI — Font Awesome icons only (confirm via `grep -n "font-awesome\|fa-solid" web/app.py` before adding any icon; reuse the existing CDN `<link>`, do not add a new one).
- No change to `LEAGUE_PIN`/`ADMIN_PIN` semantics, `is_participant`/`is_admin` server logic, or any Python file — this plan is 100% `web/app.py` template/inline-script/inline-CSS.
- No change to `live_bridge/`, `fantalab_room_id`, `fantalab_shard`.
- All 9 existing tabs (`draft`, `targets`, `strategy`, `rosters`, `listone`, `ai`, `lineup`, `audit`, `trades`) must remain reachable, same order, same `switchTab()` calls, same `id="sideNav-*"` / `id="botNav-*"` naming convention — no renaming, no removal, no reorg into macro-areas.
- Reuse existing CSS custom properties (`:root` block) and existing `cubic-bezier`/animation patterns as the styling foundation; extend, don't replace the Officina Vittoriana theme.
- Baseline test suite: `pytest -q` (via `/Users/a409835/library/python/3.9/bin/pytest -q` — this environment's only pytest install) must report `89 passed, 1 pre-existing unrelated error` unchanged after every task (this is a frontend-only plan; if any task somehow changes that count, treat it as a regression to investigate, not to ignore).
- Manual verification method: fetch the rendered page via `curl` or serve `web/app.py` locally and use headless Playwright (already available from prior session work in `/tmp/pwtest`, or reinstall via `npm install playwright && npx playwright install chromium` if unavailable) to check for zero console/page errors and to screenshot the new screens.
- Commit after every task with a clear `feat:`/`fix:` message and the required Co-authored-by trailer.

---

### Task 1: Branded splash screen (logo + spinner + fixed timer)

**Files:**
- Modify: `web/app.py` — add CSS block (near the existing `.splash-gate` rules, e.g. after line ~3399's `.splash-team-card__meta` block), add HTML markup (immediately after `<body>` at line 3458, before `#splashIdentityGate`), add JS (near `maybeStartIdentityGate()` around line 4942, and one line in `init()` around line 5748-5768).
- Test: manual Playwright smoke test (no Python test changes — this is pure front-end markup/timer logic).

**Interfaces:**
- Consumes: nothing from other tasks (this is the first, independent layer).
- Produces: a new DOM element `#appBootSplash` and a JS function `runBootSplash(onComplete)` that Task 2 will call from `init()` in place of the current direct `maybeStartIdentityGate()` invocation. `onComplete` is a zero-arg callback invoked once the fixed ~1.2s timer elapses and the splash has faded out.

- [ ] **Step 1: Add the splash screen CSS**

Insert this block into `web/app.py` right after the `.splash-team-card__meta` rule (search for `.splash-team-card__meta {` to locate it):

```css
        #appBootSplash {
            position: fixed;
            inset: 0;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 18px;
            background:
                radial-gradient(circle at 50% 20%, rgba(198,154,76,0.20) 0%, transparent 60%),
                linear-gradient(180deg, #1a130d 0%, #0e0906 100%);
            transition: opacity 0.4s ease;
        }
        #appBootSplash.fade-out {
            opacity: 0;
            pointer-events: none;
        }
        .boot-splash__logo {
            font-family: 'Outfit', sans-serif;
            font-size: clamp(1.6rem, 5vw, 2.4rem);
            font-weight: 800;
            letter-spacing: 0.02em;
            color: var(--officina-gold);
            text-shadow: 0 0 24px rgba(242,193,78,0.35);
        }
        .boot-splash__spinner {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            border: 3px solid rgba(198,154,76,0.25);
            border-top-color: var(--officina-gold);
            animation: boot-splash-spin 0.9s linear infinite;
        }
        @keyframes boot-splash-spin {
            to { transform: rotate(360deg); }
        }
        .boot-splash__version {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            color: var(--officina-muted);
        }
```

- [ ] **Step 2: Add the splash screen HTML markup**

Insert this immediately after the `<body>` tag (search for `<body>` — it currently appears once at line ~3458, right before `<div id="splashIdentityGate"`):

```html
    <div id="appBootSplash">
        <div class="boot-splash__logo">La FantaOfficina</div>
        <div class="boot-splash__spinner" aria-hidden="true"></div>
        <div class="boot-splash__version">v.1.00</div>
    </div>
```

- [ ] **Step 3: Add the `runBootSplash` JS function**

Insert this function right before `maybeStartIdentityGate()` (search for `function maybeStartIdentityGate()`):

```javascript
        function runBootSplash(onComplete) {
            const splash = document.getElementById('appBootSplash');
            if (!splash) {
                onComplete();
                return;
            }
            setTimeout(() => {
                splash.classList.add('fade-out');
                setTimeout(() => {
                    splash.style.display = 'none';
                    onComplete();
                }, 400); // matches the 0.4s CSS transition above
            }, 1200);
        }
```

- [ ] **Step 4: Wire `runBootSplash` into `init()`**

In `init()` (search for `async function init() {`), find this existing line:

```javascript
            maybeStartIdentityGate();
```

Replace it with:

```javascript
            runBootSplash(() => maybeStartIdentityGate());
```

- [ ] **Step 5: Verify no Python/backend regression**

Run: `cd /Users/a409835/Documents/myProjects/fantaofficina/.worktrees/ui-glowup && /Users/a409835/library/python/3.9/bin/pytest -q`
Expected: `89 passed, 1 warning, 1 error` (same pre-existing baseline as before this task).

- [ ] **Step 6: Manual visual/console verification**

Start the Flask app locally (check `web/app.py`'s bottom for how it's run, e.g. `python3 web/app.py` or via an existing dev script — inspect `if __name__ == "__main__":` block at the bottom of `web/app.py` for the exact command and port), then use a headless Playwright script to load the page and confirm:
- Zero `pageerror` events.
- `#appBootSplash` is visible immediately, then disappears (`display: none` or removed from flow) after ~1.6s total (1.2s timer + 0.4s fade).
- Screenshot showing "La FantaOfficina" wordmark + spinner + "v.1.00".

- [ ] **Step 7: Commit**

```bash
cd /Users/a409835/Documents/myProjects/fantaofficina/.worktrees/ui-glowup
git add web/app.py
git commit -m "feat: add branded boot splash screen with fixed timer

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: "Bentornato" returning-user screen (decoupled from PIN gate)

**Files:**
- Modify: `web/app.py` — add CSS (reuse existing `.splash-gate`/`.splash-gate__panel` shared rules), add HTML (new `#bentornatoGate` element, sibling of `#splashIdentityGate`, inserted right after it), modify JS (`maybeStartIdentityGate()` function body, plus two new functions).

**Interfaces:**
- Consumes: `runBootSplash` (Task 1) calls `maybeStartIdentityGate()` as its `onComplete` — no signature change needed, Task 2 only changes what `maybeStartIdentityGate()` does internally.
- Consumes existing globals: `activeProfileId` (number), `hasStoredProfile` (boolean), `auctionState.teams` (array of `{id, name, ...}` — same shape used by `renderSplashTeamGrid()`), `showSplashIdentityGate()`, `hideSplashIdentityGate()`, `escapeHTML()` (all already defined earlier in the same script — do not redefine them).
- Produces: `showBentornatoGate()`, `hideBentornatoGate()`, `handleNotYouClick()` — new functions later tasks do not depend on, but must exist with these exact names since this task's own steps reference them.

- [ ] **Step 1: Add the Bentornato gate CSS**

The Bentornato gate reuses the shared `.splash-gate` / `.splash-gate__panel` / `.splash-gate__eyebrow` / `.splash-gate__title` / `.splash-gate__copy` rules already defined (search for `.splash-gate,` — these are shared selectors with `.maestro-intro`). Add only the gate-specific button/link styling by inserting this block right after the `.splash-team-card__meta` rule (same insertion point used in Task 1 — insert Task 2's CSS immediately below Task 1's, so search for `.boot-splash__version {` from Task 1 and add this block right after its closing brace):

```css
        .bentornato-gate__actions {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: 12px;
            margin-top: 6px;
        }
        .bentornato-gate__continue {
            padding: 12px 28px;
        }
        .bentornato-gate__not-you {
            background: none;
            border: none;
            color: var(--officina-muted);
            font-size: 0.82rem;
            text-decoration: underline;
            cursor: pointer;
            padding: 4px 0;
        }
        .bentornato-gate__not-you:hover {
            color: var(--officina-gold);
        }
```

- [ ] **Step 2: Add the Bentornato gate HTML markup**

Insert this immediately after the closing `</div>` of `#splashIdentityGate` (search for `<div id="splashIdentityGate"` and find its matching closing `</div>` — it is the block containing `<div id="splashTeamGrid" class="splash-team-grid"></div>` followed by two closing `</div>` tags):

```html
    <div id="bentornatoGate" class="splash-gate" style="display:none;">
        <div class="splash-gate__backdrop"></div>
        <div class="splash-gate__panel">
            <div class="splash-gate__eyebrow"><i class="fa-solid fa-compass-drafting"></i> Officina Vittoriana</div>
            <h1 class="splash-gate__title" id="bentornatoTitle">Ciao! Bentornato.</h1>
            <p class="splash-gate__copy">Il tuo profilo locale è già configurato su questo browser. Prosegui per entrare nell'officina d'asta.</p>
            <div class="bentornato-gate__actions">
                <button class="btn btn-primary bentornato-gate__continue" onclick="hideBentornatoGate()">
                    <i class="fa-solid fa-door-open" style="margin-right:6px;"></i> Entra nell'officina
                </button>
                <button class="bentornato-gate__not-you" onclick="handleNotYouClick()">Non sei tu?</button>
            </div>
        </div>
    </div>
```

- [ ] **Step 3: Add the JS functions and update `maybeStartIdentityGate()`**

Add these two new functions right after `hideSplashIdentityGate()` (search for `function hideSplashIdentityGate() {` and insert after its closing brace):

```javascript
        function showBentornatoGate() {
            const gate = document.getElementById('bentornatoGate');
            if (!gate) return;
            const teams = (auctionState && auctionState.teams) || [];
            const team = teams.find(t => t.id === activeProfileId);
            const teamName = team ? team.name : `Squadra ${activeProfileId}`;
            const titleEl = document.getElementById('bentornatoTitle');
            if (titleEl) titleEl.textContent = `Ciao! Bentornato, ${teamName}.`;
            gate.style.display = 'flex';
            document.body.classList.add('app-locked');
        }

        function hideBentornatoGate() {
            const gate = document.getElementById('bentornatoGate');
            if (!gate) return;
            gate.style.display = 'none';
            document.body.classList.remove('app-locked');
        }

        function handleNotYouClick() {
            hideBentornatoGate();
            showSplashIdentityGate();
        }
```

Then replace the body of `maybeStartIdentityGate()` (search for `function maybeStartIdentityGate() {`) from:

```javascript
        function maybeStartIdentityGate() {
            if (hasStoredProfile) {
                hideSplashIdentityGate();
                return;
            }
            const loginModal = document.getElementById('sessionLoginModal');
            if (loginModal && loginModal.style.display !== 'none') {
                // PIN gate is currently showing; defer splash gate until it is dismissed.
                hideSplashIdentityGate();
                return;
            }
            showSplashIdentityGate();
        }
```

to:

```javascript
        function maybeStartIdentityGate() {
            const loginModal = document.getElementById('sessionLoginModal');
            const pinModalOpen = !!(loginModal && loginModal.style.display !== 'none');

            if (pinModalOpen) {
                // PIN gate (Asta Live access) takes precedence when already open;
                // defer both the returning-user and first-access panels until it closes.
                hideSplashIdentityGate();
                hideBentornatoGate();
                return;
            }

            if (hasStoredProfile) {
                hideSplashIdentityGate();
                showBentornatoGate();
                return;
            }

            hideBentornatoGate();
            showSplashIdentityGate();
        }
```

- [ ] **Step 4: Verify no Python/backend regression**

Run: `cd /Users/a409835/Documents/myProjects/fantaofficina/.worktrees/ui-glowup && /Users/a409835/library/python/3.9/bin/pytest -q`
Expected: `89 passed, 1 warning, 1 error` (unchanged baseline).

- [ ] **Step 5: Manual verification of both branches**

Using headless Playwright against the locally-served app:
- **First-access branch:** clear `localStorage` entirely, reload — confirm `#splashIdentityGate` (team picker) shows after the splash, `#bentornatoGate` stays hidden.
- **Returning-user branch:** with `localStorage['fanta_active_profile_id']` already set (e.g. set it manually via `page.evaluate` or by completing team selection once), reload — confirm `#bentornatoGate` shows with the correct team name interpolated, and `#splashIdentityGate` stays hidden.
- **"Non sei tu?" flow:** from the Bentornato screen, click "Non sei tu?" — confirm `#bentornatoGate` hides and `#splashIdentityGate` (team picker) shows, and confirm `localStorage['fanta_active_profile_id']` is still present (not cleared) until a new team is actually selected.
- **PIN gate precedence:** confirm that if `#sessionLoginModal` is open (e.g. force it open before calling `maybeStartIdentityGate()`), neither `#splashIdentityGate` nor `#bentornatoGate` shows.
- Confirm zero console/page errors in all four scenarios.

- [ ] **Step 6: Commit**

```bash
cd /Users/a409835/Documents/myProjects/fantaofficina/.worktrees/ui-glowup
git add web/app.py
git commit -m "feat: add Bentornato returning-user gate, decouple identity gate from PIN gate

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Restyle sidebar + bottom nav as square "game mode" tiles

**Files:**
- Modify: `web/app.py` — replace the `.sidebar-nav-btn` CSS rule block (search for `.sidebar-nav-btn {`, currently at line ~2046) and the `.nav-item`/`nav.bottom-nav` CSS rule blocks (search for `.nav-item {`, currently at line ~2237, and its related `.nav-item.active`, `.nav-item::before`, `.nav-item__icon`, `.nav-item__label` rules through line ~2286). No HTML markup changes are needed — the 9 `<button class="sidebar-nav-btn" ...>` and 9 `<button class="nav-item" ...>` elements keep their exact `id`, `onclick`, icon class, and label text; only the CSS driving their visual appearance changes.

**Interfaces:**
- Consumes: nothing from Tasks 1-2 (purely additive CSS on pre-existing, unchanged markup).
- Produces: nothing consumed by later tasks — this is the final task in this plan.

- [ ] **Step 1: Replace `.sidebar-nav-btn` CSS with the square-tile style**

Find and replace this existing block (search for `.sidebar-nav-btn {` through the closing brace of `.sidebar-nav-btn.active`):

```css
        .sidebar-nav-btn {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 14px;
            border-radius: 8px;
            border: none;
            background: transparent;
            color: var(--text-muted);
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            text-align: left;
            transition: all 0.15s ease;
        }
        .sidebar-nav-btn:hover {
            background: var(--surface-elevated);
            color: var(--text-main);
        }
        .sidebar-nav-btn.active {
            background: rgba(56, 189, 248, 0.15);
            color: var(--primary);
            font-weight: 700;
            border: 1px solid rgba(56, 189, 248, 0.4);
        }
```

with:

```css
        .sidebar-nav-btn {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            justify-content: center;
            gap: 8px;
            padding: 14px;
            aspect-ratio: 1 / 1;
            min-height: 74px;
            border-radius: 12px;
            border: 1px solid rgba(198,154,76,0.16);
            background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(0,0,0,0.10));
            color: var(--text-muted);
            font-size: 0.82rem;
            font-weight: 700;
            cursor: pointer;
            text-align: left;
            transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease, color 0.18s ease;
        }
        .sidebar-nav-btn i {
            font-size: 1.4rem !important;
        }
        .sidebar-nav-btn:hover {
            transform: translateY(-2px);
            border-color: rgba(198,154,76,0.4);
            color: var(--text-main);
        }
        .sidebar-nav-btn.active {
            border-color: var(--officina-gold);
            box-shadow: inset 0 0 0 1px rgba(242,193,78,0.25), 0 0 20px rgba(242,193,78,0.16);
            color: var(--officina-gold);
        }
```

Also change the `.sidebar-nav` container (search for `.sidebar-nav {` — the parent flex column holding these buttons) from a single-column list to a responsive tile grid. If `.sidebar-nav` currently reads:

```css
        .sidebar-nav {
            display: flex;
            flex-direction: column;
            gap: 4px;
            padding: 12px;
            flex: 1;
            overflow-y: auto;
        }
```

replace with:

```css
        .sidebar-nav {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            padding: 12px;
            flex: 1;
            overflow-y: auto;
        }
```

(If the exact current `.sidebar-nav` rule text differs from the assumed block above, locate it by searching `.sidebar-nav {` in `web/app.py`, keep `padding`, `flex`, and `overflow-y` values as they already are, and only change `display`/`flex-direction`/`gap` to the grid values shown.)

- [ ] **Step 2: Replace `.nav-item` (bottom nav) CSS with the square-tile style**

Find and replace this existing block (search for `.nav-item {` at the block starting the mobile bottom-nav rules, through `.nav-item.active .nav-item__icon`):

```css
        .nav-item {
            flex: 1;
            min-width: 0;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            gap: 4px;
            border: none;
            background: transparent;
            color: var(--officina-muted);
            text-decoration: none;
            font-size: 0.66rem;
            font-weight: 700;
            cursor: pointer;
            position: relative;
            transition: color 0.18s ease, transform 0.18s ease;
        }
        .nav-item::before {
            content: '';
            position: absolute;
            inset: 6px 4px 8px;
            border-radius: 12px;
            border: 1px solid transparent;
            background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(0,0,0,0.08));
            pointer-events: none;
        }
        .nav-item__icon {
            font-size: 1.08rem;
            line-height: 1;
        }
        .nav-item__label {
            max-width: 100%;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .nav-item.active {
            color: var(--officina-gold);
            transform: translateY(-1px);
        }
        .nav-item.active::before {
            border-color: rgba(198,154,76,0.5);
            box-shadow: inset 0 0 0 1px rgba(242,193,78,0.2), 0 0 18px rgba(242,193,78,0.18);
        }
        .nav-item.active .nav-item__icon {
            filter: drop-shadow(0 0 8px rgba(242,193,78,0.4));
        }
```

with:

```css
        .nav-item {
            flex: 1;
            min-width: 0;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            gap: 5px;
            margin: 6px 3px;
            border: none;
            background: transparent;
            color: var(--officina-muted);
            text-decoration: none;
            font-size: 0.62rem;
            font-weight: 700;
            cursor: pointer;
            position: relative;
            border-radius: 10px;
            transition: color 0.18s ease, transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
        }
        .nav-item::before {
            content: '';
            position: absolute;
            inset: 2px;
            border-radius: 10px;
            border: 1px solid rgba(198,154,76,0.14);
            background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(0,0,0,0.08));
            pointer-events: none;
        }
        .nav-item__icon {
            font-size: 1.3rem;
            line-height: 1;
        }
        .nav-item__label {
            max-width: 100%;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .nav-item.active {
            color: var(--officina-gold);
            transform: translateY(-2px) scale(1.04);
        }
        .nav-item.active::before {
            border-color: rgba(198,154,76,0.55);
            box-shadow: inset 0 0 0 1px rgba(242,193,78,0.25), 0 0 18px rgba(242,193,78,0.2);
        }
        .nav-item.active .nav-item__icon {
            filter: drop-shadow(0 0 8px rgba(242,193,78,0.4));
        }
```

- [ ] **Step 3: Verify no Python/backend regression**

Run: `cd /Users/a409835/Documents/myProjects/fantaofficina/.worktrees/ui-glowup && /Users/a409835/library/python/3.9/bin/pytest -q`
Expected: `89 passed, 1 warning, 1 error` (unchanged baseline).

- [ ] **Step 4: Manual visual verification at desktop and mobile widths**

Using headless Playwright:
- Load the app at a desktop viewport (e.g. 1440x900): screenshot the sidebar, confirm the 9 buttons render as a 2-column grid of square tiles with visibly larger icons than before, confirm the `active` tile (default `targets`) shows the gold border/glow.
- Load at a mobile viewport (e.g. 390x844): screenshot the bottom nav, confirm all 9 items fit without label truncation becoming illegible (allow ellipsis on longer labels per existing `.nav-item__label` rule, but verify none of the 9 labels overflow the tile visibly), confirm tapping between tabs updates the `active` tile correctly (reuse the existing `switchTab()` clicks from prior smoke tests).
- Click through all 9 tabs (`draft`, `targets`, `strategy`/via `targets`, `rosters`, `listone`, `ai`, `lineup`, `audit`, `trades`) on both viewports, confirm zero console/page errors and each tab's content becomes visible (non-blank).

- [ ] **Step 5: Commit**

```bash
cd /Users/a409835/Documents/myProjects/fantaofficina/.worktrees/ui-glowup
git add web/app.py
git commit -m "feat: restyle sidebar and bottom nav as square game-mode tiles

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Post-Plan Verification Checklist

After all 3 tasks are complete:

1. Run `/Users/a409835/library/python/3.9/bin/pytest -q` one final time — confirm `89 passed, 1 warning, 1 error`.
2. Full Playwright walkthrough from a clean `localStorage`: splash (Task 1) → team picker (`#splashIdentityGate`, existing) → reload → Bentornato screen (Task 2) → "Non sei tu?" round-trip → all 9 tabs reachable via the restyled nav (Task 3) on both desktop and mobile viewports → zero console errors throughout.
3. Confirm the PIN gate (`#sessionLoginModal`) for Asta Live is functionally unchanged — log in with PIN `2026`, confirm `is_participant`/admin flows still work exactly as before this plan.
4. Confirm no emoji were introduced anywhere in the touched CSS/HTML/JS (`grep -n` for common emoji ranges is unreliable in bash; instead visually confirm via the screenshots from Steps above).
5. Report to the user which items from the design spec's "Out of Scope" section remain deliberately untouched (5-tab reorg, server-side accounts, Scambi tab redesign) so expectations stay aligned.
