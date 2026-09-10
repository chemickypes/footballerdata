#!/usr/bin/env python3
"""
Unit tests for the /api/match_detail payload builder (stages 11+12 joined).
No live network calls.
"""
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web.matches_api import _build_match_detail_payload, _sort_lineup

MATCHES_PAYLOAD = {
    "available": True,
    "rounds": [
        {"round": 1, "matches": [
            {"fixture_id": 100, "round": 1, "date": "2026-08-22T16:30:00+00:00",
             "home_team": "Inter", "home_code": "INT", "home_display": "Inter",
             "away_team": "Monza", "away_code": "MON", "away_display": "Monza",
             "home_score": 4, "away_score": 1, "ht_home_score": 1, "ht_away_score": 1,
             "status": "FT", "finished": True},
            {"fixture_id": 200, "round": 1, "date": "2026-08-23T18:45:00+00:00",
             "home_team": "Lazio", "home_code": "LAZ", "home_display": "Lazio",
             "away_team": "Verona", "away_code": "VER", "away_display": "Verona",
             "home_score": None, "away_score": None,
             "ht_home_score": None, "ht_away_score": None,
             "status": "NS", "finished": False},
        ]},
    ],
}


def _pm_df():
    return pd.DataFrame([
        # Inter (casa) — titolari ordinati per maglia + un subentrato
        {"event_id": 100, "team_code": "INT", "venue": "home", "player": "Bastoni",
         "player_sofascore": "Alessandro Bastoni", "position": "D", "shirt_number": 95,
         "is_starter": True, "minutes_played": 90, "rating": 7.9, "goals": 1, "assists": 0},
        {"event_id": 100, "team_code": "INT", "venue": "home", "player": "Calhanoglu",
         "player_sofascore": "Hakan Calhanoglu", "position": "C", "shirt_number": 20,
         "is_starter": True, "minutes_played": 54, "rating": 8.0, "goals": 1, "assists": 0},
        {"event_id": 100, "team_code": "INT", "venue": "home", "player": "Frattesi",
         "player_sofascore": "Davide Frattesi", "position": "C", "shirt_number": 16,
         "is_starter": False, "minutes_played": 36, "rating": 6.9, "goals": 0, "assists": 1},
        # Monza (trasferta) — riga senza nome dataset (usa player_sofascore)
        {"event_id": 100, "team_code": "MON", "venue": "away", "player": float("nan"),
         "player_sofascore": "Some Monza Player", "position": "C", "shirt_number": 10,
         "is_starter": True, "minutes_played": 90, "rating": 6.5, "goals": 0, "assists": 0},
        # riga di un'altra partita: non deve finire nel payload
        {"event_id": 999, "team_code": "INT", "venue": "home", "player": "Altro",
         "player_sofascore": "Other", "position": "A", "shirt_number": 9,
         "is_starter": True, "minutes_played": 90, "rating": 7.0, "goals": 1, "assists": 0},
    ])


def test_match_detail_finished_with_lineups():
    payload = _build_match_detail_payload(_pm_df(), 100, MATCHES_PAYLOAD)
    assert payload is not None
    assert payload["match"]["home_team"] == "Inter"
    assert payload["match"]["home_score"] == 4
    assert payload["lineups_available"] is True
    home = payload["home"]["players"]
    away = payload["away"]["players"]
    assert len(home) == 3 and len(away) == 1
    # titolari per numero di maglia, subentrato dopo
    assert [p["player"] for p in home] == ["Calhanoglu", "Bastoni", "Frattesi"]
    # riga senza nome dataset: usa il nome Sofascore
    assert away[0]["player"] is None
    assert away[0]["player_sofascore"] == "Some Monza Player"
    # marcatori aggregati
    scorers = {s["player"]: s["goals"] for s in payload["scorers"]}
    assert scorers == {"Bastoni": 1, "Calhanoglu": 1}
    # MOTM = rating max (Calhanoglu 8.0)
    assert payload["motm"]["player"] == "Calhanoglu"
    assert payload["motm"]["rating"] == 8.0
    # meta completi
    assert payload["match"]["ht_home_score"] == 1
    assert payload["match"]["finished"] is True


def test_match_detail_not_started():
    payload = _build_match_detail_payload(_pm_df(), 200, MATCHES_PAYLOAD)
    assert payload is not None
    assert payload["match"]["status"] == "NS"
    assert payload["lineups_available"] is False
    assert payload["home"]["players"] == []
    assert payload["scorers"] == []
    assert payload["motm"] is None


def test_match_detail_without_pm_csv():
    payload = _build_match_detail_payload(None, 100, MATCHES_PAYLOAD)
    assert payload is not None
    assert payload["lineups_available"] is False


def test_match_detail_unknown_event():
    assert _build_match_detail_payload(_pm_df(), 314159, MATCHES_PAYLOAD) is None
    assert _build_match_detail_payload(_pm_df(), 100, {"available": False}) is None
    assert _build_match_detail_payload(_pm_df(), 100, None) is None


def test_sort_lineup_starters_by_shirt_then_subs_by_minutes():
    players = [
        {"player": "Sub2", "is_starter": False, "shirt_number": 30, "minutes_played": 10},
        {"player": "StarterHigh", "is_starter": True, "shirt_number": 90, "minutes_played": 80},
        {"player": "Sub1", "is_starter": False, "shirt_number": 11, "minutes_played": 45},
        {"player": "StarterLow", "is_starter": True, "shirt_number": 4, "minutes_played": 90},
        {"player": "StarterNoShirt", "is_starter": True, "shirt_number": None, "minutes_played": 90},
    ]
    ordered = _sort_lineup(players)
    assert [p["player"] for p in ordered] == [
        "StarterLow", "StarterHigh", "StarterNoShirt", "Sub1", "Sub2"]


def test_match_detail_rounding_and_none_rating():
    df = pd.DataFrame([
        {"event_id": 100, "team_code": "INT", "venue": "home", "player": "A",
         "player_sofascore": "A", "position": "P", "shirt_number": 1,
         "is_starter": True, "minutes_played": 90, "rating": 7.0333333,
         "goals": 0, "assists": 0, "xg": 0.18345, "goals_prevented": -0.12345},
    ])
    payload = _build_match_detail_payload(df, 100, MATCHES_PAYLOAD)
    row = payload["home"]["players"][0]
    assert row["rating"] == 7.03
    assert row["xg"] == 0.18
    assert row["goals_prevented"] == -0.12
