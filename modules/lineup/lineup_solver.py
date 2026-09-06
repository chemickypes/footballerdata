"""Weekly Lineup Solver."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

from modules.common.data_provider import compute_weekly_xpts, is_overlay_real

EXCLUDED_STATUSES = {"INFORTUNATO", "SQUALIFICATO"}
FORMATIONS = {
    "3-4-3": (1, 3, 4, 3),
    "3-5-2": (1, 3, 5, 2),
    "4-3-3": (1, 4, 3, 3),
    "4-4-2": (1, 4, 4, 2),
    "4-5-1": (1, 4, 5, 1),
    "5-3-2": (1, 5, 3, 2),
    "5-4-1": (1, 5, 4, 1),
}


def _solve_single_formation(df, n_p, n_d, n_c, n_a):
    n = len(df)
    if n < (n_p + n_d + n_c + n_a):
        return None
    c = -1.0 * df["xpts_week"].fillna(0.0).values
    A = np.vstack([
        (df["role"] == "P").astype(float).values,
        (df["role"] == "D").astype(float).values,
        (df["role"] == "C").astype(float).values,
        (df["role"] == "A").astype(float).values,
        np.ones(n),
    ])
    rhs = np.array([float(n_p), float(n_d), float(n_c), float(n_a), float(n_p + n_d + n_c + n_a)])
    res = milp(c=c, constraints=LinearConstraint(A, rhs, rhs), bounds=Bounds(np.zeros(n), np.ones(n)), integrality=np.ones(n))
    if not res.success:
        return None
    return np.where(res.x > 0.5)[0]


def _bonus_modificatore(df, selected_indices):
    starters = df.iloc[selected_indices]
    defenders = starters[starters["role"] == "D"]
    goalkeepers = starters[starters["role"] == "P"]
    if len(defenders) < 4:
        return 0.0
    top3_def = defenders.nlargest(3, "xpts_week")["xpts_week"].fillna(0.0)
    return float((top3_def.sum() + goalkeepers["xpts_week"].fillna(0.0).sum()) / 4.0)


def solve_lineup(roster, overlay):
    if not is_overlay_real(overlay):
        return {"success": False, "error": "feed_unavailable", "message": "Dati in tempo reale non disponibili (titolarita'/infortuni/quote). Riprova più tardi."}
    if not roster:
        return {"success": False, "error": "no_feasible_formation", "message": "Rosa vuota: nessuna formazione calcolabile."}
    df = pd.DataFrame(roster).fillna({"team": ""})
    df, _ = compute_weekly_xpts(df, overlay)
    if "status" in df.columns:
        df = df[~df["status"].isin(EXCLUDED_STATUSES)].reset_index(drop=True)
    best = None
    for formation_name, (n_p, n_d, n_c, n_a) in FORMATIONS.items():
        selected = _solve_single_formation(df, n_p, n_d, n_c, n_a)
        if selected is None:
            continue
        total_xpts = float(df.iloc[selected]["xpts_week"].fillna(0.0).sum())
        if best is None or total_xpts > best["total_xpts"]:
            best = {"formation": formation_name, "selected": selected, "total_xpts": total_xpts}
    if best is None:
        return {"success": False, "error": "no_feasible_formation", "message": "Nessun modulo regolamentare è schierabile con la rosa attuale (troppi giocatori mancanti/esclusi)."}
    starters = [{"player": r["player"], "role": r["role"], "xpts": round(float(r["xpts_week"] or 0.0), 2)} for _, r in df.iloc[best["selected"]].iterrows()]
    bench_df = df.drop(index=best["selected"]).sort_values("xpts_week", ascending=False, na_position="last")
    bench = [{"player": r["player"], "role": r["role"], "xpts": round(float(r["xpts_week"] or 0.0), 2)} for _, r in bench_df.iterrows()]
    return {"success": True, "formation": best["formation"], "starters": starters, "bench": bench, "total_xpts": round(best["total_xpts"], 2), "bonus_modificatore_expected": round(_bonus_modificatore(df, best["selected"]), 2)}
