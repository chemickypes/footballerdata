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

BASE_URL = "http://localhost:5050"
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
    print("\n▸ 9. Entity-First Copilot Retrieval — Thuram & Woltemade")
    r_copilot_comp = requests.post(f"{BASE_URL}/api/ai_query", json={"prompt": "parlami di thuram e woltemade"}, timeout=35)
    check("POST /api/ai_query comparison → 200", r_copilot_comp.status_code == 200)
    comp_json = r_copilot_comp.json()
    check("Risposta confronto non vuota", bool(comp_json))
    comp_players = [p.get("name", "").lower() for p in comp_json.get("players", [])]
    check("Confronto contiene 'thuram'", any("thuram" in p for p in comp_players) or "thuram" in str(comp_json).lower())
    check("Confronto contiene 'woltemade'", any("woltemade" in p for p in comp_players) or "woltemade" in str(comp_json).lower())

    r_copilot_single = requests.post(f"{BASE_URL}/api/ai_query", json={"prompt": "chi è woltemade?"}, timeout=35)
    check("POST /api/ai_query single player → 200", r_copilot_single.status_code == 200)
    single_json = r_copilot_single.json()
    check("Single player Woltemade riconosciuto", "woltemade" in str(single_json).lower())

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
