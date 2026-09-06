#!/usr/bin/env python3
"""
Unit tests for pipeline/dynamic/* — feed dinamico infrasettimanale (Pilastro 3).
No live network calls: all HTTP is mocked via unittest.mock.patch.
"""
import json
import os
import sys
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.dynamic.utils import normalize_name, PlayerMatcher, fetch_with_retry


def test_normalize_name_strips_accents_and_case():
    assert normalize_name("Kenan Yıldız") == "kenan yildiz"
    assert normalize_name("  Nico Paz ") == "nico paz"
    assert normalize_name("PAZ N.") == "paz n."


def test_player_matcher_exact_normalized_match():
    df = pd.DataFrame({
        "player": ["Lautaro Martinez", "Nico Paz"],
        "team": ["INT", "COM"],
    })
    matcher = PlayerMatcher(df)
    assert matcher.match("lautaro martinez", "INT") == "Lautaro Martinez"


def test_player_matcher_fuzzy_match_within_team():
    df = pd.DataFrame({
        "player": ["Kenan Yildiz", "Vlahovic"],
        "team": ["JUV", "JUV"],
    })
    matcher = PlayerMatcher(df)
    # Scraper source uses a slightly different accented spelling
    assert matcher.match("Kenan Yıldız", "JUV") == "Kenan Yildiz"


def test_player_matcher_last_name_and_global_fuzzy():
    df = pd.DataFrame({
        "player": ["Alessandro Bastoni", "Khvicha Kvaratskhelia"],
        "team": ["INT", "NAP"],
    })
    matcher = PlayerMatcher(df)
    # Test abbreviated name match within team
    assert matcher.match("A. Bastoni", "INT") == "Alessandro Bastoni"
    # Test global fuzzy match (wrong team provided by scraper, but name is distinctive)
    assert matcher.match("Khvicha Kvaratskhelia", "JUV") == "Khvicha Kvaratskhelia"


def test_player_matcher_returns_none_when_no_candidate():
    df = pd.DataFrame({"player": ["Someone Else"], "team": ["ROM"]})
    matcher = PlayerMatcher(df)
    assert matcher.match("Totally Unrelated Name", "ROM") is None


@patch("pipeline.dynamic.utils.requests.get")
def test_fetch_with_retry_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_get.return_value = mock_resp

    res = fetch_with_retry("http://example.com")
    assert res == mock_resp
    assert mock_get.call_count == 1


@patch("pipeline.dynamic.utils.time.sleep")
@patch("pipeline.dynamic.utils.requests.get")
def test_fetch_with_retry_retry_then_success(mock_get, mock_sleep):
    fail_resp = MagicMock()
    fail_resp.status_code = 500

    ok_resp = MagicMock()
    ok_resp.status_code = 200

    mock_get.side_effect = [fail_resp, ok_resp]

    res = fetch_with_retry("http://example.com", max_retries=3)
    assert res == ok_resp
    assert mock_get.call_count == 2


@patch("pipeline.dynamic.utils.time.sleep")
@patch("pipeline.dynamic.utils.requests.get")
def test_fetch_with_retry_all_attempts_fail(mock_get, mock_sleep):
    mock_get.side_effect = requests.exceptions.Timeout("Timed out")

    res = fetch_with_retry("http://example.com", max_retries=3)
    assert res is None
    assert mock_get.call_count == 3


from pipeline.dynamic import api_football_client as afc


@patch("pipeline.dynamic.api_football_client.config")
@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_fixtures_parses_response(mock_fetch, mock_config):
    mock_config.API_FOOTBALL_KEY = "test_key"
    mock_config.API_FOOTBALL_LEAGUE_ID = 135
    mock_config.API_FOOTBALL_SEASON = 2026
    
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": [
            {
                "fixture": {"id": 111, "date": "2026-09-20T18:45:00+00:00"},
                "teams": {
                    "home": {"name": "Inter"},
                    "away": {"name": "Monza"},
                },
            }
        ]
    }
    mock_fetch.return_value = mock_resp

    fixtures = afc.get_fixtures()
    assert len(fixtures) == 1
    assert fixtures[0]["home_team"] == "Inter"
    assert fixtures[0]["away_team"] == "Monza"
    assert fixtures[0]["fixture_id"] == 111


@patch("pipeline.dynamic.api_football_client.config")
@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_fixtures_returns_empty_list_on_failure(mock_fetch, mock_config):
    mock_config.API_FOOTBALL_KEY = "test_key"
    mock_fetch.return_value = None
    assert afc.get_fixtures() == []


@patch("pipeline.dynamic.api_football_client.config")
@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_fixtures_status_filter_uses_last_instead_of_next(mock_fetch, mock_config):
    mock_config.API_FOOTBALL_KEY = "test_key"
    mock_config.API_FOOTBALL_LEAGUE_ID = 135
    mock_config.API_FOOTBALL_SEASON = 2026

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": [
            {
                "fixture": {"id": 222, "date": "2026-09-13T18:45:00+00:00"},
                "teams": {"home": {"name": "Roma"}, "away": {"name": "Lazio"}},
            }
        ]
    }
    mock_fetch.return_value = mock_resp

    fixtures = afc.get_fixtures(status_filter="FT")
    assert len(fixtures) == 1
    assert fixtures[0]["fixture_id"] == 222

    _, kwargs = mock_fetch.call_args
    assert kwargs["params"]["status"] == "FT"
    assert kwargs["params"]["last"] == 10
    assert "next" not in kwargs["params"]


@patch("pipeline.dynamic.api_football_client.config")
@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_fixture_player_ratings_parses_response(mock_fetch, mock_config):
    mock_config.API_FOOTBALL_KEY = "test_key"
    mock_config.API_FOOTBALL_LEAGUE_ID = 135
    mock_config.API_FOOTBALL_SEASON = 2026
    
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": [
            {
                "players": [
                    {
                        "player": {"name": "Lautaro Martinez"},
                        "statistics": [{"games": {"rating": "7.8"}}],
                    }
                ]
            },
            {
                "players": [
                    {
                        "player": {"name": "Yann Bisseck"},
                        "statistics": [{"games": {"rating": None}}],
                    }
                ]
            },
        ]
    }
    mock_fetch.return_value = mock_resp

    ratings = afc.get_fixture_player_ratings(111)
    assert ratings["Lautaro Martinez"] == 7.8
    assert "Yann Bisseck" not in ratings  # rating nullo -> escluso


# Regression tests for exception safety


@patch("pipeline.dynamic.api_football_client.config")
@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_fixtures_handles_json_decode_error(mock_fetch, mock_config):
    """Test that get_fixtures returns [] when resp.json() raises JSONDecodeError."""
    import json
    mock_config.API_FOOTBALL_KEY = "test_key"
    mock_resp = MagicMock()
    mock_resp.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
    mock_fetch.return_value = mock_resp

    fixtures = afc.get_fixtures()
    assert fixtures == []


@patch("pipeline.dynamic.api_football_client.config")
@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_fixtures_handles_missing_nested_keys(mock_fetch, mock_config):
    """Test that get_fixtures skips items with missing required nested fields."""
    mock_config.API_FOOTBALL_KEY = "test_key"
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": [
            {
                "fixture": {"id": 111},
                "teams": {"home": {"name": "Inter"}},
                # missing away.name -> should skip
            },
            {
                "fixture": {"id": 222, "date": "2026-09-20T18:45:00+00:00"},
                # missing teams -> should skip
            },
            {
                "fixture": {"id": 333, "date": "2026-09-21T18:45:00+00:00"},
                "teams": {
                    "home": {"name": "Milan"},
                    "away": {"name": "Juve"},
                },
                # all required fields present -> included
            }
        ]
    }
    mock_fetch.return_value = mock_resp

    fixtures = afc.get_fixtures()
    assert len(fixtures) == 1
    assert fixtures[0]["fixture_id"] == 333


@patch("pipeline.dynamic.api_football_client.config")
@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_odds_handles_json_decode_error(mock_fetch, mock_config):
    """Test that get_odds returns {} when resp.json() raises JSONDecodeError."""
    import json
    mock_config.API_FOOTBALL_KEY = "test_key"
    mock_resp = MagicMock()
    mock_resp.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
    mock_fetch.return_value = mock_resp

    odds = afc.get_odds(111)
    assert odds == {}


@patch("pipeline.dynamic.api_football_client.config")
@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_odds_handles_missing_bet_name(mock_fetch, mock_config):
    """Test that get_odds skips bets with missing 'name' field."""
    mock_config.API_FOOTBALL_KEY = "test_key"
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": [
            {
                "bookmakers": [
                    {
                        "bets": [
                            {
                                "name": "1X2",
                                "values": [
                                    {"value": "1", "odd": "2.5"},
                                    {"value": "X", "odd": "3.2"},
                                ]
                            },
                            {
                                # missing name -> should skip
                                "values": [{"value": "1", "odd": "2.6"}]
                            },
                        ]
                    }
                ]
            }
        ]
    }
    mock_fetch.return_value = mock_resp

    odds = afc.get_odds(111)
    assert "1X2" in odds
    assert len(odds["1X2"]) == 2
    assert len(odds) == 1  # only 1X2 market


@patch("pipeline.dynamic.api_football_client.config")
@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_fixture_player_ratings_handles_json_decode_error(mock_fetch, mock_config):
    """Test that get_fixture_player_ratings returns {} when resp.json() raises JSONDecodeError."""
    import json
    mock_config.API_FOOTBALL_KEY = "test_key"
    mock_resp = MagicMock()
    mock_resp.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
    mock_fetch.return_value = mock_resp

    ratings = afc.get_fixture_player_ratings(111)
    assert ratings == {}


@patch("pipeline.dynamic.api_football_client.config")
@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_fixture_player_ratings_handles_empty_statistics_list(mock_fetch, mock_config):
    """Test that get_fixture_player_ratings handles empty statistics list gracefully."""
    mock_config.API_FOOTBALL_KEY = "test_key"
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": [
            {
                "players": [
                    {
                        "player": {"name": "Player One"},
                        "statistics": [],  # empty list -> should not index error
                    },
                    {
                        "player": {"name": "Player Two"},
                        "statistics": [{"games": {"rating": "7.5"}}],
                    },
                ]
            }
        ]
    }
    mock_fetch.return_value = mock_resp

    ratings = afc.get_fixture_player_ratings(111)
    assert "Player One" not in ratings  # no rating available
    assert ratings["Player Two"] == 7.5


@patch("pipeline.dynamic.api_football_client.config")
@patch("pipeline.dynamic.api_football_client.fetch_with_retry")
def test_get_fixture_player_ratings_handles_missing_player_name(mock_fetch, mock_config):
    """Test that get_fixture_player_ratings skips players with missing name."""
    mock_config.API_FOOTBALL_KEY = "test_key"
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "response": [
            {
                "players": [
                    {
                        # missing player.name -> should skip
                        "statistics": [{"games": {"rating": "7.8"}}],
                    },
                    {
                        "player": {"name": "Valid Player"},
                        "statistics": [{"games": {"rating": "7.9"}}],
                    },
                ]
            }
        ]
    }
    mock_fetch.return_value = mock_resp

    ratings = afc.get_fixture_player_ratings(111)
    assert len(ratings) == 1
    assert ratings["Valid Player"] == 7.9


from pipeline.dynamic import scrape_odds


def test_devig_probabilities_removes_bookmaker_margin():
    # Quote con aggio: 1.90 / 3.60 / 4.20 (somma probabilita implicite > 1)
    odds = [("Home", 1.90), ("Draw", 3.60), ("Away", 4.20)]
    probs = scrape_odds.devig_probabilities(odds)
    total = sum(probs.values())
    assert abs(total - 1.0) < 1e-6
    # L'esito piu probabile (quota piu bassa) deve avere probabilita maggiore
    assert probs["Home"] > probs["Draw"] > probs["Away"]


def test_devig_probabilities_empty_input_returns_empty_dict():
    assert scrape_odds.devig_probabilities([]) == {}


@patch("pipeline.dynamic.scrape_odds.get_odds")
@patch("pipeline.dynamic.scrape_odds.get_fixtures")
def test_build_odds_feed_marks_unavailable_odds(mock_fixtures, mock_odds):
    mock_fixtures.return_value = [
        {"fixture_id": 1, "home_team": "Inter", "away_team": "Monza", "date": "2026-09-20T18:45:00+00:00"}
    ]
    mock_odds.return_value = {}  # nessuna quota disponibile per questa fixture

    feed = scrape_odds.build_odds_feed()
    assert len(feed) == 1
    assert feed[0]["odds_available"] is False
    assert feed[0]["home_win_prob"] is None


from pipeline.dynamic import scrape_lineups

SAMPLE_LINEUP_HTML = """
<li class="match" data-match-id="17981" data-match-hash="JUV-MIL">
  <div class="team team-home" data-team-formation="4-2-3-1">
    <ul class="team-lineup" data-formation="4231">
      <li class="player"><a class="player-name player-link" href="/serie-a/squadre/juventus/perin/123">
        <span>Perin</span></a></li>
      <li class="separator"></li>
      <li class="player"><a class="player-name player-link" href="/serie-a/squadre/juventus/kalulu/456">
        <span>Kalulu</span></a></li>
      <li class="separator"></li>
    </ul>
  </div>
  <div class="team team-away" data-team-formation="4-3-3">
    <ul class="team-lineup" data-formation="433">
      <li class="player"><a class="player-name player-link" href="/serie-a/squadre/milan/maignan/789">
        <span>Maignan</span></a></li>
    </ul>
  </div>
</li>
"""


def test_expected_minutes_full_starter():
    assert scrape_lineups.expected_minutes(1.0, is_bench_candidate=False) == 70.0


def test_expected_minutes_bench_candidate():
    # titular_prob basso e in panchina: xMin = 0*70 + (1-0)*20*1 = 20
    assert scrape_lineups.expected_minutes(0.0, is_bench_candidate=True) == 20.0


def test_parse_probable_lineups_extracts_players_with_team_side():
    players = scrape_lineups.parse_probable_lineups(SAMPLE_LINEUP_HTML)
    names = [p["player_name"] for p in players]
    assert "Perin" in names
    assert "Kalulu" in names
    assert "Maignan" in names
    perin = next(p for p in players if p["player_name"] == "Perin")
    assert perin["match_id"] == "17981"
    assert perin["side"] == "home"


@patch("pipeline.dynamic.scrape_lineups.fetch_with_retry")
def test_scrape_probable_lineups_returns_empty_list_on_fetch_failure(mock_fetch):
    mock_fetch.return_value = None
    assert scrape_lineups.scrape_probable_lineups() == []


from pipeline.dynamic import scrape_status

SAMPLE_STATUS_HTML = """
<div id="team-1" class="card team-card">
  <span class="team-name">Atalanta</span>
  <ul class="unstyled">
    <li>
      <strong class="item-name">Sulemana K.</strong>
      <div class="item-description"><p>Lesione al ginocchio, rientro a ottobre.</p></div>
    </li>
    <li>
      <strong class="item-name">Hien</strong>
      <div class="item-description"><p>Operato, rientro a ottobre.</p></div>
    </li>
  </ul>
</div>
"""


def test_parse_status_cards_extracts_player_names():
    result = scrape_status.parse_status_cards(SAMPLE_STATUS_HTML, "INFORTUNATO")
    assert result["Sulemana K."] == "INFORTUNATO"
    assert result["Hien"] == "INFORTUNATO"
    assert len(result) == 2


def test_parse_status_cards_empty_html_returns_empty_dict():
    assert scrape_status.parse_status_cards("<html></html>", "SQUALIFICATO") == {}


@patch("pipeline.dynamic.scrape_status.fetch_with_retry")
def test_scrape_all_statuses_merges_both_sources(mock_fetch):
    injuries_resp = MagicMock()
    injuries_resp.text = SAMPLE_STATUS_HTML
    suspensions_resp = MagicMock()
    suspensions_resp.text = (
        '<div id="team-2" class="card team-card"><ul class="unstyled">'
        '<li><strong class="item-name">Orsolini</strong>'
        '<div class="item-description"><p>Squalificato 1 turno.</p></div></li>'
        '</ul></div>'
    )
    mock_fetch.side_effect = [injuries_resp, suspensions_resp]

    statuses = scrape_status.scrape_all_statuses()
    assert statuses["Sulemana K."] == "INFORTUNATO"
    assert statuses["Orsolini"] == "SQUALIFICATO"


@patch("pipeline.dynamic.scrape_status.fetch_with_retry")
def test_scrape_all_statuses_returns_injury_data_if_suspensions_fails(mock_fetch):
    """Regression test: if suspensions page parsing fails, injury data must still be returned."""
    injuries_resp = MagicMock()
    injuries_resp.text = SAMPLE_STATUS_HTML
    suspensions_resp = MagicMock()
    suspensions_resp.text = None  # Simulates invalid markup (BeautifulSoup will fail)
    mock_fetch.side_effect = [injuries_resp, suspensions_resp]

    # Should not raise; suspensions parsing failure should not crash the function
    statuses = scrape_status.scrape_all_statuses()
    
    # Injury data must still be present
    assert statuses["Sulemana K."] == "INFORTUNATO"
    assert statuses["Hien"] == "INFORTUNATO"
    assert "Orsolini" not in statuses  # suspensions data was lost due to parsing failure


@patch("pipeline.dynamic.scrape_status.fetch_with_retry")
def test_scrape_all_statuses_returns_suspensions_data_if_injuries_fails(mock_fetch):
    """Regression test: if injuries page parsing fails, suspensions data must still be returned."""
    injuries_resp = MagicMock()
    injuries_resp.text = None  # Simulates invalid markup (BeautifulSoup will fail)
    suspensions_resp = MagicMock()
    suspensions_resp.text = (
        '<div id="team-2" class="card team-card"><ul class="unstyled">'
        '<li><strong class="item-name">Orsolini</strong>'
        '<div class="item-description"><p>Squalificato 1 turno.</p></div></li>'
        '</ul></div>'
    )
    mock_fetch.side_effect = [injuries_resp, suspensions_resp]

    # Should not raise; injuries parsing failure should not crash the function
    statuses = scrape_status.scrape_all_statuses()
    
    # Suspensions data must still be present
    assert statuses["Orsolini"] == "SQUALIFICATO"
    assert len(statuses) == 1  # only suspensions data present


# Tests for scrape_results.py

from pipeline.dynamic import scrape_results


def test_update_ewma_first_observation_returns_rating_itself():
    assert scrape_results.update_ewma(None, 7.0) == 7.0


def test_update_ewma_applies_weighted_formula():
    # EWMA_t = 0.35 * rating + 0.65 * prev
    result = scrape_results.update_ewma(6.0, 8.0, alpha=0.35)
    assert abs(result - (0.35 * 8.0 + 0.65 * 6.0)) < 1e-9


def test_load_ewma_state_returns_empty_dict_when_file_missing(tmp_path, monkeypatch):
    missing_path = tmp_path / "does_not_exist.json"
    monkeypatch.setattr(scrape_results.config, "EWMA_STATE_JSON", str(missing_path))
    assert scrape_results.load_ewma_state() == {}


def test_save_then_load_ewma_state_roundtrip(tmp_path, monkeypatch):
    state_path = tmp_path / "ewma_state.json"
    monkeypatch.setattr(scrape_results.config, "EWMA_STATE_JSON", str(state_path))
    scrape_results.save_ewma_state({"Lautaro Martinez": 7.4})
    assert scrape_results.load_ewma_state() == {"Lautaro Martinez": 7.4}


@patch("pipeline.dynamic.scrape_results.get_fixture_player_ratings")
def test_update_form_from_fixtures_merges_new_ratings(mock_ratings, tmp_path, monkeypatch):
    state_path = tmp_path / "ewma_state.json"
    monkeypatch.setattr(scrape_results.config, "EWMA_STATE_JSON", str(state_path))
    scrape_results.save_ewma_state({"Lautaro Martinez": 7.0})
    mock_ratings.return_value = {"Lautaro Martinez": 8.0, "New Player": 6.5}

    updated = scrape_results.update_form_from_fixtures([111])
    assert abs(updated["Lautaro Martinez"] - (0.35 * 8.0 + 0.65 * 7.0)) < 1e-9
    assert updated["New Player"] == 6.5


# Tests for build_feed.py

from pipeline.dynamic import build_feed


def test_compute_xpts_matches_capitolato_formula():
    # xPts = (xMin/90) * [VotoBase + 3*P(Gol) + 1*P(Assist) - 1*E[GolSubiti] - 0.25*P(Ammon)]
    result = build_feed.compute_xpts(
        voto_base=6.0, p_gol=0.4, p_assist=0.2, e_gol_subiti=0.5, p_ammonizione=0.1, xmin=78
    )
    expected = (78 / 90) * (6.0 + 3 * 0.4 + 1 * 0.2 - 1 * 0.5 - 0.25 * 0.1)
    assert abs(result - expected) < 1e-9


def test_build_players_payload_applies_status_override_and_ewma():
    dataset_df = pd.DataFrame({
        "player": ["Lautaro Martinez"],
        "team": ["INT"],
        "role": ["A"],
    })
    lineup_players = [
        {"player_name": "Lautaro Martinez", "match_id": "1", "side": "home", "href": ""}
    ]
    statuses = {}  # nessuno stato negativo -> resta OK
    ewma_state = {"Lautaro Martinez": 7.4}
    odds_feed = []

    payload = build_feed.build_players_payload(
        dataset_df, lineup_players, statuses, ewma_state, odds_feed
    )
    key = "int_lautaro_martinez_a"
    assert key in payload
    assert payload[key]["status"] == "OK"
    assert payload[key]["ewma_form"] == 7.4
    assert payload[key]["titular_prob"] == scrape_lineups.BASELINE_TITULAR_PROB


def test_build_players_payload_marks_infortunato_status():
    dataset_df = pd.DataFrame({"player": ["Hien"], "team": ["ATA"], "role": ["D"]})
    statuses = {"Hien": "INFORTUNATO"}

    payload = build_feed.build_players_payload(dataset_df, [], statuses, {}, [])
    assert payload["ata_hien_d"]["status"] == "INFORTUNATO"
    assert payload["ata_hien_d"]["titular_prob"] == 0.0


def test_build_players_payload_matches_ewma_state_via_fuzzy_name_space():
    """ewma_state e' keyed sui nomi completi api-football, il dataset usa nomi
    fantacalcio-style abbreviati: la riconciliazione deve avvenire via PlayerMatcher."""
    dataset_df = pd.DataFrame({"player": ["Martinez L."], "team": ["INT"], "role": ["A"]})
    ewma_state = {"Lautaro Martinez": 7.8}

    payload = build_feed.build_players_payload(dataset_df, [], {}, ewma_state, [])
    assert payload["int_martinez_l._a"]["ewma_form"] == 7.8


def test_build_players_payload_matches_status_card_via_fuzzy_name_space():
    """Le card infortuni/squalifiche di fantacalcio.it possono avere un formato nome
    diverso da quello del dataset: anche qui la riconciliazione passa da PlayerMatcher."""
    dataset_df = pd.DataFrame({"player": ["De Ketelaere"], "team": ["ATA"], "role": ["A"]})
    statuses = {"De Ketelaere C.": "SQUALIFICATO"}

    payload = build_feed.build_players_payload(dataset_df, [], statuses, {}, [])
    assert payload["ata_de_ketelaere_a"]["status"] == "SQUALIFICATO"
    assert payload["ata_de_ketelaere_a"]["titular_prob"] == 0.0


@patch("pipeline.dynamic.build_feed.scrape_results.update_form_from_fixtures")
@patch("pipeline.dynamic.build_feed.api_football_client.get_fixtures")
def test_update_ewma_from_concluded_fixtures_invokes_update(mock_get_fixtures, mock_update):
    mock_get_fixtures.return_value = [
        {"fixture_id": 111, "date": "2026-09-13T18:45:00+00:00", "home_team": "Roma", "away_team": "Lazio"}
    ]

    build_feed.update_ewma_from_concluded_fixtures()

    mock_get_fixtures.assert_called_once_with(status_filter="FT")
    mock_update.assert_called_once_with([111])


@patch("pipeline.dynamic.build_feed.scrape_results.update_form_from_fixtures")
@patch("pipeline.dynamic.build_feed.api_football_client.get_fixtures")
def test_update_ewma_from_concluded_fixtures_skips_when_no_fixtures(mock_get_fixtures, mock_update):
    mock_get_fixtures.return_value = []

    build_feed.update_ewma_from_concluded_fixtures()

    mock_update.assert_not_called()


@patch("pipeline.dynamic.build_feed.scrape_results.update_form_from_fixtures")
@patch("pipeline.dynamic.build_feed.api_football_client.get_fixtures")
def test_update_ewma_from_concluded_fixtures_is_exception_safe(mock_get_fixtures, mock_update):
    mock_get_fixtures.side_effect = RuntimeError("boom")

    build_feed.update_ewma_from_concluded_fixtures()  # non deve propagare l'eccezione

    mock_update.assert_not_called()


@patch("pipeline.dynamic.build_feed.update_ewma_from_concluded_fixtures")
@patch("pipeline.dynamic.build_feed.scrape_lineups.scrape_probable_lineups")
@patch("pipeline.dynamic.build_feed.scrape_status.scrape_all_statuses")
@patch("pipeline.dynamic.build_feed.scrape_results.load_ewma_state")
@patch("pipeline.dynamic.build_feed.scrape_odds.build_odds_feed")
def test_build_feed_payload_calls_ewma_update_before_loading_state(
    mock_odds, mock_ewma, mock_status, mock_lineups, mock_update_ewma
):
    """build_feed_payload deve invocare l'aggiornamento EWMA prima di leggere lo stato,
    cosi' che il feed rifletta il turno concluso piu' recente."""
    mock_lineups.return_value = []
    mock_status.return_value = {}
    mock_ewma.return_value = {}
    mock_odds.return_value = []

    dataset_df = pd.DataFrame({"player": ["Test Player"], "team": ["ROM"], "role": ["C"]})
    build_feed.build_feed_payload(dataset_df, matchday=1, season="2026/2027")

    mock_update_ewma.assert_called_once()


def test_build_feed_payload_has_required_top_level_keys():
    dataset_df = pd.DataFrame({"player": ["Test Player"], "team": ["ROM"], "role": ["C"]})
    payload = build_feed.build_feed_payload(dataset_df, matchday=4, season="2026/2027")
    assert set(["matchday", "season", "updated_at", "fixtures", "players"]).issubset(payload.keys())
    assert payload["matchday"] == 4
    assert payload["season"] == "2026/2027"


@patch("pipeline.dynamic.build_feed.scrape_lineups.scrape_probable_lineups")
@patch("pipeline.dynamic.build_feed.scrape_status.scrape_all_statuses")
@patch("pipeline.dynamic.build_feed.scrape_results.load_ewma_state")
@patch("pipeline.dynamic.build_feed.scrape_odds.build_odds_feed")
def test_build_feed_payload_uses_mocked_scrapers(
    mock_odds, mock_ewma, mock_status, mock_lineups
):
    """Verify build_feed_payload properly calls and uses all scraper functions."""
    mock_lineups.return_value = [
        {"player_name": "Lautaro Martinez", "match_id": "1", "side": "home", "href": ""}
    ]
    mock_status.return_value = {}
    mock_ewma.return_value = {"Lautaro Martinez": 7.2}
    mock_odds.return_value = [
        {
            "fixture_id": 1,
            "home_team": "Inter",
            "away_team": "Monza",
            "date": "2026-09-20T18:45:00+00:00",
            "odds_available": True,
            "home_win_prob": 0.6,
        }
    ]
    
    dataset_df = pd.DataFrame({
        "player": ["Lautaro Martinez"],
        "team": ["INT"],
        "role": ["A"],
    })
    
    payload = build_feed.build_feed_payload(dataset_df, matchday=1, season="2026/2027")
    
    # Verify all scrapers were called
    mock_lineups.assert_called_once()
    mock_status.assert_called_once()
    mock_ewma.assert_called_once()
    mock_odds.assert_called_once()
    
    # Verify payload structure
    assert payload["fixtures"] == mock_odds.return_value
    assert "int_lautaro_martinez_a" in payload["players"]
    assert payload["players"]["int_lautaro_martinez_a"]["ewma_form"] == 7.2


@patch("pipeline.dynamic.build_feed.scrape_lineups.scrape_probable_lineups")
@patch("pipeline.dynamic.build_feed.scrape_status.scrape_all_statuses")
@patch("pipeline.dynamic.build_feed.scrape_results.load_ewma_state")
@patch("pipeline.dynamic.build_feed.scrape_odds.build_odds_feed")
def test_main_raises_when_insufficient_players(
    mock_odds, mock_ewma, mock_status, mock_lineups, tmp_path, monkeypatch
):
    """Verify main() raises RuntimeError when fewer than MIN_VALID_PLAYERS_IN_FEED players."""
    mock_lineups.return_value = []
    mock_status.return_value = {}
    mock_ewma.return_value = {}
    mock_odds.return_value = []
    
    # Create a small dataset with fewer than MIN_VALID_PLAYERS_IN_FEED players
    dataset_csv = tmp_path / "dataset_finale.csv"
    small_df = pd.DataFrame({
        "player": [f"Player{i}" for i in range(10)],
        "team": ["INT"] * 10,
        "role": ["A"] * 10,
    })
    small_df.to_csv(dataset_csv, index=False)
    
    # Also mock the output path
    output_json = tmp_path / "current_matchday.json"
    monkeypatch.setattr(build_feed.config, "DATASET_FINALE_CSV", str(dataset_csv))
    monkeypatch.setattr(build_feed.config, "CURRENT_MATCHDAY_JSON", str(output_json))
    
    with pytest.raises(RuntimeError) as exc_info:
        build_feed.main(matchday=1, season="2026/2027")
    
    assert "Feed dinamico incompleto" in str(exc_info.value)
    assert "giocatori validi" in str(exc_info.value)


# ──────────────────────────────────────────────────────────────────────
# CLIENT TESTS — Singleton MatchdayFeedClient with cache and fallback
# ──────────────────────────────────────────────────────────────────────

from pipeline.dynamic.client import MatchdayFeedClient


def test_client_returns_fallback_when_fetch_fails(tmp_path):
    fallback_path = tmp_path / "fallback_matchday.json"
    fallback_payload = {"matchday": 0, "season": "2026/2027", "fixtures": [], "players": {}}
    fallback_path.write_text(json.dumps(fallback_payload), encoding="utf-8")

    with patch("pipeline.dynamic.client.requests.get", side_effect=Exception("network down")):
        client = MatchdayFeedClient(
            feed_url="https://example.invalid/current_matchday.json",
            fallback_path=str(fallback_path),
        )
        feed = client.get_feed()
    assert feed == fallback_payload


def test_client_caches_within_ttl(tmp_path):
    fallback_path = tmp_path / "fallback_matchday.json"
    fallback_path.write_text(json.dumps({"matchday": 0, "fixtures": [], "players": {}}), encoding="utf-8")

    mock_response = MagicMock()
    mock_response.json.return_value = {"matchday": 5, "fixtures": [], "players": {}}
    mock_response.status_code = 200

    with patch("pipeline.dynamic.client.requests.get", return_value=mock_response) as mock_get:
        client = MatchdayFeedClient(
            feed_url="https://example.invalid/current_matchday.json",
            ttl_seconds=900,
            fallback_path=str(fallback_path),
        )
        first = client.get_feed()
        second = client.get_feed()
        assert first["matchday"] == 5
        assert second["matchday"] == 5
        assert mock_get.call_count == 1  # secondo fetch servito dalla cache


def test_client_retries_after_fallback_on_next_call(tmp_path):
    """Verify that after a fallback, the next call retries the HTTP fetch."""
    fallback_path = tmp_path / "fallback_matchday.json"
    fallback_payload = {"matchday": 0, "season": "2026/2027", "fixtures": [], "players": {}}
    fallback_path.write_text(json.dumps(fallback_payload), encoding="utf-8")

    mock_response = MagicMock()
    mock_response.json.return_value = {"matchday": 5, "fixtures": [], "players": {}}
    mock_response.status_code = 200

    call_count = [0]
    
    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise Exception("network down")
        return mock_response

    with patch("pipeline.dynamic.client.requests.get", side_effect=side_effect) as mock_get:
        client = MatchdayFeedClient(
            feed_url="https://example.invalid/current_matchday.json",
            ttl_seconds=900,
            fallback_path=str(fallback_path),
        )
        # First call: fetch fails, returns fallback
        first = client.get_feed()
        assert first == fallback_payload
        
        # Second call: fetch succeeds, returns fresh data (not cached from previous)
        second = client.get_feed()
        assert second["matchday"] == 5
        assert mock_get.call_count == 2  # Both calls attempted HTTP fetch


def test_client_expires_cache_after_ttl(tmp_path):
    """Verify that cache expires after TTL and a new fetch is attempted."""
    fallback_path = tmp_path / "fallback_matchday.json"
    fallback_path.write_text(json.dumps({"matchday": 0, "fixtures": [], "players": {}}), encoding="utf-8")

    mock_response_1 = MagicMock()
    mock_response_1.json.return_value = {"matchday": 5, "fixtures": [], "players": {}}
    mock_response_1.status_code = 200

    mock_response_2 = MagicMock()
    mock_response_2.json.return_value = {"matchday": 6, "fixtures": [], "players": {}}
    mock_response_2.status_code = 200

    responses = [mock_response_1, mock_response_2]
    response_iter = iter(responses)

    def get_response(*args, **kwargs):
        return next(response_iter)

    with patch("pipeline.dynamic.client.requests.get", side_effect=get_response) as mock_get:
        with patch("pipeline.dynamic.client.time.time") as mock_time:
            times = [0.0, 1.0, 1001.0]  # First call at 0, second at 1s, third at 1001s (>TTL)
            time_iter = iter(times)
            mock_time.side_effect = lambda: next(time_iter)
            
            client = MatchdayFeedClient(
                feed_url="https://example.invalid/current_matchday.json",
                ttl_seconds=900,
                fallback_path=str(fallback_path),
            )
            
            # First call: fetch, cache matchday 5
            first = client.get_feed()
            assert first["matchday"] == 5
            
            # Second call at 1s (within TTL): returns cache (matchday 5)
            second = client.get_feed()
            assert second["matchday"] == 5
            
            # Third call at 1001s (TTL expired): fetch again, get matchday 6
            third = client.get_feed()
            assert third["matchday"] == 6
            
            assert mock_get.call_count == 2  # First and third calls fetched


def test_client_singleton_get_default_client():
    """Verify that get_default_client() returns the same singleton instance."""
    from pipeline.dynamic.client import get_default_client, _default_client, _default_client_lock
    
    # Reset singleton for test
    import pipeline.dynamic.client as client_module
    with client_module._default_client_lock:
        client_module._default_client = None
    
    client1 = get_default_client()
    client2 = get_default_client()
    
    # Should be the same object
    assert client1 is client2
