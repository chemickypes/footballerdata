# Pilastro 4 — Moduli Analitici Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build 3 analytics modules (Weekly Lineup Solver, Post-Draft Audit Engine, Trade Machine)
in a new `modules/` package, wire the existing Pilastro 3 dynamic feed client into `app.py` for
the first time, and add 3 new UI tabs ("Formazione", "Classifica Lega", "Scambi") without touching
any existing tab/route.

**Architecture:** Pure-function analytics modules under `modules/{lineup,valuation,trades}/`, plus
a shared `modules/common/data_provider.py` that isolates dataset loading and dynamic-feed access
(with an explicit `overlay_available` flag — no silent fallback). Flask routes in `app.py` stay
thin: load state/dataset, call the module, return JSON. UI additions follow the existing
`switchTab()` / `tab-content` div pattern already used by the 6 current tabs.

**Tech Stack:** Python 3, pandas, `scipy.optimize.milp` (already a dependency, pattern copied from
`pipeline/10_roster_optimizer.py`), pytest, Flask, vanilla JS/CSS (no new frontend dependencies).

## Global Constraints

- No modification to the 6 existing tabs/routes (`draft`, `targets`, `strategy`, `rosters`,
  `listone`, `ai`) or their underlying Python functions.
- New tab names in the UI: **"Formazione"**, **"Classifica Lega"**, **"Scambi"** (short, simplified
  names — not the capitolato's original technical names).
- Weekly Lineup Solver runs for **all** teams in `state["teams"]`, but the `/api/lineup/solve`
  route defaults to and the UI only displays the team with `is_me: true`.
- No new scraping: reuse existing `dataset_finale.csv` columns
  (`giorni_infortunio_3y`, `n_infortuni_3y`, `malus_infortuni`, `surplus_value_cr`, `vorp_points`,
  `predicted_pts_p10/p50/p90`, `prezzo_fair_1000`).
- The Lineup Solver **requires** a valid dynamic feed (titolarità/infortuni/quote). If
  `pipeline.dynamic.client.get_default_client().get_feed()` cannot supply real overlay data
  (feed unavailable/matchday == 0 placeholder), the solver returns `{"success": False, "error":
  "feed_unavailable", ...}` — it must NEVER produce a lineup based only on `dataset_finale.csv`.
- No model retraining (Stage 8 GBR) in this pillar — only a lightweight re-weighting of
  `predicted_pts_p50` using EWMA history tracked in `data/season_tracking.jsonl`.
- Trade Machine manual swap UI: up to 6 total players across the trade. Win-Win Detector auto
  search: capped at 3-vs-3 (6 total) for combinatorial cost reasons.
- All new Python modules must have corresponding pytest tests with no live network calls (mock
  `pipeline.dynamic.client` and file I/O), following the style of `tests/test_dynamic_feed.py`.
- `scipy>=1.11.0` is already in `requirements.txt` — no new dependencies required for the MILP.

---

## File Structure

```
modules/
├── __init__.py
├── common/
│   ├── __init__.py
│   └── data_provider.py         # Task 1
├── lineup/
│   ├── __init__.py
│   └── lineup_solver.py         # Task 2
├── valuation/
│   ├── __init__.py
│   ├── season_tracking.py       # Task 3
│   └── audit_engine.py          # Task 4
└── trades/
    ├── __init__.py
    └── trade_analyzer.py        # Task 5

tests/
├── test_data_provider.py        # Task 1
├── test_lineup_solver.py        # Task 2
├── test_season_tracking.py      # Task 3
├── test_audit_engine.py         # Task 4
└── test_trade_analyzer.py       # Task 5

app.py                            # Task 6 (new routes), Task 7 (new tabs/nav/JS)
```

---

### Task 1: Shared Data Provider (`modules/common/data_provider.py`)

**Files:**
- Create: `modules/__init__.py` (empty)
- Create: `modules/common/__init__.py` (empty)
- Create: `modules/common/data_provider.py`
- Test: `tests/test_data_provider.py`

**Interfaces:**
- Consumes: `pipeline.dynamic.client.get_default_client()` (returns `MatchdayFeedClient`, method
  `.get_feed() -> dict` with keys `matchday`, `season`, `updated_at`, `fixtures`, `players`);
  `app.load_dataset()` is NOT imported directly (circular import risk — `app.py` will import
  `modules/*`). Instead `data_provider.get_player_pool(df)` takes the already-loaded DataFrame as
  a parameter from the caller.
- Produces:
  - `get_dynamic_overlay(client=None) -> dict | None` — returns the raw feed dict if it looks
    "real" (see below), else `None`. Never raises.
  - `is_overlay_real(feed: dict) -> bool` — returns `True` only if `feed.get("matchday", 0) > 0`
    and `len(feed.get("players", {})) > 0`. This distinguishes a genuinely fetched feed from the
    placeholder fallback (`data/fallback_matchday.json` has `matchday: 0`, empty `players`).
  - `compute_weekly_xpts(df: pd.DataFrame, overlay: dict | None) -> tuple[pd.DataFrame, bool]` —
    returns `(df_with_xpts_week_column, overlay_available: bool)`. If `overlay` is `None` or not
    "real" per `is_overlay_real`, returns `(df, False)` with an `xpts_week` column filled with
    `NaN` (callers must check the boolean, not just the column). If real, matches each dataset row
    to `overlay["players"]` by building the same key format as
    `pipeline.dynamic.build_feed._player_key(team, name, role)` — re-implemented locally (see
    Step 3) since `build_feed` is a pipeline script, not meant to be imported at request time —
    and sets `xpts_week` from `overlay["players"][key]["xpts"]` when found, `NaN` otherwise
    (players missing from overlay, e.g. new dataset entries not yet in feed).
  - `get_player_status(overlay: dict, team: str, name: str, role: str) -> str` — returns
    `overlay["players"][key]["status"]` if present, else `"OK"`.

- [ ] **Step 1: Write the failing test for `is_overlay_real`**

```python
# tests/test_data_provider.py
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.common.data_provider import (
    is_overlay_real,
    get_dynamic_overlay,
    compute_weekly_xpts,
    get_player_status,
)


def test_is_overlay_real_false_for_placeholder_feed():
    placeholder = {"matchday": 0, "season": "2026/2027", "fixtures": [], "players": {}}
    assert is_overlay_real(placeholder) is False


def test_is_overlay_real_false_for_none():
    assert is_overlay_real(None) is False


def test_is_overlay_real_true_for_populated_feed():
    real_feed = {
        "matchday": 4,
        "season": "2026/2027",
        "fixtures": [],
        "players": {"inter_lautaro_martinez_a": {"name": "Lautaro Martinez", "xpts": 6.85}},
    }
    assert is_overlay_real(real_feed) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules'`

- [ ] **Step 3: Write `modules/common/data_provider.py`**

```python
# modules/common/data_provider.py
"""
Shared data layer for the Pilastro 4 analytics modules (lineup solver, audit
engine, trade analyzer). Isolates dataset loading and dynamic-feed access so
downstream modules never talk to pipeline.dynamic.client directly.
"""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pipeline.dynamic.client import get_default_client
from pipeline.dynamic.utils import normalize_name


def is_overlay_real(feed):
    """Distinguishes a genuinely fetched dynamic feed from the empty placeholder
    fallback (data/fallback_matchday.json has matchday=0 and no players)."""
    if not feed:
        return False
    return feed.get("matchday", 0) > 0 and len(feed.get("players", {})) > 0


def get_dynamic_overlay(client=None):
    """Fetches the dynamic feed via the Pilastro 3 client. Never raises: any
    exception (network error, malformed JSON) results in None being returned,
    which callers must interpret as 'no live data available'."""
    try:
        client = client or get_default_client()
        feed = client.get_feed()
        return feed if is_overlay_real(feed) else None
    except Exception:
        return None


def _team_slug(team_value):
    return normalize_name(str(team_value)).replace(" ", "_")


def _player_key(team_value, player_name, role):
    """Mirrors pipeline.dynamic.build_feed._player_key exactly (team_player_role
    format) so overlay lookups match the keys produced by the feed builder."""
    return f"{_team_slug(team_value)}_{normalize_name(player_name).replace(' ', '_')}_{str(role).lower()}"


def compute_weekly_xpts(df, overlay):
    """Adds an 'xpts_week' column to a copy of df using the dynamic feed's
    precomputed per-player xpts. Returns (df_with_column, overlay_available).
    If overlay is None/not real, xpts_week is all NaN and overlay_available is
    False -- callers (e.g. lineup_solver) must check the flag, not just the
    column, since NaN alone doesn't distinguish 'no live data' from 'player
    missing from an otherwise valid feed'."""
    df = df.copy()
    overlay_available = is_overlay_real(overlay)

    if not overlay_available:
        df["xpts_week"] = math.nan
        return df, False

    players_feed = overlay.get("players", {})
    xpts_values = []
    for _, row in df.iterrows():
        key = _player_key(row.get("team", ""), row.get("player", ""), row.get("role", ""))
        entry = players_feed.get(key)
        xpts_values.append(entry["xpts"] if entry and "xpts" in entry else math.nan)
    df["xpts_week"] = xpts_values
    return df, True


def get_player_status(overlay, team, name, role):
    """Returns the dynamic feed status for a player ('OK' if unknown/overlay
    missing) -- used by lineup_solver to exclude INFORTUNATO/SQUALIFICATO."""
    if not is_overlay_real(overlay):
        return "OK"
    key = _player_key(team, name, role)
    entry = overlay.get("players", {}).get(key)
    return entry.get("status", "OK") if entry else "OK"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data_provider.py -v`
Expected: 3 passed

- [ ] **Step 5: Add tests for `compute_weekly_xpts` and `get_player_status`, then implementation is already in place**

```python
# append to tests/test_data_provider.py

def test_compute_weekly_xpts_returns_nan_column_when_overlay_missing():
    df = pd.DataFrame([{"player": "Malen", "role": "A", "team": "Milan"}])
    result_df, available = compute_weekly_xpts(df, None)
    assert available is False
    assert result_df["xpts_week"].isna().all()


def test_compute_weekly_xpts_matches_player_by_key_when_overlay_real():
    df = pd.DataFrame([{"player": "Lautaro Martinez", "role": "A", "team": "Inter"}])
    overlay = {
        "matchday": 4,
        "players": {
            "inter_lautaro_martinez_a": {"name": "Lautaro Martinez", "xpts": 6.85, "status": "OK"}
        },
    }
    result_df, available = compute_weekly_xpts(df, overlay)
    assert available is True
    assert result_df.loc[0, "xpts_week"] == 6.85


def test_compute_weekly_xpts_nan_for_player_missing_from_overlay():
    df = pd.DataFrame([{"player": "Unknown Player", "role": "A", "team": "Roma"}])
    overlay = {"matchday": 4, "players": {"inter_lautaro_martinez_a": {"xpts": 6.85, "status": "OK"}}}
    result_df, available = compute_weekly_xpts(df, overlay)
    assert available is True
    assert math.isnan(result_df.loc[0, "xpts_week"])


def test_get_player_status_defaults_to_ok_when_overlay_missing():
    assert get_player_status(None, "Inter", "Lautaro Martinez", "A") == "OK"


def test_get_player_status_returns_feed_status():
    overlay = {
        "matchday": 4,
        "players": {"inter_lautaro_martinez_a": {"status": "INFORTUNATO"}},
    }
    assert get_player_status(overlay, "Inter", "Lautaro Martinez", "A") == "INFORTUNATO"
```

Add `import math` at the top of `tests/test_data_provider.py` alongside the existing imports.

- [ ] **Step 6: Run full test file to verify all pass**

Run: `pytest tests/test_data_provider.py -v`
Expected: 8 passed

- [ ] **Step 7: Commit**

```bash
git add modules/__init__.py modules/common/__init__.py modules/common/data_provider.py tests/test_data_provider.py
git commit -m "feat(modules): add shared data provider with dynamic-feed overlay detection

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Weekly Lineup Solver (`modules/lineup/lineup_solver.py`)

**Files:**
- Create: `modules/lineup/__init__.py` (empty)
- Create: `modules/lineup/lineup_solver.py`
- Test: `tests/test_lineup_solver.py`

**Interfaces:**
- Consumes: `modules.common.data_provider.get_dynamic_overlay()`, `compute_weekly_xpts(df, overlay)`,
  `get_player_status(overlay, team, name, role)` from Task 1.
- Produces: `solve_lineup(roster: list[dict], overlay: dict | None) -> dict`. `roster` is a list of
  dicts shaped like `state["teams"][i]["roster"]` items (`player`, `role`, `team`, `price` keys,
  from `app.py`'s existing schema — `team` may be absent on older records, default `""`).
  Return shape on success:
  ```python
  {"success": True, "formation": "4-3-3",
   "starters": [{"player": "...", "role": "D", "xpts": 5.2}, ...],  # 11 items
   "bench": [{"player": "...", "role": "D", "xpts": 3.1}, ...],
   "total_xpts": 63.4, "bonus_modificatore_expected": 1.0}
  ```
  On failure: `{"success": False, "error": "feed_unavailable" | "no_feasible_formation", "message": "..."}`.
  This exact dict shape is consumed by Task 5 (Trade Machine, pre/post comparison) and Task 6
  (Flask route serialization).

- [ ] **Step 1: Write the failing test for the "feed unavailable" guard**

```python
# tests/test_lineup_solver.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.lineup.lineup_solver import solve_lineup, FORMATIONS

SAMPLE_ROSTER = [
    {"player": "Portiere1", "role": "P", "team": "Inter"},
    {"player": "Diff1", "role": "D", "team": "Milan"},
    {"player": "Diff2", "role": "D", "team": "Roma"},
    {"player": "Diff3", "role": "D", "team": "Napoli"},
    {"player": "Cent1", "role": "C", "team": "Lazio"},
    {"player": "Cent2", "role": "C", "team": "Atalanta"},
    {"player": "Cent3", "role": "C", "team": "Fiorentina"},
    {"player": "Att1", "role": "A", "team": "Juventus"},
    {"player": "Att2", "role": "A", "team": "Torino"},
    {"player": "Att3", "role": "A", "team": "Bologna"},
    {"player": "Riserva1", "role": "D", "team": "Genoa"},
]


def test_solve_lineup_fails_when_overlay_none():
    result = solve_lineup(SAMPLE_ROSTER, overlay=None)
    assert result["success"] is False
    assert result["error"] == "feed_unavailable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lineup_solver.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.lineup'`

- [ ] **Step 3: Write `modules/lineup/lineup_solver.py`**

```python
# modules/lineup/lineup_solver.py
"""
Weekly Lineup Solver (Pilastro 4). Requires a valid dynamic feed (titolarita',
infortuni, quote) -- there is deliberately NO fallback to static
dataset_finale.csv data here: recommending a starting XI using only historical
season averages risks fielding an injured/suspended player, which is
unacceptable for this specific use case (unlike the rest of the app, where a
static fallback is appropriate).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
from scipy.optimize import milp, LinearConstraint, Bounds

from modules.common.data_provider import is_overlay_real, compute_weekly_xpts, get_player_status

EXCLUDED_STATUSES = {"INFORTUNATO", "SQUALIFICATO"}

# (P, D, C, A) counts per legal formation.
FORMATIONS = {
    "3-4-3": (1, 3, 4, 3),
    "3-5-2": (1, 3, 5, 2),
    "4-3-3": (1, 4, 3, 3),
    "4-4-2": (1, 4, 4, 2),
    "4-5-1": (1, 4, 5, 1),
    "5-3-2": (1, 5, 3, 2),
    "5-4-1": (1, 5, 4, 1),
}


def _solve_single_formation(df, n_p, n_d, n_c, n_a):
    """Binary MILP: maximize sum(xpts_week) of the 11 starters subject to exact
    per-role counts. Returns the selected row indices, or None if infeasible."""
    n = len(df)
    if n < (n_p + n_d + n_c + n_a):
        return None

    c = -1.0 * df["xpts_week"].fillna(0.0).values

    is_p = (df["role"] == "P").astype(float).values
    is_d = (df["role"] == "D").astype(float).values
    is_c = (df["role"] == "C").astype(float).values
    is_a = (df["role"] == "A").astype(float).values
    is_any = np.ones(n)

    A = np.vstack([is_p, is_d, is_c, is_a, is_any])
    rhs = np.array([float(n_p), float(n_d), float(n_c), float(n_a), float(n_p + n_d + n_c + n_a)])
    constraints = LinearConstraint(A, rhs, rhs)

    bounds = Bounds(np.zeros(n), np.ones(n))
    integrality = np.ones(n)

    res = milp(c=c, constraints=constraints, bounds=bounds, integrality=integrality)
    if not res.success:
        return None
    return np.where(res.x > 0.5)[0]


def _bonus_modificatore(df, selected_indices):
    """Estimates the defensive-modifier bonus: if >=4 defenders are fielded,
    average of the 3 best expected defensive scores + goalkeeper's xpts."""
    starters = df.iloc[selected_indices]
    defenders = starters[starters["role"] == "D"]
    goalkeepers = starters[starters["role"] == "P"]
    if len(defenders) < 4:
        return 0.0
    top3_def = defenders.nlargest(3, "xpts_week")["xpts_week"].fillna(0.0)
    gk_xpts = goalkeepers["xpts_week"].fillna(0.0).sum()
    return float((top3_def.sum() + gk_xpts) / 4.0)


def solve_lineup(roster, overlay):
    """Solves the optimal weekly formation for a single team's roster.

    roster: list of dicts with at least 'player', 'role', 'team' keys
            (matches app.py's state["teams"][i]["roster"] item schema).
    overlay: the raw dynamic feed dict from data_provider.get_dynamic_overlay(),
             or None.
    """
    if not is_overlay_real(overlay):
        return {
            "success": False,
            "error": "feed_unavailable",
            "message": "Dati in tempo reale non disponibili (titolarita'/infortuni/quote). Riprova più tardi.",
        }

    if not roster:
        return {
            "success": False,
            "error": "no_feasible_formation",
            "message": "Rosa vuota: nessuna formazione calcolabile.",
        }

    df = pd.DataFrame(roster)
    df, _ = compute_weekly_xpts(df, overlay)

    statuses = [
        get_player_status(overlay, row.get("team", ""), row.get("player", ""), row.get("role", ""))
        for _, row in df.iterrows()
    ]
    df["status"] = statuses
    df = df[~df["status"].isin(EXCLUDED_STATUSES)].reset_index(drop=True)

    best = None
    for formation_name, (n_p, n_d, n_c, n_a) in FORMATIONS.items():
        selected = _solve_single_formation(df, n_p, n_d, n_c, n_a)
        if selected is None:
            continue
        total_xpts = float(df.iloc[selected]["xpts_week"].fillna(0.0).sum())
        if best is None or total_xpts > best["total_xpts"]:
            best = {"formation": formation_name, "selected": selected, "total_xpts": total_xpts}

    if best is None:
        return {
            "success": False,
            "error": "no_feasible_formation",
            "message": "Nessun modulo regolamentare è schierabile con la rosa attuale (troppi giocatori mancanti/esclusi).",
        }

    selected_set = set(best["selected"].tolist())
    starters = [
        {"player": r["player"], "role": r["role"], "xpts": round(float(r["xpts_week"] or 0.0), 2)}
        for _, r in df.iloc[best["selected"]].iterrows()
    ]
    bench_df = df.drop(index=best["selected"]).sort_values("xpts_week", ascending=False, na_position="last")
    bench = [
        {"player": r["player"], "role": r["role"], "xpts": round(float(r["xpts_week"] or 0.0), 2)}
        for _, r in bench_df.iterrows()
    ]

    return {
        "success": True,
        "formation": best["formation"],
        "starters": starters,
        "bench": bench,
        "total_xpts": round(best["total_xpts"], 2),
        "bonus_modificatore_expected": round(_bonus_modificatore(df, best["selected"]), 2),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lineup_solver.py -v`
Expected: 1 passed

- [ ] **Step 5: Add tests for successful solve, excluded players, and no-feasible-formation**

```python
# append to tests/test_lineup_solver.py

def _make_overlay(xpts_by_player, statuses=None):
    statuses = statuses or {}
    players = {}
    for i, (name, xpts) in enumerate(xpts_by_player.items()):
        players[f"team_{name.lower()}_x"] = {
            "name": name, "xpts": xpts, "status": statuses.get(name, "OK"),
        }
    return {"matchday": 4, "season": "2026/2027", "players": players}


def test_solve_lineup_picks_best_formation_with_full_roster():
    roster = [
        {"player": "GK", "role": "P", "team": "T"},
        *[{"player": f"D{i}", "role": "D", "team": "T"} for i in range(5)],
        *[{"player": f"C{i}", "role": "C", "team": "T"} for i in range(5)],
        *[{"player": f"A{i}", "role": "A", "team": "T"} for i in range(3)],
    ]
    xpts = {"GK": 5.0}
    xpts.update({f"D{i}": 4.0 + i * 0.1 for i in range(5)})
    xpts.update({f"C{i}": 6.0 + i * 0.1 for i in range(5)})
    xpts.update({f"A{i}": 7.0 + i * 0.1 for i in range(3)})
    overlay = _make_overlay(xpts)

    result = solve_lineup(roster, overlay)

    assert result["success"] is True
    assert result["formation"] in FORMATIONS
    assert len(result["starters"]) == 11
    assert result["total_xpts"] > 0


def test_solve_lineup_excludes_injured_players():
    roster = [
        {"player": "GK", "role": "P", "team": "T"},
        *[{"player": f"D{i}", "role": "D", "team": "T"} for i in range(5)],
        *[{"player": f"C{i}", "role": "C", "team": "T"} for i in range(5)],
        *[{"player": f"A{i}", "role": "A", "team": "T"} for i in range(3)],
    ]
    xpts = {"GK": 5.0}
    xpts.update({f"D{i}": 4.0 for i in range(5)})
    xpts.update({f"C{i}": 6.0 for i in range(5)})
    xpts.update({f"A{i}": 99.0 if i == 0 else 7.0 for i in range(3)})
    overlay = _make_overlay(xpts, statuses={"A0": "INFORTUNATO"})

    result = solve_lineup(roster, overlay)

    assert result["success"] is True
    starter_names = {s["player"] for s in result["starters"]}
    bench_names = {s["player"] for s in result["bench"]}
    assert "A0" not in starter_names
    assert "A0" not in bench_names  # excluded entirely, not just benched


def test_solve_lineup_no_feasible_formation_with_too_few_players():
    roster = [
        {"player": "GK", "role": "P", "team": "T"},
        {"player": "D0", "role": "D", "team": "T"},
    ]
    overlay = _make_overlay({"GK": 5.0, "D0": 4.0})

    result = solve_lineup(roster, overlay)

    assert result["success"] is False
    assert result["error"] == "no_feasible_formation"


def test_solve_lineup_empty_roster_returns_error_not_exception():
    overlay = _make_overlay({"X": 1.0})
    result = solve_lineup([], overlay)
    assert result["success"] is False
```

- [ ] **Step 6: Run full test file to verify all pass**

Run: `pytest tests/test_lineup_solver.py -v`
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add modules/lineup/__init__.py modules/lineup/lineup_solver.py tests/test_lineup_solver.py
git commit -m "feat(modules): add weekly lineup solver requiring live dynamic feed

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Season Tracking (`modules/valuation/season_tracking.py`)

**Files:**
- Create: `modules/valuation/__init__.py` (empty)
- Create: `modules/valuation/season_tracking.py`
- Test: `tests/test_season_tracking.py`

**Interfaces:**
- Consumes: nothing from other Task modules (standalone JSONL reader/writer).
- Produces:
  - `append_matchday_record(path: str, matchday: int, player: str, predicted_pts_p50_original: float, ewma_form_at_that_point: float, actual_score: float) -> None`
  - `load_tracking_history(path: str) -> list[dict]` — returns `[]` if file missing; silently
    skips malformed lines (never raises).
  - `get_recent_form(history: list[dict], player: str, n: int = 3) -> float | None` — average
    `ewma_form_at_that_point` over the last `n` records for `player` (by insertion/matchday order
    in the file), or `None` if fewer than 3 records exist for that player. This exact function is
    consumed by Task 4's re-weighting logic.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_season_tracking.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.valuation.season_tracking import (
    append_matchday_record,
    load_tracking_history,
    get_recent_form,
)


def test_load_tracking_history_returns_empty_list_when_file_missing(tmp_path):
    path = str(tmp_path / "does_not_exist.jsonl")
    assert load_tracking_history(path) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_season_tracking.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.valuation'`

- [ ] **Step 3: Write `modules/valuation/season_tracking.py`**

```python
# modules/valuation/season_tracking.py
"""
Append-only JSONL tracking of per-matchday prediction vs. actual performance
(Pilastro 4 Audit Engine re-weighting). One record per player per concluded
matchday. Never used for model retraining -- only for a lightweight
re-weighting of predicted_pts_p50 in audit_engine.py.
"""
import json
import os


def append_matchday_record(path, matchday, player, predicted_pts_p50_original,
                            ewma_form_at_that_point, actual_score):
    """Appends one JSONL record. Creates parent directory if needed."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    record = {
        "matchday": matchday,
        "player": player,
        "predicted_pts_p50_original": predicted_pts_p50_original,
        "ewma_form_at_that_point": ewma_form_at_that_point,
        "actual_score": actual_score,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_tracking_history(path):
    """Reads all valid JSONL records. Missing file -> []. Malformed lines are
    skipped individually so one corrupted row never breaks the whole read."""
    if not os.path.exists(path):
        return []

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def get_recent_form(history, player, n=3):
    """Average ewma_form_at_that_point over the last n records for player, in
    the order they appear in history (assumed chronological, since the file is
    append-only). Returns None if fewer than n records exist for that player,
    signaling audit_engine to skip re-weighting for this player."""
    player_records = [r for r in history if r.get("player") == player]
    if len(player_records) < n:
        return None
    recent = player_records[-n:]
    values = [r["ewma_form_at_that_point"] for r in recent if "ewma_form_at_that_point" in r]
    if len(values) < n:
        return None
    return sum(values) / len(values)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_season_tracking.py -v`
Expected: 1 passed

- [ ] **Step 5: Add remaining tests**

```python
# append to tests/test_season_tracking.py

def test_append_and_load_round_trip(tmp_path):
    path = str(tmp_path / "season_tracking.jsonl")
    append_matchday_record(path, 1, "Malen", 6.5, 6.0, 7.0)
    append_matchday_record(path, 2, "Malen", 6.5, 6.2, 5.5)

    history = load_tracking_history(path)

    assert len(history) == 2
    assert history[0]["player"] == "Malen"
    assert history[1]["matchday"] == 2


def test_load_tracking_history_skips_malformed_lines(tmp_path):
    path = tmp_path / "season_tracking.jsonl"
    path.write_text('{"player": "Malen", "matchday": 1}\nNOT VALID JSON\n{"player": "Krstovic", "matchday": 1}\n')

    history = load_tracking_history(str(path))

    assert len(history) == 2
    assert {r["player"] for r in history} == {"Malen", "Krstovic"}


def test_get_recent_form_returns_none_with_fewer_than_n_records():
    history = [
        {"player": "Malen", "ewma_form_at_that_point": 6.0},
        {"player": "Malen", "ewma_form_at_that_point": 6.2},
    ]
    assert get_recent_form(history, "Malen", n=3) is None


def test_get_recent_form_averages_last_n_records():
    history = [
        {"player": "Malen", "ewma_form_at_that_point": 5.0},
        {"player": "Malen", "ewma_form_at_that_point": 6.0},
        {"player": "Malen", "ewma_form_at_that_point": 7.0},
        {"player": "Malen", "ewma_form_at_that_point": 8.0},
    ]
    # last 3: 6.0, 7.0, 8.0 -> average 7.0
    assert get_recent_form(history, "Malen", n=3) == 7.0


def test_get_recent_form_ignores_other_players():
    history = [
        {"player": "Malen", "ewma_form_at_that_point": 6.0},
        {"player": "Malen", "ewma_form_at_that_point": 6.0},
        {"player": "Malen", "ewma_form_at_that_point": 6.0},
        {"player": "Krstovic", "ewma_form_at_that_point": 99.0},
    ]
    assert get_recent_form(history, "Malen", n=3) == 6.0
```

- [ ] **Step 6: Run full test file to verify all pass**

Run: `pytest tests/test_season_tracking.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add modules/valuation/__init__.py modules/valuation/season_tracking.py tests/test_season_tracking.py
git commit -m "feat(modules): add season tracking JSONL for lightweight form re-weighting

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Post-Draft Audit Engine (`modules/valuation/audit_engine.py`)

**Files:**
- Create: `modules/valuation/audit_engine.py`
- Test: `tests/test_audit_engine.py`

**Interfaces:**
- Consumes: `modules.valuation.season_tracking.load_tracking_history(path)`,
  `get_recent_form(history, player, n=3)` from Task 3.
- Produces: `compute_audit(teams: list[dict], player_pool_df: pd.DataFrame, tracking_history: list[dict]) -> list[dict]`.
  `teams` matches `state["teams"]` shape (each with `id`, `name`, `roster` list of
  `{player, role, price, ...}`). `player_pool_df` is `dataset_finale.csv` loaded as DataFrame
  (columns include `player`, `giorni_infortunio_3y`, `surplus_value_cr`, `predicted_pts_p50`).
  Returns a list of dicts, one per team, **sorted by `expected_points` descending**:
  ```python
  [{"team_id": 1, "team_name": "Squadra 1", "expected_points": 1234.5,
    "risk_capital_cr": 80, "risk_capital_pct": 16.0, "badges": ["Miglior Colpo VORP: ..."]}]
  ```

- [ ] **Step 1: Write the failing test for basic expected points + risk capital**

```python
# tests/test_audit_engine.py
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.valuation.audit_engine import compute_audit

POOL = pd.DataFrame([
    {"player": "Malen", "role": "A", "giorni_infortunio_3y": 10, "surplus_value_cr": 5.0, "predicted_pts_p50": 8.0},
    {"player": "Krstovic", "role": "A", "giorni_infortunio_3y": 90, "surplus_value_cr": -3.0, "predicted_pts_p50": 6.0},
])


def test_compute_audit_calculates_expected_points_and_risk_capital():
    teams = [{
        "id": 1, "name": "Squadra 1", "budget": 500,
        "roster": [
            {"player": "Malen", "role": "A", "price": 50},
            {"player": "Krstovic", "role": "A", "price": 30},
        ],
    }]

    result = compute_audit(teams, POOL, tracking_history=[])

    assert len(result) == 1
    entry = result[0]
    assert entry["team_id"] == 1
    assert entry["expected_points"] == pytest.approx(14.0)  # 8.0 + 6.0
    assert entry["risk_capital_cr"] == 30  # only Krstovic (90 gg > 60 threshold)
    assert entry["risk_capital_pct"] == pytest.approx(6.0)  # 30 / 500 * 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_audit_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.valuation.audit_engine'`

- [ ] **Step 3: Write `modules/valuation/audit_engine.py`**

```python
# modules/valuation/audit_engine.py
"""
Post-Draft League Audit & Power Rankings (Pilastro 4). Read-only report over
existing state/dataset data -- no dynamic feed dependency, since this is a
strategic season-long assessment, not a per-matchday lineup decision.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from modules.valuation.season_tracking import get_recent_form

FRAGILITY_THRESHOLD_DAYS = 60


def _player_row(pool_df, player_name):
    match = pool_df[pool_df["player"] == player_name]
    return match.iloc[0] if not match.empty else None


def _reweighted_value(pool_row, tracking_history):
    """Blends the original P50 with recent EWMA form if >=3 tracking records
    exist for the player; otherwise returns the original P50 unchanged."""
    original_p50 = float(pool_row.get("predicted_pts_p50", 0.0) or 0.0)
    recent_form = get_recent_form(tracking_history, pool_row["player"], n=3)
    if recent_form is None:
        return original_p50
    return 0.5 * original_p50 + 0.5 * recent_form


def _team_expected_points(team, pool_df, tracking_history):
    total = 0.0
    for item in team.get("roster", []):
        row = _player_row(pool_df, item.get("player"))
        if row is not None:
            total += _reweighted_value(row, tracking_history)
    return total


def _team_risk_capital(team, pool_df):
    risk_cr = 0
    for item in team.get("roster", []):
        row = _player_row(pool_df, item.get("player"))
        if row is not None and float(row.get("giorni_infortunio_3y", 0) or 0) > FRAGILITY_THRESHOLD_DAYS:
            risk_cr += int(item.get("price", 0) or 0)
    return risk_cr


def _best_worst_surplus(team, pool_df):
    best, worst = None, None
    for item in team.get("roster", []):
        row = _player_row(pool_df, item.get("player"))
        if row is None or "surplus_value_cr" not in row:
            continue
        surplus = float(row["surplus_value_cr"])
        if best is None or surplus > best[1]:
            best = (item["player"], surplus)
        if worst is None or surplus < worst[1]:
            worst = (item["player"], surplus)
    return best, worst


def _department_std(team, pool_df):
    """Standard deviation of spend across P/D/C/A -- lower means more balanced."""
    spend_by_role = {"P": 0, "D": 0, "C": 0, "A": 0}
    for item in team.get("roster", []):
        role = item.get("role")
        if role in spend_by_role:
            spend_by_role[role] += int(item.get("price", 0) or 0)
    return float(np.std(list(spend_by_role.values())))


def compute_audit(teams, player_pool_df, tracking_history):
    """Computes power ranking, risk capital, and badges for every team.

    teams: list of dicts shaped like state["teams"] (id, name, budget, roster).
    player_pool_df: dataset_finale.csv loaded as DataFrame.
    tracking_history: list of dicts from season_tracking.load_tracking_history().
    """
    entries = []
    for team in teams:
        budget = float(team.get("budget", 0) or 1)
        expected_points = _team_expected_points(team, player_pool_df, tracking_history)
        risk_cr = _team_risk_capital(team, player_pool_df)
        entries.append({
            "team_id": team["id"],
            "team_name": team.get("name", f"Squadra {team['id']}"),
            "expected_points": round(expected_points, 2),
            "risk_capital_cr": risk_cr,
            "risk_capital_pct": round((risk_cr / budget) * 100.0, 2) if budget else 0.0,
            "_department_std": _department_std(team, player_pool_df),
            "badges": [],
        })

    # Cross-team badges.
    if entries:
        for team, entry in zip(teams, entries):
            badges = []
            best, worst = _best_worst_surplus(team, player_pool_df)
            if best:
                badges.append(f"Miglior Colpo VORP: {best[0]} (+{best[1]:.1f} cr)")
            if worst and worst[1] < 0:
                badges.append(f"Peggior Overpay: {worst[0]} ({worst[1]:.1f} cr)")
            entry["badges"] = badges

        min_std = min(e["_department_std"] for e in entries)
        for entry in entries:
            if entry["_department_std"] == min_std:
                entry["badges"].append("Most Balanced Squad")

        points_sorted = sorted(entries, key=lambda e: e["expected_points"], reverse=True)
        risk_sorted = sorted(entries, key=lambda e: e["risk_capital_cr"], reverse=True)
        top3_points_ids = {e["team_id"] for e in points_sorted[:3]}
        top3_risk_ids = {e["team_id"] for e in risk_sorted[:3]}
        for entry in entries:
            if entry["team_id"] in top3_points_ids and entry["team_id"] in top3_risk_ids:
                entry["badges"].append("Glass Cannon")

        for entry in entries:
            del entry["_department_std"]

    return sorted(entries, key=lambda e: e["expected_points"], reverse=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_audit_engine.py -v`
Expected: 1 passed

- [ ] **Step 5: Add remaining tests (re-weighting, badges, missing tracking file, empty roster)**

```python
# append to tests/test_audit_engine.py

def test_compute_audit_reweights_with_recent_form_when_history_available():
    teams = [{
        "id": 1, "name": "Squadra 1", "budget": 500,
        "roster": [{"player": "Malen", "role": "A", "price": 50}],
    }]
    tracking_history = [
        {"player": "Malen", "ewma_form_at_that_point": 4.0},
        {"player": "Malen", "ewma_form_at_that_point": 4.0},
        {"player": "Malen", "ewma_form_at_that_point": 4.0},
    ]

    result = compute_audit(teams, POOL, tracking_history)

    # original P50 = 8.0, recent form avg = 4.0 -> reweighted = 0.5*8 + 0.5*4 = 6.0
    assert result[0]["expected_points"] == pytest.approx(6.0)


def test_compute_audit_no_reweighting_without_enough_history():
    teams = [{
        "id": 1, "name": "Squadra 1", "budget": 500,
        "roster": [{"player": "Malen", "role": "A", "price": 50}],
    }]
    tracking_history = [{"player": "Malen", "ewma_form_at_that_point": 4.0}]  # only 1 record

    result = compute_audit(teams, POOL, tracking_history)

    assert result[0]["expected_points"] == pytest.approx(8.0)  # unchanged original P50


def test_compute_audit_assigns_badges_across_teams():
    teams = [
        {"id": 1, "name": "Squadra 1", "budget": 500,
         "roster": [{"player": "Malen", "role": "A", "price": 50}]},
        {"id": 2, "name": "Squadra 2", "budget": 500,
         "roster": [{"player": "Krstovic", "role": "A", "price": 30}]},
    ]

    result = compute_audit(teams, POOL, tracking_history=[])

    by_id = {e["team_id"]: e for e in result}
    assert any("Miglior Colpo VORP" in b for b in by_id[1]["badges"])
    assert any("Peggior Overpay" in b for b in by_id[2]["badges"])


def test_compute_audit_handles_empty_roster_without_crashing():
    teams = [{"id": 1, "name": "Squadra 1", "budget": 500, "roster": []}]
    result = compute_audit(teams, POOL, tracking_history=[])
    assert result[0]["expected_points"] == 0.0
    assert result[0]["risk_capital_cr"] == 0
```

- [ ] **Step 6: Run full test file to verify all pass**

Run: `pytest tests/test_audit_engine.py -v`
Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add modules/valuation/audit_engine.py tests/test_audit_engine.py
git commit -m "feat(modules): add post-draft audit engine with power ranking and badges

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Trade Machine (`modules/trades/trade_analyzer.py`)

**Files:**
- Create: `modules/trades/__init__.py` (empty)
- Create: `modules/trades/trade_analyzer.py`
- Test: `tests/test_trade_analyzer.py`

**Interfaces:**
- Consumes: `modules.lineup.lineup_solver.solve_lineup(roster, overlay)` from Task 2 (for the
  "Δ Formazione Live" evaluation).
- Produces:
  - `evaluate_trade(team_a_roster, players_out, team_b_roster, players_in, player_pool_df, overlay) -> dict`.
    `players_out`/`players_in` are lists of player-name strings (max 6 combined, enforced by the
    Flask route in Task 6, not here — this function accepts any length so it stays testable in
    isolation). Returns:
    ```python
    {"value_evaluation": {"team_a_delta": 1.5, "team_b_delta": -1.5},
     "live_lineup_evaluation": {"available": True, "team_a_delta_xpts": 2.1,
                                 "team_b_delta_xpts": -0.8, "message": ""}}
    ```
    If a named player is not found in the expected roster, returns
    `{"error": "player_not_found", "message": "..."}` at the top level (no partial evaluation).
  - `find_winwin_trades(my_roster, opponent_roster, player_pool_df, max_per_side=3, top_n=10) -> list[dict]`.
    Each result: `{"players_out": [...], "players_in": [...], "my_delta": 1.2, "opponent_delta": 0.5, "combined_delta": 1.7}`.

- [ ] **Step 1: Write the failing test for value evaluation (1-for-1)**

```python
# tests/test_trade_analyzer.py
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.trades.trade_analyzer import evaluate_trade, find_winwin_trades

POOL = pd.DataFrame([
    {"player": "Malen", "role": "A", "predicted_pts_p50": 8.0, "vorp_points": 3.0},
    {"player": "Krstovic", "role": "A", "predicted_pts_p50": 6.0, "vorp_points": 1.0},
    {"player": "DifensoreX", "role": "D", "predicted_pts_p50": 5.0, "vorp_points": 2.0},
    {"player": "DifensoreY", "role": "D", "predicted_pts_p50": 4.0, "vorp_points": 0.5},
])

TEAM_A_ROSTER = [{"player": "Malen", "role": "A"}]
TEAM_B_ROSTER = [{"player": "DifensoreX", "role": "D"}]


def test_evaluate_trade_value_evaluation_one_for_one():
    result = evaluate_trade(
        team_a_roster=TEAM_A_ROSTER, players_out=["Malen"],
        team_b_roster=TEAM_B_ROSTER, players_in=["DifensoreX"],
        player_pool_df=POOL, overlay=None,
    )
    # Team A gives Malen (8.0+3.0=11.0 combined), gets DifensoreX (5.0+2.0=7.0) -> delta = -4.0
    assert result["value_evaluation"]["team_a_delta"] == pytest.approx(-4.0)
    assert result["value_evaluation"]["team_b_delta"] == pytest.approx(4.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_trade_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.trades'`

- [ ] **Step 3: Write `modules/trades/trade_analyzer.py`**

```python
# modules/trades/trade_analyzer.py
"""
Trade Machine (Pilastro 4): evaluates N-for-N trades via a static "value
evaluation" (always available, P50+VORP based) plus an optional "live lineup
evaluation" (requires the dynamic feed, via lineup_solver -- degrades
gracefully to unavailable rather than blocking the whole response).
"""
import sys
import os
from itertools import combinations

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules.lineup.lineup_solver import solve_lineup
from modules.common.data_provider import is_overlay_real


def _player_value(pool_df, player_name):
    match = pool_df[pool_df["player"] == player_name]
    if match.empty:
        return None
    row = match.iloc[0]
    return float(row.get("predicted_pts_p50", 0.0) or 0.0) + float(row.get("vorp_points", 0.0) or 0.0)


def _value_evaluation(players_out, players_in, player_pool_df):
    """Returns (team_a_delta, team_b_delta, error) where error is None on
    success or a dict describing the missing player."""
    for name in players_out + players_in:
        if _player_value(player_pool_df, name) is None:
            return None, None, {"error": "player_not_found", "message": f"Giocatore non trovato nel dataset: {name}"}

    out_value = sum(_player_value(player_pool_df, n) for n in players_out)
    in_value = sum(_player_value(player_pool_df, n) for n in players_in)

    team_a_delta = in_value - out_value
    team_b_delta = out_value - in_value
    return team_a_delta, team_b_delta, None


def _apply_trade(roster, players_removed, players_added_from_other_roster, other_roster):
    """Builds a post-trade roster: removes players_removed, adds the full
    roster entries (role/team preserved) for players_added, looked up from
    other_roster."""
    remaining = [p for p in roster if p["player"] not in players_removed]
    added_entries = [p for p in other_roster if p["player"] in players_added_from_other_roster]
    return remaining + added_entries


def evaluate_trade(team_a_roster, players_out, team_b_roster, players_in, player_pool_df, overlay):
    """players_out: players team A gives away (must be in team_a_roster).
    players_in: players team A receives (must be in team_b_roster)."""
    team_a_delta, team_b_delta, error = _value_evaluation(players_out, players_in, player_pool_df)
    if error:
        return error

    live_eval = {"available": False, "team_a_delta_xpts": None, "team_b_delta_xpts": None, "message": ""}
    if is_overlay_real(overlay):
        team_a_post = _apply_trade(team_a_roster, players_out, players_in, team_b_roster)
        team_b_post = _apply_trade(team_b_roster, players_in, players_out, team_a_roster)

        pre_a = solve_lineup(team_a_roster, overlay)
        post_a = solve_lineup(team_a_post, overlay)
        pre_b = solve_lineup(team_b_roster, overlay)
        post_b = solve_lineup(team_b_post, overlay)

        if pre_a["success"] and post_a["success"] and pre_b["success"] and post_b["success"]:
            live_eval = {
                "available": True,
                "team_a_delta_xpts": round(post_a["total_xpts"] - pre_a["total_xpts"], 2),
                "team_b_delta_xpts": round(post_b["total_xpts"] - pre_b["total_xpts"], 2),
                "message": "",
            }
        else:
            live_eval["message"] = "Formazione non calcolabile per una delle due rose (rosa incompleta)."
    else:
        live_eval["message"] = "Dati in tempo reale non disponibili: valutazione limitata al valore statico."

    return {
        "value_evaluation": {"team_a_delta": round(team_a_delta, 2), "team_b_delta": round(team_b_delta, 2)},
        "live_lineup_evaluation": live_eval,
    }


def find_winwin_trades(my_roster, opponent_roster, player_pool_df, max_per_side=3, top_n=10):
    """Searches combinations up to max_per_side players per side (default 3-vs-3,
    6 total) between my_roster and opponent_roster, using the static value
    evaluation (no dynamic feed dependency). Returns up to top_n trades where
    both sides have non-negative delta, sorted by combined delta descending."""
    my_names = [p["player"] for p in my_roster]
    opp_names = [p["player"] for p in opponent_roster]

    candidates = []
    for out_size in range(1, max_per_side + 1):
        for in_size in range(1, max_per_side + 1):
            for out_combo in combinations(my_names, out_size):
                for in_combo in combinations(opp_names, in_size):
                    team_a_delta, team_b_delta, error = _value_evaluation(
                        list(out_combo), list(in_combo), player_pool_df
                    )
                    if error:
                        continue
                    if team_a_delta >= 0 and team_b_delta >= 0:
                        candidates.append({
                            "players_out": list(out_combo),
                            "players_in": list(in_combo),
                            "my_delta": round(team_a_delta, 2),
                            "opponent_delta": round(team_b_delta, 2),
                            "combined_delta": round(team_a_delta + team_b_delta, 2),
                        })

    candidates.sort(key=lambda c: c["combined_delta"], reverse=True)
    return candidates[:top_n]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_trade_analyzer.py -v`
Expected: 1 passed

- [ ] **Step 5: Add remaining tests (player not found, live eval unavailable, N-for-N, win-win detector)**

```python
# append to tests/test_trade_analyzer.py

def test_evaluate_trade_returns_error_for_unknown_player():
    result = evaluate_trade(
        team_a_roster=TEAM_A_ROSTER, players_out=["NonEsiste"],
        team_b_roster=TEAM_B_ROSTER, players_in=["DifensoreX"],
        player_pool_df=POOL, overlay=None,
    )
    assert result["error"] == "player_not_found"


def test_evaluate_trade_live_evaluation_unavailable_when_overlay_none():
    result = evaluate_trade(
        team_a_roster=TEAM_A_ROSTER, players_out=["Malen"],
        team_b_roster=TEAM_B_ROSTER, players_in=["DifensoreX"],
        player_pool_df=POOL, overlay=None,
    )
    assert result["live_lineup_evaluation"]["available"] is False
    assert "value_evaluation" in result  # value evaluation still present


def test_evaluate_trade_n_for_n_two_for_one():
    team_a_roster = [{"player": "Malen", "role": "A"}, {"player": "Krstovic", "role": "A"}]
    team_b_roster = [{"player": "DifensoreX", "role": "D"}]

    result = evaluate_trade(
        team_a_roster=team_a_roster, players_out=["Malen", "Krstovic"],
        team_b_roster=team_b_roster, players_in=["DifensoreX"],
        player_pool_df=POOL, overlay=None,
    )
    # A gives 11.0+7.0=18.0, gets 7.0 -> delta = 7.0 - 18.0 = -11.0
    assert result["value_evaluation"]["team_a_delta"] == pytest.approx(-11.0)


def test_find_winwin_trades_filters_for_non_negative_both_sides():
    my_roster = [{"player": "Krstovic", "role": "A"}]  # low value (7.0 combined)
    opponent_roster = [{"player": "DifensoreY", "role": "D"}]  # lower value (4.5 combined)

    results = find_winwin_trades(my_roster, opponent_roster, POOL, max_per_side=1, top_n=10)

    # Krstovic (7.0) for DifensoreY (4.5): my_delta = 4.5-7.0=-2.5 (negative) -> excluded
    assert results == []


def test_find_winwin_trades_returns_sorted_top_n():
    my_roster = [{"player": "DifensoreY", "role": "D"}]  # 4.5 combined
    opponent_roster = [{"player": "Malen", "role": "A"}]  # 11.0 combined

    results = find_winwin_trades(my_roster, opponent_roster, POOL, max_per_side=1, top_n=10)

    # my_delta = 11.0-4.5=6.5 (positive), opponent_delta = 4.5-11.0=-6.5 (negative) -> excluded too
    assert results == []
```

- [ ] **Step 6: Run full test file to verify all pass**

Run: `pytest tests/test_trade_analyzer.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add modules/trades/__init__.py modules/trades/trade_analyzer.py tests/test_trade_analyzer.py
git commit -m "feat(modules): add trade machine with value + live lineup evaluation and win-win detector

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Flask Routes (`app.py`)

**Files:**
- Modify: `app.py` (add imports near top, add 4 new routes near existing `/api/*` routes, e.g.
  after the `/api/undo` route which starts around line 1300 based on the existing file — search
  for the last `@app.route("/api/...")` definition and add these after it, before the
  `if __name__ == "__main__":` block or `index()` route, whichever comes last).
- Test: manual smoke test via `curl` against a running dev server (no new automated Flask test
  file — the module-level pytest suites already cover the business logic in isolation; route
  wiring is thin enough to verify manually per this task's steps).

**Interfaces:**
- Consumes: `modules.common.data_provider.get_dynamic_overlay`, `modules.lineup.lineup_solver.solve_lineup`,
  `modules.valuation.audit_engine.compute_audit`, `modules.valuation.season_tracking.load_tracking_history`,
  `modules.trades.trade_analyzer.evaluate_trade`, `modules.trades.trade_analyzer.find_winwin_trades`
  (all from Tasks 1-5). Also consumes existing `app.py` functions: `load_state()`, `load_dataset()`,
  and the existing `config.py` module (for a new `SEASON_TRACKING_JSONL` path constant).
- Produces: 4 new Flask routes consumed by Task 7's frontend JS:
  - `POST /api/lineup/solve` — body `{}` or `{"team_id": 1}` (defaults to the `is_me` team).
  - `GET /api/audit/rankings`
  - `POST /api/trades/evaluate` — body `{"team_id_a": 1, "players_out": [...], "team_id_b": 2, "players_in": [...]}` (max 6 total names combined).
  - `GET /api/trades/winwin?team_id=1`

- [ ] **Step 1: Add the `SEASON_TRACKING_JSONL` config constant**

In `config.py`, find the line defining `EWMA_STATE_JSON = os.path.join(DATA_DIR, "ewma_state.json")`
(line ~161) and add immediately after it:

```python
SEASON_TRACKING_JSONL = os.path.join(DATA_DIR, "season_tracking.jsonl")
```

- [ ] **Step 2: Add module imports to `app.py`**

Near the top of `app.py`, alongside the existing `import config` line, add:

```python
from modules.common.data_provider import get_dynamic_overlay
from modules.lineup.lineup_solver import solve_lineup
from modules.valuation.audit_engine import compute_audit
from modules.valuation.season_tracking import load_tracking_history
from modules.trades.trade_analyzer import evaluate_trade, find_winwin_trades
```

- [ ] **Step 3: Add the 4 new routes**

Add this block after the existing `/api/undo` route (or any other existing `/api/*` route — exact
placement doesn't matter functionally, just keep it grouped with other API routes for readability):

```python
@app.route("/api/lineup/solve", methods=["POST"])
def api_lineup_solve():
    data = request.json or {}
    state = load_state()
    team_id = data.get("team_id")

    if team_id is None:
        team = next((t for t in state["teams"] if t.get("is_me")), state["teams"][0] if state["teams"] else None)
    else:
        team = next((t for t in state["teams"] if t["id"] == int(team_id)), None)

    if not team:
        return jsonify({"success": False, "error": "team_not_found", "message": "Squadra non trovata"}), 404

    overlay = get_dynamic_overlay()
    result = solve_lineup(team.get("roster", []), overlay)

    status_code = 200 if result["success"] else 503
    return jsonify(result), status_code


@app.route("/api/audit/rankings", methods=["GET"])
def api_audit_rankings():
    state = load_state()
    df = load_dataset()
    tracking_history = load_tracking_history(config.SEASON_TRACKING_JSONL)

    rankings = compute_audit(state["teams"], df, tracking_history)
    return jsonify({"success": True, "rankings": rankings})


@app.route("/api/trades/evaluate", methods=["POST"])
def api_trades_evaluate():
    data = request.json or {}
    team_id_a = data.get("team_id_a")
    team_id_b = data.get("team_id_b")
    players_out = data.get("players_out", [])
    players_in = data.get("players_in", [])

    if len(players_out) + len(players_in) > 6:
        return jsonify({"success": False, "error": "too_many_players",
                         "message": "Massimo 6 giocatori totali coinvolti nello scambio"}), 400

    state = load_state()
    team_a = next((t for t in state["teams"] if t["id"] == int(team_id_a)), None)
    team_b = next((t for t in state["teams"] if t["id"] == int(team_id_b)), None)
    if not team_a or not team_b:
        return jsonify({"success": False, "error": "team_not_found", "message": "Squadra non trovata"}), 404

    df = load_dataset()
    overlay = get_dynamic_overlay()

    result = evaluate_trade(team_a.get("roster", []), players_out, team_b.get("roster", []), players_in, df, overlay)
    if "error" in result:
        return jsonify({"success": False, **result}), 400

    return jsonify({"success": True, **result})


@app.route("/api/trades/winwin", methods=["GET"])
def api_trades_winwin():
    team_id = request.args.get("team_id")
    state = load_state()

    if team_id is None:
        my_team = next((t for t in state["teams"] if t.get("is_me")), None)
    else:
        my_team = next((t for t in state["teams"] if t["id"] == int(team_id)), None)

    if not my_team:
        return jsonify({"success": False, "error": "team_not_found", "message": "Squadra non trovata"}), 404

    df = load_dataset()
    all_trades = []
    for opponent in state["teams"]:
        if opponent["id"] == my_team["id"]:
            continue
        trades = find_winwin_trades(my_team.get("roster", []), opponent.get("roster", []), df, max_per_side=3, top_n=10)
        for t in trades:
            t["opponent_team_id"] = opponent["id"]
            t["opponent_team_name"] = opponent.get("name", "")
        all_trades.extend(trades)

    all_trades.sort(key=lambda t: t["combined_delta"], reverse=True)
    return jsonify({"success": True, "trades": all_trades[:10]})
```

- [ ] **Step 4: Manual smoke test — start the dev server**

Run: `python app.py`
Expected: server starts on `http://127.0.0.1:5000` (or configured port) without import errors.

- [ ] **Step 5: Smoke test each route with curl**

```bash
curl -s -X GET http://127.0.0.1:5000/api/audit/rankings | python3 -m json.tool | head -20
curl -s -X POST http://127.0.0.1:5000/api/lineup/solve -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
curl -s -X GET "http://127.0.0.1:5000/api/trades/winwin?team_id=1" | python3 -m json.tool | head -20
```

Expected: `/api/audit/rankings` returns `{"success": true, "rankings": [...]}` (or an empty list if
no teams have rosters yet — both are valid, not errors). `/api/lineup/solve` returns either a
success payload or `{"success": false, "error": "feed_unavailable", ...}` with HTTP 503 if the
dynamic feed isn't live in the dev environment (expected, since `data/current_matchday.json` may
not exist locally — this is the correct designed behavior, not a bug). `/api/trades/winwin` returns
`{"success": true, "trades": [...]}`.

- [ ] **Step 6: Stop the dev server**

Stop the `python app.py` process (Ctrl+C or kill the process).

- [ ] **Step 7: Run the full existing test suite to check for regressions**

Run: `pytest tests/ -v`
Expected: all tests pass (pre-existing 53 from Pilastro 3 + all new tests from Tasks 1-5).

- [ ] **Step 8: Commit**

```bash
git add app.py config.py
git commit -m "feat(app): wire lineup/audit/trades modules into new Flask API routes

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: UI Tabs (`app.py` — HTML_TEMPLATE, nav, JS)

**Files:**
- Modify: `app.py` (add 3 sidebar nav buttons, 3 bottom-nav buttons, 3 `tab-content` divs, and
  supporting JS functions inside the existing `<script>` block of `HTML_TEMPLATE`).

**Interfaces:**
- Consumes: the 4 routes from Task 6 (`/api/lineup/solve`, `/api/audit/rankings`,
  `/api/trades/evaluate`, `/api/trades/winwin`).
- Produces: 3 new tabs reachable via `switchTab('lineup')`, `switchTab('audit')`,
  `switchTab('trades')` — these tab IDs must NOT collide with the existing `draft`, `targets`,
  `strategy`, `rosters`, `listone`, `ai` IDs already in use.

- [ ] **Step 1: Add sidebar nav buttons**

In `app.py`, find the existing sidebar nav button block (around line 3179-3204, ending with the
`sideNav-ai` button). Add these 3 new buttons immediately after the `sideNav-ai` button's closing
`</button>` tag, before the sidebar nav's closing `</div>`:

```html
                <button class="sidebar-nav-btn" id="sideNav-lineup" onclick="switchTab('lineup')">
                    <i class="fa-solid fa-list-check"></i> Formazione
                </button>
                <button class="sidebar-nav-btn" id="sideNav-audit" onclick="switchTab('audit')">
                    <i class="fa-solid fa-ranking-star"></i> Classifica Lega
                </button>
                <button class="sidebar-nav-btn" id="sideNav-trades" onclick="switchTab('trades')">
                    <i class="fa-solid fa-right-left"></i> Scambi
                </button>
```

- [ ] **Step 2: Add bottom-nav buttons (mobile)**

Find the existing bottom-nav block (around line 4423-4441, ending with `botNav-ai`). Add
immediately after it:

```html
        <button class="nav-item" id="botNav-lineup" onclick="switchTab('lineup')">
            <i class="fa-solid fa-list-check"></i><span>Formazione</span>
        </button>
        <button class="nav-item" id="botNav-audit" onclick="switchTab('audit')">
            <i class="fa-solid fa-ranking-star"></i><span>Classifica</span>
        </button>
        <button class="nav-item" id="botNav-trades" onclick="switchTab('trades')">
            <i class="fa-solid fa-right-left"></i><span>Scambi</span>
        </button>
```

- [ ] **Step 3: Add the 3 tab-content divs**

Find the empty `<div id="tab-strategy" class="tab-content" style="display:none;"></div>` line
(around line 3685). Add the 3 new tab-content divs immediately after it:

```html
        <div id="tab-lineup" class="tab-content" style="display:none;">
            <div class="card" style="padding:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <h3 style="margin:0;">Formazione Consigliata</h3>
                    <button class="btn btn-primary" style="width:auto; padding:8px 16px;" onclick="loadLineupSolver()">Calcola</button>
                </div>
                <div id="lineupSolverResult">
                    <p style="color:var(--text-muted);">Premi "Calcola" per generare la formazione ottimale della giornata.</p>
                </div>
            </div>
        </div>

        <div id="tab-audit" class="tab-content" style="display:none;">
            <div class="card" style="padding:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <h3 style="margin:0;">Classifica Lega Post-Asta</h3>
                    <button class="btn btn-primary" style="width:auto; padding:8px 16px;" onclick="loadAuditRankings()">Aggiorna</button>
                </div>
                <div id="auditRankingsResult">
                    <p style="color:var(--text-muted);">Premi "Aggiorna" per calcolare la classifica di lega.</p>
                </div>
            </div>
        </div>

        <div id="tab-trades" class="tab-content" style="display:none;">
            <div class="card" style="padding:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <h3 style="margin:0;">Scambi Win-Win Suggeriti</h3>
                    <button class="btn btn-primary" style="width:auto; padding:8px 16px;" onclick="loadWinWinTrades()">Cerca Scambi</button>
                </div>
                <div id="winWinTradesResult">
                    <p style="color:var(--text-muted);">Premi "Cerca Scambi" per trovare scambi vantaggiosi per entrambe le parti (max 3 vs 3 giocatori).</p>
                </div>
            </div>
        </div>
```

- [ ] **Step 4: Add the JS functions**

Find the existing `function switchTab(tabId)` function (around line 5378). Add these 3 new
functions immediately after the closing `}` of `switchTab`:

```javascript
        async function loadLineupSolver() {
            const container = document.getElementById('lineupSolverResult');
            container.innerHTML = '<p style="color:var(--text-muted);">Caricamento...</p>';
            try {
                const resp = await fetch('/api/lineup/solve', {
                    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({})
                });
                const data = await resp.json();
                if (!data.success) {
                    container.innerHTML = `<div style="color:var(--danger, #f87171); padding:10px; border:1px solid var(--border); border-radius:8px;">⚠️ ${data.message || 'Errore sconosciuto'}</div>`;
                    return;
                }
                let html = `<p><b>Modulo:</b> ${data.formation} — <b>Totale xPts:</b> ${data.total_xpts}</p>`;
                html += '<h4>Titolari</h4><ul>';
                data.starters.forEach(p => { html += `<li>${p.player} (${p.role}) — ${p.xpts} xPts</li>`; });
                html += '</ul><h4>Panchina</h4><ul>';
                data.bench.forEach(p => { html += `<li>${p.player} (${p.role}) — ${p.xpts} xPts</li>`; });
                html += '</ul>';
                container.innerHTML = html;
            } catch (e) {
                container.innerHTML = '<div style="color:var(--danger, #f87171);">Errore di rete durante il calcolo della formazione.</div>';
            }
        }

        async function loadAuditRankings() {
            const container = document.getElementById('auditRankingsResult');
            container.innerHTML = '<p style="color:var(--text-muted);">Caricamento...</p>';
            try {
                const resp = await fetch('/api/audit/rankings');
                const data = await resp.json();
                if (!data.success) {
                    container.innerHTML = '<div style="color:var(--danger, #f87171);">Errore nel calcolo della classifica.</div>';
                    return;
                }
                let html = '<table style="width:100%; border-collapse:collapse;"><tr><th>Squadra</th><th>Punti Attesi</th><th>Capitale a Rischio</th><th>Badge</th></tr>';
                data.rankings.forEach(r => {
                    html += `<tr><td>${r.team_name}</td><td>${r.expected_points}</td><td>${r.risk_capital_cr} cr (${r.risk_capital_pct}%)</td><td>${r.badges.join(', ')}</td></tr>`;
                });
                html += '</table>';
                container.innerHTML = html;
            } catch (e) {
                container.innerHTML = '<div style="color:var(--danger, #f87171);">Errore di rete durante il calcolo della classifica.</div>';
            }
        }

        async function loadWinWinTrades() {
            const container = document.getElementById('winWinTradesResult');
            container.innerHTML = '<p style="color:var(--text-muted);">Ricerca in corso...</p>';
            try {
                const resp = await fetch('/api/trades/winwin');
                const data = await resp.json();
                if (!data.success || data.trades.length === 0) {
                    container.innerHTML = '<p style="color:var(--text-muted);">Nessuno scambio vantaggioso trovato al momento.</p>';
                    return;
                }
                let html = '<ul>';
                data.trades.forEach(t => {
                    html += `<li>Cedi [${t.players_out.join(', ')}] a ${t.opponent_team_name} per [${t.players_in.join(', ')}] — Tuo delta: ${t.my_delta}, Suo delta: ${t.opponent_delta}</li>`;
                });
                html += '</ul>';
                container.innerHTML = html;
            } catch (e) {
                container.innerHTML = '<div style="color:var(--danger, #f87171);">Errore di rete durante la ricerca degli scambi.</div>';
            }
        }
```

- [ ] **Step 5: Manual verification in browser**

Run: `python app.py`, open `http://127.0.0.1:5000` in a browser.
Expected: 3 new nav buttons ("Formazione", "Classifica Lega", "Scambi") appear in the sidebar (and
bottom nav on mobile viewport), clicking each switches to the corresponding tab without breaking
any existing tab, and each "Calcola"/"Aggiorna"/"Cerca Scambi" button triggers its fetch call
(check via browser dev tools Network tab) and renders a result or an error message without a JS
console exception.

- [ ] **Step 6: Stop the dev server**

Stop the `python app.py` process.

- [ ] **Step 7: Run the full test suite one final time**

Run: `pytest tests/ -v`
Expected: all tests pass (no regressions from the HTML/JS changes, since they're untested by
pytest but must not have broken any Python-level test collection).

- [ ] **Step 8: Commit**

```bash
git add app.py
git commit -m "feat(ui): add Formazione/Classifica Lega/Scambi tabs for Pilastro 4 modules

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Final Verification

- [ ] Run `pytest tests/ -v` one more time from repo root and confirm 0 failures.
- [ ] Run `git log --oneline -8` and confirm all 7 task commits are present in order.
- [ ] Manually start `python app.py` and click through all 3 new tabs once more to confirm no
      regressions in the existing 6 tabs (spot-check `draft` and `ai` tabs still load correctly).
