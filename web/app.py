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
from flask import Flask, jsonify, request, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # web/ — templates/ and static/ live here
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


@app.route("/")
def index():
    return render_template(
        "index.html",
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
