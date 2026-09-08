"""
footballerdata — /api/players endpoint
Player list payload: prices, quality scores, medical audit, Understat volumes,
quantile projections, starter status.
"""

import pandas as pd
from flask import Blueprint, jsonify, request

from web.config import DEFAULT_BUDGET, DEFAULT_ROSTER_SLOTS, DEFAULT_N_TEAMS, INJURIES_CACHE
from web.data import load_dataset
from web.pricing import get_dynamic_fair_prices

players_bp = Blueprint("players", __name__)


@players_bp.route("/api/players")
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
        inj_info = INJURIES_CACHE.get(p_name, {})
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
