#!/usr/bin/env python3
"""
Client per api-football.com (v3.football.api-sports.io).
Fornisce fixtures, quote bookmaker e rating per-giocatore per la Serie A.
Autenticazione via header 'x-apisports-key' (config.API_FOOTBALL_KEY).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
from core.ingestion.dynamic.utils import fetch_with_retry

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"


def _headers():
    return {"x-apisports-key": config.API_FOOTBALL_KEY}


def _parse_fixture(item):
    """Normalizza una fixture dal payload api-football in un dict piatto.

    Required fields: fixture.id, fixture.date, teams.home.name, teams.away.name.
    Missing/malformed fields cause the item to be skipped (None returned).
    Optional fields: goals.home/away/halftime, league.round, fixture.status.short.
    """
    fixture = item.get("fixture", {}) or {}
    teams = item.get("teams", {}) or {}
    goals = item.get("goals", {}) or {}
    halftime = goals.get("halftime") if isinstance(goals.get("halftime"), dict) else {}

    fixture_id = fixture.get("id")
    date = fixture.get("date")
    home_team = (teams.get("home", {}) or {}).get("name")
    away_team = (teams.get("away", {}) or {}).get("name")

    if fixture_id is None or not date or not home_team or not away_team:
        return None

    return {
        "fixture_id": fixture_id,
        "date": date,
        "home_team": home_team,
        "away_team": away_team,
        "home_score": goals.get("home"),
        "away_score": goals.get("away"),
        "ht_home_score": halftime.get("home"),
        "ht_away_score": halftime.get("away"),
        "round": (item.get("league", {}) or {}).get("round"),
        "status": (fixture.get("status", {}) or {}).get("short"),
    }


def get_fixtures(round_hint=None, status_filter=None):
    """Ritorna le fixture Serie A. Ritorna lista vuota se la chiave manca o la richiesta fallisce.

    Di default ritorna le prossime fixture non ancora giocate ('next'). Se status_filter e'
    valorizzato (es. 'FT' per le partite concluse/terminate), interroga invece le fixture
    concluse piu' recenti ('last') filtrate per quello stato, utile per aggiornare la forma
    EWMA post-turno. Ogni fixture include anche punteggi (FT/HT), giornata e stato.
    """
    if not config.API_FOOTBALL_KEY:
        return []

    params = {
        "league": config.API_FOOTBALL_LEAGUE_ID,
        "season": config.API_FOOTBALL_SEASON,
    }
    if status_filter:
        params["last"] = 10
        params["status"] = status_filter
    else:
        params["next"] = 10

    resp = fetch_with_retry(
        f"{API_FOOTBALL_BASE}/fixtures",
        headers=_headers(),
        params=params,
    )
    if resp is None:
        return []

    fixtures = []
    try:
        response_data = resp.json().get("response", [])
    except json.JSONDecodeError:
        return []

    for item in response_data:
        parsed = _parse_fixture(item)
        if parsed is not None:
            fixtures.append(parsed)
    return fixtures


def get_season_fixtures(season=None):
    """Ritorna tutte le fixture Serie A della stagione (giocate e non) in un'unica richiesta.

    Ogni fixture include punteggi FT/HT, giornata ('Regular Season - N') e stato
    ('FT'/'NS'/...). Gestisce il paging di sicurezza dell'endpoint. Ritorna lista
    vuota se la chiave manca o la richiesta fallisce.
    """
    if not config.API_FOOTBALL_KEY:
        return []

    season = season or config.API_FOOTBALL_SEASON
    fixtures = []
    page = 1
    while True:
        resp = fetch_with_retry(
            f"{API_FOOTBALL_BASE}/fixtures",
            headers=_headers(),
            params={
                "league": config.API_FOOTBALL_LEAGUE_ID,
                "season": season,
                "page": page,
            },
        )
        if resp is None:
            return []

        try:
            body = resp.json()
        except json.JSONDecodeError:
            return []

        for item in body.get("response", []):
            parsed = _parse_fixture(item)
            if parsed is not None:
                fixtures.append(parsed)

        try:
            total_pages = int((body.get("paging", {}) or {}).get("total", 1) or 1)
        except (TypeError, ValueError):
            total_pages = 1
        if page >= total_pages:
            break
        page += 1

    return fixtures


def get_odds(fixture_id):
    """Ritorna le quote grezze (bookmaker medio) per una fixture, o {} se non disponibili.
    
    If 'name' field is missing from a bet, that bet is skipped.
    If 'value' or 'odd' fields are missing, that value is skipped.
    """
    if not config.API_FOOTBALL_KEY:
        return {}

    resp = fetch_with_retry(
        f"{API_FOOTBALL_BASE}/odds",
        headers=_headers(),
        params={"fixture": fixture_id},
    )
    if resp is None:
        return {}

    try:
        response = resp.json().get("response", [])
    except json.JSONDecodeError:
        return {}

    if not response:
        return {}

    odds_by_market = {}
    for bookmaker in response[0].get("bookmakers", []):
        for bet in bookmaker.get("bets", []):
            market = bet.get("name")
            if market is None:
                continue
            odds_by_market.setdefault(market, [])
            for value in bet.get("values", []):
                try:
                    value_name = value.get("value")
                    odd_val = value.get("odd")
                    if value_name is not None and odd_val is not None:
                        odds_by_market[market].append((value_name, float(odd_val)))
                except (ValueError, TypeError):
                    continue
    return odds_by_market


def get_fixture_player_ratings(fixture_id):
    """Ritorna {player_name: rating_float} per una fixture conclusa. Esclude rating nulli.
    
    Required fields: player.name.
    Optional fields: statistics[0].games.rating (must be non-null and convertible to float).
    Missing/malformed fields cause the player to be skipped.
    """
    if not config.API_FOOTBALL_KEY:
        return {}

    resp = fetch_with_retry(
        f"{API_FOOTBALL_BASE}/fixtures/players",
        headers=_headers(),
        params={"fixture": fixture_id},
    )
    if resp is None:
        return {}

    try:
        response_data = resp.json().get("response", [])
    except json.JSONDecodeError:
        return {}

    ratings = {}
    for team_block in response_data:
        for player_block in team_block.get("players", []):
            name = player_block.get("player", {}).get("name")
            
            stats_list = player_block.get("statistics", [])
            stats = stats_list[0] if stats_list else {}
            
            rating_raw = stats.get("games", {}).get("rating")
            if name and rating_raw is not None:
                try:
                    ratings[name] = float(rating_raw)
                except (TypeError, ValueError):
                    continue
    return ratings
