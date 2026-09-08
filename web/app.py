#!/usr/bin/env python3
"""
footballerdata — Player Data & Statistics Explorer (Serie A)
Web UI: player list (listone) with filters/sort, Player Detail Drawer, AI copilot Q&A.
Fork of La FantaOfficina; the fantasy auction/league/team engine has been removed.
"""

import os
import sys
import json
import re
import pandas as pd
from flask import Flask, jsonify, request, render_template_string, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # web/ — used for static serving only
PROJECT_ROOT = os.path.dirname(BASE_DIR)  # repo root — used for data/config/env paths
sys.path.insert(0, PROJECT_ROOT)

DATA_PATH = os.path.join(PROJECT_ROOT, "data", "dataset_finale.csv")
if not os.path.exists(DATA_PATH):
    DATA_PATH = os.path.join(PROJECT_ROOT, "dataset_finale.csv")
if not os.path.exists(DATA_PATH):
    DATA_PATH = os.path.join(PROJECT_ROOT, "examples", "dataset_sample.csv")

# ──────────────────────────────────────────────────────────────────────
# ENVIRONMENT
# ──────────────────────────────────────────────────────────────────────
APP_ENV = os.environ.get("APP_ENV", "community").strip().lower()

# Load Transfermarkt injuries cache for Clinical Audit Window
_INJURIES_CACHE = {}
_inj_path = os.path.join(PROJECT_ROOT, "data", "tm_injuries_cache.json")
if not os.path.exists(_inj_path):
    _inj_path = os.path.join(PROJECT_ROOT, "tm_injuries_cache.json")
if os.path.exists(_inj_path):
    try:
        with open(_inj_path, "r", encoding="utf-8") as f:
            _INJURIES_CACHE = json.load(f)
    except Exception:
        pass

# Load local .env if present
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
if os.path.exists(ENV_PATH):
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────────────
# FIXED PRICING DEFAULTS
# Used only to calibrate VORP baselines / fair-price quality scores.
# ──────────────────────────────────────────────────────────────────────

DEFAULT_BUDGET = 1000
DEFAULT_ROSTER_SLOTS = {"P": 3, "D": 8, "C": 8, "A": 6}
DEFAULT_N_TEAMS = 10

_personal_config_path = os.path.join(PROJECT_ROOT, "core", "config.personal.py")
IS_PERSONAL = (APP_ENV == "personal")

# ──────────────────────────────────────────────────────────────────────
# BOT IDENTITY & PERSONA
# ──────────────────────────────────────────────────────────────────────
BOT_NAME = "Il Maestro"
BOT_SUBTITLE = "Assistente Tattico Quantitativo"
BOT_AVATAR_TEXT = "AI"
BOT_BADGE = "PRO DECISION"
BOT_GREETING = (
    "Ciao! Sono l'assistente quantitativo de **La FantaOfficina**. Chiedimi confronti (es. *Malen vs Lautaro*), "
    "analisi di reparto o raccomandazioni basate su VORP e proiezioni ML."
)
BOT_AVATAR_IMAGE = ""

if IS_PERSONAL and os.path.exists(_personal_config_path):
    try:
        import importlib.util
        _spec = importlib.util.spec_from_file_location("config_personal", _personal_config_path)
        _personal = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_personal)
        BOT_NAME = getattr(_personal, "BOT_NAME", BOT_NAME)
        BOT_SUBTITLE = getattr(_personal, "BOT_SUBTITLE", BOT_SUBTITLE)
        BOT_AVATAR_TEXT = getattr(_personal, "BOT_AVATAR_TEXT", BOT_AVATAR_TEXT)
        BOT_BADGE = getattr(_personal, "BOT_BADGE", BOT_BADGE)
        BOT_GREETING = getattr(_personal, "BOT_GREETING", BOT_GREETING)
    except Exception:
        pass

if IS_PERSONAL:
    _local_avatar_path = os.path.join(BASE_DIR, "static", "personal_avatar.jpg")
    if os.path.exists(_local_avatar_path):
        try:
            import base64
            with open(_local_avatar_path, "rb") as f:
                BOT_AVATAR_IMAGE = "data:image/jpeg;base64," + base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            pass

BOT_NAME = os.environ.get("BOT_NAME", BOT_NAME)
BOT_SUBTITLE = os.environ.get("BOT_SUBTITLE", BOT_SUBTITLE)
BOT_AVATAR_TEXT = os.environ.get("BOT_AVATAR_TEXT", BOT_AVATAR_TEXT)
BOT_BADGE = os.environ.get("BOT_BADGE", BOT_BADGE)
BOT_GREETING = os.environ.get("BOT_GREETING", BOT_GREETING)
BOT_AVATAR_IMAGE = os.environ.get("BOT_AVATAR_URL", BOT_AVATAR_IMAGE)

app = Flask(__name__)


@app.after_request
def add_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def load_dataset():
    """Loads player dataset and assigns market value tiers (Fasce 1-4) per macro-role using domain-calibrated fair prices."""
    df = pd.read_csv(DATA_PATH)

    df["fascia"] = 4
    for role in ["P", "D", "C", "A"]:
        mask = df["role"] == role
        if not mask.any():
            continue
        if role == "P":
            # Domain-calibrated tiers for goalkeepers (reflecting true starter vs backup value):
            # F1: Top big clubs (>= 50 cr): Svilar, Vicario, Martinez, Carnesecchi, Maignan, Butez, Meret
            # F2: Semitop / Solid starters (20-49 cr): Mandas, Skorupski, De Gea, Okoye, Falcone, Perri, Sanchez, Caprile
            # F3: Low-cost starters / Battles (6-19 cr): Muric, Bijlow, Palmisani, Stankovic, Tornqvist, Corvi, Daffara
            # F4: Backups & 1-credit reserves (<= 5 cr)
            prices = df.loc[mask, "prezzo_fair_1000"].fillna(1)
            df.loc[mask & (prices >= 50), "fascia"] = 1
            df.loc[mask & (prices >= 20) & (prices < 50), "fascia"] = 2
            df.loc[mask & (prices >= 6) & (prices < 20), "fascia"] = 3
            df.loc[mask & (prices < 6), "fascia"] = 4
        else:
            # For outfielders, use fair auction price quantiles
            prices = df.loc[mask, "prezzo_fair_1000"].fillna(1)
            q1 = prices.quantile(0.85)
            q2 = prices.quantile(0.55)
            q3 = prices.quantile(0.20)
            df.loc[mask & (prices >= q1), "fascia"] = 1
            df.loc[mask & (prices < q1) & (prices >= q2), "fascia"] = 2
            df.loc[mask & (prices < q2) & (prices >= q3), "fascia"] = 3
            df.loc[mask & (prices < q3), "fascia"] = 4

    return df


_PRICING_CACHE = {}


def get_dynamic_fair_prices(df, budget_total, roster_slots, n_teams):
    """
    Computes custom fair prices and VORP baselines calibrated specifically to:
      - custom budget (e.g. 300, 500, 1000)
      - custom roster slots (e.g. 3-10-10-6, 4-9-9-7)
      - custom number of teams (e.g. 8, 10, 12)
    Uses empirical budget shares, power-law scarcity exponents and replacement-level analysis.
    Results are cached in memory for high-performance response times.
    """
    cache_key = (int(budget_total), tuple(sorted(roster_slots.items())), int(n_teams))
    if cache_key in _PRICING_CACHE:
        return _PRICING_CACHE[cache_key]

    budget_shares = {"P": 0.09, "D": 0.18, "C": 0.33, "A": 0.40}
    scarcity_exp = {"P": 1.20, "D": 1.05, "C": 1.16, "A": 1.02}

    # 1. Positional replacement baselines
    baselines = {}
    for role, slots in roster_slots.items():
        total_drafted = n_teams * slots
        role_df = df[df["role"] == role].sort_values("predicted_pts_p50", ascending=False).reset_index(drop=True)
        if len(role_df) > total_drafted:
            base = role_df.iloc[total_drafted]["predicted_pts_p50"]
        elif len(role_df) > 0:
            base = role_df.iloc[-1]["predicted_pts_p50"] * 0.70
        else:
            base = 50.0
        baselines[role] = float(base)

    if "adj_market_fvm" in df.columns:
        adj_fvm_series = df["adj_market_fvm"].astype(float)
    else:
        adj_fvm_series = df.get("FVM_1000", df.get("prezzo_fair_1000", 10.0)).astype(float)

    fair_prices = {}
    vorp_dict = {}

    for role in ["P", "D", "C", "A"]:
        role_mask = df["role"] == role
        role_df = df[role_mask]
        gamma = scarcity_exp.get(role, 1.10)

        role_fvm_sub = adj_fvm_series[role_mask]
        role_fvm_powered = float((role_fvm_sub ** gamma).sum())

        role_slots = roster_slots.get(role, 8)
        role_total_budget = n_teams * (budget_total * budget_shares.get(role, 0.25))
        role_reserve_pool = n_teams * role_slots * 1  # 1 credit minimum reserve per slot
        role_surplus_pool = max(0.0, role_total_budget - role_reserve_pool)

        role_base = baselines.get(role, 100.0)

        for idx, row in role_df.iterrows():
            p_name = row["player"]
            pts = float(row.get("predicted_pts_p50", 150.0))
            vorp = max(0.0, pts - role_base)
            vorp_dict[p_name] = round(vorp, 1)

            fvm_val = float(adj_fvm_series[idx]) if idx in adj_fvm_series.index else 10.0
            if role_fvm_powered > 0 and fvm_val > 0:
                price = 1.0 + (role_surplus_pool / n_teams) * ((fvm_val ** gamma) / role_fvm_powered * n_teams)
            else:
                price = 1.0
            fair_prices[p_name] = max(1, int(round(price)))

    result = {
        "fair_prices": fair_prices,
        "vorp": vorp_dict,
        "baselines": baselines
    }
    _PRICING_CACHE[cache_key] = result
    return result


# ──────────────────────────────────────────────────────────────────────
# REST API ENDPOINTS
# ──────────────────────────────────────────────────────────────────────

@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory(os.path.join(BASE_DIR, "static"), path)



@app.route("/api/players")
def api_players():
    df = load_dataset()

    budget_arg = request.args.get("budget", type=int)
    budget_total = budget_arg if (budget_arg and budget_arg > 0) else DEFAULT_BUDGET
    roster_structure = DEFAULT_ROSTER_SLOTS
    n_teams = DEFAULT_N_TEAMS

    pricing_data = get_dynamic_fair_prices(df, budget_total, roster_structure, n_teams)
    custom_fair_prices = pricing_data["fair_prices"]
    custom_vorp = pricing_data["vorp"]

    budget_scale = budget_total / 1000.0

    role_filter = request.args.get("role")
    fascia_filter = request.args.get("fascia")
    search = request.args.get("q", "").strip().lower()

    records = []
    for _, row in df.iterrows():
        p_name = row["player"]

        if role_filter and role_filter != "ALL" and row["role"] != role_filter:
            continue
        if fascia_filter and fascia_filter != "ALL" and str(row["fascia"]) != str(fascia_filter):
            continue
        if search and search not in p_name.lower() and search not in str(row.get("team", "")).lower():
            continue

        fair_1000 = int(row.get("prezzo_fair_1000", 1))
        fair_500 = int(row.get("prezzo_fair_500", max(1, round(fair_1000 * 0.5))))
        if budget_total == 500 and "prezzo_fair_500" in row and pd.notna(row.get("prezzo_fair_500")):
            base_fair = fair_500
        else:
            base_fair = custom_fair_prices.get(p_name, max(1, int(round(fair_1000 * budget_scale))))
        fair_scaled = base_fair
        vorp_val = custom_vorp.get(p_name, float(row.get("vorp_points", 0)))

        # Medical & Physical Fragility Audit (Transfermarkt)
        inj_info = _INJURIES_CACHE.get(p_name, {})
        days_lost = int(row.get("giorni_infortunio_3y", 0)) if pd.notna(row.get("giorni_infortunio_3y")) else inj_info.get("giorni_infortunio_3y", 0)
        inj_count = int(row.get("n_infortuni_3y", 0)) if pd.notna(row.get("n_infortuni_3y")) else inj_info.get("n_infortuni_3y", 0)
        severe_inj = bool(row.get("infortunio_grave", 0)) if pd.notna(row.get("infortunio_grave")) else bool(inj_info.get("infortunio_grave", 0))
        recent_injuries = inj_info.get("dettaglio_infortuni", [])

        if days_lost < 15 and not severe_inj:
            med_status = "safe"
            med_label = "Affidabile"
            med_badge = '<i class="fa-solid fa-circle-check" style="color:#10b981;"></i>'
        elif days_lost <= 60 and not severe_inj:
            med_status = "warning"
            med_label = "Da Monitorare"
            med_badge = '<i class="fa-solid fa-triangle-exclamation" style="color:#f59e0b;"></i>'
        else:
            med_status = "danger"
            med_label = "Fragile / Alto Rischio"
            med_badge = '<i class="fa-solid fa-circle-exclamation" style="color:#ef4444;"></i>'

        # Understat Offensive Metrics
        xg_p90 = round(float(row.get("xg_per90", 0)), 3) if pd.notna(row.get("xg_per90")) else 0.0
        npxg_p90 = round(float(row.get("npxg_per90", 0)), 3) if pd.notna(row.get("npxg_per90")) else 0.0
        xa_p90 = round(float(row.get("xa_per90", 0)), 3) if pd.notna(row.get("xa_per90")) else 0.0
        shots_p90 = round(float(row.get("shots_per90", 0)), 2) if pd.notna(row.get("shots_per90")) else 0.0

        # Delta Realizzativo (Goals vs xG)
        gol_rate = float(row.get("gol_per_pg", 0)) if pd.notna(row.get("gol_per_pg")) else 0.0
        xg_avg = float(row.get("xg_media_3y", 0)) if pd.notna(row.get("xg_media_3y")) else 0.0
        delta_goals_xg = round((gol_rate * 30.0) - xg_avg, 2) if (gol_rate > 0 or xg_avg > 0) else 0.0

        # Quantiles & Volatility (Gradient Boosting)
        p10 = float(row.get("predicted_pts_p10", 0)) if pd.notna(row.get("predicted_pts_p10")) else 0.0
        p50 = float(row.get("predicted_pts_p50", 0)) if pd.notna(row.get("predicted_pts_p50")) else 0.0
        p90 = float(row.get("predicted_pts_p90", 0)) if pd.notna(row.get("predicted_pts_p90")) else 0.0
        spread = float(row.get("pts_volatility_spread", 0)) if pd.notna(row.get("pts_volatility_spread")) else round(p90 - p10, 1)

        # Media Voto & FantaMedia
        mv_val = round(float(row.get("mv_media_3y", 6.0)), 2) if pd.notna(row.get("mv_media_3y")) and float(row.get("mv_media_3y", 0)) > 0 else 6.0
        mfv_val = round(float(row.get("mfv_media_3y", 6.0)), 2) if pd.notna(row.get("mfv_media_3y")) and float(row.get("mfv_media_3y", 0)) > 0 else 6.0

        # Estimated appearances (partite a voto stimate)
        expected_matches = min(38, max(5, int(round(p50 / max(4.5, mfv_val))))) if mfv_val > 0 else 28

        # Bonus / Malus Range estimation (standard 28 gare baseline)
        if row["role"] == "P":
            diff = round(mv_val - mfv_val, 2)
            malus_gs = int(round(diff * 28.0)) if diff > 0 else 0
            bonus_range = f"Malus ~{malus_gs} gol subiti (28g)" if malus_gs > 0 else "Porta imbattuta frequente"
        else:
            ass_rate = float(row.get("ass_per_pg", 0)) if pd.notna(row.get("ass_per_pg")) else 0.0
            gol_proj = round(gol_rate * 28.0, 1)
            ass_proj = round(ass_rate * 28.0, 1)
            bonus_pts_proj = gol_rate * 28.0 * 3.0 + ass_rate * 28.0 * 1.0
            b_min = max(0, int(round(bonus_pts_proj * 0.8)))
            b_max = max(1 if bonus_pts_proj > 0.5 else 0, int(round(bonus_pts_proj * 1.25 + 0.4)))
            if b_max == 0:
                bonus_range = "Bonus raro (+0 pt)"
            else:
                bonus_range = f"+{b_min}/+{b_max} pt (~{gol_proj:.0f}G, {ass_proj:.0f}A su 28g)"

        records.append({
            "player": p_name,
            "role": row["role"],
            "role_mantra": str(row.get("role_mantra", "")),
            "team": str(row.get("team", "")),
            "price_official": int(row.get("Prezzo_Consigliato_Cr", 1)),
            "price_fair_1000": fair_1000,
            "price_fair_500": fair_500,
            "price_fair_scaled": fair_scaled,
            "_budget_scale": budget_scale,
            "score": float(row.get("score_composito", 0)),
            "surplus_value": int(row.get("surplus_value_cr", 0)),
            "target_price_1000": int(row.get("target_price_1000", fair_1000)),
            "target_price_500": int(row.get("target_price_500", fair_500)),
            "clearing_price_1000": int(row.get("clearing_price_1000", fair_1000)),
            "clearing_price_500": int(row.get("clearing_price_500", fair_500)),
            "target_flags": str(row.get("target_flags", "")),
            "pts_exp": p50,
            "pts_floor": p10,
            "pts_ceil": p90,
            "pts_spread": spread,
            "vorp": vorp_val,
            "mv": mv_val,
            "mfv": mfv_val,
            "expected_matches": expected_matches,
            "bonus_range": bonus_range,
            "injury_days": days_lost,
            "injury_malus": float(row.get("malus_infortuni", 0)),
            "fascia": int(row["fascia"]),
            "is_starter_2627": bool(row.get("is_starter_2627", False)),
            "starts_2627": int(row.get("starts_2627", 0)),
            "minutes_2627": int(row.get("minutes_2627", 0)),
            "xg_3y": float(row.get("xg_media_3y", 0)) if pd.notna(row.get("xg_media_3y")) else None,
            "xa_3y": float(row.get("xa_media_3y", 0)) if pd.notna(row.get("xa_media_3y")) else None,
            "medical": {
                "days_lost_3y": days_lost,
                "injuries_count_3y": inj_count,
                "infortunio_grave": severe_inj,
                "status": med_status,
                "status_label": med_label,
                "status_badge": med_badge,
                "dettaglio_infortuni": recent_injuries
            },
            "understat": {
                "xg_per90": xg_p90,
                "npxg_per90": npxg_p90,
                "xa_per90": xa_p90,
                "shots_per90": shots_p90,
                "delta_goals_xg": delta_goals_xg
            },
            "quantiles": {
                "floor_p10": p10,
                "expected_p50": p50,
                "ceiling_p90": p90,
                "spread": spread,
                "profile_label": "Regolarista da Modificatore" if spread < 135 else "Boom-or-Bust / Alta Volatilità",
                "profile_badge": '<i class="fa-solid fa-shield" style="margin-right:4px;"></i> Regolarista' if spread < 135 else '<i class="fa-solid fa-bolt icon-pulse" style="margin-right:4px;"></i> Boom-or-Bust'
            }
        })

    return jsonify({
        "players": records,
        "total": len(records),
        "budget_scale": budget_scale,
        "league_budget": budget_total,
        "roster_structure": roster_structure,
        "n_teams": n_teams
    })


@app.route("/api/ai_status", methods=["GET"])
def api_ai_status():
    """Returns AI Copilot diagnostic status and active engine."""
    try:
        from core.copilot import get_copilot_diagnostics
        diag = get_copilot_diagnostics()
        return jsonify(diag)
    except Exception as e:
        return jsonify({"error": str(e), "has_llm": False, "active_engine": "Fallback Matematico Offline"})


@app.route("/api/ai_test", methods=["GET", "POST"])
def api_ai_test():
    """Live diagnostic ping to each configured AI provider with HTTP status codes."""
    try:
        from core.copilot import test_all_providers
        return jsonify(test_all_providers())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai_query", methods=["POST"])
def api_ai_query():
    """
    Il Maestro AI — Player Q&A Engine
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
                ['is_starter_2627', 'predicted_pts_p50', 'vorp_custom'], ascending=[False, False, False]
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
                'predicted_pts_p50': float(row.get('predicted_pts_p50', 0)),
                'prezzo_fair_1000': p_fair,
                'vorp_points': p_vorp,
                'is_starter_2627': bool(row.get('is_starter_2627', False))
            })

        sample_unmentioned = sample_df[~sample_df['player'].isin(seen_explicit)]
        remaining_slots = max(0, 35 - len(explicit_sample))
        other_sample = sample_unmentioned.head(remaining_slots)[['player', 'role', 'team', 'predicted_pts_p50', 'fair_custom', 'vorp_custom', 'is_starter_2627']].rename(
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
                "pts_exp": float(r.get('predicted_pts_p50', 0)),
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
            "verdict": f"Scelta Consigliata: **{winner['player']}** è il profilo con efficienza superiore (+{winner.get('vorp_points', 0):.1f} VORP, {winner.get('predicted_pts_p50', 0):.1f} pts attesi, Prezzo Fair: {int(winner.get('prezzo_fair_1000', 1))} cr)."
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
                "pts_exp": float(row.get('predicted_pts_p50', 0)),
                "pts_floor": float(row.get('predicted_pts_p10', 0)),
                "pts_ceil": float(row.get('predicted_pts_p90', 0)),
                "fair_1000": int(row.get('prezzo_fair_1000', 1)),
                "surplus": int(row.get('surplus_value_cr', 0)),
                "vorp": float(row.get('vorp_points', 0)),
                "starts": int(row.get('starts_2627', 0)),
                "minutes": int(row.get('minutes_2627', 0)),
                "injury_days": int(row.get('giorni_infortunio_3y', 0))
            },
            "verdict": f"Valutazione Modello: Prezzo fair stimato a 1000cr: **{row.get('prezzo_fair_1000', 1)} cr**. {starter_txt} con proiezione P50 di **{row.get('predicted_pts_p50', 0):.1f} punti attesi** e VORP **+{row.get('vorp_points', 0):.1f}**."
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
        filtered = filtered[filtered['role'] == 'D'].sort_values(['is_starter_2627', 'predicted_pts_p50'], ascending=[False, False])
    elif 'scommess' in prompt_lower or 'low cost' in prompt_lower or '1 credito' in prompt_lower:
        filtered = filtered[filtered['prezzo_fair_1000'] <= 5].sort_values(['is_starter_2627', 'predicted_pts_p50'], ascending=[False, False])
    else:
        filtered = filtered.sort_values(['is_starter_2627', 'vorp_points'], ascending=[False, False])

    top_matches = filtered.head(5)
    records = []
    for _, r in top_matches.iterrows():
        records.append({
            "name": r['player'],
            "team": r['team'],
            "role": r['role'],
            "pts_exp": float(r.get('predicted_pts_p50', 0)),
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


# ──────────────────────────────────────────────────────────────────────
# FRONTEND TEMPLATE (PROFESSIONAL EXECUTIVE DARK THEME)
# ──────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>footballerdata — Player Data & Statistics Explorer (Serie A)</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="stylesheet" href="/static/css/tutorial.css">
    <style>
        :root {
            --bg: #030408;
            --surface: rgba(12, 15, 25, 0.82);
            --surface-elevated: rgba(24, 28, 44, 0.88);
            --surface-solid: #080a12;
            --border: rgba(255, 45, 117, 0.18);
            --border-glow: rgba(255, 45, 117, 0.55);
            --border-focus: #ff2d75;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #ff2d75;
            --primary-accent: #f43f5e;
            --primary-glow: rgba(255, 45, 117, 0.4);
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --gold: #fbbf24;
            --purple: #a855f7;
            --role-p: #f59e0b;
            --role-d: #10b981;
            --role-c: #38bdf8;
            --role-a: #ff2d75;
            --officina-brass: #c69a4c;
            --officina-brass-dark: #8a6329;
            --officina-gold: #f2c14e;
            --officina-leather: #241a12;
            --officina-leather-2: #2f2216;
            --officina-wood: #1a130d;
            --officina-ink: #ecdfc6;
            --officina-muted: #a68a6a;
            --officina-parchment: #e8d9b5;
            --officina-shadow: rgba(0, 0, 0, 0.62);
            --maestro-z: 1200;
            --davinci-role-p: #d99b34;
            --davinci-role-d: #5c9457;
            --davinci-role-c: #4f89a3;
            --davinci-role-a: #c0533f;
            --davinci-ink: #5a4326;
            --davinci-ink-soft: #6f5233;
            --davinci-hatch: #7a5c38;
            --davinci-parchment-a: #efe2c1;
            --davinci-parchment-b: #e4d2a6;
            --davinci-parchment-c: #c9ac74;
        }

        /* ══════════════════════════════════════════════════════════════════
           ANIMATED ICONS & MICRO-INTERACTIONS
        ══════════════════════════════════════════════════════════════════ */
        @keyframes icon-pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.18); filter: drop-shadow(0 0 8px rgba(255,45,117,0.7)); }
        }
        @keyframes icon-float {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-3px); }
        }
        @keyframes icon-spin-slow {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        @keyframes radar-pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(56, 189, 248, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(56, 189, 248, 0); }
        }
        .icon-pulse { animation: icon-pulse 2s infinite ease-in-out; }
        .icon-float { animation: icon-float 3s infinite ease-in-out; }
        .icon-spin-hover:hover { animation: icon-spin-slow 1.2s linear infinite; }
        .radar-live { animation: radar-pulse 2s infinite cubic-bezier(0, 0, 0.2, 1); }

        .nav-item i {
            font-size: 1.22rem;
            margin-bottom: 2px;
            transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
        .nav-item:active i {
            transform: scale(0.85);
        }
        .nav-item.active i {
            transform: translateY(-2px) scale(1.18);
            filter: drop-shadow(0 0 8px rgba(255, 45, 117, 0.8));
            color: var(--primary) !important;
        }

        /* Subview Segmented Controller (Inside Targets Tab) */
        .target-subview-toggle-bar {
            display: flex;
            background: #080d1a;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 4px;
            gap: 4px;
            margin-bottom: 14px;
        }
        .target-subview-btn {
            flex: 1;
            padding: 9px 12px;
            border-radius: 8px;
            border: none;
            background: transparent;
            color: var(--text-muted);
            font-size: 0.84rem;
            font-weight: 700;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: all 0.2s ease;
        }
        .target-subview-btn.active {
            background: linear-gradient(135deg, rgba(255, 45, 117, 0.22), rgba(168, 85, 247, 0.22));
            color: #fff;
            border: 1px solid var(--primary);
            box-shadow: 0 2px 10px rgba(255, 45, 117, 0.25);
        }

        html {
            font-size: 16px;
            -webkit-text-size-adjust: 100%;
            text-size-adjust: 100%;
            width: 100%;
            overflow-x: hidden;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            -webkit-tap-highlight-color: transparent;
        }

        h1, h2, h3, h4, .brand-title, .sidebar-bot-name, .card-title, .modal-title, .pitch-title-badge, .scout-price-val {
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        body {
            background: 
                radial-gradient(circle at 12% 10%, rgba(255, 45, 117, 0.15) 0%, transparent 45%),
                radial-gradient(circle at 88% 15%, rgba(244, 63, 94, 0.12) 0%, transparent 45%),
                radial-gradient(circle at 50% 90%, rgba(168, 85, 247, 0.08) 0%, transparent 55%),
                #030408;
            background-attachment: fixed;
            color: var(--text-main);
            padding-bottom: 90px;
            line-height: 1.5;
            font-size: 1rem;
            width: 100%;
            overflow-x: hidden;
        }

        /* Layout Grid */
        .app-layout {
            display: flex;
            min-height: 100vh;
            width: 100%;
        }

        /* Sidebar */
        .app-sidebar {
            width: 280px;
            background: var(--surface);
            border-right: 1px solid var(--border);
            padding: 24px 18px;
            display: flex;
            flex-direction: column;
            gap: 18px;
            position: fixed;
            top: 0;
            bottom: 0;
            left: 0;
            z-index: 1500;
            overflow-y: auto;
            transition: transform 0.25s ease;
        }

        .sidebar-bot-card {
            background: #0b111e;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 12px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.5);
        }

        .sidebar-avatar-wrap {
            position: relative;
            width: 92px;
            height: 92px;
            border-radius: 50%;
            padding: 3px;
            background: linear-gradient(135deg, #38bdf8, #0284c7, #fbbf24);
            box-shadow: 0 0 20px rgba(56, 189, 248, 0.4);
        }

        .sidebar-avatar {
            width: 100%;
            height: 100%;
            border-radius: 50%;
            object-fit: cover;
            display: block;
            background: #111726;
        }

        .sidebar-bot-name {
            font-size: 1.15rem;
            font-weight: 800;
            color: var(--text-main);
            letter-spacing: -0.3px;
        }

        .sidebar-bot-sub {
            font-size: 0.8rem;
            color: var(--primary);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .sidebar-advice-box {
            background: rgba(56, 189, 248, 0.07);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 8px;
            padding: 12px;
            font-size: 0.85rem;
            color: var(--text-muted);
            text-align: left;
            line-height: 1.45;
        }
        .sidebar-advice-title {
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 4px;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .sidebar-nav {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
        }

        .sidebar-nav-btn {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            justify-content: center;
            gap: 8px;
            padding: 14px;
            aspect-ratio: 1 / 1;
            min-height: 74px;
            border-radius: 12px;
            border: 1px solid rgba(198,154,76,0.16);
            background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(0,0,0,0.10));
            color: var(--text-muted);
            font-size: 0.82rem;
            font-weight: 700;
            cursor: pointer;
            text-align: left;
            transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease, color 0.18s ease;
        }
        .sidebar-nav-btn i {
            font-size: 1.4rem !important;
        }
        .sidebar-nav-btn:hover {
            transform: translateY(-2px);
            border-color: rgba(198,154,76,0.4);
            color: var(--text-main);
        }
        .sidebar-nav-btn.active {
            border-color: var(--officina-gold);
            box-shadow: inset 0 0 0 1px rgba(242,193,78,0.25), 0 0 20px rgba(242,193,78,0.16);
            color: var(--officina-gold);
        }

        .sidebar-profile-card {
            margin-top: auto;
            background: #0b111e;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 12px 14px;
            font-size: 0.85rem;
        }

        .main-wrapper {
            flex: 1;
            margin-left: 280px;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
            width: calc(100% - 280px);
            min-width: 0;
        }

        /* Responsive Breakpoint for Mobile & Tablets */
        @media (max-width: 899px) {
            .app-sidebar {
                transform: translateX(-100%);
            }
            .app-sidebar.open {
                transform: translateX(0);
            }
            .sidebar-backdrop {
                position: fixed;
                inset: 0;
                background: rgba(0,0,0,0.75);
                z-index: 1400;
                display: none;
            }
            .sidebar-backdrop.show {
                display: block;
            }
            .main-wrapper {
                margin-left: 0;
                width: 100%;
            }
        }

        @media (min-width: 900px) {
            nav.bottom-nav {
                display: none;
            }
            .mobile-sidebar-toggle {
                display: none;
            }
        }

        header {
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 12px 16px;
            position: sticky;
            top: 0;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
            width: 100%;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .brand-title {
            font-size: 1.15rem;
            font-weight: 800;
            color: var(--primary);
            letter-spacing: -0.3px;
        }
        .brand-tag {
            font-size: 0.75rem;
            background: rgba(56, 189, 248, 0.15);
            color: var(--primary);
            border: 1px solid rgba(56, 189, 248, 0.35);
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 700;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .profile-btn {
            background: var(--surface-elevated);
            color: var(--text-main);
            border: 1px solid var(--border);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.88rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
        }

        .admin-badge-btn {
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.82rem;
            font-weight: 700;
            cursor: pointer;
            border: 1px solid var(--border);
            background: #0b111e;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .admin-badge-btn.unlocked {
            background: rgba(16,185,129,0.18);
            border-color: rgba(16,185,129,0.5);
            color: var(--success);
        }

        .header-bot-pill {
            display: flex;
            align-items: center;
            gap: 8px;
            background: var(--surface-elevated);
            border: 1px solid var(--border);
            padding: 4px 10px 4px 6px;
            border-radius: 20px;
            cursor: pointer;
        }
        .header-avatar-img {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            object-fit: cover;
            border: 2px solid var(--primary);
        }

        .container {
            padding: 16px;
            max-width: 900px;
            margin: 0 auto;
            width: 100%;
        }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* Navigation */
        nav.bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            display: flex;
            height: 68px;
            z-index: 1000;
            padding-bottom: env(safe-area-inset-bottom);
            background: linear-gradient(180deg, #241a11, #160f09);
            border-top: 2px solid var(--officina-brass-dark);
            box-shadow: 0 -10px 24px rgba(0, 0, 0, 0.32);
        }
        .nav-item {
            flex: 1;
            min-width: 0;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            gap: 5px;
            margin: 6px 3px;
            border: none;
            background: transparent;
            color: var(--officina-muted);
            text-decoration: none;
            font-size: 0.62rem;
            font-weight: 700;
            cursor: pointer;
            position: relative;
            border-radius: 10px;
            transition: color 0.18s ease, transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
        }
        .nav-item::before {
            content: '';
            position: absolute;
            inset: 2px;
            border-radius: 10px;
            border: 1px solid rgba(198,154,76,0.14);
            background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(0,0,0,0.08));
            pointer-events: none;
        }
        .nav-item__icon {
            font-size: 1.3rem;
            line-height: 1;
        }
        .nav-item__label {
            max-width: 100%;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .nav-item.active {
            color: var(--officina-gold);
            transform: translateY(-2px) scale(1.04);
        }
        .nav-item.active::before {
            border-color: rgba(198,154,76,0.55);
            box-shadow: inset 0 0 0 1px rgba(242,193,78,0.25), 0 0 18px rgba(242,193,78,0.2);
        }
        .nav-item.active .nav-item__icon {
            filter: drop-shadow(0 0 8px rgba(242,193,78,0.4));
        }
        @media (max-width: 560px) {
            .nav-item {
                font-size: 0.62rem;
                gap: 3px;
            }
            .nav-item__icon {
                font-size: 1rem;
            }
        }
        .nav-svg { width: 22px; height: 22px; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }

        .session-login-officina {
            background: rgba(7, 5, 3, 0.88);
            backdrop-filter: blur(12px);
        }
        .session-login-officina__box {
            max-width: 440px;
            text-align: center;
            padding: 28px 24px;
            border: 1px solid rgba(198,154,76,0.4);
            box-shadow: 0 0 45px rgba(198,154,76,0.2);
            background: linear-gradient(180deg, #2a1e13, #1d140c);
        }
        .session-login-officina__crest {
            font-size: 2.2rem;
            margin-bottom: 8px;
            color: var(--officina-gold);
        }
        .session-login-officina__title {
            justify-content: center;
            margin-bottom: 4px;
            font-family: 'Outfit', sans-serif;
            font-size: 1.35rem;
            font-weight: 800;
            color: #f4e7ca;
        }
        .session-login-officina__copy,
        .session-login-officina__note {
            font-size: 0.82rem;
            color: #d8c6a5;
            line-height: 1.45;
        }
        .session-login-officina__field {
            text-align: left;
            margin: 0 0 14px;
        }
        .session-login-officina__field label {
            display: block;
            margin-bottom: 5px;
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--officina-muted);
        }
        .session-login-officina__field select,
        .session-login-officina__field input {
            width: 100%;
            margin-bottom: 0;
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid rgba(198,154,76,0.22);
            background: #0f0b08;
            color: var(--officina-ink);
        }
        .session-login-officina__submit {
            width: 100%;
            padding: 12px;
            border-radius: 8px;
            margin-top: 6px;
        }
        .session-login-officina #loginErrorMsg {
            margin-top: 6px;
            font-size: 0.8rem;
            font-weight: 600;
            color: #f59a7d;
            text-align: center;
        }

        /* Cards & Metrics */
        .card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            width: 100%;
        }
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border);
        }
        .card-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text-main);
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }

        /* Inputs & Buttons */
        input, select, textarea {
            width: 100%;
            padding: 12px 14px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: #0b111e;
            color: var(--text-main);
            font-size: 1rem;
            margin-bottom: 10px;
            outline: none;
        }
        input:focus, select:focus, textarea:focus { border-color: var(--border-focus); }

        .btn {
            width: 100%;
            min-height: 48px;
            padding: 12px 16px;
            border-radius: 8px;
            border: none;
            font-weight: 700;
            font-size: 1rem;
            cursor: pointer;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            transition: background 0.15s ease;
        }
        .btn-primary { background: linear-gradient(135deg, #ff2d75, #f43f5e); color: #ffffff; box-shadow: 0 0 16px rgba(255, 45, 117, 0.4); }
        .btn-primary:active { background: #e11d48; box-shadow: 0 0 8px rgba(255, 45, 117, 0.6); }
        .btn-secondary { background: var(--surface-elevated); color: var(--text-main); border: 1px solid var(--border); }
        .btn-danger { background: rgba(239,68,68,0.15); color: var(--danger); border: 1px solid rgba(239,68,68,0.4); }

        .price-row { display: flex; gap: 8px; align-items: center; margin-bottom: 14px; }
        .price-input { width: 120px; text-align: center; font-size: 1.4rem; font-weight: 800; color: var(--gold); }
        .btn-step { flex: 1; min-height: 44px; padding: 10px 6px; border-radius: 8px; background: var(--surface-elevated); border: 1px solid var(--border); color: var(--text-main); font-size: 0.95rem; font-weight: 700; cursor: pointer; }

        .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 0.8rem; font-weight: 800; text-align: center; }
        .badge-P { background: rgba(245,158,11,0.18); color: var(--role-p); border: 1px solid rgba(245,158,11,0.4); }
        .badge-D { background: rgba(16,185,129,0.18); color: var(--role-d); border: 1px solid rgba(16,185,129,0.4); }
        .badge-C { background: rgba(56,189,248,0.18); color: var(--role-c); border: 1px solid rgba(56,189,248,0.4); }
        .badge-A { background: rgba(255,45,117,0.18); color: var(--role-a); border: 1px solid rgba(255,45,117,0.45); }

        .tier-badge { font-size: 0.75rem; font-weight: 700; padding: 3px 8px; border-radius: 4px; }
        .tier-1 { background: rgba(239,68,68,0.18); color: #f87171; border: 1px solid rgba(239,68,68,0.4); }
        .tier-2 { background: rgba(245,158,11,0.18); color: #fbbf24; border: 1px solid rgba(245,158,11,0.4); }
        .tier-3 { background: rgba(16,185,129,0.18); color: #34d399; border: 1px solid rgba(16,185,129,0.4); }

        .pills {
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding-bottom: 6px;
            margin-bottom: 14px;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: none;
        }
        .pills::-webkit-scrollbar { display: none; }
        .pill {
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 0.88rem;
            font-weight: 600;
            background: var(--surface-elevated);
            color: var(--text-muted);
            border: 1px solid var(--border);
            white-space: nowrap;
            cursor: pointer;
            flex-shrink: 0;
            transition: all 0.15s ease;
        }
        .pill.active { background: linear-gradient(135deg, #ff2d75, #f43f5e); color: #ffffff; border-color: #ff2d75; font-weight: 800; box-shadow: 0 0 14px rgba(255, 45, 117, 0.45); }

        /* ══════════════════════════════════════════════════════════════════
           SPORT-TECH SCOUTING PLAYER CARDS
           ══════════════════════════════════════════════════════════════════ */
        .player-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 14px;
            background: rgba(15, 23, 42, 0.55);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-left: 4px solid var(--border);
            border-radius: 12px;
            margin-bottom: 8px;
            transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .player-row:hover {
            background: rgba(30, 41, 59, 0.75);
            border-color: rgba(255, 255, 255, 0.14);
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
        }
        .player-row.role-P { border-left-color: var(--role-p); }
        .player-row.role-D { border-left-color: var(--role-d); }
        .player-row.role-C { border-left-color: var(--role-c); }
        .player-row.role-A { border-left-color: var(--role-a); }

        .player-info { display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 0; }
        .player-name { font-weight: 700; font-size: 1.05rem; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .player-meta { font-size: 0.8rem; color: var(--text-muted); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
        
        .scout-tag-starter {
            display: inline-flex;
            align-items: center;
            gap: 3px;
            color: var(--success);
            font-size: 0.73rem;
            font-weight: 700;
            background: rgba(16, 185, 129, 0.12);
            padding: 1px 6px;
            border-radius: 4px;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .scout-vorp-badge {
            display: inline-flex;
            align-items: center;
            padding: 2px 7px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 800;
            background: rgba(56, 189, 248, 0.12);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.3);
        }

        .player-stats {
            text-align: right;
            min-width: 95px;
            flex-shrink: 0;
            padding-left: 10px;
        }
        .scout-price-box {
            background: linear-gradient(135deg, rgba(251, 191, 36, 0.12), rgba(217, 119, 6, 0.12));
            border: 1px solid rgba(251, 191, 36, 0.35);
            border-radius: 8px;
            padding: 4px 8px;
            display: inline-block;
            box-shadow: 0 0 10px rgba(251, 191, 36, 0.08);
        }
        .player-fair {
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            color: var(--gold);
            font-size: 1.15rem;
            line-height: 1;
        }
        .player-vorp { font-size: 0.78rem; font-weight: 700; margin-top: 2px; }

        .medical-badge {
            display: inline-flex;
            align-items: center;
            gap: 3px;
            font-size: 0.68rem;
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            cursor: pointer;
            transition: transform 0.15s, opacity 0.15s;
            user-select: none;
        }
        .medical-badge:hover {
            transform: scale(1.05);
            opacity: 0.9;
        }
        .medical-badge-success {
            background: rgba(34, 197, 94, 0.15);
            color: #4ade80;
            border: 1px solid rgba(34, 197, 94, 0.3);
        }
        .medical-badge-warning {
            background: rgba(234, 179, 8, 0.15);
            color: #facc15;
            border: 1px solid rgba(234, 179, 8, 0.3);
        }
        .medical-badge-danger {
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .target-slot-card {
            background: #0b111e;
            border: 1px solid var(--border);
            border-radius: 10px;
            margin-bottom: 8px;
            padding: 10px 14px;
            transition: all 0.2s ease;
        }
        .target-slot-card:hover {
            border-color: rgba(56, 189, 248, 0.4);
        }
        .target-slot-card.occupied {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(11, 17, 30, 0.95));
            border-left: 4px solid var(--gold);
        }
        .target-slot-card.empty {
            background: transparent;
            border: 1px dashed rgba(56, 189, 248, 0.35);
        }
        .target-slot-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }
        .target-slot-candidates {
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid var(--border);
            background: rgba(15, 23, 42, 0.65);
            border-radius: 8px;
            padding: 10px;
        }
        .candidate-player-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 10px;
            background: #0f172a;
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 6px;
            margin-bottom: 6px;
            transition: background 0.15s;
        }
        .candidate-player-row:hover {
            background: rgba(56, 189, 248, 0.08);
            border-color: rgba(56, 189, 248, 0.3);
        }

        .target-icon-btn {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border);
            border-radius: 8px;
            width: 34px;
            height: 34px;
            display: inline-flex;
            justify-content: center;
            align-items: center;
            cursor: pointer;
            color: var(--text-muted);
            margin-right: 6px;
            flex-shrink: 0;
            transition: all 0.15s ease;
        }
        .target-icon-btn:hover {
            border-color: var(--gold);
            color: var(--gold);
        }
        .target-icon-btn.active {
            background: rgba(251,191,36,0.22);
            border-color: rgba(251,191,36,0.7);
            color: var(--gold);
            box-shadow: 0 0 10px rgba(251, 191, 36, 0.3);
        }

        /* ══════════════════════════════════════════════════════════════════
           TACTICAL FANTASY STADIUM PITCH (2D VIRTUAL FIELD)
           ══════════════════════════════════════════════════════════════════ */
        .tactical-pitch-card {
            background: linear-gradient(180deg, rgba(13, 22, 38, 0.85) 0%, rgba(9, 14, 26, 0.95) 100%);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 18px;
            padding: 16px;
            margin-bottom: 18px;
            box-shadow: 0 12px 35px -8px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255,255,255,0.1);
            backdrop-filter: blur(16px);
        }
        .pitch-top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
        }
        .pitch-title-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            font-size: 0.98rem;
            color: #38bdf8;
            letter-spacing: -0.2px;
        }
        .pitch-board {
            position: relative;
            width: 100%;
            min-height: 400px;
            background: radial-gradient(ellipse at center, #0e3b23 0%, #082617 65%, #05190f 100%);
            border-radius: 14px;
            border: 2px solid rgba(255, 255, 255, 0.16);
            box-shadow: inset 0 0 45px rgba(0, 0, 0, 0.75);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 16px 12px;
        }
        .pitch-board::before {
            content: '';
            position: absolute;
            inset: 0;
            background: repeating-linear-gradient(180deg, transparent 0, transparent 40px, rgba(255,255,255,0.018) 40px, rgba(255,255,255,0.018) 80px);
            pointer-events: none;
        }
        .pitch-board::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 90px;
            height: 90px;
            border: 1.5px solid rgba(255, 255, 255, 0.14);
            border-radius: 50%;
            pointer-events: none;
        }
        .pitch-midline {
            position: absolute;
            top: 50%;
            left: 0;
            right: 0;
            height: 1.5px;
            background: rgba(255, 255, 255, 0.14);
            pointer-events: none;
        }
        .pitch-penalty-top {
            position: absolute;
            top: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 130px;
            height: 52px;
            border: 1.5px solid rgba(255, 255, 255, 0.14);
            border-top: none;
            border-radius: 0 0 8px 8px;
            pointer-events: none;
        }
        .pitch-penalty-bottom {
            position: absolute;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 130px;
            height: 52px;
            border: 1.5px solid rgba(255, 255, 255, 0.14);
            border-bottom: none;
            border-radius: 8px 8px 0 0;
            pointer-events: none;
        }
        .pitch-row {
            display: flex;
            justify-content: space-around;
            align-items: center;
            position: relative;
            z-index: 2;
            width: 100%;
            min-height: 72px;
            gap: 4px;
            flex-wrap: wrap;
        }
        .pitch-jersey {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Outfit', sans-serif;
            font-weight: 800;
            font-size: 0.85rem;
            color: #ffffff;
            box-shadow: 0 4px 14px rgba(0,0,0,0.6);
            border: 2px solid rgba(255,255,255,0.35);
            margin-bottom: 3px;
        }
        .pitch-jersey.role-P { background: linear-gradient(135deg, #f59e0b, #d97706); box-shadow: 0 0 14px rgba(245, 158, 11, 0.45); }
        .pitch-jersey.role-D { background: linear-gradient(135deg, #10b981, #059669); box-shadow: 0 0 14px rgba(16, 185, 129, 0.45); }
        .pitch-jersey.role-C { background: linear-gradient(135deg, #38bdf8, #0284c7); box-shadow: 0 0 14px rgba(56, 189, 248, 0.45); }
        .pitch-jersey.role-A { background: linear-gradient(135deg, #f43f5e, #e11d48); box-shadow: 0 0 14px rgba(244, 63, 94, 0.45); }

        .davinci-pitch-shell {
            position: relative;
            width: 100%;
            max-width: 420px;
            margin: 0 auto;
            filter: drop-shadow(0 8px 18px rgba(0,0,0,0.5));
        }
        .davinci-pitch-frame {
            position: relative;
            border-radius: 16px;
            padding: 12px;
            border: 1px solid rgba(198,154,76,0.26);
            background: linear-gradient(180deg, #2a1e13, #1c140d);
        }
        .davinci-pitch-stamp {
            position: absolute;
            top: 10px;
            left: 14px;
            z-index: 3;
            font-family: 'Cormorant Garamond', serif;
            font-style: italic;
            color: var(--officina-brass-dark);
            font-size: 0.8rem;
            opacity: 0.8;
        }
        .davinci-legend {
            display: flex;
            gap: 14px;
            flex-wrap: wrap;
            justify-content: center;
            margin-top: 12px;
            font-size: 0.72rem;
            color: var(--officina-muted);
        }
        .davinci-legend span {
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .davinci-legend i {
            width: 11px;
            height: 11px;
            border-radius: 50%;
            display: inline-block;
            border: 1px solid #3a2c14;
        }
        .davinci-token {
            cursor: pointer;
        }
        .davinci-token--empty {
            opacity: 0.56;
        }
        .davinci-jersey.role-P { fill: var(--davinci-role-p); }
        .davinci-jersey.role-D { fill: var(--davinci-role-d); }
        .davinci-jersey.role-C { fill: var(--davinci-role-c); }
        .davinci-jersey.role-A { fill: var(--davinci-role-a); }

        /* Financial HUD Progress Bar */
        .hud-squad-bar {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 4px;
            overflow: hidden;
            margin: 10px 0 6px 0;
            position: relative;
        }
        .hud-squad-progress {
            height: 100%;
            background: linear-gradient(90deg, #38bdf8, #10b981, #fbbf24);
            border-radius: 4px;
            transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 0 12px rgba(56, 189, 248, 0.5);
        }

        .suggestions { background: var(--surface-elevated); border: 1px solid var(--border); border-radius: 8px; max-height: 240px; overflow-y: auto; margin-top: -6px; margin-bottom: 12px; }
        .suggestion-item { padding: 12px 14px; border-bottom: 1px solid rgba(36,49,76,0.6); cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
        .suggestion-item:active { background: #24314c; }

        /* Dashboard Overview */
        .dept-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }
        @media (max-width: 599px) {
            .dept-grid { grid-template-columns: repeat(2, 1fr) !important; gap: 8px !important; }
            .container { padding: 12px !important; }
            .price-input { width: 95px !important; font-size: 1.25rem !important; }
        }
        .dept-card { background: #0b111e; border: 1px solid var(--border); border-radius: 8px; padding: 12px 8px; text-align: center; }
        .dept-label { font-size: 0.78rem; font-weight: 800; margin-bottom: 4px; text-transform: uppercase; }
        .dept-spent { font-size: 1.2rem; font-weight: 800; color: var(--gold); }
        .dept-count { font-size: 0.78rem; color: var(--text-muted); }

        .slot-section { margin-bottom: 16px; }
        .slot-title { font-size: 0.9rem; font-weight: 700; margin-bottom: 8px; display: flex; justify-content: space-between; color: var(--text-muted); border-bottom: 1px solid var(--border); padding-bottom: 6px; text-transform: uppercase; }
        .slot-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: #0b111e; border: 1px solid var(--border); border-radius: 8px; margin-bottom: 6px; font-size: 0.92rem; }
        .slot-row.empty { background: transparent; border: 1px dashed rgba(36,49,76,0.8); color: #64748b; font-style: italic; }
        .slot-num { font-size: 0.8rem; color: var(--text-muted); width: 26px; font-weight: 700; }
        .slot-player { font-weight: 600; display: flex; align-items: center; gap: 8px; min-width: 0; }
        .slot-price { font-weight: 800; color: var(--gold); font-size: 0.98rem; white-space: nowrap; }

        /* Modal Overlay */
        .modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 2000; display: none; justify-content: center; align-items: center; padding: 16px; }
        .modal-backdrop.active { display: flex !important; }
        .modal-box { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; width: 100%; max-width: 520px; padding: 20px; max-height: 90vh; overflow-y: auto; }
        .modal-title { font-size: 1.15rem; font-weight: 700; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center; }

        /* Strategy Planner Cards & Cluster Explorer */
        .plan-step-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 14px;
            margin-bottom: 12px;
            transition: all 0.15s ease;
        }
        .plan-step-card.active-target {
            border: 2px solid var(--primary);
            background: rgba(56,189,248,0.05);
        }
        .plan-step-card.completed {
            border-color: rgba(16,185,129,0.4);
        }
        .plan-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 8px;
            cursor: pointer;
            user-select: none;
        }
        .plan-slot-title { font-weight: 700; font-size: 0.96rem; }
        .plan-budget-badge { font-size: 0.82rem; font-weight: 700; padding: 4px 10px; border-radius: 6px; background: var(--surface-elevated); color: var(--gold); border: 1px solid var(--border); white-space: nowrap; }
        .candidate-mini-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            background: #0b111e;
            border-radius: 8px;
            margin-top: 6px;
            font-size: 0.9rem;
            cursor: pointer;
        }
        .candidate-mini-row:active { background: #182238; }

        /* Overview Table */
        .table-responsive { width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; margin-bottom: 12px; }
        .overview-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        .overview-table th, .overview-table td { padding: 10px 8px; text-align: right; border-bottom: 1px solid var(--border); white-space: nowrap; }
        .overview-table th:first-child, .overview-table td:first-child { text-align: left; }
        .overview-table th { color: var(--text-muted); font-weight: 700; background: var(--surface-elevated); }
        .overview-table tr:hover { background: rgba(56,189,248,0.04); }

        /* AI Chat / Query Box */
        .ai-query-card {
            background: linear-gradient(180deg, rgba(56,189,248,0.1) 0%, rgba(17,23,38,1) 100%);
            border: 1px solid rgba(56,189,248,0.35);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
        }
        .ai-pill {
            padding: 8px 14px;
            border-radius: 20px;
            background: rgba(56,189,248,0.12);
            border: 1px solid rgba(56,189,248,0.3);
            color: var(--primary);
            font-size: 0.82rem;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
            flex-shrink: 0;
        }
        .ai-pill:hover {
            background: var(--primary);
            color: #090d16;
        }

        /* Conversational Chat UI */
        .chat-container {
            display: flex;
            flex-direction: column;
            gap: 12px;
            min-height: 280px;
            max-height: 540px;
            overflow-y: auto;
            padding: 8px 2px;
            margin-bottom: 12px;
            scroll-behavior: smooth;
        }
        .chat-msg {
            display: flex;
            gap: 10px;
            max-width: 92%;
            animation: fadeInMsg 0.2s ease-in-out;
        }
        @keyframes fadeInMsg {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .chat-msg.user {
            align-self: flex-end;
            flex-direction: row-reverse;
        }
        .chat-msg.ai {
            align-self: flex-start;
            width: 100%;
        }
        .chat-msg-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            object-fit: cover;
            border: 1.5px solid var(--primary);
            flex-shrink: 0;
            margin-top: 2px;
        }
        .chat-bubble {
            padding: 12px 16px;
            border-radius: 12px;
            font-size: 0.95rem;
            line-height: 1.5;
            word-break: break-word;
        }
        .chat-msg.user .chat-bubble {
            background: #0284c7;
            color: #ffffff;
            border-bottom-right-radius: 2px;
        }
        .chat-msg.ai .chat-bubble {
            background: var(--surface-elevated);
            border: 1px solid var(--border);
            color: var(--text-main);
            border-bottom-left-radius: 2px;
            width: 100%;
        }
        .chat-input-row {
            display: flex;
            gap: 8px;
            align-items: center;
        }

        /* Market Inflation Badge */
        .market-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid var(--border);
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.76rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s ease;
            user-select: none;
        }
        .market-pill:hover {
            border-color: var(--primary);
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.2);
        }
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }
        .dot-green { background: var(--success); box-shadow: 0 0 6px var(--success); }
        .dot-yellow { background: var(--warning); box-shadow: 0 0 6px var(--warning); }
        .dot-red { background: var(--danger); box-shadow: 0 0 6px var(--danger); }
        .dot-blue { background: var(--primary); box-shadow: 0 0 6px var(--primary); }

        /* Toast Notifications */
        .toast-container {
            position: fixed;
            bottom: 24px;
            right: 24px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 10px;
            pointer-events: none;
            max-width: 380px;
        }
        .toast {
            background: #111726;
            color: var(--text-main);
            border: 1px solid var(--border);
            padding: 12px 18px;
            border-radius: 10px;
            font-size: 0.88rem;
            font-weight: 600;
            box-shadow: 0 8px 24px rgba(0,0,0,0.6);
            display: flex;
            align-items: center;
            gap: 10px;
            pointer-events: auto;
            animation: slideInToast 0.25s ease-out;
            transition: opacity 0.3s ease, transform 0.3s ease;
        }
        .toast.toast-success { border-color: var(--success); }
        .toast.toast-danger { border-color: var(--danger); }
        .toast.toast-warning { border-color: var(--warning); }
        .toast.toast-info { border-color: var(--primary); }
        @keyframes slideInToast {
            from { transform: translateX(40px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        /* ══════════════════════════════════════════════════════════════════
           RESPONSIVE VIEWPORT ISOLATION (PC DESKTOP VS MOBILE)
        ══════════════════════════════════════════════════════════════════ */
        @media (min-width: 900px) {
            nav.bottom-nav {
                display: none !important;
            }
            body {
                padding-bottom: 28px !important;
            }
            .mobile-sidebar-toggle {
                display: none !important;
            }
            .header-bot-pill {
                display: none !important;
            }
            .desktop-brand-title {
                display: inline-flex !important;
                align-items: center;
                gap: 8px;
            }
            .container {
                max-width: 1080px;
                margin: 0 auto;
                padding: 24px 28px;
            }
        }

        @media (max-width: 899px) {
            /* Smooth Airy Bottom Navigation (5 Tabs) */
            nav.bottom-nav {
                display: flex !important;
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                height: 60px;
                background: rgba(4, 6, 12, 0.96) !important;
                backdrop-filter: blur(20px) !important;
                -webkit-backdrop-filter: blur(20px) !important;
                border-top: 1px solid rgba(255, 45, 117, 0.25) !important;
                box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.75) !important;
                z-index: 1000;
                padding-bottom: max(6px, env(safe-area-inset-bottom, 8px)) !important;
                padding-top: 4px !important;
            }
            .nav-item {
                flex: 1;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                color: #94a3b8;
                font-size: 0.76rem !important;
                font-weight: 700;
                cursor: pointer;
                border: none;
                background: transparent;
                gap: 2px !important;
                padding: 4px 2px !important;
                border-radius: 10px;
                touch-action: manipulation;
                -webkit-tap-highlight-color: transparent;
                transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
            }
            .nav-item i {
                font-size: 1.25rem !important;
                margin-bottom: 2px;
                transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
            }
            .nav-item:active {
                transform: scale(0.90);
            }
            .nav-item.active {
                color: #ff2d75 !important;
                font-weight: 800 !important;
                background: rgba(255, 45, 117, 0.12) !important;
            }
            .nav-item.active i {
                color: var(--primary) !important;
                filter: drop-shadow(0 0 8px rgba(255, 45, 117, 0.8)) !important;
                transform: translateY(-2px) scale(1.15);
            }

            body {
                padding-bottom: calc(70px + env(safe-area-inset-bottom, 12px)) !important;
            }
            .container {
                padding: 10px 8px !important;
            }

            /* De-densified Cards & Spacing */
            .card {
                padding: 12px 10px !important;
                margin-bottom: 10px !important;
                border-radius: 10px !important;
            }
            .card-header {
                margin-bottom: 8px !important;
                padding-bottom: 6px !important;
            }
            .card-title {
                font-size: 0.88rem !important;
            }

            /* Native-feel Smooth Horizontal Pills */
            .pills {
                display: flex !important;
                flex-wrap: nowrap !important;
                overflow-x: auto !important;
                -webkit-overflow-scrolling: touch !important;
                scrollbar-width: none !important;
                gap: 8px !important;
                margin-bottom: 12px !important;
                padding: 2px 2px 6px 2px !important;
            }
            .pills::-webkit-scrollbar {
                display: none !important;
            }
            .pill {
                flex-shrink: 0 !important;
                white-space: nowrap !important;
                padding: 7px 13px !important;
                font-size: 0.80rem !important;
                font-weight: 700 !important;
                border-radius: 20px !important;
                min-height: 38px !important;
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                gap: 6px !important;
            }

            /* Lightweight Player Rows */
            .player-row {
                padding: 9px 10px !important;
                margin-bottom: 6px !important;
                border-radius: 9px !important;
                gap: 6px !important;
            }
            .player-name {
                font-size: 0.92rem !important;
                gap: 5px !important;
            }
            .player-meta {
                font-size: 0.72rem !important;
                gap: 4px !important;
            }
            .scout-price-box {
                padding: 3px 7px !important;
                border-radius: 6px !important;
            }
            .player-fair {
                font-size: 0.92rem !important;
            }

            /* Compact 2D Pitch */
            .pitch-board {
                min-height: 280px !important;
                max-height: 330px !important;
                padding: 10px 6px !important;
                border-radius: 10px !important;
            }
            /* Department Grid */
            .dept-grid {
                gap: 6px !important;
            }
            .dept-card {
                padding: 8px 4px !important;
                border-radius: 6px !important;
            }
            .dept-label {
                font-size: 0.65rem !important;
            }
            .dept-spent {
                font-size: 0.95rem !important;
            }
            .dept-count {
                font-size: 0.70rem !important;
            }

            .mobile-sidebar-toggle {
                display: flex !important;
            }
            .header-bot-pill {
                display: inline-flex !important;
            }
            .desktop-brand-title {
                display: none !important;
            }
            .hide-mobile {
                display: none !important;
            }
            .market-pill {
                padding: 3px 8px;
                font-size: 0.7rem;
            }
        }

        .splash-gate,
        .maestro-intro {
            position: fixed;
            inset: 0;
            z-index: var(--maestro-z);
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px;
        }
        .splash-gate__backdrop,
        .maestro-intro__scrim {
            position: absolute;
            inset: 0;
            background:
                radial-gradient(circle at 28% -5%, rgba(198,154,76,0.22) 0%, transparent 55%),
                linear-gradient(180deg, #1a130d 0%, #0e0906 100%);
        }
        .splash-gate__panel,
        .maestro-intro__card {
            position: relative;
            width: min(960px, 100%);
            border-radius: 18px;
            border: 1px solid rgba(198,154,76,0.34);
            background: linear-gradient(180deg, #2a1e13, #1d140c);
            box-shadow: 0 28px 80px -30px var(--officina-shadow);
            padding: 28px;
            color: var(--officina-ink);
        }
        .splash-gate__eyebrow,
        .maestro-intro__kicker {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--officina-gold);
            margin-bottom: 10px;
        }
        .splash-gate__title,
        .maestro-intro__content h2 {
            margin: 0 0 10px;
            font-family: 'Outfit', sans-serif;
            font-size: clamp(1.8rem, 4vw, 2.6rem);
            color: #f4e7ca;
        }
        .splash-gate__copy,
        .maestro-intro__content p {
            margin: 0 0 20px;
            max-width: 640px;
            color: #d8c6a5;
            line-height: 1.6;
        }
        .splash-team-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px;
        }
        .maestro-ambient {
            position: fixed;
            right: 16px;
            bottom: 84px;
            z-index: var(--maestro-z);
            border: none;
            background: transparent;
            padding: 0;
            cursor: pointer;
            display: flex;
            align-items: flex-end;
            gap: 10px;
            color: inherit;
            filter: drop-shadow(0 6px 12px rgba(0,0,0,0.6));
        }
        .maestro-ambient__halo {
            position: absolute;
            inset: -8px auto auto -8px;
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(242,193,78,0.28), transparent 70%);
            animation: maestro-pulse 3s ease-in-out infinite;
        }
        .maestro-ambient__sprite {
            position: relative;
            z-index: 1;
            display: block;
            width: 64px;
            height: 96px;
        }
        .maestro-ambient__bubble {
            position: relative;
            z-index: 1;
            max-width: 180px;
            padding: 6px 11px;
            border-radius: 8px 8px 3px 8px;
            border: 1px solid var(--officina-brass-dark);
            background: linear-gradient(180deg, #efe2c1, #dcc79a);
            color: #4a3618;
            font-family: 'Cormorant Garamond', serif;
            font-style: italic;
            font-size: 0.9rem;
            white-space: nowrap;
        }
        @keyframes maestro-pulse {
            0%, 100% { transform: scale(0.9); opacity: 0.5; }
            50% { transform: scale(1.08); opacity: 1; }
        }
        @media (max-width: 640px) {
            .maestro-ambient__bubble {
                display: none;
            }
        }

        .splash-team-card {
            border: 1px solid rgba(198,154,76,0.28);
            border-radius: 14px;
            background: linear-gradient(180deg, #312214, #21160d);
            color: var(--officina-ink);
            padding: 18px 16px;
            text-align: left;
            cursor: pointer;
            transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
        }
        .splash-team-card:hover,
        .splash-team-card:focus-visible {
            transform: translateY(-2px);
            border-color: rgba(242,193,78,0.58);
            box-shadow: 0 14px 28px -22px rgba(242,193,78,0.9);
        }
        .splash-team-card__name {
            display: block;
            font-family: 'Outfit', sans-serif;
            font-size: 1rem;
            font-weight: 800;
            color: #f4e7ca;
            margin-bottom: 4px;
        }
        .splash-team-card__meta {
            display: block;
            font-size: 0.78rem;
            color: var(--officina-muted);
        }
        #appBootSplash {
            position: fixed;
            inset: 0;
            z-index: 100000;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 18px;
            background:
                radial-gradient(circle at 50% 20%, rgba(198,154,76,0.20) 0%, transparent 60%),
                linear-gradient(180deg, #1a130d 0%, #0e0906 100%);
            transition: opacity 0.4s ease;
        }
        #appBootSplash.fade-out {
            opacity: 0;
            pointer-events: none;
        }
        .boot-splash__logo {
            font-family: 'Outfit', sans-serif;
            font-size: clamp(1.6rem, 5vw, 2.4rem);
            font-weight: 800;
            letter-spacing: 0.02em;
            color: var(--officina-gold);
            text-shadow: 0 0 24px rgba(242,193,78,0.35);
        }
        .boot-splash__spinner {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            border: 3px solid rgba(198,154,76,0.25);
            border-top-color: var(--officina-gold);
            animation: boot-splash-spin 0.9s linear infinite;
        }
        @keyframes boot-splash-spin {
            to { transform: rotate(360deg); }
        }
        .boot-splash__version {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            color: var(--officina-muted);
        }
        .bentornato-gate__actions {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            gap: 12px;
            margin-top: 6px;
        }
        .bentornato-gate__continue {
            padding: 12px 28px;
        }
        .bentornato-gate__not-you {
            background: none;
            border: none;
            color: var(--officina-muted);
            font-size: 0.82rem;
            text-decoration: underline;
            cursor: pointer;
            padding: 4px 0;
        }
        .bentornato-gate__not-you:hover {
            color: var(--officina-gold);
        }
        .maestro-intro__card {
            display: grid;
            grid-template-columns: 140px 1fr;
            gap: 20px;
            align-items: center;
        }
        .maestro-intro__art {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 140px;
            border-radius: 16px;
            background: radial-gradient(circle at 50% 30%, #3a2a19, #1b130c 75%);
            border: 2px solid var(--officina-brass);
        }
        .maestro-intro__btn {
            width: auto;
            padding: 12px 18px;
            border-radius: 10px;
        }
        @media (max-width: 680px) {
            .maestro-intro__card {
                grid-template-columns: 1fr;
                text-align: center;
            }
        }
        body.app-locked {
            overflow: hidden;
        }
        body.app-locked .maestro-ambient {
            display: none !important;
        }
    </style>
</head>
<body>

    <div id="appBootSplash">
        <div class="boot-splash__logo">footballerdata</div>
        <div class="boot-splash__spinner" aria-hidden="true"></div>
        <div class="boot-splash__version">v.1.00</div>
    </div>

    <div id="maestroIntroOverlay" class="maestro-intro" style="display:none;">
        <div class="maestro-intro__scrim"></div>
        <div class="maestro-intro__card">
            <div class="maestro-intro__art" id="maestroIntroSprite" aria-hidden="true"></div>
            <div class="maestro-intro__content">
                <div class="maestro-intro__kicker"><i class="fa-solid fa-feather"></i> Il Maestro</div>
                <h2>Benvenuto nell'Officina</h2>
                <p>Inventore, cartografo del calcio e tua guida analitica: ti mostrerò dove leggere prezzo equo, surplus, proiezioni e finestra medica di ogni calciatore.</p>
                <button class="btn btn-primary maestro-intro__btn" onclick="maybeShowMaestroIntro(true)">
                    <i class="fa-solid fa-door-open" style="margin-right:6px;"></i> Entra nella dashboard
                </button>
            </div>
        </div>
    </div>

    <div class="sidebar-backdrop" id="sidebarBackdrop" onclick="toggleMobileSidebar()"></div>

    <div class="app-layout">

        <!-- LATERAL SIDEBAR (TACTICAL ASSISTANT & NAVIGATION) -->
        <aside class="app-sidebar" id="appSidebar">
            <div class="sidebar-bot-card">
                <div class="sidebar-avatar-wrap">
                    {% if bot_avatar_image %}
                    <img src="{{ bot_avatar_image }}" class="sidebar-avatar" style="width:64px; height:64px; border-radius:50%; object-fit:cover; display:block; margin:0 auto; border:2.5px solid var(--primary); box-shadow:0 0 20px rgba(255,45,117,0.65);" alt="{{ bot_name }}">
                    {% else %}
                    <div class="sidebar-avatar" style="width:54px; height:54px; border-radius:50%; background:linear-gradient(135deg, #ff2d75, #a855f7); display:flex; align-items:center; justify-content:center; margin:0 auto; border:2px solid var(--primary); box-shadow: 0 0 16px rgba(255,45,117,0.5); font-family:'Outfit',sans-serif; font-size:1.25rem; font-weight:800; color:#ffffff;">
                        {{ bot_avatar_text }}
                    </div>
                    {% endif %}
                </div>
                <div>
                    <div class="sidebar-bot-name">{{ bot_name }}</div>
                    <div class="sidebar-bot-sub" style="color:var(--primary); font-style:italic; font-weight:600;">"{{ bot_subtitle }}"</div>
                </div>
            </div>

            <div class="sidebar-nav">
                <button class="sidebar-nav-btn active" id="sideNav-listone" onclick="switchTab('listone')">
                    <i class="fa-solid fa-table-list" style="color:#10b981; width:20px; font-size:1.1rem;"></i>
                    <span>Listone Analytics</span>
                </button>
                <button class="sidebar-nav-btn" id="sideNav-ai" onclick="switchTab('ai')">
                    <i class="fa-solid fa-robot icon-float" style="color:#a855f7; width:20px; font-size:1.1rem;"></i>
                    <span>Chiedi a {{ bot_name }}</span>
                </button>
            </div>

            <div style="margin-top:auto; padding:12px 10px; text-align:center;">
                <a href="https://buymeacoffee.com/blueskies360" target="_blank" rel="noopener noreferrer" style="display:inline-flex; align-items:center; justify-content:center; gap:6px; background:#fbbf24; color:#090d16; font-size:0.75rem; font-weight:800; padding:6px 14px; border-radius:20px; text-decoration:none; box-shadow:0 2px 8px rgba(251,191,36,0.3); width:100%;">
                    <i class="fa-solid fa-mug-hot"></i>
                    <span>Offri un Caffè</span>
                </a>
            </div>
        </aside>

        <!-- MAIN CONTENT WRAPPER -->
        <div class="main-wrapper">

            <header>
                <div class="brand">
                    <button class="profile-btn mobile-sidebar-toggle" onclick="toggleMobileSidebar()" style="padding:6px 10px; margin-right:2px;" aria-label="Menu">
                        <i class="fa-solid fa-bars" style="font-size:1.15rem; color:var(--text-main);"></i>
                    </button>
                    <div class="header-bot-pill" onclick="toggleMobileSidebar()" title="Menu Tattico">
                        {% if bot_avatar_image %}
                        <img src="{{ bot_avatar_image }}" style="width:28px; height:28px; border-radius:50%; object-fit:cover; border:1.5px solid var(--primary); margin-right:6px; box-shadow:0 0 10px rgba(255,45,117,0.55);" alt="{{ bot_name }}">
                        {% else %}
                        <div class="header-avatar-img" style="width:26px; height:26px; border-radius:50%; background:linear-gradient(135deg, #ff2d75, #a855f7); display:flex; align-items:center; justify-content:center; border:1px solid var(--primary); margin-right:4px; font-family:'Outfit',sans-serif; font-size:0.75rem; font-weight:800; color:#fff;">
                            {{ bot_avatar_text }}
                        </div>
                        {% endif %}
                        <span class="header-bot-pill-name">{{ bot_name }}</span>
                        <span class="header-bot-pill-badge">{{ bot_badge }}</span>
                    </div>

                    <div class="desktop-brand-title" style="display:none; align-items:center; gap:8px;">
                        <span style="font-family:'Outfit',sans-serif; font-weight:800; font-size:1.15rem; color:var(--text-main); letter-spacing:-0.3px;"><i class="fa-solid fa-bolt icon-pulse" style="color:var(--primary); margin-right:4px;"></i>{{ bot_name }}</span>
                        <span class="brand-tag" style="font-size:0.7rem; padding:2px 7px; background:rgba(255,45,117,0.15); border:1px solid rgba(255,45,117,0.35); color:var(--primary); font-weight:800; border-radius:4px;">{{ bot_badge }}</span>
                    </div>
                </div>

                <div class="header-actions">
                    <button id="guideNavBtn" class="profile-btn hide-mobile" onclick="FantaTour.start()" title="Avvia il tour guidato">
                        <i class="fa-solid fa-circle-question"></i>
                        <span>Guida</span>
                    </button>
                </div>
            </header>

            <div class="container">

        <div id="tab-ai" class="tab-content">
            <div class="card" style="border-top:3px solid var(--primary); padding:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom:1px solid var(--border); padding-bottom:10px;">
                    <div style="display:flex; align-items:center; gap:12px;">
                        {% if bot_avatar_image %}
                        <img src="{{ bot_avatar_image }}" style="width:42px; height:42px; border-radius:50%; object-fit:cover; border:2px solid var(--primary); box-shadow:0 0 14px rgba(255,45,117,0.55);" alt="{{ bot_name }}">
                        {% else %}
                        <div style="width:38px; height:38px; border-radius:50%; background:linear-gradient(135deg, #ff2d75, #a855f7); display:flex; align-items:center; justify-content:center; border:2px solid var(--primary); box-shadow:0 0 12px rgba(255,45,117,0.45); font-family:'Outfit',sans-serif; font-size:1rem; font-weight:800; color:#fff;">
                            {{ bot_avatar_text }}
                        </div>
                        {% endif %}
                        <div>
                            <div style="font-weight:800; font-size:1.15rem; color:var(--text-main); font-family:'Outfit',sans-serif;">{{ bot_name }} Chatbot</div>
                            <div style="font-size:0.75rem; color:var(--primary); font-weight:600; font-style:italic;">"{{ bot_subtitle }}"</div>
                        </div>
                    </div>
                    <button class="btn-secondary" onclick="clearAIChat()" style="width:auto; padding:6px 12px; font-size:0.78rem; font-weight:700;">
                        Pulisci Chat
                    </button>
                </div>

                <!-- AI Engine Diagnostic Bar -->
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; background:rgba(15,23,42,0.65); padding:6px 10px; border-radius:8px; border:1px solid var(--border);">
                    <div style="display:flex; align-items:center; gap:6px; min-width:0; overflow:hidden;">
                        <span id="aiEngineStatusDot" class="status-dot dot-yellow" style="flex-shrink:0;"></span>
                        <span style="font-size:0.75rem; color:var(--text-muted); flex-shrink:0;">Motore:</span>
                        <span id="aiActiveEngineLabel" style="font-size:0.78rem; font-weight:800; color:var(--primary); white-space:nowrap; text-overflow:ellipsis; overflow:hidden;">Verifica in corso...</span>
                    </div>
                    <button class="btn-secondary" onclick="openAIDiagnosticsModal()" style="width:auto; padding:3px 8px; font-size:0.70rem; font-weight:700; flex-shrink:0; margin-left:6px;">
                        <i class="fa-solid fa-stethoscope" style="margin-right:4px;"></i> Diagnostica
                    </button>
                </div>

                <!-- Chat Quick Chips -->
                <div class="pills" style="margin-bottom:10px;">
                    <div class="ai-pill" onclick="setAIQuery('Malen vs Lautaro Martinez')">Malen vs Lautaro</div>
                    <div class="ai-pill" onclick="setAIQuery('Migliori centrocampisti sotto 35 crediti')">Centrocampisti < 35cr</div>
                    <div class="ai-pill" onclick="setAIQuery('Top difensori per modificatore')">Top Difensori</div>
                    <div class="ai-pill" onclick="setAIQuery('Scommesse attaccanti a 1 credito')">Scommesse a 1cr</div>
                    <div class="ai-pill" onclick="setAIQuery('Scheda Dimarco')">Analizza Dimarco</div>
                </div>

                <!-- Conversational Message Stream -->
                <div id="chatMessagesStream" class="chat-container">
                    <div class="chat-msg ai">
                        {% if bot_avatar_image %}
                        <img src="{{ bot_avatar_image }}" style="width:36px; height:36px; border-radius:50%; object-fit:cover; flex-shrink:0; border:1.5px solid var(--primary); box-shadow:0 0 10px rgba(255,45,117,0.55);" alt="{{ bot_name }}">
                        {% else %}
                        <div class="chat-msg-avatar" style="width:34px; height:34px; border-radius:50%; background:linear-gradient(135deg, #ff2d75, #a855f7); display:flex; align-items:center; justify-content:center; flex-shrink:0; border:1.5px solid var(--primary); font-family:'Outfit',sans-serif; font-size:0.85rem; font-weight:800; color:#fff;">
                            {{ bot_avatar_text }}
                        </div>
                        {% endif %}
                        <div class="chat-bubble">
                            <b>{{ bot_greeting }}</b>
                        </div>
                    </div>
                </div>

                <!-- Input Row -->
                <div class="chat-input-row">
                    <input type="text" id="aiInputPrompt" placeholder="Fai una domanda (es. 'Chi prendo tra Lookman e Thuram?')..." style="margin-bottom:0; flex:1;" onkeypress="if(event.key==='Enter') submitAIQuery()">
                    <button class="btn btn-primary" id="btnSubmitAI" style="width:auto; min-height:46px; padding:0 18px; font-weight:700;" onclick="submitAIQuery()">
                        Invia
                    </button>
                </div>
            </div>
        </div>

        <!-- TAB 6: LISTONE COMPLETO & ANALYTICS -->
        <div id="tab-listone" class="tab-content active">
            <div class="pills" id="rolePills">
                <div class="pill active" onclick="setRoleFilter('ALL')">Tutti</div>
                <div class="pill" onclick="setRoleFilter('P')">Portieri <span id="pillRoleCount_P">(4)</span></div>
                <div class="pill" onclick="setRoleFilter('D')">Difensori <span id="pillRoleCount_D">(9)</span></div>
                <div class="pill" onclick="setRoleFilter('C')">Centrocampisti <span id="pillRoleCount_C">(9)</span></div>
                <div class="pill" onclick="setRoleFilter('A')">Attaccanti <span id="pillRoleCount_A">(7)</span></div>
            </div>

            <div class="pills" id="fasciaPills">
                <div class="pill active" onclick="setFasciaFilter('ALL')">Tutte le Fasce</div>
                <div class="pill" onclick="setFasciaFilter('1')">1ª Fascia Top</div>
                <div class="pill" onclick="setFasciaFilter('2')">2ª Fascia Semi-Top</div>
                <div class="pill" onclick="setFasciaFilter('3')">3ª Fascia Titolari</div>
                <div class="pill" onclick="setFasciaFilter('4')">4ª Fascia Scommesse</div>
            </div>

            <div style="display:flex; gap:8px; margin-bottom:10px; flex-wrap:wrap; align-items:center;">
                <input type="text" id="listSearch" placeholder="Cerca calciatore o squadra..." oninput="renderListone()" style="margin-bottom:0; flex:1; min-width:160px;">
                <select id="listSortBy" onchange="renderListone()" style="width:auto; margin-bottom:0; padding:8px 12px; font-size:0.82rem; font-weight:700; background:#0f172a; color:var(--text-main); border:1px solid var(--border); border-radius:6px; cursor:pointer;" title="Ordina calciatori">
                    <option value="best" selected>Migliori (Score & VORP)</option>
                    <option value="mv_desc">Media Voto (Più alta)</option>
                    <option value="mfv_desc">FantaMedia (Più alta)</option>
                    <option value="fair_desc">Prezzo Fair (Più alti)</option>
                    <option value="fair_asc">Prezzo Fair (Più bassi / 1 cr)</option>
                    <option value="pts_desc">Punti Attesi P50</option>
                    <option value="vorp_desc">VORP (+ Valore)</option>
                    <option value="alpha">Alfabetico (A-Z)</option>
                </select>
            </div>

            <div id="listoneContainer"></div>
        </div>

    </div> <!-- end .container -->
    </div> <!-- end .main-wrapper -->
    </div> <!-- end .app-layout -->

    <!-- PLAYER DETAIL DRAWER (Finestra Medica & Metriche Avanzate) -->
    <div id="playerDetailDrawer" class="modal-backdrop" style="display:none; z-index:9999;">
        <div id="playerDetailPanel" style="
            position:fixed; top:0; right:-480px; width:min(480px, 96vw); height:100vh;
            background:var(--bg); border-left:2px solid var(--primary);
            overflow-y:auto; padding:20px 18px 32px; transition:right 0.35s cubic-bezier(.4,0,.2,1);
            box-shadow:-8px 0 32px rgba(0,0,0,0.6); z-index:10000;
        ">
            <!-- Header -->
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <div>
                    <div id="pdName" style="font-size:1.25rem; font-weight:900; color:var(--text);"></div>
                    <div style="display:flex; gap:6px; align-items:center; margin-top:3px;">
                        <span id="pdRole" class="role-badge" style="font-size:0.72rem; padding:2px 8px;"></span>
                        <span id="pdTeam" style="font-size:0.82rem; color:var(--text-muted); font-weight:600;"></span>
                    </div>
                </div>
                <button onclick="closePlayerDetailDrawer()" style="background:transparent; border:none; color:var(--text-muted); font-size:1.4rem; cursor:pointer; padding:4px 8px;">✕</button>
            </div>

            <!-- Price & Value Summary Bar -->
            <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:6px; margin-bottom:16px;">
                <div style="background:#0b111e; border:1px solid var(--border); border-radius:8px; padding:8px 6px; text-align:center;">
                    <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">Fair Value</div>
                    <div id="pdFairPrice" style="font-size:1.1rem; font-weight:900; color:var(--gold);"></div>
                </div>
                <div style="background:#0b111e; border:1px solid var(--border); border-radius:8px; padding:8px 6px; text-align:center;">
                    <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">VORP</div>
                    <div id="pdVorp" style="font-size:1.1rem; font-weight:900; color:var(--primary);"></div>
                </div>
                <div style="background:#0b111e; border:1px solid var(--border); border-radius:8px; padding:8px 6px; text-align:center;">
                    <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">Score</div>
                    <div id="pdScore" style="font-size:1.1rem; font-weight:900; color:var(--accent);"></div>
                </div>
                <div style="background:#0b111e; border:1px solid var(--border); border-radius:8px; padding:8px 6px; text-align:center;">
                    <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">Fascia</div>
                    <div id="pdFascia" style="font-size:1.1rem; font-weight:900; color:var(--primary);"></div>
                </div>
            </div>

            <!-- SECTION: Econometria Aste (Target & Clearing Pricing) -->
            <div style="background:#0b111e; border:1px solid var(--border); border-radius:10px; padding:12px 14px; margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <b style="font-size:0.86rem; color:var(--primary);"><i class="fa-solid fa-scale-balanced" style="color:var(--gold); margin-right:6px;"></i>Prezzo Target & Clearing (Modello Econometrico)</b>
                    <span id="pdClearingSourceBadge" style="font-size:0.70rem; font-weight:700; padding:2px 8px; border-radius:10px; background:rgba(99,102,241,0.15); color:var(--primary);"></span>
                </div>
                <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; text-align:center; margin-bottom:8px;">
                    <div style="background:rgba(255,255,255,0.02); padding:6px; border-radius:6px; border:1px solid rgba(255,255,255,0.05);">
                        <div style="font-size:0.60rem; color:var(--text-muted); font-weight:700;">TARGET ECONOMETRICO</div>
                        <div id="pdTargetPrice" style="font-size:1.1rem; font-weight:900; color:var(--gold);"></div>
                    </div>
                    <div style="background:rgba(255,255,255,0.02); padding:6px; border-radius:6px; border:1px solid rgba(255,255,255,0.05);">
                        <div style="font-size:0.60rem; color:var(--text-muted); font-weight:700;">CLEARING STORICO</div>
                        <div id="pdClearingPrice" style="font-size:1.1rem; font-weight:900; color:var(--text);"></div>
                    </div>
                    <div style="background:rgba(255,255,255,0.02); padding:6px; border-radius:6px; border:1px solid rgba(255,255,255,0.05);">
                        <div style="font-size:0.60rem; color:var(--text-muted); font-weight:700;">SURPLUS / SCONTO</div>
                        <div id="pdSurplusVal" style="font-size:1.1rem; font-weight:900;"></div>
                    </div>
                </div>
                <div id="pdTargetFlags" style="font-size:0.72rem; color:var(--text-muted); font-family:monospace; word-break:break-all;"></div>
            </div>

            <!-- SECTION: Finestra Medica -->
            <div style="background:#0b111e; border:1px solid var(--border); border-radius:10px; padding:14px; margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <b style="font-size:0.88rem; color:var(--primary);"><i class="fa-solid fa-heart-pulse icon-pulse" style="color:var(--danger); margin-right:6px;"></i>Finestra Medica</b>
                    <span id="pdMedBadge" style="font-size:0.78rem; font-weight:800; padding:3px 10px; border-radius:12px;"></span>
                </div>
                <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin-bottom:10px;">
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">GIORNI PERSI (3Y)</div>
                        <div id="pdDaysLost" style="font-size:1.3rem; font-weight:900; color:var(--text);"></div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">N° INFORTUNI</div>
                        <div id="pdInjCount" style="font-size:1.3rem; font-weight:900; color:var(--text);"></div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">INF. GRAVE</div>
                        <div id="pdSevere" style="font-size:1.3rem; font-weight:900;"></div>
                    </div>
                </div>
                <div id="pdInjuryList" style="max-height:120px; overflow-y:auto; font-size:0.76rem; color:var(--text-muted); line-height:1.6;"></div>
            </div>

            <!-- SECTION: Understat Offensive Metrics -->
            <div style="background:#0b111e; border:1px solid var(--border); border-radius:10px; padding:14px; margin-bottom:14px;">
                <b style="font-size:0.88rem; color:var(--primary); display:block; margin-bottom:10px;"><i class="fa-solid fa-futbol" style="color:var(--gold); margin-right:6px;"></i>Volumi Offensivi (Understat)</b>
                <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin-bottom:8px;">
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">xG / 90'</div>
                        <div id="pdXg90" style="font-size:1.15rem; font-weight:900; color:var(--gold);"></div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">npxG / 90'</div>
                        <div id="pdNpxg90" style="font-size:1.15rem; font-weight:900; color:var(--gold);"></div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">xA / 90'</div>
                        <div id="pdXa90" style="font-size:1.15rem; font-weight:900; color:var(--accent);"></div>
                    </div>
                </div>
                <div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:8px;">
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">TIRI / 90'</div>
                        <div id="pdShots90" style="font-size:1.15rem; font-weight:900; color:var(--text);"></div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">Δ GOL vs xG</div>
                        <div id="pdDeltaXg" style="font-size:1.15rem; font-weight:900;"></div>
                    </div>
                </div>
            </div>

            <!-- SECTION: Quantile Volatility Profile -->
            <div style="background:#0b111e; border:1px solid var(--border); border-radius:10px; padding:14px; margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <b style="font-size:0.88rem; color:var(--primary);"><i class="fa-solid fa-chart-column" style="color:var(--primary); margin-right:6px;"></i>Profilo Quantilico</b>
                    <span id="pdProfileBadge" style="font-size:0.75rem; font-weight:800; padding:3px 10px; border-radius:12px;"></span>
                </div>
                <!-- Visual Bar P10 → P50 → P90 -->
                <div style="position:relative; background:var(--bg-card); border-radius:8px; height:32px; margin-bottom:10px; overflow:hidden;">
                    <div id="pdQuantileBar" style="position:absolute; top:0; height:100%; border-radius:8px; transition:all 0.5s;"></div>
                    <div id="pdQuantileP50Mark" style="position:absolute; top:0; height:100%; width:3px; background:var(--gold); border-radius:2px; z-index:2;"></div>
                </div>
                <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px;">
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">FLOOR P10</div>
                        <div id="pdP10" style="font-size:1.1rem; font-weight:900; color:#ef4444;"></div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">MEDIANA P50</div>
                        <div id="pdP50" style="font-size:1.1rem; font-weight:900; color:var(--gold);"></div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">CEILING P90</div>
                        <div id="pdP90" style="font-size:1.1rem; font-weight:900; color:#22c55e;"></div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">SPREAD</div>
                        <div id="pdSpread" style="font-size:1.1rem; font-weight:900; color:var(--primary);"></div>
                    </div>
                </div>
            </div>

            <!-- SECTION: Starter Status / Minutes -->
            <div style="background:#0b111e; border:1px solid var(--border); border-radius:10px; padding:14px; margin-bottom:14px;">
                <b style="font-size:0.88rem; color:var(--primary); display:block; margin-bottom:10px;"><i class="fa-solid fa-clipboard-user" style="color:var(--primary); margin-right:6px;"></i>Titolarità & Minuti 26/27</b>
                <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:8px;">
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">TITOLARE</div>
                        <div id="pdStarter" style="font-size:1.1rem; font-weight:900;"></div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">PRESENZE DA TITOLARE</div>
                        <div id="pdStarts" style="font-size:1.1rem; font-weight:900; color:var(--text);"></div>
                    </div>
                    <div style="text-align:center;">
                        <div style="font-size:0.62rem; color:var(--text-muted); font-weight:700;">MINUTI</div>
                        <div id="pdMinutes" style="font-size:1.1rem; font-weight:900; color:var(--text);"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div id="toastContainer" class="toast-container"></div>

    <div id="aiDiagnosticsModal" class="modal-backdrop">
        <div class="modal-box" style="max-width:480px;">
            <div class="modal-title">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span><i class="fa-solid fa-stethoscope" style="margin-right:6px;"></i>Diagnostica AI Copilot</span>
                    <span id="modalAiBadge" class="brand-tag">STATUS</span>
                </div>
                <button style="background:transparent; border:none; color:var(--text-muted); font-size:1.2rem; cursor:pointer;" onclick="closeAIDiagnosticsModal()">✕</button>
            </div>

            <div style="margin-bottom:12px; font-size:0.80rem; color:var(--text-muted); line-height:1.4;">
                Qui puoi verificare quale motore AI sta alimentando le risposte e configurare le API gratuite (Groq o Gemini) su Vercel a costo zero.
            </div>

            <div id="aiDiagStatusBox" style="background:#0b111e; border:1px solid var(--border); border-radius:8px; padding:10px 12px; margin-bottom:12px;">
                <div style="font-size:0.75rem; color:var(--text-muted); font-weight:700; margin-bottom:6px;">MOTORE ATTIVO CORRENTE:</div>
                <div id="diagActiveEngine" style="font-size:0.95rem; font-weight:800; color:var(--primary); margin-bottom:6px;">-</div>
                <div id="diagActiveEngineDesc" style="font-size:0.74rem; color:var(--text-muted);">-</div>
            </div>

            <div style="font-size:0.78rem; font-weight:700; color:var(--text-main); margin-bottom:8px;">STATO PROVIDER DISPONIBILI:</div>
            <div id="aiProvidersList" style="display:flex; flex-direction:column; gap:6px; margin-bottom:14px;"></div>

            <div style="background:rgba(255,45,117,0.06); border:1px solid rgba(255,45,117,0.25); border-radius:8px; padding:10px; margin-bottom:14px;">
                <div style="font-size:0.75rem; font-weight:800; color:var(--primary); margin-bottom:4px;"><i class="fa-regular fa-lightbulb" style="color:var(--gold); margin-right:4px;"></i>Come attivare Groq Free (0$) su Vercel:</div>
                <div style="font-size:0.72rem; color:var(--text-muted); line-height:1.4;">
                    1. Crea una chiave gratis su <a href="https://console.groq.com/keys" target="_blank" style="color:var(--primary); font-weight:700;">console.groq.com</a> (nessuna carta richiesta).<br>
                    2. Nel tuo pannello Vercel &rarr; <i>Settings &rarr; Environment Variables</i>.<br>
                    3. Aggiungi la variabile: <b>GROQ_API_KEY</b> = <code>gsk_...</code>.<br>
                    4. Il bot passerà istantaneamente a <b>Llama 3.3 70B</b> gratis con risposte complete e veloci.
                </div>
            </div>

            <div style="display:flex; gap:8px;">
                <button class="btn btn-secondary" style="width:40%;" onclick="closeAIDiagnosticsModal()">Chiudi</button>
                <button class="btn btn-primary" style="width:60%;" id="btnTestAI" onclick="testAIConnection()">Test Connessione Live</button>
            </div>
            <div id="testAIResult" style="margin-top:8px; font-size:0.75rem; text-align:center; display:none;"></div>
        </div>
    </div>

    <!-- Bottom Navigation -->
    <nav class="bottom-nav">
        <button class="nav-item active" id="botNav-listone" onclick="switchTab('listone')">
            <i class="fa-solid fa-table-list nav-item__icon"></i>
            <span class="nav-item__label">Listone</span>
        </button>
        <button class="nav-item" id="botNav-ai" onclick="switchTab('ai')">
            <i class="fa-solid fa-robot icon-float nav-item__icon"></i>
            <span class="nav-item__label">{{ bot_name }}</span>
        </button>
    </nav>

    <script>
        let allPlayers = [];
        let currentRoleFilter = 'ALL';
        let currentFasciaFilter = 'ALL';

        function maybeShowMaestroIntro(forceClose = false) {
            const overlay = document.getElementById('maestroIntroOverlay');
            if (!overlay) return;
            if (forceClose) {
                localStorage.setItem('fanta_maestro_intro_done', 'true');
                overlay.style.display = 'none';
                document.body.classList.remove('app-locked');
                return;
            }
            if (localStorage.getItem('fanta_maestro_intro_done') === 'true') return;
            overlay.style.display = 'flex';
            document.body.classList.add('app-locked');
        }

        function runBootSplash(onComplete) {
            const splash = document.getElementById('appBootSplash');
            if (!splash) {
                onComplete();
                return;
            }
            setTimeout(() => {
                splash.classList.add('fade-out');
                setTimeout(() => {
                    splash.style.display = 'none';
                    onComplete();
                }, 400); // matches the 0.4s CSS transition above
            }, 1200);
        }

        window.MAESTRO_SPRITES = {
            neutral: [
                '..........CC..........','.........oooo.........','.......ooHHHHHHoo......','......oHHHHHHHHHHo.....','......oHHHhhHHhHHHo....','.....oHHHHHHHHHHHHo....','.....oHHHHHHHHHHHHo....','....obBBBBBBBBBBBBbo...','....oBLBBBBBBBBBBLBo...','...oBGGgBBBBBBBBGGgBo..','...oBGGgBBBBBBBBGGgBo..','....obBBBBBBBBBBBBbo...','.....oSSSSSSSSSSSSo....','.....oSSsSSSSSSsSSo....','.....oSooSSSSSSooSo....','.....oSooSSSSSSooSo....','.....oSSSSSssSSSSSo....','......oSSSSssSSSSo.....','......oWwsSSSSswWo.....','.....oWWWWwssWWWWWo....','....oWWWWWWWWWWWWWWo...','...oWWWWWWWWWWWWWWWWo..','...oWWWWwWWWWWWwWWWWo..','...oWWWWWWWWWWWWWWWWo..','....oWWWWWWWWWWWWWWo...','.....oWWWWWwwWWWWWo....','......oWWWWWWWWWWo.....','.......oWWWWWWWWo......','...RR..oWWWWWWWWo..RR..','.RRRRRRoWWWWWWWWoRRRRRR','RRRRRRRRoWWWWWWoRRRRRRR','RRrRRRLBRRRRRRRRBLRRrRR','RRrRRRRRRRRRRRRRRRRrRRR'
            ],
            greeting: [
                '..........CC..........','.........oooo.........','.......ooHHHHHHoo......','......oHHHHHHHHHHo.....','......oHHHhhHHhHHHo....','.....oHHHHHHHHHHHHo....','.....oHHHHHHHHHHHHo....','....obBBBBBBBBBBBBbo...','....oBLBBBBBBBBBBLBo...','...oBGGgBBBBBBBBGGgBo..','...oBGGgBBBBBBBBGGgBo..','....obBBBBBBBBBBBBbo...','.....oSSSSSSSSSSSSo....','.....oSSsSSSSSSsSSo....','.....oSooSSSSSSooSo....','.....oSooSSSSSSooSo....','.....oSSSSSssSSSSSo....','......oSSSSssSSSSo.....','......oWwsSSSSswWo.....','.....oWWWWwssWWWWWo....','....oWWWWWWWWWWWWWWo...','...oWWWWWWWWWWWWWWWWo..','...oWWWWwWWWWWWwWWWWo..','...oWWWWWWWWWWWWWWWWo..','....oWWWWWWWWWWWWWWo...','.....oWWWWWwwWWWWWo....','......oWWWWWWWWWWo..B..','.......oWWWWWWWWo..BB..','...RR..oWWWWWWWWo...B..','.RRRRRRoWWWWWWWWoRRRRRR','RRRRRRRRoWWWWWWoRRRRRRR','RRrRRRLBRRRRRRRRBLRRrRR','RRrRRRRRRRRRRRRRRRRrRRR'
            ],
            pointing: [
                '..........CC..........','.........oooo.........','.......ooHHHHHHoo......','......oHHHHHHHHHHo.....','......oHHHhhHHhHHHo....','.....oHHHHHHHHHHHHo....','.....oHHHHHHHHHHHHo....','....obBBBBBBBBBBBBbo...','....oBLBBBBBBBBBBLBo...','...oBGGgBBBBBBBBGGgBo..','...oBGGgBBBBBBBBGGgBo..','....obBBBBBBBBBBBBbo...','.....oSSSSSSSSSSSSo....','.....oSSsSSSSSSsSSo....','.....oSooSSSSSSooSo....','.....oSooSSSSSSooSo....','.....oSSSSSssSSSSSo....','......oSSSSssSSSSo.....','......oWwsSSSSswWo.....','.....oWWWWwssWWWWWo....','....oWWWWWWWWWWWWWWoBBB','...oWWWWWWWWWWWWWWWWo.B','...oWWWWwWWWWWWwWWWWo..','...oWWWWWWWWWWWWWWWWo..','....oWWWWWWWWWWWWWWo...','.....oWWWWWwwWWWWWo....','......oWWWWWWWWWWo.....','.......oWWWWWWWWo......','...RR..oWWWWWWWWo..RR..','.RRRRRRoWWWWWWWWoRRRRRR','RRRRRRRRoWWWWWWoRRRRRRR','RRrRRRLBRRRRRRRRBLRRrRR','RRrRRRRRRRRRRRRRRRRrRRR'
            ],
            thoughtful: [
                '..........CC..........','.........oooo.........','.......ooHHHHHHoo......','......oHHHHHHHHHHo.....','......oHHHhhHHhHHHo....','.....oHHHHHHHHHHHHo....','.....oHHHHHHHHHHHHo....','....obBBBBBBBBBBBBbo...','....oBLBBBBBBBBBBLBo...','...oBGGgBBBBBBBBGGgBo..','...oBGGgBBBBBBBBGGgBo..','....obBBBBBBBBBBBBbo...','.....oSSSSSSSSSSSSo....','.....oSSsSSSSSSsSSo....','.....oSooSSSSSSooSo....','.....oSooSSSSSSooSo....','.....oSSSSSssSSSSSo....','......oSSSSssSSSSo.....','......oWwsSSSSswWo.....','.....oWWWWwssWWWWWo....','....oWWWWWWWWWWWWWWo...','...oWWWWWWWWWWWWWWWWo..','...oWWWWwWWWWWWwWWWWo..','...oWWWWWWWWWWWWWWWWo..','....oWWWWWWWWWWWWWWo...','.....oWWWWWwwWWWooo....','......oWWWWWWWWWo......','.......oWWWWWWWWo......','...RR..oWWWWWWWWo..RR..','.RRRRRRoWWWWWWWWoRRRRRR','RRRRRRRRoWWWWWWoRRRRRRR','RRrRRRLBRRRRRRRRBLRRrRR','RRrRRRRRRRRRRRRRRRRrRRR'
            ]
        };

        const MAESTRO_PALETTE = {
            '.': null, o: '#241a12', H: '#4a3320', h: '#33230f', B: '#c69a4c', b: '#8a6329',
            L: '#f2c14e', G: '#8fd0c8', g: '#4f9a91', S: '#e6b184', s: '#c68b5c',
            W: '#efe9dc', w: '#c3bcaa', R: '#5c4326', r: '#3f2c15', C: '#b5703a'
        };

        function renderMaestroSprite(containerId, pose = 'neutral', scale = 3.2) {
            const host = document.getElementById(containerId);
            const map = window.MAESTRO_SPRITES[pose] || window.MAESTRO_SPRITES.neutral;
            if (!host || !map) return;
            const rows = map.length;
            const cols = map[0].length;
            let rects = '';
            map.forEach((row, y) => {
                row.split('').forEach((token, x) => {
                    const fill = MAESTRO_PALETTE[token];
                    if (!fill) return;
                    rects += `<rect x="${x}" y="${y}" width="1.03" height="1.03" fill="${fill}" />`;
                });
            });
            host.innerHTML = `<svg viewBox="0 0 ${cols} ${rows}" width="${cols * scale}" height="${rows * scale}" shape-rendering="crispEdges" style="display:block">${rects}</svg>`;
        }

        let maestroCurrentPose = 'neutral';

        function setMaestroPose(pose) {
            maestroCurrentPose = pose;
            renderMaestroSprite('maestroAmbientSprite', pose, 2.9);
            const introVisible = document.getElementById('maestroIntroOverlay');
            if (introVisible) renderMaestroSprite('maestroIntroSprite', pose === 'neutral' ? 'greeting' : pose, 4.6);
        }

        function ensureMaestroAmbient() {
            const el = document.getElementById('maestroAmbient');
            if (!el) return;
            el.style.display = 'flex';
            if (!document.getElementById('maestroAmbientSprite')?.innerHTML) {
                renderMaestroSprite('maestroAmbientSprite', maestroCurrentPose, 2.9);
            }
        }

        function updateMaestroAmbientState(tabId) {
            ensureMaestroAmbient();
            const bubble = document.getElementById('maestroAmbientBubble');
            const state = {
                draft: { pose: 'pointing', text: 'Segui il lotto: fair price e surplus sono la bussola.' },
                rosters: { pose: 'thoughtful', text: 'Ogni sigillo titolare resta modificabile con un tocco.' },
                listone: { pose: 'pointing', text: 'Occhio al surplus, giovane.' },
                ai: { pose: 'neutral', text: 'Qui gli esperimenti vanno letti con giudizio.' },
                lineup: { pose: 'thoughtful', text: 'Il solver resta separato: la vera lavagna è nelle Rose.' },
                audit: { pose: 'neutral', text: 'Una buona officina misura prima di giudicare.' },
                trades: { pose: 'greeting', text: 'Ogni scambio va pesato come un ingranaggio.' },
                targets: { pose: 'greeting', text: 'Fissa i tuoi obiettivi prima che il mercato corra.' }
            }[tabId] || { pose: 'neutral', text: "Bentornato nell'officina." };
            setMaestroPose(state.pose);
            if (bubble) bubble.textContent = state.text;
        }

        /* ─────────────────────────────────────────────────────────────
           TOAST NOTIFICATIONS
        ───────────────────────────────────────────────────────────── */
        function showToast(message, type = 'info', duration = 3200) {
            const container = document.getElementById('toastContainer');
            if (!container) return;
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            const icon = type === 'success' 
                ? '<i class="fa-solid fa-circle-check" style="color:var(--accent);"></i>' 
                : type === 'danger' 
                    ? '<i class="fa-solid fa-circle-xmark" style="color:#f87171;"></i>' 
                    : type === 'warning' 
                        ? '<i class="fa-solid fa-triangle-exclamation icon-pulse" style="color:var(--gold);"></i>' 
                        : '<i class="fa-solid fa-circle-info" style="color:var(--primary);"></i>';
            toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
            container.appendChild(toast);
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(40px)';
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }

        /* ─────────────────────────────────────────────────────────────
           MARKET INFLATION BADGE & MODAL
        ───────────────────────────────────────────────────────────── */
        function openPlayerDetailDrawer(playerName) {
            const p = (typeof allPlayers !== 'undefined' ? allPlayers : []).find(x => x.player === playerName) ||
                      (typeof allPlayers !== 'undefined' ? allPlayers : []).find(x => (x.player || '').trim().toLowerCase() === (playerName || '').trim().toLowerCase());
            if (!p) {
                console.warn('Player not found for detail drawer:', playerName);
                return;
            }
            _currentDetailPlayer = p;

            // Header
            document.getElementById('pdName').textContent = p.player;
            const roleEl = document.getElementById('pdRole');
            roleEl.textContent = p.role;
            roleEl.className = 'role-badge role-' + p.role.toLowerCase();
            document.getElementById('pdTeam').textContent = p.team || '';

            // Summary bar
            document.getElementById('pdFairPrice').textContent = `${getPlayerFairPrice(p)} cr`;
            document.getElementById('pdVorp').textContent = (p.vorp || 0).toFixed(1);
            document.getElementById('pdScore').textContent = (p.score || 0).toFixed(1);
            document.getElementById('pdFascia').textContent = p.fascia;

            // Econometric Target & Clearing
            const activeB = leagueBudget || 1000;
            const targetPr = activeB === 500 ? (p.target_price_500 || p.price_fair_500 || 1) : (p.target_price_1000 || p.price_fair_1000 || 1);
            const clearPr = activeB === 500 ? (p.clearing_price_500 || targetPr) : (p.clearing_price_1000 || targetPr);
            document.getElementById('pdTargetPrice').textContent = `${targetPr} cr`;
            document.getElementById('pdClearingPrice').textContent = `${clearPr} cr`;
            const surplus = targetPr - clearPr;
            const surpEl = document.getElementById('pdSurplusVal');
            surpEl.textContent = (surplus >= 0 ? '+' : '') + `${surplus} cr`;
            surpEl.style.color = surplus >= 0 ? '#22c55e' : '#ef4444';

            const flags = p.target_flags || '';
            document.getElementById('pdTargetFlags').textContent = flags ? `Fattori: ${flags.replace(/;/g, ' • ')}` : 'Nessun fattore correttivo applicato';
            const badgeEl = document.getElementById('pdClearingSourceBadge');
            if (flags.includes('asta_xlsx')) {
                badgeEl.textContent = 'Asta Reale (1000cr)';
                badgeEl.style.background = 'rgba(34,197,94,0.15)';
                badgeEl.style.color = '#22c55e';
            } else if (flags.includes('fantabot_golden')) {
                badgeEl.textContent = 'Aste Storiche (500cr)';
                badgeEl.style.background = 'rgba(99,102,241,0.15)';
                badgeEl.style.color = '#818cf8';
            } else {
                badgeEl.textContent = 'Stima Target';
                badgeEl.style.background = 'rgba(255,255,255,0.05)';
                badgeEl.style.color = 'var(--text-muted)';
            }

            // Medical
            const med = p.medical || {};
            document.getElementById('pdDaysLost').textContent = med.days_lost_3y || 0;
            document.getElementById('pdInjCount').textContent = med.injuries_count_3y || 0;

            const severeEl = document.getElementById('pdSevere');
            severeEl.innerHTML = med.infortunio_grave 
                ? '<span style="color:#ef4444;"><i class="fa-solid fa-triangle-exclamation icon-pulse" style="margin-right:3px;"></i> Sì</span>' 
                : '<span style="color:#22c55e;"><i class="fa-solid fa-circle-check" style="margin-right:3px;"></i> No</span>';

            const medBadge = document.getElementById('pdMedBadge');
            medBadge.innerHTML = (med.status_badge || '') + ' ' + (med.status_label || 'N/D');
            if (med.status === 'safe') { medBadge.style.background = 'rgba(34,197,94,0.15)'; medBadge.style.color = '#22c55e'; }
            else if (med.status === 'warning') { medBadge.style.background = 'rgba(234,179,8,0.15)'; medBadge.style.color = '#eab308'; }
            else { medBadge.style.background = 'rgba(239,68,68,0.15)'; medBadge.style.color = '#ef4444'; }

            const injList = document.getElementById('pdInjuryList');
            const details = med.dettaglio_infortuni || [];
            if (details.length > 0) {
                injList.innerHTML = details.map(d => `<div style="padding:2px 0; border-bottom:1px solid var(--border);">• ${d}</div>`).join('');
            } else {
                injList.innerHTML = '<div style="color:var(--text-muted); font-style:italic;">Nessun dettaglio disponibile</div>';
            }

            // Understat
            const us = p.understat || {};
            document.getElementById('pdXg90').textContent = (us.xg_per90 || 0).toFixed(3);
            document.getElementById('pdNpxg90').textContent = (us.npxg_per90 || 0).toFixed(3);
            document.getElementById('pdXa90').textContent = (us.xa_per90 || 0).toFixed(3);
            document.getElementById('pdShots90').textContent = (us.shots_per90 || 0).toFixed(2);

            const deltaEl = document.getElementById('pdDeltaXg');
            const deltaVal = us.delta_goals_xg || 0;
            deltaEl.textContent = (deltaVal >= 0 ? '+' : '') + deltaVal.toFixed(2);
            deltaEl.style.color = deltaVal >= 0 ? '#22c55e' : '#ef4444';

            // Quantiles
            const q = p.quantiles || {};
            const p10 = q.floor_p10 || 0, p50 = q.expected_p50 || 0, p90 = q.ceiling_p90 || 0;
            document.getElementById('pdP10').textContent = p10.toFixed(0);
            document.getElementById('pdP50').textContent = p50.toFixed(0);
            document.getElementById('pdP90').textContent = p90.toFixed(0);
            document.getElementById('pdSpread').textContent = (q.spread || 0).toFixed(0);

            const profBadge = document.getElementById('pdProfileBadge');
            profBadge.innerHTML = q.profile_badge || '';
            if ((q.spread || 0) < 135) { profBadge.style.background = 'rgba(99,102,241,0.15)'; profBadge.style.color = '#818cf8'; }
            else { profBadge.style.background = 'rgba(245,158,11,0.15)'; profBadge.style.color = '#f59e0b'; }

            // Quantile visual bar
            const maxPts = Math.max(p90, 350);
            const barLeft = (p10 / maxPts) * 100;
            const barWidth = ((p90 - p10) / maxPts) * 100;
            const p50Pos = (p50 / maxPts) * 100;
            const qBar = document.getElementById('pdQuantileBar');
            qBar.style.left = barLeft + '%';
            qBar.style.width = barWidth + '%';
            qBar.style.background = 'linear-gradient(90deg, #ef4444 0%, var(--gold) 50%, #22c55e 100%)';
            qBar.style.opacity = '0.3';
            document.getElementById('pdQuantileP50Mark').style.left = p50Pos + '%';

            // Starter info
            const starterEl = document.getElementById('pdStarter');
            if (starterEl) {
                starterEl.innerHTML = p.is_starter_2627 
                    ? '<span style="color:#22c55e;"><i class="fa-solid fa-circle-check" style="margin-right:3px;"></i> Sì</span>' 
                    : '<span style="color:#ef4444;"><i class="fa-solid fa-circle-xmark" style="margin-right:3px;"></i> No</span>';
            }
            document.getElementById('pdStarts').textContent = p.starts_2627 || 0;
            document.getElementById('pdMinutes').textContent = (p.minutes_2627 || 0).toLocaleString();

            // Show drawer with slide animation
            const drawer = document.getElementById('playerDetailDrawer');
            if (drawer) {
                drawer.style.display = 'flex';
                drawer.classList.add('active');
                requestAnimationFrame(() => {
                    const panel = document.getElementById('playerDetailPanel');
                    if (panel) panel.style.right = '0px';
                });
            }
        }

        function closePlayerDetailDrawer() {
            const panel = document.getElementById('playerDetailPanel');
            if (panel) panel.style.right = '-480px';
            setTimeout(() => {
                const drawer = document.getElementById('playerDetailDrawer');
                if (drawer) {
                    drawer.style.display = 'none';
                    drawer.classList.remove('active');
                }
            }, 350);
            _currentDetailPlayer = null;
        }

        // Close drawer on backdrop click
        const _detailDrawerEl = document.getElementById('playerDetailDrawer');
        if (_detailDrawerEl) {
            _detailDrawerEl.addEventListener('click', function(e) {
                if (e.target === this) closePlayerDetailDrawer();
            });
        }


        function toggleMobileSidebar() {
            const sb = document.getElementById('appSidebar');
            const bd = document.getElementById('sidebarBackdrop');
            sb.classList.toggle('open');
            bd.classList.toggle('show');
        }

        async function init() {
            await fetchPlayers();
            fetchAIStatus();
            renderListone();

            ensureMaestroAmbient();
            updateMaestroAmbientState('listone');

            runBootSplash(() => maybeShowMaestroIntro());

            if (window.location.hash) {
                const tabName = window.location.hash.replace('#', '');
                if (['ai', 'listone'].includes(tabName)) {
                    switchTab(tabName);
                }
            }
        }

        let leagueBudget = 1000;

        function getPlayerFairPrice(p, budget) {
            if (!p) return 1;
            const b = budget || leagueBudget || 1000;

            // If player object has _budget_scale from API matching this budget
            if (p._budget_scale !== undefined && Math.round(p._budget_scale * 1000) === b) {
                return p.price_fair_scaled || (b === 500 ? (p.price_fair_500 || Math.round(p.price_fair_1000 * 0.5)) : p.price_fair_1000);
            }

            // Accurate benchmark for 500 cr
            if (b === 500) {
                if (p.price_fair_500) return p.price_fair_500;
                if (p.price_fair_1000) return Math.max(1, Math.round(p.price_fair_1000 * 0.5));
            }

            // Accurate benchmark for 1000 cr
            if (b === 1000) {
                if (p.price_fair_1000) return p.price_fair_1000;
            }

            // Proportional scaling for any custom budget
            let base1000 = p.price_fair_1000;
            if (!base1000) {
                if (p._budget_scale && p._budget_scale !== 1.0) {
                    base1000 = Math.round((p.price_fair_scaled || 1) / p._budget_scale);
                } else {
                    base1000 = p.price_fair_scaled || 1;
                }
            }
            return Math.max(1, Math.round(base1000 * (b / 1000.0)));
        }

        async function fetchPlayers() {
            const res = await fetch(`/api/players?budget=${leagueBudget}`);
            const data = await res.json();
            allPlayers = data.players || [];
            if (data.league_budget) leagueBudget = data.league_budget;
            renderListone();
        }

        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.sidebar-nav-btn').forEach(el => el.classList.remove('active'));

            const targetTab = document.getElementById('tab-' + tabId);
            if (targetTab) targetTab.classList.add('active');

            const botBtn = document.getElementById('botNav-' + tabId);
            if (botBtn) botBtn.classList.add('active');

            const sideBtn = document.getElementById('sideNav-' + tabId);
            if (sideBtn) sideBtn.classList.add('active');

            if (typeof updateMaestroAmbientState === 'function') updateMaestroAmbientState(tabId);

            // Close mobile drawer if open
            const sb = document.getElementById('appSidebar');
            const bd = document.getElementById('sidebarBackdrop');
            if (sb && sb.classList.contains('open')) {
                sb.classList.remove('open');
                bd.classList.remove('show');
            }

            if (tabId === 'listone') renderListone();
        }

        function setRoleFilter(role) {
            currentRoleFilter = role;
            document.querySelectorAll('#rolePills .pill').forEach(el => {
                el.classList.toggle('active', el.textContent.includes(role === 'ALL' ? 'Tutti' : role));
            });
            renderListone();
        }

        function setFasciaFilter(f) {
            currentFasciaFilter = f;
            document.querySelectorAll('#fasciaPills .pill').forEach(el => {
                el.classList.toggle('active', el.textContent.includes(f === 'ALL' ? 'Tutte' : f + 'ª'));
            });
            renderListone();
        }

        /* ─────────────────────────────────────────────────────────────
           TACTICAL AI CONVERSATIONAL CHATBOT ENGINE
        ───────────────────────────────────────────────────────────── */
        const AI_AVATAR_HTML = `<div class="chat-msg-avatar" style="width:32px; height:32px; border-radius:50%; background:linear-gradient(135deg, #0284c7, #4f46e5); display:flex; align-items:center; justify-content:center; flex-shrink:0; border:1.5px solid var(--primary);"><svg style="width:16px; height:16px; stroke:#ffffff; fill:none; stroke-width:2;" viewBox="0 0 24 24"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path></svg></div>`;

        function setAIQuery(queryText) {
            document.getElementById('aiInputPrompt').value = queryText;
            submitAIQuery();
        }

        function clearAIChat() {
            const stream = document.getElementById('chatMessagesStream');
            stream.innerHTML = `
                <div class="chat-msg ai">
                    ${AI_AVATAR_HTML}
                    <div class="chat-bubble">
                        <b>Chat azzerata.</b><br>
                        Come posso aiutarti? Chiedimi confronti tra giocatori, diagnosi sul tuo bilancio o scommesse per completare la rosa!
                    </div>
                </div>
            `;
        }

        async function submitAIQuery() {
            const input = document.getElementById('aiInputPrompt');
            const prompt = input.value.trim();
            if (!prompt) return;

            const stream = document.getElementById('chatMessagesStream');
            const btn = document.getElementById('btnSubmitAI');

            // 1. Append User Message Bubble
            const userMsg = document.createElement('div');
            userMsg.className = 'chat-msg user';
            userMsg.innerHTML = `<div class="chat-bubble">${escapeHTML(prompt)}</div>`;
            stream.appendChild(userMsg);

            input.value = '';
            if (btn) btn.disabled = true;

            // 2. Append Temporary Loading Bubble
            const loadingMsg = document.createElement('div');
            loadingMsg.className = 'chat-msg ai';
            loadingMsg.id = 'aiChatLoadingBubble';
            loadingMsg.innerHTML = `
                ${AI_AVATAR_HTML}
                <div class="chat-bubble" style="color:var(--text-muted); font-style:italic;">
                    Sto analizzando i dati del listone, VORP e formazioni reali...
                </div>
            `;
            stream.appendChild(loadingMsg);
            stream.scrollTop = stream.scrollHeight;

            try {
                const res = await fetch('/api/ai_query', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ prompt: prompt })
                });

                if (!res.ok) {
                    const errTxt = await res.text();
                    throw new Error(`Server ${res.status}: ${errTxt.slice(0, 100)}`);
                }

                const data = await res.json();

                // Remove loading bubble
                const loadElem = document.getElementById('aiChatLoadingBubble');
                if (loadElem) loadElem.remove();

                // 3. Append AI Response Bubble
                const aiMsg = document.createElement('div');
                aiMsg.className = 'chat-msg ai';
                aiMsg.innerHTML = `
                    ${AI_AVATAR_HTML}
                    <div class="chat-bubble">
                        ${renderAIChatContent(data)}
                    </div>
                `;
                stream.appendChild(aiMsg);
            } catch(e) {
                console.error("AI Chat Exception:", e);
                const loadElem = document.getElementById('aiChatLoadingBubble');
                if (loadElem) loadElem.remove();

                const errBubble = document.createElement('div');
                errBubble.className = 'chat-msg ai';
                errBubble.innerHTML = `
                    ${AI_AVATAR_HTML}
                    <div class="chat-bubble" style="color:var(--danger); font-size:0.85rem;">
                        <b>Errore di elaborazione:</b> ${escapeHTML(e.message || "Riprova con un'altra domanda.")}
                    </div>
                `;
                stream.appendChild(errBubble);
            }

            if (btn) btn.disabled = false;
            stream.scrollTop = stream.scrollHeight;
        }

        function escapeHTML(str) {
            return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
        }

        function formatMarkdownText(text) {
            if (!text) return '';
            let raw = escapeHTML(text);

            const nl = String.fromCharCode(10);
            // 1. Process Markdown Tables (| col1 | col2 |)
            const lines = raw.split(nl);
            let inTable = false;
            let tableHtml = '';
            let processedLines = [];

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i].trim();
                if (line.startsWith('|') && line.endsWith('|')) {
                    const cells = line.slice(1, -1).split('|').map(c => c.trim());
                    // Skip separator row (|---|---|)
                    if (cells.every(c => /^:?-+:?$/.test(c))) {
                        continue;
                    }
                    if (!inTable) {
                        inTable = true;
                        tableHtml = '<div style="overflow-x:auto; margin:8px 0;"><table class="ai-table" style="width:100%; border-collapse:collapse; font-size:0.80rem; text-align:left;">';
                        tableHtml += '<thead><tr style="border-bottom:1.5px solid var(--border); background:rgba(255,45,117,0.12); color:var(--text-main);">';
                        cells.forEach(c => { tableHtml += `<th style="padding:6px 8px; font-weight:800;">${c}</th>`; });
                        tableHtml += '</tr></thead><tbody>';
                    } else {
                        tableHtml += '<tr style="border-bottom:1px solid rgba(255,255,255,0.06);">';
                        cells.forEach(c => { tableHtml += `<td style="padding:5px 8px;">${c}</td>`; });
                        tableHtml += '</tr>';
                    }
                } else {
                    if (inTable) {
                        tableHtml += '</tbody></table></div>';
                        processedLines.push(tableHtml);
                        inTable = false;
                        tableHtml = '';
                    }
                    processedLines.push(line);
                }
            }
            if (inTable) {
                tableHtml += '</tbody></table></div>';
                processedLines.push(tableHtml);
            }

            let formatted = processedLines.join(nl);
            // Headers
            formatted = formatted.replace(/^### (.*$)/gim, '<h4 style="color:var(--primary); font-size:0.95rem; margin:10px 0 4px 0;">$1</h4>');
            formatted = formatted.replace(/^## (.*$)/gim, '<h3 style="color:var(--text-main); font-size:1.02rem; margin:12px 0 6px 0;">$1</h3>');
            // Bold & Italic
            formatted = formatted.replace(/\\*\\*(.*?)\\*\\*/g, '<b style="color:var(--text-main);">$1</b>');
            formatted = formatted.replace(/\\*(.*?)\\*/g, '<i style="color:var(--text-muted);">$1</i>');
            // Bullet Points
            formatted = formatted.replace(/^\\s*-\\s+(.*$)/gim, '<div style="display:flex; gap:6px; margin-bottom:3px;"><span style="color:var(--primary);">&bull;</span><span>$1</span></div>');
            // Spacing
            formatted = formatted.split(nl + nl).join('<div style="height:8px;"></div>');
            formatted = formatted.split(nl).join('<br>');
            return formatted;
        }

        function renderAIChatContent(data) {
            if (!data) return 'Nessuna risposta disponibile.';
            const engineTag = `<div style="margin-top:8px; padding-top:6px; border-top:1px dashed rgba(255,255,255,0.08); font-size:0.68rem; color:var(--text-muted); display:flex; justify-content:space-between; align-items:center;"><span>Fonte: <b style="color:var(--primary);">${data.engine || 'Regole Tattiche Offline'}</b></span><span>${new Date().toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</span></div>`;

            try {
                if (data.type === 'llm_chat') {
                    return `<div>${formatMarkdownText(data.text || '')}${engineTag}</div>`;
                }

                if (data.type === 'roster_diagnostic') {
                    const s = data.stats || {};
                    const free = s.free_slots || {};
                    return `
                        <div>
                            <div style="font-weight:800; font-size:1.02rem; color:var(--primary); margin-bottom:8px;">${data.title || 'Analisi'}</div>
                            <div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:6px; background:#0b111e; padding:8px 10px; border-radius:8px; margin-bottom:10px; font-size:0.82rem;">
                                <div>Crediti Residui: <b style="color:var(--gold);">${s.remaining || 0} cr</b></div>
                                <div>Max Rilancio: <b style="color:var(--danger);">${s.max_bid || 0} cr</b></div>
                                <div>Slot Liberi: <b>${free.total || 0}</b> (P:${free.P || 0} D:${free.D || 0} C:${free.C || 0} A:${free.A || 0})</div>
                                <div>Media cr/slot: <b>${s.avg_per_slot || 0} cr</b></div>
                            </div>
                            <div style="margin-bottom:8px;">
                                ${(data.advice || []).map(a => `<div style="margin-bottom:4px; font-size:0.85rem;">&bull; ${a}</div>`).join('')}
                            </div>
                            <div style="background:rgba(56,189,248,0.08); border-left:3px solid var(--primary); padding:8px 10px; border-radius:4px; font-size:0.85rem;">
                                ${data.verdict || ''}
                            </div>
                            ${engineTag}
                        </div>
                    `;
                }

                if (data.type === 'comparison') {
                    const players = data.players || [];
                    return `
                        <div>
                            <div style="font-weight:800; font-size:1rem; color:var(--primary); margin-bottom:10px;">${data.title || 'Confronto'}</div>
                            <div style="display:grid; grid-template-columns:${players.length > 2 ? 'repeat(3, 1fr)' : 'repeat(2, 1fr)'}; gap:8px; margin-bottom:10px;">
                                ${players.map(p => `
                                    <div style="background:#0b111e; padding:10px 8px; border-radius:8px; border:1px solid var(--border); font-size:0.82rem;">
                                        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
                                            <span class="badge badge-${p.role}">${p.role}</span>
                                            <b>${p.name}</b>
                                        </div>
                                        <div style="color:var(--text-muted); font-size:0.75rem; margin-bottom:4px;">${p.team} - ${p.starts || 0} start</div>
                                        <div>Punti Attesi: <b>${p.pts_exp || 0} pts</b></div>
                                        <div>Fair Price: <b style="color:var(--gold);">${p.fair_1000 || 1} cr</b></div>
                                        <div>VORP: <b style="color:var(--success);">+${p.vorp || 0}</b></div>
                                    </div>
                                `).join('')}
                            </div>
                            <div style="background:rgba(56,189,248,0.08); border-left:3px solid var(--primary); padding:8px 10px; border-radius:4px; font-size:0.85rem;">
                                ${formatMarkdownText(data.verdict || '')}
                            </div>
                            ${engineTag}
                        </div>
                    `;
                }

                if (data.type === 'player_deepdive') {
                    const p = data.player || {};
                    return `
                        <div>
                            <div style="font-weight:800; font-size:1.02rem; color:var(--gold); margin-bottom:8px;">${data.title}</div>
                            <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; text-align:center; margin-bottom:10px;">
                                <div style="background:#0b111e; padding:8px; border-radius:6px; border:1px solid var(--border);">
                                    <div style="font-size:0.7rem; color:var(--text-muted); font-weight:700;">PROIEZIONE P50</div>
                                    <div style="font-size:1.1rem; font-weight:800; color:var(--primary);">${p.pts_exp || 0} pts</div>
                                </div>
                                <div style="background:#0b111e; padding:8px; border-radius:6px; border:1px solid var(--border);">
                                    <div style="font-size:0.7rem; color:var(--text-muted); font-weight:700;">FAIR PRICE 1000</div>
                                    <div style="font-size:1.1rem; font-weight:800; color:var(--gold);">${p.fair_1000 || 1} cr</div>
                                </div>
                                <div style="background:#0b111e; padding:8px; border-radius:6px; border:1px solid var(--border);">
                                    <div style="font-size:0.7rem; color:var(--text-muted); font-weight:700;">TITOLARITÀ REALE</div>
                                    <div style="font-size:1.1rem; font-weight:800; color:var(--success);">${p.starts || 0} start</div>
                                </div>
                            </div>
                            <div style="background:rgba(56,189,248,0.08); border-left:3px solid var(--gold); padding:8px 10px; border-radius:4px; font-size:0.85rem; margin-bottom:8px;">
                                ${formatMarkdownText(data.verdict || '')}
                            </div>
                            ${engineTag}
                        </div>
                    `;
                }

                if (data.type === 'recommendations') {
                    const players = data.players || [];
                    return `
                        <div>
                            <div style="font-weight:800; font-size:1rem; color:var(--success); margin-bottom:8px;">${data.title}</div>
                            <div style="margin-bottom:10px;">
                                ${players.map(p => `
                                    <div class="candidate-mini-row" style="display:flex; justify-content:space-between; align-items:center; padding:6px 8px; margin-bottom:4px; background:#0b111e; border-radius:6px; border:1px solid var(--border);">
                                        <div style="display:flex; align-items:center; gap:8px;">
                                            <span class="badge badge-${p.role}">${p.role}</span>
                                            <b>${p.name}</b> <small style="color:var(--text-muted);">(${p.team})</small>
                                        </div>
                                        <div style="text-align:right;">
                                            <span style="color:var(--gold); font-weight:800; font-size:0.95rem;">${p.fair_1000} cr</span>
                                            <span style="color:var(--primary); font-size:0.78rem; margin-left:6px;">+${p.vorp} vorp</span>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                            <div style="background:rgba(16,185,129,0.08); border-left:3px solid var(--success); padding:8px 10px; border-radius:4px; font-size:0.85rem;">
                                ${formatMarkdownText(data.verdict || '')}
                            </div>
                            ${engineTag}
                        </div>
                    `;
                }

                // Generic fallback for any unexpected type or structure
                const fallbackText = data.text || data.verdict || JSON.stringify(data);
                return `<div>${formatMarkdownText(fallbackText)}${engineTag}</div>`;
            } catch(renderErr) {
                console.error("renderAIChatContent Error:", renderErr);
                return `<div>${formatMarkdownText(data.text || data.verdict || 'Risposta elaborata.')}${engineTag}</div>`;
            }
        }

        async function fetchAIStatus() {
            try {
                const res = await fetch('/api/ai_status');
                const diag = await res.json();
                const dot = document.getElementById('aiEngineStatusDot');
                const lbl = document.getElementById('aiActiveEngineLabel');
                if (diag.has_llm) {
                    if (dot) dot.className = 'status-dot dot-green';
                    if (lbl) {
                        lbl.textContent = diag.active_engine;
                        lbl.style.color = 'var(--success)';
                    }
                } else {
                    if (dot) dot.className = 'status-dot dot-yellow';
                    if (lbl) {
                        lbl.textContent = 'Fallback Matematico (Nessuna API Key)';
                        lbl.style.color = 'var(--gold)';
                    }
                }
                return diag;
            } catch(e) {
                return null;
            }
        }

        async function openAIDiagnosticsModal() {
            const diag = await fetchAIStatus();
            const modal = document.getElementById('aiDiagnosticsModal');
            if (!modal || !diag) return;

            document.getElementById('diagActiveEngine').textContent = diag.active_engine || 'Nessuno';
            document.getElementById('diagActiveEngineDesc').textContent = diag.has_llm 
                ? 'LLM Cloud attivo: le risposte sono generate con intelligenza artificiale conversazionale.' 
                : 'Attualmente attivo il motore a regole locali: riconosce confronti, schede giocatore, formazioni e diagnosi, ma non genera risposte libere complesse.';

            const badge = document.getElementById('modalAiBadge');
            if (badge) {
                badge.textContent = diag.has_llm ? 'ONLINE' : 'OFFLINE MODE';
                badge.style.color = diag.has_llm ? 'var(--success)' : 'var(--gold)';
            }

            const list = document.getElementById('aiProvidersList');
            if (list && diag.providers) {
                list.innerHTML = Object.entries(diag.providers).map(([k, p]) => `
                    <div style="background:#0b111e; border:1px solid var(--border); border-radius:6px; padding:8px 10px; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <div style="font-weight:700; font-size:0.82rem; color:var(--text-main);">${p.name}</div>
                            <div style="font-size:0.70rem; color:var(--text-muted);">Env Vercel: <code>${p.env_var}</code></div>
                        </div>
                        <span class="badge ${p.configured ? 'badge-D' : 'badge-P'}" style="font-size:0.72rem;">
                            ${p.configured ? '✓ Configurato' : 'Non configurato'}
                        </span>
                    </div>
                `).join('');
            }

            document.getElementById('testAIResult').style.display = 'none';
            modal.classList.add('active');
        }

        function closeAIDiagnosticsModal() {
            const modal = document.getElementById('aiDiagnosticsModal');
            if (modal) modal.classList.remove('active');
        }

        async function testAIConnection() {
            const btn = document.getElementById('btnTestAI');
            const resBox = document.getElementById('testAIResult');
            if (btn) btn.disabled = true;
            if (resBox) {
                resBox.style.display = 'block';
                resBox.innerHTML = '<span style="color:var(--text-muted);">Ping live ai provider in corso...</span>';
            }

            const t0 = performance.now();
            try {
                const res = await fetch('/api/ai_test');
                const testData = await res.json();
                const latency = Math.round(performance.now() - t0);
                
                let details = '';
                if (testData.groq) {
                    details += `<div>Groq: <b style="color:${testData.groq.ok ? 'var(--success)' : 'var(--danger)'};">${testData.groq.msg}</b></div>`;
                }
                if (testData.gemini) {
                    details += `<div>Gemini: <b style="color:${testData.gemini.ok ? 'var(--success)' : 'var(--danger)'};">${testData.gemini.msg}</b></div>`;
                }

                if (resBox) {
                    resBox.innerHTML = `
                        <div style="background:#090d16; border:1px solid var(--border); border-radius:6px; padding:8px; text-align:left; font-size:0.75rem;">
                            <div style="font-weight:800; color:var(--text-main); margin-bottom:4px;">Esito Ping (${latency}ms):</div>
                            ${details}
                        </div>
                    `;
                }
                fetchAIStatus();
            } catch(e) {
                if (resBox) {
                    resBox.innerHTML = `<span style="color:var(--danger); font-weight:700;">✕ Errore di chiamata: ${e.message}</span>`;
                }
            }
            if (btn) btn.disabled = false;
        }

        /* ─────────────────────────────────────────────────────────────
           LISTONE & ANALYTICS TAB
        ───────────────────────────────────────────────────────────── */
        function renderListone() {
            const q = (document.getElementById('listSearch')?.value || '').toLowerCase();
            const activeBudget = leagueBudget || 1000;
            const sortBy = document.getElementById('listSortBy')?.value || 'best';

            const filtered = allPlayers.filter(p => {
                if (currentRoleFilter !== 'ALL' && p.role !== currentRoleFilter) return false;
                if (currentFasciaFilter !== 'ALL' && String(p.fascia) !== String(currentFasciaFilter)) return false;
                if (q && !p.player.toLowerCase().includes(q) && !p.team.toLowerCase().includes(q)) return false;
                return true;
            });

            // Sorting logic (Default: Miglior Giocatore come in Scala Slot)
            filtered.sort((a, b) => {
                if (sortBy === 'best') {
                    const aScore = (parseFloat(a.score) || 0) * 12 + (parseFloat(a.vorp) || 0) * 2 + (a.is_starter_2627 ? 15 : 0) + (parseFloat(a.pts_exp) || 0) * 0.1;
                    const bScore = (parseFloat(b.score) || 0) * 12 + (parseFloat(b.vorp) || 0) * 2 + (b.is_starter_2627 ? 15 : 0) + (parseFloat(b.pts_exp) || 0) * 0.1;
                    return bScore - aScore;
                } else if (sortBy === 'mv_desc') {
                    return (parseFloat(b.mv) || 0) - (parseFloat(a.mv) || 0);
                } else if (sortBy === 'mfv_desc') {
                    return (parseFloat(b.mfv) || 0) - (parseFloat(a.mfv) || 0);
                } else if (sortBy === 'fair_desc') {
                    const aFair = getPlayerFairPrice(a, activeBudget);
                    const bFair = getPlayerFairPrice(b, activeBudget);
                    return bFair - aFair;
                } else if (sortBy === 'fair_asc') {
                    const aFair = getPlayerFairPrice(a, activeBudget);
                    const bFair = getPlayerFairPrice(b, activeBudget);
                    return aFair - bFair;
                } else if (sortBy === 'pts_desc') {
                    return (parseFloat(b.pts_exp) || 0) - (parseFloat(a.pts_exp) || 0);
                } else if (sortBy === 'vorp_desc') {
                    return (parseFloat(b.vorp) || 0) - (parseFloat(a.vorp) || 0);
                } else if (sortBy === 'alpha') {
                    return a.player.localeCompare(b.player);
                }
                return 0;
            });

            const container = document.getElementById('listoneContainer');
            if (!container) return;

            if (!allPlayers || allPlayers.length === 0) {
                container.innerHTML = '<div class="card" style="text-align:center; color:var(--text-muted); padding:24px;">Caricamento calciatori in corso...</div>';
                return;
            }

            if (filtered.length === 0) {
                container.innerHTML = '<div class="card" style="text-align:center; color:var(--text-muted); padding:24px;">Nessun calciatore trovato con i filtri selezionati.</div>';
                return;
            }

            container.innerHTML = filtered.map(p => {
                const fairLive = getPlayerFairPrice(p, activeBudget);

                const isStarter = p.is_starter_2627 === 1 || p.is_starter_2627 === true || p.is_starter_2627 === "1";
                const medDays = (p.medical && p.medical.days_lost_3y) || 0;
                const encPlayer = encodeURIComponent(p.player);
                const medBadge = medDays >= 120 
                    ? `<span class="medical-badge medical-badge-danger" data-player="${encPlayer}" onclick="event.stopPropagation(); openPlayerDetailDrawer(decodeURIComponent(this.getAttribute('data-player')))" title="Finestra Medica: ${medDays} gg infortunio (3 anni)"><i class="fa-solid fa-heart-pulse icon-pulse"></i> ${medDays}gg</span>`
                    : (medDays >= 30 
                        ? `<span class="medical-badge medical-badge-warning" data-player="${encPlayer}" onclick="event.stopPropagation(); openPlayerDetailDrawer(decodeURIComponent(this.getAttribute('data-player')))" title="Finestra Medica: ${medDays} gg infortunio (3 anni)"><i class="fa-solid fa-triangle-exclamation"></i> ${medDays}gg</span>`
                        : `<span class="medical-badge medical-badge-success" data-player="${encPlayer}" onclick="event.stopPropagation(); openPlayerDetailDrawer(decodeURIComponent(this.getAttribute('data-player')))" title="Finestra Medica: Integro (${medDays} gg infortunio)"><i class="fa-solid fa-circle-check"></i> Integro</span>`);

                return `
                    <div class="player-row role-${p.role}">
                        <div class="player-info">
                            <div class="player-name">
                                <span class="badge badge-${p.role}">${p.role}</span>
                                <span style="font-family:'Outfit',sans-serif; font-weight:700; font-size:1.05rem; cursor:pointer;" data-player="${encPlayer}" onclick="openPlayerDetailDrawer(decodeURIComponent(this.getAttribute('data-player')))"> ${p.player}</span>
                                <button data-player="${encPlayer}" onclick="openPlayerDetailDrawer(decodeURIComponent(this.getAttribute('data-player')))"
                                    title="Dettaglio Giocatore" style="background:transparent; border:none; cursor:pointer; font-size:0.85rem; padding:0 3px; color:var(--primary); opacity:0.75; transition:opacity 0.2s;"
                                    onmouseenter="this.style.opacity='1'" onmouseleave="this.style.opacity='0.75'"><i class="fa-solid fa-circle-info"></i></button>
                                <small style="color:var(--text-muted); font-weight:600;">(${p.team})</small>
                                ${medBadge}
                                ${isStarter ? `<span class="scout-tag-starter">✓ Titolare</span>` : ''}
                            </div>
                            <div class="player-meta" style="display:flex; align-items:center; flex-wrap:wrap; gap:6px 10px; margin-top:4px;">
                                <span style="background:rgba(56,189,248,0.12); color:#38bdf8; padding:2px 7px; border-radius:5px; font-size:0.78rem; font-weight:700;">MV: <b>${p.mv || '6.0'}</b></span>
                                <span style="background:rgba(16,185,129,0.12); color:#34d399; padding:2px 7px; border-radius:5px; font-size:0.78rem; font-weight:700;">FM: <b>${p.mfv || '6.0'}</b></span>
                                <span style="color:var(--text-main); font-size:0.78rem; font-weight:600;"><span style="color:var(--gold); font-weight:700;">Bonus:</span> ${p.bonus_range || 'N/D'}</span>
                                <span class="scout-vorp-badge" style="font-size:0.75rem;">VORP +${p.vorp}</span>
                                <small style="color:var(--text-muted); font-size:0.72rem; margin-left:auto;">P50: <b>${p.pts_exp} pt</b> (~${p.expected_matches || 28}p)</small>
                            </div>
                        </div>
                        <div class="player-stats">
                            <div class="scout-price-box">
                                <div class="player-fair" title="Prezzo Fair calcolato sul tuo budget di lega (${activeBudget} cr)">${fairLive} <span style="font-size:0.7rem; font-weight:700;">cr</span></div>
                            </div>
                            <div style="font-size:0.68rem; color:var(--text-muted); margin-top:2px;">
                                su ${activeBudget} cr
                            </div>
                            <div class="player-vorp" style="color:${p.surplus_value > 0 ? 'var(--success)' : 'var(--danger)'}">
                                ${p.surplus_value > 0 ? '+' : ''}${p.surplus_value} cr
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        window.onload = function () {
            init();
            if (typeof FantaTour !== 'undefined') {
                FantaTour.maybeAutoStart();
            }
        };
    </script>
    <button id="maestroAmbient" class="maestro-ambient" type="button" style="display:none;" onclick="FantaTour && FantaTour.start && FantaTour.start()">
        <span class="maestro-ambient__halo"></span>
        <span id="maestroAmbientSprite" class="maestro-ambient__sprite" aria-hidden="true"></span>
        <span id="maestroAmbientBubble" class="maestro-ambient__bubble">Occhio al surplus, giovane.</span>
    </button>
    <script src="/static/js/tutorial.js"></script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(
        HTML_TEMPLATE,
        bot_name=BOT_NAME,
        bot_subtitle=BOT_SUBTITLE,
        bot_avatar_text=BOT_AVATAR_TEXT,
        bot_avatar_image=BOT_AVATAR_IMAGE,
        bot_badge=BOT_BADGE,
        bot_greeting=BOT_GREETING,
        is_personal=IS_PERSONAL
    )


def main():
    import socket
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "127.0.0.1"

    print("\n" + "=" * 70)
    print("  footballerdata — Player Data & Statistics Explorer (Serie A)")
    print("=" * 70)
    print(f"\n  Accesso Desktop: http://localhost:5050")
    print(f"  Accesso Mobile:  http://{local_ip}:5050 (stessa rete Wi-Fi)\n")

    app.run(host="0.0.0.0", port=5050, debug=False)


if __name__ == "__main__":
    main()
