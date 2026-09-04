"""
Chargement et validation de la matrice réglementaire comparée (UIT, FCC, ARCEP, ARTP, OFCOM).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "regulatory" / "regulatory_matrix.csv"

REQUIRED_COLUMNS = {
    "regulator", "country_zone", "legal_framework", "starlink_status",
    "conditions_imposed", "date_status", "source_url", "date_maj",
}


def load_regulatory_matrix(path: Path = DATA_PATH) -> pd.DataFrame:
    """Charge la matrice réglementaire et valide sa structure minimale."""
    df = pd.read_csv(path, parse_dates=["date_status", "date_maj"])

    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(f"Colonnes manquantes dans {path.name} : {missing_cols}")

    critical_cols = ["regulator", "country_zone", "starlink_status"]
    if df[critical_cols].isnull().any().any():
        raise ValueError(f"Valeurs manquantes dans les colonnes critiques {critical_cols}")

    return df


def filter_matrix(df: pd.DataFrame, regulators: list[str] | None = None,
                   statuses: list[str] | None = None) -> pd.DataFrame:
    """Filtre la matrice par régulateur et/ou statut, pour les filtres interactifs (D10)."""
    result = df
    if regulators:
        result = result[result["regulator"].isin(regulators)]
    if statuses:
        result = result[result["starlink_status"].isin(statuses)]
    return result


if __name__ == "__main__":
    df = load_regulatory_matrix()
    print(f"{len(df)} entrées réglementaires chargées et validées")
    print(df[["regulator", "country_zone", "starlink_status"]].to_string(index=False))
