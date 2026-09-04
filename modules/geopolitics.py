"""
Chargement et traitement des données géopolitiques : comparaison des
méga-constellations, chronologie des événements militaires/souveraineté.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

CONSTELLATIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "geopolitical" / "constellations_comparison.csv"
EVENTS_PATH = Path(__file__).resolve().parent.parent / "data" / "geopolitical" / "military_soft_power_events.csv"


def load_constellations(path: Path = CONSTELLATIONS_PATH) -> pd.DataFrame:
    """Charge le comparatif des méga-constellations (course aux constellations)."""
    df = pd.read_csv(path)
    critical = ["constellation", "operator", "satellites_active", "satellites_planned"]
    if df[critical].isnull().any().any():
        raise ValueError(f"Valeurs manquantes dans les colonnes critiques {critical}")
    if (df["satellites_active"] < 0).any() or (df["satellites_planned"] < 0).any():
        raise ValueError("Nombre de satellites négatif détecté (incohérence de données)")
    if (df["satellites_active"] > df["satellites_planned"]).any():
        raise ValueError("Nombre de satellites actifs supérieur au nombre prévu (incohérence)")
    return df


def load_events(path: Path = EVENTS_PATH) -> pd.DataFrame:
    """Charge la chronologie des événements militaires/souveraineté."""
    df = pd.read_csv(path, parse_dates=["event_date", "date_maj"])
    if df[["event_date", "event", "category"]].isnull().any().any():
        raise ValueError("Valeurs manquantes dans les colonnes critiques de la chronologie")
    return df.sort_values("event_date")


def filter_events(df: pd.DataFrame, categories: list[str] | None = None,
                   year_min: int | None = None, year_max: int | None = None) -> pd.DataFrame:
    """Filtre la chronologie par catégorie et/ou plage d'années"""
    result = df
    if categories:
        result = result[result["category"].isin(categories)]
    if year_min is not None:
        result = result[result["event_date"].dt.year >= year_min]
    if year_max is not None:
        result = result[result["event_date"].dt.year <= year_max]
    return result


if __name__ == "__main__":
    constellations = load_constellations()
    events = load_events()
    print(f"{len(constellations)} constellations, {len(events)} événements chargés")
    print("\n--- Course aux constellations ---")
    print(constellations[["constellation", "satellites_active", "satellites_planned"]]
          .to_string(index=False))
    print("\n--- Chronologie ---")
    print(events[["event_date", "event"]].to_string(index=False))
