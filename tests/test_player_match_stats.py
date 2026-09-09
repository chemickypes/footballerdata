#!/usr/bin/env python3
"""
Unit tests for stage 12 (per-match player stats from Sofascore lineups) and
the /api/player_matches payload builder. No live network calls.
"""
import importlib
import os
import sys
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

stage12 = importlib.import_module("core.ingestion.static.12_harvest_player_match_stats")

from core.ingestion.static import sofascore_api
from web.matches_api import _build_player_matches_payload


SAMPLE_LINEUP = {
    "confirmed": True,
    "home": {"players": [
        {
            "player": {"id": 823591, "name": "Lautaro Martínez", "shortName": "L. Martínez",
                       "position": "F", "jerseyNumber": 10},
            "position": "F", "shirtNumber": 10, "substitute": False,
            "statistics": {
                "minutesPlayed": 90, "rating": 7.4, "goals": 1, "goalAssist": 1,
                "keyPass": 2, "totalShots": 3, "onTargetScoringAttempt": 2,
                "expectedGoals": 0.6712, "expectedAssists": 0.2143,
                "accuratePass": 22, "totalPass": 28, "totalTackle": 0,
                "interceptionWon": 1, "totalClearance": 0, "duelWon": 5,
                "duelLost": 2, "touches": 41, "fouls": 1,
            },
        },
        {
            "player": {"id": 111, "name": "Sub Guy", "position": "M", "jerseyNumber": 20},
            "position": "M", "shirtNumber": 20, "substitute": True,
            "statistics": {"minutesPlayed": 12},
        },
        {
            "player": {"id": 112, "name": "Bench Guy", "position": "D", "jerseyNumber": 31},
            "position": "D", "shirtNumber": 31, "substitute": True,
            "statistics": {},
        },
    ]},
    "away": {"players": [
        {
            "player": {"id": 222, "name": "Away Player", "position": "F", "jerseyNumber": 9},
            "position": "F", "shirtNumber": 9, "substitute": False,
            "statistics": {"minutesPlayed": 90, "rating": 6.2, "goals": 0, "goalAssist": 0},
        },
    ]},
}

SAMPLE_FIXTURE = {
    "fixture_id": 16283050, "round": 1, "date": "2026-08-22T16:30:00+00:00",
    "home_team": "Inter", "away_team": "Monza",
}


def test_parse_event_lineup_starter():
    rows = sofascore_api.parse_event_lineup(SAMPLE_FIXTURE, SAMPLE_LINEUP)
    by_name = {r["player_sofascore"]: r for r in rows}
    lautaro = by_name["Lautaro Martínez"]
    assert lautaro["is_starter"] is True
    assert lautaro["minutes_played"] == 90
    assert lautaro["rating"] == 7.4
    assert lautaro["goals"] == 1
    assert lautaro["assists"] == 1  # goalAssist
    assert lautaro["key_passes"] == 2
    assert lautaro["shots"] == 3
    assert lautaro["shots_on_target"] == 2
    assert lautaro["xg"] == pytest.approx(0.671, abs=1e-3)
    assert lautaro["xa"] == pytest.approx(0.214, abs=1e-3)
    assert lautaro["sofascore_player_id"] == 823591
    assert lautaro["team_name"] == "Inter"
    assert lautaro["venue"] == "home"


def test_parse_event_lineup_skips_dnp_and_handles_sub():
    rows = sofascore_api.parse_event_lineup(SAMPLE_FIXTURE, SAMPLE_LINEUP)
    names = {r["player_sofascore"] for r in rows}
    assert "Bench Guy" not in names  # mai entrato: nessun minutesPlayed
    sub = next(r for r in rows if r["player_sofascore"] == "Sub Guy")
    assert sub["is_starter"] is False
    assert sub["minutes_played"] == 12
    assert sub["rating"] is None
    away = next(r for r in rows if r["player_sofascore"] == "Away Player")
    assert away["venue"] == "away"
    assert away["team_name"] == "Monza"
    assert away["goals"] == 0


def test_parse_event_lineup_empty_payload():
    assert sofascore_api.parse_event_lineup(SAMPLE_FIXTURE, {}) == []
    assert sofascore_api.parse_event_lineup(SAMPLE_FIXTURE, None) == []


def test_harvest_fixtures_assigns_team_and_opponent_codes():
    fixtures_df = pd.DataFrame([{
        "fixture_id": 16283050, "round": 1, "date_utc": "2026-08-22T16:30:00+00:00",
        "home_team": "Inter", "away_team": "Monza",
        "home_team_code": "INT", "away_team_code": "MON",
    }])
    calls = []

    def fake_fetcher(event_id):
        calls.append(event_id)
        return SAMPLE_LINEUP

    rows = stage12.harvest_fixtures(fixtures_df, fake_fetcher, rate_limit_sec=0)
    assert calls == [16283050]
    by_name = {r["player_sofascore"]: r for r in rows}
    assert by_name["Lautaro Martínez"]["team_code"] == "INT"
    assert by_name["Lautaro Martínez"]["opponent_code"] == "MON"
    assert by_name["Away Player"]["team_code"] == "MON"
    assert by_name["Away Player"]["opponent_code"] == "INT"


def test_harvest_fixtures_skips_failed_fetch():
    fixtures_df = pd.DataFrame([
        {"fixture_id": 1, "round": 1, "date_utc": "d1", "home_team": "A", "away_team": "B",
         "home_team_code": "ATA", "away_team_code": "BOL"},
        {"fixture_id": 2, "round": 1, "date_utc": "d2", "home_team": "C", "away_team": "D",
         "home_team_code": "COM", "away_team_code": "CAG"},
    ])
    def fake_fetcher(event_id):
        return SAMPLE_LINEUP if event_id == 2 else None

    rows = stage12.harvest_fixtures(fixtures_df, fake_fetcher, rate_limit_sec=0)
    assert {r["event_id"] for r in rows} == {2}


def test_match_players_alias_and_fuzzy():
    dataset_df = pd.DataFrame({
        "player": ["Martinez L.", "Thuram", "Bisseck"],
        "team": ["INT", "INT", "INT"],
    })
    rows = [
        {"player_sofascore": "Josep Martínez", "team_code": "INT"},   # alias esplicito
        {"player_sofascore": "Lautaro Martínez", "team_code": "INT"}, # fuzzy per squadra (cognome)
        {"player_sofascore": "Yann Bisseck", "team_code": "INT"},     # fuzzy nome completo
        {"player_sofascore": "Totally Unknown", "team_code": "XXX"},  # unmatched
    ]
    rows, n_matched, unmatched = stage12.match_players(rows, dataset_df)
    assert rows[0]["player"] == "Martinez Jo."  # alias: nome non nel df sintetico ma mappato
    assert rows[1]["player"] == "Martinez L."   # Lautaro via fallback cognome
    assert rows[2]["player"] == "Bisseck"
    assert n_matched == 3
    assert rows[3]["player"] == ""
    assert any("Totally Unknown" in u for u in unmatched)


def test_match_players_without_dataset():
    rows = [{"player_sofascore": "Lautaro Martínez", "team_code": "INT"}]
    rows, n_matched, unmatched = stage12.match_players(rows, None)
    assert rows[0]["player"] == ""
    assert n_matched == 0


def test_merge_rows_dedupes_on_event_and_player():
    existing = [
        {"event_id": 1, "sofascore_player_id": 10, "player": "A", "minutes_played": 90},
    ]
    new = [
        {"event_id": 1, "sofascore_player_id": 10, "player": "A", "minutes_played": 90},  # dup
        {"event_id": 1, "sofascore_player_id": 11, "player": "B", "minutes_played": 12},
        {"event_id": 2, "sofascore_player_id": 10, "player": "A", "minutes_played": 90},
    ]
    merged, added = stage12.merge_rows(existing, new)
    assert len(merged) == 3
    assert added == 2


def test_harvested_event_ids_handles_floats_from_csv():
    rows = [
        {"event_id": 16283050.0, "sofascore_player_id": 1.0},
        {"event_id": 999.0, "sofascore_player_id": 2.0},
    ]
    ids = stage12.harvested_event_ids(rows)
    assert ids == {16283050.0, 999.0}
    assert 16283050 in ids  # int == float per hash/eq


def _make_stats_df():
    return pd.DataFrame([
        {"player": "Martinez L.", "round": 1, "date_utc": "2026-08-22", "venue": "home",
         "opponent_code": "MON", "minutes_played": 90, "rating": 7.4, "goals": 1,
         "assists": 0, "key_passes": 2, "shots": 3, "xg": 0.67, "xa": 0.1, "is_starter": True},
        {"player": "Martinez L.", "round": 2, "date_utc": "2026-08-30", "venue": "away",
         "opponent_code": "CAG", "minutes_played": 82, "rating": 6.8, "goals": 0,
         "assists": 1, "key_passes": 1, "shots": 2, "xg": 0.21, "xa": 0.3, "is_starter": True},
        {"player": "Thuram", "round": 1, "date_utc": "2026-08-22", "venue": "home",
         "opponent_code": "MON", "minutes_played": 90, "rating": 7.0, "goals": 2,
         "assists": 0, "key_passes": 0, "shots": 4, "xg": 1.1, "xa": 0.0, "is_starter": True},
    ])


def test_build_player_matches_payload():
    payload = _build_player_matches_payload(_make_stats_df(), "Martinez L.")
    assert payload is not None
    assert payload["available"] is True
    ms = payload["matches"]
    assert len(ms) == 2
    # ordine cronologico inverso
    assert ms[0]["round"] == 2 and ms[1]["round"] == 1
    assert ms[0]["opponent"] == "CAG"
    assert ms[0]["opponent_display"]  # nome display risolto
    s = payload["summary"]
    assert s["played"] == 2
    assert s["starts"] == 2
    assert s["minutes"] == 172
    assert s["avg_rating"] == pytest.approx(7.1)
    assert s["goals"] == 1 and s["assists"] == 1
    assert s["xg"] == pytest.approx(0.88, abs=1e-2)


def test_build_player_matches_payload_unknown_player():
    assert _build_player_matches_payload(_make_stats_df(), "Nessuno") is None
    assert _build_player_matches_payload(None, "Martinez L.") is None
    assert _build_player_matches_payload(pd.DataFrame(), "Martinez L.") is None
