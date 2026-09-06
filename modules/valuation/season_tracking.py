# modules/valuation/season_tracking.py
"""
Append-only JSONL tracking of per-matchday prediction vs. actual performance
(Pilastro 4 Audit Engine re-weighting). One record per player per concluded
matchday. Never used for model retraining -- only for a lightweight
re-weighting of predicted_pts_p50 in audit_engine.py.
"""
import json
import os


def append_matchday_record(path, matchday, player, predicted_pts_p50_original,
                            ewma_form_at_that_point, actual_score):
    """Appends one JSONL record. Creates parent directory if needed."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    record = {
        "matchday": matchday,
        "player": player,
        "predicted_pts_p50_original": predicted_pts_p50_original,
        "ewma_form_at_that_point": ewma_form_at_that_point,
        "actual_score": actual_score,
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_tracking_history(path):
    """Reads all valid JSONL records. Missing file -> []. Malformed lines are
    skipped individually so one corrupted row never breaks the whole read."""
    if not os.path.exists(path):
        return []

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def get_recent_form(history, player, n=3):
    """Average ewma_form_at_that_point over the last n records for player, in
    the order they appear in history (assumed chronological, since the file is
    append-only). Returns None if fewer than n records exist for that player,
    signaling audit_engine to skip re-weighting for this player."""
    player_records = [r for r in history if r.get("player") == player]
    if len(player_records) < n:
        return None
    recent = player_records[-n:]
    values = [r["ewma_form_at_that_point"] for r in recent if "ewma_form_at_that_point" in r]
    if len(values) < n:
        return None
    return sum(values) / len(values)
