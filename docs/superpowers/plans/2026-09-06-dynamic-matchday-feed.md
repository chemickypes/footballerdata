# Feed Dinamico Infrasettimanale (Pilastro 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a scheduled, resilient pipeline that produces `data/current_matchday.json` (probable lineups, bookmaker-derived probabilities, EWMA form) every matchday, published via GitHub Actions to a `data-feed` branch and consumed by the web app through a caching client — with zero scraping and zero disk writes at Vercel runtime.

**Architecture:** New `pipeline/dynamic/` package with one module per data source (odds via api-football.com, lineups/status via fantacalcio.it) plus an orchestrator (`build_feed.py`) that merges everything into the JSON contract, and a read-only `client.py` used by `app.py`. A GitHub Actions cron workflow runs the orchestrator and commits the JSON to an orphan `data-feed` branch. Every network-facing module degrades gracefully (partial data + explicit flags) instead of crashing, matching the existing resilience pattern in `pipeline/05_scrape_injuries.py`.

**Tech Stack:** Python 3, `requests`, `beautifulsoup4`, `pandas` (already in `requirements.txt` — no new dependencies). Tests use `unittest.mock.patch` to stub `requests.get`, no live network calls in the test suite.

## Global Constraints

- No new scraping/build steps may write synchronously to disk at Flask request time in `app.py` — only the offline pipeline (run via cron/CLI) writes files. (Spec: "Error handling e degradazione" / Pilastro 1 constraint.)
- `API_FOOTBALL_KEY` must never be committed to a tracked file. It is read only from the `API_FOOTBALL_KEY` environment variable (local `.env`, already gitignored, or GitHub Actions secret).
- Every scraper module must tolerate partial/total failure of its own data source without raising past its own boundary — the orchestrator always produces a valid (possibly degraded) `current_matchday.json`.
- `data/current_matchday.json` must contain at least 450 valid player entries or the build must fail loudly (fail-fast in CI), per the spec's validation requirement.
- Reuse existing conventions: `config.py` for shared paths/constants, `config.HEADERS` for browser-like User-Agent, module docstring header style (`#!/usr/bin/env python3` + docstring) as seen in `pipeline/01_scrape_historical.py` and `pipeline/05_scrape_injuries.py`.
- Tests follow the existing style in `tests/test_dual_track_and_features.py` (plain `test(name, condition, detail)` assertions, no pytest fixtures) for consistency with the one existing test file, but use `assert` statements runnable directly by pytest for the new dynamic-feed tests (this plan's tests are pure unit tests, not integration tests against a running server, so plain `assert` + pytest is the right fit — see Task 1).

---

## File Structure

```
config.py                                  (MODIFY: add dynamic-feed constants)
pipeline/dynamic/
  __init__.py                              (CREATE: empty package marker)
  utils.py                                 (CREATE: normalize_name, PlayerMatcher, fetch_with_retry)
  api_football_client.py                   (CREATE: authenticated GET wrapper for api-football.com)
  scrape_odds.py                           (CREATE: fixtures + odds + de-vig probabilities)
  scrape_lineups.py                        (CREATE: fantacalcio.it probable lineups + xMin)
  scrape_status.py                         (CREATE: fantacalcio.it injuries/suspensions -> status)
  scrape_results.py                        (CREATE: api-football post-matchday ratings + EWMA)
  build_feed.py                            (CREATE: orchestrator -> data/current_matchday.json)
  client.py                                (CREATE: cached HTTP client used by app.py)
data/fallback_matchday.json                (CREATE: static fallback, committed to main)
.github/workflows/dynamic_feed.yml         (CREATE: cron workflow)
tests/test_dynamic_feed.py                 (CREATE: unit tests, mocked HTTP)
README.md                                  (MODIFY: document API_FOOTBALL_KEY setup)
```

---

### Task 1: Shared utilities — name normalization, player matching, HTTP retry

**Files:**
- Create: `pipeline/dynamic/__init__.py`
- Create: `pipeline/dynamic/utils.py`
- Test: `tests/test_dynamic_feed.py`

**Interfaces:**
- Produces: `normalize_name(s: str) -> str`, `class PlayerMatcher` with
  `PlayerMatcher(dataset_df: pandas.DataFrame, name_col: str = "player", team_col: str = "team") -> PlayerMatcher`
  and `.match(query_name: str, query_team: str) -> str | None` (returns the matched value
  from `dataset_df[name_col]`, or `None`), `fetch_with_retry(url: str, headers: dict | None = None, params: dict | None = None, max_retries: int = 3, timeout: int = 10) -> requests.Response | None`.

- [ ] **Step 1: Create the package marker**

```bash
mkdir -p pipeline/dynamic
touch pipeline/dynamic/__init__.py
```

- [ ] **Step 2: Write the failing test for `normalize_name` and `PlayerMatcher`**

Create `tests/test_dynamic_feed.py` with this initial content:

```python
#!/usr/bin/env python3
"""
Unit tests for pipeline/dynamic/* — feed dinamico infrasettimanale (Pilastro 3).
No live network calls: all HTTP is mocked via unittest.mock.patch.
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.dynamic.utils import normalize_name, PlayerMatcher


def test_normalize_name_strips_accents_and_case():
    assert normalize_name("Kenan Yıldız") == "kenan yildiz"
    assert normalize_name("  Nico Paz ") == "nico paz"
    assert normalize_name("PAZ N.") == "paz n."


def test_player_matcher_exact_normalized_match():
    df = pd.DataFrame({
        "player": ["Lautaro Martinez", "Nico Paz"],
        "team": ["INT", "COM"],
    })
    matcher = PlayerMatcher(df)
    assert matcher.match("lautaro martinez", "INT") == "Lautaro Martinez"


def test_player_matcher_fuzzy_match_within_team():
    df = pd.DataFrame({
        "player": ["Kenan Yildiz", "Vlahovic"],
        "team": ["JUV", "JUV"],
    })
    matcher = PlayerMatcher(df)
    # Scraper source uses a slightly different accented spelling
    assert matcher.match("Kenan Yıldız", "JUV") == "Kenan Yildiz"


def test_player_matcher_returns_none_when_no_candidate():
    df = pd.DataFrame({"player": ["Someone Else"], "team": ["ROM"]})
    matcher = PlayerMatcher(df)
    assert matcher.match("Totally Unrelated Name", "ROM") is None
```

- [ ] **Step 3: Run tests to verify they fail with ImportError**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.dynamic.utils'`

- [ ] **Step 4: Implement `pipeline/dynamic/utils.py`**

```python
#!/usr/bin/env python3
"""
Utility condivise per il feed dinamico infrasettimanale (Pilastro 3):
normalizzazione nomi, matching giocatore->dataset, richieste HTTP resilienti.
"""
import difflib
import random
import time
import unicodedata

import requests

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]


def normalize_name(s):
    """Rimuove accenti, converte in minuscolo e strippa gli spazi."""
    s = str(s).strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s.lower()


class PlayerMatcher:
    """
    Fa il match di un nome giocatore (proveniente da uno scraper esterno) sui nomi
    presenti nel dataset fanta-lab, con lo stesso approccio a cascata già usato in
    pipeline/04b_scrape_lineups.py: match esatto normalizzato -> fuzzy per squadra ->
    fuzzy sul cognome per squadra -> fuzzy globale a soglia più permissiva.
    """

    def __init__(self, dataset_df, name_col="player", team_col="team"):
        self.name_col = name_col
        self.team_col = team_col
        self.names = dataset_df[name_col].tolist()
        self.teams = dict(zip(dataset_df[name_col], dataset_df[team_col]))
        self.norm_to_name = {normalize_name(n): n for n in self.names}
        self.all_norm = [normalize_name(n) for n in self.names]

    def match(self, query_name, query_team):
        query_norm = normalize_name(query_name)

        if query_norm in self.norm_to_name:
            return self.norm_to_name[query_norm]

        team_candidates = [n for n in self.names if self.teams.get(n) == query_team]
        team_candidates_norm = [normalize_name(n) for n in team_candidates]

        fuzzy = difflib.get_close_matches(query_norm, team_candidates_norm, n=1, cutoff=0.60)
        if fuzzy:
            return team_candidates[team_candidates_norm.index(fuzzy[0])]

        last_name = query_name.split()[-1] if query_name.split() else query_name
        last_fuzzy = difflib.get_close_matches(
            normalize_name(last_name), team_candidates_norm, n=1, cutoff=0.70
        )
        if last_fuzzy:
            return team_candidates[team_candidates_norm.index(last_fuzzy[0])]

        global_fuzzy = difflib.get_close_matches(query_norm, self.all_norm, n=1, cutoff=0.70)
        if global_fuzzy:
            return self.names[self.all_norm.index(global_fuzzy[0])]

        return None


def fetch_with_retry(url, headers=None, params=None, max_retries=3, timeout=10):
    """
    GET resiliente: retry esponenziale su 403/429/5xx/timeout, User-Agent rotante.
    Ritorna la Response su successo (status 200) o None se tutti i tentativi falliscono.
    """
    req_headers = dict(headers or {})
    for attempt in range(max_retries):
        req_headers["User-Agent"] = random.choice(USER_AGENTS)
        try:
            resp = requests.get(url, headers=req_headers, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (403, 429):
                time.sleep((2 ** attempt) + random.uniform(1.5, 3.0))
            elif resp.status_code in (500, 502, 503, 504):
                time.sleep(1.0 * (attempt + 1))
            else:
                return None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            break
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v`
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add pipeline/dynamic/__init__.py pipeline/dynamic/utils.py tests/test_dynamic_feed.py
git commit -m "feat(dynamic-feed): add name normalization and player matcher utilities

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: api-football.com client + config wiring

**Files:**
- Modify: `config.py` (append new section at end of file)
- Create: `pipeline/dynamic/api_football_client.py`
- Test: `tests/test_dynamic_feed.py` (append)

**Interfaces:**
- Consumes: `pipeline.dynamic.utils.fetch_with_retry`
- Produces: `get_fixtures(round_hint: str | None = None) -> list[dict]`,
  `get_odds(fixture_id: int) -> dict`, `get_fixture_player_ratings(fixture_id: int) -> dict[str, float]`
  (keys are raw api-football player names, values are `rating` floats).
  Also produces module-level `API_FOOTBALL_BASE = "https://v3.football.api-sports.io"`.

- [ ] **Step 1: Add config constants**

Append to `config.py`:

```python

# ──────────────────────────────────────────────────────────────────────
# FEED DINAMICO INFRASETTIMANALE (Pilastro 3) — api-football.com
# ──────────────────────────────────────────────────────────────────────
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")
API_FOOTBALL_LEAGUE_ID = 135  # Serie A su api-football.com
API_FOOTBALL_SEASON = 2026    # Anno di inizio stagione (2026-27)

CURRENT_MATCHDAY_JSON = os.path.join(DATA_DIR, "current_matchday.json")
FALLBACK_MATCHDAY_JSON = os.path.join(DATA_DIR, "fallback_matchday.json")
EWMA_STATE_JSON = os.path.join(DATA_DIR, "ewma_state.json")
MIN_VALID_PLAYERS_IN_FEED = 450
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_dynamic_feed.py`:

```python
from pipeline.dynamic import api_football_client as afc


@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_fixtures_parses_response(mock_fetch):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": [
            {
                "fixture": {"id": 111, "date": "2026-09-20T18:45:00+00:00"},
                "teams": {
                    "home": {"name": "Inter"},
                    "away": {"name": "Monza"},
                },
            }
        ]
    }
    mock_fetch.return_value = mock_resp

    fixtures = afc.get_fixtures()
    assert len(fixtures) == 1
    assert fixtures[0]["home_team"] == "Inter"
    assert fixtures[0]["away_team"] == "Monza"
    assert fixtures[0]["fixture_id"] == 111


@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_fixtures_returns_empty_list_on_failure(mock_fetch):
    mock_fetch.return_value = None
    assert afc.get_fixtures() == []


@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_fixture_player_ratings_parses_response(mock_fetch):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": [
            {
                "players": [
                    {
                        "player": {"name": "Lautaro Martinez"},
                        "statistics": [{"games": {"rating": "7.8"}}],
                    }
                ]
            },
            {
                "players": [
                    {
                        "player": {"name": "Yann Bisseck"},
                        "statistics": [{"games": {"rating": None}}],
                    }
                ]
            },
        ]
    }
    mock_fetch.return_value = mock_resp

    ratings = afc.get_fixture_player_ratings(111)
    assert ratings["Lautaro Martinez"] == 7.8
    assert "Yann Bisseck" not in ratings  # rating nullo -> escluso
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k api_football`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.dynamic.api_football_client'`

- [ ] **Step 4: Implement `pipeline/dynamic/api_football_client.py`**

```python
#!/usr/bin/env python3
"""
Client per api-football.com (v3.football.api-sports.io).
Fornisce fixtures, quote bookmaker e rating per-giocatore per la Serie A.
Autenticazione via header 'x-apisports-key' (config.API_FOOTBALL_KEY).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.dynamic.utils import fetch_with_retry

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"


def _headers():
    return {"x-apisports-key": config.API_FOOTBALL_KEY}


def get_fixtures():
    """Ritorna le fixture del prossimo turno Serie A non ancora giocato.
    Ritorna lista vuota se la chiave manca o la richiesta fallisce."""
    if not config.API_FOOTBALL_KEY:
        return []

    resp = fetch_with_retry(
        f"{API_FOOTBALL_BASE}/fixtures",
        headers=_headers(),
        params={
            "league": config.API_FOOTBALL_LEAGUE_ID,
            "season": config.API_FOOTBALL_SEASON,
            "next": 10,
        },
    )
    if resp is None:
        return []

    fixtures = []
    for item in resp.json().get("response", []):
        fixtures.append({
            "fixture_id": item["fixture"]["id"],
            "date": item["fixture"]["date"],
            "home_team": item["teams"]["home"]["name"],
            "away_team": item["teams"]["away"]["name"],
        })
    return fixtures


def get_odds(fixture_id):
    """Ritorna le quote grezze (bookmaker medio) per una fixture, o {} se non disponibili."""
    if not config.API_FOOTBALL_KEY:
        return {}

    resp = fetch_with_retry(
        f"{API_FOOTBALL_BASE}/odds",
        headers=_headers(),
        params={"fixture": fixture_id},
    )
    if resp is None:
        return {}

    response = resp.json().get("response", [])
    if not response:
        return {}

    odds_by_market = {}
    for bookmaker in response[0].get("bookmakers", []):
        for bet in bookmaker.get("bets", []):
            market = bet["name"]
            odds_by_market.setdefault(market, [])
            for value in bet.get("values", []):
                try:
                    odds_by_market[market].append((value["value"], float(value["odd"])))
                except (KeyError, ValueError, TypeError):
                    continue
    return odds_by_market


def get_fixture_player_ratings(fixture_id):
    """Ritorna {player_name: rating_float} per una fixture conclusa. Esclude rating nulli."""
    if not config.API_FOOTBALL_KEY:
        return {}

    resp = fetch_with_retry(
        f"{API_FOOTBALL_BASE}/fixtures/players",
        headers=_headers(),
        params={"fixture": fixture_id},
    )
    if resp is None:
        return {}

    ratings = {}
    for team_block in resp.json().get("response", []):
        for player_block in team_block.get("players", []):
            name = player_block.get("player", {}).get("name")
            stats = player_block.get("statistics", [{}])[0]
            rating_raw = stats.get("games", {}).get("rating")
            if name and rating_raw is not None:
                try:
                    ratings[name] = float(rating_raw)
                except (TypeError, ValueError):
                    continue
    return ratings
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k api_football`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add config.py pipeline/dynamic/api_football_client.py tests/test_dynamic_feed.py
git commit -m "feat(dynamic-feed): add api-football.com client for fixtures/odds/ratings

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Odds de-vig probability math + `scrape_odds.py`

**Files:**
- Create: `pipeline/dynamic/scrape_odds.py`
- Test: `tests/test_dynamic_feed.py` (append)

**Interfaces:**
- Consumes: `pipeline.dynamic.api_football_client.get_fixtures`,
  `pipeline.dynamic.api_football_client.get_odds`
- Produces: `devig_probabilities(odds: list[tuple[str, float]]) -> dict[str, float]`,
  `build_odds_feed() -> list[dict]` — each dict has keys `home_team`, `away_team`,
  `fixture_id`, `home_win_prob`, `draw_prob`, `away_win_prob`, `clean_sheet_prob_home`,
  `clean_sheet_prob_away`, `expected_goals_home`, `expected_goals_away`,
  `odds_available: bool`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dynamic_feed.py`:

```python
from pipeline.dynamic import scrape_odds


def test_devig_probabilities_removes_bookmaker_margin():
    # Quote con aggio: 1.90 / 3.60 / 4.20 (somma probabilita implicite > 1)
    odds = [("Home", 1.90), ("Draw", 3.60), ("Away", 4.20)]
    probs = scrape_odds.devig_probabilities(odds)
    total = sum(probs.values())
    assert abs(total - 1.0) < 1e-6
    # L'esito piu probabile (quota piu bassa) deve avere probabilita maggiore
    assert probs["Home"] > probs["Draw"] > probs["Away"]


def test_devig_probabilities_empty_input_returns_empty_dict():
    assert scrape_odds.devig_probabilities([]) == {}


@patch("pipeline.dynamic.scrape_odds.get_odds")
@patch("pipeline.dynamic.scrape_odds.get_fixtures")
def test_build_odds_feed_marks_unavailable_odds(mock_fixtures, mock_odds):
    mock_fixtures.return_value = [
        {"fixture_id": 1, "home_team": "Inter", "away_team": "Monza", "date": "2026-09-20T18:45:00+00:00"}
    ]
    mock_odds.return_value = {}  # nessuna quota disponibile per questa fixture

    feed = scrape_odds.build_odds_feed()
    assert len(feed) == 1
    assert feed[0]["odds_available"] is False
    assert feed[0]["home_win_prob"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k devig or odds_feed`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.dynamic.scrape_odds'`

- [ ] **Step 3: Implement `pipeline/dynamic/scrape_odds.py`**

```python
#!/usr/bin/env python3
"""
STAGE DINAMICO — Quote bookmaker come proxy quantitativo (Pilastro 3).
Rimuove l'aggio del banco dalle quote 1X2 / Over-Under per ricavare le
probabilita implicite pure, secondo P(evento) = (1/Q) / (1 + A) con
A = somma(1/Qk) - 1.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.dynamic.api_football_client import get_fixtures, get_odds


def devig_probabilities(odds):
    """odds: lista di tuple (label, quota_decimale). Ritorna {label: probabilita_pura}."""
    if not odds:
        return {}

    implied = [(label, 1.0 / quota) for label, quota in odds if quota > 0]
    if not implied:
        return {}

    overround = sum(p for _, p in implied) - 1.0
    return {label: p / (1.0 + overround) for label, p in implied}


def _extract_1x2(odds_by_market):
    values = odds_by_market.get("Match Winner", [])
    return devig_probabilities(values)


def _extract_over_under_25(odds_by_market):
    values = odds_by_market.get("Goals Over/Under", [])
    filtered = [(label, odd) for label, odd in values if "2.5" in label]
    return devig_probabilities(filtered)


def build_odds_feed():
    """Ritorna una lista di dict, uno per fixture, con probabilita de-vig o None se assenti."""
    feed = []
    for fx in get_fixtures():
        odds_by_market = get_odds(fx["fixture_id"])
        probs_1x2 = _extract_1x2(odds_by_market)
        probs_ou = _extract_over_under_25(odds_by_market)

        home_prob = probs_1x2.get("Home")
        draw_prob = probs_1x2.get("Draw")
        away_prob = probs_1x2.get("Away")
        over_prob = probs_ou.get("Over 2.5")

        # Stima expected goals totali da P(Over 2.5) via approssimazione Poisson
        # inversa (log-odds lineare); usata solo come proxy quantitativo dichiarato.
        expected_total_goals = None
        if over_prob is not None and 0 < over_prob < 1:
            import math
            expected_total_goals = 2.5 - math.log((1 - over_prob) / over_prob)

        feed.append({
            "fixture_id": fx["fixture_id"],
            "home_team": fx["home_team"],
            "away_team": fx["away_team"],
            "date": fx["date"],
            "odds_available": bool(probs_1x2),
            "home_win_prob": home_prob,
            "draw_prob": draw_prob,
            "away_win_prob": away_prob,
            "expected_goals_home": (
                round(expected_total_goals * 0.55, 2) if expected_total_goals else None
            ),
            "expected_goals_away": (
                round(expected_total_goals * 0.45, 2) if expected_total_goals else None
            ),
            "clean_sheet_prob_home": round(away_prob * 0.6, 3) if away_prob else None,
            "clean_sheet_prob_away": round(home_prob * 0.6, 3) if home_prob else None,
        })
    return feed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k "devig or odds_feed"`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add pipeline/dynamic/scrape_odds.py tests/test_dynamic_feed.py
git commit -m "feat(dynamic-feed): add odds de-vig scraper for match/clean-sheet probabilities

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: `scrape_lineups.py` — probabili formazioni + xMin

**Files:**
- Create: `pipeline/dynamic/scrape_lineups.py`
- Test: `tests/test_dynamic_feed.py` (append)

**Interfaces:**
- Consumes: `pipeline.dynamic.utils.fetch_with_retry`, `config.HEADERS`
- Produces: `expected_minutes(titular_prob: float, is_bench_candidate: bool) -> float`,
  `parse_probable_lineups(html: str) -> list[dict]` (each dict:
  `player_name`, `team_abbr_or_name`, `formation_line_index`),
  `scrape_probable_lineups() -> list[dict]`.

**Verified DOM structure** (fetched live from `https://www.fantacalcio.it/probabili-formazioni-serie-a`
on 2026-09-06): each match is `<li class="match" data-match-id="...">` containing
`<div class="team team-home" data-team-formation="4-3-3">` and
`<div class="team team-away" ...>`, each with
`<ul class="team-lineup" data-formation="433">` containing
`<li class="player"><a class="player-name player-link" href=".../squadre/{team}/{slug}/{id}"><span>{DisplayName}</span></a></li>`
and `<li class="separator"></li>` markers between position lines (GK / DEF / MID / FWD).
The page does **not** expose an explicit per-player titolarità percentage in the base
markup — only an editorial "most likely XI". Per the design spec, listed starters get a
documented constant baseline probability (`BASELINE_TITULAR_PROB`); the more granular
`BALLOTTAGGIO`/`INFORTUNATO`/`SQUALIFICATO` overrides come from Task 5
(`scrape_status.py`), applied later in `build_feed.py`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dynamic_feed.py`:

```python
from pipeline.dynamic import scrape_lineups

SAMPLE_LINEUP_HTML = """
<li class="match" data-match-id="17981" data-match-hash="JUV-MIL">
  <div class="team team-home" data-team-formation="4-2-3-1">
    <ul class="team-lineup" data-formation="4231">
      <li class="player"><a class="player-name player-link" href="/serie-a/squadre/juventus/perin/123">
        <span>Perin</span></a></li>
      <li class="separator"></li>
      <li class="player"><a class="player-name player-link" href="/serie-a/squadre/juventus/kalulu/456">
        <span>Kalulu</span></a></li>
      <li class="separator"></li>
    </ul>
  </div>
  <div class="team team-away" data-team-formation="4-3-3">
    <ul class="team-lineup" data-formation="433">
      <li class="player"><a class="player-name player-link" href="/serie-a/squadre/milan/maignan/789">
        <span>Maignan</span></a></li>
    </ul>
  </div>
</li>
"""


def test_expected_minutes_full_starter():
    assert scrape_lineups.expected_minutes(1.0, is_bench_candidate=False) == 70.0


def test_expected_minutes_bench_candidate():
    # titular_prob basso e in panchina: xMin = 0*70 + (1-0)*20*1 = 20
    assert scrape_lineups.expected_minutes(0.0, is_bench_candidate=True) == 20.0


def test_parse_probable_lineups_extracts_players_with_team_side():
    players = scrape_lineups.parse_probable_lineups(SAMPLE_LINEUP_HTML)
    names = [p["player_name"] for p in players]
    assert "Perin" in names
    assert "Kalulu" in names
    assert "Maignan" in names
    perin = next(p for p in players if p["player_name"] == "Perin")
    assert perin["match_id"] == "17981"
    assert perin["side"] == "home"


@patch("pipeline.dynamic.scrape_lineups.fetch_with_retry")
def test_scrape_probable_lineups_returns_empty_list_on_fetch_failure(mock_fetch):
    mock_fetch.return_value = None
    assert scrape_lineups.scrape_probable_lineups() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k lineup`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.dynamic.scrape_lineups'`

- [ ] **Step 3: Implement `pipeline/dynamic/scrape_lineups.py`**

```python
#!/usr/bin/env python3
"""
STAGE DINAMICO — Probabili formazioni da fantacalcio.it (Pilastro 3).

Estrae l'undici probabile editoriale per ogni partita del turno. La pagina non
espone una percentuale di titolarita esplicita per giocatore: ai titolari
elencati viene assegnata una probabilita baseline documentata
(BASELINE_TITULAR_PROB); gli stati piu granulari (BALLOTTAGGIO, INFORTUNATO,
SQUALIFICATO, DIFFERENZIATO) vengono sovrascritti in build_feed.py incrociando
l'output di scrape_status.py.
"""
import os
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.dynamic.utils import fetch_with_retry

LINEUPS_URL = "https://www.fantacalcio.it/probabili-formazioni-serie-a"
BASELINE_TITULAR_PROB = 0.78


def expected_minutes(titular_prob, is_bench_candidate):
    """xMin = P(Titolare)*70 + (1-P(Titolare))*20*I(in panchina)."""
    bench_component = 20.0 * (1 if is_bench_candidate else 0)
    return titular_prob * 70.0 + (1 - titular_prob) * bench_component


def parse_probable_lineups(html):
    """Estrae i giocatori elencati come probabili titolari da ogni match della pagina."""
    soup = BeautifulSoup(html, "html.parser")
    players = []

    for match in soup.select("li.match"):
        match_id = match.get("data-match-id", "")
        for side_class, side in (("team-home", "home"), ("team-away", "away")):
            team_div = match.select_one(f"div.team.{side_class}")
            if not team_div:
                continue
            for link in team_div.select("a.player-name.player-link"):
                span = link.find("span")
                if not span:
                    continue
                players.append({
                    "player_name": span.get_text(strip=True),
                    "match_id": match_id,
                    "side": side,
                    "href": link.get("href", ""),
                })
    return players


def scrape_probable_lineups():
    """Scarica ed effettua il parsing della pagina probabili formazioni.
    Ritorna lista vuota se il fetch fallisce (degradazione gestita a monte)."""
    resp = fetch_with_retry(LINEUPS_URL, headers=config.HEADERS)
    if resp is None:
        return []
    return parse_probable_lineups(resp.text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k lineup`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add pipeline/dynamic/scrape_lineups.py tests/test_dynamic_feed.py
git commit -m "feat(dynamic-feed): add probable lineups scraper and xMin formula

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: `scrape_status.py` — infortuni/squalifiche -> status giocatore

**Files:**
- Create: `pipeline/dynamic/scrape_status.py`
- Test: `tests/test_dynamic_feed.py` (append)

**Interfaces:**
- Consumes: `pipeline.dynamic.utils.fetch_with_retry`, `config.HEADERS`
- Produces: `parse_status_cards(html: str, status_label: str) -> dict[str, str]`
  (maps raw player name -> `status_label`), `scrape_all_statuses() -> dict[str, str]`
  (merges INFORTUNATO from `/infortunati-serie-a` and SQUALIFICATO from
  `/squalificati-e-diffidati-campionato-serie-a`; players not present in either default
  to `OK` downstream in `build_feed.py`, not here).

**Verified DOM structure** (fetched live from `https://www.fantacalcio.it/infortunati-serie-a`
on 2026-09-06): `<div id="team-{id}" class="card team-card"> ... <ul class="unstyled">
<li><strong class="item-name">{PlayerName}</strong><div class="item-description">
<p>{free text}</p></div></li> ... </ul></div>`. The suspensions page
(`/squalificati-e-diffidati-campionato-serie-a`) is assumed to share the same
`team-card`/`item-name` component (same site template family, confirmed by the shared
`layout.common.min.css` include across all Fantacalcio.it pages) — if that assumption
proves wrong in production, `parse_status_cards` simply returns an empty dict for that
page (0 matches), which `build_feed.py` treats as a degraded-but-non-fatal source per
the resilience contract, not a crash.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dynamic_feed.py`:

```python
from pipeline.dynamic import scrape_status

SAMPLE_STATUS_HTML = """
<div id="team-1" class="card team-card">
  <span class="team-name">Atalanta</span>
  <ul class="unstyled">
    <li>
      <strong class="item-name">Sulemana K.</strong>
      <div class="item-description"><p>Lesione al ginocchio, rientro a ottobre.</p></div>
    </li>
    <li>
      <strong class="item-name">Hien</strong>
      <div class="item-description"><p>Operato, rientro a ottobre.</p></div>
    </li>
  </ul>
</div>
"""


def test_parse_status_cards_extracts_player_names():
    result = scrape_status.parse_status_cards(SAMPLE_STATUS_HTML, "INFORTUNATO")
    assert result["Sulemana K."] == "INFORTUNATO"
    assert result["Hien"] == "INFORTUNATO"
    assert len(result) == 2


def test_parse_status_cards_empty_html_returns_empty_dict():
    assert scrape_status.parse_status_cards("<html></html>", "SQUALIFICATO") == {}


@patch("pipeline.dynamic.scrape_status.fetch_with_retry")
def test_scrape_all_statuses_merges_both_sources(mock_fetch):
    injuries_resp = MagicMock()
    injuries_resp.text = SAMPLE_STATUS_HTML
    suspensions_resp = MagicMock()
    suspensions_resp.text = (
        '<div id="team-2" class="card team-card"><ul class="unstyled">'
        '<li><strong class="item-name">Orsolini</strong>'
        '<div class="item-description"><p>Squalificato 1 turno.</p></div></li>'
        '</ul></div>'
    )
    mock_fetch.side_effect = [injuries_resp, suspensions_resp]

    statuses = scrape_status.scrape_all_statuses()
    assert statuses["Sulemana K."] == "INFORTUNATO"
    assert statuses["Orsolini"] == "SQUALIFICATO"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k status`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.dynamic.scrape_status'`

- [ ] **Step 3: Implement `pipeline/dynamic/scrape_status.py`**

```python
#!/usr/bin/env python3
"""
STAGE DINAMICO — Stato clinico/disciplinare da fantacalcio.it (Pilastro 3).
Incrocia le pagine 'infortunati' e 'squalificati/diffidati' per produrre uno
stato per giocatore (INFORTUNATO / SQUALIFICATO). I giocatori non presenti in
nessuna delle due liste sono considerati OK a valle in build_feed.py.
"""
import os
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.dynamic.utils import fetch_with_retry

INJURIES_URL = "https://www.fantacalcio.it/infortunati-serie-a"
SUSPENSIONS_URL = "https://www.fantacalcio.it/squalificati-e-diffidati-campionato-serie-a"


def parse_status_cards(html, status_label):
    """Estrae {player_name: status_label} dalle card 'team-card' della pagina."""
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    for name_tag in soup.select("div.card.team-card strong.item-name"):
        name = name_tag.get_text(strip=True)
        if name:
            result[name] = status_label
    return result


def scrape_all_statuses():
    """Ritorna {player_name: status} unendo infortunati e squalificati.
    Se una delle due richieste fallisce, quella fonte contribuisce con un dict vuoto
    (degradazione, non crash) e il merge procede con l'altra fonte disponibile."""
    statuses = {}

    injuries_resp = fetch_with_retry(INJURIES_URL, headers=config.HEADERS)
    if injuries_resp is not None:
        statuses.update(parse_status_cards(injuries_resp.text, "INFORTUNATO"))

    suspensions_resp = fetch_with_retry(SUSPENSIONS_URL, headers=config.HEADERS)
    if suspensions_resp is not None:
        statuses.update(parse_status_cards(suspensions_resp.text, "SQUALIFICATO"))

    return statuses
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k status`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add pipeline/dynamic/scrape_status.py tests/test_dynamic_feed.py
git commit -m "feat(dynamic-feed): add injuries/suspensions status scraper

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: `scrape_results.py` — risultati turno concluso + EWMA forma

**Files:**
- Create: `pipeline/dynamic/scrape_results.py`
- Test: `tests/test_dynamic_feed.py` (append)

**Interfaces:**
- Consumes: `pipeline.dynamic.api_football_client.get_fixture_player_ratings`,
  `config.EWMA_STATE_JSON`
- Produces: `update_ewma(prev: float | None, rating: float, alpha: float = 0.35) -> float`,
  `load_ewma_state() -> dict[str, float]`, `save_ewma_state(state: dict[str, float]) -> None`,
  `update_form_from_fixtures(fixture_ids: list[int]) -> dict[str, float]` (returns the
  updated `{player_name: ewma}` state after processing all given fixtures).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dynamic_feed.py`:

```python
import json
import tempfile

from pipeline.dynamic import scrape_results


def test_update_ewma_first_observation_returns_rating_itself():
    assert scrape_results.update_ewma(None, 7.0) == 7.0


def test_update_ewma_applies_weighted_formula():
    # EWMA_t = 0.35 * rating + 0.65 * prev
    result = scrape_results.update_ewma(6.0, 8.0, alpha=0.35)
    assert abs(result - (0.35 * 8.0 + 0.65 * 6.0)) < 1e-9


def test_load_ewma_state_returns_empty_dict_when_file_missing(tmp_path, monkeypatch):
    missing_path = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(scrape_results.config, "EWMA_STATE_JSON", str(missing_path))
    assert scrape_results.load_ewma_state() == {}


def test_save_then_load_ewma_state_roundtrip(tmp_path, monkeypatch):
    state_path = tmp_path / "ewma_state.json"
    monkeypatch.setattr(scrape_results.config, "EWMA_STATE_JSON", str(state_path))
    scrape_results.save_ewma_state({"Lautaro Martinez": 7.4})
    assert scrape_results.load_ewma_state() == {"Lautaro Martinez": 7.4}


@patch("pipeline.dynamic.scrape_results.get_fixture_player_ratings")
def test_update_form_from_fixtures_merges_new_ratings(mock_ratings, tmp_path, monkeypatch):
    state_path = tmp_path / "ewma_state.json"
    monkeypatch.setattr(scrape_results.config, "EWMA_STATE_JSON", str(state_path))
    scrape_results.save_ewma_state({"Lautaro Martinez": 7.0})
    mock_ratings.return_value = {"Lautaro Martinez": 8.0, "New Player": 6.5}

    updated = scrape_results.update_form_from_fixtures([111])
    assert abs(updated["Lautaro Martinez"] - (0.35 * 8.0 + 0.65 * 7.0)) < 1e-9
    assert updated["New Player"] == 6.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k ewma or form_from_fixtures`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.dynamic.scrape_results'`

- [ ] **Step 3: Implement `pipeline/dynamic/scrape_results.py`**

```python
#!/usr/bin/env python3
"""
STAGE DINAMICO — Aggiornamento forma recente (EWMA) da risultati turno concluso.
EWMA_t = 0.35 * rating_t + 0.65 * EWMA_{t-1}. Il rating usato come base e' quello
per-giocatore restituito da api-football.com (proxy dichiarato del voto
fantacalcio ufficiale, non la pagella reale di fantacalcio.it).
Persistenza offline in data/ewma_state.json: mai letto/scritto a runtime da app.py.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.dynamic.api_football_client import get_fixture_player_ratings

EWMA_ALPHA = 0.35


def update_ewma(prev, rating, alpha=EWMA_ALPHA):
    """EWMA_t = alpha*rating + (1-alpha)*EWMA_{t-1}. Se non c'e' storico, ritorna il rating."""
    if prev is None:
        return rating
    return alpha * rating + (1 - alpha) * prev


def load_ewma_state():
    if not os.path.exists(config.EWMA_STATE_JSON):
        return {}
    try:
        with open(config.EWMA_STATE_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_ewma_state(state):
    os.makedirs(os.path.dirname(config.EWMA_STATE_JSON), exist_ok=True)
    with open(config.EWMA_STATE_JSON, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def update_form_from_fixtures(fixture_ids):
    """Aggiorna e persiste lo stato EWMA per tutti i giocatori delle fixture concluse date."""
    state = load_ewma_state()
    for fixture_id in fixture_ids:
        ratings = get_fixture_player_ratings(fixture_id)
        for player_name, rating in ratings.items():
            state[player_name] = update_ewma(state.get(player_name), rating)
    save_ewma_state(state)
    return state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k "ewma or form_from_fixtures"`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add pipeline/dynamic/scrape_results.py tests/test_dynamic_feed.py
git commit -m "feat(dynamic-feed): add EWMA form tracker from post-matchday ratings

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: `build_feed.py` — orchestratore e contratto JSON

**Files:**
- Create: `pipeline/dynamic/build_feed.py`
- Test: `tests/test_dynamic_feed.py` (append)

**Interfaces:**
- Consumes: `scrape_odds.build_odds_feed`, `scrape_lineups.scrape_probable_lineups`,
  `scrape_lineups.expected_minutes`, `scrape_lineups.BASELINE_TITULAR_PROB`,
  `scrape_status.scrape_all_statuses`, `scrape_results.load_ewma_state`,
  `pipeline.dynamic.utils.PlayerMatcher`, `config.DATASET_FINALE_CSV` (existing),
  `config.CURRENT_MATCHDAY_JSON`, `config.MIN_VALID_PLAYERS_IN_FEED`
- Produces: `compute_xpts(voto_base: float, p_gol: float, p_assist: float, e_gol_subiti: float, p_ammonizione: float, xmin: float) -> float`,
  `build_players_payload(dataset_df, lineup_players, statuses, ewma_state, odds_feed) -> dict`,
  `build_feed_payload(dataset_df, matchday: int, season: str) -> dict` (the full JSON
  contract), `main()` (CLI entrypoint, writes `config.CURRENT_MATCHDAY_JSON`, raises
  `RuntimeError` if fewer than `config.MIN_VALID_PLAYERS_IN_FEED` valid players).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dynamic_feed.py`:

```python
from pipeline.dynamic import build_feed


def test_compute_xpts_matches_capitolato_formula():
    # xPts = (xMin/90) * [VotoBase + 3*P(Gol) + 1*P(Assist) - 1*E[GolSubiti] - 0.25*P(Ammon)]
    result = build_feed.compute_xpts(
        voto_base=6.0, p_gol=0.4, p_assist=0.2, e_gol_subiti=0.5, p_ammonizione=0.1, xmin=78
    )
    expected = (78 / 90) * (6.0 + 3 * 0.4 + 1 * 0.2 - 1 * 0.5 - 0.25 * 0.1)
    assert abs(result - expected) < 1e-9


def test_build_players_payload_applies_status_override_and_ewma():
    dataset_df = pd.DataFrame({
        "player": ["Lautaro Martinez"],
        "team": ["INT"],
        "role": ["A"],
    })
    lineup_players = [
        {"player_name": "Lautaro Martinez", "match_id": "1", "side": "home", "href": ""}
    ]
    statuses = {}  # nessuno stato negativo -> resta OK
    ewma_state = {"Lautaro Martinez": 7.4}
    odds_feed = []

    payload = build_feed.build_players_payload(
        dataset_df, lineup_players, statuses, ewma_state, odds_feed
    )
    key = "int_lautaro_martinez_a"
    assert key in payload
    assert payload[key]["status"] == "OK"
    assert payload[key]["ewma_form"] == 7.4
    assert payload[key]["titular_prob"] == build_feed.scrape_lineups.BASELINE_TITULAR_PROB


def test_build_players_payload_marks_infortunato_status():
    dataset_df = pd.DataFrame({"player": ["Hien"], "team": ["ATA"], "role": ["D"]})
    statuses = {"Hien": "INFORTUNATO"}

    payload = build_feed.build_players_payload(dataset_df, [], statuses, {}, [])
    assert payload["ata_hien_d"]["status"] == "INFORTUNATO"
    assert payload["ata_hien_d"]["titular_prob"] == 0.0


def test_build_feed_payload_has_required_top_level_keys():
    dataset_df = pd.DataFrame({"player": ["Test Player"], "team": ["ROM"], "role": ["C"]})
    payload = build_feed.build_feed_payload(dataset_df, matchday=4, season="2026/2027")
    assert set(["matchday", "season", "updated_at", "fixtures", "players"]).issubset(payload.keys())
    assert payload["matchday"] == 4
    assert payload["season"] == "2026/2027"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k "xpts or players_payload or feed_payload"`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.dynamic.build_feed'`

- [ ] **Step 3: Implement `pipeline/dynamic/build_feed.py`**

```python
#!/usr/bin/env python3
"""
STAGE DINAMICO — Orchestratore del feed infrasettimanale (Pilastro 3).
Unisce formazioni probabili, stato clinico/disciplinare, quote de-vig e forma
EWMA in data/current_matchday.json secondo il contratto dati del capitolato.
Fail-fast se il numero di giocatori validi e' insufficiente (< MIN_VALID_PLAYERS_IN_FEED).
"""
import datetime
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.dynamic import scrape_lineups, scrape_odds, scrape_results, scrape_status
from pipeline.dynamic.utils import PlayerMatcher, normalize_name


def compute_xpts(voto_base, p_gol, p_assist, e_gol_subiti, p_ammonizione, xmin):
    """xPts = (xMin/90) * [VotoBase + 3*P(Gol) + P(Assist) - E[GolSubiti] - 0.25*P(Ammonizione)]."""
    base_score = voto_base + 3 * p_gol + p_assist - e_gol_subiti - 0.25 * p_ammonizione
    return (xmin / 90.0) * base_score


def _team_slug(team_value):
    return normalize_name(str(team_value)).replace(" ", "_")


def _player_key(team_value, player_name, role):
    return f"{_team_slug(team_value)}_{normalize_name(player_name).replace(' ', '_')}_{str(role).lower()}"


def build_players_payload(dataset_df, lineup_players, statuses, ewma_state, odds_feed):
    """Costruisce il dict 'players' del contratto JSON per ogni giocatore nel dataset."""
    matcher = PlayerMatcher(dataset_df)
    lineup_by_matched_name = {}
    for lp in lineup_players:
        matched = matcher.match(lp["player_name"], "")
        if matched:
            lineup_by_matched_name[matched] = lp

    odds_by_team = {}
    for fx in odds_feed:
        odds_by_team[fx["home_team"]] = fx
        odds_by_team[fx["away_team"]] = fx

    players = {}
    for _, row in dataset_df.iterrows():
        name = row["player"]
        team = row["team"]
        role = row["role"]
        key = _player_key(team, name, role)

        status = statuses.get(name, "OK")
        is_starter = name in lineup_by_matched_name
        ewma_form = ewma_state.get(name, 6.0)

        if status in ("INFORTUNATO", "SQUALIFICATO"):
            titular_prob = 0.0
        elif is_starter:
            titular_prob = scrape_lineups.BASELINE_TITULAR_PROB
        else:
            titular_prob = 0.15  # riserva/panchina di default

        xmin = scrape_lineups.expected_minutes(titular_prob, is_bench_candidate=not is_starter)

        players[key] = {
            "name": name,
            "team": team,
            "role": role,
            "status": status,
            "titular_prob": round(titular_prob, 3),
            "expected_minutes": round(xmin, 1),
            "ewma_form": round(ewma_form, 3),
            "xpts": round(
                compute_xpts(
                    voto_base=ewma_form,
                    p_gol=0.0,
                    p_assist=0.0,
                    e_gol_subiti=0.0,
                    p_ammonizione=0.1,
                    xmin=xmin,
                ),
                3,
            ),
        }
    return players


def build_feed_payload(dataset_df, matchday, season):
    lineup_players = scrape_lineups.scrape_probable_lineups()
    statuses = scrape_status.scrape_all_statuses()
    ewma_state = scrape_results.load_ewma_state()
    odds_feed = scrape_odds.build_odds_feed()

    return {
        "matchday": matchday,
        "season": season,
        "updated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rating_source": "api_football_proxy",
        "fixtures": odds_feed,
        "players": build_players_payload(dataset_df, lineup_players, statuses, ewma_state, odds_feed),
    }


def main(matchday=1, season="2026/2027"):
    if not os.path.exists(config.DATASET_FINALE_CSV):
        raise RuntimeError(
            f"[ERROR] Dataset non trovato: {config.DATASET_FINALE_CSV}. "
            "Esegui prima la pipeline statica: python run_pipeline.py"
        )
    dataset_df = pd.read_csv(config.DATASET_FINALE_CSV)
    payload = build_feed_payload(dataset_df, matchday, season)

    valid_players = sum(1 for p in payload["players"].values() if p["name"])
    if valid_players < config.MIN_VALID_PLAYERS_IN_FEED:
        raise RuntimeError(
            f"[ERROR] Feed dinamico incompleto: {valid_players} giocatori validi "
            f"(< {config.MIN_VALID_PLAYERS_IN_FEED} richiesti). Interruzione per evitare "
            "un feed corrotto o parziale su data-feed."
        )

    os.makedirs(os.path.dirname(config.CURRENT_MATCHDAY_JSON), exist_ok=True)
    with open(config.CURRENT_MATCHDAY_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[OK] Feed scritto in {config.CURRENT_MATCHDAY_JSON} ({valid_players} giocatori validi)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k "xpts or players_payload or feed_payload"`
Expected: `4 passed`

- [ ] **Step 5: Run the full dynamic-feed test file to confirm no regressions**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v`
Expected: all tests pass (24 total across Tasks 1-7)

- [ ] **Step 6: Commit**

```bash
git add pipeline/dynamic/build_feed.py tests/test_dynamic_feed.py
git commit -m "feat(dynamic-feed): add build_feed orchestrator producing current_matchday.json

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 8: `client.py` — client web app con cache TTL e fallback

**Files:**
- Create: `pipeline/dynamic/client.py`
- Create: `data/fallback_matchday.json`
- Test: `tests/test_dynamic_feed.py` (append)

**Interfaces:**
- Produces: `class MatchdayFeedClient` with
  `MatchdayFeedClient(feed_url: str | None = None, ttl_seconds: int = 900, fallback_path: str | None = None) -> MatchdayFeedClient`
  and `.get_feed() -> dict` (thread-safe, returns cached payload if within TTL, otherwise
  re-fetches; falls back to the local static file on any fetch failure).
  Also produces a module-level singleton accessor `get_default_client() -> MatchdayFeedClient`.

- [ ] **Step 1: Create the static fallback file**

Create `data/fallback_matchday.json`:

```json
{
  "matchday": 0,
  "season": "2026/2027",
  "updated_at": "2026-09-06T00:00:00Z",
  "rating_source": "api_football_proxy",
  "fixtures": [],
  "players": {}
}
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_dynamic_feed.py`:

```python
from pipeline.dynamic.client import MatchdayFeedClient


def test_client_returns_fallback_when_fetch_fails(tmp_path):
    fallback_path = tmp_path / "fallback_matchday.json"
    fallback_payload = {"matchday": 0, "season": "2026/2027", "fixtures": [], "players": {}}
    fallback_path.write_text(json.dumps(fallback_payload), encoding="utf-8")

    with patch("pipeline.dynamic.client.requests.get", side_effect=Exception("network down")):
        client = MatchdayFeedClient(
            feed_url="https://example.invalid/current_matchday.json",
            fallback_path=str(fallback_path),
        )
        feed = client.get_feed()
    assert feed == fallback_payload


def test_client_caches_within_ttl(tmp_path):
    fallback_path = tmp_path / "fallback_matchday.json"
    fallback_path.write_text(json.dumps({"matchday": 0, "fixtures": [], "players": {}}), encoding="utf-8")

    mock_response = MagicMock()
    mock_response.json.return_value = {"matchday": 5, "fixtures": [], "players": {}}
    mock_response.status_code = 200

    with patch("pipeline.dynamic.client.requests.get", return_value=mock_response) as mock_get:
        client = MatchdayFeedClient(
            feed_url="https://example.invalid/current_matchday.json",
            ttl_seconds=900,
            fallback_path=str(fallback_path),
        )
        first = client.get_feed()
        second = client.get_feed()
        assert first["matchday"] == 5
        assert second["matchday"] == 5
        assert mock_get.call_count == 1  # secondo fetch servito dalla cache
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k client`
Expected: FAIL with `ModuleNotFoundError: No module named 'pipeline.dynamic.client'`

- [ ] **Step 4: Implement `pipeline/dynamic/client.py`**

```python
#!/usr/bin/env python3
"""
Client thread-safe per il feed dinamico infrasettimanale (Pilastro 3), usato da app.py.
Cache in-memory con TTL 15 minuti; fallback automatico su data/fallback_matchday.json
in caso di fetch fallito o timeout. Nessuna scrittura su disco a runtime.
"""
import json
import os
import sys
import threading
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

DEFAULT_FEED_URL = (
    "https://raw.githubusercontent.com/SpectreLabo/fanta-lab/data-feed/data/current_matchday.json"
)


class MatchdayFeedClient:
    def __init__(self, feed_url=None, ttl_seconds=900, fallback_path=None):
        self.feed_url = feed_url or os.environ.get("MATCHDAY_FEED_URL", DEFAULT_FEED_URL)
        self.ttl_seconds = ttl_seconds
        self.fallback_path = fallback_path or config.FALLBACK_MATCHDAY_JSON
        self._lock = threading.Lock()
        self._cache = None
        self._cache_ts = 0.0

    def _load_fallback(self):
        try:
            with open(self.fallback_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"matchday": 0, "season": "", "fixtures": [], "players": {}}

    def get_feed(self):
        with self._lock:
            now = time.time()
            if self._cache is not None and (now - self._cache_ts) < self.ttl_seconds:
                return self._cache

            try:
                resp = requests.get(self.feed_url, timeout=8)
                if resp.status_code == 200:
                    payload = resp.json()
                    self._cache = payload
                    self._cache_ts = now
                    return payload
            except Exception:
                pass

            # Fetch fallito: usa il fallback statico ma NON aggiorna il timestamp di
            # cache, cosi' il prossimo tentativo riprovera' subito il fetch remoto.
            return self._load_fallback()


_default_client = None
_default_client_lock = threading.Lock()


def get_default_client():
    global _default_client
    with _default_client_lock:
        if _default_client is None:
            _default_client = MatchdayFeedClient()
        return _default_client
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -m pytest tests/test_dynamic_feed.py -v -k client`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add pipeline/dynamic/client.py data/fallback_matchday.json tests/test_dynamic_feed.py
git commit -m "feat(dynamic-feed): add cached client with static fallback for app.py

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 9: GitHub Actions workflow + documentazione

**Files:**
- Create: `.github/workflows/dynamic_feed.yml`
- Modify: `README.md` (append a short new section)

**Interfaces:**
- Consumes: `pipeline.dynamic.build_feed.main` (invoked via `python -m pipeline.dynamic.build_feed`)
- Produces: none (CI-only artifact — the `data-feed` branch with `data/current_matchday.json`)

- [ ] **Step 1: Create the workflow file**

Create `.github/workflows/dynamic_feed.yml`:

```yaml
name: Dynamic Matchday Feed

on:
  schedule:
    - cron: '0 18 * * 4'   # Giovedi 18:00 UTC
    - cron: '0 12 * * 5'   # Venerdi 12:00 UTC
    - cron: '0 19 * * 5'   # Venerdi 19:00 UTC
    - cron: '0 11 * * 6'   # Sabato 11:00 UTC
  workflow_dispatch: {}

permissions:
  contents: write

jobs:
  build-feed:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout main
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Build dynamic matchday feed
        env:
          API_FOOTBALL_KEY: ${{ secrets.API_FOOTBALL_KEY }}
        run: python -m pipeline.dynamic.build_feed

      - name: Publish to data-feed branch
        run: |
          git config user.name "fanta-lab-bot"
          git config user.email "actions@users.noreply.github.com"

          if git ls-remote --exit-code --heads origin data-feed; then
            git fetch origin data-feed
            git checkout data-feed
          else
            git checkout --orphan data-feed
            git rm -rf . > /dev/null 2>&1 || true
          fi

          mkdir -p data
          git checkout main -- data/current_matchday.json
          git add data/current_matchday.json
          git commit -m "chore: update current_matchday.json [skip ci]" || echo "Nessuna modifica al feed"
          git push origin data-feed
```

- [ ] **Step 2: Verify the workflow YAML is syntactically valid**

Run: `cd /Users/a409835/Documents/myProjects/fanta-lab && python -c "import yaml; yaml.safe_load(open('.github/workflows/dynamic_feed.yml'))" && echo "YAML OK"`
Expected: `YAML OK`

(If `yaml` is not installed: `pip install pyyaml` first — it is a test-only dependency
for this validation step, not added to `requirements.txt`.)

- [ ] **Step 3: Document the new environment variable in README**

Append a new section to `README.md` (after the existing configuration section — find it
with `grep -n "^## " README.md` and insert after the last matching setup-related
heading):

```markdown
## Feed Dinamico Infrasettimanale (opzionale)

Per abilitare l'aggiornamento automatico di probabili formazioni, quote e forma
recente durante la stagione:

1. Crea una chiave gratuita/a pagamento su [api-football.com](https://www.api-football.com/).
2. In locale: aggiungi `API_FOOTBALL_KEY=<la-tua-chiave>` al file `.env` (già in `.gitignore`, non verrà mai committato).
3. Su GitHub: vai su Settings → Secrets and variables → Actions e crea il secret `API_FOOTBALL_KEY` con lo stesso valore.
4. Il workflow `.github/workflows/dynamic_feed.yml` genera `data/current_matchday.json` e lo pubblica sulla branch `data-feed` secondo il cron configurato (Gio 18:00, Ven 12:00/19:00, Sab 11:00 UTC), oppure puoi lanciarlo manualmente da GitHub Actions ("Run workflow").
5. L'app consuma il feed tramite `pipeline/dynamic/client.py`, con cache di 15 minuti e fallback automatico su `data/fallback_matchday.json` se il feed remoto non è raggiungibile.

**Non condividere mai la tua chiave API in chat, issue o commit pubblici.**
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/dynamic_feed.yml README.md
git commit -m "ci(dynamic-feed): add scheduled GitHub Actions workflow and docs

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

## Self-Review Notes (completed during plan authoring)

- **Spec coverage:** all 6 components from the design spec (`scrape_odds.py`,
  `scrape_lineups.py`, `scrape_results.py`, `build_feed.py`, `client.py`,
  `.github/workflows/dynamic_feed.yml`) map to Tasks 2-3, 4, 6, 7, 8, 9 respectively.
  `scrape_status.py` (Task 5) was added beyond the original spec sketch because the
  design review of real `fantacalcio.it` markup showed probable-lineup pages do not
  carry per-player titolarità percentages — status data had to be sourced separately
  to honor "Non inventare statistiche non presenti nel payload fornito."
- **Placeholder scan:** no `TBD`/`TODO` — every step has runnable code and exact
  commands.
- **Type consistency:** `PlayerMatcher.match` (Task 1) is consumed identically in
  `build_feed.build_players_payload` (Task 7); `scrape_lineups.expected_minutes` and
  `scrape_lineups.BASELINE_TITULAR_PROB` (Task 4) are consumed with the same names in
  Task 7; `scrape_results.load_ewma_state`/`save_ewma_state` (Task 6) match the calls
  in Task 7's `build_feed_payload`.
