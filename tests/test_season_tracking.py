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
