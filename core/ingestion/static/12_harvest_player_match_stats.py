#!/usr/bin/env python3
"""
STAGE 12 — Statistiche per-partita dei giocatori (Sofascore).

Per ogni partita conclusa non ancora raccolta scarica le formazioni complete
(una richiesta per partita, endpoint /event/{id}/lineups) e produce
data/player_match_stats.csv: una riga per giocatore entrato in campo con
minuti, rating, gol, assist, xG/xA, passaggi, duelli, parate ecc.

I giocatori vengono riconciliati sui nomi del dataset via PlayerMatcher
(cascata esatto/fuzzy per squadra/fuzzy globale) + alias espliciti in
config.SOFASCORE_PLAYER_ALIASES. Le righe non riconciliate mantengono
player vuoto e vengono conteggiate in output.

Incrementale: gli event gia' presenti nel CSV non vengono riscaricati.
Fonte delle partite: data/match_results.csv (stage 11); se assente,
percorre le giornate Sofascore direttamente.

Nota: l'endpoint lineups non espone i cartellini (gialli/rossi non disponibili).
"""

import importlib
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
from core.ingestion.static import sofascore_api

stage11 = importlib.import_module("core.ingestion.static.11_scrape_match_results")

FINISHED_STATUSES = {"FT", "AET", "PEN"}
RATE_LIMIT_SEC = 0.4

CSV_COLUMNS = [
    "event_id", "round", "date_utc", "venue", "team_code", "opponent_code",
    "player", "player_sofascore", "sofascore_player_id", "position",
    "shirt_number", "is_starter", "minutes_played", "rating", "goals",
    "assists", "key_passes", "shots", "shots_on_target", "xg", "xa",
    "passes_acc", "passes_tot", "tackles", "interceptions", "clearances",
    "duels_won", "duels_lost", "touches", "fouls", "saves", "goals_prevented",
]


def load_finished_fixtures(results_csv=None):
    """Fixture concluse da raccogliere: legge lo stage 11 (match_results.csv) o,
    se assente, percorre le giornate Sofascore direttamente. Ritorna DataFrame."""
    path = results_csv or config.MATCH_RESULTS_CSV
    if os.path.exists(path):
        df = pd.read_csv(path)
        df = df[df["status"].isin(FINISHED_STATUSES)].copy()
        df["round"] = df["round"].astype(int)
        return df

    fixtures = sofascore_api.get_season_fixtures()
    if not fixtures:
        return pd.DataFrame()
    rows = [{
        "fixture_id": fx["fixture_id"],
        "round": stage11.round_number(fx.get("round")),
        "date_utc": fx.get("date"),
        "home_team": fx["home_team"],
        "away_team": fx["away_team"],
        "home_team_code": stage11.map_team(fx["home_team"]),
        "away_team_code": stage11.map_team(fx["away_team"]),
        "status": fx.get("status"),
    } for fx in fixtures if fx.get("status") in FINISHED_STATUSES]
    return pd.DataFrame(rows)


def harvest_fixtures(fixtures_df, fetcher, rate_limit_sec=RATE_LIMIT_SEC):
    """Scarica le formazioni per le fixture indicate (DataFrame con le colonne
    dello stage 11) e ritorna le righe grezze per giocatore (parse_event_lineup)."""
    rows = []
    for i, (_, fx) in enumerate(fixtures_df.iterrows()):
        fixture = {
            "fixture_id": int(fx["fixture_id"]),
            "round": int(fx["round"]),
            "date": fx.get("date_utc"),
            "home_team": fx.get("home_team"),
            "away_team": fx.get("away_team"),
        }
        lineup_data = fetcher(fixture["fixture_id"])
        if lineup_data is None:
            print(f"    [WARN] Formazioni non disponibili per event {fixture['fixture_id']} "
                  f"(giornata {fixture['round']}): saltato")
            continue
        match_rows = sofascore_api.parse_event_lineup(fixture, lineup_data)
        for r in match_rows:
            if r["venue"] == "home":
                r["team_code"] = fx.get("home_team_code")
                r["opponent_code"] = fx.get("away_team_code")
            else:
                r["team_code"] = fx.get("away_team_code")
                r["opponent_code"] = fx.get("home_team_code")
        rows.extend(match_rows)
        if i < len(fixtures_df) - 1:
            time.sleep(rate_limit_sec)
    return rows


def match_players(rows, dataset_df):
    """Aggiunge la colonna 'player' (nome dataset) alle righe via alias espliciti
    + PlayerMatcher. Ritorna (rows, n_matched, unmatched_descriptions)."""
    from core.ingestion.dynamic.utils import PlayerMatcher

    matcher = PlayerMatcher(dataset_df) if dataset_df is not None and not dataset_df.empty else None
    unmatched = []
    n_matched = 0
    for r in rows:
        name = r.get("player_sofascore")
        team = r.get("team_code")
        matched = config.SOFASCORE_PLAYER_ALIASES.get((name, team))
        if not matched and matcher is not None:
            matched = matcher.match(name, team)
        if matched:
            r["player"] = matched
            n_matched += 1
        else:
            r["player"] = ""
            unmatched.append(f"{name} ({team})")
    return rows, n_matched, unmatched


def merge_rows(existing_rows, new_rows):
    """Unisce le righe esistenti alle nuove deduplicando su (event_id, sofascore_player_id)."""
    seen = {(r.get("event_id"), r.get("sofascore_player_id")) for r in existing_rows}
    merged = list(existing_rows)
    added = 0
    for r in new_rows:
        key = (r.get("event_id"), r.get("sofascore_player_id"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(r)
        added += 1
    return merged, added


def load_existing_rows(csv_path):
    if not os.path.exists(csv_path):
        return []
    try:
        df = pd.read_csv(csv_path)
        return df.to_dict("records")
    except Exception:
        return []


def harvested_event_ids(rows):
    return {r.get("event_id") for r in rows if r.get("event_id") is not None
            and not (isinstance(r.get("event_id"), float) and pd.isna(r.get("event_id")))}


def main():
    print("=" * 60)
    print("  STAGE 12 — STATISTICHE PER-PARTITA GIOCATORI (Sofascore)")
    print("=" * 60)

    fixtures_df = load_finished_fixtures()
    if fixtures_df.empty:
        print("\n  [ERROR] Nessuna partita conclusa da raccogliere: esegui prima lo stage 11 "
              "(python run_pipeline.py --step 11).")
        return

    existing_rows = load_existing_rows(config.PLAYER_MATCH_STATS_CSV)
    done_ids = harvested_event_ids(existing_rows)
    todo = fixtures_df[~fixtures_df["fixture_id"].astype(int).isin(done_ids)]

    print(f"\n  Partite concluse: {len(fixtures_df)} · già raccolte: {len(done_ids)} "
          f"· da raccogliere: {len(todo)}")

    if todo.empty:
        print("\n  [OK] Nessuna nuova partita da raccogliere.")
        print(f"\n  Output: {config.PLAYER_MATCH_STATS_CSV}")
        print("\n  STAGE 12 COMPLETED.\n")
        return

    print(f"  Scarico {len(todo)} formazioni (1 richiesta/partita, ~{RATE_LIMIT_SEC}s di pausa)...")
    new_rows = harvest_fixtures(todo, sofascore_api.get_event_lineups)
    if not new_rows:
        print("\n  [ERROR] Nessuna riga raccolta (Sofascore irraggiungibile?).")
        return

    dataset_df = None
    if os.path.exists(config.DATASET_FINALE_CSV):
        dataset_df = pd.read_csv(config.DATASET_FINALE_CSV)
    new_rows, n_matched, unmatched = match_players(new_rows, dataset_df)

    merged, added = merge_rows(existing_rows, new_rows)
    df = pd.DataFrame(merged, columns=CSV_COLUMNS)
    df = df.sort_values(["round", "date_utc", "event_id"]).reset_index(drop=True)
    df.to_csv(config.PLAYER_MATCH_STATS_CSV, index=False, encoding="utf-8-sig")

    total_rows = len(df)
    print(f"\n  [OK] +{added} nuove righe ({len(todo)} partite) → {total_rows} righe totali")
    if dataset_df is not None:
        print(f"  Riconciliazione nomi: {n_matched}/{len(new_rows)} righe matchate sul dataset")
        if unmatched:
            unique_unmatched = sorted(set(unmatched))
            shown = ", ".join(unique_unmatched[:10]) + (" ..." if len(unique_unmatched) > 10 else "")
            print(f"  [WARN] {len(unique_unmatched)} giocatori non matchati: {shown}")
    print(f"\n  Output: {config.PLAYER_MATCH_STATS_CSV}")
    print("\n  STAGE 12 COMPLETED.\n")


if __name__ == "__main__":
    main()
