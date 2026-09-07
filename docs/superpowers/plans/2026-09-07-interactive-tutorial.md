# Tutorial Interattivo Spotlight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-dependency, all-Italian, 7-step interactive "Spotlight" walkthrough for
`fanta-lab` that teaches new users the League Settings panel, Tactical Blueprints, Listone
columns, Medical Card, and the Draft/Lineup/Audit navigation modules, persisted via
`localStorage` and re-launchable anytime from a navbar "❓ Guida" button.

**Architecture:** Two new static assets (`static/js/tutorial.js`, `static/css/tutorial.css`)
served by the existing Flask static route, wired into `app.py`'s embedded `HTML_TEMPLATE` via a
`<link>`/`<script>` tag pair, a navbar button, and one `window.onload` hook. The tour itself is a
plain-JS module (`FantaTour` global object) with no external libraries: a 4-rectangle overlay
computed from `getBoundingClientRect()` creates the spotlight cutout, a single tooltip element is
repositioned per step, and step definitions are a static JS array with optional `requiresTab`
fields that call the app's existing `switchTab()` function before measuring the target element.

**Tech Stack:** Vanilla JavaScript (ES6, IIFE module pattern), vanilla CSS, Flask
`send_from_directory` static serving (already configured in `app.py:819-821`).

## Global Constraints

- The tutorial UI text is **Italian only** — no i18n framework, no English strings, no language
  toggle (confirmed with user: the app's UI is Italian-only by design; bilingual documentation
  applies only to repo-level docs, not app UI).
- **Zero external dependencies** — no new npm packages, no CDN scripts beyond what's already
  loaded (Font Awesome icons already available via `app.py:1792` — new UI may use `fa-solid`
  icon classes already loaded).
- New static files go under `static/js/` and `static/css/` (repo root `static/` directory,
  already served by `@app.route("/static/<path:path>")` at `app.py:819-821`) — **not**
  `web/static/` (that path does not exist in this repository).
- The overlay must use `rgba(0, 0, 0, 0.75)` for the darkening layer (exact value from spec).
- Persistence key is exactly `fanta_tour_done` in `localStorage`, set to the string `'true'`.
- Must not modify or duplicate any existing tab, nav button, or JS function already in `app.py`
  (`switchTab`, `switchTargetSubview`, existing sidebar/bottom-nav buttons) — only additive changes.
- No automated test suite exists for frontend JS/CSS in this repository (confirmed: Pilastro 4's
  UI task used manual curl/grep verification, not pytest). This plan follows the same pattern —
  no new pytest test files are created; verification is manual per task via curl/grep and a
  final full `pytest tests/ -v` run to confirm zero regressions (expected: 89 passed, 1
  pre-existing unrelated collection error in `tests/test_dual_track_and_features.py::test`).
- Every commit must include the trailer: `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`

---

### Task 1: Tutorial CSS (`static/css/tutorial.css`)

**Files:**
- Create: `static/css/tutorial.css`

**Interfaces:**
- Consumes: existing CSS custom properties already defined in `app.py`'s `<style>` block:
  `--surface` (rgba(12, 15, 25, 0.82)), `--border` (rgba(255, 45, 117, 0.18)), `--primary`
  (used for accents, referenced as `var(--primary)` elsewhere in `app.py`), `--gold` (used for
  highlight accents elsewhere in `app.py`), `--text-muted` (used for secondary text elsewhere in
  `app.py`).
- Produces: CSS classes consumed by Task 3's JS: `.tour-overlay-rect` (the 4 darkening rectangles
  and the highlight-outline rectangle — 5 elements total, distinguished by a modifier class),
  `.tour-overlay-highlight` (the 5th rectangle, outline-only), `.tour-tooltip`,
  `.tour-tooltip-arrow` (with modifiers `.tour-tooltip-arrow-top` / `.tour-tooltip-arrow-bottom`
  for the two placement directions), `.tour-tooltip-title`, `.tour-tooltip-text`,
  `.tour-tooltip-progress`, `.tour-tooltip-actions`, `.tour-btn` (with modifiers `.tour-btn-primary`
  and `.tour-btn-secondary`), `.tour-btn-skip`.

- [ ] **Step 1: Create the CSS file with full spotlight/tooltip styling**

Create `static/css/tutorial.css` with this exact content:

```css
/* ============================================================
   Tutorial Interattivo Spotlight — fanta-lab
   Zero-dependency walkthrough overlay styles.
   ============================================================ */

.tour-overlay-rect {
    position: fixed;
    background: rgba(0, 0, 0, 0.75);
    z-index: 10000;
    pointer-events: auto;
    transition: none;
}

.tour-overlay-highlight {
    position: fixed;
    background: transparent;
    border-radius: 8px;
    box-shadow: 0 0 0 3px var(--gold, #f5b642), 0 0 24px 4px rgba(245, 182, 66, 0.45);
    z-index: 10001;
    pointer-events: none;
}

.tour-tooltip {
    position: fixed;
    z-index: 10002;
    background: var(--surface, rgba(12, 15, 25, 0.95));
    border: 1px solid var(--border, rgba(255, 45, 117, 0.18));
    border-radius: 12px;
    padding: 16px 18px;
    max-width: 320px;
    min-width: 240px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    font-family: 'Outfit', 'Plus Jakarta Sans', sans-serif;
    color: #f1f5f9;
}

.tour-tooltip-arrow {
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 9px solid transparent;
    border-right: 9px solid transparent;
}

.tour-tooltip-arrow-top {
    /* tooltip is below the target: arrow points up, sits at top edge */
    top: -9px;
    border-bottom: 9px solid var(--surface, rgba(12, 15, 25, 0.95));
}

.tour-tooltip-arrow-bottom {
    /* tooltip is above the target: arrow points down, sits at bottom edge */
    bottom: -9px;
    border-top: 9px solid var(--surface, rgba(12, 15, 25, 0.95));
}

.tour-tooltip-title {
    font-size: 1.05rem;
    font-weight: 700;
    margin: 0 0 8px 0;
    color: #fff;
}

.tour-tooltip-text {
    font-size: 0.88rem;
    line-height: 1.5;
    color: var(--text-muted, #94a3b8);
    margin: 0 0 14px 0;
}

.tour-tooltip-progress {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted, #94a3b8);
    margin-bottom: 10px;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}

.tour-tooltip-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
}

.tour-btn {
    border: none;
    border-radius: 8px;
    padding: 7px 14px;
    font-size: 0.82rem;
    font-weight: 700;
    cursor: pointer;
    font-family: inherit;
    transition: opacity 0.15s ease;
}

.tour-btn:hover {
    opacity: 0.85;
}

.tour-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
}

.tour-btn-primary {
    background: var(--primary, #ff2d75);
    color: #fff;
}

.tour-btn-secondary {
    background: rgba(255, 255, 255, 0.08);
    color: #f1f5f9;
}

.tour-btn-skip {
    position: absolute;
    top: 10px;
    right: 12px;
    background: transparent;
    border: none;
    color: var(--text-muted, #94a3b8);
    font-size: 0.72rem;
    font-weight: 600;
    cursor: pointer;
    padding: 4px 6px;
}

.tour-btn-skip:hover {
    color: #f1f5f9;
}

#guideNavBtn {
    /* Matches existing .profile-btn sibling styling context; no override needed beyond icon spacing */
}
```

- [ ] **Step 2: Verify the file is syntactically valid CSS**

Run: `python3 -c "import re; content = open('static/css/tutorial.css').read(); assert content.count('{') == content.count('}'), 'brace mismatch'; print('OK', content.count('{'), 'rule blocks')"`
Expected output: `OK <N> rule blocks` with no assertion error.

- [ ] **Step 3: Commit**

```bash
git add static/css/tutorial.css
git commit -m "feat(tutorial): add spotlight overlay and tooltip CSS

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Tutorial JS core — overlay engine and step renderer (`static/js/tutorial.js`)

**Files:**
- Create: `static/js/tutorial.js`

**Interfaces:**
- Consumes: DOM only (no app.py functions needed for this task — cross-tab step navigation via
  `switchTab()` is added in Task 3). Consumes CSS classes produced by Task 1
  (`.tour-overlay-rect`, `.tour-overlay-highlight`, `.tour-tooltip`, etc.).
- Produces: global `window.FantaTour` object with methods `start()`, `maybeAutoStart()`,
  `next()`, `prev()`, `skip()` — all consumed by Task 3 (step data) and Task 4 (button wiring).
  Internal (not consumed elsewhere, but must exist for Task 2's own step-rendering logic):
  `_renderStep(index)`, `_computeOverlayRects(targetEl)`, `_positionTooltip(targetEl)`,
  `_teardown()`.

This task builds the **engine** with a hardcoded 2-step placeholder `STEPS` array (real 7-step
content is added in Task 3, replacing the placeholder) so the overlay/tooltip/navigation logic can
be verified end-to-end before wiring in real app selectors.

- [ ] **Step 1: Create `static/js/tutorial.js` with the full engine and a 2-step placeholder**

```javascript
/* ============================================================
   Tutorial Interattivo Spotlight — fanta-lab
   Zero-dependency walkthrough engine (vanilla JS, IIFE module).
   ============================================================ */

window.FantaTour = (function () {
    'use strict';

    // Placeholder steps for engine verification (Task 3 replaces this with the real 7-step tour).
    var STEPS = [
        { selector: 'body', title: 'Passo 1 (placeholder)', text: 'Testo placeholder 1.' },
        { selector: 'body', title: 'Passo 2 (placeholder)', text: 'Testo placeholder 2.' }
    ];

    var STORAGE_KEY = 'fanta_tour_done';
    var currentIndex = -1;
    var overlayEls = [];
    var tooltipEl = null;
    var resizeHandler = null;

    function _clearOverlay() {
        overlayEls.forEach(function (el) {
            if (el && el.parentNode) el.parentNode.removeChild(el);
        });
        overlayEls = [];
        if (tooltipEl && tooltipEl.parentNode) {
            tooltipEl.parentNode.removeChild(tooltipEl);
        }
        tooltipEl = null;
    }

    function _computeOverlayRects(targetEl) {
        var rect = targetEl.getBoundingClientRect();
        var vw = window.innerWidth;
        var vh = window.innerHeight;
        return {
            top: { top: 0, left: 0, width: vw, height: Math.max(0, rect.top) },
            bottom: { top: rect.bottom, left: 0, width: vw, height: Math.max(0, vh - rect.bottom) },
            left: { top: rect.top, left: 0, width: Math.max(0, rect.left), height: rect.height },
            right: { top: rect.top, left: rect.right, width: Math.max(0, vw - rect.right), height: rect.height },
            highlight: { top: rect.top - 4, left: rect.left - 4, width: rect.width + 8, height: rect.height + 8 }
        };
    }

    function _applyRectStyle(el, rectDef) {
        el.style.top = rectDef.top + 'px';
        el.style.left = rectDef.left + 'px';
        el.style.width = rectDef.width + 'px';
        el.style.height = rectDef.height + 'px';
    }

    function _renderOverlay(targetEl) {
        var rects = _computeOverlayRects(targetEl);
        var keys = ['top', 'bottom', 'left', 'right'];
        keys.forEach(function (key) {
            var el = document.createElement('div');
            el.className = 'tour-overlay-rect';
            _applyRectStyle(el, rects[key]);
            document.body.appendChild(el);
            overlayEls.push(el);
        });
        var highlightEl = document.createElement('div');
        highlightEl.className = 'tour-overlay-highlight';
        _applyRectStyle(highlightEl, rects.highlight);
        document.body.appendChild(highlightEl);
        overlayEls.push(highlightEl);
    }

    function _positionTooltip(targetEl, step) {
        var rect = targetEl.getBoundingClientRect();
        var vh = window.innerHeight;
        var spaceBelow = vh - rect.bottom;
        var spaceAbove = rect.top;
        var placeBelow = spaceBelow >= 160 || spaceBelow >= spaceAbove;

        tooltipEl = document.createElement('div');
        tooltipEl.className = 'tour-tooltip';

        var skipBtn = document.createElement('button');
        skipBtn.className = 'tour-btn-skip';
        skipBtn.textContent = 'Salta Tutorial ✕';
        skipBtn.onclick = function () { FantaTour.skip(); };
        tooltipEl.appendChild(skipBtn);

        var titleEl = document.createElement('div');
        titleEl.className = 'tour-tooltip-title';
        titleEl.textContent = step.title;
        tooltipEl.appendChild(titleEl);

        var textEl = document.createElement('div');
        textEl.className = 'tour-tooltip-text';
        textEl.textContent = step.text;
        tooltipEl.appendChild(textEl);

        var progressEl = document.createElement('div');
        progressEl.className = 'tour-tooltip-progress';
        progressEl.textContent = 'Passo ' + (currentIndex + 1) + ' di ' + STEPS.length;
        tooltipEl.appendChild(progressEl);

        var actionsEl = document.createElement('div');
        actionsEl.className = 'tour-tooltip-actions';

        var prevBtn = document.createElement('button');
        prevBtn.className = 'tour-btn tour-btn-secondary';
        prevBtn.textContent = 'Indietro';
        prevBtn.disabled = currentIndex === 0;
        prevBtn.onclick = function () { FantaTour.prev(); };
        actionsEl.appendChild(prevBtn);

        var nextBtn = document.createElement('button');
        nextBtn.className = 'tour-btn tour-btn-primary';
        nextBtn.textContent = (currentIndex === STEPS.length - 1) ? 'Fine' : 'Avanti';
        nextBtn.onclick = function () { FantaTour.next(); };
        actionsEl.appendChild(nextBtn);

        tooltipEl.appendChild(actionsEl);

        var arrow = document.createElement('div');
        arrow.className = 'tour-tooltip-arrow ' + (placeBelow ? 'tour-tooltip-arrow-top' : 'tour-tooltip-arrow-bottom');
        tooltipEl.appendChild(arrow);

        document.body.appendChild(tooltipEl);

        // Measure after insertion to get real tooltip dimensions.
        var tw = tooltipEl.offsetWidth;
        var th = tooltipEl.offsetHeight;
        var left = Math.min(Math.max(8, rect.left + rect.width / 2 - tw / 2), window.innerWidth - tw - 8);
        var top = placeBelow ? (rect.bottom + 14) : (rect.top - th - 14);
        top = Math.max(8, Math.min(top, window.innerHeight - th - 8));

        tooltipEl.style.left = left + 'px';
        tooltipEl.style.top = top + 'px';
    }

    function _renderStep(index) {
        _clearOverlay();
        if (index < 0 || index >= STEPS.length) return;
        var step = STEPS[index];
        var targetEl = document.querySelector(step.selector);
        if (!targetEl) {
            console.warn('[FantaTour] Target not found for step ' + index + ' (selector: ' + step.selector + '), skipping.');
            if (index < currentIndex || currentIndex === -1) {
                currentIndex = index;
                _advanceSkippingMissing(1);
            } else {
                currentIndex = index;
                _advanceSkippingMissing(-1);
            }
            return;
        }
        currentIndex = index;
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        _renderOverlay(targetEl);
        _positionTooltip(targetEl, step);
    }

    function _advanceSkippingMissing(direction) {
        var nextIndex = currentIndex + direction;
        if (nextIndex < 0) { _teardown(); return; }
        if (nextIndex >= STEPS.length) { _finish(); return; }
        _renderStep(nextIndex);
    }

    function _teardown() {
        _clearOverlay();
        currentIndex = -1;
        if (resizeHandler) {
            window.removeEventListener('resize', resizeHandler);
            window.removeEventListener('scroll', resizeHandler, true);
            resizeHandler = null;
        }
    }

    function _finish() {
        localStorage.setItem(STORAGE_KEY, 'true');
        _teardown();
    }

    function start() {
        _teardown();
        currentIndex = 0;
        _renderStep(0);
        resizeHandler = function () {
            if (currentIndex >= 0 && currentIndex < STEPS.length) {
                var step = STEPS[currentIndex];
                var targetEl = document.querySelector(step.selector);
                if (targetEl) {
                    _clearOverlay();
                    _renderOverlay(targetEl);
                    _positionTooltip(targetEl, step);
                }
            }
        };
        window.addEventListener('resize', resizeHandler);
        window.addEventListener('scroll', resizeHandler, true);
    }

    function next() {
        if (currentIndex === STEPS.length - 1) {
            _finish();
            return;
        }
        _renderStep(currentIndex + 1);
    }

    function prev() {
        if (currentIndex <= 0) return;
        _renderStep(currentIndex - 1);
    }

    function skip() {
        localStorage.setItem(STORAGE_KEY, 'true');
        _teardown();
    }

    function maybeAutoStart() {
        if (localStorage.getItem(STORAGE_KEY) === 'true') return;
        setTimeout(function () { start(); }, 600);
    }

    return {
        start: start,
        next: next,
        prev: prev,
        skip: skip,
        maybeAutoStart: maybeAutoStart
    };
})();
```

- [ ] **Step 2: Verify the file is syntactically valid JS**

Run: `node --check static/js/tutorial.js`
Expected: no output, exit code 0 (Node.js syntax-checks without executing).

If `node` is not available in this environment, instead run:
`python3 -c "content = open('static/js/tutorial.js').read(); assert content.count('{') == content.count('}'); assert content.count('(') == content.count(')'); print('balanced')"`
Expected: `balanced` with no assertion error.

- [ ] **Step 3: Commit**

```bash
git add static/js/tutorial.js
git commit -m "feat(tutorial): add spotlight overlay engine with placeholder steps

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Real 7-step tour content with cross-tab navigation

**Files:**
- Modify: `static/js/tutorial.js` (replace the placeholder `STEPS` array; add `requiresTab`
  support to `_renderStep`)

**Interfaces:**
- Consumes: the global `switchTab(tabId)` function already defined in `app.py`'s embedded
  `<script>` block (confirmed present at `app.py:5439`, accessible as `window.switchTab` since
  it's a top-level `function` declaration in the page's inline script — no import needed, it's
  available in the same global `window` scope as `tutorial.js` once both are loaded in the same
  HTML page).
- Produces: same `FantaTour` public API as Task 2 (`start`, `next`, `prev`, `skip`,
  `maybeAutoStart`) — signatures unchanged, only internal `STEPS` content and `_renderStep`
  behavior change.

- [ ] **Step 1: Replace the placeholder `STEPS` array with the real 7-step tour**

In `static/js/tutorial.js`, replace this block:

```javascript
    // Placeholder steps for engine verification (Task 3 replaces this with the real 7-step tour).
    var STEPS = [
        { selector: 'body', title: 'Passo 1 (placeholder)', text: 'Testo placeholder 1.' },
        { selector: 'body', title: 'Passo 2 (placeholder)', text: 'Testo placeholder 2.' }
    ];
```

with:

```javascript
    var STEPS = [
        {
            selector: '#btnLeagueSettings',
            title: 'Pannello Impostazioni',
            text: 'Configura qui budget di lega, numero di squadre e slot per ruolo. Puoi modificarli in qualsiasi momento.'
        },
        {
            selector: '#sideNav-strategy',
            title: 'Blueprint Strategici',
            text: 'Scegli tra 5 piani tattici pre-configurati (es. Trazione Anteriore, Moneyball) con soglie di spesa per ruolo calcolate sul tuo budget di lega.'
        },
        {
            selector: '#tab-listone',
            requiresTab: 'listone',
            title: 'Colonne Listone',
            text: 'Le colonne chiave: Prezzo Equo (il massimo razionale da offrire), P50 (punti attesi), e Surplus di Mercato (l\'affare potenziale rispetto alla quotazione).'
        },
        {
            selector: '.medical-badge',
            requiresTab: 'listone',
            fallbackSelector: '#tab-listone',
            title: 'Scheda Clinica',
            text: 'Clicca il badge medico di un giocatore per aprire la sua cartella clinica: stato di rischio, giorni di infortunio, e metriche avanzate xG/xA.'
        },
        {
            selector: '#sideNav-draft',
            title: 'Modulo Asta',
            text: 'Qui gestisci l\'asta live: assegnazione giocatori, tracciamento budget, live draft.'
        },
        {
            selector: '#sideNav-lineup',
            title: 'Formazione Settimanale',
            text: 'Calcola la formazione ottimale della giornata in base a probabili formazioni, quote e xPts.'
        },
        {
            selector: '#sideNav-audit',
            title: 'Valutatore & Scambi',
            text: 'Analizza la classifica di lega post-asta e valuta scambi vantaggiosi con gli altri manager nella sezione Scambi.'
        }
    ];
```

- [ ] **Step 2: Add `requiresTab` and `fallbackSelector` support to `_renderStep`**

In `static/js/tutorial.js`, replace this function:

```javascript
    function _renderStep(index) {
        _clearOverlay();
        if (index < 0 || index >= STEPS.length) return;
        var step = STEPS[index];
        var targetEl = document.querySelector(step.selector);
        if (!targetEl) {
            console.warn('[FantaTour] Target not found for step ' + index + ' (selector: ' + step.selector + '), skipping.');
            if (index < currentIndex || currentIndex === -1) {
                currentIndex = index;
                _advanceSkippingMissing(1);
            } else {
                currentIndex = index;
                _advanceSkippingMissing(-1);
            }
            return;
        }
        currentIndex = index;
        targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        _renderOverlay(targetEl);
        _positionTooltip(targetEl, step);
    }
```

with:

```javascript
    function _renderStep(index) {
        _clearOverlay();
        if (index < 0 || index >= STEPS.length) return;
        var step = STEPS[index];
        var direction = (index >= currentIndex) ? 1 : -1;

        if (step.requiresTab && typeof window.switchTab === 'function') {
            window.switchTab(step.requiresTab);
        }

        setTimeout(function () {
            var targetEl = document.querySelector(step.selector);
            if (!targetEl && step.fallbackSelector) {
                targetEl = document.querySelector(step.fallbackSelector);
            }
            if (!targetEl) {
                console.warn('[FantaTour] Target not found for step ' + index + ' (selector: ' + step.selector + '), skipping.');
                currentIndex = index;
                _advanceSkippingMissing(direction);
                return;
            }
            currentIndex = index;
            targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            _renderOverlay(targetEl);
            _positionTooltip(targetEl, step);
        }, step.requiresTab ? 120 : 0);
    }
```

- [ ] **Step 3: Verify the file is syntactically valid JS**

Run: `node --check static/js/tutorial.js`
Expected: no output, exit code 0.

If `node` unavailable, run the brace/paren-balance Python check from Task 2 Step 2 instead.

- [ ] **Step 4: Commit**

```bash
git add static/js/tutorial.js
git commit -m "feat(tutorial): wire real 7-step tour content with cross-tab navigation

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Wire tutorial into `app.py` (link/script tags, Guida button, auto-start)

**Files:**
- Modify: `app.py` (add `<link>`/`<script>` tags in `<head>`, add navbar button, add
  `maybeAutoStart()` call after existing `window.onload`)

**Interfaces:**
- Consumes: `FantaTour.start()` and `FantaTour.maybeAutoStart()` from Task 3's `tutorial.js`.
- Produces: nothing new consumed by later tasks (this is the final integration task).

- [ ] **Step 1: Add the CSS `<link>` tag to the `<head>` section**

In `app.py`, find this exact line (confirmed present at line 1792):

```html
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
```

Add immediately after it:

```html
    <link rel="stylesheet" href="/static/css/tutorial.css">
```

- [ ] **Step 2: Add the navbar "❓ Guida" button**

In `app.py`, find this exact block (confirmed present around line 3297-3300):

```html
                    <button id="btnLeagueSettings" class="profile-btn hide-mobile" onclick="openLeagueSettingsModal()" title="Configura Budget, Slot e Squadre">
                        <i class="fa-solid fa-gear"></i>
                        <span>Lega</span>
                    </button>
```

Add immediately after this block's closing `</button>`:

```html

                    <button id="guideNavBtn" class="profile-btn hide-mobile" onclick="FantaTour.start()" title="Avvia il tour guidato">
                        <i class="fa-solid fa-circle-question"></i>
                        <span>Guida</span>
                    </button>
```

- [ ] **Step 3: Add the JS `<script>` tag and the auto-start call**

In `app.py`, find this exact line (confirmed present at line 8247):

```html
        window.onload = init;
    </script>
</body>
</html>
```

Replace it with:

```html
        window.onload = function () {
            init();
            if (typeof FantaTour !== 'undefined') {
                FantaTour.maybeAutoStart();
            }
        };
    </script>
    <script src="/static/js/tutorial.js"></script>
</body>
</html>
```

(Note: `tutorial.js` is loaded via a separate `<script src="...">` tag placed just before
`</body>`, after the inline `<script>` block closes, so `switchTab` and other inline-script
globals are already defined on `window` by the time `tutorial.js` executes. The
`window.onload` handler references `FantaTour` — since `window.onload` fires only after all
`<script>` tags including the external `tutorial.js` have executed and defined
`window.FantaTour`, this ordering is safe.)

- [ ] **Step 4: Start the dev server and verify via curl**

Run: `python app.py &` (or run in background), wait 2 seconds, then:

```bash
curl -s http://127.0.0.1:5050/ -o /tmp/tutorial_check.html
grep -c 'tutorial.css' /tmp/tutorial_check.html
grep -c 'tutorial.js' /tmp/tutorial_check.html
grep -c 'guideNavBtn' /tmp/tutorial_check.html
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5050/static/css/tutorial.css
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5050/static/js/tutorial.js
```

Expected: each `grep -c` returns a number `>= 1`; both `curl -w "%{http_code}"` calls print `200`.

(Adjust the port in the curl commands if `python app.py`'s startup log shows a different port —
check the terminal output for the actual bound port before running these checks.)

- [ ] **Step 5: Stop the dev server**

Stop the `python app.py` background process (find its PID via `jobs` or the shell tool's process
list, and terminate it — do not use `pkill`/`killall`; use a specific PID).

- [ ] **Step 6: Run the full test suite to confirm zero regressions**

Run: `pytest tests/ -v 2>&1 | tail -15`
Expected: `89 passed` (or the current total from `main` at plan-execution time), plus exactly one
pre-existing unrelated error in `tests/test_dual_track_and_features.py::test` (a fixture
collection issue unrelated to this change) — no other failures.

- [ ] **Step 7: Commit**

```bash
git add app.py
git commit -m "feat(app): wire interactive tutorial into HTML template with Guida button and auto-start

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Final Verification

- [ ] Run `pytest tests/ -v` one more time from repo root and confirm the only failure is the
      pre-existing `tests/test_dual_track_and_features.py::test` collection error.
- [ ] Run `git log --oneline -5` and confirm all 4 task commits are present in order.
- [ ] Start `python app.py` once more, curl `/`, and grep for `sideNav-strategy`, `tab-listone`,
      `sideNav-draft`, `sideNav-lineup`, `sideNav-audit` to confirm all 7-step target selectors
      referenced in Task 3's `STEPS` array still exist in the served HTML (this catches any
      accidental selector drift between this plan's assumptions and the current `app.py` state).
      Stop the server afterward.
