# UI Glow-Up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the existing Flask single-file frontend into the approved Officina Vittoriana + Da Vinci experience, including onboarding, mascot guidance, compact bottom navigation, and both decorative and functional pitch treatments without changing backend behavior.

**Architecture:** `web/app.py` remains the source of truth for page structure, inline theme CSS, and app-level JS, while `web/static/css/tutorial.css` and `web/static/js/tutorial.js` absorb the mascot-aware tutorial extensions because they are the only established precedent for split-out frontend assets. Naming clarification: the spec’s “Tab Formazione” functional pitch work targets the real tactical pitch in `tab-rosters` (`renderRosterTab()` + `renderTacticalPitch()` + `renderPitchRow()`), not the placeholder `tab-lineup` solver card. The auction tab gets a separate decorative Da Vinci pitch component inserted between the active-lot block and the manual draft card so future live-preview logic can plug into a shared renderer without restructuring.

**Tech Stack:** Flask-rendered HTML in `web/app.py`, vanilla JavaScript, CSS custom properties, inline SVG, Font Awesome 6.5.1 CDN, existing `tutorial.js` / `tutorial.css`, `localStorage`, manual browser verification via Flask dev server on port 5050.

## Global Constraints

- Keep all behavior changes frontend-only; no backend, pipeline, ML, or PIN-authentication logic changes are in scope (spec section 7).
- Reuse and extend the existing spotlight tutorial system in `web/static/js/tutorial.js` and `web/static/css/tutorial.css`; do not introduce a second tutorial framework (spec sections 5 and 7).
- The Asta tab Da Vinci pitch is decorative-only in this iteration; structure it for future live-preview data, but do not implement preview functionality now (spec section 6.2).
- Keep identity single-user and `localStorage`-based via the existing `activeProfileId`; do not add accounts, backend state, or a new team data format (spec sections 3 and 7).
- Do not add any new JS/CSS framework, asset pipeline, or build step; stay within `web/app.py`, `web/static/js/tutorial.js`, and `web/static/css/tutorial.css` (spec section 7).
- Use Font Awesome 6.5.1 already loaded at `web/app.py:1794`; never substitute emoji for UI chrome.
- Preserve 8-tab bottom-nav density inside the existing `68px` bar in `web/app.py:2095-2231`; do not repeat the rejected oversized-journal-card treatment.
- Introduce new scoped Da Vinci role variables such as `--davinci-role-p`, `--davinci-role-d`, `--davinci-role-c`, and `--davinci-role-a`; do not modify the existing global `--role-*` tokens or `.pitch-jersey.role-*` classes used elsewhere.
- Treat `tab-rosters` as the real Formazione target because that is where the interactive tactical pitch, formation selector, HUD, and localStorage lineup logic already live (`web/app.py:3748-3838`, `7254-7598`).
- Every task must end with grep verification, Flask dev-server verification instructions using `cd web && python3 app.py` on port `5050`, a manual visual comparison against the approved PNG mockups, and a conventional commit with the required Copilot co-author trailer.

---

## File Structure

- `web/app.py` — monolithic Flask template containing the current root tokens (`1796-1818`), bottom-nav CSS (`2095-2231`), current pitch CSS (`2548-2680`), page body (`3159+`), Asta tab markup (`3332+`), session login modal (`4382+`), `activeProfileId` handling (`4542`, `4987`, `5071`, `7901`), `switchTab()` (`5447+`), roster pitch rendering (`7254+`, `7320+`, `7432+`, `7508+`). All structural HTML, shared theme tokens, splash screen DOM, mascot host element, Da Vinci SVG renderers, and pitch restyles land here.
- `web/static/js/tutorial.js` — existing walkthrough engine (`6-267`). Extend it to support Maestro copy, pose switching, mascot docking, and spotlight-compatible positioning without replacing `window.FantaTour`.
- `web/static/css/tutorial.css` — existing spotlight styles (`6-132`). Extend it with Officina Vittoriana tooltip skinning plus `.tour-maestro-*` classes that the JS can toggle.
- `docs/superpowers/plans/2026-09-07-ui-glowup-implementation.md` — this handoff document only.

### Task 1: Splash screen identity gate and first-time Maestro intro

**Files:**
- Modify: `web/app.py:1796-1818`
- Modify: `web/app.py:3159-3331`
- Modify: `web/app.py:4542-5079`
- Modify: `web/app.py:5447-5490`
- Test: manual verification via `curl`/browser against `/`

**Interfaces:**
- Consumes: existing `activeProfileId: number` localStorage contract in `web/app.py:4542`, existing team data loaded by the page, existing `switchTab(tabId: string): void` behavior.
- Produces: `showSplashIdentityGate(): void`, `hideSplashIdentityGate(): void`, `completeSplashTeamSelection(teamId: number): void`, `maybeShowMaestroIntro(): void`, DOM ids `splashIdentityGate`, `splashTeamGrid`, `maestroIntroOverlay`, and localStorage flag `fanta_maestro_intro_done` for later mascot tasks.

- [ ] **Step 1: Add failing grep checks for the new onboarding hooks**

```bash
grep -n "splashIdentityGate\|maestroIntroOverlay\|showSplashIdentityGate\|completeSplashTeamSelection\|fanta_maestro_intro_done" web/app.py
```

Expected: exit code `1` or no matches because the onboarding UI does not exist yet.

- [ ] **Step 2: Add new Officina onboarding tokens near the existing root variables**

Insert immediately after `--role-a: #ff2d75;` inside `web/app.py:1796-1818`:

```css
            --officina-brass: #c69a4c;
            --officina-brass-dark: #8a6329;
            --officina-gold: #f2c14e;
            --officina-leather: #241a12;
            --officina-leather-2: #2f2216;
            --officina-wood: #1a130d;
            --officina-ink: #ecdfc6;
            --officina-muted: #a68a6a;
            --officina-parchment: #e8d9b5;
            --officina-shadow: rgba(0, 0, 0, 0.62);
            --maestro-z: 1100;
```

- [ ] **Step 3: Add the splash gate and one-time intro overlays above the existing app layout**

Insert immediately after `<body>` at `web/app.py:3159`:

```html
    <div id="splashIdentityGate" class="splash-gate" style="display:none;">
        <div class="splash-gate__backdrop"></div>
        <div class="splash-gate__panel">
            <div class="splash-gate__eyebrow"><i class="fa-solid fa-compass-drafting"></i> Officina Vittoriana</div>
            <h1 class="splash-gate__title">Seleziona la tua Squadra</h1>
            <p class="splash-gate__copy">Scegli il tuo profilo locale per entrare nell'officina d'asta. Nessun account: il profilo resta salvato solo su questo browser.</p>
            <div id="splashTeamGrid" class="splash-team-grid"></div>
        </div>
    </div>

    <div id="maestroIntroOverlay" class="maestro-intro" style="display:none;">
        <div class="maestro-intro__scrim"></div>
        <div class="maestro-intro__card">
            <div class="maestro-intro__art" id="maestroIntroSprite" aria-hidden="true"></div>
            <div class="maestro-intro__content">
                <div class="maestro-intro__kicker"><i class="fa-solid fa-feather"></i> Il Maestro</div>
                <h2>Benvenuto nell'Officina</h2>
                <p>Inventore, cartografo del calcio e tua guida d'asta: ti mostrerò dove leggere prezzo equo, surplus e formazione senza cambiare la logica della tua lega.</p>
                <button class="btn btn-primary maestro-intro__btn" onclick="maybeShowMaestroIntro(true)">
                    <i class="fa-solid fa-door-open" style="margin-right:6px;"></i> Entra nella dashboard
                </button>
            </div>
        </div>
    </div>
```

- [ ] **Step 4: Add the actual splash and intro styling inside the main style block**

Append this block near the other layout components in `web/app.py` after the nav styles section:

```css
        .splash-gate,
        .maestro-intro {
            position: fixed;
            inset: 0;
            z-index: 1200;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }
        .splash-gate__backdrop,
        .maestro-intro__scrim {
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle at 28% -5%, rgba(198,154,76,0.22) 0%, transparent 55%),
                linear-gradient(180deg, #1a130d 0%, #0e0906 100%);
        }
        .splash-gate__panel,
        .maestro-intro__card {
            position: relative;
            width: min(960px, 100%);
            border-radius: 18px;
            border: 1px solid rgba(198,154,76,0.34);
            background: linear-gradient(180deg, #2a1e13, #1d140c);
            box-shadow: 0 28px 80px -30px var(--officina-shadow);
            padding: 28px;
            color: var(--officina-ink);
        }
        .splash-gate__eyebrow,
        .maestro-intro__kicker {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--officina-gold);
            margin-bottom: 10px;
        }
        .splash-gate__title,
        .maestro-intro__content h2 {
            margin: 0 0 10px;
            font-family: 'Outfit', sans-serif;
            font-size: clamp(1.8rem, 4vw, 2.6rem);
            color: #f4e7ca;
        }
        .splash-gate__copy,
        .maestro-intro__content p {
            margin: 0 0 20px;
            max-width: 640px;
            color: #d8c6a5;
            line-height: 1.6;
        }
        .splash-team-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px;
        }
        .splash-team-card {
            border: 1px solid rgba(198,154,76,0.28);
            border-radius: 14px;
            background: linear-gradient(180deg, #312214, #21160d);
            color: var(--officina-ink);
            padding: 18px 16px;
            text-align: left;
            cursor: pointer;
            transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
        }
        .splash-team-card:hover,
        .splash-team-card:focus-visible {
            transform: translateY(-2px);
            border-color: rgba(242,193,78,0.58);
            box-shadow: 0 14px 28px -22px rgba(242,193,78,0.9);
        }
        .splash-team-card__name {
            display: block;
            font-family: 'Outfit', sans-serif;
            font-size: 1rem;
            font-weight: 800;
            color: #f4e7ca;
            margin-bottom: 4px;
        }
        .splash-team-card__meta {
            display: block;
            font-size: 0.78rem;
            color: var(--officina-muted);
        }
        .maestro-intro__card {
            display: grid;
            grid-template-columns: 140px 1fr;
            gap: 20px;
            align-items: center;
        }
        .maestro-intro__art {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 140px;
            border-radius: 16px;
            background: radial-gradient(circle at 50% 30%, #3a2a19, #1b130c 75%);
            border: 2px solid var(--officina-brass);
        }
        .maestro-intro__btn {
            width: auto;
            padding: 12px 18px;
            border-radius: 10px;
        }
        @media (max-width: 680px) {
            .maestro-intro__card {
                grid-template-columns: 1fr;
                text-align: center;
            }
        }
```

- [ ] **Step 5: Wire the onboarding logic into the existing `activeProfileId` flow**

Add this JS near `let activeProfileId = ...` in `web/app.py:4542-5079`:

```javascript
        let hasStoredProfile = !!localStorage.getItem('fanta_active_profile_id');

        function renderSplashTeamGrid() {
            const wrap = document.getElementById('splashTeamGrid');
            if (!wrap) return;
            const teams = (auctionState && auctionState.teams) || [];
            wrap.innerHTML = teams.map((team, idx) => `
                <button class="splash-team-card" onclick="completeSplashTeamSelection(${team.id})">
                    <span class="splash-team-card__name">${team.name}</span>
                    <span class="splash-team-card__meta">Profilo locale #${idx + 1} · entra nell'officina</span>
                </button>
            `).join('');
        }

        function showSplashIdentityGate() {
            const gate = document.getElementById('splashIdentityGate');
            if (!gate) return;
            renderSplashTeamGrid();
            gate.style.display = 'flex';
            document.body.classList.add('app-locked');
        }

        function hideSplashIdentityGate() {
            const gate = document.getElementById('splashIdentityGate');
            if (!gate) return;
            gate.style.display = 'none';
            document.body.classList.remove('app-locked');
        }

        function maybeShowMaestroIntro(forceClose = false) {
            const overlay = document.getElementById('maestroIntroOverlay');
            if (!overlay) return;
            if (forceClose) {
                localStorage.setItem('fanta_maestro_intro_done', 'true');
                overlay.style.display = 'none';
                document.body.classList.remove('app-locked');
                return;
            }
            if (localStorage.getItem('fanta_maestro_intro_done') === 'true') return;
            overlay.style.display = 'flex';
            document.body.classList.add('app-locked');
        }

        function completeSplashTeamSelection(teamId) {
            activeProfileId = teamId;
            localStorage.setItem('fanta_active_profile_id', activeProfileId);
            hasStoredProfile = true;
            hideSplashIdentityGate();
            renderApp();
            maybeShowMaestroIntro();
        }
```

Also add this helper style anywhere once in CSS:

```css
        body.app-locked {
            overflow: hidden;
        }
```

- [ ] **Step 6: Call the onboarding gate only for first-time visitors and preserve the existing later login flows**

At the end of the initial app bootstrap path, add:

```javascript
        function maybeStartIdentityGate() {
            if (hasStoredProfile) {
                hideSplashIdentityGate();
                return;
            }
            showSplashIdentityGate();
        }
```

Then, after the first successful state render (where the page currently selects the default tab), call:

```javascript
            maybeStartIdentityGate();
```

And keep the two existing login/team-selection persistence points intact by appending only:

```javascript
                hasStoredProfile = true;
```

immediately after each existing `localStorage.setItem('fanta_active_profile_id', activeProfileId);` assignment at `web/app.py:4987` and `5071`.

- [ ] **Step 7: Verify markup and first-visit behavior hooks exist**

Run:

```bash
grep -n "splashIdentityGate\|maestroIntroOverlay\|showSplashIdentityGate\|completeSplashTeamSelection\|fanta_maestro_intro_done\|hasStoredProfile" web/app.py
```

Expected: all six identifiers appear with concrete line numbers.

- [ ] **Step 8: Verify rendered HTML from Flask contains the new gate**

Run:

```bash
cd web && python3 app.py
```

In a second terminal:

```bash
curl -s http://localhost:5050/ | grep -c "splashIdentityGate"
curl -s http://localhost:5050/ | grep -c "maestroIntroOverlay"
```

Expected: both commands print `1`.

- [ ] **Step 9: Manually compare onboarding against the approved mascot hero mockup**

Open `http://localhost:5050/` in a browser with a clean localStorage state and compare against `.superpowers/brainstorm/mockups-davinci-mascot/mascot-hero.png`. Confirm: warm brass/leather palette, character-select cards rather than generic modal inputs, one-time Maestro intro after first team selection, and automatic skip on reload once `fanta_active_profile_id` is present.

- [ ] **Step 10: Commit the onboarding task**

```bash
git add web/app.py
git commit -m "feat: add splash screen identity gate" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2: Officina Vittoriana bottom-nav and session gate restyle

**Files:**
- Modify: `web/app.py:2095-2231`
- Modify: `web/app.py:4382-4412`
- Modify: `web/app.py:4483-4510`
- Modify: `web/app.py:5447-5470`
- Test: manual verification via `curl`/browser against `/`

**Interfaces:**
- Consumes: `switchTab(tabId: string): void`, existing `.nav-item` buttons `#botNav-*`, existing `#sessionLoginModal` logic.
- Produces: refined `.bottom-nav`, `.nav-item`, `.nav-item__icon`, `.nav-item__label`, `.nav-item.active`, `.session-login-officina`, and `updateMaestroAmbientState(tabId: string): void` hook call site for later mascot persistence.

- [ ] **Step 1: Capture the pre-change nav selectors as a failing check for new structure**

```bash
grep -n "nav-item__icon\|session-login-officina\|updateMaestroAmbientState" web/app.py
```

Expected: no matches.

- [ ] **Step 2: Replace the nav CSS with the compact approved brass/leather treatment**

Replace the existing `nav.bottom-nav` and `.nav-item` definitions in `web/app.py:2095-2231` with:

```css
        nav.bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            display: flex;
            height: 68px;
            z-index: 1000;
            padding-bottom: env(safe-area-inset-bottom);
            background: linear-gradient(180deg, #241a11, #160f09);
            border-top: 2px solid var(--officina-brass-dark);
            box-shadow: 0 -10px 24px rgba(0, 0, 0, 0.32);
        }
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
        @media (max-width: 560px) {
            .nav-item {
                font-size: 0.62rem;
                gap: 3px;
            }
            .nav-item__icon {
                font-size: 1rem;
            }
        }
```

- [ ] **Step 3: Update the 8 bottom-nav buttons to use explicit icon/label spans**

For each button in `web/app.py:4483-4510`, convert this pattern:

```html
        <button class="nav-item" id="botNav-draft" onclick="switchTab('draft')">
            <i class="fa-solid fa-gavel"></i>
            <span>Asta</span>
        </button>
```

into this pattern (repeat for all 8 tabs, preserving ids and onclick handlers):

```html
        <button class="nav-item" id="botNav-draft" onclick="switchTab('draft')">
            <i class="fa-solid fa-gavel nav-item__icon"></i>
            <span class="nav-item__label">Asta</span>
        </button>
```

Use the existing semantic Font Awesome icons already present in the file; do not swap to emoji or larger art.

- [ ] **Step 4: Restyle the session PIN gate visually without touching its login logic**

Replace the outer `#sessionLoginModal` card styling block in `web/app.py:4382-4412` with this structure:

```html
    <div id="sessionLoginModal" class="modal-backdrop session-login-officina" style="display:none; z-index:99999;">
        <div class="modal-box session-login-officina__box">
            <div class="session-login-officina__crest"><i class="fa-solid fa-trophy icon-pulse"></i></div>
            <div class="modal-title session-login-officina__title">
                <span>Asta Live Condivisa</span>
            </div>
            <div class="session-login-officina__copy">
                Tutti i partecipanti sono sincronizzati in tempo reale sulla stessa asta. Seleziona la tua squadra e inserisci il PIN di accesso.
            </div>
            <div class="session-login-officina__field">
                <label>LA TUA FANTASQUADRA:</label>
                <select id="loginTeamSelect">
                    <!-- Dynamically populated -->
                </select>
            </div>
            <div class="session-login-officina__field">
                <label>PIN DI ACCESSO (LEGA O ADMIN):</label>
                <input type="password" id="loginPinInput" placeholder="Inserisci PIN (es. 2026)" onkeypress="if(event.key==='Enter') submitSessionLogin()">
                <div id="loginErrorMsg" style="display:none;"></div>
            </div>
            <button class="btn btn-primary session-login-officina__submit" onclick="submitSessionLogin()">
                <i class="fa-solid fa-bolt" style="margin-right:6px;"></i> Entra nell'Asta Live
            </button>
            <div class="session-login-officina__note">
                Con il <b>PIN Admin</b> hai accesso completo alla battuta, sniffer e reset sessione.
            </div>
        </div>
    </div>
```

Then add CSS:

```css
        .session-login-officina {
            background: rgba(7, 5, 3, 0.88);
            backdrop-filter: blur(12px);
        }
        .session-login-officina__box {
            max-width: 440px;
            text-align: center;
            padding: 28px 24px;
            border: 1px solid rgba(198,154,76,0.4);
            box-shadow: 0 0 45px rgba(198,154,76,0.2);
            background: linear-gradient(180deg, #2a1e13, #1d140c);
        }
        .session-login-officina__crest {
            font-size: 2.2rem;
            margin-bottom: 8px;
            color: var(--officina-gold);
        }
        .session-login-officina__title {
            justify-content: center;
            margin-bottom: 4px;
            font-family: 'Outfit', sans-serif;
            font-size: 1.35rem;
            font-weight: 800;
            color: #f4e7ca;
        }
        .session-login-officina__copy,
        .session-login-officina__note {
            font-size: 0.82rem;
            color: #d8c6a5;
            line-height: 1.45;
        }
        .session-login-officina__field {
            text-align: left;
            margin: 0 0 14px;
        }
        .session-login-officina__field label {
            display: block;
            margin-bottom: 5px;
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--officina-muted);
        }
        .session-login-officina__field select,
        .session-login-officina__field input {
            width: 100%;
            margin-bottom: 0;
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid rgba(198,154,76,0.22);
            background: #0f0b08;
            color: var(--officina-ink);
        }
        .session-login-officina__submit {
            width: 100%;
            padding: 12px;
            border-radius: 8px;
            margin-top: 6px;
        }
        .session-login-officina #loginErrorMsg {
            margin-top: 6px;
            font-size: 0.8rem;
            font-weight: 600;
            color: #f59a7d;
            text-align: center;
        }
```

- [ ] **Step 5: Reserve the `switchTab()` hook for global ambient updates**

Append this line inside `switchTab(tabId)` in `web/app.py:5447-5470` after the active classes are updated:

```javascript
            if (typeof updateMaestroAmbientState === 'function') updateMaestroAmbientState(tabId);
```

- [ ] **Step 6: Verify the nav and session gate hooks exist**

Run:

```bash
grep -n "nav-item__icon\|nav-item__label\|session-login-officina\|updateMaestroAmbientState" web/app.py
```

Expected: matches for all four identifiers.

- [ ] **Step 7: Verify rendered HTML keeps all eight nav items and the login gate**

Run:

```bash
cd web && python3 app.py
```

Then:

```bash
curl -s http://localhost:5050/ | grep -c 'id="botNav-'
curl -s http://localhost:5050/ | grep -c 'session-login-officina'
```

Expected: first command prints `8`; second prints `1`.

- [ ] **Step 8: Manually compare the nav density against the approved hero mockup**

Open the app and compare the bottom bar to `.superpowers/brainstorm/mockups-davinci-mascot/mascot-hero.png`. Confirm the bar still fits eight items inside the 68px footprint, uses brass/leather materials, highlights the active tab with subtle glow, and does not regress into oversized notebook-card tabs.

- [ ] **Step 9: Commit the nav/session restyle**

```bash
git add web/app.py
git commit -m "feat: restyle bottom navigation and session gate" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 3: Base Maestro sprite system and persistent ambient corner peek

**Files:**
- Modify: `web/app.py:3159-3331`
- Modify: `web/app.py:4542-5590`
- Test: manual verification via `curl`/browser against `/`

**Interfaces:**
- Consumes: `switchTab(tabId: string): void`, `maybeShowMaestroIntro(): void` from Task 1.
- Produces: `window.MAESTRO_SPRITES: Record<string,string[]>`, `renderMaestroSprite(containerId: string, pose?: string, scale?: number): void`, `ensureMaestroAmbient(): void`, `setMaestroPose(pose: 'neutral'|'greeting'|'pointing'|'thoughtful'): void`, `updateMaestroAmbientState(tabId: string): void`, DOM ids `maestroAmbient`, `maestroAmbientSprite`, `maestroAmbientBubble`.

- [ ] **Step 1: Prove the Maestro runtime does not exist yet**

```bash
grep -n "MAESTRO_SPRITES\|renderMaestroSprite\|maestroAmbient\|updateMaestroAmbientState" web/app.py
```

Expected: no matches.

- [ ] **Step 2: Add the single global ambient host element below the app shell**

Insert near the end of the body, before the tutorial script include at `web/app.py:8262`:

```html
    <button id="maestroAmbient" class="maestro-ambient" type="button" style="display:none;" onclick="FantaTour && FantaTour.start && FantaTour.start()">
        <span class="maestro-ambient__halo"></span>
        <span id="maestroAmbientSprite" class="maestro-ambient__sprite" aria-hidden="true"></span>
        <span id="maestroAmbientBubble" class="maestro-ambient__bubble">Occhio al surplus, giovane.</span>
    </button>
```

- [ ] **Step 3: Add the ambient mascot styling using the approved 64px footprint**

Insert into `web/app.py` CSS:

```css
        .maestro-ambient {
            position: fixed;
            right: 16px;
            bottom: 84px;
            z-index: var(--maestro-z);
            border: none;
            background: transparent;
            padding: 0;
            cursor: pointer;
            display: flex;
            align-items: flex-end;
            gap: 10px;
            color: inherit;
            filter: drop-shadow(0 6px 12px rgba(0,0,0,0.6));
        }
        .maestro-ambient__halo {
            position: absolute;
            inset: -8px auto auto -8px;
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(242,193,78,0.28), transparent 70%);
            animation: maestro-pulse 3s ease-in-out infinite;
        }
        .maestro-ambient__sprite {
            position: relative;
            z-index: 1;
            display: block;
            width: 64px;
            height: 96px;
        }
        .maestro-ambient__bubble {
            position: relative;
            z-index: 1;
            max-width: 180px;
            padding: 6px 11px;
            border-radius: 8px 8px 3px 8px;
            border: 1px solid var(--officina-brass-dark);
            background: linear-gradient(180deg, #efe2c1, #dcc79a);
            color: #4a3618;
            font-family: 'Cormorant Garamond', serif;
            font-style: italic;
            font-size: 0.9rem;
            white-space: nowrap;
        }
        @keyframes maestro-pulse {
            0%, 100% { transform: scale(0.9); opacity: 0.5; }
            50% { transform: scale(1.08); opacity: 1; }
        }
        @media (max-width: 640px) {
            .maestro-ambient__bubble {
                display: none;
            }
        }
```

- [ ] **Step 4: Add the approved 22×33-ish pixel-art sprite maps and renderer**

Insert this JS in `web/app.py` before tutorial bootstrapping:

```javascript
        window.MAESTRO_SPRITES = {
            neutral: [
                '..........CC..........','.........oooo.........','.......ooHHHHHHoo......','......oHHHHHHHHHHo.....','......oHHHhhHHhHHHo....','.....oHHHHHHHHHHHHo....','.....oHHHHHHHHHHHHo....','....obBBBBBBBBBBBBbo...','....oBLBBBBBBBBBBLBo...','...oBGGgBBBBBBBBGGgBo..','...oBGGgBBBBBBBBGGgBo..','....obBBBBBBBBBBBBbo...','.....oSSSSSSSSSSSSo....','.....oSSsSSSSSSsSSo....','.....oSooSSSSSSooSo....','.....oSooSSSSSSooSo....','.....oSSSSSssSSSSSo....','......oSSSSssSSSSo.....','......oWwsSSSSswWo.....','.....oWWWWwssWWWWWo....','....oWWWWWWWWWWWWWWo...','...oWWWWWWWWWWWWWWWWo..','...oWWWWwWWWWWWwWWWWo..','...oWWWWWWWWWWWWWWWWo..','....oWWWWWWWWWWWWWWo...','.....oWWWWWwwWWWWWo....','......oWWWWWWWWWWo.....','.......oWWWWWWWWo......','...RR..oWWWWWWWWo..RR..','.RRRRRRoWWWWWWWWoRRRRRR','RRRRRRRRoWWWWWWoRRRRRRR','RRrRRRLBRRRRRRRRBLRRrRR','RRrRRRRRRRRRRRRRRRRrRRR'
            ],
            greeting: [
                '..........CC..........','.........oooo.........','.......ooHHHHHHoo......','......oHHHHHHHHHHo.....','......oHHHhhHHhHHHo....','.....oHHHHHHHHHHHHo....','.....oHHHHHHHHHHHHo....','....obBBBBBBBBBBBBbo...','....oBLBBBBBBBBBBLBo...','...oBGGgBBBBBBBBGGgBo..','...oBGGgBBBBBBBBGGgBo..','....obBBBBBBBBBBBBbo...','.....oSSSSSSSSSSSSo....','.....oSSsSSSSSSsSSo....','.....oSooSSSSSSooSo....','.....oSooSSSSSSooSo....','.....oSSSSSssSSSSSo....','......oSSSSssSSSSo.....','......oWwsSSSSswWo.....','.....oWWWWwssWWWWWo....','....oWWWWWWWWWWWWWWo...','...oWWWWWWWWWWWWWWWWo..','...oWWWWwWWWWWWwWWWWo..','...oWWWWWWWWWWWWWWWWo..','....oWWWWWWWWWWWWWWo...','.....oWWWWWwwWWWWWo....','......oWWWWWWWWWWo..B..','.......oWWWWWWWWo..BB..','...RR..oWWWWWWWWo...B..','.RRRRRRoWWWWWWWWoRRRRRR','RRRRRRRRoWWWWWWoRRRRRRR','RRrRRRLBRRRRRRRRBLRRrRR','RRrRRRRRRRRRRRRRRRRrRRR'
            ],
            pointing: [
                '..........CC..........','.........oooo.........','.......ooHHHHHHoo......','......oHHHHHHHHHHo.....','......oHHHhhHHhHHHo....','.....oHHHHHHHHHHHHo....','.....oHHHHHHHHHHHHo....','....obBBBBBBBBBBBBbo...','....oBLBBBBBBBBBBLBo...','...oBGGgBBBBBBBBGGgBo..','...oBGGgBBBBBBBBGGgBo..','....obBBBBBBBBBBBBbo...','.....oSSSSSSSSSSSSo....','.....oSSsSSSSSSsSSo....','.....oSooSSSSSSooSo....','.....oSooSSSSSSooSo....','.....oSSSSSssSSSSSo....','......oSSSSssSSSSo.....','......oWwsSSSSswWo.....','.....oWWWWwssWWWWWo....','....oWWWWWWWWWWWWWWoBBB','...oWWWWWWWWWWWWWWWWo.B','...oWWWWwWWWWWWwWWWWo..','...oWWWWWWWWWWWWWWWWo..','....oWWWWWWWWWWWWWWo...','.....oWWWWWwwWWWWWo....','......oWWWWWWWWWWo.....','.......oWWWWWWWWo......','...RR..oWWWWWWWWo..RR..','.RRRRRRoWWWWWWWWoRRRRRR','RRRRRRRRoWWWWWWoRRRRRRR','RRrRRRLBRRRRRRRRBLRRrRR','RRrRRRRRRRRRRRRRRRRrRRR'
            ],
            thoughtful: [
                '..........CC..........','.........oooo.........','.......ooHHHHHHoo......','......oHHHHHHHHHHo.....','......oHHHhhHHhHHHo....','.....oHHHHHHHHHHHHo....','.....oHHHHHHHHHHHHo....','....obBBBBBBBBBBBBbo...','....oBLBBBBBBBBBBLBo...','...oBGGgBBBBBBBBGGgBo..','...oBGGgBBBBBBBBGGgBo..','....obBBBBBBBBBBBBbo...','.....oSSSSSSSSSSSSo....','.....oSSsSSSSSSsSSo....','.....oSooSSSSSSooSo....','.....oSooSSSSSSooSo....','.....oSSSSSssSSSSSo....','......oSSSSssSSSSo.....','......oWwsSSSSswWo.....','.....oWWWWwssWWWWWo....','....oWWWWWWWWWWWWWWo...','...oWWWWWWWWWWWWWWWWo..','...oWWWWwWWWWWWwWWWWo..','...oWWWWWWWWWWWWWWWWo..','....oWWWWWWWWWWWWWWo...','.....oWWWWWwwWWWooo....','......oWWWWWWWWWo......','.......oWWWWWWWWo......','...RR..oWWWWWWWWo..RR..','.RRRRRRoWWWWWWWWoRRRRRR','RRRRRRRRoWWWWWWoRRRRRRR','RRrRRRLBRRRRRRRRBLRRrRR','RRrRRRRRRRRRRRRRRRRrRRR'
            ]
        };

        const MAESTRO_PALETTE = {
            '.': null, o: '#241a12', H: '#4a3320', h: '#33230f', B: '#c69a4c', b: '#8a6329',
            L: '#f2c14e', G: '#8fd0c8', g: '#4f9a91', S: '#e6b184', s: '#c68b5c',
            W: '#efe9dc', w: '#c3bcaa', R: '#5c4326', r: '#3f2c15', C: '#b5703a'
        };

        function renderMaestroSprite(containerId, pose = 'neutral', scale = 3.2) {
            const host = document.getElementById(containerId);
            const map = window.MAESTRO_SPRITES[pose] || window.MAESTRO_SPRITES.neutral;
            if (!host || !map) return;
            let rects = '';
            map.forEach((row, y) => {
                row.split('').forEach((token, x) => {
                    const fill = MAESTRO_PALETTE[token];
                    if (!fill) return;
                    rects += `<rect x="${x}" y="${y}" width="1.03" height="1.03" fill="${fill}" />`;
                });
            });
            host.innerHTML = `<svg viewBox="0 0 22 33" width="${22 * scale}" height="${33 * scale}" shape-rendering="crispEdges" style="display:block">${rects}</svg>`;
        }
```

- [ ] **Step 5: Add the persistent ambient behavior and tab-aware copy**

Insert this JS after the sprite renderer:

```javascript
        let maestroCurrentPose = 'neutral';

        function setMaestroPose(pose) {
            maestroCurrentPose = pose;
            renderMaestroSprite('maestroAmbientSprite', pose, 2.9);
            const introVisible = document.getElementById('maestroIntroOverlay');
            if (introVisible) renderMaestroSprite('maestroIntroSprite', pose === 'neutral' ? 'greeting' : pose, 4.6);
        }

        function ensureMaestroAmbient() {
            const el = document.getElementById('maestroAmbient');
            if (!el) return;
            el.style.display = 'flex';
            if (!document.getElementById('maestroAmbientSprite')?.innerHTML) {
                renderMaestroSprite('maestroAmbientSprite', maestroCurrentPose, 2.9);
            }
        }

        function updateMaestroAmbientState(tabId) {
            ensureMaestroAmbient();
            const bubble = document.getElementById('maestroAmbientBubble');
            const state = {
                draft: { pose: 'pointing', text: 'Segui il lotto: fair price e surplus sono la bussola.' },
                rosters: { pose: 'thoughtful', text: 'Ogni sigillo titolare resta modificabile con un tocco.' },
                listone: { pose: 'pointing', text: 'Occhio al surplus, giovane.' },
                ai: { pose: 'neutral', text: 'Qui gli esperimenti vanno letti con giudizio.' },
                lineup: { pose: 'thoughtful', text: 'Il solver resta separato: la vera lavagna è nelle Rose.' },
                audit: { pose: 'neutral', text: 'Una buona officina misura prima di giudicare.' },
                trades: { pose: 'greeting', text: 'Ogni scambio va pesato come un ingranaggio.' },
                targets: { pose: 'greeting', text: 'Fissa i tuoi obiettivi prima che il mercato corra.' }
            }[tabId] || { pose: 'neutral', text: 'Bentornato nell\'officina.' };
            setMaestroPose(state.pose);
            if (bubble) bubble.textContent = state.text;
        }
```

Then call `ensureMaestroAmbient(); updateMaestroAmbientState('targets');` once after the first app render completes.

- [ ] **Step 6: Verify the Maestro runtime was inserted correctly**

Run:

```bash
grep -n "MAESTRO_SPRITES\|renderMaestroSprite\|maestroAmbient\|updateMaestroAmbientState\|setMaestroPose" web/app.py
```

Expected: all identifiers appear.

- [ ] **Step 7: Verify the mascot host is rendered by Flask**

Run:

```bash
cd web && python3 app.py
curl -s http://localhost:5050/ | grep -c 'id="maestroAmbient"'
```

Expected: prints `1`.

- [ ] **Step 8: Manually compare size and placement to the approved mascot hero mockup**

Open the app and compare against `.superpowers/brainstorm/mockups-davinci-mascot/mascot-hero.png`. Confirm the ambient Maestro sits in the bottom corner at roughly a 64px sprite footprint, persists while switching all tabs, and stays in gutter space instead of covering dense list/table rows.

- [ ] **Step 9: Commit the ambient mascot foundation**

```bash
git add web/app.py
git commit -m "feat: add persistent maestro ambient mascot" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 4: Multi-pose Maestro tutorial integration on the existing spotlight system

**Files:**
- Modify: `web/static/js/tutorial.js:1-267`
- Modify: `web/static/css/tutorial.css:1-132`
- Test: manual verification via `curl`/browser against `/static/js/tutorial.js` and `/static/css/tutorial.css`

**Interfaces:**
- Consumes: `window.MAESTRO_SPRITES`, `renderMaestroSprite(containerId, pose, scale)`, `setMaestroPose(pose)` from Task 3, existing `window.FantaTour` module.
- Produces: extended tutorial step schema `{ selector, title, text, maestroText, maestroPose, requiresTab? }`, helper functions `_ensureMaestroDock()`, `_positionMaestroDock(targetEl, placeBelow)`, CSS classes `.tour-maestro`, `.tour-maestro--pointing`, `.tour-maestro--thoughtful`, `.tour-tooltip--officina`.

- [ ] **Step 1: Confirm the current tutorial has no Maestro support**

```bash
grep -n "maestroText\|maestroPose\|tour-maestro\|_ensureMaestroDock" web/static/js/tutorial.js web/static/css/tutorial.css
```

Expected: no matches.

- [ ] **Step 2: Expand the tutorial step definitions with approved Maestro copy and poses**

Replace the current `STEPS` array in `web/static/js/tutorial.js` with the same selectors/tabs plus these additional keys:

```javascript
    var STEPS = [
        {
            selector: '#btnLeagueSettings',
            title: 'Pannello Impostazioni',
            text: 'Configura qui budget di lega, numero di squadre e slot per ruolo. Puoi modificarli in qualsiasi momento.',
            maestroText: 'Ogni officina parte da misure corrette: budget e slot fissano il telaio della lega.',
            maestroPose: 'greeting'
        },
        {
            selector: '#sideNav-strategy',
            title: 'Blueprint Strategici',
            text: 'Scegli tra 5 piani tattici pre-configurati (es. Trazione Anteriore, Moneyball) con soglie di spesa per ruolo calcolate sul tuo budget di lega.',
            maestroText: 'Qui scegli il disegno della macchina: aggressiva davanti o disciplinata nel mezzo.',
            maestroPose: 'thoughtful'
        },
        {
            selector: '#tab-listone',
            requiresTab: 'listone',
            title: 'Colonne Listone',
            text: 'Le colonne chiave: Prezzo Equo (il massimo razionale da offrire), P50 (punti attesi), e Surplus di Mercato (l\'affare potenziale rispetto alla quotazione).',
            maestroText: 'Il Prezzo Equo è il mio compasso: oltre quella soglia, il mercato comanda te.',
            maestroPose: 'pointing'
        },
        {
            selector: '.medical-badge',
            requiresTab: 'listone',
            fallbackSelector: '#tab-listone',
            title: 'Scheda Clinica',
            text: 'Clicca il badge medico di un giocatore per aprire la sua cartella clinica: stato di rischio, giorni di infortunio, e metriche avanzate xG/xA.',
            maestroText: 'La bravura conta, ma la fragilità rompe gli ingranaggi nei momenti peggiori.',
            maestroPose: 'thoughtful'
        },
        {
            selector: '#sideNav-draft',
            title: 'Modulo Asta',
            text: 'Qui gestisci l\'asta live: assegnazione giocatori, tracciamento budget, live draft.',
            maestroText: 'Quando parte la battuta, tieni un occhio sul lotto e uno sul tuo margine di rilancio.',
            maestroPose: 'pointing'
        },
        {
            selector: '#sideNav-lineup',
            title: 'Formazione Settimanale',
            text: 'Calcola la formazione ottimale della giornata in base a probabili formazioni, quote e xPts.',
            maestroText: 'Ricorda: il solver giornata è distinto dalla lavagna tattica della Rosa.',
            maestroPose: 'neutral'
        },
        {
            selector: '#sideNav-audit',
            title: 'Valutatore & Scambi',
            text: 'Analizza la classifica di lega post-asta e valuta scambi vantaggiosi con gli altri manager nella sezione Scambi.',
            maestroText: 'Prima valuta i pesi della tua officina, poi contratta lo scambio giusto.',
            maestroPose: 'greeting'
        }
    ];
```

- [ ] **Step 3: Add the Maestro dock rendering and positioning without replacing `tour-tooltip`**

Insert into `web/static/js/tutorial.js`:

```javascript
    var maestroDockEl = null;

    function _ensureMaestroDock(step) {
        if (!maestroDockEl) {
            maestroDockEl = document.createElement('div');
            maestroDockEl.className = 'tour-maestro';
            maestroDockEl.innerHTML = '<div class="tour-maestro__sprite" id="tourMaestroSprite"></div><div class="tour-maestro__shadow"></div>';
            document.body.appendChild(maestroDockEl);
        }
        maestroDockEl.className = 'tour-maestro tour-maestro--' + (step.maestroPose || 'neutral');
        if (typeof window.renderMaestroSprite === 'function') {
            window.renderMaestroSprite('tourMaestroSprite', step.maestroPose || 'neutral', 4.2);
        }
        if (typeof window.setMaestroPose === 'function') {
            window.setMaestroPose(step.maestroPose || 'neutral');
        }
    }

    function _positionMaestroDock(targetEl, placeBelow) {
        if (!maestroDockEl || !tooltipEl) return;
        var tw = tooltipEl.offsetWidth;
        var th = tooltipEl.offsetHeight;
        var mw = maestroDockEl.offsetWidth;
        var left = parseFloat(tooltipEl.style.left || '0');
        var top = parseFloat(tooltipEl.style.top || '0');
        maestroDockEl.style.left = Math.max(8, left - mw + 18) + 'px';
        maestroDockEl.style.top = (placeBelow ? top - 24 : top + th - 74) + 'px';
    }
```

Then inside `_positionTooltip(targetEl, step)` change:

```javascript
        tooltipEl.className = 'tour-tooltip';
```

to:

```javascript
        tooltipEl.className = 'tour-tooltip tour-tooltip--officina';
```

And immediately after `document.body.appendChild(tooltipEl);` add:

```javascript
        _ensureMaestroDock(step);
```

Finally, after the tooltip position is computed, add:

```javascript
        _positionMaestroDock(targetEl, placeBelow);
```

and append the Maestro narration line to the tooltip body:

```javascript
        if (step.maestroText) {
            var maestroLine = document.createElement('div');
            maestroLine.className = 'tour-tooltip-maestro-line';
            maestroLine.innerHTML = step.maestroText + ' — <i>Il Maestro</i>';
            tooltipEl.insertBefore(maestroLine, progressEl);
        }
```

- [ ] **Step 4: Extend teardown/resizing logic so the mascot stays aligned**

In `_clearOverlay()` and `resizeHandler`, add:

```javascript
        if (maestroDockEl && maestroDockEl.parentNode) {
            maestroDockEl.parentNode.removeChild(maestroDockEl);
            maestroDockEl = null;
        }
```

and let the existing resize path call `_positionTooltip(...)`, which now also repositions the Maestro.

- [ ] **Step 5: Add the actual tooltip + mascot styles into `tutorial.css`**

Append to `web/static/css/tutorial.css`:

```css
.tour-tooltip--officina {
    background: linear-gradient(180deg, #2a1e13, #1d140c);
    border: 1px solid rgba(198,154,76,0.34);
    color: #f1e6cd;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
}

.tour-tooltip--officina .tour-tooltip-title {
    color: #f6e9cc;
    font-weight: 800;
}

.tour-tooltip--officina .tour-tooltip-text {
    color: #cdb992;
}

.tour-tooltip-maestro-line {
    margin: 0 0 12px;
    font-family: 'Cormorant Garamond', serif;
    font-style: italic;
    font-size: 0.94rem;
    color: #f2c14e;
}

.tour-maestro {
    position: fixed;
    z-index: 10002;
    width: 96px;
    height: 138px;
    pointer-events: none;
    filter: drop-shadow(0 6px 12px rgba(0,0,0,0.6));
    animation: tour-maestro-float 4s ease-in-out infinite;
}

.tour-maestro__sprite {
    position: relative;
    z-index: 1;
}

.tour-maestro__shadow {
    position: absolute;
    left: 50%;
    bottom: -6px;
    transform: translateX(-50%);
    width: 70%;
    height: 8px;
    border-radius: 50%;
    background: radial-gradient(ellipse, rgba(0,0,0,0.45), transparent 70%);
}

.tour-maestro--pointing { transform-origin: bottom center; }
.tour-maestro--thoughtful { filter: drop-shadow(0 6px 12px rgba(0,0,0,0.72)); }

@keyframes tour-maestro-float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-5px); }
}
```

- [ ] **Step 6: Verify tutorial assets now expose Maestro hooks**

Run:

```bash
grep -n "maestroText\|maestroPose\|tour-maestro\|tour-tooltip--officina\|_ensureMaestroDock" web/static/js/tutorial.js web/static/css/tutorial.css
```

Expected: matches in both files.

- [ ] **Step 7: Verify the served assets contain the new tutorial code**

Run:

```bash
cd web && python3 app.py
curl -s http://localhost:5050/static/js/tutorial.js | grep -c 'maestroPose'
curl -s http://localhost:5050/static/css/tutorial.css | grep -c 'tour-maestro'
```

Expected: both commands print a value greater than `0`.

- [ ] **Step 8: Manually compare the tutorial overlay to the approved tutorial mockup**

Open the app, trigger the guide, and compare to `.superpowers/brainstorm/mockups-davinci-mascot/mascot-tutorial-context.png`. Confirm the existing spotlight rectangles/highlight remain intact, the tooltip is now leather/parchment toned, and the Maestro docks beside the tooltip in distinct poses instead of replacing the tour engine.

- [ ] **Step 9: Commit the tutorial integration**

```bash
git add web/static/js/tutorial.js web/static/css/tutorial.css
git commit -m "feat: dock maestro into tutorial spotlight" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 5: Shared Da Vinci pitch component and scoped sepia role tokens

**Files:**
- Modify: `web/app.py:1796-1818`
- Modify: `web/app.py:2548-2680`
- Modify: `web/app.py:7254-7598`
- Test: manual verification via `curl`/browser against `/`

**Interfaces:**
- Consumes: existing roster data and `PITCH_FORMATIONS`, existing A/C/D/P role ordering.
- Produces: scoped CSS vars `--davinci-role-p`, `--davinci-role-d`, `--davinci-role-c`, `--davinci-role-a`; JS helpers `getDavinciPitchSvg(options: { seed?: number, counts?: Record<string, number>, labels?: Record<string, string[]>, interactive?: boolean }): string` and `getDavinciRoleColor(role: string): string`; CSS classes `.davinci-pitch-shell`, `.davinci-pitch-frame`, `.davinci-token`, `.davinci-token--empty`, `.davinci-legend`, `.davinci-jersey.role-P|D|C|A`.

- [ ] **Step 1: Confirm the shared Da Vinci component does not exist yet**

```bash
grep -n "davinci-role\|getDavinciPitchSvg\|davinci-pitch-shell\|davinci-token" web/app.py
```

Expected: no matches.

- [ ] **Step 2: Add scoped Da Vinci role variables without touching existing global role tokens**

Append to `:root` in `web/app.py:1796-1818`:

```css
            --davinci-role-p: #d99b34;
            --davinci-role-d: #5c9457;
            --davinci-role-c: #4f89a3;
            --davinci-role-a: #c0533f;
            --davinci-ink: #5a4326;
            --davinci-ink-soft: #6f5233;
            --davinci-hatch: #7a5c38;
            --davinci-parchment-a: #efe2c1;
            --davinci-parchment-b: #e4d2a6;
            --davinci-parchment-c: #c9ac74;
```

- [ ] **Step 3: Add reusable Da Vinci CSS separate from the current green pitch classes**

Append to the pitch section in `web/app.py:2548-2680`:

```css
        .davinci-pitch-shell {
            position: relative;
            width: 100%;
            max-width: 420px;
            margin: 0 auto;
            filter: drop-shadow(0 8px 18px rgba(0,0,0,0.5));
        }
        .davinci-pitch-frame {
            position: relative;
            border-radius: 16px;
            padding: 12px;
            border: 1px solid rgba(198,154,76,0.26);
            background: linear-gradient(180deg, #2a1e13, #1c140d);
        }
        .davinci-pitch-stamp {
            position: absolute;
            top: 10px;
            left: 14px;
            z-index: 3;
            font-family: 'Cormorant Garamond', serif;
            font-style: italic;
            color: var(--officina-brass-dark);
            font-size: 0.8rem;
            opacity: 0.8;
        }
        .davinci-legend {
            display: flex;
            gap: 14px;
            flex-wrap: wrap;
            justify-content: center;
            margin-top: 12px;
            font-size: 0.72rem;
            color: var(--officina-muted);
        }
        .davinci-legend span {
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .davinci-legend i {
            width: 11px;
            height: 11px;
            border-radius: 50%;
            display: inline-block;
            border: 1px solid #3a2c14;
        }
        .davinci-token {
            cursor: pointer;
        }
        .davinci-token--empty {
            opacity: 0.56;
        }
        .davinci-jersey.role-P { fill: var(--davinci-role-p); }
        .davinci-jersey.role-D { fill: var(--davinci-role-d); }
        .davinci-jersey.role-C { fill: var(--davinci-role-c); }
        .davinci-jersey.role-A { fill: var(--davinci-role-a); }
```

- [ ] **Step 4: Add the shared SVG generator and role-color helper in `web/app.py`**

Insert near the pitch logic helpers around `web/app.py:7254-7320`:

```javascript
        function getDavinciRoleColor(role) {
            return ({
                P: 'var(--davinci-role-p)',
                D: 'var(--davinci-role-d)',
                C: 'var(--davinci-role-c)',
                A: 'var(--davinci-role-a)'
            })[role] || 'var(--davinci-role-c)';
        }

        function getDavinciPitchSvg(options) {
            options = options || {};
            const seed = options.seed || 5;
            const counts = options.counts || { A: 0, C: 0, D: 0, P: 0 };
            const labels = options.labels || { A: [], C: [], D: [], P: [] };
            const tokenMode = options.interactive ? 'interactive' : 'decorative';
            const rowsY = { A: 96, C: 170, D: 300, P: 392 };
            let tokens = '';
            ['A', 'C', 'D', 'P'].forEach(role => {
                const n = counts[role] || 0;
                if (!n) return;
                const left = 52;
                const right = 288;
                const span = right - left;
                for (let i = 0; i < n; i++) {
                    const x = n === 1 ? 170 : left + span * (i / (n - 1));
                    const y = rowsY[role];
                    const label = (labels[role] && labels[role][i]) || role;
                    const className = `davinci-token ${tokenMode === 'interactive' ? '' : 'davinci-token--static'}`.trim();
                    tokens += `
                        <g class="${className}" data-role="${role}" data-slot="${i}" transform="translate(${x},${y})">
                            <ellipse cx="1.5" cy="16" rx="15" ry="4" fill="#3a2c14" opacity="0.18"></ellipse>
                            <circle class="davinci-jersey role-${role}" r="14" stroke="#3a2c14" stroke-width="1.6"></circle>
                            <circle r="14" fill="none" stroke="#efe2c1" stroke-width="0.8" opacity="0.6"></circle>
                            <circle r="10.5" fill="none" stroke="#efe2c1" stroke-width="0.6" opacity="0.35" stroke-dasharray="1.5 2"></circle>
                            <text y="4" text-anchor="middle" font-size="12" font-weight="700" fill="#f3e7c8">${role}</text>
                            <rect x="-28" y="18" width="56" height="13" rx="2" fill="#e9d9b0" stroke="#9c7d47" stroke-width="0.6" opacity="0.94"></rect>
                            <text y="28" text-anchor="middle" font-size="9" fill="#4a3618" font-style="italic">${label}</text>
                        </g>`;
                }
            });
            return `
                <svg viewBox="0 0 340 470" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="'Cormorant Garamond','Georgia',serif">
                    <defs>
                        <filter id="davinciWobble${seed}"><feTurbulence type="fractalNoise" baseFrequency="0.018" numOctaves="2" seed="${seed}" result="n"></feTurbulence><feDisplacementMap in="SourceGraphic" in2="n" scale="2.4" xChannelSelector="R" yChannelSelector="G"></feDisplacementMap></filter>
                        <filter id="davinciPaper${seed}"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="f"></feTurbulence><feColorMatrix in="f" type="matrix" values="0 0 0 0 0.42 0 0 0 0 0.31 0 0 0 0 0.16 0 0 0 0.10 0"></feColorMatrix><feComposite operator="over" in2="SourceGraphic"></feComposite></filter>
                        <radialGradient id="davinciParchment${seed}" cx="42%" cy="34%" r="85%"><stop offset="0%" stop-color="#efe2c1"></stop><stop offset="55%" stop-color="#e4d2a6"></stop><stop offset="100%" stop-color="#c9ac74"></stop></radialGradient>
                        <linearGradient id="davinciEdge${seed}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#9c7d47"></stop><stop offset="100%" stop-color="#7c5f31"></stop></linearGradient>
                        <pattern id="davinciHatch${seed}" width="6" height="6" patternTransform="rotate(38)" patternUnits="userSpaceOnUse"><line x1="0" y1="0" x2="0" y2="6" stroke="#7a5c38" stroke-width="0.7" opacity="0.45"></line></pattern>
                    </defs>
                    <path filter="url(#davinciPaper${seed})" fill="url(#davinciParchment${seed})" stroke="url(#davinciEdge${seed})" stroke-width="2.5" d="M14,10 L60,7 L120,11 L190,6 L250,12 L300,8 L328,16 L331,80 L326,180 L332,300 L327,400 L330,452 L280,458 L200,452 L120,460 L60,453 L12,458 L9,380 L14,260 L8,150 L11,70 Z"></path>
                    <g filter="url(#davinciWobble${seed})" fill="none" stroke="#5a4326" stroke-width="1.6" stroke-linecap="round" opacity="0.9">
                        <rect x="34" y="40" width="272" height="392" rx="4"></rect>
                        <rect x="36" y="42" width="268" height="388" rx="4" stroke-width="0.7" opacity="0.5"></rect>
                        <line x1="34" y1="236" x2="306" y2="236"></line>
                        <circle cx="170" cy="236" r="46"></circle>
                        <circle cx="170" cy="236" r="2.6" fill="#5a4326"></circle>
                        <rect x="96" y="40" width="148" height="60"></rect>
                        <rect x="130" y="40" width="80" height="26"></rect>
                        <path d="M120,100 A40,30 0 0 0 220,100"></path>
                        <rect x="96" y="372" width="148" height="60"></rect>
                        <rect x="130" y="406" width="80" height="26"></rect>
                        <path d="M120,372 A40,30 0 0 1 220,372"></path>
                    </g>
                    <rect x="96" y="40" width="148" height="26" fill="url(#davinciHatch${seed})" opacity="0.5"></rect>
                    <rect x="96" y="406" width="148" height="26" fill="url(#davinciHatch${seed})" opacity="0.5"></rect>
                    <g fill="#6f5233" font-style="italic" opacity="0.78">
                        <text x="300" y="34" font-size="11" text-anchor="end">studio tattico</text>
                        <text x="42" y="452" font-size="10">porta · custode</text>
                    </g>
                    <text x="300" y="450" font-size="10" fill="#6f5233" font-style="italic" opacity="0.55" text-anchor="end" transform="rotate(-3 300 450)">— Cod. FantaLab, f.34r</text>
                    ${tokens}
                </svg>`;
        }
```

- [ ] **Step 5: Verify the shared pitch component hooks exist**

Run:

```bash
grep -n "davinci-role-p\|getDavinciPitchSvg\|getDavinciRoleColor\|davinci-pitch-shell\|davinci-legend" web/app.py
```

Expected: matches for all identifiers.

- [ ] **Step 6: Verify the rendered page contains the shared SVG function name**

Run:

```bash
cd web && python3 app.py
curl -s http://localhost:5050/ | grep -c 'getDavinciPitchSvg'
```

Expected: prints `1`.

- [ ] **Step 7: Manually compare the shared materials against the approved Da Vinci pitch references**

Open the app after later tasks consume this helper and compare parchment tone, hand-drawn line wobble, hatch texture, and marginalia against `.superpowers/brainstorm/mockups-davinci-mascot/pitch-davinci-auction.png` and `.superpowers/brainstorm/mockups-davinci-mascot/pitch-davinci-lineup.png`.

- [ ] **Step 8: Commit the shared pitch foundation**

```bash
git add web/app.py
git commit -m "feat: add shared da vinci pitch component" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 6: Decorative Da Vinci pitch placement in the Asta tab

**Files:**
- Modify: `web/app.py:3332-3432`
- Modify: `web/app.py:3433-3465`
- Test: manual verification via `curl`/browser against `/`

**Interfaces:**
- Consumes: `getDavinciPitchSvg(options)` from Task 5, existing live lot ids `flLotRole`, `flLotTeam`, `flLotName`, `flLotFair`, `flLotPts`, `flLotFascia`, `flLotPrice`, `flLotBidder`, `flLotTimer`, `flLotAdvisoryBanner`, and `applyLiveLotToManualDraft()`.
- Produces: Asta-only wrapper ids `auctionDavinciCard`, `auctionDavinciPitch`, helper `renderAuctionDavinciPitch(lot?: { role?: string, player?: string }): void`, future-ready dataset container `auctionDavinciPitch.dataset.previewMode = 'decorative'`.

- [ ] **Step 1: Verify the insertion point currently jumps straight from the live lot card to the manual draft card**

```bash
grep -n "flLotAdvisoryBanner\|applyLiveLotToManualDraft\|MANUAL DRAFT CARD" web/app.py
```

Expected: `applyLiveLotToManualDraft()` remains just above `<!-- MANUAL DRAFT CARD -->` around `3421-3435`.

- [ ] **Step 2: Insert the new Da Vinci card between the active lot block and the manual draft card**

Insert immediately after the active lot widget closes and before `<!-- MANUAL DRAFT CARD -->` in `web/app.py:3433`:

```html
            <div class="card" id="auctionDavinciCard">
                <div class="card-header" style="margin-bottom:10px;">
                    <div>
                        <div class="card-title" style="display:flex; align-items:center; gap:8px;">
                            <i class="fa-solid fa-compass-drafting" style="color:var(--officina-brass);"></i>
                            Tavola Tattica del Lotto
                        </div>
                        <div style="font-size:0.74rem; color:var(--officina-muted);">
                            Campo Da Vinci decorativo per il lotto in corso — già predisposto per una futura preview live senza cambiare la struttura.
                        </div>
                    </div>
                </div>
                <div class="davinci-pitch-frame">
                    <span class="davinci-pitch-stamp">tavola tattica</span>
                    <div id="auctionDavinciPitch" class="davinci-pitch-shell" data-preview-mode="decorative"></div>
                </div>
            </div>
```

- [ ] **Step 3: Add the dedicated auction renderer using the shared SVG function**

Insert near the other draft helpers in `web/app.py`:

```javascript
        function renderAuctionDavinciPitch(lot) {
            const host = document.getElementById('auctionDavinciPitch');
            if (!host || typeof getDavinciPitchSvg !== 'function') return;
            const role = lot && lot.role ? lot.role : 'A';
            const label = lot && lot.player ? lot.player : 'lotto in studio';
            host.dataset.previewMode = 'decorative';
            host.innerHTML = getDavinciPitchSvg({
                seed: 3,
                counts: { A: role === 'A' ? 1 : 0, C: role === 'C' ? 1 : 0, D: role === 'D' ? 1 : 0, P: role === 'P' ? 1 : 0 },
                labels: { A: role === 'A' ? [label] : [], C: role === 'C' ? [label] : [], D: role === 'D' ? [label] : [], P: role === 'P' ? [label] : [] },
                interactive: false
            });
        }
```

- [ ] **Step 4: Call the decorative renderer on initial load and whenever the active lot updates**

After the draft tab initializes, add:

```javascript
        renderAuctionDavinciPitch();
```

And inside the function that hydrates the live lot widget (where `flLotRole`, `flLotName`, and friends are updated), append:

```javascript
                    renderAuctionDavinciPitch({ role: lot.role, player: lot.player });
```

This preserves current live-lot behavior while keeping the new card synchronized visually.

- [ ] **Step 5: Verify the Asta pitch insertion and renderer hooks exist**

Run:

```bash
grep -n "auctionDavinciCard\|auctionDavinciPitch\|renderAuctionDavinciPitch\|data-preview-mode=\"decorative\"" web/app.py
```

Expected: matches for all four additions.

- [ ] **Step 6: Verify rendered HTML contains the decorative pitch card**

Run:

```bash
cd web && python3 app.py
curl -s http://localhost:5050/ | grep -c 'auctionDavinciPitch'
```

Expected: prints `1`.

- [ ] **Step 7: Manually compare the Asta placement to the approved auction pitch mockup**

Open the Draft/Asta tab and compare against `.superpowers/brainstorm/mockups-davinci-mascot/pitch-davinci-auction.png`. Confirm the parchment field sits between the active lot area and the manual draft card, feels like a contextual tactical plate, and remains decorative-only with no new controls or live-preview mechanics.

- [ ] **Step 8: Commit the auction pitch task**

```bash
git add web/app.py
git commit -m "feat: add decorative auction da vinci pitch" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 7: Functional Da Vinci restyle of the real tactical pitch in `tab-rosters`

**Files:**
- Modify: `web/app.py:3748-3838`
- Modify: `web/app.py:7254-7598`
- Test: manual verification via `curl`/browser against `/`

**Interfaces:**
- Consumes: `PITCH_FORMATIONS`, `getActivePitchFormation()`, `onPitchFormationChange(newForm)`, `getPitchLineup()`, `setPitchLineup(lineup)`, `resetPitchLineup()`, `resolvePitchLineup(team, formation)`, `openPitchPlayerPickerModal(role, slotIndex, currentAssigned, formation)`, `getDavinciPitchSvg(options)` from Task 5.
- Produces: restyled `renderTacticalPitch(team, struct): void`, helper `getDavinciPitchLabels(lineup: Record<string, Array<any>>): Record<string, string[]>`, roster-pitch DOM wrapper `pitchBoardDavinci`, retained click contract on `.davinci-token[data-role][data-slot]`.

- [ ] **Step 1: Confirm the current functional pitch is still the green stadium version**

```bash
grep -n "pitch-board\|pitch-row-a\|pitch-jersey\|renderTacticalPitch\|renderPitchRow" web/app.py
```

Expected: matches point to the existing green board and row renderer.

- [ ] **Step 2: Replace the roster pitch markup with the Da Vinci shell while keeping ids required by JS**

In `web/app.py:3793-3838`, replace the inner pitch board block:

```html
                    <div class="pitch-board" id="pitchBoard">
                        <div class="pitch-penalty-top"></div>
                        <div class="pitch-midline"></div>
                        <div class="pitch-penalty-bottom"></div>
                        <div class="pitch-row pitch-row-a" id="pitchRowA"></div>
                        <div class="pitch-row pitch-row-c" id="pitchRowC"></div>
                        <div class="pitch-row pitch-row-d" id="pitchRowD"></div>
                        <div class="pitch-row pitch-row-p" id="pitchRowP"></div>
                    </div>
```

with:

```html
                    <div class="davinci-pitch-frame">
                        <span class="davinci-pitch-stamp">f.34r · lo schieramento</span>
                        <div id="pitchBoardDavinci" class="davinci-pitch-shell"></div>
                    </div>
                    <div class="davinci-legend">
                        <span><i style="background:var(--davinci-role-p);"></i> Portiere</span>
                        <span><i style="background:var(--davinci-role-d);"></i> Difesa</span>
                        <span><i style="background:var(--davinci-role-c);"></i> Centrocampo</span>
                        <span><i style="background:var(--davinci-role-a);"></i> Attacco</span>
                        <span style="color:var(--officina-brass);"><i class="fa-solid fa-hand-pointer" style="border:none; width:auto; height:auto;"></i> Tocca un sigillo per cambiare titolare</span>
                    </div>
```

Keep `pitchFormationSelect`, `pitchLegalityBadge`, `pitchStatsHud`, and `resetPitchLineup()` exactly wired as before.

- [ ] **Step 3: Add a helper that converts the resolved lineup into Da Vinci labels**

Insert before `renderTacticalPitch(team, struct)`:

```javascript
        function getDavinciPitchLabels(lineup) {
            return {
                A: (lineup.A || []).map(slot => slot && slot.player ? ((slot.player.player || '').length > 9 ? slot.player.player.substring(0, 8) + '…' : slot.player.player) : '+ Scegli'),
                C: (lineup.C || []).map(slot => slot && slot.player ? ((slot.player.player || '').length > 9 ? slot.player.player.substring(0, 8) + '…' : slot.player.player) : '+ Scegli'),
                D: (lineup.D || []).map(slot => slot && slot.player ? ((slot.player.player || '').length > 9 ? slot.player.player.substring(0, 8) + '…' : slot.player.player) : '+ Scegli'),
                P: (lineup.P || []).map(slot => slot && slot.player ? ((slot.player.player || '').length > 9 ? slot.player.player.substring(0, 8) + '…' : slot.player.player) : '+ Scegli')
            };
        }
```

- [ ] **Step 4: Replace the row-based render with SVG token wiring while preserving all 9 formations and click behavior**

Inside `renderTacticalPitch(team, struct)`, keep the existing legality/HUD calculations but replace the row-rendering block beginning at `const renderPitchRow = ...` with:

```javascript
            const pitchHost = document.getElementById('pitchBoardDavinci');
            if (pitchHost) {
                const labels = getDavinciPitchLabels(lineup);
                pitchHost.innerHTML = getDavinciPitchSvg({
                    seed: 5,
                    counts: counts,
                    labels: labels,
                    interactive: true
                });

                ['A', 'C', 'D', 'P'].forEach(role => {
                    const slots = lineup[role] || [];
                    pitchHost.querySelectorAll(`.davinci-token[data-role="${role}"]`).forEach((node, idx) => {
                        const slot = slots[idx];
                        if (!slot || slot.isEmpty || !slot.player) {
                            node.classList.add('davinci-token--empty');
                        }
                        node.addEventListener('click', function () {
                            openPitchPlayerPickerModal(role, idx, slot && slot.player ? slot.player.player : null, formation);
                        });
                    });
                });
            }
```

Delete the old `renderPitchRow('A'...)` / `pitchRowA` / `pitchRowC` / `pitchRowD` / `pitchRowP` rendering path, because the SVG now owns the layout. Keep `window.onPitchNodeClicked` only if another caller still needs it; otherwise remove it cleanly in the same task.

- [ ] **Step 5: Update the HUD copy to match the approved lineup mockup while preserving existing metrics**

Inside `#pitchStatsHud`, change the third stat label from `Media Voto:` to `xPts giornata:` only if the underlying value is already the expected metric; otherwise keep `Media Voto:` and add a note in the legend. Do not invent new backend data. If no explicit xPts field exists, keep the current metric labels and restyle only:

```html
<div id="pitchStatsHud" style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; padding:8px 12px; margin-bottom:12px; background:rgba(198,154,76,0.07); border-radius:8px; font-size:0.75rem; border:1px solid rgba(198,154,76,0.2);">
```

This preserves the visual target without falsifying data.

- [ ] **Step 6: Verify the restyled roster pitch hooks exist and all 9 formations remain referenced**

Run:

```bash
grep -n "pitchBoardDavinci\|getDavinciPitchLabels\|davinci-token\|PITCH_FORMATIONS\|openPitchPlayerPickerModal" web/app.py
```

Expected: matches show the new renderer plus the unchanged `PITCH_FORMATIONS` object at `web/app.py:7320+`.

- [ ] **Step 7: Verify the rendered page still exposes the functional roster pitch shell**

Run:

```bash
cd web && python3 app.py
curl -s http://localhost:5050/ | grep -c 'pitchBoardDavinci'
```

Expected: prints `1`.

- [ ] **Step 8: Manually compare the real roster pitch against the approved lineup mockup**

Open the Rose tab (not the placeholder Formazione solver tab) and compare against `.superpowers/brainstorm/mockups-davinci-mascot/pitch-davinci-lineup.png`. Confirm parchment board, wax-seal style role tokens, visible role legend, preserved formation selector/HUD/Auto-Fill controls, and working click-to-swap interactions across multiple formations such as `3-4-3`, `4-3-3`, and `5-3-2`.

- [ ] **Step 9: Commit the functional pitch restyle**

```bash
git add web/app.py
git commit -m "feat: restyle roster tactical pitch as da vinci board" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 8: Final cross-tab QA and spec-to-implementation self-review pass

**Files:**
- Modify: `web/app.py` (only if fixes are discovered)
- Modify: `web/static/js/tutorial.js` (only if fixes are discovered)
- Modify: `web/static/css/tutorial.css` (only if fixes are discovered)
- Test: repository grep checks, Flask visual QA, manual comparison checklist

**Interfaces:**
- Consumes: all prior tasks’ DOM ids, CSS vars, and JS functions.
- Produces: final verification notes in commit history and any last-mile polish required to satisfy spec sections 3, 4, 5, 6.2, 6.3, 7, and 8.

- [ ] **Step 1: Run the full grep checklist for all critical interfaces**

```bash
grep -n "splashIdentityGate\|maestroIntroOverlay\|maestroAmbient\|session-login-officina\|auctionDavinciPitch\|pitchBoardDavinci\|davinci-role-p\|tour-maestro\|fanta_maestro_intro_done" web/app.py web/static/js/tutorial.js web/static/css/tutorial.css
```

Expected: each identifier appears at least once in the intended file.

- [ ] **Step 2: Verify served HTML/assets expose all major UI hooks**

Run:

```bash
cd web && python3 app.py
curl -s http://localhost:5050/ | grep -c 'splashIdentityGate'
curl -s http://localhost:5050/ | grep -c 'maestroAmbient'
curl -s http://localhost:5050/ | grep -c 'auctionDavinciPitch'
curl -s http://localhost:5050/ | grep -c 'pitchBoardDavinci'
curl -s http://localhost:5050/static/js/tutorial.js | grep -c 'maestroPose'
curl -s http://localhost:5050/static/css/tutorial.css | grep -c 'tour-maestro'
```

Expected: every command prints a value greater than `0`, with the four HTML ids printing exactly `1`.

- [ ] **Step 3: Manually execute the eight-section visual QA checklist**

In a browser, verify:

```text
1. First visit shows the team-selection splash and one-time Maestro intro (spec section 3).
2. Returning visit skips the splash using saved activeProfileId (spec section 3).
3. Bottom nav fits 8 tabs in 68px with brass/leather styling and active glow (spec section 4).
4. Session PIN gate is visually restyled but login behavior is unchanged (spec sections 3.2 and 7).
5. Ambient Maestro persists across all tabs at ~64px and never covers dense data (spec section 5).
6. Tutorial spotlight still uses the existing overlay engine, now with Maestro docked in multiple poses (spec section 5).
7. Asta tab shows the decorative Da Vinci pitch between live lot and manual draft, with no live-preview behavior (spec section 6.2).
8. Rose tab pitch, not the placeholder tab-lineup card, is restyled as the functional Da Vinci board with all existing interactions preserved (spec section 6.3).
```

Compare against all four approved PNGs in `.superpowers/brainstorm/mockups-davinci-mascot/` while checking desktop and a narrow mobile-width viewport.

- [ ] **Step 4: Fix any visual or naming mismatches found in Step 3 immediately**

Use targeted edits only. If, for example, the Maestro bubble overlaps list content on mobile, reduce or hide `.maestro-ambient__bubble` under the existing mobile media query instead of altering unrelated layout.

- [ ] **Step 5: Commit the QA/polish pass**

```bash
git add web/app.py web/static/js/tutorial.js web/static/css/tutorial.css
git commit -m "chore: polish ui glowup qa issues" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
