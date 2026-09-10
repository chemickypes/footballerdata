# footballerdata — Player Data & Statistics Explorer (Serie A)

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm--Noncommercial--1.0.0-blue.svg)](LICENSE)
[![ML: Quantile Regression](https://img.shields.io/badge/ML-Scikit--Learn%20Quantile%20GBR-yellow.svg)](https://scikit-learn.org/)
[![Local AI: Ollama](https://img.shields.io/badge/AI-Ollama%20gemma4:e4b-8b5cf6.svg)](https://ollama.com/)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-yellow.svg?logo=buy-me-a-coffee)](https://buymeacoffee.com/blueskies360)

A modular pipeline that scrapes, models and serves **player data & statistics for Serie A**: historical ratings and career trajectories, xG/xA shot volumes, injury history, lineups/minutes, per-match logs, touch heatmaps, advanced season statistics, market profile & contract — plus ML quantile projections and VORP-based quality scores — exposed through a fast Flask web explorer with a local-AI chat assistant.

> **Fork notice**: this project is a fork of [**La FantaOfficina**](https://github.com/spectrelabo/fantaofficina) by [SpectreLabo](https://github.com/spectrelabo). The upstream project is a full Fantacalcio auction framework; this fork pivots the same engine into a **player data & statistics explorer**. All league/auction/team management (live draft, rosters, lineups, trades, budgets, admin auth) has been removed. What remains is everything that describes *players*.

📖 **Model Interpretability & Math Guide**: [docs/MODEL_INTERPRETABILITY.md](docs/MODEL_INTERPRETABILITY.md)

---

## What You Get

### Web Explorer (`python3 web/app.py` → http://localhost:5050)

- **Listone** — 533 Serie A players × 62 features: filters by role/team/search, sortable columns, fascia tiers. Player names are real links (ctrl/middle-click opens in a new tab).
- **Player Page** — dedicated full-page deep dive (`/player/<name>`, bento layout, browser back button works):
  - **Traiettoria Carriera**: SVG chart of per-season average rating (MV) across 11 historical seasons (from `data/player_history.json`)
  - **Finestra Medica**: 3-year injury audit (days lost, recurrence) from Transfermarkt
  - **Understat volumes**: xG, xA, npxG, shots (per-90 aggregates)
  - **Profilo & Contratto**: age, height, foot, market value, contract until (Transfermarkt)
  - **Proiezioni**: P10/P50/P90 quantile profile and volatility spread
  - **Titolarità & minutes** from Sofascore early-matchday lineups
  - **Ultime Partite**: per-match log (minutes, rating, goals, assists, xG/xA…) + season summary and rating sparkline (stage 12)
  - **Mappa di Gioco**: season touch heatmap (30×20 grid on an SVG pitch, own goal left) with "fino alla giornata N" period selector (stage 13)
  - **Statistiche Avanzate**: season totals/per-90/percentages with role-relative percentile bars, cards included (stage 14)
  - **Forma Squadra**: last-5 W/D/L chips + season record for the player's team
- **Partite tab** — Serie A results & schedule with matchday navigation; match cards open a dedicated **Match Page** (`/match/<id>`) with lineups, scorers and MOTM (player names link to the player page; a "run stage 11" hint shows when results data is absent).
- **"Analista" AI chat** — grounded Q&A over the dataset (see below).

### Conversational AI Copilot ("Analista")

- Runs **fully local and free** on [Ollama](https://ollama.com/) with **`gemma4:e4b`** as the default model (CPU-friendly).
- RAG-style grounding: the API injects a computed player table (projections, VORP, fair prices, titolarità) into the prompt — the model synthesizes, never invents.
- Ask for player deep-dives, role/team recommendations, **comparisons** (`Thuram vs Retegui`) with numeric verdicts.
- Cascading fallbacks: local Ollama → Groq → Gemini → OpenAI-compatible cloud → built-in **zero-dependency local quantitative reasoner** (works with no LLM at all).

### Quality Scores (VORP & Fair Prices — kept from upstream, reinterpreted)

VORP, `prezzo_fair_*` and `surplus_value_cr` are retained and work as **general player quality scores** (high score = good player, regardless of fantasy play). Read them with two caveats:
- VORP baselines are **role-relative** — cross-role comparison is skewed (keepers are compressed vs forwards).
- Fair prices are budget-dependent rescalings of VORP (calibrated on a reference 1000-cr / 10-team league), **not real market prices**. `surplus_value_cr` (fair − official list price) is a market-undervaluation signal.

---

## Data Pipeline

Ordered stages (`python run_pipeline.py`; CLI order: 1, 3, 4, 5, 6, 8, 9, 10, 7, then 11–14):

| Step | File | Source | Output |
|---|---|---|---|
| 1 | `01_scrape_historical.py` | fantacalcio.it (11 seasons) + football-data.co.uk | per-player career history, 3y weighted ratings, volatility, availability |
| 3 | `03_update_listone.py` | Official quotations Excel (manual download) | active roster, list prices (Qt.A), roles P/D/C/A |
| 4 | `04_scrape_understat.py` | Understat API | xG/xA/npxG/shots per-90 |
| 4b | `04b_scrape_lineups.py` (manual) | Sofascore API | starts/subs/minutes, starter flag |
| 5 | `05_scrape_injuries.py` | Transfermarkt | 3y injury days, severity + `tm_injuries_cache.json` |
| 5b | `05b_scrape_attributes.py` (manual) | Transfermarkt profiles | age, height, foot, market value, contract + `tm_attributes_cache.json` |
| 6 | `06_build_dataset.py` | merges all above (4-tier fuzzy name matching) | **`data/dataset_finale.csv`** (533 × 62) |
| 8 | `08_quantile_points_model.py` | lagged historical seasons | quantile Gradient Boosting → `predicted_contrib_p10/p50/p90`, spread. Target: season rating-volume `pg × mv` (fantasy-neutral) |
| 9 | `09_vorp_auction_pricing.py` | stage-6 dataset + ML P50 | `vorp_points`, fair/target/clearing prices, surplus value |
| 10 | `10_roster_optimizer.py` | legacy upstream (MILP knapsack demo) | prints an optimal squad; kept for reference |
| 7 | `07_generate_excel.py` | legacy upstream | styled multi-tab Excel export |
| 11 | `11_scrape_match_results.py` | Sofascore (default, no key) or api-football (`--source apifootball`, needs key) | `data/match_results.csv` (fixtures, FT/HT scores) + `data/team_form.json` (last-5 form, season record) |
| 12 | `12_harvest_player_match_stats.py` | Sofascore lineups (1 req/match, incremental) | `data/player_match_stats.csv`: per-player-per-match rows (minutes, rating, goals, assists, key passes, shots, xG/xA, duels, saves) |
| 13 | `13_scrape_heatmaps.py` | Sofascore heatmap endpoint (1 req/player-match, incremental, `--limit` for chunks) | `data/player_heatmaps.json`: 30×20 touch grid per player per match + season aggregate (raw y flipped at ingestion: row 0 = top touchline) |
| 14 | `14_scrape_advanced_stats.py` | Sofascore season statistics (1 req/player, incremental, `--refresh` to redo) | `data/player_advanced.json`: curated totals/per-90/percentages + cards + role-relative percentiles |

Out-of-sample validation (2025-26 season): 80% CI coverage 75.4%, P50 MAE 49.4 rating-points.

---

## Quick Start

### 1. Environment Setup
```bash
git clone <this-fork>
cd footballerdata

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Run the Web Explorer
```bash
python3 web/app.py          # → http://localhost:5050
```

### 3. Enable the Local AI (optional, free & offline)
```bash
ollama pull gemma4:e4b
cp .env.example .env        # then set:
#   LLM_BASE_URL=http://localhost:11434   (your Ollama address/port)
#   LLM_MODEL=gemma4:e4b
#   LLM_TIMEOUT=300                       (CPU inference needs generous timeouts)
#   LLM_REASONING_EFFORT=off              (gemma4:e4b thinks by default; off = faster, complete answers)
```
Cloud fallbacks (optional): `GROQ_API_KEY`, `GEMINI_API_KEY` or `LLM_API_KEY` in `.env`.

### 4. Data Pipeline & Utilities
```bash
python run_pipeline.py              # full scrape → dataset → ML → VORP
python run_pipeline.py --step 6     # single stage
python run_pipeline.py --from 8     # ML stages onward

python export_player_history.py     # data/player_history.json (career trajectories)
python export_dataset.py            # dataset_finale_{500,1000}.csv exports
python demo.py                      # zero-config terminal demo (no scraping needed)

python -m pytest tests/ -q          # 130 unit tests
```

---

## Repository Structure

```
footballerdata/
├── core/
│   ├── config.py                  # Central config: paths, seasons, team maps, scoring weights
│   ├── ingestion/static/          # Numbered pipeline stages (see table above)
│   ├── ingestion/dynamic/         # Weekly live matchday feed (api-football + lineups/odds)
│   ├── copilot/                   # LLM providers (Ollama/Groq/Gemini/OpenAI), prompts, Modelfile
│   └── models/                    # Docs only (quantiles, VORP)
├── modules/common/                # Shared data-provider layer for the live feed
├── web/
│   ├── app.py                     # Flask entrypoint (~75 lines)
│   ├── config.py / data.py / pricing.py
│   ├── players_api.py             # /api/players payload builder
│   ├── matches_api.py             # /api/matches, /api/player_matches, /api/player_heatmap,
│   │                              # /api/player_advanced, /api/match_detail
│   ├── ai_api.py                  # /api/ai_{status,test,query}
│   └── templates/ static/         # Jinja template, theme CSS, app.js + tutorial.js
├── data/                          # Generated artifacts (dataset_finale.csv, player_history.json,
│                                  # match_results.csv, player_match_stats.csv, player_heatmaps.json,
│                                  # player_advanced.json, caches, exports)
├── dataset_finale.csv             # Root copy of the master dataset (533 players, 62 cols)
├── run_pipeline.py                # CLI: --step N / --from N over ordered stages
├── export_player_history.py       # Career-trajectory JSON for the drawer chart
├── export_dataset.py / demo.py
├── tests/                         # pytest suites + HTTP smoke script (needs app on :5050)
└── docs/                          # Architecture docs (upstream + fork)
```

Project documentation (Italian/English):
- [core/](core/README.md) — configurazione, ingestion, copilot AI
- [core/ingestion/](core/ingestion/README.md) — pipeline statica e feed dinamico
- [core/copilot/](core/copilot/README.md) — setup Ollama locale e provider AI
- [core/models/](core/models/README.md) — modelli quantili e VORP
- [web/](web/README.md) — app Flask ed API
- [Timeline del progetto](docs/it/TIMELINE_PROGETTO.md) / [Project timeline](docs/en/PROJECT_TIMELINE.md)

---

## Feed Dinamico Infrasettimanale (opzionale)

Per abilitare l'aggiornamento automatico di probabili formazioni, quote e forma
recente durante la stagione:

1. Crea una chiave gratuita/a pagamento su [api-football.com](https://www.api-football.com/).
2. In locale: aggiungi `API_FOOTBALL_KEY=<la-tua-chiave>` al file `.env` (già in `.gitignore`, non verrà mai committato).
3. Su GitHub: vai su Settings → Secrets and variables → Actions e crea il secret `API_FOOTBALL_KEY` con lo stesso valore.
4. Il workflow `.github/workflows/dynamic_feed.yml` genera `data/current_matchday.json` e lo pubblica sulla branch `data-feed` secondo il cron configurato, oppure puoi lanciarlo manualmente da GitHub Actions ("Run workflow").
5. L'app consuma il feed tramite `core/ingestion/dynamic/client.py`, con cache di 15 minuti e fallback automatico su `data/fallback_matchday.json` se il feed remoto non è raggiungibile.

**Non condividere mai la tua chiave API in chat, issue o commit pubblici.**

---

## Credits & Ingestion Sources

This project stands on the shoulders of the open-source football analytics community:

- **[fantabeto](https://github.com/uPeppe/fantabeto)** by [@uPeppe](https://github.com/uPeppe): Groundbreaking work applying Bayesian neural network modeling to fantasy sports performance estimation.
- **[Fantacalcio.it](http://fantacalcio.it/)**: Official ratings, historical match data, player registries, and quotations.
- **[FBref.com](http://fbref.com/)**: Standard-setting repository for European football statistics.
- **[ff_prob](https://github.com/amiles2233/ff_prob)**: Foundational inspiration for applying TensorFlow Probability to fantasy sports projections.
- **[Scrape-FBref-data](https://github.com/parth1902/Scrape-FBref-data)**: Utility for structured data extraction.
- **[Understat.com](https://understat.com/)**: Shot-level analytics, Expected Goals ($xG$), and Expected Assists ($xA$).
- **[Transfermarkt.com](https://www.transfermarkt.com/)**: Comprehensive injury logs, missed match records, medical histories, and player profiles.
- **[Sofascore.com](https://www.sofascore.com/)**: lineups, starts and minutes, match results, per-match player statistics, touch heatmaps and advanced season statistics.
- **[Ollama](https://ollama.com/)** + Google **Gemma**: free local LLM inference powering the "Analista" copilot.

---

## Support the Project

If `La FantaOfficina` prevented an emotional 2:00 AM panic buy, saved your budget, or gave you an algorithmic edge in your fantasy auction, consider buying a coffee to support ongoing open-source maintenance:

[![Buy Me A Coffee](https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png)](https://buymeacoffee.com/blueskies360)

---

## Contributing & License

Contributions, feature proposals, and model extensions are welcome via Pull Requests and Issues.
Distributed under the **PolyForm Noncommercial License 1.0.0**. Noncommercial use, research, and personal projects are freely permitted; commercial use requires a separate license from the copyright holder. See [LICENSE](LICENSE) for full legal text.

**Upstream project**: [La FantaOfficina](https://github.com/spectrelabo/fantaofficina) — designed, built and maintained by [SpectreLabo](https://github.com/spectrelabo). This fork repurposes that work as a player data & statistics explorer; all credit for the original pipeline, models and architecture belongs to the upstream author.
