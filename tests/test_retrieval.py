#!/usr/bin/env python3
"""
Unit tests for web.retrieval — structured RAG layer (entity resolution +
context blocks) for the copilot. Fully hermetic: synthetic dataframes and
payloads, no data/ artifacts, no network.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import retrieval


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures sintetiche
# ─────────────────────────────────────────────────────────────────────────────

def make_df():
    return pd.DataFrame([
        {
            "player": "Martinez L.", "role": "A", "role_mantra": "A", "team": "INT",
            "predicted_contrib_p10": 98.1, "predicted_contrib_p50": 152.3,
            "predicted_contrib_p90": 201.7, "contrib_volatility_spread": 103.6,
            "prezzo_fair_1000": 48, "surplus_value_cr": 3, "vorp_points": 31.2,
            "starts_2627": 2, "minutes_2627": 144, "is_starter_2627": True,
            "xg_per90": 0.353, "xa_per90": 0.118, "shots_per90": 2.41,
            "giorni_infortunio_3y": 140, "n_infortuni_3y": 2, "infortunio_grave": False,
            "age": 28, "market_value_eur": 110000000,
            "yellow_cards_espn": 1, "red_cards_espn": 0,
        },
        {
            "player": "Martinez Jo.", "role": "P", "role_mantra": "P", "team": "INT",
            "predicted_contrib_p10": 40.0, "predicted_contrib_p50": 60.0,
            "predicted_contrib_p90": 80.0, "contrib_volatility_spread": 40.0,
            "prezzo_fair_1000": 12, "surplus_value_cr": 0, "vorp_points": 5.0,
            "starts_2627": 1, "minutes_2627": 90, "is_starter_2627": False,
            "xg_per90": float("nan"), "xa_per90": float("nan"), "shots_per90": float("nan"),
            "giorni_infortunio_3y": 10, "n_infortuni_3y": 1, "infortunio_grave": False,
            "age": 33, "market_value_eur": 5000000,
            "yellow_cards_espn": 0, "red_cards_espn": 1,
        },
        {
            "player": "Thuram", "role": "A", "role_mantra": "A", "team": "INT",
            "predicted_contrib_p10": 90.0, "predicted_contrib_p50": 140.0,
            "predicted_contrib_p90": 190.0, "contrib_volatility_spread": 100.0,
            "prezzo_fair_1000": 40, "surplus_value_cr": 1, "vorp_points": 28.0,
            "starts_2627": 3, "minutes_2627": 250, "is_starter_2627": True,
            "xg_per90": 0.30, "xa_per90": 0.10, "shots_per90": 2.0,
            "giorni_infortunio_3y": 0, "n_infortuni_3y": 0, "infortunio_grave": False,
            "age": 29, "market_value_eur": 60000000,
            "yellow_cards_espn": 0, "red_cards_espn": 0,
        },
        {
            "player": "Thuram K.", "role": "C", "role_mantra": "C", "team": "JUV",
            "predicted_contrib_p10": 50.0, "predicted_contrib_p50": 80.0,
            "predicted_contrib_p90": 110.0, "contrib_volatility_spread": 60.0,
            "prezzo_fair_1000": 18, "surplus_value_cr": -2, "vorp_points": 9.0,
            "starts_2627": 2, "minutes_2627": 160, "is_starter_2627": True,
            "xg_per90": 0.05, "xa_per90": 0.08, "shots_per90": 0.9,
            "giorni_infortunio_3y": 5, "n_infortuni_3y": 1, "infortunio_grave": False,
            "age": 24, "market_value_eur": 40000000,
            "yellow_cards_espn": 2, "red_cards_espn": 0,
        },
    ])


def make_matches_payload():
    def meta(fid, rnd, home, hc, away, ac, hs=None, as_=None, ht=(None, None), status="FT", date=""):
        return {
            "fixture_id": fid, "round": rnd,
            "date": date, "home_team": home, "home_code": hc, "home_display": home,
            "away_team": away, "away_code": ac, "away_display": away,
            "home_score": hs, "away_score": as_,
            "ht_home_score": ht[0], "ht_away_score": ht[1],
            "status": status, "finished": status in ("FT", "AET", "PEN"),
        }

    return {
        "available": True,
        "current_round": 2,
        "rounds": [
            {"round": 1, "matches": [
                meta(101, 1, "Inter", "INT", "Monza", "MON", 4, 1, (1, 1), "FT", "2026-08-22T16:30:00+00:00"),
                meta(102, 1, "AC Milan", "MIL", "Venezia", "VEN", 2, 0, (0, 0), "FT", "2026-08-22T18:45:00+00:00"),
            ]},
            {"round": 2, "matches": [
                meta(103, 2, "Inter", "INT", "AC Milan", "MIL", 1, 2, (0, 1), "FT", "2026-08-29T16:30:00+00:00"),
                meta(104, 2, "Juventus", "JUV", "Como", "COM", None, None, (None, None), "NS", "2026-08-30T18:45:00+00:00"),
            ]},
        ],
        "team_form": {
            "INT": {"matches": [
                {"result": "W"}, {"result": "W"}, {"result": "L"},
            ]},
        },
    }


def make_pm_df():
    return pd.DataFrame([
        {"event_id": 101, "round": 1, "date_utc": "2026-08-22T16:30:00+00:00", "venue": "home",
         "team_code": "INT", "opponent_code": "MON", "player": "Martinez L.", "player_sofascore": "Lautaro Martinez",
         "is_starter": True, "minutes_played": 90, "rating": 8.8, "goals": 2, "assists": 1,
         "xg": 1.2, "xa": 0.3},
        {"event_id": 103, "round": 2, "date_utc": "2026-08-29T16:30:00+00:00", "venue": "home",
         "team_code": "INT", "opponent_code": "MIL", "player": "Martinez L.", "player_sofascore": "Lautaro Martinez",
         "is_starter": True, "minutes_played": 90, "rating": 6.5, "goals": 0, "assists": 0,
         "xg": 0.1, "xa": 0.05},
        {"event_id": 101, "round": 1, "date_utc": "2026-08-22T16:30:00+00:00", "venue": "home",
         "team_code": "INT", "opponent_code": "MON", "player": "Thuram", "player_sofascore": "Marcus Thuram",
         "is_starter": True, "minutes_played": 75, "rating": 7.9, "goals": 1, "assists": 0,
         "xg": 0.6, "xa": 0.1},
    ])


def make_espn_store():
    return {
        "101": {
            "event_id": 101,
            "form": {"home": "3-5-2", "away": "3-4-2-1"},
            "events": [
                {"minute": 19, "side": "home", "kind": "goal", "player": "Milutin Osmajic", "assist": "Lorenzo Colombo"},
                {"minute": 25, "side": "away", "kind": "goal", "player": "Martin Baturina", "assist": ""},
                {"minute": 36, "side": "home", "kind": "yellow", "player": "Djibril Sow", "assist": ""},
                {"minute": 78, "side": "away", "kind": "red", "player": "Armando Izzo", "assist": ""},
            ],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entity resolution — giocatori
# ─────────────────────────────────────────────────────────────────────────────

def test_resolve_players_alias():
    names = retrieval.resolve_players("come va lautaro?", make_df())
    assert names[0] == "Martinez L."


def test_resolve_players_surname_token():
    names = retrieval.resolve_players("proiezioni per Thuram", make_df())
    # "thuram" matcha entrambi i Thuram, Marcus ("Thuram") ha priorità per ordine dataset
    assert "Thuram" in names and "Thuram K." in names
    assert names[0] == "Thuram"


def test_resolve_players_full_alias_disambiguates():
    names = retrieval.resolve_players("statistiche di khephren thuram", make_df())
    assert names[0] == "Thuram K."


def test_resolve_players_alias_does_not_pull_namesake():
    # "lautaro" → Martinez L. SOLO: il token 'martinez' dell'alias non deve
    # trascinare dentro Martinez Jo. (altrimenti 2 match = falso confronto)
    names = retrieval.resolve_players("quanti xG ha lautaro?", make_df())
    assert names == ["Martinez L."]


def test_resolve_players_alias_plus_surname_comparison():
    # alias + altro cognome: il token del cognome (sul prompt originale) resta valido
    names = retrieval.resolve_players("meglio lautaro o thuram?", make_df())
    assert names[0] == "Martinez L."
    assert "Thuram" in names


def test_resolve_players_accents_insensitive():
    names = retrieval.resolve_players("martinez l.", make_df())
    assert "Martinez L." in names


def test_resolve_players_no_match():
    assert retrieval.resolve_players("migliori difensori sotto i 10 crediti", make_df()) == []


def test_resolve_players_short_tokens_ignored():
    # "Jo" (2 char) non deve matchare nulla da solo
    assert retrieval.resolve_players("jo", make_df()) == []


# ─────────────────────────────────────────────────────────────────────────────
# Entity resolution — partite
# ─────────────────────────────────────────────────────────────────────────────

def test_resolve_matches_head_to_head():
    payload = make_matches_payload()
    metas = retrieval.resolve_matches("inter vs milan", payload)
    assert len(metas) == 1
    assert metas[0]["fixture_id"] == 103


def test_resolve_matches_head_to_head_prefers_finished():
    payload = make_matches_payload()
    # la JUV-COM (NS) esiste solo come gara futura: deve comunque tornare
    metas = retrieval.resolve_matches("juve como", payload)
    assert [m["fixture_id"] for m in metas] == [104]
    # in un h2h con gara disputata e gara futura, vince la disputata
    payload["rounds"].append({"round": 3, "matches": [
        {"fixture_id": 105, "round": 3, "date": "2026-09-12T16:30:00+00:00",
         "home_team": "Inter", "home_code": "INT", "home_display": "Inter",
         "away_team": "AC Milan", "away_code": "MIL", "away_display": "AC Milan",
         "home_score": None, "away_score": None,
         "ht_home_score": None, "ht_away_score": None, "status": "NS", "finished": False},
    ]})
    metas = retrieval.resolve_matches("cartellini inter milan", payload)
    assert [m["fixture_id"] for m in metas] == [103]


def test_resolve_matches_single_team_latest_finished():
    payload = make_matches_payload()
    metas = retrieval.resolve_matches("come è andata l'inter?", payload)
    assert len(metas) == 1
    assert metas[0]["fixture_id"] == 103  # ultima finita (g2), non la NS


def test_resolve_matches_team_plus_round():
    payload = make_matches_payload()
    metas = retrieval.resolve_matches("inter giornata 1", payload)
    assert [m["fixture_id"] for m in metas] == [101]


def test_resolve_matches_round_only():
    payload = make_matches_payload()
    metas = retrieval.resolve_matches("risultati giornata 1", payload)
    assert {m["fixture_id"] for m in metas} == {101, 102}


def test_resolve_matches_upcoming():
    payload = make_matches_payload()
    metas = retrieval.resolve_matches("prossima partita della juve", payload)
    assert [m["fixture_id"] for m in metas] == [104]


def test_resolve_matches_last_round():
    payload = make_matches_payload()
    metas = retrieval.resolve_matches("ultima giornata", payload)
    assert {m["fixture_id"] for m in metas} == {103, 104}


def test_resolve_matches_unavailable_payload(monkeypatch):
    monkeypatch.setattr(retrieval, "_auto_matches_payload", lambda: None)
    assert retrieval.resolve_matches("inter") == []
    monkeypatch.setattr(retrieval, "_auto_matches_payload", lambda: {"available": False})
    assert retrieval.resolve_matches("inter") == []


# ─────────────────────────────────────────────────────────────────────────────
# Blocchi di contesto
# ─────────────────────────────────────────────────────────────────────────────

def test_player_block_contains_expected_sections():
    block = retrieval.build_player_block("Martinez L.", df=make_df(), pm_df=make_pm_df(), advanced={})
    # nome completo Sofascore nell'header: l'LLM deve collegare "Lautaro"
    assert "GIOCATORE: Martinez L. — Lautaro / Lautaro Martinez (INT · A" in block
    assert "P50 152" in block
    assert "xG/90 0.353" in block
    assert "140 giorni" in block
    assert "1 gialli, 0 rossi" in block
    assert "media voto" in block
    assert "G1 vsMON | 90' | 8.8 | 3 | 1.50" in block


def test_player_block_known_names_from_aliases():
    block = retrieval.build_player_block("Martinez L.", df=make_df(), pm_df=None, advanced={})
    assert "Lautaro" in block.split("\n")[0]


def test_player_block_nan_xg_omits_understat_line():
    block = retrieval.build_player_block("Martinez Jo.", df=make_df(), pm_df=make_pm_df(), advanced={})
    assert "Sottoporta" not in block
    assert "1 rossi" in block


def test_player_block_unknown_player():
    assert retrieval.build_player_block("Inesistente", df=make_df()) is None


def test_player_block_advanced_section():
    advanced = {"players": {"Martinez L.": {
        "minutes": 180, "rating": 7.65, "no_data": False,
        "cards": {"yellow": 1, "red": 0, "yellow_red": 0, "direct_red": 0},
        "totals": {"goals": 2.0, "assists": 1.0},
        "per90": {"shots_per90": 2.5},
    }}}
    block = retrieval.build_player_block("Martinez L.", df=make_df(), pm_df=None, advanced=advanced)
    assert "Stagione avanzate" in block
    assert "rossi 0" in block


def test_match_block_with_espn_events():
    block = retrieval.build_match_block(
        make_matches_payload()["rounds"][0]["matches"][0],
        team_form=make_matches_payload()["team_form"],
        pm_df=make_pm_df(),
        espn_store=make_espn_store(),
    )
    assert "PARTITA: Inter 4-1 Monza" in block
    assert "Primo tempo: 1-1" in block
    assert "Gol (ESPN): 19' Milutin Osmajic (INT, ass. Lorenzo Colombo)" in block
    assert "Ammoniti: 36' Djibril Sow (INT)" in block
    assert "Espulsi: 78' Armando Izzo (MON)" in block
    assert "Moduli: Inter 3-5-2" in block
    assert "Miglior voto: Martinez L." in block
    assert "Forma INT (ultime 5): V V S" in block


def test_match_block_without_espn_uses_stage12_scorers():
    block = retrieval.build_match_block(
        make_matches_payload()["rounds"][0]["matches"][0],
        team_form={}, pm_df=make_pm_df(), espn_store={},
    )
    assert "non disponibili in cache locale" in block
    assert "Marcatori (stage 12): Martinez L. x2 · Thuram x1" in block


def test_match_block_upcoming():
    meta = make_matches_payload()["rounds"][1]["matches"][1]
    block = retrieval.build_match_block(meta, team_form={}, pm_df=None, espn_store={})
    assert "in programma" in block
    assert "—" in block  # punteggio assente


# ─────────────────────────────────────────────────────────────────────────────
# Aggregati
# ─────────────────────────────────────────────────────────────────────────────

def test_aggregate_scorers_from_df_injected():
    block = retrieval.build_aggregate_block("chi sono i marcatori?", df=make_df(), pm_df=make_pm_df())
    assert "MARCATORI" in block
    assert "Martinez L. (INT): 2 gol" in block
    assert "Thuram (INT): 1 gol" in block


def test_aggregate_scorers_from_csv_cache(monkeypatch, tmp_path):
    csv = tmp_path / "player_match_stats.csv"
    make_pm_df().to_csv(csv, index=False)
    monkeypatch.setattr(retrieval, "PLAYER_MATCH_STATS_CSV", str(csv))
    retrieval._aggregate_cache["scorers"] = None
    retrieval._aggregate_cache["mtime"] = None
    block = retrieval.build_aggregate_block("capocannoniere?", df=make_df(), pm_df=None)
    assert "Martinez L. (INT): 2 gol" in block
    retrieval._aggregate_cache["scorers"] = None
    retrieval._aggregate_cache["mtime"] = None


def test_aggregate_red_cards_from_dataset():
    block = retrieval.build_aggregate_block("chi è stato espulso?", df=make_df(), pm_df=make_pm_df())
    assert "ESPULSI" in block
    assert "Martinez Jo." in block
    assert "crowdsourced" in block


def test_aggregate_yellow_cards():
    block = retrieval.build_aggregate_block("ammoniti di più?", df=make_df(), pm_df=make_pm_df())
    assert "AMMONITI" in block
    assert "Thuram K." in block


def test_aggregate_none_for_other_prompts():
    assert retrieval.build_aggregate_block("proiezioni lautaro", df=make_df(), pm_df=make_pm_df()) is None


# ─────────────────────────────────────────────────────────────────────────────
# build_llm_context (top-level)
# ─────────────────────────────────────────────────────────────────────────────

def test_build_llm_context_player_and_match(monkeypatch):
    payload = make_matches_payload()
    monkeypatch.setattr(retrieval, "_auto_matches_payload", lambda: payload)
    monkeypatch.setattr(retrieval, "_auto_pm_df", lambda: make_pm_df())
    monkeypatch.setattr(retrieval, "_auto_espn_store", lambda: make_espn_store())
    monkeypatch.setattr(retrieval, "_auto_advanced", lambda: {})
    blocks = retrieval.build_llm_context("come è andato lautaro contro il milan?", df=make_df())
    assert any("GIOCATORE: Martinez L." in b for b in blocks)
    assert any("PARTITA: Inter 1-2 AC Milan" in b for b in blocks)


def test_build_llm_context_aggregate_fallback(monkeypatch):
    monkeypatch.setattr(retrieval, "_auto_matches_payload", lambda: {"available": False})
    monkeypatch.setattr(retrieval, "_auto_pm_df", lambda: make_pm_df())
    monkeypatch.setattr(retrieval, "_load_scorer_index", lambda: [("Martinez L.", "INT", 2)])
    blocks = retrieval.build_llm_context("marcatori 2026/27", df=make_df())
    assert len(blocks) == 1
    assert "MARCATORI" in blocks[0]


def test_build_llm_context_empty(monkeypatch):
    monkeypatch.setattr(retrieval, "_auto_matches_payload", lambda: {"available": False})
    blocks = retrieval.build_llm_context("tempo che fa?", df=make_df())
    assert blocks == []
