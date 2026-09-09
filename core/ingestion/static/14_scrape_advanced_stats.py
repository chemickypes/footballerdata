#!/usr/bin/env python3
"""
STAGE 14 — Statistiche avanzate di stagione per giocatore (Sofascore).

Per ogni giocatore presente in data/player_match_stats.csv (stage 12, da cui
riusa gli id Sofascore) scarica le statistiche aggregate di stagione Serie A
da /player/{id}/unique-tournament/23/season/{sid}/statistics/overall (~115
metriche: passaggi, dribbling, duelli, difesa, portiere, cartellini) e le
aggrega in data/player_advanced.json con:

  - totals: conteggi della stagione (gol, assist, xG, tackle, recuperi...)
  - per90:  medie per 90 minuti (dai conteggi)
  - pcts:   percentuali (passaggi riusciti, dribbling, duelli...)
  - cards:  cartellini gialli/rossi (non disponibili nello stage 12)
  - percentiles: posizione percentile (0-100) di ogni metrica/percentuale
    rispetto ai pari ruolo (stesso ruolo dataset, min. MIN_MINUTES giocati)

Nota storica: l'obiettivo iniziale era FBref, ma il sito e' dietro un
challenge Cloudflare invalicabile da script; le stesse famiglie di statistiche
vengono da Sofascore, gia' usato dagli stage 11-13.

Incrementale: i giocatori gia' presenti nel JSON con la stagione corrente non
vengono riscaricati (usare --refresh per rifare tutto).
"""

import argparse
import datetime
import json
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
from core.ingestion.static import sofascore_api

RATE_LIMIT_SEC = 0.4
MIN_MINUTES = 60          # minuti minimi per entrare nel pool dei pari ruolo
MIN_MINUTES_PER90 = 30    # minuti minimi per esporre le medie per 90

# Conteggi -> chiavi curate (tot = chiave Sofascore)
TOTAL_MAP = {
    "goals": "goals",
    "assists": "assists",
    "xg": "expectedGoals",
    "xa": "expectedAssists",
    "shots": "totalShots",
    "shots_on_target": "shotsOnTarget",
    "key_passes": "keyPasses",
    "big_chances_created": "bigChancesCreated",
    "big_chances_missed": "bigChancesMissed",
    "passes_final_third": "accurateFinalThirdPasses",
    "crosses": "accurateCrosses",
    "long_balls": "accurateLongBalls",
    "tackles": "tackles",
    "interceptions": "interceptions",
    "clearances": "clearances",
    "blocks": "outfielderBlocks",
    "aerials_won": "aerialDuelsWon",
    "aerials_lost": "aerialLost",
    "ball_recoveries": "ballRecovery",
    "dribbles": "successfulDribbles",
    "dribbles_attempted": "totalContest",
    "dispossessed": "dispossessed",
    "possession_lost": "possessionLost",
    "possession_won_att_third": "possessionWonAttThird",
    "was_fouled": "wasFouled",
    "fouls": "fouls",
    "offsides": "offsides",
    "dribbled_past": "dribbledPast",
    "errors_lead_to_shot": "errorLeadToShot",
    "errors_lead_to_goal": "errorLeadToGoal",
}

# Percentuali dirette (gia' nella risposta)
PCT_MAP = {
    "passes_pct": "accuratePassesPercentage",
    "dribbles_pct": "successfulDribblesPercentage",
    "aerials_pct": "aerialDuelsWonPercentage",
    "duels_pct": "totalDuelsWonPercentage",
    "tackles_pct": "tacklesWonPercentage",
    "long_balls_pct": "accurateLongBallsPercentage",
}

# Metriche da portare a per-90 (sottinsieme dei conteggi)
PER90_KEYS = [
    "goals", "assists", "xg", "xa", "shots", "shots_on_target", "key_passes",
    "big_chances_created", "passes_final_third", "crosses", "touches",
    "dribbles", "tackles", "interceptions", "clearances", "blocks",
    "aerials_won", "ball_recoveries",
]

# Conteggi specifici portieri
KEEPER_TOTAL_MAP = {
    "saves": "saves",
    "saves_caught": "savesCaught",
    "saves_parried": "savesParried",
    "high_claims": "highClaims",
    "punches": "punches",
    "goals_prevented": "goalsPrevented",
    "clean_sheets": "cleanSheet",
    "goals_conceded": "goalsConceded",
    "penalty_saves": "penaltySave",
    "crosses_not_claimed": "crossesNotClaimed",
    "runs_out": "runsOut",
}

KEEPER_PER90_KEYS = ["saves", "high_claims", "punches", "runs_out"]

# Metriche con percentile per gli outfield (tutte dove "piu' alto = meglio")
PERCENTILE_KEYS = [f"{k}_per90" for k in PER90_KEYS] + list(PCT_MAP.keys())

# Metriche con percentile per i portieri
KEEPER_PERCENTILE_KEYS = [
    "saves_per90", "high_claims_per90", "punches_per90", "clean_sheets_per90",
    "goals_prevented", "passes_pct", "long_balls_pct",
]


def curate_statistics(raw, is_keeper=False):
    """Da un dict Sofascore 'statistics' alle metriche curate del JSON.

    Ritorna dict con minutes, appearances, matches_started, rating,
    cards, totals, pcts, per90 (None se minuti < MIN_MINUTES_PER90)."""
    def _f(key):
        v = raw.get(key)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    minutes = _f("minutesPlayed") or 0.0
    totals = {}
    for out_key, src_key in TOTAL_MAP.items():
        v = _f(src_key)
        if v is not None:
            totals[out_key] = v
    if "touches" in raw:
        try:
            totals["touches"] = float(raw["touches"])
        except (TypeError, ValueError):
            pass
    if is_keeper:
        for out_key, src_key in KEEPER_TOTAL_MAP.items():
            v = _f(src_key)
            if v is not None:
                totals[out_key] = v

    pcts = {k: _f(src) for k, src in PCT_MAP.items() if _f(src) is not None}

    per90 = None
    if minutes >= MIN_MINUTES_PER90:
        per90 = {}
        for k in PER90_KEYS:
            if k in totals:
                per90[f"{k}_per90"] = round(totals[k] / minutes * 90.0, 2)
        if is_keeper:
            for k in KEEPER_PER90_KEYS:
                if k in totals:
                    per90[f"{k}_per90"] = round(totals[k] / minutes * 90.0, 2)

    cards = {
        "yellow": int(_f("yellowCards") or 0),
        "red": int(_f("redCards") or 0),
        "yellow_red": int(_f("yellowRedCards") or 0),
        "direct_red": int(_f("directRedCards") or 0),
    }

    return {
        "minutes": int(minutes),
        "appearances": int(_f("appearances") or 0),
        "matches_started": int(_f("matchesStarted") or 0),
        "rating": _f("rating"),
        "cards": cards,
        "totals": totals,
        "pcts": pcts,
        "per90": per90,
    }


def percentile_of(values, x):
    """Percentile (0-100) di x nella distribuzione values: share di pari ruolo
    non superiore a x (i pari valore contano come non meglio di te).
    None se x assente o pool insufficiente."""
    clean = [v for v in values if v is not None]
    if x is None or not clean:
        return None
    not_worse = sum(1 for v in clean if v <= x)
    return round(not_worse / len(clean) * 100.0, 1)


def _stat_value(entry, key):
    """Legge un valore per-90 o pct dall'entry (None-safe anche per 0.0)."""
    v = (entry.get("per90") or {}).get(key)
    if v is None:
        v = (entry.get("pcts") or {}).get(key)
    return v


def compute_percentiles(entry, pool, role_key="outfield"):
    """Aggiunge entry['percentiles'] confrontando con il pool (altri giocatori
    stesso ruolo con minuti >= MIN_MINUTES). pool: lista di dict curati."""
    keys = KEEPER_PERCENTILE_KEYS if role_key == "keeper" else PERCENTILE_KEYS
    percentiles = {}
    for key in keys:
        if key == "goals_prevented":
            mine = (entry["totals"] or {}).get("goals_prevented")
            theirs = [(p["totals"] or {}).get("goals_prevented") for p in pool]
        else:
            mine = _stat_value(entry, key)
            theirs = [_stat_value(p, key) for p in pool]
        pct = percentile_of(theirs, mine)
        if pct is not None:
            percentiles[key] = pct
    entry["percentiles"] = percentiles


def load_advanced(path=None):
    """Carica player_advanced.json; struttura vuota se il file manca/corrotto."""
    path = path or config.PLAYER_ADVANCED_JSON
    empty = {"source": "Sofascore player season statistics (overall)",
             "season_id": None, "players": {}}
    if not os.path.exists(path):
        return empty
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return empty
    if not isinstance(data, dict) or "players" not in data:
        return empty
    data.setdefault("players", {})
    data.setdefault("season_id", None)
    return data


def save_advanced(data, path=None):
    path = path or config.PLAYER_ADVANCED_JSON
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def build_pairs(stats_df):
    """Coppie (player, sofascore_player_id) distinte dal CSV stage 12, in ordine.

    Puo' capitare (mismatch di nomi homonimi in stage 12) che uno stesso nome
    dataset sia associato a piu' id Sofascore: qui restano coppie distinte e
    la risoluzione avviene in resolve_players()."""
    pairs = []
    seen = set()
    for _, r in stats_df.iterrows():
        name = r.get("player")
        pid = r.get("sofascore_player_id")
        if pd.isna(name) or not str(name).strip():
            continue
        if pd.isna(pid):
            continue
        name, pid = str(name), int(pid)
        if (name, pid) in seen:
            continue
        seen.add((name, pid))
        pairs.append((name, pid))
    return pairs


def build_todo(pairs, existing, season_id, refresh=False):
    """Coppie da scaricare (incrementale per stagione). Un pid e' considerato
    gia' raccolto se l'entry del nome ha la stagione corrente, quel pid tra
    quelli gia' controllati (sofascore_player_id o checked_ids) e il team_code
    valorizzato (schema completo). Le coppie di un nome con piu' id vengono
    comunque riscaricate se l'entry non ha registrato la risoluzione degli
    omonimi (duplicate_ids assente: risoluzione vecchia/interrotta)."""
    players = existing.get("players", {})
    ids_per_name = {}
    for name, pid in pairs:
        ids_per_name.setdefault(name, set()).add(pid)

    todo = []
    for name, pid in pairs:
        if refresh:
            todo.append((name, pid))
            continue
        entry = players.get(name)
        if not entry or entry.get("season_id") != season_id or entry.get("team_code") is None:
            todo.append((name, pid))
            continue
        if len(ids_per_name.get(name, ())) > 1 and not entry.get("duplicate_ids"):
            todo.append((name, pid))  # omonimo mai risolto esplicitamente
            continue
        checked = set(entry.get("checked_ids") or [])
        if entry.get("sofascore_player_id") is not None:
            checked.add(int(entry["sofascore_player_id"]))
        if pid not in checked:
            todo.append((name, pid))
    return todo


def build_pair_teams(stats_df):
    """{(name, pid): team_code} dal CSV stage 12 (modalita' dei team_code visti)."""
    out = {}
    for (name, pid), g in stats_df.groupby(["player", "sofascore_player_id"]):
        if pd.isna(name) or pd.isna(pid):
            continue
        codes = g["team_code"].dropna()
        if len(codes):
            out[(str(name), int(pid))] = str(codes.mode().iloc[0])
    return out


def resolve_players(by_name, expected_teams=None):
    """Da {name: [entry, ...]} al dict players finale.

    Se l'entry del nome ha un team atteso (expected_teams[name] = codice squadra
    del dataset), tra gli id omonimi vince quello della squadra giusta; a parita'
    (o se non disponibile) vince la entry con piu' minuti. Gli id scartati
    restano registrati in duplicate_ids; le entry no_data cedono a quelle con
    dati; i duplicati sul medesimo pid si risolvono a favore della piu' fresca."""
    players = {}
    for name, entries in by_name.items():
        # dedupe per pid: vince la PRIMA (l'entry appena fetchata, che arriva
        # prima delle vecchie nella lista costruita da merge_and_save)
        by_pid = {}
        for e in entries:
            pid = e.get("sofascore_player_id")
            if pid is None or pid in by_pid:
                continue
            by_pid[pid] = e
        pool_entries = list(by_pid.values())
        with_data = [e for e in pool_entries if not e.get("no_data")]
        source = with_data or pool_entries
        if not source:
            continue
        expected = (expected_teams or {}).get(name)
        if expected:
            # candidati: squadra attesa O team sconosciuto (entry vecchie senza
            # team_code restano in gara); esclusi solo i team noti e diversi
            matched = [e for e in source
                       if e.get("team_code") == expected or e.get("team_code") is None]
            cands = matched or source
        else:
            cands = source
        winner = max(cands, key=lambda e: (e.get("minutes") or 0))
        win_pid = winner.get("sofascore_player_id")
        dupes = [{"id": pid, "minutes": e.get("minutes") or 0,
                  "no_data": bool(e.get("no_data"))}
                 for pid, e in by_pid.items() if pid != win_pid]
        winner["checked_ids"] = sorted(by_pid)
        if dupes:
            winner["duplicate_ids"] = dupes
        players[name] = winner
    return players


def merge_and_save(existing, fetched, teams, season_id, path=None):
    """Risolve gli omonimi (fetch appena fatto + entry esistenti della stagione
    corrente), applica i percentili, fonde nel JSON e salva. Usata a fine run e
    a ogni chunk, cosi' un'interruzione non perde il progresso."""
    by_name = {}
    for (name, pid), entry in fetched.items():
        by_name.setdefault(name, []).append(entry)
    existing_players = existing.get("players", {})
    for name in list(by_name):
        old = existing_players.get(name)
        if old and old.get("season_id") == season_id:
            by_name[name].append(old)
    resolved = resolve_players(by_name, expected_teams=teams)

    merged = dict(existing_players)
    for name, entry in resolved.items():
        if entry.get("no_data") and name in merged and not merged[name].get("no_data"):
            continue  # non degradare un'entry valida esistente
        merged[name] = entry

    data = {"source": existing.get("source", "Sofascore player season statistics (overall)"),
            "season_id": season_id, "updated": _now(), "players": merged}
    apply_percentiles(data["players"])
    save_advanced(data, path)
    return data


def harvest(pairs, roles, season_id, fetcher=None, rate_limit_sec=RATE_LIMIT_SEC,
            pair_teams=None, on_chunk=None, chunk_size=50):
    """Scarica e cura le statistiche delle coppie (name, pid).
    fetcher iniettabile per test. on_chunk(fetched_so_far) ogni chunk_size coppie
    processate (per salvataggi incrementali). Ritorna {(name, pid): entry, ...}."""
    fetcher = fetcher or sofascore_api.get_player_season_statistics
    pair_teams = pair_teams or {}
    fetched = {}
    n_ok = n_fail = 0
    consecutive_fails = 0
    for i, (name, pid) in enumerate(pairs):
        raw = fetcher(pid, season_id)
        if raw is None:
            n_fail += 1
            consecutive_fails += 1
            if consecutive_fails >= 10:
                raise RuntimeError(
                    "Sofascore non raggiungibile (10 fallimenti consecutivi): "
                    "possibile rate-limit/blocco temporaneo, rilanciare piu' tardi "
                    "(il run e' incrementale e riprende da dove si e' fermato).")
            continue
        consecutive_fails = 0
        if not raw:
            # stagione senza dati per questo giocatore: entry vuota segnalata
            fetched[(name, pid)] = {"sofascore_player_id": pid, "season_id": season_id,
                                    "no_data": True, "updated": _now(),
                                    "team_code": pair_teams.get((name, pid))}
            n_ok += 1
        else:
            is_keeper = roles.get(name) == "P"
            entry = curate_statistics(raw, is_keeper=is_keeper)
            entry.update({"sofascore_player_id": pid, "season_id": season_id,
                          "role": roles.get(name), "updated": _now(),
                          "team_code": pair_teams.get((name, pid))})
            fetched[(name, pid)] = entry
            n_ok += 1
        if on_chunk is not None and (i + 1) % chunk_size == 0:
            on_chunk(fetched)
        if i < len(pairs) - 1:
            time.sleep(rate_limit_sec)
    return fetched, n_ok, n_fail


def apply_percentiles(players):
    """Percentili vs pari ruolo (ruolo dataset, minuti >= MIN_MINUTES)."""
    eligible = {n: e for n, e in players.items()
                if not e.get("no_data") and (e.get("minutes") or 0) >= MIN_MINUTES}
    for name, entry in players.items():
        if entry.get("no_data") or (entry.get("minutes") or 0) < MIN_MINUTES:
            entry["percentiles"] = {}
            continue
        role = entry.get("role")
        role_key = "keeper" if role == "P" else "outfield"
        pool = [e for n, e in eligible.items()
                if n != name and (e.get("role") == role or role is None)]
        compute_percentiles(entry, pool, role_key=role_key)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def main():
    parser = argparse.ArgumentParser(description="Stage 14 — Statistiche avanzate stagione (Sofascore)")
    parser.add_argument("--refresh", action="store_true",
                        help="Riscarica anche i giocatori gia' presenti per la stagione corrente")
    args, _ = parser.parse_known_args(sys.argv[1:])

    print("=" * 60)
    print("  STAGE 14 — STATISTICHE AVANZATE GIOCATORI (Sofascore)")
    print("=" * 60)

    if not os.path.exists(config.PLAYER_MATCH_STATS_CSV):
        print("\n  [ERROR] data/player_match_stats.csv mancante: esegui prima lo stage 12 "
              "(python run_pipeline.py --step 12).")
        return

    season_id = sofascore_api.get_serie_a_season_id()
    stats_df = pd.read_csv(config.PLAYER_MATCH_STATS_CSV)
    existing = load_advanced()

    # Ruoli e squadre dal dataset (percentili vs pari ruolo + risoluzione omonimi)
    roles = {}
    teams = {}
    if os.path.exists(config.DATASET_FINALE_CSV):
        ds = pd.read_csv(config.DATASET_FINALE_CSV)
        role_col = next((c for c in ("role", "R") if c in ds.columns), None)
        if role_col:
            roles = dict(zip(ds["player"].astype(str), ds[role_col].astype(str)))
        if "team" in ds.columns:
            teams = dict(zip(ds["player"].astype(str), ds["team"].astype(str)))

    pairs = build_pairs(stats_df)
    todo = build_todo(pairs, existing, season_id, refresh=args.refresh)
    print(f"\n  Stagione: {season_id} · coppie giocatore/id in stage 12: {len(pairs)} · "
          f"da scaricare: {len(todo)}" + (" (refresh)" if args.refresh else ""))

    if not todo:
        print("\n  [OK] Nessun aggiornamento necessario.")
        print(f"\n  Output: {config.PLAYER_ADVANCED_JSON}")
        print("\n  STAGE 14 COMPLETED.\n")
        return

    fetched, n_ok, n_fail = harvest(
        todo, roles, season_id, pair_teams=build_pair_teams(stats_df),
        on_chunk=lambda fetched_so_far: (
            print(f"  ... {len(fetched_so_far)}/{len(todo)} scaricate (salvate)"),
            merge_and_save(existing, fetched_so_far, teams, season_id)))

    data = merge_and_save(existing, fetched, teams, season_id)

    size_kb = os.path.getsize(config.PLAYER_ADVANCED_JSON) / 1024
    n_dupes = sum(1 for e in data["players"].values() if e.get("duplicate_ids"))
    print(f"\n  [OK] {n_ok} giocatori ({n_fail} falliti/ritentabili) · "
          f"{len(data['players'])} totali nel JSON · {n_dupes} omonimi risolti · {size_kb:.0f} KB")

    ranked = [(n, e) for n, e in data["players"].items()
              if not e.get("no_data") and (e.get("per90") or {}).get("xg_per90")]
    if ranked:
        print("\n  Top per xG/90:")
        for n, e in sorted(ranked, key=lambda kv: kv[1]["per90"]["xg_per90"], reverse=True)[:5]:
            print(f"    {n:24s} {e['per90']['xg_per90']:.2f} xG/90 · "
                  f"{e['totals'].get('goals', 0):.0f} gol · {e['minutes']} min")

    print(f"\n  Output: {config.PLAYER_ADVANCED_JSON}")
    print("\n  STAGE 14 COMPLETED.\n")


if __name__ == "__main__":
    main()
