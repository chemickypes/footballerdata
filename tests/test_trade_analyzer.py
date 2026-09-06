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
    result = evaluate_trade(TEAM_A_ROSTER, ["Malen"], TEAM_B_ROSTER, ["DifensoreX"], POOL, overlay=None)
    assert result["value_evaluation"]["team_a_delta"] == pytest.approx(-4.0)
    assert result["value_evaluation"]["team_b_delta"] == pytest.approx(4.0)


def test_evaluate_trade_returns_error_for_unknown_player():
    result = evaluate_trade(TEAM_A_ROSTER, ["NonEsiste"], TEAM_B_ROSTER, ["DifensoreX"], POOL, overlay=None)
    assert result["error"] == "player_not_found"


def test_evaluate_trade_live_evaluation_unavailable_when_overlay_none():
    result = evaluate_trade(TEAM_A_ROSTER, ["Malen"], TEAM_B_ROSTER, ["DifensoreX"], POOL, overlay=None)
    assert result["live_lineup_evaluation"]["available"] is False
    assert "value_evaluation" in result


def test_evaluate_trade_n_for_n_two_for_one():
    team_a_roster = [{"player": "Malen", "role": "A"}, {"player": "Krstovic", "role": "A"}]
    team_b_roster = [{"player": "DifensoreX", "role": "D"}]
    result = evaluate_trade(team_a_roster, ["Malen", "Krstovic"], team_b_roster, ["DifensoreX"], POOL, overlay=None)
    assert result["value_evaluation"]["team_a_delta"] == pytest.approx(-11.0)


def test_find_winwin_trades_filters_for_non_negative_both_sides():
    my_roster = [{"player": "Krstovic", "role": "A"}]
    opponent_roster = [{"player": "DifensoreY", "role": "D"}]
    assert find_winwin_trades(my_roster, opponent_roster, POOL, max_per_side=1, top_n=10) == []


def test_find_winwin_trades_returns_sorted_top_n():
    my_roster = [{"player": "DifensoreY", "role": "D"}]
    opponent_roster = [{"player": "Malen", "role": "A"}]
    assert find_winwin_trades(my_roster, opponent_roster, POOL, max_per_side=1, top_n=10) == []
