"""
Shared data layer for the Pilastro 4 analytics modules (lineup solver, audit
engine, trade analyzer). Isolates dataset loading and dynamic-feed access so
downstream modules never talk to pipeline.dynamic.client directly.
"""
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pipeline.dynamic.client import get_default_client
from pipeline.dynamic.utils import normalize_name


def is_overlay_real(feed):
    """Distinguishes a genuinely fetched dynamic feed from the empty placeholder
    fallback (data/fallback_matchday.json has matchday=0 and no players)."""
    if not feed:
        return False
    return feed.get("matchday", 0) > 0 and len(feed.get("players", {})) > 0


def get_dynamic_overlay(client=None):
    """Fetches the dynamic feed via the Pilastro 3 client. Never raises: any
    exception (network error, malformed JSON) results in None being returned,
    which callers must interpret as 'no live data available'."""
    try:
        client = client or get_default_client()
        feed = client.get_feed()
        return feed if is_overlay_real(feed) else None
    except Exception:
        return None


def _team_slug(team_value):
    return normalize_name(str(team_value)).replace(" ", "_")


def _player_key(team_value, player_name, role):
    """Mirrors pipeline.dynamic.build_feed._player_key exactly (team_player_role
    format) so overlay lookups match the keys produced by the feed builder."""
    return f"{_team_slug(team_value)}_{normalize_name(player_name).replace(' ', '_')}_{str(role).lower()}"


def compute_weekly_xpts(df, overlay):
    """Adds an 'xpts_week' column to a copy of df using the dynamic feed's
    precomputed per-player xpts. Returns (df_with_column, overlay_available).
    If overlay is None/not real, xpts_week is all NaN and overlay_available is
    False -- callers (e.g. lineup_solver) must check the flag, not just the
    column, since NaN alone doesn't distinguish 'no live data' from 'player
    missing from an otherwise valid feed'."""
    df = df.copy()
    overlay_available = is_overlay_real(overlay)

    if not overlay_available:
        df["xpts_week"] = math.nan
        return df, False

    players_feed = overlay.get("players", {})
    xpts_values = []
    for _, row in df.iterrows():
        key = _player_key(row.get("team", ""), row.get("player", ""), row.get("role", ""))
        entry = players_feed.get(key)
        xpts_values.append(entry["xpts"] if entry and "xpts" in entry else math.nan)
    df["xpts_week"] = xpts_values
    return df, True


def get_player_status(overlay, team, name, role):
    """Returns the dynamic feed status for a player ('OK' if unknown/overlay
    missing) -- used by lineup_solver to exclude INFORTUNATO/SQUALIFICATO."""
    if not is_overlay_real(overlay):
        return "OK"
    key = _player_key(team, name, role)
    entry = overlay.get("players", {}).get(key)
    return entry.get("status", "OK") if entry else "OK"
