#!/usr/bin/env python3
"""
FASE 3b — Scraping attributi giocatori da Transfermarkt.

Per ogni giocatore nel dataset, cerca il profilo su Transfermarkt (stessa
risoluzione search+team della Fase 3 infortuni) ed estrae gli attributi
anagrafici e di carriera: età, altezza, piede, valore di mercato, scadenza contratto.

NOT IN run_pipeline (esecuzione manuale, come 04b):
    python core/ingestion/static/05b_scrape_attributes.py

Output:
  - data/tm_attributes_cache.json   (cache incrementale, keyed by dataset player name)
  - Nuove colonne nel dataset finale: age, height_cm, foot, market_value_eur, contract_until
"""

import os, sys, re, time, json, warnings, urllib.parse, threading, random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # static -> ingestion -> core -> repo root
sys.path.insert(0, _REPO_ROOT)  # standalone-capable
from core import config

warnings.filterwarnings("ignore")

lock = threading.Lock()
cache = {}

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
]

ATTRIBUTES_CACHE_JSON = os.path.join(config.DATA_DIR, "tm_attributes_cache.json")


def clean_query(name):
    """Pulisce iniziali tipo ' L.' o ' Jo.' per la ricerca su Transfermarkt."""
    q = re.sub(r'\s+[A-Z][a-z]?\.$', '', name).strip()
    return q


def fetch_url_with_retry(url, headers=None, max_retries=3, timeout=8):
    """Esegue richiesta HTTP GET con retry esponenziale su 403/429/5xx/timeout e User-Agent rotanti."""
    req_headers = dict(headers or config.HEADERS)
    for attempt in range(max_retries):
        req_headers["User-Agent"] = random.choice(USER_AGENTS)
        try:
            resp = requests.get(url, headers=req_headers, timeout=timeout)
            if resp.status_code == 200:
                return resp
            elif resp.status_code in (403, 429):
                sleep_time = (2 ** attempt) + random.uniform(1.5, 3.0)
                time.sleep(sleep_time)
            elif resp.status_code in (500, 502, 503, 504):
                time.sleep(1.0 * (attempt + 1))
            else:
                return resp
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            break
    return None


def parse_market_value_eur(html):
    """Estrae il valore di mercato corrente dal box data-header (es. '€35.00m' -> 35000000)."""
    m = re.search(r'data-header__market-value-wrapper.*?</a>', html, re.S)
    if not m:
        return None
    text = re.sub(r'<[^>]+>', ' ', m.group(0))
    vm = re.search(r'€\s*([\d.,]+)\s*(th|k|m|bn)?', text)
    if not vm:
        return None
    try:
        val = float(vm.group(1).replace(",", ""))  # TM uses the dot as decimal separator (e.g. '35.00m')
    except ValueError:
        return None
    mult = {"th": 1e3, "k": 1e3, "m": 1e6, "bn": 1e9}.get(vm.group(2) or "", 1.0)
    return int(val * mult)


def parse_contract_until(html):
    """Estrae la scadenza contratto e la normalizza a ISO (yyyy-mm-dd)."""
    m = re.search(r'Contract expires:?\s*<span class="data-header__content[^"]*"[^>]*>\s*([^<]+?)\s*<', html)
    if not m:
        return None
    raw = m.group(1).strip()
    try:
        return datetime.strptime(raw, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return raw


def parse_attributes(profile_html):
    """Estrae age/height_cm/foot/market_value_eur/contract_until dalla pagina profilo TM."""
    html = profile_html

    age = None
    ma = re.search(r'Date of birth/Age:?\s*<span[^>]*>\s*[^<]*?\((\d{1,2})\)', html)
    if ma:
        age = int(ma.group(1))

    height_cm = None
    mh = re.search(r'itemprop="height"[^>]*>\s*([\d]+(?:[.,]\d+)?)\s*m', html)
    if mh:
        try:
            height_cm = int(round(float(mh.group(1).replace(",", ".")) * 100))
        except ValueError:
            pass

    foot = None
    mf = re.search(r'Foot:\s*</span>\s*<span class="info-table__content info-table__content--bold">\s*([^<]+?)\s*<', html)
    if mf:
        foot = mf.group(1).strip().lower()

    mv = parse_market_value_eur(html)
    contract = parse_contract_until(html)

    return age, height_cm, foot, mv, contract


def fetch_player_attributes(row):
    """Cerca un giocatore su Transfermarkt e ne estrae gli attributi di profilo."""
    player_name = str(row["player"]).strip()
    team_abbr = str(row["team"]).strip() if pd.notna(row.get("team")) else ""
    team_tm = config.TEAM_TM_MAP.get(team_abbr, "")

    q_name = clean_query(player_name)
    search_url = f"https://www.transfermarkt.com/schnellsuche/ergebnis/schnellsuche?query={urllib.parse.quote(q_name)}"

    result = {
        "player_name": player_name,
        "tm_found": False,
        "tm_matched_name": "",
        "age": None,
        "height_cm": None,
        "foot": None,
        "market_value_eur": None,
        "contract_until": None,
    }

    try:
        resp = fetch_url_with_retry(search_url, headers=config.HEADERS, timeout=8)
        if resp and resp.ok:
            soup = BeautifulSoup(resp.text, "html.parser")
            player_rows = soup.select("div.box #yw1 tbody tr")
            if not player_rows:
                player_rows = soup.select("table.items tbody tr")

            target_href = None
            target_name = ""

            for pr in player_rows:
                a_link = pr.select_one('td.hauptlink a[href*="/profil/spieler/"]')
                if not a_link:
                    continue

                p_title = a_link.get_text(strip=True)
                p_href = a_link["href"]

                club_img = pr.select_one("td.zentriert img[alt]")
                club_name = club_img["alt"] if club_img else ""

                if team_tm and team_tm.lower() in club_name.lower():
                    target_href = p_href
                    target_name = p_title
                    break
                elif not target_href:
                    target_href = p_href
                    target_name = p_title

            if target_href:
                profile_url = "https://www.transfermarkt.com" + target_href
                resp2 = fetch_url_with_retry(profile_url, headers=config.HEADERS, timeout=8)
                if resp2 and resp2.ok:
                    age, height_cm, foot, mv, contract = parse_attributes(resp2.text)
                    result.update({
                        "tm_found": True,
                        "tm_matched_name": target_name,
                        "age": age,
                        "height_cm": height_cm,
                        "foot": foot,
                        "market_value_eur": mv,
                        "contract_until": contract,
                    })
    except Exception:
        pass

    with lock:
        cache[player_name] = result

    return player_name, result


def main():
    print("=" * 60)
    print("  FASE 3b — SCRAPING ATTRIBUTI TRANSFERMARKT")
    print("=" * 60)

    df = pd.read_csv(config.DATASET_FINALE_CSV)

    # Cache incrementale: salta i profili già risolti
    if os.path.exists(ATTRIBUTES_CACHE_JSON):
        try:
            with open(ATTRIBUTES_CACHE_JSON, "r", encoding="utf-8") as f:
                cache.update(json.load(f))
            n_cached = sum(1 for v in cache.values() if v.get("tm_found"))
            print(f"  Cache caricata: {n_cached} profili validi su {len(cache)}")
        except Exception as e:
            print(f"  ⚠️ Errore lettura cache: {e}")

    rows_to_process = [r for _, r in df.iterrows() if not cache.get(str(r["player"]).strip(), {}).get("tm_found")]

    print(f"\n  Giocatori da processare: {len(rows_to_process)} (già in cache: {len(df) - len(rows_to_process)})")
    start_time = time.time()
    completed = 0

    with ThreadPoolExecutor(max_workers=config.TM_MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_player_attributes, r): r["player"] for r in rows_to_process}
        for future in as_completed(futures):
            completed += 1
            if completed % 30 == 0 or completed == len(rows_to_process):
                with lock:
                    with open(ATTRIBUTES_CACHE_JSON, "w", encoding="utf-8") as f:
                        json.dump(cache, f, ensure_ascii=False, indent=2)
                elapsed = time.time() - start_time
                print(f"  Progresso: {completed} / {len(rows_to_process)} in {elapsed:.1f}s")

    with open(ATTRIBUTES_CACHE_JSON, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    found_count = sum(1 for v in cache.values() if v.get("tm_found"))
    print(f"\n  Scraping terminato in {time.time() - start_time:.1f}s")
    print(f"  Profili TM trovati online: {found_count} / {len(cache)}")

    if found_count == 0:
        print("  ⚠️ [WARNING] Nessun profilo estratto (blocco anti-bot o offline). Colonne attributi lasciate invariate.")
        return

    # Aggiorna dataset
    age_list, height_list, foot_list, mv_list, contract_list = [], [], [], [], []
    for _, row in df.iterrows():
        info = cache.get(str(row["player"]).strip(), {})
        age_list.append(info.get("age"))
        height_list.append(info.get("height_cm"))
        foot_list.append(info.get("foot"))
        mv_list.append(info.get("market_value_eur"))
        contract_list.append(info.get("contract_until"))

    df["age"] = pd.Series(age_list, dtype="Float64")
    df["height_cm"] = pd.Series(height_list, dtype="Float64")
    df["foot"] = pd.Series(foot_list, dtype="string")
    df["market_value_eur"] = pd.Series(mv_list, dtype="Float64")
    df["contract_until"] = pd.Series(contract_list, dtype="string")

    df.to_csv(config.DATASET_FINALE_CSV, index=False, encoding="utf-8-sig")
    print(f"  ✅ Dataset aggiornato: {config.DATASET_FINALE_CSV}")

    filled = df["age"].notna().sum()
    print(f"  Età compilata: {filled} / {len(df)} giocatori")

    print("\n  SAMPLE ATTRIBUTI:")
    sample_names = ["Svilar", "Martinez L.", "Calhanoglu", "Dimarco", "Thuram"]
    sub = df[df["player"].isin(sample_names)]
    for _, r in sub.iterrows():
        mv_str = f"{int(r['market_value_eur'])/1e6:.0f}M" if pd.notna(r.get("market_value_eur")) else "N/D"
        print(f"    {r['player']:<14} età:{r.get('age') or 'N/D':<3} altezza:{r.get('height_cm') or 'N/D':<4} "
              f"piede:{r.get('foot') or 'N/D':<6} mv:{mv_str:<6} contratto:{r.get('contract_until') or 'N/D'}")

    print("\n  FASE 3b COMPLETATA.\n")


if __name__ == "__main__":
    main()
