#!/usr/bin/env python3
"""
Unit tests for export_player_cards.py: ESPN full-name -> dataset short-name
resolution (accents, particles, "Kamara H." forms, team disambiguation) and
card aggregation. No live network calls.
"""
import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

epc = importlib.import_module("export_player_cards")


DATASET = [
    ("Thuram", "INT"), ("Thuram K.", "JUV"), ("Orsolini", "BOL"),
    ("De Roon", "ROM"), ("Kamara H.", "VEN"), ("Konè M.", "ROM"),
    ("El Shaarawy", "GEN"),
]


def test_resolve_full_and_surname():
    assert epc.resolve_player("Ricardo Orsolini", "BOL", DATASET) == "Orsolini"
    # cognome: ultimo token ESPN vs primo token dataset
    assert epc.resolve_player("Hilton Kamara", "VEN", DATASET) == "Kamara H."
    # accenti
    assert epc.resolve_player("Manu Koné", "ROM", DATASET) == "Konè M."
    # particelle: il nome ESPN termina con il nome dataset
    assert epc.resolve_player("Marten de Roon", "ROM", DATASET) == "De Roon"
    assert epc.resolve_player("Stephane El Shaarawy", "GEN", DATASET) == "El Shaarawy"


def test_resolve_ambiguous_by_team():
    # "Thuram" mappa su due giocatori: decide la squadra del lato dell'azione
    assert epc.resolve_player("Marcus Thuram", "INT", DATASET) == "Thuram"
    assert epc.resolve_player("Marcus Thuram", "JUV", DATASET) == "Thuram K."
    # senza squadra non disambiguabile -> None
    assert epc.resolve_player("Marcus Thuram", "", DATASET) is None
    # nome sconosciuto
    assert epc.resolve_player("Franz Beckenbauer", "MIL", DATASET) is None


def test_aggregate_cards(tmp_path):
    events = {
        "101": {"match_state": "post", "events": [
            {"minute": 10, "side": "home", "kind": "goal", "player": "Marcus Thuram", "assist": ""},
            {"minute": 30, "side": "home", "kind": "yellow", "player": "Marcus Thuram", "assist": ""},
            {"minute": 55, "side": "away", "kind": "yellow", "player": "Khephren Thuram", "assist": ""},
        ]},
        "102": {"match_state": "post", "events": [
            {"minute": 80, "side": "home", "kind": "red", "player": "Ricardo Orsolini", "assist": ""},
            {"minute": 81, "side": "home", "kind": "sub", "player": "X", "assist": "Y"},  # non cartellino
        ]},
    }
    p = tmp_path / "espn_match_events.json"
    p.write_text(__import__("json").dumps(events), encoding="utf-8")
    fixtures = {101: ("INT", "JUV", "1"), 102: ("BOL", "MIL", "2")}

    res = epc.aggregate_cards(str(p), fixtures, DATASET)
    assert res["matches_covered"] == 2
    assert res["players"]["Thuram"]["yellow_cards"] == 1
    assert res["players"]["Thuram"]["red_cards"] == 0
    assert res["players"]["Thuram K."]["yellow_cards"] == 1
    assert res["players"]["Orsolini"]["red_cards"] == 1
    # i gol/cambi non finiscono tra i cartellini
    assert res["players"]["Thuram"]["matches"][0]["kind"] == "yellow"


def test_aggregate_missing_store(tmp_path):
    res = epc.aggregate_cards(str(tmp_path / "missing.json"), {}, DATASET)
    assert res == {"matches_covered": 0, "players": {}, "unresolved": []}


def test_update_dataset_csv(tmp_path):
    import csv as _csv
    src = tmp_path / "dataset.csv"
    with open(src, "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=["player", "team", "mv_media_3y"])
        w.writeheader()
        w.writerow({"player": "Orsolini", "team": "BOL", "mv_media_3y": "6.85"})
        w.writerow({"player": "Thuram", "team": "INT", "mv_media_3y": "7.10"})
    players = {"Orsolini": {"team": "BOL", "yellow_cards": 2, "red_cards": 1, "matches": []}}
    epc.update_dataset_csv(str(src), players)
    rows = list(_csv.DictReader(open(src, encoding="utf-8")))
    assert [r["player"] for r in rows] == ["Orsolini", "Thuram"]           # ordine invariato
    assert rows[0]["mv_media_3y"] == "6.85"                                # altri campi byte-per-byte
    assert rows[0]["yellow_cards_espn"] == "2" and rows[0]["red_cards_espn"] == "1"
    assert rows[1]["yellow_cards_espn"] == "0" and rows[1]["red_cards_espn"] == "0"
    # idempotente: le colonne non vengono duplicate
    epc.update_dataset_csv(str(src), {})
    rows2 = list(_csv.DictReader(open(src, encoding="utf-8")))
    assert rows2[0]["yellow_cards_espn"] == "0"
    with open(src, encoding="utf-8") as f:
        header = f.readline().strip()
    assert header.count("yellow_cards_espn") == 1
