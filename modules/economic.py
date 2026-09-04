"""
Chargement et traitement des données économiques : revenus opérateurs,
tarification Starlink.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FINANCIALS_PATH = Path(__file__).resolve().parent.parent / "data" / "economic" / "operators_financials.csv"
PRICING_PATH = Path(__file__).resolve().parent.parent / "data" / "economic" / "starlink_pricing.csv"


def load_operators_financials(path: Path = FINANCIALS_PATH) -> pd.DataFrame:
    """Charge les données financières des opérateurs (GEO/MEO/LEO)."""
    df = pd.read_csv(path)
    if df[["operator", "year", "revenue_musd"]].isnull().any().any():
        raise ValueError("Valeurs manquantes dans les colonnes critiques operator/year/revenue_musd")
    if not df["year"].between(2015, 2030).all():
        raise ValueError("Année hors plage plausible (2015-2030) détectée")
    return df


def load_starlink_pricing(path: Path = PRICING_PATH) -> pd.DataFrame:
    """Charge la grille tarifaire Starlink (et comparatif VSAT)."""
    df = pd.read_csv(path)
    if df[["offer", "country_zone", "subscription_price_usd_month"]].isnull().any().any():
        raise ValueError("Valeurs manquantes dans les colonnes critiques de la tarification")
    return df


def filter_financials(df: pd.DataFrame, operators: list[str] | None = None,
                       year_min: int | None = None, year_max: int | None = None) -> pd.DataFrame:
    """Filtre par opérateur et/ou plage d'années (filtres interactifs D10)."""
    result = df
    if operators:
        result = result[result["operator"].isin(operators)]
    if year_min is not None:
        result = result[result["year"] >= year_min]
    if year_max is not None:
        result = result[result["year"] <= year_max]
    return result


def revenue_growth_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule la croissance du CA entre la première et la dernière année
    """
    rows = []
    for operator, group in df.groupby("operator"):
        group_sorted = group.sort_values("year")
        first, last = group_sorted.iloc[0], group_sorted.iloc[-1]
        if first["revenue_musd"] and first["revenue_musd"] != 0:
            growth_pct = (last["revenue_musd"] - first["revenue_musd"]) / first["revenue_musd"] * 100
        else:
            growth_pct = float("nan")
        rows.append({
            "operator": operator,
            "year_first": int(first["year"]), "revenue_first_musd": first["revenue_musd"],
            "year_last": int(last["year"]), "revenue_last_musd": last["revenue_musd"],
            "growth_pct": round(growth_pct, 1),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    financials = load_operators_financials()
    pricing = load_starlink_pricing()
    print(f"{len(financials)} lignes financières, {len(pricing)} offres tarifaires chargées")
    print("\n--- Croissance du CA par opérateur ---")
    print(revenue_growth_summary(financials).to_string(index=False))
