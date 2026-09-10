#!/usr/bin/env python3
"""
Unit tests for the ESPN match-events store (crowdsourced cache): payload
sanitization, no-downgrade merge and store roundtrip. No live network calls.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import matches_api


def _event(minute=10, side="home", kind="goal", player="Rossi", assist=""):
    return {"minute": minute, "side": side, "kind": kind, "player": player, "assist": assist}


def test_sanitize_valid_payload():
    clean = matches_api.sanitize_espn_payload({
        "event_id": 123, "espn_event_id": "987", "match_state": "post",
        "form": {"home": "3-4-2-1", "away": "4-3-3"},
        "events": [_event(), _event(side="away", kind="yellow", player="Bianchi")],
    })
    assert clean["event_id"] == 123
    assert clean["espn_event_id"] == "987"
    assert clean["match_state"] == "post"
    assert clean["form"] == {"home": "3-4-2-1", "away": "4-3-3"}
    assert clean["events"] == [_event(), _event(side="away", kind="yellow", player="Bianchi")]


def test_sanitize_rejects_and_clamps():
    assert matches_api.sanitize_espn_payload(None) is None
    assert matches_api.sanitize_espn_payload("hack") is None
    assert matches_api.sanitize_espn_payload({"event_id": -1}) is None
    assert matches_api.sanitize_espn_payload({"event_id": "abc"}) is None
    # evento illegittimo scartato; minuto fuori scala -> None; stringhe troncate
    clean = matches_api.sanitize_espn_payload({
        "event_id": 1,
        "events": [_event(minute=999, player="x" * 200),
                   {"minute": 5, "side": "mid", "kind": "hack", "player": "no"}],
    })
    assert len(clean["events"]) == 1
    assert clean["events"][0]["minute"] is None
    assert clean["events"][0]["player"] == "x" * 80
    # match_state sconosciuto -> None; form non-dict -> vuoto
    clean = matches_api.sanitize_espn_payload({
        "event_id": 1, "match_state": "whenever", "form": "3-4-3",
        "events": [_event()],
    })
    assert clean["match_state"] is None
    assert clean["form"] == {"home": "", "away": ""}


def test_merge_no_downgrade():
    store = {}
    full = matches_api.sanitize_espn_payload({
        "event_id": 7, "match_state": "post",
        "events": [_event(), _event(side="away", kind="red", player="B")],
    })
    partial = matches_api.sanitize_espn_payload({
        "event_id": 7, "match_state": "in", "events": [_event()],
    })
    empty = matches_api.sanitize_espn_payload({"event_id": 7, "match_state": "post", "events": []})
    assert matches_api.merge_espn_payload(store, partial) is True
    assert matches_api.merge_espn_payload(store, empty) is False      # 1 -> 0 bloccato
    assert matches_api.merge_espn_payload(store, partial) is False    # identico: no riscrittura
    assert matches_api.merge_espn_payload(store, full) is True        # 1 -> 2 ok
    assert len(store["7"]["events"]) == 2
    assert store["7"]["match_state"] == "post"
    assert store["7"]["fetched_at"].endswith("Z")


def test_merge_link_upgrade_keeps_richer_events():
    store = {}
    rich = matches_api.sanitize_espn_payload({
        "event_id": 9, "match_state": "post",
        "events": [_event(), _event(minute=2, side="away", kind="yellow", player="B")],
    })
    matches_api.merge_espn_payload(store, rich)
    # stesso numero di eventi ma con link canonico: aggiornabile
    with_link = matches_api.sanitize_espn_payload({
        "event_id": 9, "match_state": "post",
        "espn_link": "https://www.espn.com/soccer/match/_/gameId/1/x",
        "events": [_event()],
    })
    assert matches_api.merge_espn_payload(store, with_link) is True
    assert store["9"]["espn_link"].endswith("/x")
    assert len(store["9"]["events"]) == 2          # gli eventi ricchi restano
    # senza upgrade: write debole bloccata
    assert matches_api.merge_espn_payload(store, rich) is False
    # piu' eventi con link: sovrascrive tutto
    richer = matches_api.sanitize_espn_payload({
        "event_id": 9, "match_state": "post",
        "espn_link": "https://www.espn.com/soccer/match/_/gameId/1/y",
        "events": [_event(), _event(minute=2, side="away", kind="yellow", player="B"),
                   _event(minute=3, side="home", kind="red", player="C")],
    })
    assert matches_api.merge_espn_payload(store, richer) is True
    assert len(store["9"]["events"]) == 3 and store["9"]["espn_link"].endswith("/y")


def test_store_roundtrip(tmp_path):
    path = str(tmp_path / "espn_match_events.json")
    orig = matches_api.ESPN_EVENTS_JSON
    try:
        matches_api.ESPN_EVENTS_JSON = path
        matches_api._save_espn_store({"9": {"event_id": 9, "match_state": "post",
                                            "form": {"home": "4-3-3", "away": ""},
                                            "espn_event_id": "55", "events": [_event()]}})
        store = matches_api._load_espn_store()
        assert store["9"]["event_id"] == 9
        assert store["9"]["events"][0]["player"] == "Rossi"
        # la scrittura e' atomica: nessun file .tmp residuo
        assert not os.path.exists(path + ".tmp")
    finally:
        matches_api.ESPN_EVENTS_JSON = orig


def test_load_store_missing_or_corrupt(tmp_path):
    orig = matches_api.ESPN_EVENTS_JSON
    try:
        matches_api.ESPN_EVENTS_JSON = str(tmp_path / "missing.json")
        assert matches_api._load_espn_store() == {}
        corrupt = tmp_path / "corrupt.json"
        corrupt.write_text("{non json", encoding="utf-8")
        matches_api.ESPN_EVENTS_JSON = str(corrupt)
        assert matches_api._load_espn_store() == {}
    finally:
        matches_api.ESPN_EVENTS_JSON = orig
