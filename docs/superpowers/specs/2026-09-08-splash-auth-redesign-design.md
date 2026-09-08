# Design Spec: Splash / Personal Auth Flow Redesign & Nav Restyle

**Date:** 2026-09-08
**Status:** Approved
**Author:** AI pairing session with @AlessioPicco
**Branch target:** `ui-glowup` (extends the existing, unmerged UI glow-up work)

## 1. Context & Motivation

The user's handwritten notes (`~/Downloads/Scansione 8 set 2026.pdf`) sketched a
desired app-open experience: a branded splash screen, a returning-user
"Bentornato" shortcut, and a home screen with large, game-mode-style square
tabs. This spec covers only the **first sub-project** identified during
brainstorming from those notes — splash + personal auth flow + nav visual
restyle. Two other sub-projects surfaced during discussion are explicitly
**out of scope** here and will get their own brainstorming cycles later:

- Reorganizing the 9 existing tabs into 5 macro-areas (Asta, Listone, Analisi,
  Scambi, "La tua giornata") as literally sketched — deferred.
- Any server-side account/login system, and the broader question of a
  commercial (private) vs. open-source dual-repo strategy — deferred. This
  cycle stays on **localStorage-only** persistence, consistent with the
  existing dual-track architecture (see
  `docs/superpowers/specs/2026-09-08-rebrand-fantaofficina-design.md` and the
  original Pilastro 1 dual-track design).

## 2. Current State (branch `ui-glowup`, unmerged)

- `#splashIdentityGate` already exists: a full-screen gate showing a grid of
  local "team profile" cards (`renderSplashTeamGrid`), backed by
  `localStorage['fanta_active_profile_id']`. `hasStoredProfile` (a JS boolean,
  computed once at load from that key) gates whether this shows.
- `#maestroIntroOverlay` is a separate, one-time "Il Maestro" welcome overlay
  shown once per browser (`localStorage['fanta_maestro_intro_done']`),
  triggered right after `completeSplashTeamSelection()`.
- `#sessionLoginModal` is the PIN gate (`LEAGUE_PIN` / `ADMIN_PIN`, checked
  against `localStorage['fanta_session_auth']`) — currently conflated in
  `maybeStartIdentityGate()` with the identity gate's precedence logic (PIN
  modal takes precedence if visible).
- No literal splash/loading screen with logo + spinner exists yet — the app
  renders directly into whichever gate applies.
- Bottom nav (`.nav-item`, 9 items) and sidebar nav (`.sidebar-nav-btn`, 9
  items) already carry the Officina Vittoriana brass/gold theme, but are
  simple flex rows with small icons — not the "square game-mode tile" look
  from the sketch.

## 3. Scope of This Redesign

### 3.1 Branded splash screen (new)
- New full-screen overlay, shown **immediately on page load**, before any
  gate logic runs: "La FantaOfficina" wordmark/logo, a spinner, and a small
  version string (e.g. `v.1.00`), styled in the Officina Vittoriana theme
  (brass/gold, existing fonts).
- **Duration:** fixed ~1.2s (a single timer, not tied to any data fetch —
  the probable-lineups dataset is produced by an offline batch pipeline
  (`core/ingestion/dynamic/`) and is irrelevant to this splash's timing).
  After the timer elapses, fade out and proceed to the personal-auth
  decision (3.2).
- Implementation note: this is a pure presentational gate layered in front
  of the existing gates — it does not change what `maybeStartIdentityGate()`
  or the PIN modal do, only delays their visibility by the fixed timer.

### 3.2 Personal auth gate — decouple from the PIN gate
Today, `hasStoredProfile` and the PIN gate are checked together in
`maybeStartIdentityGate()`. This redesign makes explicit that these are two
**independent** gates with independent purposes:

- **Personal identity gate** (`fanta_active_profile_id` in localStorage):
  governs everyday app access, valid year-round, decoupled from the auction.
  - If **not set** → show the existing `#splashIdentityGate` team-profile
    picker unchanged (same markup/logic, `renderSplashTeamGrid` /
    `completeSplashTeamSelection`).
  - If **set** → show a new **"Bentornato" screen**: a lightweight full-screen
    panel styled like `#splashIdentityGate` displaying "Ciao! Bentornato,
    `<team name>`" (resolve the name from `auctionState.teams` by
    `activeProfileId`, matching the existing pattern in
    `renderSplashTeamGrid`), with a single primary action to continue into
    the app, and a text link **"Non sei tu?"**.
    - Clicking "Non sei tu?" does **not** clear `fanta_active_profile_id`
      immediately — it re-opens `#splashIdentityGate` (the team picker) so
      the user can pick a different profile. Only selecting a new team via
      `completeSplashTeamSelection()` overwrites the stored profile id (this
      matches existing behavior — no destructive action needed).
- **PIN gate** (`#sessionLoginModal`, `LEAGUE_PIN`/`ADMIN_PIN`) stays exactly
  as-is functionally, but is no longer part of the "first access" concept.
  It continues to gate the Asta Live tab/actions specifically (this is
  already how `is_participant`/`is_admin` are used server-side — no backend
  change needed). Precedence rule when both could apply: if the PIN modal is
  already open when the identity/Bentornato flow would show, keep current
  behavior (PIN modal wins, identity gate stays hidden until PIN modal
  closes) — this preserves the existing `maybeStartIdentityGate()`
  precedence check, just documented as intentional rather than incidental.
- The Maestro one-time intro overlay (`#maestroIntroOverlay`) is unaffected —
  still shown once per browser after the identity gate resolves for the
  first time.

### 3.3 Home navigation restyle — "game mode tiles"
- Applies to **both** `.sidebar-nav-btn` (desktop sidebar) and `.nav-item`
  (mobile bottom nav) — the same 9 existing tabs (`draft`, `targets`,
  `strategy`, `rosters`, `listone`, `ai`, `lineup`, `audit`, `trades`), no
  tab reorganization, no renaming, no removal.
- Visual direction: square/tile-shaped buttons (larger icon-to-label ratio,
  clear box boundary per tab — evoking distinct "game mode" selections)
  rather than the current slim flex rows / bottom-nav strip items.
- Icons: reuse Font Awesome (already loaded — verify via
  `grep -n "font-awesome\|fa-solid" web/app.py`) for every tab icon; no
  emoji, consistent with prior UI glow-up decisions.
- Animation: purposeful micro-interactions only — hover/focus state and
  active-tab state transitions (scale/glow/underline in the existing
  brass/gold palette), not decorative motion unconnected to state.
- Must remain usable at the current tab count (9) and at mobile width —
  verify readability/tap-target size against the real 9-tab list, not an
  idealized smaller set.
- Reuse existing design tokens (`:root` CSS custom properties, existing
  `cubic-bezier` easing) as the foundation per the `fantalab-ui-designer`
  agent's operating constraints; extend deliberately, do not replace the
  Officina Vittoriana theme wholesale.

### 3.4 Implementation ownership
This visual work (3.1 splash, 3.2's presentational panels, 3.3 nav restyle)
will be implemented by dispatching the existing custom agent
`fantalab-ui-designer` (`.github/agents/fantalab-ui-designer.agent.md`),
created specifically for high-craft visual/UI work on this app. The
non-visual gating logic (3.2's localStorage read/precedence rules) is
plain JS logic and can be written directly or by the same agent — it is not
split into a separate task since it's tightly coupled to the panels it
controls.

## 4. Out of Scope (explicit)

- No server-side accounts, sessions, or database of any kind (Upstash,
  Postgres, etc.) — deferred to a future, separately-scoped **personal**
  (non-open-source) feature track.
- No change to `LEAGUE_PIN`/`ADMIN_PIN` semantics, `is_participant`/`is_admin`
  logic, or any backend/`core/config.py` code.
- No reorganization of the 9 tabs into 5 macro-areas — deferred sub-project.
- No changes to the Scambi tab's suggestion logic — deferred sub-project
  (separately identified from the same handwritten notes).
- No changes to `live_bridge/` or `fantalab_room_id`/`fantalab_shard` keys.
- No new npm/build tooling — stays vanilla HTML/CSS/JS inline in
  `web/app.py`, consistent with the existing architecture.

## 5. Data / Storage Contract

All new state lives in **existing or new localStorage keys** on the client,
no new server endpoints:

| Key | Existing/New | Purpose |
|---|---|---|
| `fanta_active_profile_id` | existing | Determines personal identity gate vs. Bentornato screen |
| `fanta_maestro_intro_done` | existing | One-time Maestro welcome, unaffected |
| `fanta_session_auth` | existing | PIN gate for Asta Live, unaffected, semantically decoupled from "first access" |
| *(none new)* | — | The splash screen (3.1) needs no persisted state — it always shows once per page load |

## 6. Acceptance Criteria

1. On every full page load, a branded splash (logo + spinner + version)
   shows for a fixed ~1.2s before any auth gate becomes visible.
2. After the splash: if no team profile is stored, the existing
   `#splashIdentityGate` team picker shows unchanged; if a profile is
   stored, a new "Ciao! Bentornato, `<team>`" screen shows instead, with a
   working "Non sei tu?" link that re-opens the team picker without
   deleting any stored profile data.
3. The PIN gate (`#sessionLoginModal`) behavior for Asta Live access is
   unchanged — verified by re-running the app's existing PIN-login test
   path manually (Playwright smoke test, PIN `2026`).
4. All 9 existing tabs are reachable, in the same order, via both the
   restyled sidebar and restyled bottom nav, on desktop and mobile widths.
5. No emoji appear in the nav; all icons are Font Awesome glyphs already
   available in the app's loaded icon set.
6. `pytest -q` baseline stays at 89 passed / 1 pre-existing unrelated error
   (this is a frontend-only change; no Python test should be affected, but
   the baseline must be re-verified after implementation).
7. Manual Playwright (or equivalent headless) smoke test confirms zero
   console/page errors through: splash → Bentornato (or team picker) →
   Maestro intro (first run only) → each of the 9 tabs opens without a
   blank pane.
