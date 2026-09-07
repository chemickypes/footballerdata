# Repo Restructure & Documentation (Pilastro 7) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `fanta-lab` from a flat root layout into the `core/`/`modules/`/`web/` modular tree defined in the approved design spec, add per-module documentation (divulgative + technical) and a bilingual project timeline, and switch the license from MIT to PolyForm Noncommercial 1.0.0 — with zero regressions in the existing pytest suite.

**Architecture:** Pure file moves + import-path rewrites (no behavior changes). Files move in dependency order (config → static pipeline → dynamic pipeline → copilot → app/web) so that each task's test run only needs already-moved dependencies. Documentation tasks (README files, timeline, license) come after all code moves are verified green.

**Tech Stack:** Python 3.11, Flask, pytest, `git mv` for history-preserving moves.

## Global Constraints

- Baseline to preserve: `pytest` must report **89 passed, 1 error** (pre-existing unrelated collection error in `tests/test_dual_track_and_features.py::test`, fixture `'name'` not found) after every task — never fewer passes, never new errors.
- No behavior changes: only paths/imports/docs change. Do not touch business logic in any moved file.
- All moves use `git mv` (not delete+create) to preserve file history.
- Governing spec: `docs/superpowers/specs/2026-09-07-repo-restructure-design.md` — every task must trace back to a section of this spec.
- License: PolyForm Noncommercial 1.0.0 (full text fetched from https://polyformproject.org/licenses/noncommercial/1.0.0/), copyright holder unchanged from current `LICENSE` file.
- Run `pytest -q` after every task; paste failing output into the task if it fails, fix before moving on.

---

### Task 1: Move config layer into `core/`

**Files:**
- Create (via `git mv`): `core/config.py`, `core/config_defaults.py`, `core/config.personal.example.py` (from root `config.py`, `config_defaults.py`, `config.personal.example.py`)
- Note: `config.personal.py` is gitignored and may not exist in the working tree; if present, `git mv` it too, else skip.
- Modify: `core/config.py` (fix `PROJECT_DIR`)
- Modify (import site): `pipeline/01_scrape_historical.py:24`, `pipeline/03_update_listone.py:21`, `pipeline/04_scrape_understat.py:19`, `pipeline/04b_scrape_lineups.py:24`, `pipeline/05_scrape_injuries.py:22`, `pipeline/06_build_dataset.py:23`, `pipeline/07_generate_excel.py:22`, `pipeline/08_quantile_points_model.py:16`, `pipeline/09_vorp_auction_pricing.py:23`, `pipeline/10_roster_optimizer.py:25`, `pipeline/target_pricing.py:35`, `pipeline/generate_excel_italiano.py:25`, `pipeline/dynamic/api_football_client.py:12`, `pipeline/dynamic/build_feed.py:18`, `pipeline/dynamic/client.py:16`, `pipeline/dynamic/scrape_lineups.py:18`, `pipeline/dynamic/scrape_results.py:14`, `pipeline/dynamic/scrape_status.py:15`, `app.py:15`
- Create: `core/__init__.py` (empty)
- Test: existing `tests/` suite (no new test file needed; this is a mechanical rename verified by the full suite)

**Interfaces:**
- Produces: `core.config` module importable exactly as `config` was before (same public names: `DATA_DIR`, `EXAMPLES_DIR`, `PROJECT_DIR`, etc.)

- [ ] **Step 1: Create `core/` package and move config files**

```bash
mkdir -p core
touch core/__init__.py
git mv config.py core/config.py
git mv config_defaults.py core/config_defaults.py
git mv config.personal.example.py core/config.personal.example.py
if [ -f config.personal.py ]; then git mv config.personal.py core/config.personal.py; fi
```

- [ ] **Step 2: Fix `PROJECT_DIR` in `core/config.py`**

Open `core/config.py` line 12. It currently reads:

```python
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
```

Change to point one directory up (repo root), since the file is now nested inside `core/`:

```python
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

- [ ] **Step 3: Update every `import config` call site to `from core import config`**

For each of these files, change the line `import config` to `from core import config` (keep all other usages of `config.X` unchanged since the module is still referenced as `config`):

`pipeline/01_scrape_historical.py:24`, `pipeline/03_update_listone.py:21`, `pipeline/04_scrape_understat.py:19`, `pipeline/04b_scrape_lineups.py:24`, `pipeline/05_scrape_injuries.py:22`, `pipeline/06_build_dataset.py:23`, `pipeline/07_generate_excel.py:22`, `pipeline/08_quantile_points_model.py:16`, `pipeline/09_vorp_auction_pricing.py:23`, `pipeline/10_roster_optimizer.py:25`, `pipeline/target_pricing.py:35`, `pipeline/generate_excel_italiano.py:25`, `pipeline/dynamic/api_football_client.py:12`, `pipeline/dynamic/build_feed.py:18`, `pipeline/dynamic/client.py:16`, `pipeline/dynamic/scrape_lineups.py:18`, `pipeline/dynamic/scrape_results.py:14`, `pipeline/dynamic/scrape_status.py:15`, `app.py:15`

Verify no stragglers remain:

```bash
grep -rn "^import config$" --include="*.py" .
```

Expected: no output.

- [ ] **Step 4: Run full test suite**

Run: `pytest -q`
Expected: `89 passed, 1 error` (same baseline as before this task; the 1 error is the pre-existing unrelated `test_dual_track_and_features.py::test` fixture issue).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(core): move config module into core/ package"
```

---

### Task 2: Move static pipeline scripts into `core/ingestion/static/`

**Files:**
- Create (via `git mv`): `core/ingestion/static/01_scrape_historical.py`, `.../03_update_listone.py`, `.../04_scrape_understat.py`, `.../04b_scrape_lineups.py`, `.../05_scrape_injuries.py`, `.../06_build_dataset.py`, `.../07_generate_excel.py`, `.../08_quantile_points_model.py`, `.../09_vorp_auction_pricing.py`, `.../10_roster_optimizer.py`, `.../target_pricing.py`, `.../generate_excel_italiano.py` (all from `pipeline/*.py`, excluding `pipeline/dynamic/` and `pipeline/__init__.py` which move in Task 3)
- Create: `core/ingestion/__init__.py`, `core/ingestion/static/__init__.py` (empty)
- Modify: `run_pipeline.py` (STEPS dict prefix, `run_step()` import prefix)
- Modify: `demo.py:92,95`
- Modify (internal cross-imports): `core/ingestion/static/09_vorp_auction_pricing.py:123,150`, `core/ingestion/static/06_build_dataset.py:25`, `core/ingestion/static/10_roster_optimizer.py:135-136`

**Interfaces:**
- Consumes: `core.config` from Task 1.
- Produces: modules importable as `core.ingestion.static.<module_name>` (e.g. `core.ingestion.static.target_pricing`, `core.ingestion.static.generate_excel_italiano`). Numbered modules (`01_scrape_historical` etc.) remain importable only via `importlib.import_module("core.ingestion.static.01_scrape_historical")` since they start with digits (same constraint as before the move, just with new prefix).

- [ ] **Step 1: Move the static pipeline files**

```bash
mkdir -p core/ingestion/static
touch core/ingestion/__init__.py core/ingestion/static/__init__.py
for f in 01_scrape_historical.py 03_update_listone.py 04_scrape_understat.py \
         04b_scrape_lineups.py 05_scrape_injuries.py 06_build_dataset.py \
         07_generate_excel.py 08_quantile_points_model.py 09_vorp_auction_pricing.py \
         10_roster_optimizer.py target_pricing.py generate_excel_italiano.py; do
  git mv "pipeline/$f" "core/ingestion/static/$f"
done
```

- [ ] **Step 2: Update `run_pipeline.py`'s import prefix**

In `run_pipeline.py`, the `STEPS` dict (lines 25-35) maps step numbers to bare module name strings (e.g. `"01_scrape_historical"`). Find `run_step()` (around line 49):

```python
module = importlib.import_module(f"pipeline.{module_name}")
```

Change to:

```python
module = importlib.import_module(f"core.ingestion.static.{module_name}")
```

Leave the `STEPS` dict values unchanged (they're bare names, not full paths).

- [ ] **Step 3: Update `demo.py`**

At `demo.py:92` and `:95`, replace references to `pipeline.p10_roster_optimizer` / `pipeline.10_roster_optimizer` with `core.ingestion.static.10_roster_optimizer` (using `importlib.import_module` since the name starts with a digit, matching whatever pattern is already used at that call site — inspect the existing line to preserve the exact `importlib.import_module(...)` vs. attribute-access style already in place before editing).

- [ ] **Step 4: Fix internal cross-imports inside moved files**

In `core/ingestion/static/09_vorp_auction_pricing.py`:
- Line 123: `from pipeline.target_pricing import compute_target_prices` → `from core.ingestion.static.target_pricing import compute_target_prices`
- Line 150: `importlib.import_module("pipeline.08_quantile_points_model")` → `importlib.import_module("core.ingestion.static.08_quantile_points_model")`

In `core/ingestion/static/06_build_dataset.py:25`:
- `importlib.import_module("pipeline.03_update_listone")` → `importlib.import_module("core.ingestion.static.03_update_listone")`

In `core/ingestion/static/10_roster_optimizer.py:135-136`:
- Update the two `importlib.import_module(...)` calls referencing `pipeline.08_quantile_points_model` and `pipeline.09_vorp_auction_pricing` to use the `core.ingestion.static.` prefix instead of `pipeline.`.

- [ ] **Step 5: Run full test suite**

Run: `pytest -q`
Expected: `89 passed, 1 error` (unchanged baseline).

- [ ] **Step 6: Smoke-test the CLI orchestrator**

Run: `python run_pipeline.py --help`
Expected: help text prints without `ModuleNotFoundError`.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(core): move static pipeline scripts into core/ingestion/static/"
```

---

### Task 3: Move dynamic pipeline scripts into `core/ingestion/dynamic/`

**Files:**
- Create (via `git mv`): everything under `pipeline/dynamic/*` → `core/ingestion/dynamic/*` (including `__init__.py`, `api_football_client.py`, `build_feed.py`, `client.py`, `scrape_lineups.py`, `scrape_odds.py`, `scrape_results.py`, `scrape_status.py`, `utils.py`, and any other files present in that directory)
- Remove: `pipeline/__init__.py` (delete the now-empty `pipeline/` package marker once both Task 2 and this task have emptied the directory; verify with `ls pipeline/` first)
- Modify: `modules/common/data_provider.py:12-13`
- Modify: `tests/test_dynamic_feed.py` (all `pipeline.dynamic.*` imports, including the inline `import pipeline.dynamic.client as client_module`)
- Modify: `tests/test_lineup_solver.py:6`, `tests/test_trade_analyzer.py:6`
- Modify: `.github/workflows/dynamic_feed.yml` (the `python -m pipeline.dynamic.build_feed` line)

**Interfaces:**
- Consumes: `core.config` from Task 1.
- Produces: `core.ingestion.dynamic.client.get_default_client`, `core.ingestion.dynamic.utils.normalize_name` — same names, new import path `core.ingestion.dynamic.*`.

- [ ] **Step 1: Move the dynamic pipeline directory**

```bash
mkdir -p core/ingestion/dynamic
git mv pipeline/dynamic/* core/ingestion/dynamic/
ls pipeline/  # confirm only __init__.py (or nothing) remains
git rm pipeline/__init__.py
rmdir pipeline 2>/dev/null || true
```

- [ ] **Step 2: Update `modules/common/data_provider.py`**

Lines 12-13, change:

```python
from pipeline.dynamic.client import get_default_client
from pipeline.dynamic.utils import normalize_name
```

to:

```python
from core.ingestion.dynamic.client import get_default_client
from core.ingestion.dynamic.utils import normalize_name
```

- [ ] **Step 3: Update `tests/test_dynamic_feed.py`**

Replace every `from pipeline.dynamic.<x> import ...` with `from core.ingestion.dynamic.<x> import ...` for: `utils`, `api_football_client`, `scrape_odds`, `scrape_lineups`, `scrape_status`, `scrape_results`, `build_feed`, `client`. Also replace the inline `import pipeline.dynamic.client as client_module` with `import core.ingestion.dynamic.client as client_module` (search the whole file for any remaining `pipeline.dynamic` string and replace all occurrences, including inside `mock.patch(...)` target strings if any exist — these use dotted-path strings that must also be updated, e.g. `"pipeline.dynamic.client.requests.get"` → `"core.ingestion.dynamic.client.requests.get"`).

- [ ] **Step 4: Update `tests/test_lineup_solver.py` and `tests/test_trade_analyzer.py`**

In both files at line 6: `from pipeline.dynamic.utils import normalize_name` → `from core.ingestion.dynamic.utils import normalize_name`.

- [ ] **Step 5: Update the GitHub Actions workflow**

In `.github/workflows/dynamic_feed.yml`, find the line:

```yaml
        run: python -m pipeline.dynamic.build_feed
```

Change to:

```yaml
        run: python -m core.ingestion.dynamic.build_feed
```

Leave the rest of the workflow (checkout, dependency install, orphan `data-feed` branch commit/push steps) untouched.

- [ ] **Step 6: Run full test suite**

Run: `pytest -q`
Expected: `89 passed, 1 error` (unchanged baseline).

- [ ] **Step 7: Grep-verify no stragglers**

```bash
grep -rn "pipeline\.dynamic\|pipeline\." --include="*.py" --include="*.yml" . | grep -v "docs/superpowers"
```

Expected: no output (all references updated).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(core): move dynamic pipeline scripts into core/ingestion/dynamic/"
```

---

### Task 4: Move copilot providers into `core/copilot/`

**Files:**
- Create (via `git mv`): `core/copilot/__init__.py`, `core/copilot/providers.py`, `core/copilot/Modelfile` (from `copilot/__init__.py`, `copilot/providers.py`, `copilot/Modelfile` — move every file present in the current `copilot/` directory)
- Modify: `app.py:1332,1343,1412` (the 3 `from copilot import ...` call sites)

**Interfaces:**
- Consumes: nothing from earlier tasks (copilot module is self-contained).
- Produces: `core.copilot.get_copilot_diagnostics`, `core.copilot.test_all_providers`, `core.copilot.get_copilot_response` — same public names re-exported from `core/copilot/__init__.py` exactly as they were from `copilot/__init__.py`.

- [ ] **Step 1: Move the copilot directory**

```bash
mkdir -p core/copilot
git mv copilot/__init__.py core/copilot/__init__.py
git mv copilot/providers.py core/copilot/providers.py
git mv copilot/Modelfile core/copilot/Modelfile
rmdir copilot 2>/dev/null || true
```

(If `ls copilot/` before this step shows additional files beyond `__init__.py`, `providers.py`, `Modelfile`, `git mv` those too into `core/copilot/` with the same relative filename.)

- [ ] **Step 2: Update `app.py`'s three copilot import sites**

- Line 1332: `from copilot import get_copilot_diagnostics` → `from core.copilot import get_copilot_diagnostics`
- Line 1343: `from copilot import test_all_providers` → `from core.copilot import test_all_providers`
- Line 1412: `from copilot import get_copilot_response` → `from core.copilot import get_copilot_response`

- [ ] **Step 3: Run full test suite**

Run: `pytest -q`
Expected: `89 passed, 1 error` (unchanged baseline).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(core): move copilot providers into core/copilot/"
```

---

### Task 5: Move `app.py` and `static/` into `web/`, split `BASE_DIR`

**Files:**
- Create (via `git mv`): `web/app.py` (from root `app.py`), `web/static/` (from root `static/`)
- Modify: `web/app.py` (BASE_DIR split — see Step 2)
- Modify: `vercel.json` (`builds[0].src` and route `dest`)
- Create: `web/__init__.py` (empty, so `web` is importable if any test needs `from web import app` in the future — check existing tests first per Step 4)

**Interfaces:**
- Produces: `PROJECT_ROOT` (repo root, parent of `web/`) used for all data/config/env paths; `BASE_DIR` (directory containing `web/app.py`, i.e. `web/`) used only for static-serving paths. Both are plain `str` absolute paths.

- [ ] **Step 1: Move `app.py` and `static/`**

```bash
mkdir -p web
git mv app.py web/app.py
git mv static web/static
```

- [ ] **Step 2: Split `BASE_DIR` in `web/app.py`**

Open `web/app.py` line 23. It currently reads:

```python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
```

Since the file now lives in `web/`, this line still correctly computes `.../fanta-lab/web` — but all the *other* 10 usages of `BASE_DIR` (for `data/`, `examples/`, `.env`, `config.personal.py`, avatar files) need the repo root, not `web/`. Replace this single line with:

```python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # web/ — used for static serving only
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # repo root — used for data/config/env paths
```

Then, for every other `BASE_DIR`-based path in the file that refers to `data/`, `examples/`, `.env`, `config.personal.py`, or the avatar directory (NOT the static route), replace `BASE_DIR` with `PROJECT_ROOT`. Concretely:

- The `.env` path construction (originally around line 71) — change `os.path.join(BASE_DIR, ".env")` to `os.path.join(PROJECT_ROOT, ".env")`.
- The `config.personal.py` path construction (originally around line 93) — change `os.path.join(BASE_DIR, "config.personal.py")` to `os.path.join(PROJECT_ROOT, "core", "config.personal.py")` (note: this path must also reflect that `config.personal.py` now lives in `core/` per Task 1).
- The avatar path (originally around line 154) — change `os.path.join(BASE_DIR, ...)` to `os.path.join(PROJECT_ROOT, ...)` for whatever subdirectory it targets (inspect the exact line before editing to preserve the subpath after `BASE_DIR`).
- Any `data/` or `examples/` path built directly from `BASE_DIR` in `app.py` (rather than sourced from `core.config.DATA_DIR`/`EXAMPLES_DIR`) — change to `PROJECT_ROOT`.
- Leave the static route (originally lines 819-821, `send_from_directory(os.path.join(BASE_DIR, "static"), path)`) **unchanged** — `BASE_DIR` still correctly points to `web/`, and `web/static/` is exactly where the static files now live.

After editing, grep to confirm every remaining bare `BASE_DIR` usage in the file is either the static route or a genuinely web-relative path:

```bash
grep -n "BASE_DIR" web/app.py
```

Manually review each line in the output; anything referencing `data`, `examples`, `.env`, or `config.personal` must use `PROJECT_ROOT` instead.

- [ ] **Step 3: Update `vercel.json`**

Change:

```json
{
  "builds": [{ "src": "app.py", "use": "@vercel/python" }],
  "routes": [{ "src": "/(.*)", "dest": "app.py" }]
}
```

to reference `web/app.py` in both the `builds[0].src` field and the route `dest` field (preserve every other key/value already present in the file — only change the two path strings).

- [ ] **Step 4: Check for test files that import `app` directly**

```bash
grep -rln "^import app\|from app import\|import app as" tests/
```

If any test imports the root `app` module, update it to `from web import app` (or `sys.path`-insert `web/` before importing, matching whatever pattern the test already used before this task — inspect before editing). If no test imports `app` directly, no change needed here.

- [ ] **Step 5: Run full test suite**

Run: `pytest -q`
Expected: `89 passed, 1 error` (unchanged baseline).

- [ ] **Step 6: Manual smoke test of the Flask app**

```bash
cd web && python app.py &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5000/
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5000/static/css/style.css
kill %1
```

Expected: both curl commands print `200` (adjust the static asset filename to match whatever CSS file actually exists under `web/static/css/` if `style.css` isn't the real filename — check with `ls web/static/css/` first).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(web): move app.py and static/ into web/, split BASE_DIR/PROJECT_ROOT"
```

---

### Task 6: Replace LICENSE with PolyForm Noncommercial 1.0.0

**Files:**
- Modify: `LICENSE` (full replacement)
- Modify: `README.md` (license badge/section)

**Interfaces:**
- None (documentation-only task).

- [ ] **Step 1: Fetch and write the PolyForm Noncommercial 1.0.0 license text**

Fetch the canonical text from `https://polyformproject.org/licenses/noncommercial/1.0.0/` and write it verbatim into `LICENSE`, preserving the existing copyright line's holder name and year from the current `LICENSE` file (inspect the current file first to preserve `Copyright (c) <year> <holder>` exactly, only replacing the MIT license body below it with the PolyForm Noncommercial 1.0.0 text).

- [ ] **Step 2: Update `README.md`'s license badge/section**

Find the license badge (typically a shields.io badge near the top) and any "License" section near the bottom of `README.md`. Replace `MIT` references with `PolyForm Noncommercial 1.0.0`, and update the badge URL to point to a PolyForm-Noncommercial-1.0.0 badge (e.g. `https://img.shields.io/badge/license-PolyForm--Noncommercial--1.0.0-blue`) linking to the local `LICENSE` file.

- [ ] **Step 3: Grep-verify zero residual "MIT" mentions**

```bash
grep -rln "MIT License\|MIT license\|license-MIT" --include="*.md" .
```

Expected: no output. If any file references MIT (e.g. in `docs/`), update it to reference PolyForm Noncommercial 1.0.0 instead.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "docs(license): switch from MIT to PolyForm Noncommercial 1.0.0"
```

---

### Task 7: Write per-module READMEs

**Files:**
- Create: `core/README.md`, `core/ingestion/README.md`, `core/models/README.md`, `core/copilot/README.md`, `modules/common/README.md`, `modules/lineup/README.md`, `modules/valuation/README.md`, `modules/trades/README.md`, `modules/auction/README.md`, `web/README.md`
- Create: `core/models/__init__.py` if `core/models/` doesn't already exist as a package (it's documentation-only per the spec, no code moves — verify with `ls core/models/` first; if absent, create the directory with just the `__init__.py` and `README.md`)
- Create: `modules/auction/README.md`'s parent directory `modules/auction/` if absent (documentation-only, per spec — no code extraction from `web/app.py`)

**Interfaces:**
- None (documentation-only task). Each README follows the spec's 4-section format: (1) divulgativo — plain-language explanation for non-technical users, (2) tecnico — algorithms/formulas/data flow, (3) screenshot — embed an existing image from `docs/assets/` if topically relevant, else the placeholder line `> 📸 *Screenshot da aggiungere dopo il redesign UI (glow up).*`, (4) dipendenze — which other modules/files this one relies on.

- [ ] **Step 1: Verify/create `core/models/` and `modules/auction/` as doc-only directories**

```bash
mkdir -p core/models modules/auction
touch core/models/__init__.py
```

(`modules/auction/` needs no `__init__.py` since it contains no code — it's a documentation pointer to auction logic that lives in `web/app.py`.)

- [ ] **Step 2: Write `core/README.md`**

Write an index README for the `core/` package covering: what lives in `core/config.py` (unified cascading config, `APP_ENV` community/personal switch), `core/ingestion/` (static + dynamic scraping — link to `core/ingestion/README.md`), `core/models/` (link to `core/models/README.md`), `core/copilot/` (link to `core/copilot/README.md`). Divulgative section: "Il cuore del motore — qui vivono la configurazione e tutta la raccolta dati". Technical section: package layout tree with one line per subpackage. Dependencies section: `core/` has no internal dependencies on `modules/` or `web/` (it's the foundation layer).

- [ ] **Step 3: Write `core/ingestion/README.md`**

Cover both `core/ingestion/static/` (the 10 numbered pipeline steps + `target_pricing.py` + `generate_excel_italiano.py`, run via `run_pipeline.py`) and `core/ingestion/dynamic/` (the in-season scrapers producing `data/current_matchday.json`, consumed by `core.ingestion.dynamic.client`). Adapt path references from `docs/pipeline_architecture.md` (update any `pipeline/` path mentions in the adapted excerpt to `core/ingestion/static/` or `core/ingestion/dynamic/`). Embed screenshot placeholder (no existing screenshot matches this module specifically). Technical section: list each of the 10 static steps by number and one-line purpose, and each of the dynamic scrapers (`scrape_lineups.py`, `scrape_odds.py`, `scrape_results.py`, `scrape_status.py`, `build_feed.py`, `client.py`, `utils.py`) by one-line purpose.

- [ ] **Step 4: Write `core/models/README.md`**

Documentation-only (no code lives here — the actual model code is in `core/ingestion/static/08_quantile_points_model.py` and `09_vorp_auction_pricing.py`). Extract and adapt the quantile GBR methodology and VORP/fair-price formulas from `docs/MODEL_INTERPRETABILITY.md` and `docs/scoring_methodology.md`. Divulgative section explains P10/P50/P90 in plain language (reuse the glossary text: "P50 è la stima centrale, P10 è il pavimento minimo garantito, P90 è il massimo potenziale"). Technical section: quantile regression formula, VORP formula (`VORP = xPts_player - xPts_replacement_level`), fair price formula (rapporto budget/VORP). Note explicitly at the top: "Questo modulo è documentazione pura: il codice vive in `core/ingestion/static/08_quantile_points_model.py` e `09_vorp_auction_pricing.py`."

- [ ] **Step 5: Write `core/copilot/README.md`**

Cover the Provider-Agnostic architecture from Pilastro 5: `CopilotProvider` abstract interface, `OllamaProvider` (default, `http://localhost:11434/api/generate`), `GeminiProvider` (activated only if `GEMINI_API_KEY` present), `HeuristicFallbackProvider` (zero-cost deterministic fallback). Source technical content from the docstring header in `core/copilot/providers.py` (lines 1-9, documenting provider priority order). Embed the existing screenshot `docs/assets/ai_tactical_copilot.png` with a markdown image tag and one-line caption. Divulgative section: "Il tuo assistente tattico locale e gratuito, senza bisogno di API a pagamento".

- [ ] **Step 6: Write `modules/common/README.md`**

Cover `modules/common/data_provider.py` — the shared data-access layer used by `modules/lineup/`, `modules/valuation/`, `modules/trades/` to fetch the current matchday feed via `core.ingestion.dynamic.client.get_default_client()` and normalize player names via `core.ingestion.dynamic.utils.normalize_name`. Technical section: function signatures exposed by `data_provider.py` (inspect the file's public functions before writing this section to list them accurately). No screenshot (internal shared utility, not user-facing).

- [ ] **Step 7: Write `modules/lineup/README.md`**

Cover the Weekly Lineup Solver (`modules/lineup/lineup_solver.py`): the xPts objective formula, the MILP solver over the 7 admitted formations (3-4-3, 3-5-2, 4-3-3, 4-4-2, 4-5-1, 5-3-2, 5-4-1), the defensive-modifier bonus logic (≥4 defenders → average of top-3 defensive votes + goalkeeper), and Panchina Intelligente ordering. Adapt formula content already used in Pilastro 4's implementation. Screenshot placeholder (no existing lineup-solver-specific screenshot).

- [ ] **Step 8: Write `modules/valuation/README.md`**

Cover the Post-Draft League Audit & Power Rankings (`modules/valuation/audit_engine.py`): Expected Season Points calculation, Indice di Capitale a Rischio (Fragilità Medica) formula, and the 4 Draft Badges (Miglior Colpo VORP, Peggior Overpay, Most Balanced Squad, Glass Cannon) with their exact selection criteria. Screenshot: embed `docs/assets/listone_analytics.png` if its content topically matches valuation/analytics (verify the image's actual content before embedding; if it's clearly listone-browsing UI rather than audit/power-rankings UI, use the placeholder instead).

- [ ] **Step 9: Write `modules/trades/README.md`**

Cover the Trade Machine & marginal utility analysis (`modules/trades/trade_analyzer.py`): the Δ Utilità formula (`E[Punti Titolari Post-Trade] - E[Punti Titolari Pre-Trade]`), and the Win-Win Detector Combinatorio logic. Screenshot placeholder.

- [ ] **Step 10: Write `modules/auction/README.md`**

Documentation-only pointer README (per spec — no code extraction). State explicitly: "La logica d'asta (VORP, Knapsack MILP, Stop-Loss, Live Draft, blueprint tattici, assegnazione battitore) vive attualmente in `web/app.py` e non in questo modulo. Questo README documenta la logica per riferimento, senza spostare codice." Cover: the 4 rewritten blueprint percentages from Pilastro 2 fix #4 (Trazione Anteriore P5/D15/C25/A55, Modificatore di Ferro P8/D32/C25/A35, Centrocampo Dominante P6/D18/C42/A34, Moneyball P7/D23/C30/A40), the runtime cap formula `Cap_Ruolo = Budget_Lega × Quota_Ruolo`, and the Scala Slot Tiers percentile fix (Tier 1 top 10%, Tier 2 10-30%, Tier 3 30-65%, Tier 4 remainder, computed disjointly per role P/D/C/A). Embed `docs/assets/scala_slot_tactics.png`.

- [ ] **Step 11: Write `web/README.md`**

Cover the unified Flask web server (`web/app.py`), the `PROJECT_ROOT`/`BASE_DIR` split introduced in Task 5, the dual-track `APP_ENV` behavior (community vs. personal), the read-only-filesystem constraint on Vercel (no synchronous disk writes — all user mutations persist via `localStorage`), and the static asset layout (`web/static/css/`, `web/static/js/`, including `tutorial.js`/`tutorial.css` from Pilastro 6). Embed `docs/assets/command_center_overview.png`.

- [ ] **Step 12: Run full test suite (sanity check — docs shouldn't break anything)**

Run: `pytest -q`
Expected: `89 passed, 1 error` (unchanged baseline).

- [ ] **Step 13: Commit**

```bash
git add -A
git commit -m "docs: add per-module READMEs for core/, modules/, web/"
```

---

### Task 8: Write the bilingual project timeline

**Files:**
- Create: `docs/it/TIMELINE_PROGETTO.md`
- Create: `docs/en/PROJECT_TIMELINE.md`

**Interfaces:**
- None (documentation-only task).

- [ ] **Step 1: Write `docs/it/TIMELINE_PROGETTO.md`**

Write a 3-part narrative document:
1. **Da dove veniamo** — `fanta-lab` è nato come script pre-stagionale per l'asta, focalizzato su un singolo evento annuale (draft) con pricing statico basato su regressione quantile (GBR) per stimare P10/P50/P90 dei punti attesi, e VORP per il fair price.
2. **Cosa abbiamo costruito (Pilastri 1-7)** — un elenco cronologico sintetico: Pilastro 1 (dual-track community/personal), Pilastro 2 (bugfix critici: player_id fallback, resilienza scraping, ricalibrazione percentili per ruolo, blueprint percentuali dinamiche), Pilastro 3 (feed dinamico infrasettimanale via GitHub Actions + branch orfana `data-feed`), Pilastro 4 (moduli analitici: lineup solver MILP, audit post-draft, trade machine), Pilastro 5 (AI copilot locale Provider-Agnostic con Ollama), Pilastro 6 (finestra medica UI + tutorial interattivo), Pilastro 7 (questa ristrutturazione: modularità, licenza, documentazione). Enfasi sull'approccio statistico: passaggio da stima statica pre-asta a un sistema vivo che aggiorna le probabilità (quote bookmaker devigged, EWMA della forma, probabilità di titolarità) 3 volte a settimana per tutte le 38 giornate.
3. **Dove vogliamo arrivare** (visionario, non una roadmap concreta) — evoluzione verso un motore predittivo sempre più calibrato sull'incertezza (non solo punti attesi ma intere distribuzioni), maggiore autonomia dell'AI copilot nel suggerire decisioni in-season, e un'esperienza utente che rende accessibili a chiunque concetti statistici avanzati (quantili, VORP, fragilità) senza richiedere competenze tecniche.

2. **Write `docs/en/PROJECT_TIMELINE.md`** (Same 3-part structure, in English, faithful translation — not machine-translated boilerplate, but the same statistical emphasis and pillar list.)

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: add bilingual project timeline (IT/EN)"
```

---

### Task 9: Rewrite root README.md as an index

**Files:**
- Modify: `README.md`

**Interfaces:**
- None (documentation-only task).

- [ ] **Step 1: Restructure `README.md`**

Keep the existing quickstart/installation instructions (updating any file paths that changed, e.g. `python app.py` → `python web/app.py`, `python run_pipeline.py` unchanged since it stays at root). Add a new "Struttura del Progetto" / "Project Structure" section linking to every module README created in Task 7: `core/README.md`, `core/ingestion/README.md`, `core/models/README.md`, `core/copilot/README.md`, `modules/common/README.md`, `modules/lineup/README.md`, `modules/valuation/README.md`, `modules/trades/README.md`, `modules/auction/README.md`, `web/README.md`. Add links to `docs/it/TIMELINE_PROGETTO.md` / `docs/en/PROJECT_TIMELINE.md`. Verify the license badge/section already reflects PolyForm Noncommercial 1.0.0 from Task 6.

- [ ] **Step 2: Grep-verify all internal README links resolve to existing files**

```bash
grep -oE '\[.*\]\([^)]*\.md\)' README.md | grep -oE '\([^)]*\.md\)' | tr -d '()' | while read f; do
  [ -f "$f" ] && echo "OK: $f" || echo "MISSING: $f"
done
```

Expected: every line prints `OK:`, no `MISSING:` lines.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs: rewrite root README as module index"
```

---

### Task 10: Final whole-repo verification

**Files:**
- None created/modified (verification-only task).

**Interfaces:**
- None.

- [ ] **Step 1: Full pytest run**

Run: `pytest -q`
Expected: `89 passed, 1 error` (same baseline as the start of this plan).

- [ ] **Step 2: Grep for residual stale references**

```bash
grep -rn "^import config$\|from copilot import\|pipeline\.dynamic\|pipeline\.[0-9]" --include="*.py" --include="*.yml" . | grep -v "docs/superpowers"
grep -rln "MIT License\|MIT license" --include="*.md" .
```

Expected: both commands produce no output.

- [ ] **Step 3: Verify `vercel.json` and workflow file point to new paths**

```bash
grep -n "app.py\|src" vercel.json
grep -n "core.ingestion" .github/workflows/dynamic_feed.yml
```

Expected: `vercel.json` shows `web/app.py`; the workflow shows `core.ingestion.dynamic.build_feed`.

- [ ] **Step 4: Manual curl smoke test on `web/app.py`**

```bash
cd web && python app.py &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5000/
kill %1
cd ..
```

Expected: `200`.

- [ ] **Step 5: Commit final verification note (if any stragglers were fixed in this task)**

```bash
git add -A
git commit -m "chore: final verification pass for repo restructure (Pilastro 7)" --allow-empty
```
