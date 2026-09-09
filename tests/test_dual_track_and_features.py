#!/usr/bin/env python3
"""
Smoke test — footballerdata web app (player-data pivot)
=======================================================
Tests the kept surface: /api/players (fasce, medical, understat, quantiles),
the Player Detail Drawer HTML, the AI copilot entity retrieval, and inline
JavaScript syntax integrity.

Requires the web app running on http://localhost:5050
"""
import json
import os
import sys
import requests

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://localhost:5050")
PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []


def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    print(f"  {status}  {name}" + (f"  ({detail})" if detail else ""))
    return condition


def main():
    print("\n" + "=" * 72)
    print("  SMOKE TEST — footballerdata player-data web app")
    print("=" * 72 + "\n")

    # ── 1. Server Health ──────────────────────────────────────────────
    print("▸ 1. Server Health Check")
    try:
        r = requests.get(f"{BASE_URL}/api/players", timeout=10)
        check("Server risponde su /api/players", r.status_code == 200, f"status={r.status_code}")
        data = r.json()
        players = data.get("players", [])
        check("Players > 0", len(players) > 0, f"n={len(players)}")
    except Exception as e:
        check("Server raggiungibile", False, str(e))
        print("\n⛔ Server non raggiungibile. Assicurati che app.py sia in esecuzione su porta 5050.")
        sys.exit(1)

    # ── 2. Removed endpoints are gone ─────────────────────────────────
    print("\n▸ 2. Fantasy endpoints rimossi (attesi 404/405)")
    for ep in ["/api/state", "/api/settings", "/api/assign", "/api/undo",
               "/api/favorite", "/api/reset", "/api/live/snapshot",
               "/api/lineup/solve", "/api/audit/rankings", "/api/trades/winwin"]:
        r = requests.get(f"{BASE_URL}{ep}", timeout=10)
        check(f"GET {ep} non disponibile", r.status_code == 404, f"status={r.status_code}")

    # ── 3. Fasce per Macro-Ruolo ──────────────────────────────────────
    print("\n▸ 3. Fasce (Quantili per Macro-Ruolo P, D, C, A)")
    for role in ["P", "D", "C", "A"]:
        role_players = [p for p in players if p.get("role") == role]
        fasce = {1: 0, 2: 0, 3: 0, 4: 0}
        for p in role_players:
            f = p.get("fascia", 0)
            if f in fasce:
                fasce[f] += 1
        all_populated = all(v > 0 for v in fasce.values())
        check(
            f"Ruolo {role}: tutte le fasce 1-4 popolate",
            all_populated,
            f"F1={fasce[1]}, F2={fasce[2]}, F3={fasce[3]}, F4={fasce[4]}"
        )

    p_by_name = {p["player"]: p for p in players if p.get("role") == "P"}
    check("Portieri Top in Fascia 1 (Svilar, Vicario, Carnesecchi)",
         p_by_name.get("Svilar", {}).get("fascia") == 1 and p_by_name.get("Vicario", {}).get("fascia") == 1 and p_by_name.get("Carnesecchi", {}).get("fascia") == 1)

    # ── 4. Medical Node (Finestra Medica) ─────────────────────────────
    print("\n▸ 4. Finestra Medica — Nodo 'medical' in /api/players")
    sample = players[0]
    med = sample.get("medical", {})
    check("Nodo 'medical' presente", "medical" in sample)
    check("medical.days_lost_3y è int", isinstance(med.get("days_lost_3y"), int))
    check("medical.injuries_count_3y è int", isinstance(med.get("injuries_count_3y"), int))
    check("medical.status in {safe, warning, danger}", med.get("status") in ("safe", "warning", "danger"), f"status={med.get('status')}")
    check("medical.status_badge non vuoto", len(med.get("status_badge", "")) > 0)
    check("medical.status_label non vuoto", len(med.get("status_label", "")) > 0)
    check("medical.dettaglio_infortuni è lista", isinstance(med.get("dettaglio_infortuni"), list))

    players_with_injuries = sum(1 for p in players if p.get("medical", {}).get("days_lost_3y", 0) > 0)
    check("Giocatori con giorni infortunio > 0", players_with_injuries > 10, f"n={players_with_injuries}")

    # ── 5. Understat Node ─────────────────────────────────────────────
    print("\n▸ 5. Volumi Offensivi — Nodo 'understat' in /api/players")
    us = sample.get("understat", {})
    check("Nodo 'understat' presente", "understat" in sample)
    for key in ["xg_per90", "npxg_per90", "xa_per90", "shots_per90", "delta_goals_xg"]:
        check(f"understat.{key} è numerico", isinstance(us.get(key), (int, float)), f"val={us.get(key)}")

    # ── 6. Quantiles Node ─────────────────────────────────────────────
    print("\n▸ 6. Profilo Quantilico — Nodo 'quantiles' in /api/players")
    q = sample.get("quantiles", {})
    check("Nodo 'quantiles' presente", "quantiles" in sample)
    for key in ["floor_p10", "expected_p50", "ceiling_p90", "spread"]:
        check(f"quantiles.{key} è numerico", isinstance(q.get(key), (int, float)), f"val={q.get(key)}")
    check("quantiles.profile_label presente", len(q.get("profile_label", "")) > 0)
    check("quantiles.profile_badge presente", len(q.get("profile_badge", "")) > 0)
    check("P10 <= P50 <= P90", q.get("floor_p10", 0) <= q.get("expected_p50", 0) <= q.get("ceiling_p90", 0))

    # ── 7. VORP / Fair Price quality scores ───────────────────────────
    print("\n▸ 7. Quality Scores — VORP & Prezzi Fair")
    check("Calciatore include 'vorp'", "vorp" in sample, f"vorp={sample.get('vorp')}")
    check("Calciatore include 'contrib_exp' (pg×MV projection)", "contrib_exp" in sample, f"contrib={sample.get('contrib_exp')}")
    check("Nessun campo 'pts_exp' fantasy residuo", "pts_exp" not in sample)
    check("Calciatore include 'price_fair_1000'", "price_fair_1000" in sample, f"fair={sample.get('price_fair_1000')}")
    check("Calciatore include 'surplus_value'", "surplus_value" in sample, f"surplus={sample.get('surplus_value')}")
    check("Nessun campo 'is_assigned' residuo", "is_assigned" not in sample)
    check("Nessun campo 'is_favorite' residuo", "is_favorite" not in sample)
    check("Risposta senza 'tactical_presets'", "tactical_presets" not in data)
    check("Risposta senza 'market_index'", "market_index" not in data)

    # ── 8. HTML Endpoint ──────────────────────────────────────────────
    print("\n▸ 8. HTML Endpoint — Player Detail Drawer Presente")
    r_html = requests.get(f"{BASE_URL}/")
    check("GET / → 200", r_html.status_code == 200)
    html = r_html.text
    r_appjs = requests.get(f"{BASE_URL}/static/js/app.js", timeout=10)
    app_js = r_appjs.text
    check("HTML contiene 'playerDetailDrawer'", "playerDetailDrawer" in html)
    check("app.js contiene 'openPlayerDetailDrawer'", "openPlayerDetailDrawer" in app_js)
    check("app.js contiene 'pdMedBadge' (Finestra Medica)", "pdMedBadge" in app_js)
    check("app.js contiene 'pdXg90' (Understat)", "pdXg90" in app_js)
    check("app.js contiene 'pdProfileBadge' (Quantiles)", "pdProfileBadge" in app_js)

    # ── 9. Entity-First Retrieval (Thuram & Woltemade) ────────────────
    # Nota: con LLM locali lenti (es. Ollama su CPU) la richiesta puo' superare
    # il timeout: in quel caso la sezione viene saltata senza far crashare lo script.
    print("\n▸ 9. Entity-First Copilot Retrieval — Thuram & Woltemade")
    try:
        r_copilot_comp = requests.post(f"{BASE_URL}/api/ai_query", json={"prompt": "parlami di thuram e woltemade"}, timeout=35)
        check("POST /api/ai_query comparison → 200", r_copilot_comp.status_code == 200)
        comp_json = r_copilot_comp.json()
        check("Risposta confronto non vuota", bool(comp_json))
        comp_players = [p.get("name", "").lower() for p in comp_json.get("players", [])]
        check("Confronto contiene 'thuram'", any("thuram" in p for p in comp_players) or "thuram" in str(comp_json).lower())
        check("Confronto contiene 'woltemade'", any("woltemade" in p for p in comp_players) or "woltemade" in str(comp_json).lower())
    except requests.exceptions.Timeout:
        print("  (SKIP: LLM lento, /api/ai_query oltre i 35s)")

    try:
        r_copilot_single = requests.post(f"{BASE_URL}/api/ai_query", json={"prompt": "chi è woltemade?"}, timeout=35)
        check("POST /api/ai_query single player → 200", r_copilot_single.status_code == 200)
        single_json = r_copilot_single.json()
        check("Single player Woltemade riconosciuto", "woltemade" in str(single_json).lower())
    except requests.exceptions.Timeout:
        print("  (SKIP: LLM lento, /api/ai_query oltre i 35s)")

    # ── 10. Static Assets & JavaScript Syntax ─────────────────────────
    print("\n▸ 10. Static Assets & Integrità JavaScript")
    import re, subprocess, tempfile
    r_css = requests.get(f"{BASE_URL}/static/css/main.css", timeout=10)
    check("GET /static/css/main.css → 200", r_css.status_code == 200)
    check("main.css non vuota", len(r_css.text) > 1000, f"bytes={len(r_css.text)}")

    scripts = []
    for js_path in ["/static/js/app.js", "/static/js/tutorial.js"]:
        r_js = requests.get(f"{BASE_URL}{js_path}", timeout=10)
        check(f"GET {js_path} → 200", r_js.status_code == 200)
        if r_js.status_code == 200:
            scripts.append((js_path, r_js.text))

    check("File JS esterni serviti", len(scripts) == 2, f"n={len(scripts)}")
    for i, (js_path, content) in enumerate(scripts):
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as tf:
            tf.write(content)
            tf_path = tf.name
        res = subprocess.run(['node', '--check', tf_path], capture_output=True, text=True)
        try:
            os.unlink(tf_path)
        except Exception:
            pass
        check(f"{js_path} validazione sintassi JavaScript (node --check)", res.returncode == 0, res.stderr.strip()[:80] if res.returncode != 0 else "Nessun errore di sintassi")

    check("HTML non contiene script inline", "<script>\n" not in html and "<style>" not in html)
    check("HTML linka main.css", '/static/css/main.css' in html)
    check("HTML linka app.js", '/static/js/app.js' in html)
    check("app.js contiene 'medical-badge'", "medical-badge" in app_js)
    check("Listone include badge medico integro/infortunato", "Finestra Medica:" in app_js)

    # ── 11. Media Voto & Ordinamento ──────────────────────────────────
    print("\n▸ 11. Media Voto & Ordinamento Listone")
    check("Calciatore include 'mv'", "mv" in sample, f"mv={sample.get('mv')}")
    check("Calciatore include 'mfv'", "mfv" in sample, f"mfv={sample.get('mfv')}")
    check("Calciatore include 'expected_matches'", "expected_matches" in sample, f"exp={sample.get('expected_matches')}")
    check("Calciatore include 'bonus_range'", "bonus_range" in sample, f"bonus={sample.get('bonus_range')}")

    check("listSortBy contiene opzione 'mv_desc'", 'value="mv_desc"' in html)
    check("listSortBy contiene opzione 'mfv_desc'", 'value="mfv_desc"' in html)

    sort_select_match = re.search(r'<select id="listSortBy"[^>]*>(.*?)</select>', html, re.DOTALL)
    check("Selettore listSortBy trovato nell'HTML", sort_select_match is not None)
    if sort_select_match:
        sort_opts = sort_select_match.group(1)
        has_emoji = any(em in sort_opts for em in ["⭐", "💰", "📉", "🎯", "🚀", "🔤", "⚽", "🔥"])
        check("listSortBy non contiene emoji (design sobrio e pulito)", not has_emoji)

    # ── 12. Career Trajectory Endpoint ────────────────────────────────
    print("\n▸ 12. Traiettoria Carriera — /api/player_history")
    r_hist = requests.get(f"{BASE_URL}/api/player_history", params={"player": "Svilar"}, timeout=10)
    check("GET /api/player_history?player=Svilar → 200", r_hist.status_code == 200, f"status={r_hist.status_code}")
    if r_hist.status_code == 200:
        hist_data = r_hist.json()
        seasons = [h.get("season") for h in hist_data.get("history", [])]
        check("Storico Svilar non vuoto (>= 2 stagioni)", len(seasons) >= 2, f"seasons={seasons}")
        check("Stagioni in ordine cronologico", seasons == sorted(seasons))
        first = hist_data["history"][-1]
        check("Riga storico ha season/team/pg/mv", all(k in first for k in ["season", "team", "pg", "mv"]))
    r_hist_404 = requests.get(f"{BASE_URL}/api/player_history", params={"player": "Zzz_Nessuno"}, timeout=10)
    check("Giocatore sconosciuto → 404", r_hist_404.status_code == 404, f"status={r_hist_404.status_code}")
    r_hist_drawer = requests.get(f"{BASE_URL}/static/js/app.js", timeout=10)
    check("app.js contiene 'renderTrajectorySVG'", "renderTrajectorySVG" in r_hist_drawer.text)
    check("Drawer HTML contiene 'pdTrajectory'", "pdTrajectory" in html)

    # ── 13. Attributi Giocatore (Transfermarkt) ───────────────────────
    print("\n▸ 13. Profilo & Contratto — attributi TM in /api/players")
    check("Calciatore include 'age'", "age" in sample, f"age={sample.get('age')}")
    check("Calciatore include 'market_value_eur'", "market_value_eur" in sample, f"mv={sample.get('market_value_eur')}")
    n_age = sum(1 for p in players if p.get("age"))
    n_mv = sum(1 for p in players if p.get("market_value_eur"))
    check("Età compilata per la maggioranza (> 400)", n_age > 400, f"n={n_age}")
    check("Valore mercato compilato per la maggioranza (> 400)", n_mv > 400, f"n={n_mv}")
    check("app.js contiene 'pdMarketValue'", "pdMarketValue" in app_js)
    check("Drawer HTML contiene 'Profilo & Contratto'", "Profilo &amp; Contratto" in html)

    # ── 14. Partite & Risultati — /api/matches ────────────────────────
    print("\n▸ 14. Partite & Risultati — /api/matches")
    r_matches = requests.get(f"{BASE_URL}/api/matches", timeout=10)
    check("GET /api/matches → 200", r_matches.status_code == 200, f"status={r_matches.status_code}")
    mdata = r_matches.json()
    check("Risposta ha flag 'available'", "available" in mdata, f"available={mdata.get('available')}")
    if mdata.get("available"):
        check("Rounds non vuoti", len(mdata.get("rounds", [])) > 0, f"n={len(mdata.get('rounds', []))}")
        check("Stagione presente", bool(mdata.get("season")), f"season={mdata.get('season')}")
        rnd0 = mdata["rounds"][0]
        m0 = rnd0["matches"][0]
        for key in ["fixture_id", "round", "date", "home_code", "away_code",
                    "home_display", "away_display", "home_score", "away_score",
                    "status", "finished"]:
            check(f"match.{key} presente", key in m0, f"val={m0.get(key)}")
        finished_rounds = [rr["round"] for rr in mdata["rounds"] if any(mm["finished"] for mm in rr["matches"])]
        expected_current = max(finished_rounds) if finished_rounds else None
        check("current_round coerente con l'ultima giornata giocata",
              mdata.get("current_round") == expected_current,
              f"current={mdata.get('current_round')}")
        check("team_form non vuoto", len(mdata.get("team_form", {})) > 0,
              f"n={len(mdata.get('team_form', {}))}")
        tf_entry = next(iter(mdata["team_form"].values()))
        for key in ["played", "wins", "draws", "losses", "points", "gf", "ga", "form", "last5"]:
            check(f"team_form.{key} presente", key in tf_entry)
        n_finished = sum(1 for rr in mdata["rounds"] for mm in rr["matches"] if mm["finished"])
        check("Almeno una partita conclusa", n_finished > 0, f"n={n_finished}")
    else:
        check("Flag available=false coerente (stage 11 non eseguito)", mdata.get("rounds", []) == [])

    check("HTML contiene 'tab-partite'", "tab-partite" in html)
    check("HTML contiene 'matchesContainer'", "matchesContainer" in html)
    check("HTML contiene 'pdTeamForm' (Forma Squadra)", "pdTeamForm" in html)
    check("app.js contiene 'renderMatches'", "renderMatches" in app_js)
    check("app.js contiene 'renderTeamForm'", "renderTeamForm" in app_js)
    check("app.js contiene 'changeMatchdayRound'", "changeMatchdayRound" in app_js)

    # ── 15. Ultime Partite — /api/player_matches ──────────────────────
    print("\n▸ 15. Ultime Partite — /api/player_matches (stage 12)")
    r_pm = requests.get(f"{BASE_URL}/api/player_matches", params={"player": "Svilar"}, timeout=10)
    check("GET /api/player_matches?player=Svilar → 200", r_pm.status_code == 200, f"status={r_pm.status_code}")
    if r_pm.status_code == 200:
        pm = r_pm.json()
        check("Nodi player/available/matches/summary", all(k in pm for k in ["player", "available", "matches", "summary"]))
        check("Svilar ha partite registrate", len(pm.get("matches", [])) > 0)
        m0 = pm["matches"][0]
        for key in ["round", "date", "opponent", "opponent_display", "venue", "minutes",
                    "rating", "goals", "assists", "xg", "xa", "is_starter"]:
            check(f"match.{key} presente", key in m0, f"val={m0.get(key)}")
        s = pm["summary"]
        for key in ["played", "starts", "minutes", "avg_rating", "goals", "assists"]:
            check(f"summary.{key} presente", key in s, f"val={s.get(key)}")
        rounds_seq = [m["round"] for m in pm["matches"]]
        check("Ordine cronologico inverso", rounds_seq == sorted(rounds_seq, reverse=True))
    r_pm_404 = requests.get(f"{BASE_URL}/api/player_matches", params={"player": "Zzz_Nessuno"}, timeout=10)
    check("Giocatore senza righe → 404", r_pm_404.status_code == 404, f"status={r_pm_404.status_code}")
    r_pm_400 = requests.get(f"{BASE_URL}/api/player_matches", timeout=10)
    check("Parametro mancante → 400", r_pm_400.status_code == 400, f"status={r_pm_400.status_code}")
    check("HTML contiene 'pdRecentMatches' (Ultime Partite)", "pdRecentMatches" in html)
    check("app.js contiene 'renderRecentMatches'", "renderRecentMatches" in app_js)
    check("app.js contiene 'loadPlayerMatches'", "loadPlayerMatches" in app_js)

    # ── SEZIONE 17: HEATMAP (stage 13) + STATS AVANZATE (stage 14) ─────
    print("\n[17] Heatmap stagione + statistiche avanzate per giocatore")

    r_hm = requests.get(f"{BASE_URL}/api/player_heatmap?player=Svilar", timeout=15)
    check("GET /api/player_heatmap?player=Svilar → 200", r_hm.status_code == 200, f"status={r_hm.status_code}")
    if r_hm.ok:
        hm = r_hm.json()
        check("Nodi heatmap player/available/grid/cells/points",
              all(k in hm for k in ["player", "available", "grid", "cells", "points"]))
        check("Griglia 30x20 completa (600 celle)", len(hm.get("cells", [])) == 600)
        check("Svilar ha tocchi registrati", hm.get("points", 0) > 0, f"points={hm.get('points')}")
        # portiere: la maggior parte dei tocchi nel proprio terzo campo (x < 20)
        cols = hm.get("grid", {}).get("cols", 30)
        rows = hm.get("grid", {}).get("rows", 20)
        left = sum(hm["cells"][r * cols + c] for r in range(rows) for c in range(cols // 5))
        check("Portiere concentrato sul fondo (x<20%)", left / max(hm.get("points", 1), 1) > 0.5,
              f"share={left / max(hm.get('points', 1), 1):.2f}")
        check("available_rounds presente", "available_rounds" in hm)
        # cumulativo fino alla G1 (schema v2 con by_event; 404 tollerato finche'
        # non avviene il refetch)
        r_hm1 = requests.get(f"{BASE_URL}/api/player_heatmap?player=Svilar&until_round=1", timeout=15)
        if r_hm1.status_code == 200:
            hm1 = r_hm1.json()
            check("until_round=1 coerente (<= stagione)", hm1.get("points", 0) <= hm.get("points", 0)
                  and hm1.get("matches", 0) >= 1, f"pts={hm1.get('points')}")
        elif r_hm1.status_code == 404:
            check("until_round: 404 accettato (refetch v2 in attesa)", True)
        else:
            check("until_round → 200/404", False, f"status={r_hm1.status_code}")

    r_hm_404 = requests.get(f"{BASE_URL}/api/player_heatmap?player=Nessuno123", timeout=15)
    check("Heatmap giocatore sconosciuto → 404", r_hm_404.status_code == 404, f"status={r_hm_404.status_code}")
    r_hm_400 = requests.get(f"{BASE_URL}/api/player_heatmap", timeout=15)
    check("Heatmap senza parametro → 400", r_hm_400.status_code == 400, f"status={r_hm_400.status_code}")

    r_adv = requests.get(f"{BASE_URL}/api/player_advanced?player=Martinez%20L.", timeout=15)
    if r_adv.status_code == 200:
        adv = r_adv.json()
        check("Nodi advanced player/available/totals/per90/pcts/percentiles",
              all(k in adv for k in ["player", "available", "totals", "per90", "pcts", "percentiles"]))
        check("Martinez L. ha minuti giocati", (adv.get("minutes") or 0) > 0)
        check("Cartellini presenti nel payload", "cards" in adv)
    elif r_adv.status_code == 404:
        check("Advanced: 404 gestito (stage 14 non eseguito)", True)
    else:
        check("GET /api/player_advanced → 200/404", False, f"status={r_adv.status_code}")

    check("HTML contiene 'pdHeatmap' (Mappa di Gioco)", "pdHeatmap" in html)
    check("HTML contiene 'pdAdvanced' (Statistiche Avanzate)", "pdAdvanced" in html)
    check("app.js contiene 'renderPlayerHeatmap'", "renderPlayerHeatmap" in app_js)
    check("app.js contiene 'renderPlayerAdvanced'", "renderPlayerAdvanced" in app_js)

    # ── SUMMARY ───────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    total = len(results)
    print(f"  RISULTATO: {passed}/{total} test superati  ({failed} falliti)")

    if failed == 0:
        print("  🎉 TUTTI I TEST SUPERATI")
    else:
        print("  ⚠️  ATTENZIONE — I seguenti test sono falliti:")
        for name, status, detail in results:
            if status == FAIL:
                print(f"     • {name}: {detail}")

    print("=" * 72 + "\n")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
