#!/usr/bin/env python3
"""
Client per l'API non ufficiale di Sofascore (api.sofascore.com/api/v1).
Fornisce la stagione Serie A corrente e gli eventi per giornata (punteggi
FT/HT, stato), normalizzati nello stesso formato di
core.ingestion.dynamic.api_football_client._parse_fixture, cosi' che gli
stage a valle (11 risultati, futuri stats/heatmap per-match) possano
consumare le due fonti in modo intercambiabile.

Nessuna chiave richiesta: usare pacing educato (RATE_LIMIT_SEC) e i retry
con rotazione User-Agent di core.ingestion.dynamic.utils.fetch_with_retry.
"""

import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
from core.ingestion.dynamic.utils import fetch_with_retry

SOFASCORE_BASE = "https://api.sofascore.com/api/v1"
SERIE_A_TOURNAMENT_ID = 23  # Serie A unique tournament ID su Sofascore
SERIE_A_MAX_ROUNDS = 38
RATE_LIMIT_SEC = 0.4

_STATUS_TYPE_MAP = {
    "notstarted": "NS",
    "inprogress": "LIVE",
    "finished": "FT",
    "postponed": "PST",
    "canceled": "CANC",
    "cancelled": "CANC",
    "delayed": "DEL",
    "suspended": "SUSP",
    "interrupted": "INT",
}

# Stati con punteggio valido (finale o in corso)
PLAYED_STATUSES = {"FT", "AET", "PEN", "LIVE"}


def _map_status(status):
    """Mappa l'oggetto status Sofascore su short code stile api-football."""
    stype = str((status or {}).get("type") or "").strip().lower()
    desc = str((status or {}).get("description") or "").lower()
    code = _STATUS_TYPE_MAP.get(stype)
    if code == "FT":
        if "penalt" in desc:
            return "PEN"
        if "extra" in desc:
            return "AET"
    return code


def parse_event(event):
    """Normalizza un evento Sofascore nel formato fixture condiviso.

    Required fields: id, startTimestamp, homeTeam.name, awayTeam.name.
    Optional fields: status, homeScore/awayScore (current, period1), roundInfo.round.
    """
    event_id = event.get("id")
    ts = event.get("startTimestamp")
    home_team = (event.get("homeTeam") or {}).get("name")
    away_team = (event.get("awayTeam") or {}).get("name")
    if event_id is None or not ts or not home_team or not away_team:
        return None

    status = _map_status(event.get("status"))
    played = status in PLAYED_STATUSES
    home_score = event.get("homeScore") or {}
    away_score = event.get("awayScore") or {}
    rnd = (event.get("roundInfo") or {}).get("round")

    return {
        "fixture_id": event_id,
        "date": datetime.datetime.fromtimestamp(int(ts), tz=datetime.timezone.utc).isoformat(),
        "home_team": home_team,
        "away_team": away_team,
        "home_score": home_score.get("current") if played else None,
        "away_score": away_score.get("current") if played else None,
        "ht_home_score": home_score.get("period1") if played else None,
        "ht_away_score": away_score.get("period1") if played else None,
        "round": f"Regular Season - {rnd}" if rnd else None,
        "status": status,
    }


def get_serie_a_season_id():
    """Ritorna l'id della stagione Serie A corrente su Sofascore (la prima della lista)."""
    resp = fetch_with_retry(
        f"{SOFASCORE_BASE}/unique-tournament/{SERIE_A_TOURNAMENT_ID}/seasons",
        headers=config.HEADERS,
    )
    if resp is None:
        raise RuntimeError("Sofascore: fetch delle stagioni fallito (retry esauriti)")
    try:
        seasons = resp.json().get("seasons", []) or []
    except json.JSONDecodeError:
        seasons = []
    if not seasons:
        raise RuntimeError("Sofascore: nessuna stagione trovata per la Serie A")
    return seasons[0]["id"]


def get_round_events(season_id, round_num):
    """Eventi grezzi di una giornata. None su fallimento di rete (dopo i retry),
    lista (anche vuota) su risposta valida."""
    resp = fetch_with_retry(
        f"{SOFASCORE_BASE}/unique-tournament/{SERIE_A_TOURNAMENT_ID}"
        f"/season/{season_id}/events/round/{round_num}",
        headers=config.HEADERS,
    )
    if resp is None:
        return None
    try:
        return resp.json().get("events", []) or []
    except json.JSONDecodeError:
        return []


def get_season_fixtures(max_rounds=SERIE_A_MAX_ROUNDS, rate_limit_sec=RATE_LIMIT_SEC):
    """Tutte le fixture Serie A della stagione corrente (giocate e programmate),
    normalizzate nel formato condiviso. Una richiesta per giornata."""
    season_id = get_serie_a_season_id()
    fixtures = []
    for rnd in range(1, max_rounds + 1):
        events = get_round_events(season_id, rnd)
        if events is None:
            if rnd == 1:
                raise RuntimeError("Sofascore: fetch della giornata 1 fallito (retry esauriti)")
            break  # giornata oltre la fine stagione (404): stop
        for ev in events:
            parsed = parse_event(ev)
            if parsed is not None:
                fixtures.append(parsed)
        if rnd < max_rounds:
            time.sleep(rate_limit_sec)
    return fixtures


def get_event_lineups(event_id):
    """Formazioni complete di un evento (entrambe le squadre). None su fallimento."""
    resp = fetch_with_retry(
        f"{SOFASCORE_BASE}/event/{event_id}/lineups",
        headers=config.HEADERS,
    )
    if resp is None:
        return None
    try:
        return resp.json()
    except json.JSONDecodeError:
        return None


def get_player_season_statistics(player_id, season_id=None):
    """Statistiche aggregate di stagione per un giocatore (Serie A).

    Payload /player/{id}/unique-tournament/23/season/{sid}/statistics/overall:
    ~115 chiavi (passaggi, dribbling, duelli, difesa, portiere, cartellini...).
    None su fallimento di rete, dict vuoto se nessun dato di stagione."""
    if season_id is None:
        season_id = get_serie_a_season_id()
    resp = fetch_with_retry(
        f"{SOFASCORE_BASE}/player/{player_id}/unique-tournament/{SERIE_A_TOURNAMENT_ID}"
        f"/season/{season_id}/statistics/overall",
        headers=config.HEADERS,
    )
    if resp is None:
        return None
    try:
        return resp.json().get("statistics", {}) or {}
    except json.JSONDecodeError:
        return None


def get_player_heatmap(event_id, player_id):
    """Punti heatmap {x, y} (0-100) di un giocatore in un evento.

    Coordinate team-normalizzate (verificate empiricamente): x=0 porta propria,
    x=100 porta avversaria, per ENTRAMBE le squadre. None su fallimento di rete,
    lista (anche vuota) su risposta valida."""
    resp = fetch_with_retry(
        f"{SOFASCORE_BASE}/event/{event_id}/player/{player_id}/heatmap",
        headers=config.HEADERS,
    )
    if resp is None:
        return None
    try:
        return resp.json().get("heatmap", []) or []
    except json.JSONDecodeError:
        return None


def _num(value, ndigits=3):
    if value is None:
        return None
    try:
        return round(float(value), ndigits)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_event_lineup(fixture, lineup_data):
    """Normalizza le convocate di un evento in righe per giocatore (formato CSV stage 12).

    fixture: dict con fixture_id, round (int), date, home_team, away_team.
    lineup_data: payload di /event/{id}/lineups. I giocatori elencati ma mai
    entrati in campo (minutesPlayed assente) vengono saltati.
    Nota: l'endpoint non espone i cartellini.
    """
    rows = []
    fixture_id = fixture.get("fixture_id")
    for side, team_name in (("home", fixture.get("home_team")), ("away", fixture.get("away_team"))):
        block = (lineup_data or {}).get(side) or {}
        for p in block.get("players", []) or []:
            player = p.get("player") or {}
            stats = p.get("statistics") or {}
            if stats.get("minutesPlayed") is None:
                continue
            rows.append({
                "event_id": fixture_id,
                "round": fixture.get("round"),
                "date_utc": fixture.get("date"),
                "venue": side,
                "team_name": team_name,
                "player_sofascore": player.get("name"),
                "sofascore_player_id": player.get("id"),
                "position": p.get("position") or player.get("position"),
                "shirt_number": p.get("shirtNumber") or player.get("jerseyNumber"),
                "is_starter": not bool(p.get("substitute")),
                "minutes_played": int(stats["minutesPlayed"]),
                "rating": _num(stats.get("rating")),
                "goals": _int_or_zero(stats.get("goals")),
                "assists": _int_or_zero(stats.get("goalAssist")),
                "key_passes": _int_or_zero(stats.get("keyPass")),
                "shots": _int_or_zero(stats.get("totalShots")),
                "shots_on_target": _int_or_zero(stats.get("onTargetScoringAttempt")),
                "xg": _num(stats.get("expectedGoals")),
                "xa": _num(stats.get("expectedAssists")),
                "passes_acc": stats.get("accuratePass"),
                "passes_tot": stats.get("totalPass"),
                "tackles": stats.get("totalTackle"),
                "interceptions": stats.get("interceptionWon"),
                "clearances": stats.get("totalClearance"),
                "duels_won": stats.get("duelWon"),
                "duels_lost": stats.get("duelLost"),
                "touches": stats.get("touches"),
                "fouls": stats.get("fouls"),
                "saves": stats.get("saves"),
                "goals_prevented": _num(stats.get("goalsPrevented")),
            })
    return rows
