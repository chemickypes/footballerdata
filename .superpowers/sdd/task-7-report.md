# Task 7 Report

## Files created
- `core/README.md` — index del package foundation con layout tree, ruolo di configurazione e dipendenze di alto livello.
- `core/ingestion/README.md` — overview completa della pipeline statica (10 step) e del feed dinamico settimanale con sorgenti dati.
- `core/models/README.md` — documentazione pura su quantili P10/P50/P90, quantile regression, VORP e fair price curve.
- `core/models/__init__.py` — file package marker per il modulo documentale `core.models`.
- `core/copilot/README.md` — architettura provider-agnostic del tactical copilot, con provider, cascata e fallback.
- `modules/common/README.md` — documentazione del shared data layer e delle sue funzioni pubbliche per overlay/xPts/status.
- `modules/lineup/README.md` — spiegazione del Weekly Lineup Solver, MILP, formazioni, bonus modificatore e panchina.
- `modules/valuation/README.md` — audit post-asta, expected season points, capitale a rischio e criteri dei draft badges.
- `modules/trades/README.md` — trade machine con delta utilità, role multipliers e win-win detector combinatorio.
- `modules/auction/README.md` — documentazione-only module che descrive blueprint, cap di reparto e tier slots, rimandando a `web/app.py`.
- `web/README.md` — documentazione del server Flask, path split `BASE_DIR`/`PROJECT_ROOT`, APP_ENV e asset statici.

## Verification
### Pytest
Command run:
```bash
/usr/bin/python3 -m pytest -q
```
Result:
- `89 passed, 1 warning, 1 error in 2.88s`
- The single error is the pre-existing baseline setup error in `tests/test_dual_track_and_features.py::test` (`fixture 'name' not found`).

### Markdown placeholder scan
Command run:
```bash
grep -rln "TBD\|TODO\|implement later\|fill in details" --include="*.md" core/ modules/ web/
```
Result:
- Exit code `1` (no matches).
- No forbidden placeholder strings were found in the newly created README files.

## Self-review
- Confirmed 4-section format present in each of the 10 README files: `Divulgativo`, `Tecnico`, `Screenshot`, `Dipendenze`.
- Confirmed real screenshots embedded in exactly 4 files:
  - `core/ingestion/README.md` → `docs/assets/listone_analytics.png`
  - `core/copilot/README.md` → `docs/assets/ai_tactical_copilot.png`
  - `modules/auction/README.md` → `docs/assets/scala_slot_tactics.png`
  - `web/README.md` → `docs/assets/command_center_overview.png`
- Confirmed exact placeholder line used in the other 6 README files:
  - `core/README.md`
  - `core/models/README.md`
  - `modules/common/README.md`
  - `modules/lineup/README.md`
  - `modules/valuation/README.md`
  - `modules/trades/README.md`
- Confirmed content was derived from the referenced docs and actual module code instead of invented APIs.

## Concerns
- `core/copilot/README.md` follows the requested provider-agnostic narrative, but the current code in `core/copilot/providers.py` now includes `OpenAIProvider`, `GroqProvider`, and `CascadeProvider` in addition to Ollama/Gemini; the README documents the real current behavior rather than omitting those classes.
- `web/app.py` still contains a `/tmp` fallback inside `_get_writable_path()`; this was only documented, not modified, because Task 7 is documentation-only.
