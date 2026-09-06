#!/usr/bin/env python3
"""
Utility condivise per il feed dinamico infrasettimanale (Pilastro 3):
normalizzazione nomi, matching giocatore->dataset, richieste HTTP resilienti.
"""
import difflib
import random
import time
import unicodedata

import requests

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]


def normalize_name(s):
    """Rimuove accenti, converte in minuscolo e strippa gli spazi."""
    s = str(s).strip()
    s = s.replace("ı", "i").replace("İ", "I")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s.lower()


class PlayerMatcher:
    """
    Fa il match di un nome giocatore (proveniente da uno scraper esterno) sui nomi
    presenti nel dataset fanta-lab, con lo stesso approccio a cascata già usato in
    pipeline/04b_scrape_lineups.py: match esatto normalizzato -> fuzzy per squadra ->
    fuzzy sul cognome per squadra -> fuzzy globale a soglia più permissiva.
    """

    def __init__(self, dataset_df, name_col="player", team_col="team"):
        self.name_col = name_col
        self.team_col = team_col
        self.names = dataset_df[name_col].tolist()
        self.teams = dict(zip(dataset_df[name_col], dataset_df[team_col]))
        self.norm_to_name = {normalize_name(n): n for n in self.names}
        self.all_norm = [normalize_name(n) for n in self.names]

    def match(self, query_name, query_team):
        query_norm = normalize_name(query_name)

        if query_norm in self.norm_to_name:
            return self.norm_to_name[query_norm]

        team_candidates = [n for n in self.names if self.teams.get(n) == query_team]
        team_candidates_norm = [normalize_name(n) for n in team_candidates]

        fuzzy = difflib.get_close_matches(query_norm, team_candidates_norm, n=1, cutoff=0.60)
        if fuzzy:
            return team_candidates[team_candidates_norm.index(fuzzy[0])]

        last_name = query_name.split()[-1] if query_name.split() else query_name
        last_fuzzy = difflib.get_close_matches(
            normalize_name(last_name), team_candidates_norm, n=1, cutoff=0.70
        )
        if last_fuzzy:
            return team_candidates[team_candidates_norm.index(last_fuzzy[0])]

        global_fuzzy = difflib.get_close_matches(query_norm, self.all_norm, n=1, cutoff=0.70)
        if global_fuzzy:
            return self.names[self.all_norm.index(global_fuzzy[0])]

        return None


def fetch_with_retry(url, headers=None, params=None, max_retries=3, timeout=10):
    """
    GET resiliente: retry esponenziale su 403/429/5xx/timeout, User-Agent rotante.
    Ritorna la Response su successo (status 200) or None se tutti i tentativi falliscono.
    """
    req_headers = dict(headers or {})
    for attempt in range(max_retries):
        req_headers["User-Agent"] = random.choice(USER_AGENTS)
        try:
            resp = requests.get(url, headers=req_headers, params=params, timeout=timeout)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (403, 429):
                time.sleep((2 ** attempt) + random.uniform(1.5, 3.0))
            elif resp.status_code in (500, 502, 503, 504):
                time.sleep(1.0 * (attempt + 1))
            else:
                return None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            break
    return None
