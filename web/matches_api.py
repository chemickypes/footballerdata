"""
footballerdata — /api/matches + /api/player_matches endpoints
Serie A match results & schedule plus per-team recent form (stage-11 artifacts),
per-player match stats (stage-12), heatmaps (stage-13) and advanced season
stats (stage-14), from the data/ artifacts.
"""

import csv
import json
import os

import pandas as pd
from flask import Blueprint, jsonify, request

from web.config import PROJECT_ROOT

matches_bp = Blueprint("matches", __name__)

MATCH_RESULTS_CSV = os.path.join(PROJECT_ROOT, "data", "match_results.csv")
TEAM_FORM_JSON = os.path.join(PROJECT_ROOT, "data", "team_form.json")
PLAYER_MATCH_STATS_CSV = os.path.join(PROJECT_ROOT, "data", "player_match_stats.csv")
PLAYER_HEATMAPS_JSON = os.path.join(PROJECT_ROOT, "data", "player_heatmaps.json")
PLAYER_ADVANCED_JSON = os.path.join(PROJECT_ROOT, "data", "player_advanced.json")

FINISHED_STATUSES = {"FT", "AET", "PEN"}

# Sigla → nome display (inverso di core.config.TEAM_ABBR_MAP)
try:
    from core import config as _core_config
    _TEAM_DISPLAY = {v: k for k, v in _core_config.TEAM_ABBR_MAP.items()}
except Exception:
    _TEAM_DISPLAY = {}


def _int_or_none(value):
    try:
        if value is None or str(value).strip() in ("", "None", "nan"):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _team_display(code, fallback):
    return _TEAM_DISPLAY.get(code, fallback or code or "?")


def _build_payload(csv_path, form_path):
    """Costruisce il payload /api/matches dai file stage 11. None se il CSV manca/corrotto."""
    if not os.path.exists(csv_path):
        return None

    rounds = {}
    try:
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                rnd = _int_or_none(row.get("round"))
                if rnd is None:
                    continue
                home_code = (row.get("home_team_code") or "").strip() or None
                away_code = (row.get("away_team_code") or "").strip() or None
                rounds.setdefault(rnd, []).append({
                    "fixture_id": _int_or_none(row.get("fixture_id")),
                    "round": rnd,
                    "date": (row.get("date_utc") or "").strip() or None,
                    "home_team": row.get("home_team"),
                    "home_code": home_code,
                    "home_display": _team_display(home_code, row.get("home_team")),
                    "away_team": row.get("away_team"),
                    "away_code": away_code,
                    "away_display": _team_display(away_code, row.get("away_team")),
                    "home_score": _int_or_none(row.get("home_score")),
                    "away_score": _int_or_none(row.get("away_score")),
                    "ht_home_score": _int_or_none(row.get("ht_home_score")),
                    "ht_away_score": _int_or_none(row.get("ht_away_score")),
                    "status": (row.get("status") or "").strip() or None,
                    "finished": (row.get("status") or "").strip() in FINISHED_STATUSES,
                })
    except Exception:
        return None

    # Un CSV valido dello stage 11 contiene sempre tutte le fixture: zero
    # giornate parsate = file corrotto/troncato.
    if not rounds:
        return None

    team_form = {}
    try:
        with open(form_path, "r", encoding="utf-8") as f:
            team_form = json.load(f)
    except Exception:
        team_form = {}

    current_round = None
    for rnd in sorted(rounds):
        if any(m["finished"] for m in rounds[rnd]):
            current_round = rnd

    try:
        season_start = int(_core_config.API_FOOTBALL_SEASON)
        season_label = f"{season_start}/{(season_start + 1) % 100:02d}"
    except Exception:
        season_label = None

    return {
        "available": True,
        "season": season_label,
        "current_round": current_round,
        "rounds": [
            {
                "round": rnd,
                "matches": sorted(rounds[rnd], key=lambda m: (m["date"] or "")),
            }
            for rnd in sorted(rounds)
        ],
        "team_form": team_form,
    }


_cache = {"mtime": None, "payload": None}


def _load_payload():
    if not os.path.exists(MATCH_RESULTS_CSV):
        return None
    mtime = os.path.getmtime(MATCH_RESULTS_CSV)
    if _cache["payload"] is not None and _cache["mtime"] == mtime:
        return _cache["payload"]
    payload = _build_payload(MATCH_RESULTS_CSV, TEAM_FORM_JSON)
    if payload is not None:
        _cache["mtime"] = mtime
        _cache["payload"] = payload
    return payload


@matches_bp.route("/api/matches")
def api_matches():
    """Risultati e calendario Serie A + forma squadre (dagli artifact dello stage 11)."""
    payload = _load_payload()
    if payload is None:
        return jsonify({
            "available": False,
            "season": None,
            "current_round": None,
            "rounds": [],
            "team_form": {},
        })
    return jsonify(payload)


_pm_cache = {"mtime": None, "df": None}


def _load_pm_stats():
    if not os.path.exists(PLAYER_MATCH_STATS_CSV):
        return None
    mtime = os.path.getmtime(PLAYER_MATCH_STATS_CSV)
    if _pm_cache["df"] is not None and _pm_cache["mtime"] == mtime:
        return _pm_cache["df"]
    try:
        df = pd.read_csv(PLAYER_MATCH_STATS_CSV)
    except Exception:
        return None
    _pm_cache["mtime"] = mtime
    _pm_cache["df"] = df
    return df


def _fnum(v):
    try:
        if v is None or pd.isna(v):
            return None
        return round(float(v), 3)
    except (TypeError, ValueError):
        return None


def _build_player_matches_payload(df, player_name, limit=10):
    """Righe per-partita del giocatore (ultime `limit`, ordine cronologico inverso)
    + riepilogo. None se il giocatore non ha righe o il DataFrame e' vuoto."""
    if df is None or df.empty:
        return None
    rows = df[df["player"] == player_name]
    if rows.empty:
        return None

    rows = rows.sort_values(["round", "date_utc"], ascending=False).head(limit)

    def _match_row(r):
        opp = r.get("opponent_code")
        return {
            "round": int(r["round"]) if pd.notna(r.get("round")) else None,
            "date": r.get("date_utc"),
            "opponent": opp,
            "opponent_display": _team_display(opp, opp),
            "venue": r.get("venue"),
            "minutes": int(r["minutes_played"]) if pd.notna(r.get("minutes_played")) else 0,
            "rating": _fnum(r.get("rating")),
            "goals": int(r.get("goals") or 0),
            "assists": int(r.get("assists") or 0),
            "key_passes": int(r.get("key_passes") or 0),
            "shots": int(r.get("shots") or 0),
            "xg": _fnum(r.get("xg")),
            "xa": _fnum(r.get("xa")),
            "is_starter": bool(r.get("is_starter")),
        }

    all_rows = df[df["player"] == player_name]
    with_rating = all_rows[all_rows["rating"].notna()] if "rating" in all_rows.columns else all_rows.iloc[0:0]
    summary = {
        "played": int(len(all_rows)),
        "starts": int(all_rows["is_starter"].sum()) if "is_starter" in all_rows.columns else None,
        "minutes": int(all_rows["minutes_played"].sum()) if "minutes_played" in all_rows.columns else None,
        "avg_rating": round(float(with_rating["rating"].mean()), 2) if len(with_rating) else None,
        "goals": int(all_rows["goals"].sum()) if "goals" in all_rows.columns else 0,
        "assists": int(all_rows["assists"].sum()) if "assists" in all_rows.columns else 0,
        "xg": _fnum(all_rows["xg"].sum()) if "xg" in all_rows.columns else None,
        "xa": _fnum(all_rows["xa"].sum()) if "xa" in all_rows.columns else None,
    }

    return {
        "player": player_name,
        "available": True,
        "matches": [_match_row(r) for _, r in rows.iterrows()],
        "summary": summary,
    }


@matches_bp.route("/api/player_matches")
def api_player_matches():
    """Statistiche per-partita del giocatore (stage 12): ultime gare + riepilogo."""
    name = request.args.get("player", "").strip()
    if not name:
        return jsonify({"error": "player parameter required"}), 400

    df = _load_pm_stats()
    if df is None:
        return jsonify({"error": "player match stats not available (run stage 12)"}), 404

    payload = _build_player_matches_payload(df, name)
    if payload is None:
        return jsonify({"error": "no recorded matches for this player"}), 404
    return jsonify(payload)


_hm_cache = {"mtime": None, "data": None}


def _load_heatmaps():
    if not os.path.exists(PLAYER_HEATMAPS_JSON):
        return None
    mtime = os.path.getmtime(PLAYER_HEATMAPS_JSON)
    if _hm_cache["data"] is not None and _hm_cache["mtime"] == mtime:
        return _hm_cache["data"]
    try:
        with open(PLAYER_HEATMAPS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    _hm_cache["mtime"] = mtime
    _hm_cache["data"] = data
    return data


def _player_heatmap_response(data, player_name, until_round=None, single_round=None):
    """Payload heatmap per giocatore dal JSON stage 13, o None se assente/vuoto.

    without until_round/single_round: aggregato stagione completa.
    until_round=N: cumulativo delle giornate 1..N; single_round=N: solo la
    giornata N. Slicing per-evento dal dict by_event."""
    if not data:
        return None
    entry = (data.get("players") or {}).get(player_name)
    if not entry or not entry.get("points"):
        return None
    grid_meta = data.get("grid") or {}
    by_event = entry.get("by_event") or {}

    if until_round is not None or single_round is not None:
        selected = []
        for ev in by_event.values():
            rnd = ev.get("round") or 0
            if until_round is not None and rnd <= int(until_round):
                selected.append(ev.get("grid") or [])
            elif single_round is not None and rnd == int(single_round):
                selected.append(ev.get("grid") or [])
        if not selected:
            return None
        cols = grid_meta.get("cols", 30)
        rows = grid_meta.get("rows", 20)
        cells = [0] * (cols * rows)
        for g in selected:
            cells = [a + b for a, b in zip(cells, g)]
        matches = len(selected)
        minutes = sum(int(ev.get("minutes") or 0) for ev in by_event.values()
                      if (until_round is not None and (ev.get("round") or 0) <= int(until_round))
                      or (single_round is not None and (ev.get("round") or 0) == int(single_round)))
        return {
            "player": player_name,
            "available": True,
            "grid": {"cols": cols, "rows": rows},
            "cells": cells,
            "matches": matches,
            "minutes": minutes,
            "points": sum(cells),
            "available_rounds": sorted({int(ev.get("round") or 0)
                                        for ev in by_event.values() if ev.get("round")}),
        }

    return {
        "player": player_name,
        "available": True,
        "grid": {"cols": grid_meta.get("cols", 30), "rows": grid_meta.get("rows", 20)},
        "cells": entry.get("grid", []),
        "matches": entry.get("matches", 0),
        "minutes": entry.get("minutes", 0),
        "points": entry.get("points", 0),
        "available_rounds": sorted({int(ev.get("round") or 0)
                                    for ev in by_event.values() if ev.get("round")}),
    }


@matches_bp.route("/api/player_heatmap")
def api_player_heatmap():
    """Heatmap del giocatore (stage 13): stagione completa di default;
    ?until_round=N per il cumulativo fino alla giornata N, ?round=N per la
    singola giornata."""
    name = request.args.get("player", "").strip()
    if not name:
        return jsonify({"error": "player parameter required"}), 400
    until_round = request.args.get("until_round", type=int)
    single_round = request.args.get("round", type=int)

    data = _load_heatmaps()
    if data is None:
        return jsonify({"error": "player heatmaps not available (run stage 13)"}), 404

    payload = _player_heatmap_response(data, name, until_round=until_round,
                                       single_round=single_round)
    if payload is None:
        return jsonify({"error": "no heatmap data for this selection"}), 404
    return jsonify(payload)


_adv_cache = {"mtime": None, "data": None}


def _load_advanced():
    if not os.path.exists(PLAYER_ADVANCED_JSON):
        return None
    mtime = os.path.getmtime(PLAYER_ADVANCED_JSON)
    if _adv_cache["data"] is not None and _adv_cache["mtime"] == mtime:
        return _adv_cache["data"]
    try:
        with open(PLAYER_ADVANCED_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    _adv_cache["mtime"] = mtime
    _adv_cache["data"] = data
    return data


def _player_advanced_response(data, player_name):
    """Payload statistiche avanzate per giocatore dal JSON stage 14, o None."""
    if not data:
        return None
    entry = (data.get("players") or {}).get(player_name)
    if not entry or entry.get("no_data") or not entry.get("minutes"):
        return None
    return {
        "player": player_name,
        "available": True,
        "season_id": entry.get("season_id"),
        "role": entry.get("role"),
        "minutes": entry.get("minutes"),
        "appearances": entry.get("appearances"),
        "matches_started": entry.get("matches_started"),
        "rating": entry.get("rating"),
        "cards": entry.get("cards") or {},
        "totals": entry.get("totals") or {},
        "pcts": entry.get("pcts") or {},
        "per90": entry.get("per90") or {},
        "percentiles": entry.get("percentiles") or {},
    }


@matches_bp.route("/api/player_advanced")
def api_player_advanced():
    """Statistiche avanzate di stagione del giocatore (stage 14): totals/per90/pcts + percentili pari ruolo."""
    name = request.args.get("player", "").strip()
    if not name:
        return jsonify({"error": "player parameter required"}), 400

    data = _load_advanced()
    if data is None:
        return jsonify({"error": "advanced stats not available (run stage 14)"}), 404

    payload = _player_advanced_response(data, name)
    if payload is None:
        return jsonify({"error": "no advanced stats for this player"}), 404
    return jsonify(payload)
