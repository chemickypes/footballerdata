#!/usr/bin/env python3
"""
STAGE DINAMICO — Probabili formazioni da fantacalcio.it (Pilastro 3).

Estrae l'undici probabile editoriale per ogni partita del turno. La pagina non
espone una percentuale di titolarita esplicita per giocatore: ai titolari
elencati viene assegnata una probabilita baseline documentata
(BASELINE_TITULAR_PROB); gli stati piu granulari (BALLOTTAGGIO, INFORTUNATO,
SQUALIFICATO, DIFFERENZIATO) vengono sovrascritti in build_feed.py incrociando
l'output di scrape_status.py.
"""
import os
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
from core.ingestion.dynamic.utils import fetch_with_retry

LINEUPS_URL = "https://www.fantacalcio.it/probabili-formazioni-serie-a"
BASELINE_TITULAR_PROB = 0.78


def expected_minutes(titular_prob, is_bench_candidate):
    """xMin = P(Titolare)*70 + (1-P(Titolare))*20*I(in panchina)."""
    bench_component = 20.0 * (1 if is_bench_candidate else 0)
    return titular_prob * 70.0 + (1 - titular_prob) * bench_component


def parse_probable_lineups(html):
    """Estrae i giocatori elencati come probabili titolari da ogni match della pagina."""
    soup = BeautifulSoup(html, "html.parser")
    players = []

    for match in soup.select("li.match"):
        match_id = match.get("data-match-id", "")
        for side_class, side in (("team-home", "home"), ("team-away", "away")):
            team_div = match.select_one(f"div.team.{side_class}")
            if not team_div:
                continue
            for link in team_div.select("a.player-name.player-link"):
                span = link.find("span")
                if not span:
                    continue
                players.append({
                    "player_name": span.get_text(strip=True),
                    "match_id": match_id,
                    "side": side,
                    "href": link.get("href", ""),
                })
    return players


def scrape_probable_lineups():
    """Scarica ed effettua il parsing della pagina probabili formazioni.
    Ritorna lista vuota se il fetch fallisce (degradazione gestita a monte)."""
    resp = fetch_with_retry(LINEUPS_URL, headers=config.HEADERS)
    if resp is None:
        return []
    return parse_probable_lineups(resp.text)
