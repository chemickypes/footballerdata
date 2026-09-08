#!/usr/bin/env python3
"""
Export per-player career history (per-season rows) from the historical scrape
into data/player_history.json, keyed by normalized player name.

Consumed by the web app: /api/player_history?player=<name> (Traiettoria Carriera chart).

Source : data/storico_giocatori_raw.csv (stage 1 scrape, player x season rows)
Output : data/player_history.json
"""

import json
import os
import re
import sys

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_PATH = os.path.join(DATA_DIR, "storico_giocatori_raw.csv")
OUT_PATH = os.path.join(DATA_DIR, "player_history.json")

HISTORY_FIELDS = ["season", "team", "pg", "mv", "gol", "assist", "mfv"]


def normalize_name(s):
    """Shared normalization with the web layer: lower-case, no dots/apostrophes/hyphens/spaces."""
    return re.sub(r"[.'\-\s]", "", str(s or "").lower().strip())


def main():
    if not os.path.exists(RAW_PATH):
        print(f"Errore: {RAW_PATH} non trovato. Esegui prima: python run_pipeline.py --step 1")
        return 1

    df = pd.read_csv(RAW_PATH)
    df = df[df["pg"].notna() & (df["pg"] > 0) | df["mv"].notna()]

    out = {}
    for (name, role), grp in df.groupby(["player_name", "role"]):
        grp = grp.sort_values("season")
        history = []
        for _, r in grp.iterrows():
            row = {}
            for f in HISTORY_FIELDS:
                v = r.get(f)
                if pd.isna(v):
                    row[f] = None
                elif f in ("pg", "gol", "assist"):
                    row[f] = int(v)
                elif f in ("season", "team"):
                    row[f] = str(v)
                else:
                    row[f] = float(v)
            history.append(row)

        key = normalize_name(name)
        out[key] = {
            "name": str(name),
            "role": str(role),
            "history": history,
        }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)

    n_players = len(out)
    n_rows = sum(len(v["history"]) for v in out.values())
    size_kb = os.path.getsize(OUT_PATH) / 1024
    print(f"Exported {n_players} players / {n_rows} player-season rows -> {OUT_PATH} ({size_kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
