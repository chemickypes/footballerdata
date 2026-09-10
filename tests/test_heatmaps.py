#!/usr/bin/env python3
"""
Unit tests for stage 13 (season player heatmaps) and the /api/player_heatmap
payload builder. No live network calls.
"""
import importlib
import os
import sys
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

stage13 = importlib.import_module("core.ingestion.static.13_scrape_heatmaps")

from core.ingestion.static import sofascore_api
from web.matches_api import _player_heatmap_response


def test_points_to_grid_counts_and_bounds():
    grid = stage13.points_to_grid([{"x": 0, "y": 0}, {"x": 100, "y": 100}, {"x": 50, "y": 50},
                                   {"x": 50, "y": 50}])
    cols, rows = stage13.HEATMAP_GRID_COLS, stage13.HEATMAP_GRID_ROWS
    assert len(grid) == cols * rows
    # y Sofascore invertita: y=0 = linea inferiore -> riga ultima (basso-sinistra)
    assert grid[(rows - 1) * cols] == 1
    # x=100, y=100 -> alto-destra (clampato)
    assert grid[cols - 1] == 1
    # centro: y=50 -> cy_raw=10 -> riga 9
    center = (rows // 2 - 1) * cols + cols // 2
    assert grid[center] == 2


def test_points_to_grid_skips_invalid():
    grid = stage13.points_to_grid([{"x": 150, "y": 10}, {"x": 10, "y": -5},
                                   {"x": "abc", "y": 10}, {}, None])
    assert sum(grid) == 0


def test_add_grids():
    assert stage13.add_grids([1, 2, 3], [10, 20, 30]) == [11, 22, 33]


def test_build_todo_skips_unmatched_and_harvested():
    stats_df = pd.DataFrame([
        {"player": "Martinez L.", "sofascore_player_id": 823984, "event_id": 1.0,
         "minutes_played": 90, "round": 1},
        {"player": "Martinez L.", "sofascore_player_id": 823984, "event_id": 2.0,
         "minutes_played": 45, "round": 2},
        {"player": float("nan"), "sofascore_player_id": 923820, "event_id": 1.0,
         "minutes_played": 90, "round": 1},  # non matchato
        {"player": "Thuram", "sofascore_player_id": float("nan"), "event_id": 1.0,
         "minutes_played": 90, "round": 1},  # no id
        {"player": "Thuram", "sofascore_player_id": 555, "event_id": 3.0,
         "minutes_played": 10, "round": 3},
    ])
    data = {"grid": {"cols": 30, "rows": 20}, "players": {
        "Martinez L.": {"by_event": {
            # event 1 gia' raccolto (chiave stringa, round int/float CSV)
            "1": {"round": 1, "minutes": 90, "grid": [0] * 600},
        }, "matches": 1, "minutes": 90, "points": 10, "grid": [0] * 600},
    }}
    todo = stage13.build_todo(stats_df, data)
    pairs = [(t["player"], t["event_id"]) for t in todo]
    assert ("Martinez L.", 2) in pairs
    assert ("Martinez L.", 1) not in pairs  # gia' raccolto
    assert ("Thuram", 3) in pairs
    assert len(todo) == 2
    assert all(t["player_id"] > 0 for t in todo)
    assert all(t["round"] > 0 for t in todo)


def test_harvest_aggregates_and_by_event():
    def fake_fetcher(event_id, player_id):
        if player_id == 200:
            return []  # B: risposta valida ma vuota
        if event_id == 1:
            return [{"x": 10, "y": 10}, {"x": 12, "y": 14}, {"x": 80, "y": 50}]
        return []

    todo = [
        {"player": "A", "event_id": 1, "event_key": "1", "player_id": 100,
         "round": 1, "minutes": 90},
        {"player": "A", "event_id": 2, "event_key": "2", "player_id": 100,
         "round": 2, "minutes": 30},
        {"player": "B", "event_id": 1, "event_key": "1", "player_id": 200,
         "round": 1, "minutes": 90},
    ]
    with patch.object(stage13, "load_heatmaps") as mock_load, \
         patch.object(stage13, "save_heatmaps"):
        mock_load.return_value = {"grid": {"cols": 30, "rows": 20}, "players": {}}
        data, n_ok, n_fail = stage13.harvest(todo, fetcher=fake_fetcher, rate_limit_sec=0)

    assert n_ok == 3 and n_fail == 0
    a = data["players"]["A"]
    assert a["matches"] == 2
    assert a["minutes"] == 120
    assert a["points"] == 3
    assert set(a["by_event"].keys()) == {"1", "2"}
    assert a["by_event"]["1"]["round"] == 1
    assert sum(a["by_event"]["1"]["grid"]) == 3
    assert a["by_event"]["2"]["round"] == 2
    assert sum(a["grid"]) == 3  # aggregato derivato
    assert data["players"]["B"]["points"] == 0
    assert data["players"]["B"]["matches"] == 1


def test_recompute_aggregate_from_by_event():
    entry = {"by_event": {
        "1": {"round": 1, "minutes": 90, "grid": [1] + [0] * 599},
        "2": {"round": 2, "minutes": 45, "grid": [0] * 599 + [2]},
    }}
    stage13.recompute_aggregate(entry)
    assert entry["matches"] == 2
    assert entry["minutes"] == 135
    assert entry["points"] == 3
    assert entry["grid"][0] == 1 and entry["grid"][-1] == 2
    assert sum(entry["grid"]) == 3


def test_harvest_failure_not_marked():
    def fake_fetcher(event_id, player_id):
        return None  # fallimento rete

    todo = [{"player": "A", "event_id": 1, "player_id": 100, "minutes": 90}]
    with patch.object(stage13, "load_heatmaps") as mock_load, \
         patch.object(stage13, "save_heatmaps"):
        mock_load.return_value = {"grid": {"cols": 30, "rows": 20}, "players": {}}
        data, n_ok, n_fail = stage13.harvest(todo, fetcher=fake_fetcher, rate_limit_sec=0)

    assert n_ok == 0 and n_fail == 1
    assert "A" not in data["players"]  # da ritentare alla prossima esecuzione


def test_harvest_limit():
    todo = [{"player": f"P{i}", "event_id": i, "event_key": str(i), "player_id": i,
             "round": 1, "minutes": 1} for i in range(10)]
    with patch.object(stage13, "load_heatmaps") as mock_load, \
         patch.object(stage13, "save_heatmaps"):
        mock_load.return_value = {"grid": {"cols": 30, "rows": 20}, "players": {}}
        data, n_ok, _ = stage13.harvest(todo, fetcher=lambda e, p: [], rate_limit_sec=0, limit=3)
    assert n_ok == 3


def test_get_player_heatmap_parses_response():
    resp = {"heatmap": [{"x": 27, "y": 31}, {"x": 11, "y": 56}]}
    with patch.object(sofascore_api, "fetch_with_retry") as mock_fetch:
        mock_fetch.return_value.json.return_value = resp
        pts = sofascore_api.get_player_heatmap(16283050, 845291)
    assert pts == [{"x": 27, "y": 31}, {"x": 11, "y": 56}]


def test_get_player_heatmap_none_on_fetch_failure():
    with patch.object(sofascore_api, "fetch_with_retry", return_value=None):
        assert sofascore_api.get_player_heatmap(1, 2) is None


def test_player_heatmap_response():
    grid_a = [0] * 599 + [5]
    data = {"grid": {"cols": 30, "rows": 20}, "players": {
        "Martinez L.": {
            "by_event": {
                "101": {"round": 1, "minutes": 90, "grid": [1] + [0] * 599},
                "102": {"round": 2, "minutes": 45, "grid": [0] * 599 + [4]},
            },
            "grid": grid_a, "matches": 2, "minutes": 135, "points": 5,
        },
        "Zero Player": {"by_event": {}, "grid": [0] * 600, "matches": 0,
                        "minutes": 0, "points": 0},
    }}
    payload = _player_heatmap_response(data, "Martinez L.")
    assert payload["available"] is True
    assert payload["grid"] == {"cols": 30, "rows": 20}
    assert len(payload["cells"]) == 600
    assert payload["cells"][-1] == 5
    assert payload["points"] == 5 and payload["matches"] == 2
    assert payload["available_rounds"] == [1, 2]

    assert _player_heatmap_response(data, "Zero Player") is None
    assert _player_heatmap_response(data, "Sconosciuto") is None
    assert _player_heatmap_response(None, "Martinez L.") is None


def test_player_heatmap_response_round_slicing():
    data = {"grid": {"cols": 30, "rows": 20}, "players": {
        "Martinez L.": {
            "by_event": {
                "101": {"round": 1, "minutes": 90, "grid": [1] + [0] * 599},
                "102": {"round": 2, "minutes": 45, "grid": [0] * 599 + [4]},
                "103": {"round": 3, "minutes": 90, "grid": [0] * 300 + [7] + [0] * 299},
            },
            "grid": [1] + [0] * 299 + [7] + [0] * 298 + [4],
            "matches": 3, "minutes": 225, "points": 12,
        },
    }}
    # cumulativo fino alla G2: eventi 1+2
    p2 = _player_heatmap_response(data, "Martinez L.", until_round=2)
    assert p2["matches"] == 2
    assert p2["minutes"] == 135
    assert p2["points"] == 5
    assert p2["cells"][0] == 1 and p2["cells"][-1] == 4
    assert p2["available_rounds"] == [1, 2, 3]  # tutte le giornate esistenti

    # singola giornata 3
    p3 = _player_heatmap_response(data, "Martinez L.", single_round=3)
    assert p3["matches"] == 1
    assert p3["minutes"] == 90
    assert p3["points"] == 7

    # selezione senza dati -> None
    assert _player_heatmap_response(data, "Martinez L.", until_round=0) is None
    assert _player_heatmap_response(data, "Martinez L.", single_round=9) is None


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "player_heatmaps.json"
    data = {"grid": {"cols": 30, "rows": 20}, "players": {
        "A": {"by_event": {
            "1": {"round": 1, "minutes": 90, "grid": [0, 1, 2] + [0] * 597},
        }, "grid": [0, 1, 2] + [0] * 597, "matches": 1, "minutes": 90, "points": 3},
    }}
    stage13.save_heatmaps(data, str(path))
    loaded = stage13.load_heatmaps(str(path))
    assert loaded["players"]["A"]["by_event"]["1"]["grid"][1] == 1
    assert loaded["grid"]["cols"] == 30
