#!/usr/bin/env python3
"""
Esporta le statistiche di disciplina raccolte via ESPN (cache crowdsourced
data/espn_match_events.json, alimentata dalle visite alle pagine partita) e le
aggiunge al dataset giocatori.

Cosa fa:
  1. Legge data/espn_match_events.json (eventi per fixture: gol/cartellini/cambi)
  2. Risolve i nomi completi ESPN sui nomi brevi del dataset:
       - match normalizzato del nome completo
       - cognome: ultimo token ESPN vs primo token dataset ("Kamara H.")
       - fallback: il nome ESPN termina con il nome dataset ("de Roon")
     La disambiguazione tra omonimi usa la squadra: il lato (home/away) della
    azione + data/match_results.csv -> team_code ("Marcus Thuram" INT vs
     "Khephren Thuram" JUV).
  3. Aggrega per giocatore: ammonizioni (yellow), espulsioni (red), dettaglio.
  4. Scrive data/espn_player_cards.json.
  5. Aggiorna data/dataset_finale.csv con le colonne yellow_cards_espn /
     red_cards_espn (0 dove non ci sono dati), preservando il resto del CSV
     byte per byte (nessuna riscrittura pandas).

Nota: la copertura dipende dalle partite visitate (la cache e' crowdsourced):
0 cartellini significa "nessun dato raccolto", non "giocatore prudente".

Uso: python export_player_cards.py
"""

import csv
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ESPN_EVENTS_JSON = os.environ.get("ESPN_EVENTS_JSON", os.path.join(DATA_DIR, "espn_match_events.json"))
MATCH_RESULTS_CSV = os.path.join(DATA_DIR, "match_results.csv")
DATASET_CSV = os.path.join(DATA_DIR, "dataset_finale.csv")
OUTPUT_JSON = os.path.join(DATA_DIR, "espn_player_cards.json")

CARD_KINDS = {"yellow": "yellow_cards", "red": "red_cards"}


def norm_name(s):
    """Normalizza un nome: lowercase, niente accenti/segni/spazi."""
    import unicodedata
    s = unicodedata.normalize("NFD", str(s or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return "".join(c for c in s.lower() if c.isalpha())


def load_fixtures_map(csv_path):
    """fixture_id -> (home_team_code, away_team_code)."""
    fixtures = {}
    if not os.path.exists(csv_path):
        return fixtures
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                fid = int(row.get("fixture_id") or 0)
            except ValueError:
                continue
            home = (row.get("home_team_code") or "").strip()
            away = (row.get("away_team_code") or "").strip()
            rnd = (row.get("round") or "").strip()
            if fid:
                fixtures[fid] = (home, away, rnd)
    return fixtures


def resolve_player(espn_name, team_code, dataset_rows):
    """Risolve un nome ESPN nel nome dataset. dataset_rows: [(nome, team_code)]."""
    target = norm_name(espn_name)
    if not target:
        return None
    parts = [p for p in str(espn_name or "").replace("-", " ").replace("'", " ").split() if p]
    surname = norm_name(parts[-1]) if parts else ""
    hits = [name for name, _ in dataset_rows if norm_name(name) == target]
    if not hits and surname:
        hits = [name for name, _ in dataset_rows
                if name.split() and norm_name(name.split()[0]) == surname]
    if not hits:
        hits = [name for name, _ in dataset_rows
                if len(norm_name(name)) >= 4 and target.endswith(norm_name(name))]
    if not hits:
        return None
    if len(hits) > 1 and team_code:
        same_team = [n for n in hits
                     if dict(dataset_rows).get(n) == team_code]
        if same_team:
            return same_team[0]
    if len(hits) > 1:
        return None  # omonimi non disambiguabili
    return hits[0]


def aggregate_cards(events_path, fixtures_map, dataset_rows):
    """Aggrega i cartellini per giocatore dataset dalla cache ESPN."""
    if not os.path.exists(events_path):
        return {"matches_covered": 0, "players": {}, "unresolved": []}
    try:
        with open(events_path, "r", encoding="utf-8") as f:
            store = json.load(f)
    except Exception:
        return {"matches_covered": 0, "players": {}, "unresolved": []}

    players = {}
    unresolved = {}
    matches_covered = 0
    for key, entry in store.items():
        try:
            fid = int(key)
        except ValueError:
            continue
        events = entry.get("events") or []
        if not events:
            continue
        matches_covered += 1
        fx = fixtures_map.get(fid, ("", "", ""))
        for ev in events:
            kind = ev.get("kind")
            if kind not in CARD_KINDS:
                continue
            side = ev.get("side")
            team_code = fx[0] if side == "home" else (fx[1] if side == "away" else "")
            name = resolve_player(ev.get("player"), team_code, dataset_rows)
            if not name:
                slug = f"{ev.get('player')}|{team_code or '?'}"
                unresolved[slug] = unresolved.get(slug, 0) + 1
                continue
            slot = players.setdefault(name, {
                "team": dict(dataset_rows).get(name, ""),
                "yellow_cards": 0,
                "red_cards": 0,
                "matches": [],
            })
            slot[CARD_KINDS[kind]] += 1
            slot["matches"].append({
                "fixture_id": fid,
                "round": fx[2],
                "kind": kind,
                "minute": ev.get("minute"),
            })
    return {
        "matches_covered": matches_covered,
        "players": players,
        "unresolved": [{"name": k.split("|")[0], "team": k.split("|")[1], "occurrences": v}
                       for k, v in sorted(unresolved.items(), key=lambda kv: -kv[1])],
    }


def update_dataset_csv(csv_path, players):
    """Aggiorna/crea le colonne yellow_cards_espn e red_cards_espn riscrivendo
    solo i due campi. Il file viene preservato: BOM iniziale (se presente),
    fine riga LF (come l'output pandas dello stage 6), valori originali delle
    altre colonne invariati byte per byte."""
    with open(csv_path, "rb") as f:
        has_bom = f.read(3) == b"\xef\xbb\xbf"
    enc = "utf-8-sig" if has_bom else "utf-8"
    with open(csv_path, newline="", encoding=enc) as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    for col in ("yellow_cards_espn", "red_cards_espn"):
        if col not in fieldnames:
            fieldnames.append(col)
    for row in rows:
        slot = players.get(row.get("player") or "", {})
        row["yellow_cards_espn"] = int(slot.get("yellow_cards") or 0)
        row["red_cards_espn"] = int(slot.get("red_cards") or 0)
    tmp = csv_path + ".tmp"
    with open(tmp, "w", newline="", encoding=enc) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, csv_path)


def main():
    print("=" * 60)
    print("  ESPORTAZIONE CARTELLINI ESPN (cache crowdsourced) -> dataset")
    print("=" * 60)

    if not os.path.exists(DATASET_CSV):
        print(f"\n  [ERROR] {DATASET_CSV} mancante (esegui prima lo stage 6).")
        return 1
    if not os.path.exists(ESPN_EVENTS_JSON):
        print(f"\n  [WARN] {ESPN_EVENTS_JSON} assente: nessun evento ESPN ancora raccolto.")
        print("  Visita le pagine partita nel web app per alimentare la cache.")

    with open(DATASET_CSV, newline="", encoding="utf-8-sig") as f:
        dataset_rows = [(r.get("player") or "", (r.get("team") or "").strip())
                        for r in csv.DictReader(f)]
    fixtures_map = load_fixtures_map(MATCH_RESULTS_CSV)
    result = aggregate_cards(ESPN_EVENTS_JSON, fixtures_map, dataset_rows)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            **result,
        }, f, ensure_ascii=False, indent=1)

    n_cards = sum(p["yellow_cards"] + p["red_cards"] for p in result["players"].values())
    print(f"\n  Partite nella cache: {result['matches_covered']}")
    print(f"  Giocatori con cartellini risolti: {len(result['players'])} ({n_cards} cartellini)")
    if result["unresolved"]:
        print(f"  Nomi non risolti: {len(result['unresolved'])} (es. "
              + ", ".join(u['name'] for u in result['unresolved'][:3]) + ")")

    update_dataset_csv(DATASET_CSV, result["players"])
    print(f"\n  [OK] Colonne yellow_cards_espn / red_cards_espn aggiornate in {DATASET_CSV}")
    print(f"  [OK] Dettaglio salvato in {OUTPUT_JSON}")
    print("\n  ESPORTAZIONE CARTELLINI COMPLETED.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
