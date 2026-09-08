"""
footballerdata — AI copilot endpoints
/api/ai_status, /api/ai_test: copilot diagnostics.
/api/ai_query: player Q&A — LLM copilot first (Ollama/OpenAI/Gemini),
then a zero-dependency local quantitative reasoner.
"""

import re
from flask import Blueprint, jsonify, request

from web.config import DEFAULT_BUDGET, DEFAULT_ROSTER_SLOTS, DEFAULT_N_TEAMS, IS_PERSONAL
from web.data import load_dataset
from web.pricing import get_dynamic_fair_prices

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/api/ai_status", methods=["GET"])
def api_ai_status():
    """Returns AI Copilot diagnostic status and active engine."""
    try:
        from core.copilot import get_copilot_diagnostics
        diag = get_copilot_diagnostics()
        return jsonify(diag)
    except Exception as e:
        return jsonify({"error": str(e), "has_llm": False, "active_engine": "Fallback Matematico Offline"})


@ai_bp.route("/api/ai_test", methods=["GET", "POST"])
def api_ai_test():
    """Live diagnostic ping to each configured AI provider with HTTP status codes."""
    try:
        from core.copilot import test_all_providers
        return jsonify(test_all_providers())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@ai_bp.route("/api/ai_query", methods=["POST"])
def api_ai_query():
    """
    Analista AI — Player Q&A Engine
    Priorità: Ollama locale -> OpenAI-compatible -> Google Gemini -> Local Quantitative Reasoner.
    """
    data = request.json or {}
    prompt = str(data.get("prompt", "")).strip()

    if not prompt:
        return jsonify({"error": "Prompt vuoto"}), 400

    df = load_dataset()

    prompt_lower = prompt.lower()

    # ─────────────────────────────────────────────────────────────
    # ENTITY EXTRACTION & QUERY NORMALIZATION
    # ─────────────────────────────────────────────────────────────
    aliases = {
        'lautaro': 'martinez l.',
        'lautaro martinez': 'martinez l.',
        'kvara': 'kvaratskhelia',
        'calha': 'calhanoglu',
        'chalanoglu': 'calhanoglu',
        'dimash': 'dimarco',
        'douglas': 'douglas luiz',
        'thuram': 'thuram',
        'woltemade': 'woltemade',
    }
    expanded_prompt = prompt_lower
    for k_alias, v_target in aliases.items():
        if k_alias in expanded_prompt and v_target not in expanded_prompt:
            expanded_prompt += f" {v_target}"

    def player_matches_query(p_name_str, query_str):
        p_clean = str(p_name_str).lower().strip()
        if p_clean in query_str:
            return True
        tokens = [t for t in re.split(r'[\s\.\-]+', p_clean) if len(t) >= 3]
        for tok in tokens:
            if re.search(rf'\b{re.escape(tok)}\b', query_str):
                return True
        return False

    explicit_matches = []
    seen_explicit = set()
    for _, row in df.iterrows():
        p_name = row['player']
        if player_matches_query(p_name, expanded_prompt) and p_name not in seen_explicit:
            seen_explicit.add(p_name)
            explicit_matches.append(row)

    # ─────────────────────────────────────────────────────────────
    # 1. MODULAR COPILOT INTEGRATION (Ollama / OpenAI / Gemini)
    # ─────────────────────────────────────────────────────────────
    try:
        from core.copilot import get_copilot_response
        budget_total = DEFAULT_BUDGET
        roster_structure = DEFAULT_ROSTER_SLOTS
        n_teams = DEFAULT_N_TEAMS

        pricing_data = get_dynamic_fair_prices(df, budget_total, roster_structure, n_teams)
        custom_fair_prices = pricing_data["fair_prices"]
        custom_vorp = pricing_data["vorp"]

        pool_df = df.copy()
        pool_df['fair_custom'] = pool_df['player'].map(custom_fair_prices).fillna(1).astype(int)
        pool_df['vorp_custom'] = pool_df['player'].map(custom_vorp).fillna(0.0).astype(float)

        sample_df = pool_df.copy()

        role_map_kw = {'portier': 'P', 'difensor': 'D', 'centrocampist': 'C', 'attaccant': 'A'}
        for r_key, r_code in role_map_kw.items():
            if r_key in prompt_lower:
                sample_df = sample_df[sample_df['role'] == r_code]
                break

        team_kw = {
            'como': 'COM', 'milan': 'MIL', 'juve': 'JUV', 'juventus': 'JUV',
            'inter': 'INT', 'roma': 'ROM', 'lazio': 'LAZ', 'atalanta': 'ATA',
            'napoli': 'NAP', 'bologna': 'BOL', 'fiorentina': 'FIO', 'torino': 'TOR',
            'genoa': 'GEN', 'lecce': 'LEC', 'udinese': 'UDI', 'parma': 'PAR',
            'sassuolo': 'SAS', 'monza': 'MON', 'venezia': 'VEN', 'cagliari': 'CAG'
        }
        for t_k, t_c in team_kw.items():
            if re.search(rf'\b{re.escape(t_k)}\b', prompt_lower):
                sample_df = sample_df[sample_df['team'] == t_c]
                break

        is_low_cost = any(term in prompt_lower for term in ["a 1", "1 credito", "1 cr", "low cost", "scommess", "economici", "risparmi", "prezzo basso", "meno di 5", "sotto i 5"])
        low_cost_threshold = max(3, int(budget_total * 0.02))
        if is_low_cost:
            sample_df = sample_df[sample_df['fair_custom'] <= low_cost_threshold].sort_values(
                ['is_starter_2627', 'predicted_contrib_p50', 'vorp_custom'], ascending=[False, False, False]
            )
        else:
            sample_df = sample_df.sort_values(['is_starter_2627', 'vorp_custom'], ascending=[False, False])

        if sample_df.empty:
            sample_df = pool_df.sort_values('vorp_custom', ascending=False)

        explicit_sample = []
        for row in explicit_matches:
            p_name = row['player']
            p_fair = int(custom_fair_prices.get(p_name, row.get('prezzo_fair_1000', 1)))
            p_vorp = float(custom_vorp.get(p_name, row.get('vorp_points', 0.0)))
            explicit_sample.append({
                'player': p_name,
                'role': row['role'],
                'team': row['team'],
                'predicted_contrib_p50': float(row.get('predicted_contrib_p50', 0)),
                'prezzo_fair_1000': p_fair,
                'vorp_points': p_vorp,
                'is_starter_2627': bool(row.get('is_starter_2627', False))
            })

        sample_unmentioned = sample_df[~sample_df['player'].isin(seen_explicit)]
        remaining_slots = max(0, 35 - len(explicit_sample))
        other_sample = sample_unmentioned.head(remaining_slots)[['player', 'role', 'team', 'predicted_contrib_p50', 'fair_custom', 'vorp_custom', 'is_starter_2627']].rename(
            columns={'fair_custom': 'prezzo_fair_1000', 'vorp_custom': 'vorp_points'}
        ).to_dict(orient='records')

        top_sample = explicit_sample + other_sample

        llm_reply = get_copilot_response(
            prompt, {}, top_sample,
            budget_total=DEFAULT_BUDGET,
            is_personal=IS_PERSONAL
        )
        if llm_reply:
            return jsonify(llm_reply)
    except Exception as e:
        print(f"Copilot exception: {e}")

    # ─────────────────────────────────────────────────────────────
    # 2. LOCAL QUANTITATIVE REASONING ENGINE (Zero Latency & 0 Cost)
    # ─────────────────────────────────────────────────────────────

    # B. Multi-Player Comparison (2 or more players, explicit or comparison query)
    is_comp = any(w in prompt_lower for w in ["vs", "contro", "confront", "meglio tra", "differenza tra", "chi tra", "chi prendere tra"]) or len(explicit_matches) >= 2
    if is_comp and len(explicit_matches) >= 2:
        matched_players = list(explicit_matches[:3])
        matched_players.sort(key=lambda r: float(r.get('vorp_points', 0)), reverse=True)
        winner = matched_players[0]

        p_list = []
        for r in matched_players:
            p_list.append({
                "name": r['player'], "team": r['team'], "role": r['role'],
                "contrib_exp": float(r.get('predicted_contrib_p50', 0)),
                "fair_1000": int(r.get('prezzo_fair_1000', 1)),
                "vorp": float(r.get('vorp_points', 0)),
                "starts": int(r.get('starts_2627', 0)),
                "injury_days": int(r.get('giorni_infortunio_3y', 0))
            })

        return jsonify({
            "type": "comparison",
            "title": f"Confronto: {' vs '.join([p['name'] for p in p_list])}",
            "engine": "Regole Tattiche Locali (Offline)",
            "players": p_list,
            "winner": winner['player'],
            "verdict": f"Scelta Consigliata: **{winner['player']}** è il profilo con efficienza superiore (+{winner.get('vorp_points', 0):.1f} VORP, {winner.get('predicted_contrib_p50', 0):.1f} punti-rating attesi, Prezzo Fair: {int(winner.get('prezzo_fair_1000', 1))} cr)."
        })

    # C. Specific Player Analysis
    target_matches = explicit_matches if explicit_matches else [row for _, row in df.iterrows() if player_matches_query(row['player'], expanded_prompt)]
    if target_matches:
        row = target_matches[0]
        starter_txt = "Titolare confermato 2026/27" if row.get('is_starter_2627') else "Rotazione / Non ancora titolare fisso"
        return jsonify({
            "type": "player_deepdive",
            "title": f"Scheda Analitica: {row['player']} ({row['team']})",
            "engine": "Regole Tattiche Locali (Offline)",
            "player": {
                "name": row['player'],
                "team": row['team'],
                "role": row['role'],
                "role_mantra": str(row.get('role_mantra', '')),
                "contrib_exp": float(row.get('predicted_contrib_p50', 0)),
                "contrib_floor": float(row.get('predicted_contrib_p10', 0)),
                "contrib_ceil": float(row.get('predicted_contrib_p90', 0)),
                "fair_1000": int(row.get('prezzo_fair_1000', 1)),
                "surplus": int(row.get('surplus_value_cr', 0)),
                "vorp": float(row.get('vorp_points', 0)),
                "starts": int(row.get('starts_2627', 0)),
                "minutes": int(row.get('minutes_2627', 0)),
                "injury_days": int(row.get('giorni_infortunio_3y', 0))
            },
            "verdict": f"Valutazione Modello: Prezzo fair stimato a 1000cr: **{row.get('prezzo_fair_1000', 1)} cr**. {starter_txt} con proiezione P50 di **{row.get('predicted_contrib_p50', 0):.1f} punti-rating attesi (pg×MV)** e VORP **+{row.get('vorp_points', 0):.1f}**."
        })

    # D. Recommendations by Role, Team, Budget, or Modificatore
    role_map = {'portier': 'P', 'difensor': 'D', 'centrocampist': 'C', 'attaccant': 'A'}
    target_role = None
    for k, v in role_map.items():
        if k in prompt_lower:
            target_role = v
            break

    team_map = {
        'como': 'COM', 'milan': 'MIL', 'juve': 'JUV', 'juventus': 'JUV',
        'inter': 'INT', 'roma': 'ROM', 'lazio': 'LAZ', 'atalanta': 'ATA',
        'napoli': 'NAP', 'bologna': 'BOL', 'fiorentina': 'FIO', 'torino': 'TOR',
        'genoa': 'GEN', 'lecce': 'LEC', 'udinese': 'UDI', 'parma': 'PAR',
        'sassuolo': 'SAS', 'monza': 'MON', 'venezia': 'VEN', 'frosinone': 'FRO',
        'cagliari': 'CAG'
    }
    target_team = None
    for k_team, v_code in team_map.items():
        if re.search(rf'\b{re.escape(k_team)}\b', prompt_lower):
            target_team = v_code
            break

    budget_match = re.search(r'(?:sotto|meno di|max|entro|budget|fino a)\s*(\d+)', prompt_lower)
    max_budget = int(budget_match.group(1)) if budget_match else None

    filtered = df.copy()

    if target_team:
        filtered = filtered[filtered['team'] == target_team]
    if target_role:
        filtered = filtered[filtered['role'] == target_role]
    if max_budget:
        filtered = filtered[filtered['prezzo_fair_1000'] <= max_budget]

    if 'modificatore' in prompt_lower or 'difesa' in prompt_lower:
        filtered = filtered[filtered['role'] == 'D'].sort_values(['is_starter_2627', 'predicted_contrib_p50'], ascending=[False, False])
    elif 'scommess' in prompt_lower or 'low cost' in prompt_lower or '1 credito' in prompt_lower:
        filtered = filtered[filtered['prezzo_fair_1000'] <= 5].sort_values(['is_starter_2627', 'predicted_contrib_p50'], ascending=[False, False])
    else:
        filtered = filtered.sort_values(['is_starter_2627', 'vorp_points'], ascending=[False, False])

    top_matches = filtered.head(5)
    records = []
    for _, r in top_matches.iterrows():
        records.append({
            "name": r['player'],
            "team": r['team'],
            "role": r['role'],
            "contrib_exp": float(r.get('predicted_contrib_p50', 0)),
            "fair_1000": int(r.get('prezzo_fair_1000', 1)),
            "vorp": float(r.get('vorp_points', 0)),
            "starts": int(r.get('starts_2627', 0))
        })

    role_desc = {"P": "Portieri", "D": "Difensori", "C": "Centrocampisti", "A": "Attaccanti"}.get(target_role, "Calciatori")
    team_desc = f" ({target_team})" if target_team else ""
    budget_desc = f" entro {max_budget} cr" if max_budget else ""

    return jsonify({
        "type": "recommendations",
        "title": f"Migliori Opportunità Disponibili: {role_desc}{team_desc}{budget_desc}",
        "engine": "Regole Tattiche Locali (Offline)",
        "players": records,
        "verdict": "Consiglio Tattico: I profili selezionati offrono il miglior compromesso tra titolarità confermata e surplus di valore VORP."
    })
