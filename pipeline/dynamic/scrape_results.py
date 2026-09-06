#!/usr/bin/env python3
"""
STAGE DINAMICO — Aggiornamento forma recente (EWMA) da risultati turno concluso.
EWMA_t = 0.35 * rating_t + 0.65 * EWMA_{t-1}. Il rating usato come base e' quello
per-giocatore restituito da api-football.com (proxy dichiarato del voto
fantacalcio ufficiale, non la pagella reale di fantacalcio.it).
Persistenza offline in data/ewma_state.json: mai letto/scritto a runtime da app.py.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pipeline.dynamic.api_football_client import get_fixture_player_ratings

EWMA_ALPHA = 0.35


def update_ewma(prev, rating, alpha=EWMA_ALPHA):
    """EWMA_t = alpha*rating + (1-alpha)*EWMA_{t-1}. Se non c'e' storico, ritorna il rating."""
    if prev is None:
        return rating
    return alpha * rating + (1 - alpha) * prev


def load_ewma_state():
    """Carica lo stato EWMA da file JSON. Ritorna {} se il file non esiste o e' corrotto."""
    if not os.path.exists(config.EWMA_STATE_JSON):
        return {}
    try:
        with open(config.EWMA_STATE_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_ewma_state(state):
    """Salva lo stato EWMA nel file JSON."""
    os.makedirs(os.path.dirname(config.EWMA_STATE_JSON), exist_ok=True)
    with open(config.EWMA_STATE_JSON, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def update_form_from_fixtures(fixture_ids):
    """Aggiorna e persiste lo stato EWMA per tutti i giocatori delle fixture concluse date."""
    state = load_ewma_state()
    for fixture_id in fixture_ids:
        ratings = get_fixture_player_ratings(fixture_id)
        for player_name, rating in ratings.items():
            state[player_name] = update_ewma(state.get(player_name), rating)
    save_ewma_state(state)
    return state
