"""
footballerdata — /api/matches + /api/player_matches endpoints
Serie A match results & schedule plus per-team recent form (stage-11 artifacts),
per-player match stats (stage-12), heatmaps (stage-13) and advanced season
stats (stage-14), from the data/ artifacts.
"""

import csv
import json
import os
from datetime import datetime, timezone

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


def _num_or_none(value):
    try:
        if value is None or str(value).strip() in ("", "None", "nan"):
            return None
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


MATCH_PLAYER_FIELDS = [
    "player", "player_sofascore", "position", "shirt_number", "is_starter",
    "minutes_played", "rating", "goals", "assists", "key_passes",
    "shots", "shots_on_target", "xg", "xa", "passes_acc", "passes_tot",
    "tackles", "interceptions", "duels_won", "duels_lost", "touches",
    "fouls", "saves", "goals_prevented",
]


def _match_player_row(r):
    """Riga giocatore normalizzata per il payload match_detail."""
    out = {}
    for f in MATCH_PLAYER_FIELDS:
        v = r.get(f)
        if f in ("player", "player_sofascore", "position"):
            out[f] = None if pd.isna(v) else str(v)
        elif f in ("shirt_number", "minutes_played", "goals", "assists", "key_passes",
                   "shots", "shots_on_target", "passes_acc", "passes_tot", "tackles",
                   "interceptions", "duels_won", "duels_lost", "touches", "fouls", "saves"):
            out[f] = _int_or_none(v)
        else:  # rating, xg, xa, goals_prevented
            out[f] = _num_or_none(v)
    out["is_starter"] = bool(out.get("is_starter")) if out.get("is_starter") is not None else False
    return out


def _sort_lineup(players):
    """Titolari per numero di maglia, poi subentrati per minuti."""
    starters = sorted((p for p in players if p["is_starter"]),
                      key=lambda p: (p["shirt_number"] is None,
                                     p["shirt_number"] or 0))
    subs = sorted((p for p in players if not p["is_starter"]),
                  key=lambda p: -(p["minutes_played"] or 0))
    return starters + subs


def _build_match_detail_payload(pm_df, fixture_id, matches_payload):
    """Payload /api/match_detail: meta partita + formazioni per lato +
    marcatori + MOTM, dal CSV stage 12. None se la partita non esiste."""
    meta = None
    if matches_payload and matches_payload.get("available"):
        for rnd in matches_payload.get("rounds", []):
            for m in rnd.get("matches", []):
                if m.get("fixture_id") == fixture_id:
                    meta = m
                    break
            if meta:
                break
    if meta is None:
        return None

    result = {
        "match": {
            "event_id": fixture_id,
            "round": meta.get("round"),
            "date": meta.get("date"),
            "home_team": meta.get("home_display") or meta.get("home_team"),
            "home_code": meta.get("home_code"),
            "away_team": meta.get("away_display") or meta.get("away_team"),
            "away_code": meta.get("away_code"),
            "home_score": meta.get("home_score"),
            "away_score": meta.get("away_score"),
            "ht_home_score": meta.get("ht_home_score"),
            "ht_away_score": meta.get("ht_away_score"),
            "status": meta.get("status"),
            "finished": meta.get("finished"),
        },
        "lineups_available": False,
        "home": {"code": meta.get("home_code"),
                 "name": meta.get("home_display") or meta.get("home_team"),
                 "players": []},
        "away": {"code": meta.get("away_code"),
                 "name": meta.get("away_display") or meta.get("away_team"),
                 "players": []},
        "scorers": [],
        "motm": None,
    }

    if pm_df is None:
        return result

    ev = pm_df[pm_df["event_id"] == fixture_id]
    if not len(ev):
        return result

    home_code = meta.get("home_code")
    away_code = meta.get("away_code")
    sides = {"home": [], "away": []}
    all_rows = []
    for _, r in ev.iterrows():
        row = _match_player_row(r)
        code = r.get("team_code")
        code = None if pd.isna(code) else str(code)
        if code == home_code or (code is None and str(r.get("venue")) == "home"):
            sides["home"].append(row)
        elif code == away_code or (code is None and str(r.get("venue")) == "away"):
            sides["away"].append(row)
        else:
            continue
        all_rows.append(row)

    if not all_rows:
        return result

    result["lineups_available"] = True
    result["home"]["players"] = _sort_lineup(sides["home"])
    result["away"]["players"] = _sort_lineup(sides["away"])

    # Marcatori (gol per giocatore aggregati)
    scorers = {}
    for row in all_rows:
        g = row.get("goals") or 0
        if g > 0 and row.get("player"):
            scorers[row["player"]] = scorers.get(row["player"], 0) + g
    result["scorers"] = [{"player": p, "goals": g}
                         for p, g in sorted(scorers.items(), key=lambda kv: -kv[1])]

    # MOTM: rating massimo tra i due lati
    rated = [(row, side) for side in ("home", "away")
             for row in result[side]["players"] if row.get("rating") is not None]
    if rated:
        best, best_side = max(rated, key=lambda t: t[0]["rating"])
        result["motm"] = {
            "player": best.get("player") or best.get("player_sofascore"),
            "team": result[best_side]["code"],
            "team_name": result[best_side]["name"],
            "rating": best["rating"],
        }
    return result


_md_cache = {"mtime": None, "pm_df": None}


@matches_bp.route("/api/match_detail")
def api_match_detail():
    """Dettaglio partita (stage 11+12): formazioni, marcatori, MOTM."""
    event_id = request.args.get("event", type=int)
    if not event_id:
        return jsonify({"error": "event parameter required"}), 400

    matches_payload = _load_payload()
    if matches_payload is None:
        return jsonify({"error": "match results not available (run stage 11)"}), 404

    if not os.path.exists(PLAYER_MATCH_STATS_CSV):
        payload = _build_match_detail_payload(None, event_id, matches_payload)
        if payload is None:
            return jsonify({"error": "match not found"}), 404
        return jsonify(payload)

    mtime = os.path.getmtime(PLAYER_MATCH_STATS_CSV)
    if _md_cache["pm_df"] is None or _md_cache["mtime"] != mtime:
        _md_cache["mtime"] = mtime
        _md_cache["pm_df"] = pd.read_csv(PLAYER_MATCH_STATS_CSV)
    pm_df = _md_cache["pm_df"]

    payload = _build_match_detail_payload(pm_df, event_id, matches_payload)
    if payload is None:
        return jsonify({"error": "match not found"}), 404
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────────────────────
# ESPN match-events store (crowdsourced cache)
#
# Le statistiche di gara (gol/assist/cartellini/cambi/moduli) arrivano da ESPN
# SOLO dal browser del visitatore (ESPN blocca le richieste server-side).
# Quando una pagina partita le scarica, il client le POSTa qui: vengono
# salvate in data/espn_match_events.json (chiave = fixture_id stage 11) e le
# visite successive le leggono dalla cache senza toccare ESPN. Merge senza
# downgrade: una versione con meno eventi non sostituisce una piu' ricca.
# ─────────────────────────────────────────────────────────────────────────────
ESPN_EVENTS_JSON = os.environ.get(
    "ESPN_EVENTS_JSON", os.path.join(PROJECT_ROOT, "data", "espn_match_events.json")
)
VALID_KINDS = {"goal", "penalty", "own", "yellow", "red", "sub"}
VALID_SIDES = {"home", "away"}
VALID_STATES = {"pre", "in", "post"}


def _load_espn_store():
    if not os.path.exists(ESPN_EVENTS_JSON):
        return {}
    try:
        with open(ESPN_EVENTS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_espn_store(store):
    """Scrittura atomica (tmp + replace) per non troncare il file su crash."""
    os.makedirs(os.path.dirname(ESPN_EVENTS_JSON), exist_ok=True)
    tmp = ESPN_EVENTS_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, ESPN_EVENTS_JSON)


def _clean_str(value, cap):
    s = str(value or "").strip()
    return s[:cap] if s else ""


def sanitize_espn_payload(data):
    """Valida e normalizza il payload POSTato dal client. None se illegittimo."""
    if not isinstance(data, dict):
        return None
    event_id = _int_or_none(data.get("event_id"))
    if event_id is None or event_id <= 0:
        return None
    match_state = data.get("match_state")
    if match_state not in VALID_STATES:
        match_state = None
    form_raw = data.get("form") or {}
    form = {
        "home": _clean_str(form_raw.get("home"), 12) if isinstance(form_raw, dict) else "",
        "away": _clean_str(form_raw.get("away"), 12) if isinstance(form_raw, dict) else "",
    }
    events = []
    raw_events = data.get("events")
    if isinstance(raw_events, list):
        for e in raw_events[:200]:
            if not isinstance(e, dict):
                continue
            kind = e.get("kind")
            side = e.get("side")
            if kind not in VALID_KINDS or side not in VALID_SIDES:
                continue
            minute = _int_or_none(e.get("minute"))
            if minute is not None and not 0 <= minute <= 130:
                minute = None
            events.append({
                "minute": minute,
                "side": side,
                "kind": kind,
                "player": _clean_str(e.get("player"), 80),
                "assist": _clean_str(e.get("assist"), 80),
            })
    espn_link = _clean_str(data.get("espn_link"), 250)
    if espn_link and not espn_link.startswith("https://www.espn.com/"):
        espn_link = ""
    return {
        "event_id": event_id,
        "espn_event_id": _clean_str(data.get("espn_event_id"), 20),
        "match_state": match_state,
        "form": form,
        "events": events,
        "espn_link": espn_link,
    }


def merge_espn_payload(store, clean):
    """Inserisce/aggiorna la chiave senza mai degradare i dati: una versione
    con meno eventi non sostituisce una piu' ricca. Unico upgrade consentito
    a parita' di eventi: aggiungere il link canonico ESPN a una voce che non
    lo ha (gli eventi piu' ricchi restano invariati). True se scritta."""
    key = str(clean["event_id"])
    prev = store.get(key)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if prev is not None:
        try:
            prev_count = len(prev.get("events") or [])
        except Exception:
            prev_count = 0
        link_upgrade = bool(clean.get("espn_link")) and not (prev.get("espn_link") or "")
        if prev_count > len(clean["events"]):
            if not link_upgrade:
                return False
            # solo upgrade del link: gli eventi piu' ricchi restano
            entry = dict(prev)
            entry["espn_link"] = clean["espn_link"]
            entry["fetched_at"] = now
            store[key] = entry
            return True
        if prev_count == len(clean["events"]) and not link_upgrade:
            return False
    entry = dict(clean)
    entry["fetched_at"] = now
    store[key] = entry
    return True


_espn_store_cache = {"mtime": None, "data": None}


def _espn_store_cached():
    """Store in cache per le GET: rilettura solo se il file e' cambiato."""
    if not os.path.exists(ESPN_EVENTS_JSON):
        return {}
    mtime = os.path.getmtime(ESPN_EVENTS_JSON)
    if _espn_store_cache["data"] is None or _espn_store_cache["mtime"] != mtime:
        _espn_store_cache["mtime"] = mtime
        _espn_store_cache["data"] = _load_espn_store()
    return _espn_store_cache["data"]


@matches_bp.route("/api/match_events")
def api_match_events_get():
    """Eventi ESPN cachati per una partita (gol/cartellini/cambi/moduli)."""
    event_id = request.args.get("event", type=int)
    if not event_id:
        return jsonify({"error": "event parameter required"}), 400
    entry = _espn_store_cached().get(str(event_id))
    if not entry:
        return jsonify({"error": "no cached events for this match"}), 404
    return jsonify({
        "available": True,
        "event_id": event_id,
        "espn_event_id": entry.get("espn_event_id"),
        "espn_link": entry.get("espn_link"),
        "match_state": entry.get("match_state"),
        "fetched_at": entry.get("fetched_at"),
        "form": entry.get("form") or {},
        "events": entry.get("events") or [],
    })


@matches_bp.route("/api/espn_events", methods=["POST"])
def api_espn_events_post():
    """Salva gli eventi ESPN raccolti dal browser di un visitatore."""
    payload = sanitize_espn_payload(request.get_json(silent=True))
    if payload is None:
        return jsonify({"error": "invalid payload"}), 400
    # rileggi dal disco (non dalla cache di lettura) per non perdere chiavi
    store = _load_espn_store()
    written = merge_espn_payload(store, payload)
    if written:
        _save_espn_store(store)
        _espn_store_cache["mtime"] = None  # forza rilettura alla prossima GET
    return jsonify({"saved": written, "event_id": payload["event_id"],
                    "events": len(payload["events"])})


@matches_bp.route("/api/espn_events", methods=["DELETE"])
def api_espn_events_delete():
    """Rimuove una chiave dalla cache (es. dati errati da correggere)."""
    event_id = request.args.get("event", type=int)
    if not event_id:
        return jsonify({"error": "event parameter required"}), 400
    store = _load_espn_store()
    key = str(event_id)
    if key not in store:
        return jsonify({"error": "no cached events for this match"}), 404
    del store[key]
    _save_espn_store(store)
    _espn_store_cache["mtime"] = None
    return jsonify({"deleted": key})
