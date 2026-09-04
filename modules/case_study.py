"""
Chargement et validation de la chronologie de l'étude de cas Viasat KA-SAT.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

CASE_STUDY_PATH = Path(__file__).resolve().parent.parent / "data" / "cyber" / "viasat_case_study.csv"

VALID_PHASES = {
    "Contexte", "Accès initial", "Découverte / Mouvement latéral", "Impact",
    "Attribution", "Communication officielle", "Réponse gouvernementale", "Suivi",
}


def load_viasat_case_study(path: Path = CASE_STUDY_PATH) -> pd.DataFrame:
    """Charge la chronologie Viasat KA-SAT, triée et validée."""
    df = pd.read_csv(path, parse_dates=["event_datetime"])

    required = {"event_datetime", "phase", "event"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans {path.name} : {missing}")

    if df[["event_datetime", "phase", "event"]].isnull().any().any():
        raise ValueError("Valeurs manquantes dans les colonnes critiques de la chronologie")

    invalid_phases = set(df["phase"]) - VALID_PHASES
    if invalid_phases:
        raise ValueError(f"Phases inconnues détectées : {invalid_phases}")

    return df.sort_values("event_datetime").reset_index(drop=True)


def filter_case_study(df: pd.DataFrame, phases: Optional[List[str]] = None) -> pd.DataFrame:
    """Filtre la chronologie par phase (filtre interactif)."""
    if phases:
        return df[df["phase"].isin(phases)]
    return df


if __name__ == "__main__":
    df = load_viasat_case_study()
    print(f"{len(df)} événements chargés, {df['phase'].nunique()} phases distinctes")
    print(df[["event_datetime", "phase"]].to_string(index=False))
