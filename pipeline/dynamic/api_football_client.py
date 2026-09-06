#!/usr/bin/env python3
"""
Client per api-football.com (v3.football.api-sports.io).
Fornisce fixtures, quote bookmaker e rating per-giocatore per la Serie A.
Autenticazione via header 'x-apisports-key' (config.API_FOOTBALL_KEY).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.dynamic.utils import fetch_with_retry

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"


def _headers():
    return {"x-apisports-key": config.API_FOOTBALL_KEY}


def get_fixtures(round_hint=None):
    """Ritorna le fixture del prossimo turno Serie A non ancora giocato.
    Ritorna lista vuota se la chiave manca o la richiesta fallisce."""
    if not config.API_FOOTBALL_KEY:
        return []

    resp = fetch_with_retry(
        f"{API_FOOTBALL_BASE}/fixtures",
        headers=_headers(),
        params={
            "league": config.API_FOOTBALL_LEAGUE_ID,
            "season": config.API_FOOTBALL_SEASON,
            "next": 10,
        },
    )
    if resp is None:
        return []

    fixtures = []
    for item in resp.json().get("response", []):
        fixtures.append({
            "fixture_id": item["fixture"]["id"],
            "date": item["fixture"]["date"],
            "home_team": item["teams"]["home"]["name"],
            "away_team": item["teams"]["away"]["name"],
        })
    return fixtures


def get_odds(fixture_id):
    """Ritorna le quote grezze (bookmaker medio) per una fixture, o {} se non disponibili."""
    if not config.API_FOOTBALL_KEY:
        return {}

    resp = fetch_with_retry(
        f"{API_FOOTBALL_BASE}/odds",
        headers=_headers(),
        params={"fixture": fixture_id},
    )
    if resp is None:
        return {}

    response = resp.json().get("response", [])
    if not response:
        return {}

    odds_by_market = {}
    for bookmaker in response[0].get("bookmakers", []):
        for bet in bookmaker.get("bets", []):
            market = bet["name"]
            odds_by_market.setdefault(market, [])
            for value in bet.get("values", []):
                try:
                    odds_by_market[market].append((value["value"], float(value["odd"])))
                except (KeyError, ValueError, TypeError):
                    continue
    return odds_by_market


def get_fixture_player_ratings(fixture_id):
    """Ritorna {player_name: rating_float} per una fixture conclusa. Esclude rating nulli."""
    if not config.API_FOOTBALL_KEY:
        return {}

    resp = fetch_with_retry(
        f"{API_FOOTBALL_BASE}/fixtures/players",
        headers=_headers(),
        params={"fixture": fixture_id},
    )
    if resp is None:
        return {}

    ratings = {}
    for team_block in resp.json().get("response", []):
        for player_block in team_block.get("players", []):
            name = player_block.get("player", {}).get("name")
            stats = player_block.get("statistics", [{}])[0]
            rating_raw = stats.get("games", {}).get("rating")
            if name and rating_raw is not None:
                try:
                    ratings[name] = float(rating_raw)
                except (TypeError, ValueError):
                    continue
    return ratings
