#!/usr/bin/env python3
"""
STAGE DINAMICO — Orchestratore del feed infrasettimanale (Pilastro 3).
Unisce formazioni probabili, stato clinico/disciplinare, quote de-vig e forma
EWMA in data/current_matchday.json secondo il contratto dati del capitolato.
Fail-fast se il numero di giocatori validi è insufficiente (< MIN_VALID_PLAYERS_IN_FEED).
"""
import argparse
import datetime
import json
import logging
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
from core.ingestion.dynamic import api_football_client, scrape_lineups, scrape_odds, scrape_results, scrape_status
from core.ingestion.dynamic.utils import PlayerMatcher, normalize_name

logger = logging.getLogger(__name__)


def compute_xpts(voto_base, p_gol, p_assist, e_gol_subiti, p_ammonizione, xmin):
    """xPts = (xMin/90) * [VotoBase + 3*P(Gol) + P(Assist) - E[GolSubiti] - 0.25*P(Ammonizione)]."""
    base_score = voto_base + 3 * p_gol + p_assist - e_gol_subiti - 0.25 * p_ammonizione
    return (xmin / 90.0) * base_score


def _team_slug(team_value):
    """Converts team value to lowercase slug."""
    return normalize_name(str(team_value)).replace(" ", "_")


def _player_key(team_value, player_name, role):
    """Generates player key in format: team_player_role."""
    return f"{_team_slug(team_value)}_{normalize_name(player_name).replace(' ', '_')}_{str(role).lower()}"


def _match_foreign_dict(items_dict, matcher):
    """Riconcilia un dict {nome_esterno: valore} sui nomi del dataset via PlayerMatcher.
    Usato per statuses (fantacalcio.it) ed ewma_state (api-football), i cui nomi
    non coincidono in generale con lo spazio dei nomi del dataset."""
    matched = {}
    for foreign_name, value in items_dict.items():
        matched_name = matcher.match(foreign_name, "")
        if matched_name:
            matched[matched_name] = value
    return matched


def update_ewma_from_concluded_fixtures():
    """Recupera le fixture concluse piu' recenti da api-football e aggiorna/persiste
    lo stato EWMA. Exception-safe: se il recupero fallisce, non aggiorna nulla."""
    try:
        concluded_fixtures = api_football_client.get_fixtures(status_filter="FT")
        fixture_ids = [f["fixture_id"] for f in concluded_fixtures]
        if fixture_ids:
            scrape_results.update_form_from_fixtures(fixture_ids)
    except Exception:
        logger.exception("Aggiornamento EWMA da fixture concluse fallito")


def build_players_payload(dataset_df, lineup_players, statuses, ewma_state, odds_feed):
    """Constructs the 'players' dict of the JSON contract for each player in dataset."""
    matcher = PlayerMatcher(dataset_df)
    lineup_by_matched_name = {}
    for lp in lineup_players:
        matched = matcher.match(lp["player_name"], "")
        if matched:
            lineup_by_matched_name[matched] = lp

    statuses_by_matched_name = _match_foreign_dict(statuses, matcher)
    ewma_by_matched_name = _match_foreign_dict(ewma_state, matcher)

    players = {}
    for _, row in dataset_df.iterrows():
        name = row["player"]
        team = row["team"]
        role = row["role"]
        key = _player_key(team, name, role)

        status = statuses_by_matched_name.get(name, "OK")
        is_starter = name in lineup_by_matched_name
        ewma_form = ewma_by_matched_name.get(name, 6.0)

        if status in ("INFORTUNATO", "SQUALIFICATO"):
            titular_prob = 0.0
        elif is_starter:
            titular_prob = scrape_lineups.BASELINE_TITULAR_PROB
        else:
            titular_prob = 0.15  # riserva/panchina di default

        xmin = scrape_lineups.expected_minutes(titular_prob, is_bench_candidate=not is_starter)

        players[key] = {
            "name": name,
            "team": team,
            "role": role,
            "status": status,
            "titular_prob": round(titular_prob, 3),
            "expected_minutes": round(xmin, 1),
            "ewma_form": round(ewma_form, 3),
            "xpts": round(
                compute_xpts(
                    voto_base=ewma_form,
                    p_gol=0.0,
                    p_assist=0.0,
                    e_gol_subiti=0.0,
                    p_ammonizione=0.1,
                    xmin=xmin,
                ),
                3,
            ),
        }
    return players


def build_feed_payload(dataset_df, matchday, season):
    """Builds the complete JSON feed payload."""
    lineup_players = scrape_lineups.scrape_probable_lineups()
    statuses = scrape_status.scrape_all_statuses()
    update_ewma_from_concluded_fixtures()
    ewma_state = scrape_results.load_ewma_state()
    odds_feed = scrape_odds.build_odds_feed()

    return {
        "matchday": matchday,
        "season": season,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rating_source": "api_football_proxy",
        "fixtures": odds_feed,
        "players": build_players_payload(dataset_df, lineup_players, statuses, ewma_state, odds_feed),
    }


def main(matchday=1, season="2026/2027"):
    """CLI entrypoint: loads dataset, builds feed, validates, and writes to disk."""
    if not os.path.exists(config.DATASET_FINALE_CSV):
        raise RuntimeError(
            f"[ERROR] Dataset non trovato: {config.DATASET_FINALE_CSV}. "
            "Esegui prima la pipeline statica: python run_pipeline.py"
        )
    dataset_df = pd.read_csv(config.DATASET_FINALE_CSV)
    payload = build_feed_payload(dataset_df, matchday, season)

    valid_players = sum(1 for p in payload["players"].values() if p["name"])
    if valid_players < config.MIN_VALID_PLAYERS_IN_FEED:
        raise RuntimeError(
            f"[ERROR] Feed dinamico incompleto: {valid_players} giocatori validi "
            f"(< {config.MIN_VALID_PLAYERS_IN_FEED} richiesti). Interruzione per evitare "
            "un feed corrotto o parziale su data-feed."
        )

    os.makedirs(os.path.dirname(config.CURRENT_MATCHDAY_JSON), exist_ok=True)
    with open(config.CURRENT_MATCHDAY_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[OK] Feed scritto in {config.CURRENT_MATCHDAY_JSON} ({valid_players} giocatori validi)")


def _parse_cli_matchday(argv):
    """Estrae opzionalmente il numero di giornata da linea di comando (default 1)."""
    parser = argparse.ArgumentParser(description="Build dynamic matchday feed")
    parser.add_argument(
        "--matchday", type=int, default=1, help="Numero di giornata (default: 1)"
    )
    args, _ = parser.parse_known_args(argv)
    return args.matchday


if __name__ == "__main__":
    main(matchday=_parse_cli_matchday(sys.argv[1:]))
