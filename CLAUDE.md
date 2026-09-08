# CLAUDE.md — Project Guide

## What This Repo Is (Fork Context)

This repo (`footballerdata`) is a **fork of [spectrelabo/fantaofficina](https://github.com/spectrelabo/fantaofficina)** ("La FantaOfficina"), a Serie A fantasy-football (Fantacalcio) analytics framework: data scraping → ML projections → VORP auction pricing → MILP roster optimization → a Flask "Live Auction Command Center" web app.

**The fork's mission is different**: transform this into a **player data & statistics explorer**. We only care about *info and stats about players* (ratings, xG/xA, injuries, minutes, projections, profiles). We do **NOT** care about:
- League management ("Lega" settings, multi-team state, admin/battitore)
- Team/squad management (rose, formations/lineup solver, trades, post-auction audit)
- The live draft engine and FantaLab bridge
- Auction *mechanics*: budgets, bidding, stop-loss, tactical presets, roster slots

**Deliberate exception — credits & VORP are KEPT**: although born in the fantacalcio economy, `vorp_points`, `prezzo_fair_*`, `target/clearing_price_*`, `Prezzo_Consigliato_Cr` (official list price) and `FVM_1000` work as **general player quality scores** (a good player = a high score, regardless of fantasy play). VORP = value over a replacement-level player at the same role; fair price = VORP rescaled to credits. Caveats when reading them as quality: VORP baselines are **role-relative** (cross-role comparison is skewed, e.g. keepers are compressed); fair prices are budget-dependent rescalings (500 vs 1000 variants differ only by a factor); `surplus_value_cr` (fair − official price) is a *market-undervaluation* signal, not pure quality.

The pivot has NOT started yet — the code below describes the current (upstream) state, with a keep/remove map at the end.

## Repo Layout (current state)

```
core/
  config.py                  # Central config: paths, seasons, team maps, scoring weights
  config_defaults.py         # League defaults (budget 500, roster 3P/8D/8C/6A, 10 teams, admin pwd)
  ingestion/static/          # The data pipeline (numbered stages, see below)
  ingestion/dynamic/         # Weekly live matchday feed (api-football + fantacalcio.it odds/lineups)
  copilot/                   # LLM chat layer (Ollama/OpenAI/Gemini/Groq providers, prompt RAG)
  models/                    # Docs only (no code)
modules/
  common/data_provider.py    # Shared data layer for overlay (live feed) access
web/
  app.py                    # Flask entrypoint (~75 lines): app assembly, index route, blueprint registration, main()
  config.py                 # Paths, .env loading, persona, injuries cache, pricing defaults (~100 lines)
  data.py                   # load_dataset() + fascia tiering (~40 lines)
  pricing.py                # get_dynamic_fair_prices() VORP/fair-price quality scoring (~80 lines)
  players_api.py            # Blueprint: /api/players payload builder (~185 lines)
  ai_api.py                 # Blueprint: /api/ai_{status,test,query} — LLM copilot + local reasoner (~295 lines)
  templates/index.html      # Jinja template (~450 lines): page structure, bot persona vars
  static/css/main.css       # Theme stylesheet (~970 lines, purged of dead selectors)
  static/css/tutorial.css   # Guided-tour styles
  static/js/app.js          # Frontend logic (~880 lines): listone render, drawer, AI chat, tour hooks
  static/js/tutorial.js     # "FantaTour" guided tour (3 steps)
data/                        # Generated artifacts (dataset_finale.csv etc.)
dataset_finale.csv           # Root copy of the master dataset (533 players, 57 cols)
run_pipeline.py              # CLI: --step N / --from N over ordered stages [1,3,4,5,6,8,9,10,7]
export_player_history.py     # Exports data/player_history.json (per-season career rows, feeds trajectory chart)
demo.py                      # Zero-config terminal demo (hype-trap, volatility, MILP, lookup)
export_dataset.py            # Exports dataset_finale_{500,1000}.csv with unified prezzo_fair
tests/                       # pytest suites + 1 HTTP smoke script (test_dual_track_and_features.py)
docs/                        # Architecture docs (pipeline, scoring, live command center, UI handoff)
```

## Data Pipeline (core/ingestion/static/)

Ordered stages (note: CLI step 7 = Excel export, runs last):

| Step | File | Source | Output |
|---|---|---|---|
| 1 | `01_scrape_historical.py` | fantacalcio.it (11 seasons) + football-data.co.uk | `data/storico_giocatori_{raw,aggregato}.csv`, team indices. Cols: mv/mfv 3y weighted means, std, trend, availability, per-game rates |
| 3 | `03_update_listone.py` | Local Excel `data/Quotazioni_Fantacalcio_Stagione_2026_27_latest.xlsx` (manual download) | Active roster + official prices (Qt.A), roles P/D/C/A. NOTE: `NN_*`, `Prob_*`, `Clean_Sheet_%` columns are placeholder constants, never filled |
| 4 | `04_scrape_understat.py` | Understat API (Serie A) | xG/xA/npxG/shots per-90 aggregations |
| 4b | `04b_scrape_lineups.py` | Sofascore API (NOT in CLI, run manually) | `starts/sub_apps/minutes/is_starter/starter_pct` for 2026/27 first matchdays |
| 5 | `05_scrape_injuries.py` | Transfermarkt (multithreaded) | `giorni/n_infortuni_3y`, severity, malus + `data/tm_injuries_cache.json` |
| 5b | `05b_scrape_attributes.py` | Transfermarkt profiles (NOT in CLI, run manually) | `age/height_cm/foot/market_value_eur/contract_until` + `data/tm_attributes_cache.json` (incremental) |
| 6 | `06_build_dataset.py` | Merges all above via 4-tier fuzzy name matching (`MANUAL_FUZZY_MAP` in config) | **`data/dataset_finale.csv`** + `score_composito` |
| 8 | `08_quantile_points_model.py` | Trains 3 GradientBoosting quantile regressors (P10/P50/P90) on lagged historical seasons; **target = season rating-volume `pg × mv` (fantasy-neutral, retargeted in Step 4b)** | Adds `predicted_contrib_p10/p50/p90`, `contrib_volatility_spread`. Models NOT persisted |
| 9 | `09_vorp_auction_pricing.py` + `target_pricing.py` | Replacement-level math + econometric price regression | Adds `vorp_points`, `target/clearing/fair prices`, `surplus_value_cr` |
| 10 | `10_roster_optimizer.py` | scipy MILP knapsack | Prints optimal 25-player squad (no file output) |
| 7 | `07_generate_excel.py` | `dataset_finale.csv` | `data/analisi_fantacalcio_completa.xlsx` multi-tab workbook |

### dataset_finale.csv schema (57 columns, 533 players)

Column groups: identity (player, role, role_mantra, team) → auction prices (cols 5-12) → historical aggregates (13-24) → Understat xG/xA (25-31) → team indices (32-33) → injuries (34-37) → Sofascore lineups (38-42) → composite scores (43-44) → ML quantile projections (predicted_contrib_p*, contrib_volatility_spread) → VORP/pricing → TM attributes (age/height_cm/foot/market_value_eur/contract_until). Full header in the CSV itself.

### Key hardcoded Fantacalcio assumptions

- Budgets 500/1000 credits; 25-player roster 3P/8D/8C/6A (but 09 uses 4/9/9/7 — inconsistent); 10-team league
- Role codes P/D/C/A + `role_mantra`; MFV/fantavoto (rating + fantasy bonus/malus) in historical aggregates only — the ML target was retargeted to `pg × mv` (Step 4b); `mfv` dropped from model features
- Injury "malus" designed to discount fantasy auction value
- `score_composito` weights include fantavote/bonus-probability terms (`SCORE_WEIGHTS` in `core/config.py`)
- Quotazioni xlsx filename hardcoded to season 2026_27; Serie-A-only team maps

## Web App (web/) — structure

Standard Flask layout: split backend (Step 4a) + extracted frontend (Step 3):

- `web/app.py` (~75 lines) — entrypoint: Flask app, cache headers, `/` index route, blueprint registration, `main()`
- `web/config.py` (~100 lines) — paths, `.env` loading, `APP_ENV`/`IS_PERSONAL`, bot persona, `INJURIES_CACHE`, pricing defaults (`DEFAULT_BUDGET`/`DEFAULT_ROSTER_SLOTS`/`DEFAULT_N_TEAMS`)
- `web/data.py` (~40 lines) — `load_dataset()` + fascia tiering
- `web/pricing.py` (~80 lines) — `get_dynamic_fair_prices()` VORP/fair-price quality scoring (in-memory cache)
- `web/players_api.py` (~185 lines) — Blueprint `/api/players`: full player payload (prices, VORP, medical, understat, quantiles)
- `web/ai_api.py` (~295 lines) — Blueprint `/api/ai_{status,test,query}`: LLM copilot integration + local rule-based reasoner
- `web/__init__.py` — puts repo root on `sys.path` so `web.*` and `core.*` imports work in script/package/Vercel modes
- `web/templates/index.html` (~450 lines) — Jinja template; vars: `bot_name`, `bot_subtitle`, `bot_avatar_text`, `bot_avatar_image`, `bot_badge`, `bot_greeting`, `is_personal`
- `web/static/css/main.css` (~970 lines) — "Officina Vittoriana" dark theme, purged of dead selectors
- `web/static/js/app.js` (~880 lines) — listone render + filters/sort, Player Detail Drawer, AI chat, boot splash/maestro mascot
- `web/static/js/tutorial.js` — 3-step guided tour

2 tabs: `listone` (player list — the stats core, default active) and `ai` (copilot chat "Il Maestro").

### Route map (after Step 1 backend strip)

- **Trajectory (KEPT, Step 4c)**: `/api/player_history?player=<name>` — per-season career rows (season/team/pg/mv/gol/assist/mfv) from `data/player_history.json`, normalized-name keyed; 404 = no Serie A history. Drawer section "Traiettoria Carriera" renders an SVG mv-per-season chart.
- **Player stats (KEPT)**: `/api/players` — loads `dataset_finale.csv`, richest payload: prices, score, P10/P50/P90, spread, VORP, bonus range, injury audit, Understat metrics, quantile profile, starter status. Decoupled from auction state; pricing computed with fixed defaults (budget 1000, slots 3/8/8/6, 10 teams) via `get_dynamic_fair_prices()`.
- **Copilot (KEPT)**: `/api/ai_status`, `/api/ai_test`, `/api/ai_query` — player deep-dive/comparison/recommendations only (squad_diagnostic branch removed). Local rule-based fallback reasoner needs no LLM key.
- **REMOVED (404)**: `/api/settings`, `/api/state`, `/api/sync_state`, `/api/assign`, `/api/undo`, `/api/favorite`, `/api/reset`, `/api/live/snapshot`, `/api/auth_admin`, `/api/auth/login`, `/api/session/reset`, `/api/lineup/solve`, `/api/audit/rankings`, `/api/trades/*`

Frontend keepers: `tab-listone` + `renderListone()` + filters/sorts; **Player Detail Drawer** `openPlayerDetailDrawer()` — price/value, Finestra Medica (injury history), Understat volumes, Traiettoria Carriera (SVG per-season mv chart), quantile profile, starter/minutes. No polling, no gates, no `auctionState`.

## Commands

```bash
# Setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Web app (port 5050)
python3 web/app.py

# Pipeline
python run_pipeline.py              # full run
python run_pipeline.py --step 6     # single stage
python run_pipeline.py --from 8     # ML stages onward

# Demo (no scraping needed)
python demo.py

# Tests (64 unit tests pass; test_dual_track_and_features.py is an HTTP smoke script needing the web app on :5050)
python -m pytest tests/ -x -q
```

Optional `.env` keys: `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY` (copilot), `API_FOOTBALL_KEY` (dynamic feed), `ADMIN_PASSWORD`. CI: only `.github/workflows/dynamic_feed.yml` (scheduled matchday feed → `data-feed` branch). Deploys to Vercel via `vercel.json` → `web/app.py`.

## Refactor Plan: Player-Stats-Only Pivot

### KEEP (player data core)
- Pipeline stages **1, 4, 4b, 5** (historical ratings, Understat, Sofascore lineups, injuries) — generic player analytics
- Stage **6** (dataset build/fuzzy matching) — keep, strip fantasy scoring columns
- Stage **9** (VORP + fair pricing) — **KEEP, reinterpreted as quality scoring** (see "Deliberate exception" above). Keeps `vorp_points`, `prezzo_fair_*`, `target/clearing_price_*` in the dataset; the web UI keeps showing them as quality/value columns
- ~~ML stage **8** concept — retarget away from `pg × mfv`~~ — **DONE (Step 4b: target = `pg × mv` season rating-volume; columns `predicted_contrib_*`)**
- Web: `/api/players`, tab-listone, Player Detail Drawer, filters/sort/search, copilot (player Q&A only)
- `core/ingestion/dynamic/` — live status/lineups/form feed is genuinely useful player info
- Tests for kept components; docs update

### REMOVE (fantasy/league/team)
- ~~Stages 10/7~~ — still pending decision (Excel export could become a stats-only export)
- ~~`modules/lineup`, `modules/valuation`, `modules/trades`, `modules/auction`, `live_bridge/`~~ — **DONE (removed)**
- Web: ~~league settings, shared auction state (Redis/JSON), assign/undo, admin auth, FantaLab sniffer, market inflation, TACTICAL_PRESETS~~ — **DONE (backend removed in Step 1)**; the frontend tabs/UI (targets/strategy/rosters/lineup/audit/trades/draft, modals, admin JS, sniffer JS) are still present but inert — removal is Step 2
- `core/config_defaults.py` league constants; `ADMIN_*`/`LEAGUE_PIN` auth — done for the web app; config_defaults.py itself still exists (used by pipeline stages 9/10)

### Pivot progress
- **Step 1 (DONE)**: backend strip of `web/app.py` — removed all league/auction/auth/live/lineup/audit/trades routes, Redis helpers, auction state, TACTICAL_PRESETS, market inflation; decoupled `/api/players` (no is_assigned/is_favorite/market_index; fixed pricing defaults: budget 1000, slots 3/8/8/6, 10 teams for VORP baselines); `/api/ai_query` reduced to player Q&A (squad_diagnostic branch removed); frontend keeps booting via a static `auctionState` stub (no polling, no identity/session gates). Deleted `modules/{lineup,valuation,trades,auction}`, `live_bridge/` and their tests; smoke test `tests/test_dual_track_and_features.py` pruned to kept surface (72 checks, incl. removed-endpoints-404 + node --check).
- **Step 2 (DONE)**: frontend strip — removed tabs draft/targets/strategy/rosters/lineup/audit/trades, all their modals (target/pitch-picker/profile/custom-tactic/league-settings/inflation/admin/session), identity gates, admin/session JS, FantaLab sniffer JS, target/profile/preset systems, market-badge JS, draft helpers (search/assign/undo/recent); sidebar/bottom-nav reduced to Listone + AI; listone is the default active tab; `tutorial.js` pruned to 3 steps; AI quick-chips retargeted to player queries; branding → footballerdata. `web/app.py` now ~3.8k lines (from 9.1k). Known leftover: ~1.7k lines of inline CSS still contain dead selectors for removed UI (inert; cleanup happens in Step 3 when CSS moves to its own file).
- **Step 3 (DONE)**: frontend extraction — `HTML_TEMPLATE` string deleted; frontend now lives in `web/templates/index.html` (Jinja), `web/static/css/main.css` (1733 → 968 lines: 130 dead rules + 145 dead selectors + 8 dead keyframes purged), `web/static/js/app.js` (dead `showToast`/toast UI removed). `web/app.py` is pure Python (~720 lines, from 9116 pre-pivot) using `render_template()` + Flask built-in static serving. Smoke test updated to check external assets (78/78).
- **Step 4a (DONE)**: backend split — `web/app.py` (720 lines) → entrypoint (~75) + `web/config.py` (paths/.env/persona/injuries/pricing defaults) + `web/data.py` (`load_dataset` + fasce) + `web/pricing.py` (VORP/fair-price) + `web/players_api.py` (Blueprint `/api/players`) + `web/ai_api.py` (Blueprint `/api/ai_*`); `web/__init__.py` bootstraps `sys.path` for script/package/Vercel import modes. Also fixed: `core/copilot/__init__.py` broken absolute imports (`from copilot.*` → relative) so the LLM copilot path actually engages; smoke-script helper renamed `test()` → `check()` (was breaking pytest collection). Unit tests 64/64, smoke 78/78.
- **Step 4b (DONE)**: ML retargeting — stage 8 target `pg × mfv` (fantasy pts) → `pg × mv` (season rating-volume); features drop fantasy-derived `mfv`, add rating-consistency `std_mv`; columns renamed `predicted_contrib_p10/p50/p90` + `contrib_volatility_spread`; stage 9 VORP rebased on new P50 and made price-preserving (target/clearing/fair prices are ML-independent and are no longer recomputed when already present — protects observed clearing prices now that Asta.xlsx/quotazioni cache are absent); web payload `pts_exp/floor/ceil/spread` → `contrib_*`; UI labels de-fantasy-ized ("Contributo Atteso", profile threshold recalibrated to spread median 150); fixed latent `.str.upper()` bug in stage 8 player_id fallback; storico rebuilt via stage 1 scrape (11 seasons, 7291 rows; football-data.co.uk unreachable — team indices empty, stage-6-only input). OOT validation on 2025-26: 80% CI coverage 75.4%, P50 MAE 49.4 rating-pts.
- **Step 4c — Part A (DONE)**: per-season trajectory — `export_player_history.py` -> `data/player_history.json` (2502 players / 7023 season rows from the stage-1 storico, 78% of current dataset covered; misses = youth/new signings with no Serie A history); `/api/player_history` endpoint; drawer SVG chart (mv line + pg labels + native tooltips); smoke 87/87. Also fixed 4b leftovers in app.js (spread threshold 135 -> 150 aligned with backend, quantile bar scale 350 -> 250).
- **Step 4c — Part B (DONE)**: Transfermarkt attributes — new `05b_scrape_attributes.py` (search+team-match resolution like stage 5, threaded with retry/UA-rotation, incremental cache, standalone-capable bootstrap); dataset +62 columns (age, height_cm, foot, market_value_eur, contract_until; 530/533 profiles resolved); payload flat keys + drawer section "Profilo & Contratto"; smoke 93/93. Known gap: foot missing for a handful of players (TM page variance).

### EXPAND (the fork's actual goal — more player data)
Candidate new sources/metrics to discuss before implementing:
- FBref (full stats: passing, defending, possession, per-90 splits, percentiles)
- Sofascore/Transfermarkt player attributes (age, height, foot, market value, contract)
- Per-season history in the UI (player trajectory charts), not just 3y aggregates
- More leagues beyond Serie A (requires dropping Serie-A-only team maps)

### Watch out
- ~~`web/app.py` is one giant string template~~ — fixed in Step 3; frontend is now in real files (Jinja template + static css/js)
- `/api/players` was decoupled from auction state in Step 1; pricing uses fixed defaults (budget 1000, slots 3/8/8/6, 10 teams)
- `scripts/generate_value_maps.py` has a hardcoded dev-machine output path
- Upstream merge history: production served the `ui-glowup` branch which is merged into main here (b7221ec)
