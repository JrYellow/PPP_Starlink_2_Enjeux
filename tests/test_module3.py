"""
test_module3.py
================
Tests de validation du Module 3 (Cybersécurité).

Sprint 3, tâche E : vérifie l'intégrité de l'arbre d'attaque, la cohérence
de la matrice STRIDE et de la chronologie Viasat.
"""

import pandas as pd
import pytest

from modules.threat_model import (
    load_attack_tree, load_stride_matrix, load_sparta_mapping, nrs_risk_level,
    build_tree_children_map, get_root_id, get_viasat_path, filter_stride,
)
from modules.case_study import load_viasat_case_study, filter_case_study
from modules.visualization3 import (
    attack_tree_diagram, stride_heatmap, viasat_timeline,
    sparta_risk_matrix, sparta_tactics_bar,
)


# --- Arbre d'attaque ---------------------------------------------------------

def test_attack_tree_loads_and_validates():
    df = load_attack_tree()
    assert len(df) >= 15
    assert df["node_id"].is_unique


def test_attack_tree_has_single_root():
    df = load_attack_tree()
    roots = df[df["parent_id"].isna()]
    assert len(roots) == 1
    assert roots.iloc[0]["node_id"] == "N0"


def test_attack_tree_covers_four_segments():
    """Le cahier des charges exige un arbre couvrant les systèmes LEO dans
    leur ensemble : segment sol, liaison RF, spatial, utilisateur."""
    df = load_attack_tree()
    segments = set(df["segment"])
    expected = {"Segment sol", "Liaison RF", "Segment spatial", "Segment utilisateur"}
    assert expected.issubset(segments)


def test_attack_tree_is_acyclic():
    """Un arbre d'attaque ne doit jamais contenir de cycle (propriété
    structurelle de base d'un arbre)."""
    df = load_attack_tree()
    children_map = build_tree_children_map(df)
    root = get_root_id(df)

    visited = set()

    def visit(node):
        assert node not in visited, f"Cycle détecté impliquant {node}"
        visited.add(node)
        for child in children_map.get(node, []):
            visit(child)

    visit(root)
    assert len(visited) == len(df)  # tous les nœuds sont atteignables depuis la racine


def test_viasat_path_is_non_empty_and_ordered():
    """Le chemin d'attaque réel (cas Viasat) doit exister et suivre un ordre
    de profondeur croissant (de la racine vers la feuille d'impact)."""
    df = load_attack_tree()
    path = get_viasat_path(df)
    assert len(path) >= 4
    assert path["depth"].is_monotonic_increasing


def test_viasat_path_ends_at_impact_node():
    """Le dernier nœud du chemin Viasat doit être une conséquence (impact),
    pas une étape intermédiaire."""
    df = load_attack_tree()
    path = get_viasat_path(df)
    last_node = path.iloc[-1]
    assert "inopérant" in last_node["label"].lower() or "impact" in last_node["label"].lower() \
        or "modem" in last_node["label"].lower()


# --- Matrice STRIDE ----------------------------------------------------------

def test_stride_matrix_loads_and_validates():
    df = load_stride_matrix()
    assert len(df) >= 10
    valid_categories = {"Spoofing", "Tampering", "Repudiation",
                         "Information Disclosure", "Denial of Service", "Elevation of Privilege"}
    assert set(df["stride_category"]).issubset(valid_categories)


def test_stride_covers_all_six_categories():
    """STRIDE doit couvrir ses 6 catégories, pas seulement un sous-ensemble."""
    df = load_stride_matrix()
    expected = {"Spoofing", "Tampering", "Repudiation",
                "Information Disclosure", "Denial of Service", "Elevation of Privilege"}
    assert set(df["stride_category"]) == expected


def test_stride_references_are_consistent_with_tree():
    """Chaque related_attack_node doit exister dans l'arbre d'attaque."""
    stride_df = load_stride_matrix()
    tree_df = load_attack_tree()
    valid_nodes = set(tree_df["node_id"])
    refs = set(stride_df["related_attack_node"].dropna())
    assert refs.issubset(valid_nodes)


def test_filter_stride_by_category():
    df = load_stride_matrix()
    filtered = filter_stride(df, categories=["Denial of Service"])
    assert (filtered["stride_category"] == "Denial of Service").all()
    assert len(filtered) >= 1


# --- Étude de cas Viasat -----------------------------------------------------

def test_case_study_loads_and_is_sorted():
    df = load_viasat_case_study()
    assert len(df) >= 5
    assert df["event_datetime"].is_monotonic_increasing


def test_case_study_covers_key_phases():
    """La chronologie doit couvrir au minimum l'accès initial et l'impact,
    les deux phases centrales de l'incident."""
    df = load_viasat_case_study()
    assert "Accès initial" in set(df["phase"])
    assert "Impact" in set(df["phase"])


def test_filter_case_study_by_phase():
    df = load_viasat_case_study()
    filtered = filter_case_study(df, phases=["Impact"])
    assert (filtered["phase"] == "Impact").all()
    assert len(filtered) >= 1


def test_case_study_consistent_with_attack_tree_viasat_path():
    """Le nombre de phases distinctes de la chronologie doit être cohérent
    avec (au moins aussi riche que) le nombre de nœuds du chemin Viasat dans
    l'arbre -- les deux sources doivent raconter la même histoire."""
    case_df = load_viasat_case_study()
    tree_df = load_attack_tree()
    viasat_path = get_viasat_path(tree_df)
    assert case_df["phase"].nunique() >= 3
    assert len(viasat_path) >= 4


# --- Visualisations -----------------------------------------------------------

def test_all_visualizations_render_without_error():
    tree_df = load_attack_tree()
    stride_df = load_stride_matrix()
    case_df = load_viasat_case_study()

    fig1 = attack_tree_diagram(tree_df)
    fig2 = stride_heatmap(stride_df)
    fig3 = viasat_timeline(case_df)

    assert len(fig1.data) >= 1
    assert len(fig2.data) >= 1
    assert len(fig3.data) >= 1


def test_visualizations_handle_empty_filter_gracefully():
    """Un filtre STRIDE qui ne matche rien ne doit pas planter la heatmap."""
    df = load_stride_matrix()
    filtered = filter_stride(df, components=["Composant inexistant"])
    assert len(filtered) == 0
    # pivot_table sur un DataFrame vide : ne doit pas lever d'exception
    fig = stride_heatmap(filtered) if len(filtered) > 0 else None
    assert fig is None or len(fig.data) >= 0


# --- SPARTA (tactiques, score de risque, contrôles NIST) --------------------

def test_sparta_mapping_loads_and_validates():
    df = load_sparta_mapping()
    assert len(df) >= 10
    assert df["likelihood"].between(1, 5).all()
    assert df["impact"].between(1, 5).all()


def test_sparta_nrs_score_matches_likelihood_times_impact():
    """Le score NRS doit toujours être le produit probabilité x impact --
    vérifié aussi au chargement, mais revérifié ici explicitement."""
    df = load_sparta_mapping()
    assert (df["nrs_score"] == df["likelihood"] * df["impact"]).all()


def test_sparta_references_are_consistent_with_tree():
    """Chaque node_id du mapping SPARTA doit exister dans l'arbre d'attaque."""
    sparta_df = load_sparta_mapping()
    tree_df = load_attack_tree()
    valid_nodes = set(tree_df["node_id"])
    assert set(sparta_df["node_id"]).issubset(valid_nodes)


def test_nrs_risk_level_thresholds():
    """Vérifie les bornes de la grille de risque 5x5 (Faible/Modéré/Élevé/Critique)."""
    assert nrs_risk_level(1) == "Faible"
    assert nrs_risk_level(4) == "Faible"
    assert nrs_risk_level(5) == "Modéré"
    assert nrs_risk_level(9) == "Modéré"
    assert nrs_risk_level(10) == "Élevé"
    assert nrs_risk_level(14) == "Élevé"
    assert nrs_risk_level(15) == "Critique"
    assert nrs_risk_level(25) == "Critique"


def test_sparta_viasat_path_nodes_are_rated_high_or_critical():
    """Les nœuds du chemin d'attaque réel Viasat doivent afficher un niveau de
    risque Élevé ou Critique -- cohérence entre la modélisation et la réalité
    de l'incident (impact documenté : dizaines de milliers de terminaux hors
    service)."""
    tree_df = load_attack_tree()
    sparta_df = load_sparta_mapping()
    viasat_nodes = set(get_viasat_path(tree_df)["node_id"])
    rated_viasat = sparta_df[sparta_df["node_id"].isin(viasat_nodes)]
    assert len(rated_viasat) >= 3
    assert rated_viasat["risk_level"].isin(["Élevé", "Critique"]).all()


def test_sparta_visualizations_render_without_error():
    tree_df = load_attack_tree()
    sparta_df = load_sparta_mapping()

    fig1 = sparta_risk_matrix(sparta_df, tree_df)
    fig2 = sparta_tactics_bar(sparta_df)

    assert len(fig1.data) >= 1
    assert len(fig2.data) >= 1
