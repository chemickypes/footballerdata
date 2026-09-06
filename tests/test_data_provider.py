import math
import os
import sys
from unittest.mock import MagicMock

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.common.data_provider import (
    is_overlay_real,
    get_dynamic_overlay,
    compute_weekly_xpts,
    get_player_status,
)


def test_is_overlay_real_false_for_placeholder_feed():
    placeholder = {"matchday": 0, "season": "2026/2027", "fixtures": [], "players": {}}
    assert is_overlay_real(placeholder) is False


def test_is_overlay_real_false_for_none():
    assert is_overlay_real(None) is False


def test_is_overlay_real_true_for_populated_feed():
    real_feed = {
        "matchday": 4,
        "season": "2026/2027",
        "fixtures": [],
        "players": {"inter_lautaro_martinez_a": {"name": "Lautaro Martinez", "xpts": 6.85}},
    }
    assert is_overlay_real(real_feed) is True


def test_compute_weekly_xpts_returns_nan_column_when_overlay_missing():
    df = pd.DataFrame([{"player": "Malen", "role": "A", "team": "Milan"}])
    result_df, available = compute_weekly_xpts(df, None)
    assert available is False
    assert result_df["xpts_week"].isna().all()


def test_compute_weekly_xpts_matches_player_by_key_when_overlay_real():
    df = pd.DataFrame([{"player": "Lautaro Martinez", "role": "A", "team": "Inter"}])
    overlay = {
        "matchday": 4,
        "players": {
            "inter_lautaro_martinez_a": {"name": "Lautaro Martinez", "xpts": 6.85, "status": "OK"}
        },
    }
    result_df, available = compute_weekly_xpts(df, overlay)
    assert available is True
    assert result_df.loc[0, "xpts_week"] == 6.85


def test_compute_weekly_xpts_nan_for_player_missing_from_overlay():
    df = pd.DataFrame([{"player": "Unknown Player", "role": "A", "team": "Roma"}])
    overlay = {"matchday": 4, "players": {"inter_lautaro_martinez_a": {"xpts": 6.85, "status": "OK"}}}
    result_df, available = compute_weekly_xpts(df, overlay)
    assert available is True
    assert math.isnan(result_df.loc[0, "xpts_week"])


def test_get_player_status_defaults_to_ok_when_overlay_missing():
    assert get_player_status(None, "Inter", "Lautaro Martinez", "A") == "OK"


def test_get_player_status_returns_feed_status():
    overlay = {
        "matchday": 4,
        "players": {"inter_lautaro_martinez_a": {"status": "INFORTUNATO"}},
    }
    assert get_player_status(overlay, "Inter", "Lautaro Martinez", "A") == "INFORTUNATO"


def test_get_dynamic_overlay_returns_none_when_client_raises():
    """get_dynamic_overlay() must never raise: any exception (network error,
    malformed JSON, etc.) must result in None being returned."""
    mock_client = MagicMock()
    mock_client.get_feed.side_effect = Exception("Network error")
    result = get_dynamic_overlay(client=mock_client)
    assert result is None


def test_get_dynamic_overlay_returns_populated_feed():
    """get_dynamic_overlay() returns the feed dict when it contains real data
    (matchday > 0 and non-empty players)."""
    populated_feed = {
        "matchday": 4,
        "season": "2026/2027",
        "fixtures": [],
        "players": {"inter_lautaro_martinez_a": {"name": "Lautaro Martinez", "xpts": 6.85}},
    }
    mock_client = MagicMock()
    mock_client.get_feed.return_value = populated_feed
    result = get_dynamic_overlay(client=mock_client)
    assert result == populated_feed


def test_get_dynamic_overlay_returns_none_for_placeholder_feed():
    """get_dynamic_overlay() returns None for the placeholder feed
    (matchday=0 and empty players dict)."""
    placeholder_feed = {"matchday": 0, "season": "2026/2027", "fixtures": [], "players": {}}
    mock_client = MagicMock()
    mock_client.get_feed.return_value = placeholder_feed
    result = get_dynamic_overlay(client=mock_client)
    assert result is None
