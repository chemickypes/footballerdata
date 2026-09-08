"""
footballerdata — VORP / fair-price quality scoring
Replacement-level analysis + power-law scarcity pricing, calibrated to a
fixed reference economy (budget / roster slots / number of teams).
"""

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
