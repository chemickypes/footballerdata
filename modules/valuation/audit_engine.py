"""
Post-Draft League Audit & Power Rankings (Pilastro 4). Read-only report over
existing state/dataset data -- no dynamic feed dependency, since this is a
strategic season-long assessment, not a per-matchday lineup decision.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from modules.valuation.season_tracking import get_recent_form

FRAGILITY_THRESHOLD_DAYS = 60


def _player_row(pool_df, player_name):
    match = pool_df[pool_df["player"] == player_name]
    return match.iloc[0] if not match.empty else None


def _reweighted_value(pool_row, tracking_history):
    """Blends the original P50 with recent EWMA form if >=3 tracking records
    exist for the player; otherwise returns the original P50 unchanged."""
    original_p50 = float(pool_row.get("predicted_pts_p50", 0.0) or 0.0)
    recent_form = get_recent_form(tracking_history, pool_row["player"], n=3)
    if recent_form is None:
        return original_p50
    return 0.5 * original_p50 + 0.5 * recent_form


def _team_expected_points(team, pool_df, tracking_history):
    total = 0.0
    for item in team.get("roster", []):
        row = _player_row(pool_df, item.get("player"))
        if row is not None:
            total += _reweighted_value(row, tracking_history)
    return total


def _team_risk_capital(team, pool_df):
    risk_cr = 0
    for item in team.get("roster", []):
        row = _player_row(pool_df, item.get("player"))
        if row is not None and float(row.get("giorni_infortunio_3y", 0) or 0) > FRAGILITY_THRESHOLD_DAYS:
            risk_cr += int(item.get("price", 0) or 0)
    return risk_cr


def _best_worst_surplus(team, pool_df):
    best, worst = None, None
    for item in team.get("roster", []):
        row = _player_row(pool_df, item.get("player"))
        if row is None or "surplus_value_cr" not in row:
            continue
        surplus = float(row["surplus_value_cr"])
        if best is None or surplus > best[1]:
            best = (item["player"], surplus)
        if worst is None or surplus < worst[1]:
            worst = (item["player"], surplus)
    return best, worst


def _department_std(team, pool_df):
    """Standard deviation of spend across P/D/C/A -- lower means more balanced."""
    spend_by_role = {"P": 0, "D": 0, "C": 0, "A": 0}
    for item in team.get("roster", []):
        role = item.get("role")
        if role in spend_by_role:
            spend_by_role[role] += int(item.get("price", 0) or 0)
    return float(np.std(list(spend_by_role.values())))


def compute_audit(teams, player_pool_df, tracking_history):
    """Computes power ranking, risk capital, and badges for every team.

    teams: list of dicts shaped like state["teams"] (id, name, budget, roster).
    player_pool_df: dataset_finale.csv loaded as DataFrame.
    tracking_history: list of dicts from season_tracking.load_tracking_history().
    """
    entries = []
    for team in teams:
        budget = float(team.get("budget", 0) or 1)
        expected_points = _team_expected_points(team, player_pool_df, tracking_history)
        risk_cr = _team_risk_capital(team, player_pool_df)
        entries.append({
            "team_id": team["id"],
            "team_name": team.get("name", f"Squadra {team['id']}"),
            "expected_points": round(expected_points, 2),
            "risk_capital_cr": risk_cr,
            "risk_capital_pct": round((risk_cr / budget) * 100.0, 2) if budget else 0.0,
            "_department_std": _department_std(team, player_pool_df),
            "badges": [],
        })

    if entries:
        for team, entry in zip(teams, entries):
            badges = []
            best, worst = _best_worst_surplus(team, player_pool_df)
            if best:
                badges.append(f"Miglior Colpo VORP: {best[0]} (+{best[1]:.1f} cr)")
            if worst and worst[1] < 0:
                badges.append(f"Peggior Overpay: {worst[0]} ({worst[1]:.1f} cr)")
            entry["badges"] = badges

        min_std = min(e["_department_std"] for e in entries)
        for entry in entries:
            if entry["_department_std"] == min_std:
                entry["badges"].append("Most Balanced Squad")

        points_sorted = sorted(entries, key=lambda e: e["expected_points"], reverse=True)
        risk_sorted = sorted(entries, key=lambda e: e["risk_capital_cr"], reverse=True)
        top3_points_ids = {e["team_id"] for e in points_sorted[:3]}
        top3_risk_ids = {e["team_id"] for e in risk_sorted[:3]}
        for entry in entries:
            if entry["team_id"] in top3_points_ids and entry["team_id"] in top3_risk_ids:
                entry["badges"].append("Glass Cannon")

        for entry in entries:
            del entry["_department_std"]

    return sorted(entries, key=lambda e: e["expected_points"], reverse=True)
