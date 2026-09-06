"""Trade Machine: evaluates trades via static value and optional live lineup."""
from itertools import combinations

from modules.lineup.lineup_solver import solve_lineup

ROLE_TARGET = {"P": 3, "D": 8, "C": 8, "A": 6}
NEED_MULTIPLIER = 1.2
SURPLUS_MULTIPLIER = 0.8


def _player_value(pool_df, player_name):
    match = pool_df[pool_df["player"] == player_name]
    if match.empty:
        return None
    row = match.iloc[0]
    return float(row.get("predicted_pts_p50", 0.0) or 0.0) + float(row.get("vorp_points", 0.0) or 0.0)


def _role_counts(roster):
    counts = {}
    for p in roster:
        counts[p["role"]] = counts.get(p["role"], 0) + 1
    return counts


def _role_multiplier(role, role_counts):
    count = role_counts.get(role, 0)
    return NEED_MULTIPLIER if count < ROLE_TARGET.get(role, 0) else SURPLUS_MULTIPLIER


def _value_evaluation(team_a_roster, players_out, team_b_roster, players_in, player_pool_df):
    for name in players_out + players_in:
        if _player_value(player_pool_df, name) is None:
            return None, None, {"error": "player_not_found", "message": f"Giocatore non trovato nel dataset: {name}"}
    def _role_of(name, roster):
        for p in roster:
            if p["player"] == name:
                return p["role"]
        return None
    team_a_before_counts = _role_counts(team_a_roster)
    team_a_after_removal = [p for p in team_a_roster if p["player"] not in players_out]
    team_a_after_removal_counts = _role_counts(team_a_after_removal)
    a_out_value = 0.0
    for name in players_out:
        role = _role_of(name, team_a_roster)
        raw = _player_value(player_pool_df, name)
        a_out_value += raw * _role_multiplier(role, team_a_before_counts)
    a_in_value = 0.0
    for name in players_in:
        role = _role_of(name, team_b_roster)
        raw = _player_value(player_pool_df, name)
        a_in_value += raw * _role_multiplier(role, team_a_after_removal_counts)
    team_a_delta = a_in_value - a_out_value
    team_b_before_counts = _role_counts(team_b_roster)
    team_b_after_removal = [p for p in team_b_roster if p["player"] not in players_in]
    team_b_after_removal_counts = _role_counts(team_b_after_removal)
    b_out_value = 0.0
    for name in players_in:
        role = _role_of(name, team_b_roster)
        raw = _player_value(player_pool_df, name)
        b_out_value += raw * _role_multiplier(role, team_b_before_counts)
    b_in_value = 0.0
    for name in players_out:
        role = _role_of(name, team_a_roster)
        raw = _player_value(player_pool_df, name)
        b_in_value += raw * _role_multiplier(role, team_b_after_removal_counts)
    team_b_delta = b_in_value - b_out_value
    return team_a_delta, team_b_delta, None


def _apply_trade(roster, players_removed, players_added_from_other_roster, other_roster):
    roster_names = {p["player"] for p in roster}
    other_names = {p["player"] for p in other_roster}
    missing_removed = [name for name in players_removed if name not in roster_names]
    missing_added = [name for name in players_added_from_other_roster if name not in other_names]
    if missing_removed or missing_added:
        return {"error": "invalid_trade_players", "message": "Some trade players are not present in the expected roster.", "missing_players_out": missing_removed, "missing_players_in": missing_added}
    remaining = [p for p in roster if p["player"] not in players_removed]
    added_entries = [p for p in other_roster if p["player"] in players_added_from_other_roster]
    return remaining + added_entries


def evaluate_trade(team_a_roster, players_out, team_b_roster, players_in, player_pool_df, overlay):
    """Evaluate a proposed trade with static value and optional live lineup deltas."""
    roster_error = _apply_trade(team_a_roster, players_out, [], team_b_roster)
    if isinstance(roster_error, dict):
        return roster_error
    roster_error = _apply_trade(team_b_roster, players_in, [], team_a_roster)
    if isinstance(roster_error, dict):
        return roster_error
    team_a_delta, team_b_delta, error = _value_evaluation(team_a_roster, players_out, team_b_roster, players_in, player_pool_df)
    if error:
        return error

    live_eval = {"available": False, "team_a_delta_xpts": None, "team_b_delta_xpts": None, "message": ""}
    if overlay is not None and overlay.get("available", True) is not False:
        team_a_post = _apply_trade(team_a_roster, players_out, players_in, team_b_roster)
        team_b_post = _apply_trade(team_b_roster, players_in, players_out, team_a_roster)

        pre_a = solve_lineup(team_a_roster, overlay)
        post_a = solve_lineup(team_a_post, overlay)
        pre_b = solve_lineup(team_b_roster, overlay)
        post_b = solve_lineup(team_b_post, overlay)
        for result in (pre_a, post_a, pre_b, post_b):
            if not result.get("success"):
                return {"error": result.get("error", "feed_unavailable"), "message": result.get("message", "Formazione non calcolabile.")}
        live_eval = {"available": True, "team_a_delta_xpts": round(post_a["total_xpts"] - pre_a["total_xpts"], 2), "team_b_delta_xpts": round(post_b["total_xpts"] - pre_b["total_xpts"], 2), "message": ""}
    else:
        live_eval["message"] = "Dati in tempo reale non disponibili: valutazione limitata al valore statico."

    return {"value_evaluation": {"team_a_delta": round(team_a_delta, 2), "team_b_delta": round(team_b_delta, 2)}, "live_lineup_evaluation": live_eval}


def find_winwin_trades(my_roster, opponent_roster, player_pool_df, max_per_side=3, top_n=10):
    """Find trade combinations that strictly improve both sides by static value."""
    my_names = [p["player"] for p in my_roster]
    opp_names = [p["player"] for p in opponent_roster]
    candidates = []
    for out_size in range(1, max_per_side + 1):
        for in_size in range(1, max_per_side + 1):
            for out_combo in combinations(my_names, out_size):
                for in_combo in combinations(opp_names, in_size):
                    team_a_delta, team_b_delta, error = _value_evaluation(my_roster, list(out_combo), opponent_roster, list(in_combo), player_pool_df)
                    if error:
                        continue
                    if team_a_delta > 0 and team_b_delta > 0:
                        candidates.append({"players_out": list(out_combo), "players_in": list(in_combo), "my_delta": round(team_a_delta, 2), "opponent_delta": round(team_b_delta, 2), "combined_delta": round(team_a_delta + team_b_delta, 2)})
    return sorted(candidates, key=lambda c: c["combined_delta"], reverse=True)[:top_n]
