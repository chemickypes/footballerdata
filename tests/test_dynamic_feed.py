#!/usr/bin/env python3
"""
Unit tests for pipeline/dynamic/* — feed dinamico infrasettimanale (Pilastro 3).
No live network calls: all HTTP is mocked via unittest.mock.patch.
"""
import os
import sys
from unittest.mock import patch, MagicMock

import pandas as pd
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
