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
