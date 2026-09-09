#!/usr/bin/env python3
"""
STAGE 11 — Risultati e calendario Serie A.

Fonte primaria: Sofascore (API non ufficiale, nessuna chiave, una richiesta
per giornata). Fallback: api-football.com (--source apifootball, richiede
API_FOOTBALL_KEY, un'unica richiesta per l'intera stagione).

Produce:
  - data/match_results.csv : una riga per partita (giornata, data, squadre, FT/HT, stato)
  - data/team_form.json    : per ogni squadra: ultime 5 gare, forma W/D/L, punti e gol

I nomi squadra delle due fonti vengono mappati sulle sigle pipeline via
config.TEAM_APIFB_MAP / config.TEAM_SOFASCORE_MAP (+ fallback fuzzy); i match
senza mapping mantengono il nome grezzo e vengono segnalati in output.
"""

import argparse
import difflib
import json
import os
import re
import sys
import unicodedata

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import config
from core.ingestion.static import sofascore_api

SOURCES = ("sofascore", "apifootball")
FINISHED_STATUSES = {"FT", "AET", "PEN"}


def round_number(round_name):
    """'Regular Season - 3' → 3. Ritorna None se non parsabile."""
    if not round_name:
        return None
    m = re.search(r"(\d+)", str(round_name))
    return int(m.group(1)) if m else None


def _norm(s):
    s = "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")
    return s.lower().strip()


# Unione normalizzata dei mapping squadra di entrambe le fonti (api-football + Sofascore)
_NORM_TEAM_MAP = {}
for _src_map in (config.TEAM_APIFB_MAP, config.TEAM_SOFASCORE_MAP):
    for _k, _v in _src_map.items():
        _NORM_TEAM_MAP.setdefault(_norm(_k), _v)


def map_team(name):
    """Mappa il nome squadra (api-football o Sofascore) sulla sigla pipeline.
    Cascata: esatto → normalizzato → fuzzy (cutoff 0.75). None se ignoto."""
    if not name:
        return None
    for m in (config.TEAM_APIFB_MAP, config.TEAM_SOFASCORE_MAP):
        if name in m:
            return m[name]
    norm = _norm(name)
    if norm in _NORM_TEAM_MAP:
        return _NORM_TEAM_MAP[norm]
    fuzzy = difflib.get_close_matches(norm, list(_NORM_TEAM_MAP.keys()), n=1, cutoff=0.75)
    if fuzzy:
        return _NORM_TEAM_MAP[fuzzy[0]]
    return None


def _fetch_fixtures(source):
    """Scarica le fixture di stagione dalla fonte richiesta (formato condiviso)."""
    if source == "apifootball":
        from core.ingestion.dynamic.api_football_client import get_season_fixtures
        return get_season_fixtures()
    return sofascore_api.get_season_fixtures()


def fetch_results_dataframe(source="sofascore"):
    """Scarica le fixture di stagione e le normalizza in un DataFrame ordinato."""
    fixtures = _fetch_fixtures(source)
    if not fixtures:
        return pd.DataFrame()

    rows = []
    for fx in fixtures:
        rows.append({
            "fixture_id": fx["fixture_id"],
            "round": round_number(fx.get("round")),
            "round_name": fx.get("round"),
            "date_utc": fx.get("date"),
            "home_team": fx["home_team"],
            "home_team_code": map_team(fx["home_team"]),
            "away_team": fx["away_team"],
            "away_team_code": map_team(fx["away_team"]),
            "home_score": fx.get("home_score"),
            "away_score": fx.get("away_score"),
            "ht_home_score": fx.get("ht_home_score"),
            "ht_away_score": fx.get("ht_away_score"),
            "status": fx.get("status"),
        })

    df = pd.DataFrame(rows)
    return df.sort_values(["round", "date_utc"], na_position="last").reset_index(drop=True)


def _result_for(gf, ga):
    if gf > ga:
        return "W"
    if gf < ga:
        return "L"
    return "D"


def build_team_form(df):
    """Costruisce {sigla_squadra: forma} dalle partite concluse del DataFrame risultati.

    Ogni voce contiene: elenco gare, streak ultime 5 ('form'), punti/gol stagionali
    e gli aggregati last5 (punti, GF, GA).
    """
    form = {}
    if df.empty or "status" not in df.columns:
        return form

    played = df[df["status"].isin(FINISHED_STATUSES)]
    for _, m in played.iterrows():
        hs, as_ = m.get("home_score"), m.get("away_score")
        if pd.isna(hs) or pd.isna(as_):
            continue
        hs, as_ = int(hs), int(as_)

        for side, code, gf, ga in (
            ("home", m.get("home_team_code"), hs, as_),
            ("away", m.get("away_team_code"), as_, hs),
        ):
            if not code or pd.isna(code):
                continue
            entry = form.setdefault(code, {
                "matches": [], "played": 0, "wins": 0, "draws": 0, "losses": 0,
                "gf": 0, "ga": 0, "points": 0,
            })
            opponent = m.get("away_team_code") if side == "home" else m.get("home_team_code")
            rnd = m.get("round")
            entry["matches"].append({
                "date": m.get("date_utc"),
                "round": int(rnd) if pd.notna(rnd) else None,
                "opponent": opponent if pd.notna(opponent) else None,
                "venue": side,
                "gf": gf,
                "ga": ga,
                "result": _result_for(gf, ga),
            })
            entry["played"] += 1
            entry["gf"] += gf
            entry["ga"] += ga
            if entry["matches"][-1]["result"] == "W":
                entry["wins"] += 1
                entry["points"] += 3
            elif entry["matches"][-1]["result"] == "D":
                entry["draws"] += 1
                entry["points"] += 1
            else:
                entry["losses"] += 1

    for entry in form.values():
        entry["matches"].sort(key=lambda x: (x["round"] or 0, str(x["date"])))
        last5 = entry["matches"][-5:]
        entry["last5"] = last5
        entry["form"] = "".join(x["result"] for x in last5)
        entry["points_last5"] = sum({"W": 3, "D": 1, "L": 0}[x["result"]] for x in last5)
        entry["gf_last5"] = sum(x["gf"] for x in last5)
        entry["ga_last5"] = sum(x["ga"] for x in last5)

    return form


def _parse_source(argv):
    parser = argparse.ArgumentParser(description="Stage 11 — Risultati Serie A")
    parser.add_argument(
        "--source", choices=list(SOURCES), default="sofascore",
        help="Fonte dati: sofascore (default, nessuna chiave) o apifootball (richiede API_FOOTBALL_KEY)",
    )
    args, _ = parser.parse_known_args(argv)
    return args.source


def main(source="sofascore"):
    if source not in SOURCES:
        source = "sofascore"
    print("=" * 60)
    print(f"  STAGE 11 — RISULTATI SERIE A (fonte: {source})")
    print("=" * 60)

    if source == "apifootball" and not config.API_FOOTBALL_KEY:
        print("\n  [ERROR] API_FOOTBALL_KEY non configurata (aggiungila al file .env) "
              "oppure usa la fonte di default: --source sofascore.")
        return

    try:
        df = fetch_results_dataframe(source)
    except RuntimeError as e:
        print(f"\n  [ERROR] {e}")
        return

    if df.empty:
        print("\n  [ERROR] Nessuna fixture recuperata dalla fonte selezionata.")
        return

    unmatched = sorted(set(
        df.loc[df["home_team_code"].isna(), "home_team"].tolist()
        + df.loc[df["away_team_code"].isna(), "away_team"].tolist()
    ))

    df.to_csv(config.MATCH_RESULTS_CSV, index=False, encoding="utf-8-sig")

    form = build_team_form(df)
    with open(config.TEAM_FORM_JSON, "w", encoding="utf-8") as f:
        json.dump(form, f, ensure_ascii=False, indent=2)

    finished = df[df["status"].isin(FINISHED_STATUSES)]
    print(f"\n  [OK] {len(df)} fixture totali, {len(finished)} concluse "
          f"(giornate {int(df['round'].min())}-{int(df['round'].max())})")

    if unmatched:
        shown = ", ".join(unmatched[:8]) + (" ..." if len(unmatched) > 8 else "")
        print(f"  [WARN] Squadre non mappate su sigla pipeline: {shown}")

    if form:
        print("\n  Forma squadre (top 5 per punti stagionali):")
        top = sorted(form.items(), key=lambda kv: kv[1]["points"], reverse=True)[:5]
        for code, e in top:
            print(f"    {code}: {e['points']:2d} pt · forma {e['form'] or '-'} · "
                  f"GF {e['gf']:2d} GA {e['ga']:2d}")

    print(f"\n  Output: {config.MATCH_RESULTS_CSV}")
    print(f"  Output: {config.TEAM_FORM_JSON}")
    print("\n  STAGE 11 COMPLETED.\n")


if __name__ == "__main__":
    main(source=_parse_source(sys.argv[1:]))
