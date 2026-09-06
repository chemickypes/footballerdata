import os, sys
import pandas as pd
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.trades.trade_analyzer import evaluate_trade, find_winwin_trades, _value_evaluation
from pipeline.dynamic.utils import normalize_name

def _key(team, name, role): return f"{normalize_name(team).replace(' ', '_')}_{normalize_name(name).replace(' ', '_')}_{role.lower()}"
def _overlay(roster, xpts):
    return {"matchday": 4, "season": "2026/2027", "players": {_key(p["team"], p["player"], p["role"]): {"name": p["player"], "xpts": xpts[p["player"]], "status": "OK"} for p in roster if p["player"] in xpts}, "available": True}

def test_evaluate_trade_value_evaluation_one_for_one():
    pool = pd.DataFrame([{"player": "Malen", "role": "A", "predicted_pts_p50": 8.0, "vorp_points": 3.0}, {"player": "DifensoreX", "role": "D", "predicted_pts_p50": 5.0, "vorp_points": 2.0}])
    a = [{"player": "Malen", "role": "A"}]; b = [{"player": "DifensoreX", "role": "D"}]
    res = evaluate_trade(a, ["Malen"], b, ["DifensoreX"], pool, overlay=None)
    assert res["value_evaluation"]["team_a_delta"] == pytest.approx(-4.8)
    assert res["value_evaluation"]["team_b_delta"] == pytest.approx(4.8)

def test_evaluate_trade_invalid_trade_players_is_rejected():
    pool = pd.DataFrame([{"player": "Malen", "role": "A", "predicted_pts_p50": 8.0, "vorp_points": 3.0}, {"player": "DifensoreX", "role": "D", "predicted_pts_p50": 5.0, "vorp_points": 2.0}])
    a = [{"player": "Malen", "role": "A"}]; b = [{"player": "DifensoreX", "role": "D"}]
    assert evaluate_trade(a, ["NotOnRoster"], b, ["DifensoreX"], pool, overlay=None)["error"] == "invalid_trade_players"

def test_evaluate_trade_returns_error_for_unknown_player():
    pool = pd.DataFrame([{"player": "Malen", "role": "A", "predicted_pts_p50": 8.0, "vorp_points": 3.0}])
    a = [{"player": "Malen", "role": "A"}]; b = [{"player": "DifensoreX", "role": "D"}]
    assert evaluate_trade(a, ["Malen"], b, ["DifensoreX"], pool, overlay=None)["error"] == "player_not_found"

def test_find_winwin_trades_returns_positive_sorted_results():
    pool = pd.DataFrame([
        {"player": "A1", "role": "A", "predicted_pts_p50": 10.0, "vorp_points": 0.0},
        {"player": "A2", "role": "A", "predicted_pts_p50": 8.0, "vorp_points": 0.0},
        {"player": "D1", "role": "D", "predicted_pts_p50": 9.0, "vorp_points": 0.0},
        {"player": "D2", "role": "D", "predicted_pts_p50": 7.0, "vorp_points": 0.0},
    ])
    my_roster = [{"player": "A1", "role": "A"}, {"player": "A2", "role": "A"}, {"player": "A3", "role": "A"}, {"player": "A4", "role": "A"}, {"player": "A5", "role": "A"}, {"player": "A6", "role": "A"}, {"player": "D1", "role": "D"}, {"player": "D2", "role": "D"}]
    opp_roster = [{"player": "D3", "role": "D"}, {"player": "D4", "role": "D"}, {"player": "D5", "role": "D"}, {"player": "D6", "role": "D"}, {"player": "D7", "role": "D"}, {"player": "D8", "role": "D"}, {"player": "D9", "role": "D"}, {"player": "D10", "role": "D"}]
    pool = pd.concat([pool, pd.DataFrame([{"player": f"A{i}", "role": "A", "predicted_pts_p50": 4.0 + i, "vorp_points": 0.0} for i in range(3, 7)] + [{"player": f"D{i}", "role": "D", "predicted_pts_p50": 10.0 + i, "vorp_points": 0.0} for i in range(3, 11)])], ignore_index=True)
    results = find_winwin_trades(my_roster, opp_roster, pool, max_per_side=1, top_n=10)
    assert results and all(x["my_delta"] > 0 and x["opponent_delta"] > 0 for x in results)
    assert [x["combined_delta"] for x in results] == sorted([x["combined_delta"] for x in results], reverse=True)

def test_find_winwin_trades_respects_top_n_limit():
    pool = pd.DataFrame([{"player": f"A{i}", "role": "A", "predicted_pts_p50": 4.0 + i, "vorp_points": 0.0} for i in range(1, 7)] + [{"player": f"D{i}", "role": "D", "predicted_pts_p50": 10.0 + i, "vorp_points": 0.0} for i in range(1, 7)])
    my_roster = [{"player": f"A{i}", "role": "A"} for i in range(1, 7)] + [{"player": "D1", "role": "D"}, {"player": "D2", "role": "D"}]
    opp_roster = [{"player": f"D{i}", "role": "D"} for i in range(1, 7)] + [{"player": "A1", "role": "A"}, {"player": "A2", "role": "A"}]
    assert len(find_winwin_trades(my_roster, opp_roster, pool, max_per_side=1, top_n=2)) == 2

def test_evaluate_trade_live_evaluation_valid_overlay():
    team_a = [{"player": "GK", "role": "P", "team": "T"}, {"player": "DA", "role": "D", "team": "T"}, {"player": "DB", "role": "D", "team": "T"}, {"player": "DC", "role": "D", "team": "T"}, {"player": "CA", "role": "C", "team": "T"}, {"player": "CB", "role": "C", "team": "T"}, {"player": "CC", "role": "C", "team": "T"}, {"player": "AA", "role": "A", "team": "T"}, {"player": "AB", "role": "A", "team": "T"}, {"player": "AC", "role": "A", "team": "T"}]
    team_b = [{"player": "GK2", "role": "P", "team": "U"}, {"player": "D1", "role": "D", "team": "U"}, {"player": "D2", "role": "D", "team": "U"}, {"player": "D3", "role": "D", "team": "U"}, {"player": "C1", "role": "C", "team": "U"}, {"player": "C2", "role": "C", "team": "U"}, {"player": "C3", "role": "C", "team": "U"}, {"player": "A1", "role": "A", "team": "U"}, {"player": "A2", "role": "A", "team": "U"}, {"player": "A3", "role": "A", "team": "U"}]
    pool = pd.DataFrame([{ "player": p["player"], "role": p["role"], "predicted_pts_p50": 1.0, "vorp_points": 0.0} for p in team_a + team_b])
    overlay = _overlay(team_a + team_b, {p["player"]: 5.0 for p in team_a + team_b})
    result = evaluate_trade(team_a, ["AA"], team_b, ["D1"], pool, overlay)
    assert result["error"] == "no_feasible_formation"

def test_evaluate_trade_propagates_feed_unavailable_error():
    pool = pd.DataFrame([{"player": "Malen", "role": "A", "predicted_pts_p50": 8.0, "vorp_points": 3.0}, {"player": "DifensoreX", "role": "D", "predicted_pts_p50": 5.0, "vorp_points": 2.0}])
    a = [{"player": "Malen", "role": "A"}]; b = [{"player": "DifensoreX", "role": "D"}]
    assert evaluate_trade(a, ["Malen"], b, ["DifensoreX"], pool, overlay={"available": False})["live_lineup_evaluation"]["available"] is False

def test_evaluate_trade_propagates_no_feasible_formation_error():
    team_a = [{"player": "GK", "role": "P", "team": "T"}, {"player": "D1", "role": "D", "team": "T"}]
    team_b = [{"player": "GK2", "role": "P", "team": "U"}, {"player": "D2", "role": "D", "team": "U"}]
    pool = pd.DataFrame([{"player": p["player"], "role": p["role"], "predicted_pts_p50": 1.0, "vorp_points": 0.0} for p in team_a + team_b])
    overlay = _overlay(team_a + team_b, {p["player"]: 5.0 for p in team_a + team_b})
    assert evaluate_trade(team_a, ["D1"], team_b, ["D2"], pool, overlay)["error"] == "no_feasible_formation"
