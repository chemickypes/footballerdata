#!/usr/bin/env python3
"""
Client thread-safe per il feed dinamico infrasettimanale (Pilastro 3), usato da app.py.
Cache in-memory con TTL 15 minuti; fallback automatico su data/fallback_matchday.json
in caso di fetch fallito o timeout. Nessuna scrittura su disco a runtime.
"""
import json
import os
import sys
import threading
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

DEFAULT_FEED_URL = (
    "https://raw.githubusercontent.com/SpectreLabo/fanta-lab/data-feed/data/current_matchday.json"
)


class MatchdayFeedClient:
    def __init__(self, feed_url=None, ttl_seconds=900, fallback_path=None):
        self.feed_url = feed_url or os.environ.get("MATCHDAY_FEED_URL", DEFAULT_FEED_URL)
        self.ttl_seconds = ttl_seconds
        self.fallback_path = fallback_path or config.FALLBACK_MATCHDAY_JSON
        self._lock = threading.Lock()
        self._cache = None
        self._cache_ts = 0.0

    def _load_fallback(self):
        try:
            with open(self.fallback_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"matchday": 0, "season": "", "fixtures": [], "players": {}}

    def get_feed(self):
        with self._lock:
            now = time.time()
            if self._cache is not None and (now - self._cache_ts) < self.ttl_seconds:
                return self._cache

            try:
                resp = requests.get(self.feed_url, timeout=8)
                if resp.status_code == 200:
                    payload = resp.json()
                    self._cache = payload
                    self._cache_ts = now
                    return payload
            except Exception:
                pass

            # Fetch fallito: usa il fallback statico ma NON aggiorna il timestamp di
            # cache, cosi' il prossimo tentativo riprovera' subito il fetch remoto.
            return self._load_fallback()


_default_client = None
_default_client_lock = threading.Lock()


def get_default_client():
    global _default_client
    with _default_client_lock:
        if _default_client is None:
            _default_client = MatchdayFeedClient()
        return _default_client
