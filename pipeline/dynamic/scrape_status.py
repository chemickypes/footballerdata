#!/usr/bin/env python3
"""
STAGE DINAMICO — Stato clinico/disciplinare da fantacalcio.it (Pilastro 3).
Incrocia le pagine 'infortunati' e 'squalificati/diffidati' per produrre uno
stato per giocatore (INFORTUNATO / SQUALIFICATO). I giocatori non presenti in
nessuna delle due liste sono considerati OK a valle in build_feed.py.
"""
import logging
import os
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
from pipeline.dynamic.utils import fetch_with_retry

logger = logging.getLogger(__name__)

INJURIES_URL = "https://www.fantacalcio.it/infortunati-serie-a"
SUSPENSIONS_URL = "https://www.fantacalcio.it/squalificati-e-diffidati-campionato-serie-a"


def parse_status_cards(html, status_label):
    """Estrae {player_name: status_label} dalle card 'team-card' della pagina."""
    soup = BeautifulSoup(html, "html.parser")
    result = {}
    for name_tag in soup.select("div.card.team-card strong.item-name"):
        name = name_tag.get_text(strip=True)
        if name:
            result[name] = status_label
    return result


def scrape_all_statuses():
    """Ritorna {player_name: status} unendo infortunati e squalificati.
    Se una delle due richieste fallisce, quella fonte contribuisce con un dict vuoto
    (degradazione, non crash) e il merge procede con l'altra fonte disponibile."""
    statuses = {}

    injuries_resp = fetch_with_retry(INJURIES_URL, headers=config.HEADERS)
    if injuries_resp is not None:
        try:
            statuses.update(parse_status_cards(injuries_resp.text, "INFORTUNATO"))
        except Exception as e:
            logger.warning(f"Failed to parse injuries page: {e}", exc_info=True)

    suspensions_resp = fetch_with_retry(SUSPENSIONS_URL, headers=config.HEADERS)
    if suspensions_resp is not None:
        try:
            statuses.update(parse_status_cards(suspensions_resp.text, "SQUALIFICATO"))
        except Exception as e:
            logger.warning(f"Failed to parse suspensions page: {e}", exc_info=True)

    return statuses
