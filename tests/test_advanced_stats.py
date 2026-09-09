#!/usr/bin/env python3
"""
Unit tests for stage 14 (advanced season stats via Sofascore) and the
/api/player_advanced payload builder. No live network calls.
"""
import importlib
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

stage14 = importlib.import_module("core.ingestion.static.14_scrape_advanced_stats")

from core.ingestion.static import sofascore_api
from web.matches_api import _player_advanced_response


SAMPLE_FW = {
    "minutesPlayed": 270, "appearances": 3, "matchesStarted": 3, "rating": 7.03,
    "goals": 2, "assists": 0, "expectedGoals": 1.5, "expectedAssists": 0.18,
    "totalShots": 9, "shotsOnTarget": 4, "keyPasses": 3, "bigChancesCreated": 1,
    "accurateFinalThirdPasses": 12, "accurateCrosses": 2, "accurateLongBalls": 5,
    "touches": 90, "successfulDribbles": 5, "totalContest": 11,
    "successfulDribblesPercentage": 45.5, "accuratePassesPercentage": 79.0,
    "totalDuelsWonPercentage": 50.0, "tacklesWonPercentage": 60.0,
    "aerialDuelsWonPercentage": 33.3, "accurateLongBallsPercentage": 55.0,
    "tackles": 2, "interceptions": 1, "clearances": 0, "outfielderBlocks": 0,
    "aerialDuelsWon": 1, "aerialLost": 2, "ballRecovery": 8,
    "possessionLost": 30, "possessionWonAttThird": 2, "dispossessed": 3,
    "wasFouled": 4, "fouls": 1, "offsides": 1, "dribbledPast": 2,
    "yellowCards": 1, "redCards": 0, "yellowRedCards": 0, "directRedCards": 0,
    "errorLeadToShot": 0, "errorLeadToGoal": 0,
}

SAMPLE_GK = {
    "minutesPlayed": 270, "appearances": 3, "matchesStarted": 3, "rating": 7.1,
    "saves": 11, "savesCaught": 4, "savesParried": 7, "highClaims": 3,
    "punches": 1, "goalsPrevented": 1.2, "cleanSheet": 1, "goalsConceded": 3,
    "penaltySave": 0, "crossesNotClaimed": 1, "runsOut": 2,
    "accuratePassesPercentage": 70.0, "accurateLongBallsPercentage": 40.0,
    "yellowCards": 0, "redCards": 0, "yellowRedCards": 0, "directRedCards": 0,
}


def test_curate_forward():
    c = stage14.curate_statistics(SAMPLE_FW, is_keeper=False)
    assert c["minutes"] == 270 and c["appearances"] == 3
    assert c["cards"] == {"yellow": 1, "red": 0, "yellow_red": 0, "direct_red": 0}
    assert c["totals"]["goals"] == 2 and c["totals"]["xg"] == 1.5
    assert "saves" not in c["totals"]  # keeper-only keys escluse per i non portieri
    assert c["per90"]["goals_per90"] == pytest.approx(2 / 270 * 90, abs=0.01)
    assert c["per90"]["xg_per90"] == pytest.approx(0.5, abs=0.01)
    assert c["pcts"]["passes_pct"] == pytest.approx(79.0)
    assert c["rating"] == pytest.approx(7.03)


def test_curate_keeper():
    c = stage14.curate_statistics(SAMPLE_GK, is_keeper=True)
    assert c["totals"]["saves"] == 11
    assert c["totals"]["goals_prevented"] == pytest.approx(1.2)
    assert c["per90"]["saves_per90"] == pytest.approx(11 / 270 * 90, abs=0.01)
    # un portiere NON riceve le metriche da attaccante per-90 (goals assenti nel campione GK)
    assert "goals_per90" not in c["per90"]


def test_curate_low_minutes_no_per90():
    raw = dict(SAMPLE_FW, minutesPlayed=20, appearances=1, matchesStarted=0)
    c = stage14.curate_statistics(raw, is_keeper=False)
    assert c["per90"] is None


def test_percentile_of():
    assert stage14.percentile_of([1, 2, 3, 4], 3) == 75.0  # sotto+pari = 3/4
    assert stage14.percentile_of([1, 2], 0.5) == 0.0
    assert stage14.percentile_of([2, 2], 2) == 100.0  # pari valore = non meglio di te
    assert stage14.percentile_of([1, 2], None) is None
    assert stage14.percentile_of([], 5) is None


def test_compute_percentiles_outfield_vs_pool():
    mine = stage14.curate_statistics(SAMPLE_FW, is_keeper=False)
    peer = stage14.curate_statistics(dict(SAMPLE_FW, goals=0, expectedGoals=0.3,
                                          accuratePassesPercentage=60.0), is_keeper=False)
    stage14.compute_percentiles(mine, [peer], role_key="outfield")
    assert mine["percentiles"]["goals_per90"] == 100.0
    assert mine["percentiles"]["xg_per90"] == 100.0
    assert mine["percentiles"]["passes_pct"] == 100.0
    # metrica non-percentile non presente
    assert "fouls" not in mine["percentiles"]


def test_compute_percentiles_keeper_goals_prevented():
    mine = stage14.curate_statistics(SAMPLE_GK, is_keeper=True)
    peer = stage14.curate_statistics(dict(SAMPLE_GK, goalsPrevented=-0.5), is_keeper=True)
    stage14.compute_percentiles(mine, [peer], role_key="keeper")
    assert mine["percentiles"]["goals_prevented"] == 100.0
    assert mine["percentiles"]["saves_per90"] == 100.0
    # chiavi outfield escluse per i portieri
    assert "goals_per90" not in mine["percentiles"]
    assert "tackles_per90" not in mine["percentiles"]


def test_get_player_season_statistics_parses():
    resp = {"statistics": {"goals": 2, "minutesPlayed": 270}}
    from unittest.mock import patch
    with patch.object(sofascore_api, "fetch_with_retry") as mock_fetch:
        mock_fetch.return_value.json.return_value = resp
        stats = sofascore_api.get_player_season_statistics(823984, season_id=95836)
    assert stats == {"goals": 2, "minutesPlayed": 270}


def test_harvest_and_incremental():
    calls = []

    def fake_fetch(pid, season_id):
        calls.append(pid)
        return dict(SAMPLE_FW)

    pairs = [("Martinez L.", 823984), ("Thuram", 555)]
    fetched, n_ok, n_fail = stage14.harvest(pairs, {"Martinez L.": "A", "Thuram": "A"},
                                            95836, fetcher=fake_fetch, rate_limit_sec=0)
    assert n_ok == 2 and n_fail == 0
    assert fetched[("Martinez L.", 823984)]["role"] == "A"
    assert calls == [823984, 555]

    players = stage14.resolve_players({name: [e] for (name, pid), e in fetched.items()})
    assert players["Martinez L."]["sofascore_player_id"] == 823984
    assert players["Martinez L."]["checked_ids"] == [823984]
    assert "duplicate_ids" not in players["Martinez L."]


def test_resolve_duplicates_keeps_max_minutes():
    a = dict(stage14.curate_statistics(SAMPLE_FW, is_keeper=False),
             sofascore_player_id=153257, season_id=95836, minutes=250)
    b = dict(stage14.curate_statistics(dict(SAMPLE_FW, minutesPlayed=15), is_keeper=False),
             sofascore_player_id=962364, season_id=95836, minutes=15)
    players = stage14.resolve_players({"Di Lorenzo": [a, b]})
    entry = players["Di Lorenzo"]
    assert entry["sofascore_player_id"] == 153257
    assert entry["minutes"] == 250
    assert entry["checked_ids"] == [153257, 962364]
    assert entry["duplicate_ids"] == [{"id": 962364, "minutes": 15, "no_data": False}]

    # no_data cede a chi ha dati
    nd = {"sofascore_player_id": 1, "season_id": 95836, "no_data": True, "minutes": 0}
    real = dict(stage14.curate_statistics(SAMPLE_FW, is_keeper=False),
                sofascore_player_id=2, season_id=95836, minutes=270)
    players2 = stage14.resolve_players({"X": [nd, real]})
    assert players2["X"]["sofascore_player_id"] == 2

    # omonimi di squadre diverse: vince quello della squadra attesa dal dataset
    laz = dict(stage14.curate_statistics(dict(SAMPLE_FW, minutesPlayed=10), is_keeper=False),
               sofascore_player_id=273405, season_id=95836, minutes=10, team_code="LAZ")
    mon = dict(stage14.curate_statistics(SAMPLE_FW, is_keeper=False),
               sofascore_player_id=967747, season_id=95836, minutes=20, team_code="MON")
    players5 = stage14.resolve_players({"Lazzari": [laz, mon]}, expected_teams={"Lazzari": "LAZ"})
    assert players5["Lazzari"]["sofascore_player_id"] == 273405
    # squadra non in dataset -> fallback minuti
    players6 = stage14.resolve_players({"Lazzari": [laz, mon]})
    assert players6["Lazzari"]["sofascore_player_id"] == 967747

    # entry vecchia con lo stesso pid della nuova: vince la fresca (prima nel by_pid)
    stale = dict(a, minutes=999)  # vecchia entry corrotta, stesso pid
    fresh = dict(a, minutes=250)  # entry appena scaricata
    players3 = stage14.resolve_players({"Di Lorenzo": [fresh, stale]})
    assert players3["Di Lorenzo"]["minutes"] == 250


def test_build_todo_incremental():
    stats_df = pd.DataFrame([
        {"player": "Martinez L.", "sofascore_player_id": 823984},
        {"player": "Thuram", "sofascore_player_id": 555},
        {"player": float("nan"), "sofascore_player_id": 9},
    ])
    pairs = stage14.build_pairs(stats_df)
    assert pairs == [("Martinez L.", 823984), ("Thuram", 555)]

    existing = {"players": {"Martinez L.": {"season_id": 95836, "sofascore_player_id": 823984, "team_code": "INT"}}}
    todo = stage14.build_todo(pairs, existing, 95836, refresh=False)
    assert todo == [("Thuram", 555)]
    assert stage14.build_todo(pairs, existing, 95836, refresh=True) == pairs
    # stagione diversa -> riscarica
    assert stage14.build_todo(pairs, existing, 99999, refresh=False) == pairs


def test_build_todo_namesake_second_id_fetched_then_stable():
    # entry con primo id gia' raccolto ma omonimo non risolto (no duplicate_ids):
    # entrambe le coppie vengono riscaricate e poi la risoluzione stabilizza
    pairs = [("Di Lorenzo", 153257), ("Di Lorenzo", 962364)]
    existing = {"players": {"Di Lorenzo": {
        "season_id": 95836, "sofascore_player_id": 153257, "minutes": 250, "team_code": "NAP"}}}
    todo1 = stage14.build_todo(pairs, existing, 95836, refresh=False)
    assert todo1 == pairs

    # dopo il fetch e la risoluzione, entrambi gli id sono in checked_ids
    a = dict(stage14.curate_statistics(SAMPLE_FW, is_keeper=False),
             sofascore_player_id=153257, season_id=95836, minutes=250, team_code="NAP")
    b = dict(stage14.curate_statistics(dict(SAMPLE_FW, minutesPlayed=10), is_keeper=False),
             sofascore_player_id=962364, season_id=95836, minutes=10, team_code="NAP")
    players = stage14.resolve_players({"Di Lorenzo": [a, b]})
    existing2 = {"players": players}
    assert stage14.build_todo(pairs, existing2, 95836, refresh=False) == []

def test_build_todo_unrefolved_namesake_refetched():
    # entry con team_code e checked_ids completi MA senza duplicate_ids:
    # le coppie dell'omonimo vengono riscaricate per risolverlo
    pairs = [("Di Lorenzo", 153257), ("Di Lorenzo", 962364)]
    existing = {"players": {"Di Lorenzo": {
        "season_id": 95836, "sofascore_player_id": 962364, "minutes": 40,
        "team_code": "NAP", "checked_ids": [153257, 962364]}}}
    assert stage14.build_todo(pairs, existing, 95836, refresh=False) == pairs

    # con duplicate_ids registrati: stabile
    fixed = dict(existing["players"]["Di Lorenzo"],
                 sofascore_player_id=153257, minutes=270,
                 duplicate_ids=[{"id": 962364, "minutes": 40, "no_data": False}])
    existing2 = {"players": {"Di Lorenzo": fixed}}
    assert stage14.build_todo(pairs, existing2, 95836, refresh=False) == []


def test_apply_percentiles_skips_low_minutes():
    players = {
        "A": dict(stage14.curate_statistics(SAMPLE_FW, is_keeper=False), role="A",
                  minutes=270),
        "B": dict(stage14.curate_statistics(SAMPLE_FW, is_keeper=False), role="A",
                  minutes=10),
        "C": dict(stage14.curate_statistics(SAMPLE_GK, is_keeper=True), role="P",
                  minutes=270),
        "D": dict(stage14.curate_statistics(dict(SAMPLE_GK, goalsPrevented=-0.5),
                                            is_keeper=True), role="P", minutes=90),
    }
    stage14.apply_percentiles(players)
    # A: nessun pari ruolo (B sotto soglia) -> percentili vuoti
    assert players["A"]["percentiles"] == {}
    assert players["B"]["percentiles"] == {}
    # C: unico pari ruolo D (sotto nel pool) -> 100
    assert players["C"]["percentiles"]["goals_prevented"] == 100.0
    assert players["C"]["percentiles"]["saves_per90"] == 100.0
    assert players["D"]["percentiles"]["goals_prevented"] == 0.0

def test_resolve_team_match_keeps_old_unknown_team_entry():
    # entry vecchia (senza team_code, piu' minuti) vs fresca con team noto:
    # la vecchia non deve essere esclusa dai candidati
    old = dict(stage14.curate_statistics(SAMPLE_FW, is_keeper=False),
               sofascore_player_id=153257, season_id=95836, minutes=270,
               team_code=None)
    fresh = dict(stage14.curate_statistics(dict(SAMPLE_FW, minutesPlayed=40), is_keeper=False),
                 sofascore_player_id=962364, season_id=95836, minutes=40,
                 team_code="NAP")
    players = stage14.resolve_players({"Di Lorenzo": [fresh, old]},
                                      expected_teams={"Di Lorenzo": "NAP"})
    assert players["Di Lorenzo"]["sofascore_player_id"] == 153257
    assert players["Di Lorenzo"]["team_code"] is None

    # entry di squadra nota diversa: esclusa dai candidati
    other = dict(fresh, sofascore_player_id=967747, minutes=999, team_code="MON")
    players2 = stage14.resolve_players({"Lazzari": [old, other]},
                                       expected_teams={"Lazzari": "LAZ"})
    assert players2["Lazzari"]["sofascore_player_id"] == 153257

    # fail-fast su raffica di fallimenti
    def always_fail(pid, season_id):
        return None
    import pytest as _pytest
    with _pytest.raises(RuntimeError):
        stage14.harvest([("A", i) for i in range(10)], {}, 95836,
                        fetcher=always_fail, rate_limit_sec=0)


def test_player_advanced_response():
    data = {"players": {
        "Martinez L.": {
            "sofascore_player_id": 823984, "season_id": 95836, "role": "A",
            "minutes": 270, "appearances": 3, "matches_started": 3, "rating": 7.03,
            "cards": {"yellow": 1, "red": 0, "yellow_red": 0, "direct_red": 0},
            "totals": {"goals": 2}, "pcts": {"passes_pct": 79.0},
            "per90": {"goals_per90": 0.67}, "percentiles": {"goals_per90": 88.0},
        },
        "NoData Player": {"no_data": True, "season_id": 95836},
    }}
    payload = _player_advanced_response(data, "Martinez L.")
    assert payload["available"] is True
    assert payload["totals"]["goals"] == 2
    assert payload["percentiles"]["goals_per90"] == 88.0
    assert payload["cards"]["yellow"] == 1

    assert _player_advanced_response(data, "NoData Player") is None
    assert _player_advanced_response(data, "Sconosciuto") is None
    assert _player_advanced_response(None, "Martinez L.") is None
