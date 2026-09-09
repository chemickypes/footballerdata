#!/usr/bin/env python3
"""
Unit tests for stage 11 (Serie A match results) and the /api/matches payload.
No live network calls: the api-football client is mocked.
"""
import importlib
import json
import os
import sys
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

stage11 = importlib.import_module("core.ingestion.static.11_scrape_match_results")

from core.ingestion.static import sofascore_api
from web.matches_api import _build_payload


SAMPLE_FIXTURES = [
    {
        "fixture_id": 1, "date": "2026-08-23T18:45:00+00:00",
        "home_team": "Inter", "away_team": "AS Roma",
        "home_score": 2, "away_score": 1,
        "ht_home_score": 1, "ht_away_score": 0,
        "round": "Regular Season - 1", "status": "FT",
    },
    {
        "fixture_id": 2, "date": "2026-08-24T20:45:00+00:00",
        "home_team": "SSC Napoli", "away_team": "AC Milan",
        "home_score": 0, "away_score": 0,
        "ht_home_score": 0, "ht_away_score": 0,
        "round": "Regular Season - 1", "status": "FT",
    },
    {
        "fixture_id": 3, "date": "2026-08-30T18:45:00+00:00",
        "home_team": "AS Roma", "away_team": "SSC Napoli",
        "home_score": None, "away_score": None,
        "ht_home_score": None, "ht_away_score": None,
        "round": "Regular Season - 2", "status": "NS",
    },
]


def test_round_number():
    assert stage11.round_number("Regular Season - 3") == 3
    assert stage11.round_number("Regular Season - 38") == 38
    assert stage11.round_number("") is None
    assert stage11.round_number(None) is None


def test_map_team_exact_and_variants():
    assert stage11.map_team("Inter") == "INT"
    assert stage11.map_team("AS Roma") == "ROM"
    assert stage11.map_team("SSC Napoli") == "NAP"
    assert stage11.map_team("AC Milan") == "MIL"


def test_map_team_fuzzy_and_unknown():
    # Nome non noto → None (nessun match fuzzy plausibile)
    assert stage11.map_team("Totally Unknown FC") is None
    assert stage11.map_team("") is None
    assert stage11.map_team(None) is None


@patch.object(sofascore_api, "get_season_fixtures")
def test_fetch_results_dataframe(mock_season):
    mock_season.return_value = SAMPLE_FIXTURES
    df = stage11.fetch_results_dataframe()
    assert len(df) == 3
    row0 = df[df["fixture_id"] == 1].iloc[0]
    assert row0["round"] == 1
    assert row0["home_team_code"] == "INT"
    assert row0["away_team_code"] == "ROM"
    assert row0["home_score"] == 2
    assert row0["away_score"] == 1
    assert row0["ht_home_score"] == 1
    assert row0["status"] == "FT"
    # ordinamento per giornata
    assert df.iloc[0]["round"] <= df.iloc[-1]["round"]


@patch.object(sofascore_api, "get_season_fixtures")
def test_fetch_results_dataframe_empty(mock_season):
    mock_season.return_value = []
    df = stage11.fetch_results_dataframe()
    assert df.empty


def test_build_team_form_home_and_away_perspective():
    with patch.object(sofascore_api, "get_season_fixtures", return_value=SAMPLE_FIXTURES):
        df = stage11.fetch_results_dataframe()

    form = stage11.build_team_form(df)

    # Inter ha vinto 2-1 in casa
    inter = form["INT"]
    assert inter["played"] == 1 and inter["wins"] == 1
    assert inter["gf"] == 2 and inter["ga"] == 1
    assert inter["points"] == 3
    assert inter["form"] == "W"
    assert inter["points_last5"] == 3

    # Roma ha perso 2-1 in trasferta (prospettiva away)
    roma = form["ROM"]
    assert roma["losses"] == 1
    assert roma["gf"] == 1 and roma["ga"] == 2
    assert roma["form"] == "L"

    # Napoli-Milan 0-0: pareggio per entrambe
    assert form["NAP"]["draws"] == 1 and form["NAP"]["points"] == 1
    assert form["MIL"]["draws"] == 1 and form["MIL"]["points"] == 1

    # La partita non giocata (NS) non conta
    assert form["NAP"]["played"] == 1
    assert form["ROM"]["played"] == 1

    # Le sigle sono le chiavi del dict
    assert all(len(k) == 3 for k in form.keys())


def test_build_team_form_last5_caps_at_five():
    fixtures = []
    for rnd in range(1, 7):
        fixtures.append({
            "fixture_id": 100 + rnd, "date": f"2026-09-{rnd:02d}T15:00:00+00:00",
            "home_team": "Inter", "away_team": f"Team{rnd}",
            "home_score": rnd, "away_score": 0,
            "ht_home_score": None, "ht_away_score": None,
            "round": f"Regular Season - {rnd}", "status": "FT",
        })
    with patch.object(sofascore_api, "get_season_fixtures", return_value=fixtures):
        df = stage11.fetch_results_dataframe()
    form = stage11.build_team_form(df)
    inter = form["INT"]
    assert inter["played"] == 6
    assert inter["wins"] == 6
    assert inter["points"] == 18
    assert len(inter["last5"]) == 5
    assert inter["form"] == "WWWWW"
    assert inter["points_last5"] == 15
    assert inter["gf_last5"] == sum(range(2, 7))  # gare 2..6


def test_build_team_form_empty_df():
    assert stage11.build_team_form(pd.DataFrame()) == {}


def test_build_payload_from_files(tmp_path):
    with patch.object(sofascore_api, "get_season_fixtures", return_value=SAMPLE_FIXTURES):
        df = stage11.fetch_results_dataframe()

    csv_path = tmp_path / "match_results.csv"
    form_path = tmp_path / "team_form.json"
    df.to_csv(csv_path, index=False)
    form = stage11.build_team_form(df)
    with open(form_path, "w", encoding="utf-8") as f:
        json.dump(form, f)

    payload = _build_payload(str(csv_path), str(form_path))
    assert payload is not None
    assert payload["available"] is True
    assert [r["round"] for r in payload["rounds"]] == [1, 2]

    # current_round = ultima giornata con almeno una partita conclusa
    assert payload["current_round"] == 1

    rnd1 = payload["rounds"][0]
    m1 = next(m for m in rnd1["matches"] if m["fixture_id"] == 1)
    assert m1["home_code"] == "INT" and m1["away_code"] == "ROM"
    assert m1["home_display"] == "Inter"
    assert m1["home_score"] == 2 and m1["away_score"] == 1
    assert m1["ht_home_score"] == 1 and m1["ht_away_score"] == 0
    assert m1["finished"] is True

    rnd2 = payload["rounds"][1]
    m3 = rnd2["matches"][0]
    assert m3["finished"] is False
    assert m3["home_score"] is None

    assert "INT" in payload["team_form"]
    assert payload["team_form"]["INT"]["form"] == "W"
    assert payload["season"] == "2026/27"


def test_build_payload_missing_csv(tmp_path):
    assert _build_payload(str(tmp_path / "nope.csv"), str(tmp_path / "nope.json")) is None


def test_build_payload_corrupt_csv(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("this,is,not,a,valid\n\"unclosed")
    assert _build_payload(str(bad), str(tmp_path / "nope.json")) is None


# ──────────────────────────────────────────────────────────────────────
# Sofascore source
# ──────────────────────────────────────────────────────────────────────
def test_sofascore_map_status():
    assert sofascore_api._map_status({"type": "finished", "description": "Ended"}) == "FT"
    assert sofascore_api._map_status({"type": "finished", "description": "After extra time"}) == "AET"
    assert sofascore_api._map_status({"type": "finished", "description": "After penalties"}) == "PEN"
    assert sofascore_api._map_status({"type": "inprogress", "description": "1st half"}) == "LIVE"
    assert sofascore_api._map_status({"type": "notstarted", "description": "Not started"}) == "NS"
    assert sofascore_api._map_status({"type": "postponed", "description": "Postponed"}) == "PST"
    assert sofascore_api._map_status({}) is None
    assert sofascore_api._map_status({"type": "weirdtype"}) is None


def test_sofascore_parse_event_finished():
    ev = {
        "id": 11352136,
        "startTimestamp": 1755967500,
        "status": {"code": 100, "description": "Ended", "type": "finished"},
        "homeTeam": {"id": 2697, "name": "Inter"},
        "awayTeam": {"id": 2714, "name": "AS Roma"},
        "homeScore": {"current": 2, "display": 2, "normaltime": 2, "period1": 1, "period2": 1},
        "awayScore": {"current": 1, "display": 1, "normaltime": 1, "period1": 0, "period2": 1},
        "roundInfo": {"round": 1},
    }
    fx = sofascore_api.parse_event(ev)
    assert fx["fixture_id"] == 11352136
    assert fx["home_team"] == "Inter" and fx["away_team"] == "AS Roma"
    assert fx["home_score"] == 2 and fx["away_score"] == 1
    assert fx["ht_home_score"] == 1 and fx["ht_away_score"] == 0
    assert fx["round"] == "Regular Season - 1"
    assert fx["status"] == "FT"
    assert fx["date"].startswith("2025-08-23")  # 1755967500 = 23 ago 2025 18:45 UTC


def test_sofascore_parse_event_scheduled_has_no_scores():
    ev = {
        "id": 999,
        "startTimestamp": 1756572300,
        "status": {"code": 0, "description": "Not started", "type": "notstarted"},
        "homeTeam": {"id": 1, "name": "Juventus"},
        "awayTeam": {"id": 2, "name": "Atalanta"},
        "homeScore": {},
        "awayScore": {},
        "roundInfo": {"round": 2},
    }
    fx = sofascore_api.parse_event(ev)
    assert fx["status"] == "NS"
    assert fx["home_score"] is None and fx["away_score"] is None
    assert fx["ht_home_score"] is None
    assert fx["round"] == "Regular Season - 2"


def test_sofascore_parse_event_inprogress_keeps_live_score():
    ev = {
        "id": 998,
        "startTimestamp": 1756572300,
        "status": {"type": "inprogress", "description": "2nd half"},
        "homeTeam": {"name": "Genoa"},
        "awayTeam": {"name": "Como 1907"},
        "homeScore": {"current": 1, "period1": 1},
        "awayScore": {"current": 0, "period1": 0},
        "roundInfo": {"round": 3},
    }
    fx = sofascore_api.parse_event(ev)
    assert fx["status"] == "LIVE"
    assert fx["home_score"] == 1 and fx["away_score"] == 0
    assert fx["ht_home_score"] == 1


def test_sofascore_parse_event_malformed_skipped():
    assert sofascore_api.parse_event({"id": 1}) is None
    assert sofascore_api.parse_event({}) is None


def test_map_team_sofascore_names():
    assert stage11.map_team("Inter") == "INT"
    assert stage11.map_team("AS Roma") == "ROM"
    assert stage11.map_team("Como 1907") == "COM"
    assert stage11.map_team("Hellas Verona") == "VER"
    assert stage11.map_team("AC Milan") == "MIL"


@patch.object(sofascore_api, "get_season_fixtures")
def test_fetch_results_dataframe_sofascore_source(mock_sofa):
    mock_sofa.return_value = [
        sofascore_api.parse_event({
            "id": 11352136,
            "startTimestamp": 1755967500,
            "status": {"type": "finished", "description": "Ended"},
            "homeTeam": {"name": "Inter"},
            "awayTeam": {"name": "AS Roma"},
            "homeScore": {"current": 2, "period1": 1},
            "awayScore": {"current": 1, "period1": 0},
            "roundInfo": {"round": 1},
        })
    ]
    df = stage11.fetch_results_dataframe("sofascore")
    assert len(df) == 1
    row = df.iloc[0]
    assert row["home_team_code"] == "INT" and row["away_team_code"] == "ROM"
    assert row["round"] == 1 and row["status"] == "FT"
    mock_sofa.assert_called_once()


@patch("core.ingestion.dynamic.api_football_client.get_season_fixtures")
def test_fetch_results_dataframe_apifootball_source(mock_api):
    mock_api.return_value = SAMPLE_FIXTURES
    df = stage11.fetch_results_dataframe("apifootball")
    assert len(df) == 3
    assert mock_api.call_count == 1


def test_sofascore_round_events_fetch_failure_returns_none():
    with patch.object(sofascore_api, "fetch_with_retry", return_value=None):
        assert sofascore_api.get_round_events(12345, 1) is None


def test_sofascore_get_season_fixtures_first_round_failure_raises():
    with patch.object(sofascore_api, "get_serie_a_season_id", return_value=12345), \
         patch.object(sofascore_api, "get_round_events", return_value=None):
        with pytest.raises(RuntimeError):
            sofascore_api.get_season_fixtures()
