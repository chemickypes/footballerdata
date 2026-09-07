import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ingestion.dynamic.utils import normalize_name
from modules.lineup.lineup_solver import solve_lineup, FORMATIONS

SAMPLE_ROSTER = [
    {"player": "Portiere1", "role": "P", "team": "Inter"},
    {"player": "Diff1", "role": "D", "team": "Milan"},
    {"player": "Diff2", "role": "D", "team": "Roma"},
    {"player": "Diff3", "role": "D", "team": "Napoli"},
    {"player": "Cent1", "role": "C", "team": "Lazio"},
    {"player": "Cent2", "role": "C", "team": "Atalanta"},
    {"player": "Cent3", "role": "C", "team": "Fiorentina"},
    {"player": "Att1", "role": "A", "team": "Juventus"},
    {"player": "Att2", "role": "A", "team": "Torino"},
    {"player": "Att3", "role": "A", "team": "Bologna"},
    {"player": "Riserva1", "role": "D", "team": "Genoa"},
]


def test_solve_lineup_fails_when_overlay_none():
    result = solve_lineup(SAMPLE_ROSTER, overlay=None)
    assert result["success"] is False
    assert result["error"] == "feed_unavailable"


def _player_key(team, name, role):
    team_slug = normalize_name(str(team)).replace(" ", "_")
    return f"{team_slug}_{normalize_name(name).replace(' ', '_')}_{str(role).lower()}"


def _make_overlay(roster, xpts_by_player, statuses=None):
    statuses = statuses or {}
    players = {}
    for item in roster:
        name = item["player"]
        if name not in xpts_by_player:
            continue
        key = _player_key(item.get("team", ""), name, item["role"])
        players[key] = {"name": name, "xpts": xpts_by_player[name], "status": statuses.get(name, "OK")}
    return {"matchday": 4, "season": "2026/2027", "players": players}


def test_solve_lineup_picks_best_formation_with_full_roster():
    roster = [
        {"player": "GK", "role": "P", "team": "T"},
        *[{"player": f"D{i}", "role": "D", "team": "T"} for i in range(5)],
        *[{"player": f"C{i}", "role": "C", "team": "T"} for i in range(5)],
        *[{"player": f"A{i}", "role": "A", "team": "T"} for i in range(3)],
    ]
    xpts = {"GK": 5.0}
    xpts.update({f"D{i}": 4.0 + i * 0.1 for i in range(5)})
    xpts.update({f"C{i}": 6.0 + i * 0.1 for i in range(5)})
    xpts.update({f"A{i}": 7.0 + i * 0.1 for i in range(3)})
    overlay = _make_overlay(roster, xpts)

    result = solve_lineup(roster, overlay)

    assert result["success"] is True
    assert result["formation"] in FORMATIONS
    assert len(result["starters"]) == 11
    assert result["total_xpts"] > 0


def test_solve_lineup_excludes_injured_players():
    roster = [
        {"player": "GK", "role": "P", "team": "T"},
        *[{"player": f"D{i}", "role": "D", "team": "T"} for i in range(5)],
        *[{"player": f"C{i}", "role": "C", "team": "T"} for i in range(5)],
        *[{"player": f"A{i}", "role": "A", "team": "T"} for i in range(3)],
    ]
    xpts = {"GK": 5.0}
    xpts.update({f"D{i}": 4.0 for i in range(5)})
    xpts.update({f"C{i}": 6.0 for i in range(5)})
    xpts.update({f"A{i}": 99.0 if i == 0 else 7.0 for i in range(3)})
    overlay = _make_overlay(roster, xpts, statuses={"A0": "INFORTUNATO"})

    result = solve_lineup(roster, overlay)

    assert result["success"] is True
    starter_names = {s["player"] for s in result["starters"]}
    bench_names = {s["player"] for s in result["bench"]}
    assert "A0" not in starter_names
    assert "A0" not in bench_names  # excluded entirely, not just benched


def test_solve_lineup_no_feasible_formation_with_too_few_players():
    roster = [
        {"player": "GK", "role": "P", "team": "T"},
        {"player": "D0", "role": "D", "team": "T"},
    ]
    overlay = _make_overlay(roster, {"GK": 5.0, "D0": 4.0})

    result = solve_lineup(roster, overlay)

    assert result["success"] is False
    assert result["error"] == "no_feasible_formation"


def test_solve_lineup_empty_roster_returns_error_not_exception():
    overlay = _make_overlay([], {"X": 1.0})
    result = solve_lineup([], overlay)
    assert result["success"] is False
