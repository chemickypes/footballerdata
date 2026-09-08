"""
footballerdata — dataset access layer
Loads the player dataset and assigns market value tiers (fasce).
"""

import pandas as pd

from web.config import DATA_PATH


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
