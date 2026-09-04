"""
Chargement et validation de l'arbre d'attaque et de la matrice STRIDE.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

ATTACK_TREE_PATH = Path(__file__).resolve().parent.parent / "data" / "cyber" / "attack_tree.csv"
STRIDE_PATH = Path(__file__).resolve().parent.parent / "data" / "cyber" / "stride_matrix.csv"


def load_attack_tree(path: Path = ATTACK_TREE_PATH) -> pd.DataFrame:
    """
    Charge l'arbre d'attaque et valide son intégrité référentielle :
    - chaque parent_id (sauf racine) doit exister comme node_id
    - un seul nœud racine (parent_id vide)
    - pas de node_id dupliqué
    """
    df = pd.read_csv(path)

    required = {"node_id", "parent_id", "label", "node_type", "gate", "segment", "viasat_case"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans {path.name} : {missing}")

    node_ids = set(df["node_id"])
    parent_ids = set(df["parent_id"].dropna())
    orphans = parent_ids - node_ids
    if orphans:
        raise ValueError(f"parent_id référençant des nœuds inexistants : {orphans}")

    roots = df[df["parent_id"].isna()]
    if len(roots) != 1:
        raise ValueError(f"L'arbre doit avoir exactement 1 racine, trouvé {len(roots)}")

    if df["node_id"].duplicated().any():
        dupes = df.loc[df["node_id"].duplicated(), "node_id"].tolist()
        raise ValueError(f"node_id dupliqué(s) : {dupes}")

    return df


def load_stride_matrix(path: Path = STRIDE_PATH) -> pd.DataFrame:
    """Charge la matrice STRIDE et vérifie la cohérence avec l'arbre d'attaque."""
    df = pd.read_csv(path)

    valid_categories = {"Spoofing", "Tampering", "Repudiation",
                         "Information Disclosure", "Denial of Service", "Elevation of Privilege"}
    invalid_categories = set(df["stride_category"]) - valid_categories
    if invalid_categories:
        raise ValueError(f"Catégories STRIDE invalides : {invalid_categories}")

    tree = load_attack_tree()
    valid_nodes = set(tree["node_id"])
    invalid_refs = set(df["related_attack_node"].dropna()) - valid_nodes
    if invalid_refs:
        raise ValueError(f"related_attack_node référençant des nœuds inexistants : {invalid_refs}")

    return df


def build_tree_children_map(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Retourne {parent_id: [child_id, ...]} pour parcourir l'arbre."""
    children: Dict[str, List[str]] = {}
    for _, row in df.iterrows():
        if pd.notna(row["parent_id"]):
            children.setdefault(row["parent_id"], []).append(row["node_id"])
    return children


def get_root_id(df: pd.DataFrame) -> str:
    return df.loc[df["parent_id"].isna(), "node_id"].iloc[0]


def get_viasat_path(df: pd.DataFrame) -> pd.DataFrame:
    """
    Retourne les nœuds marqués comme faisant partie du chemin d'attaque réel
    observé dans le cas Viasat KA-SAT (viasat_case == 'oui'), triés selon la
    profondeur dans l'arbre (racine en premier).
    """
    viasat_nodes = df[df["viasat_case"] == "oui"].copy()

    depth_map: Dict[str, int] = {}

    def compute_depth(node_id: str) -> int:
        if node_id in depth_map:
            return depth_map[node_id]
        row = df.loc[df["node_id"] == node_id].iloc[0]
        if pd.isna(row["parent_id"]):
            depth_map[node_id] = 0
        else:
            depth_map[node_id] = compute_depth(row["parent_id"]) + 1
        return depth_map[node_id]

    viasat_nodes["depth"] = viasat_nodes["node_id"].apply(compute_depth)
    return viasat_nodes.sort_values("depth")


def filter_stride(df: pd.DataFrame, components: Optional[List[str]] = None,
                   categories: Optional[List[str]] = None,
                   min_severity: Optional[List[str]] = None) -> pd.DataFrame:
    """Filtre la matrice STRIDE (filtres interactifs)."""
    result = df
    if components:
        result = result[result["component"].isin(components)]
    if categories:
        result = result[result["stride_category"].isin(categories)]
    if min_severity:
        result = result[result["severity"].isin(min_severity)]
    return result


if __name__ == "__main__":
    tree = load_attack_tree()
    stride = load_stride_matrix()
    print(f"{len(tree)} nœuds dans l'arbre d'attaque, racine = {get_root_id(tree)}")
    print(f"{len(stride)} entrées STRIDE")
    print("\n--- Chemin d'attaque réel (cas Viasat) ---")
    for _, row in get_viasat_path(tree).iterrows():
        print(f"  {'  ' * row['depth']}└─ {row['label']}")
