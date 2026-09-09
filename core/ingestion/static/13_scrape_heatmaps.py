#!/usr/bin/env python3
"""
STAGE 13 — Heatmap stagionali dei giocatori (Sofascore).

Per ogni coppia (partita, giocatore) presente in data/player_match_stats.csv
(stage 12) e non ancora raccolta, scarica l'heatmap da
/event/{id}/player/{pid}/heatmap e la archivia per-evento in
data/player_heatmaps.json.

Schema v2: per ogni giocatore, "by_event" mappa event_id -> griglia 30x20
della singola partita (+ round e minuti); l'aggregato stagionale (grid,
matches, minutes, points) e' DERIVATO da by_event. Cosi' l'endpoint web puo'
ricostruire heatmap cumulative "fino alla giornata N" o di una singola
giornata, oltre alla stagione completa.

Griglia: HEATMAP_GRID_COLS x HEATMAP_GRID_ROWS celle su campo normalizzato
100x100. Coordinate Sofascore team-normalizzate (verificato empiricamente su
portieri casa/trasferta della stessa partita): x=0 porta propria, x=100 porta
avversaria, y=0..100 larghezza — nessun mirroring necessario.

Incrementale: le coppie (giocatore, evento) gia' presenti in by_event non
vengono riscaricate. Salvataggio a chunk (ogni CHUNK_SIZE coppie) per non
perdere progresso in caso di interruzione; fail-fast dopo N fallimenti
consecutivi (riprendere rilanciando).

Opzionale: --limit N per limitare le richieste di una singola esecuzione.
"""

import argparse
import json
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
from core.ingestion.static import sofascore_api

HEATMAP_GRID_COLS = 30
HEATMAP_GRID_ROWS = 20
RATE_LIMIT_SEC = 0.4
CHUNK_SIZE = 50
FAIL_FAST_CONSECUTIVE = 10


def points_to_grid(points, cols=HEATMAP_GRID_COLS, rows=HEATMAP_GRID_ROWS):
    """Converte una lista di punti {x, y} (0-100) in una griglia piatta di conteggi."""
    grid = [0] * (cols * rows)
    for p in points or []:
        try:
            x, y = float(p.get("x")), float(p.get("y"))
        except (TypeError, ValueError, AttributeError):
            continue
        if not (0 <= x <= 100 and 0 <= y <= 100):
            continue
        cx = min(int(x / 100.0 * cols), cols - 1)
        cy = min(int(y / 100.0 * rows), rows - 1)
        grid[cy * cols + cx] += 1
    return grid


def add_grids(a, b):
    """Somma elemento per elemento di due griglie piatte."""
    return [x + y for x, y in zip(a, b)]


def recompute_aggregate(entry, cols=HEATMAP_GRID_COLS, rows=HEATMAP_GRID_ROWS):
    """Ricalcola grid/matches/minutes/points dal dict by_event dell'entry."""
    agg = [0] * (cols * rows)
    matches = minutes = points = 0
    for ev in (entry.get("by_event") or {}).values():
        agg = add_grids(agg, ev.get("grid") or [])
        matches += 1
        minutes += int(ev.get("minutes") or 0)
        points += sum(ev.get("grid") or [])
    entry["grid"] = agg
    entry["matches"] = matches
    entry["minutes"] = minutes
    entry["points"] = points
    return entry


def load_heatmaps(path=None):
    """Carica player_heatmaps.json; struttura vuota se il file manca/corrotto."""
    path = path or config.PLAYER_HEATMAPS_JSON
    empty = {
        "grid": {"cols": HEATMAP_GRID_COLS, "rows": HEATMAP_GRID_ROWS},
        "players": {},
    }
    if not os.path.exists(path):
        return empty
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return empty
    if not isinstance(data, dict) or "players" not in data:
        return empty
    data.setdefault("grid", {"cols": HEATMAP_GRID_COLS, "rows": HEATMAP_GRID_ROWS})
    data.setdefault("players", {})
    return data


def save_heatmaps(data, path=None):
    path = path or config.PLAYER_HEATMAPS_JSON
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def build_todo(stats_df, heatmaps_data):
    """Coppie (player, event_id, player_id, round, minutes) ancora da raccogliere.
    Salta righe senza nome dataset, senza sofascore_player_id o gia' presenti
    in by_event (chiave stringa: le chiavi JSON sono stringhe)."""
    players = heatmaps_data.get("players", {})
    todo = []
    seen = set()
    for _, r in stats_df.iterrows():
        name = r.get("player")
        pid = r.get("sofascore_player_id")
        ev = r.get("event_id")
        if pd.isna(name) or not str(name).strip():
            continue
        if pd.isna(pid) or pd.isna(ev):
            continue
        try:
            minutes = int(r.get("minutes_played") or 0)
        except (TypeError, ValueError):
            minutes = 0
        try:
            rnd = int(r.get("round") or 0)
        except (TypeError, ValueError):
            rnd = 0
        ev_key = str(int(ev))
        item = {
            "player": str(name),
            "event_id": int(ev),
            "event_key": ev_key,
            "player_id": int(pid),
            "round": rnd,
            "minutes": minutes,
        }
        pair = (item["player"], ev_key)
        if pair in seen:
            continue
        seen.add(pair)
        entry = players.get(item["player"]) or {}
        if ev_key in (entry.get("by_event") or {}):
            continue
        todo.append(item)
    return todo


def harvest(todo, fetcher=None, rate_limit_sec=RATE_LIMIT_SEC, limit=None,
            on_chunk=None):
    """Scarica le heatmap del todo e le archivia per-evento. fetcher
    iniettabile per i test; on_chunk() invocato ogni CHUNK_SIZE per salvare.
    Ritorna (heatmaps_data, n_ok, n_fail)."""
    fetcher = fetcher or sofascore_api.get_player_heatmap
    data = load_heatmaps()
    players = data["players"]
    cols = data["grid"]["cols"]
    rows = data["grid"]["rows"]

    n_ok = n_fail = 0
    consecutive_fails = 0
    batch = todo if limit is None else todo[:limit]
    for i, item in enumerate(batch):
        points = fetcher(item["event_id"], item["player_id"])
        if points is None:
            n_fail += 1
            consecutive_fails += 1
            if consecutive_fails >= FAIL_FAST_CONSECUTIVE:
                raise RuntimeError(
                    "Sofascore non raggiungibile (10 fallimenti consecutivi): "
                    "possibile rate-limit/blocco temporaneo, rilanciare piu' tardi "
                    "(il run e' incrementale e riprende da dove si e' fermato).")
            continue
        consecutive_fails = 0

        entry = players.setdefault(item["player"], {"by_event": {}})
        entry.setdefault("by_event", {})[item["event_key"]] = {
            "round": item["round"],
            "minutes": item["minutes"],
            "grid": points_to_grid(points, cols, rows),
        }
        recompute_aggregate(entry, cols, rows)
        n_ok += 1

        if on_chunk is not None and (i + 1) % CHUNK_SIZE == 0:
            on_chunk()
        if i < len(batch) - 1:
            time.sleep(rate_limit_sec)

    return data, n_ok, n_fail


def main():
    parser = argparse.ArgumentParser(description="Stage 13 — Heatmap stagionali (Sofascore)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Numero massimo di heatmap da scaricare in questa esecuzione")
    args, _ = parser.parse_known_args(sys.argv[1:])

    print("=" * 60)
    print("  STAGE 13 — HEATMAP STAGIONALI GIOCATORI (Sofascore)")
    print("=" * 60)

    if not os.path.exists(config.PLAYER_MATCH_STATS_CSV):
        print("\n  [ERROR] data/player_match_stats.csv mancante: esegui prima lo stage 12 "
              "(python run_pipeline.py --step 12).")
        return

    stats_df = pd.read_csv(config.PLAYER_MATCH_STATS_CSV)
    data = load_heatmaps()
    todo = build_todo(stats_df, data)

    print(f"\n  Righe partita-giocatore: {len(stats_df)} · giocatori con heatmap: "
          f"{len(data['players'])} · da scaricare: {len(todo)}"
          + (f" (limite: {args.limit})" if args.limit else ""))

    if not todo:
        print("\n  [OK] Nessuna nuova heatmap da scaricare.")
        print(f"\n  Output: {config.PLAYER_HEATMAPS_JSON}")
        print("\n  STAGE 13 COMPLETED.\n")
        return

    def on_chunk():
        save_heatmaps(data)
        print(f"  ... {sum(len(e.get('by_event', {})) for e in data['players'].values())}"
              f"/{len(todo)} coppie archiviate (salvate)")

    data, n_ok, n_fail = harvest(todo, limit=args.limit, on_chunk=on_chunk)
    save_heatmaps(data)

    size_kb = os.path.getsize(config.PLAYER_HEATMAPS_JSON) / 1024
    print(f"\n  [OK] {n_ok} heatmap archiviate ({n_fail} fallite/ritentabili) · "
          f"{len(data['players'])} giocatori · {size_kb:.0f} KB")

    top = sorted(data["players"].items(), key=lambda kv: kv[1]["points"], reverse=True)[:5]
    print("\n  Piu' attivi (tocchi registrati):")
    for name, e in top:
        print(f"    {name:24s} {e['points']:5d} tocchi · {e['matches']} partite")

    print(f"\n  Output: {config.PLAYER_HEATMAPS_JSON}")
    print("\n  STAGE 13 COMPLETED.\n")


if __name__ == "__main__":
    main()
