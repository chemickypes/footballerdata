#!/usr/bin/env python3
"""
STAGE DINAMICO — Quote bookmaker come proxy quantitativo (Pilastro 3).
Rimuove l'aggio del banco dalle quote 1X2 / Over-Under per ricavare le
probabilita implicite pure, secondo P(evento) = (1/Q) / (1 + A) con
A = somma(1/Qk) - 1.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.ingestion.dynamic.api_football_client import get_fixtures, get_odds


def devig_probabilities(odds):
    """odds: lista di tuple (label, quota_decimale). Ritorna {label: probabilita_pura}."""
    if not odds:
        return {}

    implied = [(label, 1.0 / quota) for label, quota in odds if quota > 0]
    if not implied:
        return {}

    overround = sum(p for _, p in implied) - 1.0
    return {label: p / (1.0 + overround) for label, p in implied}


def _extract_1x2(odds_by_market):
    values = odds_by_market.get("Match Winner", [])
    return devig_probabilities(values)


def _extract_over_under_25(odds_by_market):
    values = odds_by_market.get("Goals Over/Under", [])
    filtered = [(label, odd) for label, odd in values if "2.5" in label]
    return devig_probabilities(filtered)


def build_odds_feed():
    """Ritorna una lista di dict, uno per fixture, con probabilita de-vig o None se assenti."""
    feed = []
    for fx in get_fixtures():
        odds_by_market = get_odds(fx["fixture_id"])
        probs_1x2 = _extract_1x2(odds_by_market)
        probs_ou = _extract_over_under_25(odds_by_market)

        home_prob = probs_1x2.get("Home")
        draw_prob = probs_1x2.get("Draw")
        away_prob = probs_1x2.get("Away")
        over_prob = probs_ou.get("Over 2.5")

        # Stima expected goals totali da P(Over 2.5) via approssimazione Poisson
        # inversa (log-odds lineare); usata solo come proxy quantitativo dichiarato.
        expected_total_goals = None
        if over_prob is not None and 0 < over_prob < 1:
            expected_total_goals = 2.5 - math.log((1 - over_prob) / over_prob)

        feed.append({
            "fixture_id": fx["fixture_id"],
            "home_team": fx["home_team"],
            "away_team": fx["away_team"],
            "date": fx["date"],
            "odds_available": bool(probs_1x2),
            "home_win_prob": home_prob,
            "draw_prob": draw_prob,
            "away_win_prob": away_prob,
            "expected_goals_home": (
                round(expected_total_goals * 0.55, 2) if expected_total_goals else None
            ),
            "expected_goals_away": (
                round(expected_total_goals * 0.45, 2) if expected_total_goals else None
            ),
            "clean_sheet_prob_home": round(away_prob * 0.6, 3) if away_prob else None,
            "clean_sheet_prob_away": round(home_prob * 0.6, 3) if home_prob else None,
        })
    return feed
