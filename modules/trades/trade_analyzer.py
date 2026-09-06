"""
Trade Machine: evaluates trades via static value and optional live lineup.
"""
from itertools import combinations

from modules.common.data_provider import is_overlay_real
from modules.lineup.lineup_solver import solve_lineup


def _player_value(pool_df, player_name):
    match = pool_df[pool_df["player"] == player_name]
    if match.empty:
        return None
    row = match.iloc[0]
    return float(row.get("predicted_pts_p50", 0.0) or 0.0) + float(row.get("vorp_points", 0.0) or 0.0)


def _value_evaluation(players_out, players_in, player_pool_df):
    for name in players_out + players_in:
        if _player_value(player_pool_df, name) is None:
            return None, None, {"error": "player_not_found", "message": f"Giocatore non trovato nel dataset: {name}"}
    out_value = sum(_player_value(player_pool_df, n) for n in players_out)
    in_value = sum(_player_value(player_pool_df, n) for n in players_in)
    return in_value - out_value, out_value - in_value, None


def _apply_trade(roster, players_removed, players_added_from_other_roster, other_roster):
    remaining = [p for p in roster if p["player"] not in players_removed]
    added_entries = [p for p in other_roster if p["player"] in players_added_from_other_roster]
    return remaining + added_entries


def evaluate_trade(team_a_roster, players_out, team_b_roster, players_in, player_pool_df, overlay):
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
        if not all(r.get("success") for r in (pre_a, post_a, pre_b, post_b)):
            return {"error": "feed_unavailable", "message": "Formazione non calcolabile per feed non disponibile."}
        live_eval = {"available": True, "team_a_delta_xpts": round(post_a["total_xpts"] - pre_a["total_xpts"], 2), "team_b_delta_xpts": round(post_b["total_xpts"] - pre_b["total_xpts"], 2), "message": ""}
    else:
        live_eval["message"] = "Dati in tempo reale non disponibili: valutazione limitata al valore statico."

    return {"value_evaluation": {"team_a_delta": round(team_a_delta, 2), "team_b_delta": round(team_b_delta, 2)}, "live_lineup_evaluation": live_eval}


def find_winwin_trades(my_roster, opponent_roster, player_pool_df, max_per_side=3, top_n=10):
    my_names = [p["player"] for p in my_roster]
    opp_names = [p["player"] for p in opponent_roster]
    candidates = []
    for out_size in range(1, max_per_side + 1):
        for in_size in range(1, max_per_side + 1):
            for out_combo in combinations(my_names, out_size):
                for in_combo in combinations(opp_names, in_size):
                    team_a_delta, team_b_delta, error = _value_evaluation(list(out_combo), list(in_combo), player_pool_df)
                    if error:
                        continue
                    if team_a_delta >= 0 and team_b_delta >= 0:
                        candidates.append({"players_out": list(out_combo), "players_in": list(in_combo), "my_delta": round(team_a_delta, 2), "opponent_delta": round(team_b_delta, 2), "combined_delta": round(team_a_delta + team_b_delta, 2)})
    return sorted(candidates, key=lambda c: c["combined_delta"], reverse=True)[:top_n]
