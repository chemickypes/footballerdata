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
  static/css/main.css       # Theme stylesheet (~1000 lines, purged of dead selectors)
  static/css/tutorial.css   # Guided-tour styles
  static/js/espn.js         # ESPNX — ESPN client-side live feed (browser-only: ESPN 403s datacenter IPs)
  static/js/app.js          # Frontend logic (~1550 lines): listone render, player page, AI chat, Partite views
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
| 11 | `11_scrape_match_results.py` | **Sofascore** (default, no key, 1 request/round via shared `sofascore_api.py`) or api-football (`--source apifootball`, needs `API_FOOTBALL_KEY`, whole season in 1 request) | `data/match_results.csv` (round/date/teams/FT+HT scores/status) + `data/team_form.json` (per-team last-5 W/D/L, season points/GF/GA). Team names → codes via `TEAM_APIFB_MAP`/`TEAM_SOFASCORE_MAP` + fuzzy fallback |
| 12 | `12_harvest_player_match_stats.py` | Sofascore `/event/{id}/lineups` (1 request per finished match, incremental — harvested events derived from the CSV itself) | `data/player_match_stats.csv`: per-player-per-match rows (minutes, rating, goals, assists, key passes, shots, xG/xA, passes, duels, saves; sofascore_player_id kept for Phase 3). Names → dataset via `PlayerMatcher` + `SOFASCORE_PLAYER_ALIASES`. **No card data** (endpoint doesn't expose it) |
| 13 | `13_scrape_heatmaps.py` | Sofascore `/event/{id}/player/{pid}/heatmap` (1 request per player per finished match, incremental — (event, player) pairs derived from the per-player `by_event` map in the output JSON; `--limit N` for chunked runs; chunked saves every 50; fail-fast after 10 consecutive network failures) | `data/player_heatmaps.json` schema v2: per-player `by_event` = {event_id: {round, minutes, grid 30×20}} + season aggregate (grid/matches/minutes/points, derived from by_event). Coordinates are team-normalized (verified empirically: x=0 own goal, x=100 opponent goal for both teams; **raw y is bottom-origin** — y=0 lower touchline in the attack-rightward frame, flipped at ingestion so row 0 = top touchline). Needs stage 12 first. v1→v2 migration = one full refetch |
| 14 | `14_scrape_advanced_stats.py` | Sofascore `/player/{id}/unique-tournament/23/season/{sid}/statistics/overall` (1 request per player, incremental per season — `team_code` + `checked_ids` + `duplicate_ids` mark resolved entries; chunked saves every 50; fail-fast after 10 consecutive network failures; `--refresh` to redo) | `data/player_advanced.json`: per-player curated totals/per90/pcts + cards (yellow/red — fills the stage-12 gap) + role-relative percentiles vs peers (same dataset role, ≥60 min). Namesakes (8 names with 2 Sofascore ids from stage-12 matching) resolved by dataset-team match, then max minutes; discarded ids kept in `duplicate_ids`. Needs stage 12 first |

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
- `web/matches_api.py` (~150 lines) — Blueprint `/api/matches`: Serie A results/schedule + team form from stage-11 artifacts (mtime-cached CSV loader). Also `/api/player_matches?player=`: per-player match log + summary from stage-12 artifact
- `web/ai_api.py` (~295 lines) — Blueprint `/api/ai_{status,test,query}`: LLM copilot integration + local rule-based reasoner
- `web/__init__.py` — puts repo root on `sys.path` so `web.*` and `core.*` imports work in script/package/Vercel modes
- `web/templates/index.html` (~450 lines) — Jinja template; vars: `bot_name`, `bot_subtitle`, `bot_avatar_text`, `bot_avatar_image`, `bot_badge`, `bot_greeting`, `is_personal`
- `web/static/css/main.css` (~862 lines) — "dark professional" theme (Linear/Vercel-style: neutral near-black surfaces, single #5e8bff accent, flat borders; replaced the old pink/brass theme in the UI restyle)
- `web/static/js/app.js` (~870 lines) — listone render + filters/sort, Player Detail Drawer, AI chat, minimal boot splash (mascot removed in the UI restyle)
- `web/static/js/tutorial.js` — 3-step guided tour

2 tabs: `listone` (player list — the stats core, default active), `partite` (Serie A results/schedule with matchday nav; shows a "run stage 11" hint when data is absent) and `ai` (copilot chat "Analista", sober branding). Players open in a **dedicated full-page view** (`#playerPage`, `.pv-grid` bento layout — replaced the old right-side drawer): route `/player/<name>` serves it with `initial_player` pre-opened, listone names are real links (ctrl/middle-click opens in a new tab), and History API pushState/popstate keeps the browser back button working. Matches likewise open a **dedicated match page** (`#matchPage`, route `/match/<id>`, `initial_match`) with lineups/scorers/MOTM and player links.

### Route map (after Step 1 backend strip)

- **Trajectory (KEPT, Step 4c)**: `/api/player_history?player=<name>` — per-season career rows (season/team/pg/mv/gol/assist/mfv) from `data/player_history.json`, normalized-name keyed; 404 = no Serie A history. Drawer section "Traiettoria Carriera" renders an SVG mv-per-season chart.
- **Player stats (KEPT)**: `/api/players` — loads `dataset_finale.csv`, richest payload: prices, score, P10/P50/P90, spread, VORP, bonus range, injury audit, Understat metrics, quantile profile, starter status. Decoupled from auction state; pricing computed with fixed defaults (budget 1000, slots 3/8/8/6, 10 teams) via `get_dynamic_fair_prices()`.
- **Copilot (KEPT)**: `/api/ai_status`, `/api/ai_test`, `/api/ai_query` — player deep-dive/comparison/recommendations only (squad_diagnostic branch removed). Local rule-based fallback reasoner needs no LLM key.
- **Matches (NEW, Phase 1)**: `/api/matches` — Serie A results/schedule + `team_form` from stage-11 artifacts; `available:false` (still 200) when `data/match_results.csv` is absent, so the Partite tab can show a "run stage 11" hint.
- **Player match log (NEW, Phase 2)**: `/api/player_matches?player=<name>` — per-player match rows (last 10, desc) + season summary (played/starts/avg rating/G/A/xG/xA) from `data/player_match_stats.csv` (stage 12); 404 = no rows or stage not run. Drawer section "Ultime Partite" renders a rating sparkline + match rows.
- **Player heatmap (NEW, Phase 3)**: `/api/player_heatmap?player=<name>` — 30×20 density grid + meta (matches/minutes/touches/available_rounds) from `data/player_heatmaps.json` (stage 13); season aggregate by default, `?until_round=N` for the cumulative rounds 1..N, `?round=N` for a single matchday; 404 = no data for the selection. Drawer section "Mappa di Gioco" renders an SVG pitch (blurred cell rects, blue→red scale, own goal left / opponent goal right) + a "Periodo" select (Stagione completa / Fino alla G-N) when the player has ≥2 matchdays.
- **Advanced season stats (NEW, Phase 4)**: `/api/player_advanced?player=<name>` — season totals/per-90/percentages + role-relative percentiles + cards from `data/player_advanced.json` (stage 14); 404 = no data. Drawer section "Statistiche Avanzate" renders grouped rows (Attacco/Passaggi/Possesso/Difesa/Portiere) with percentile bars.
- **Match detail (NEW, Phase 5)**: `/api/match_detail?event=<fixture_id>` — match meta (score/HT/status) + per-side lineups (starters by shirt number, subs by minutes) + scorers + MOTM (max rating), joining stage-11 fixtures with stage-12 per-player rows; `lineups_available:false` for not-yet-played matches; 404 = unknown event. Match page `#matchPage` (route `/match/<id>`, same pushState/popstate pattern as the player page) — clickable match cards in the Partite tab; player names in lineups link to the player page.
- **REMOVED (404)**: `/api/settings`, `/api/state`, `/api/sync_state`, `/api/assign`, `/api/undo`, `/api/favorite`, `/api/reset`, `/api/live/snapshot`, `/api/auth_admin`, `/api/auth/login`, `/api/session/reset`, `/api/lineup/solve`, `/api/audit/rankings`, `/api/trades/*`

Frontend keepers: `tab-listone` + `renderListone()` + filters/sorts; `tab-partite` + `renderMatches()` (matchday nav, match cards); **Player page** `openPlayerDetailDrawer()` (fills `#playerPage`; closes via History back) — price/value, Finestra Medica (injury history), Understat volumes, Traiettoria Carriera (SVG per-season mv chart), Forma Squadra (last-5 W/D/L chips), quantile profile, starter/minutes. No polling, no gates, no `auctionState`.

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

# Tests (122 unit tests pass; test_dual_track_and_features.py is an HTTP smoke script
# needing the web app on :5050, or SMOKE_BASE_URL to point elsewhere)
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
- **Phase 1 — Match results (DONE)**: new stage `11_scrape_match_results.py` — **Sofascore primary** (no key; new shared client `core/ingestion/static/sofascore_api.py` with `parse_event()` normalized to the api-football fixture format; `TEAM_SOFASCORE_MAP` consolidated in config, 04b now references it) with `--source apifootball` fallback (`get_season_fixtures()` + score fields added to `api_football_client._parse_fixture`) → `data/match_results.csv` + `data/team_form.json`; unified team resolver (both maps + fuzzy); `core/config.py` now loads `.env` (setdefault) so CLI stages see `API_FOOTBALL_KEY`; new `web/matches_api.py` blueprint `/api/matches` (mtime-cached, `available:false` 200 when CSV absent) + Partite tab (matchday nav, match cards w/ FT+HT+winner highlight) + drawer "Forma Squadra" (last-5 W/D/L chips + season record). Unit tests 85/85 (new `tests/test_match_results.py`); smoke section 14 added. **Ran live via Sofascore: 380 fixtures, 30 played (rounds 1-3), all 20 teams mapped.** The local API_FOOTBALL_KEY is rejected ("Error/Missing application key" — no active subscription bound to it); the apifootball path activates if the key ever gets fixed. Note: smoke section 9 (AI copilot) times out on slow local Ollama — pre-existing, unrelated.
- **Phase 2 (DONE)**: per-match player stats — new stage `12_harvest_player_match_stats.py` (Sofascore `/event/{id}/lineups`, 1 req/match, incremental via event ids derived from the CSV) → `data/player_match_stats.csv` (957 rows / 30 matches / 388 players after rounds 1-3; minutes, rating, goals, `goalAssist`→assists, key passes, shots, xG/xA, duels, saves — **no cards**, endpoint doesn't expose them; `sofascore_player_id` stored for Phase 3); names → dataset via `PlayerMatcher` + `SOFASCORE_PLAYER_ALIASES` (moved to config, 04b references it); `/api/player_matches` + drawer "Ultime Partite" (rating sparkline SVG + last-8 match rows + summary). Unit tests 96/96. Live-verified: Lautaro 8.8 rating vs Napoli etc. Note: smoke section 9 (AI copilot) still blocked by slow local Ollama (gemma4:e4b ~90s for 5 tokens on CPU — user may want a smaller model or Groq free tier).
- **Phase 3 (DONE)**: season heatmaps — new stage `13_scrape_heatmaps.py` (Sofascore `/event/{id}/player/{pid}/heatmap`, 1 req/player-match, incremental via per-player `events` list in the output JSON, `--limit` for chunked runs) → `data/player_heatmaps.json` (30×20 density grid per player; 939 heatmaps / 388 players after rounds 1-3, 490 KB). **Axis orientation verified empirically**: coords are team-normalized (both keepers of the same match cluster at x≈10) → x=0 own goal, x=100 opponent goal, no mirroring; **raw y is bottom-origin in the attack-rightward frame (verified vs Sofascore's own rendered heatmaps: RWs sit at raw y≈0-3, LBs at raw y≈16-19, home and away alike) and is flipped at ingestion** (`cy = rows-1 - y_raw`, grid mapping `cx = x/100*30`); existing v1 grids migrated in place. `/api/player_heatmap` + drawer "Mappa di Gioco" (SVG pitch, blurred cell rects, blue→red scale, own goal left). Unit tests 130/130.
- **Phase 4 (DONE)**: advanced season stats — FBref was the original target but is behind an unbeatable Cloudflare managed challenge (403 `cf-mitigated: challenge` for requests/curl_cffi/cloudscraper/playwright headless+headful); pivoted to **Sofascore** `statistics/overall` (~115 season metrics/player, reuses the stage-12 `sofascore_player_id`s). New stage `14_scrape_advanced_stats.py` → `data/player_advanced.json` (curated totals/per-90/pcts + **cards** — fills the stage-12 gap — + role-relative percentiles vs peers ≥60 min; keepers get a dedicated metric/percentile set). Incremental per season via `team_code`+`checked_ids`+`duplicate_ids` markers, chunked saves every 50 pairs, fail-fast after 10 consecutive failures. Namesake handling: 8 dataset names carry 2 Sofascore ids (stage-12 matcher over-merges, e.g. Lazzari LAZ/MON) — resolved by dataset-team match, then max minutes; discarded ids in `duplicate_ids`. Sofascore soft-flags the IP after high daily volume (403 "challenge", lifts after ~10-20 min quiet) — retries are resumable. `/api/player_advanced` + drawer "Statistiche Avanzate" (grouped Attacco/Passaggi/Possesso/Difesa/Portiere rows with percentile bars). Unit tests 122/122.
- **Phase 6 (DONE)**: ESPN live enrichment of the Partite tab — **client-side only** (`web/static/js/espn.js`, no new Flask routes, no pipeline stage): ESPN's public `site.api.espn.com` API serves browsers with CORS but **403s datacenter/server-side requests** (verified: first curl ok, then blocked), so all fetching happens in the visitor's browser. `ESPNX` client: season scoreboard (14-day `?dates=` ranges, deduped, memoized per session), lookup by `utc-day|team-codes` (±1 day for postponements; ESPN abbreviations map to `TEAM_ABBR_MAP` codes — only `ROMA→ROM`, `COMO→COM` need remapping), `summary?event=` parsing (goals + assist from "Assisted by" text/fallback second athlete, yellow/red cards from keyEvents, substitutions, formations from rosters), `standings` (v2 endpoint, memo 10 min), scorers (scoreboard-details counting with ≥80% coverage check, fallback = per-finished-match summaries, 5 concurrent; empty result = retryable; scorer names resolve to dataset players via `_resolveDatasetPlayer` — full-name match, then surname (last ESPN token vs first dataset token, handles "Kamara H." forms, accent-insensitive), team-code disambiguation via `ESPNX.codeFromLabel` when a surname maps to multiple players, e.g. "Marcus Thuram"→INT vs "Khéphren Thuram"→JUV — unresolvable names stay plain text). **Fetches are lazy — nothing at page boot**: the season scoreboard loads on first Partite-tab render or match-page open (user request: no auto-refresh polling, no prefetch). UI: Partite tab gets **Partite / Classifica / Marcatori** view pills; match cards get team logos + live badge (blinking dot, clock, live score — also fills FT scores before stage-11 re-scrape); match page gets "Gol, cartellini & cambi" timeline (2-col home/away grid) + formation badges + ESPN link; match-detail 404 falls back to matchesData+ESPN-only rendering (works for live/upcoming matches without stage-12 data). All ESPN paths degrade gracefully (no data → current UI unchanged). Smoke 209/209; join logic functionally verified in node with mocked fetch; full click-flow verified with Playwright/headless chromium. **Bugfix in the same pass**: `_currentDetailPlayer` was an undeclared global referenced by `openMatchPage` — clicking a match card before ever opening a player page threw `ReferenceError` and silently aborted navigation (latent since the Phase-5 match page); now properly declared. **ESPN match-events store (crowdsourced cache)**: when a match page fetches the ESPN summary, the client POSTs the parsed events to `POST /api/espn_events` → sanitized (kinds/sides whitelists, string caps, minutes 0-130, ≤200 events) and merged **without downgrade** into `data/espn_match_events.json` (keyed by fixture_id; `GET /api/match_events?event=`, `DELETE /api/espn_events?event=` for corrections). `enrichMatchDetailEspn` is cache-first: cached events render instantly; if `match_state === 'post'` ESPN is not contacted at all; partial (live) caches trigger a refetch that re-POSTs when richer. Path overridable via `ESPN_EVENTS_JSON` env (unit tests use tmp_path). Caveat: on Vercel the filesystem is ephemeral, so the cache only persists on local/self-hosted runs — there it degrades to the live-fetch-only behavior. **Refresh + canonical links + cards export (same phase, user feedback)**: match page gets an "ESPN" refresh button (`refreshMatchEspn` → `ESPNX.refreshEvent` re-fetches the day scoreboard + forced summary, bypassing the session memo, then re-POSTs); `espnLink` now uses the **canonical `ev.links` URL** (`.../gameId/<id>/<slug>` — the bare `/gameId/<id>` no longer resolves on espn.com) persisted as `espn_link` in the store (merge rule: a link upgrade is allowed at equal event count without dropping richer events); new `export_player_cards.py` aggregates the cached card events into per-player `yellow_cards_espn` / `red_cards_espn` columns in `data/dataset_finale.csv` (+ `data/espn_player_cards.json` detail; ESPN full names → dataset names via accent-insensitive surname matching, omonims disambiguated by event side → fixture team; CSV rewrite preserves BOM/LF byte-for-byte — the dataset has a UTF-8 BOM, read with `utf-8-sig`), payload exposes both fields and the player page shows a 🟨/🟥 badge when nonzero; coverage is crowdsourced (0 = "no data collected", not "no cards").
- **Phase 7 (DONE) — Copilot structured RAG**: new `web/retrieval.py` — entity-keyed retrieval (NO embeddings: closed domain of 533 players/380 fixtures → deterministic resolution beats semantic search). `resolve_players()`: alias expansion (`PLAYER_NAME_ALIASES` in core/config.py) + full-name containment + accent-insensitive token matching (≥3 chars, word-boundary) — **alias targets only feed containment; token matching runs on the ORIGINAL prompt** so "lautaro"→"Martinez L." doesn't drag "Martinez Jo." into a false 2-player comparison; containment scores 100+len(norm) so "Thuram K." beats "Thuram" when fully typed. `resolve_matches()`: `TEAM_KEYWORD_MAP` (also core/config.py, dedupes the 2 inline ai_api team maps) → codes in order of appearance; h2h ≥2 codes (prefers finished over upcoming), 1 code = latest finished (or `giornata N` / `prossima`), round-only = full matchday. Context blocks: **player** (dataset row incl. xG/90·xA/90·injuries·ESPN cards·TM value + stage-12 last-5 gare table + season totals "xG totale" labels + stage-14 advanced one-liner; header carries **known names** — Sofascore full name + reverse aliases, e.g. "Martinez L. — Lautaro Martínez" — without which the LLM's rule 5 grounding makes it refuse "lautaro" questions); **match** (stage-11 meta + ESPN events from `espn_match_events.json` rendered as Gol/Ammoniti/Espulsi with team codes + stage-12 scorer fallback + MOTM + last-5 forma V/N/S); **aggregates** (marcatori index from stage-12 CSV, mtime-cached; espulsi/ammoniti from dataset ESPN card columns). `build_llm_context()` order: players → matches → aggregate fallback. `core/copilot/prompts.py`: `build_user_prompt(prompt, top_players, context_blocks)` renders blocks ahead of the VORP table; system rule 6 = short numeric answers for factual queries. `web/ai_api.py` rewired on retrieval; local reasoner gains `match_summary`/`aggregate_answer` response types (plain `text`, rendered by the frontend's generic fallback — no JS changes) and the deepdive verdict now cites xG/90, xA/90, ESPN cards. Unit tests 173/173 (new hermetic `tests/test_retrieval.py`, 31 tests with injected data); smoke 215/215. Live-verified on Ollama: "cartellini rossi inter napoli" → correct "0 rossi" + exact yellows; "quanti xG ha lautaro?" → grounded answer (~26-51s CPU).

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
