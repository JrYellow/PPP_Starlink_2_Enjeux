"""
Visualisations du Module 3 : arbre d'attaque interactif (avec branche Viasat
mise en évidence), heatmap STRIDE, frise chronologique de l'étude de cas.

"""

from __future__ import annotations

import networkx as nx
import pandas as pd
import plotly.graph_objects as go

SEGMENT_COLORS = {
    "Global": "#7f8c8d",
    "Segment sol": "#e74c3c",
    "Liaison RF": "#3498db",
    "Segment spatial": "#9b59b6",
    "Segment utilisateur": "#2ecc71",
}

SEVERITY_ORDER = {"Critique": 3, "Élevée": 2, "Moyenne": 1, "Faible": 0}


# --- D : Arbre d'attaque interactif -----------------------------------------

def _build_graph(tree_df: pd.DataFrame) -> nx.DiGraph:
    graph = nx.DiGraph()
    for _, row in tree_df.iterrows():
        graph.add_node(row["node_id"], **row.to_dict())
    for _, row in tree_df.iterrows():
        if pd.notna(row["parent_id"]):
            graph.add_edge(row["parent_id"], row["node_id"])
    return graph


def _hierarchical_layout(graph: nx.DiGraph, root: str) -> dict:
    """
    Positionnement hiérarchique manuel (niveau = profondeur, x = ordre parmi
    les frères/sœurs). Évite une dépendance à graphviz/pygraphviz.
    """
    levels: dict[str, int] = {root: 0}
    order: dict[int, list] = {0: [root]}

    for node in nx.bfs_tree(graph, root):
        if node == root:
            continue
        parent = list(graph.predecessors(node))[0]
        levels[node] = levels[parent] + 1
        order.setdefault(levels[node], []).append(node)

    positions = {}
    for depth, nodes in order.items():
        n = len(nodes)
        for i, node in enumerate(nodes):
            x = (i - (n - 1) / 2)
            positions[node] = (x, -depth)
    return positions


def attack_tree_diagram(tree_df: pd.DataFrame) -> go.Figure:
    """
    Diagramme de l'arbre d'attaque : nœuds colorés par segment, branche
    réellement empruntée dans le cas Viasat mise en évidence en rouge/gras.
    """
    root = tree_df.loc[tree_df["parent_id"].isna(), "node_id"].iloc[0]
    graph = _build_graph(tree_df)
    pos = _hierarchical_layout(graph, root)

    fig = go.Figure()

    for parent, child in graph.edges():
        x0, y0 = pos[parent]
        x1, y1 = pos[child]
        is_viasat_edge = (graph.nodes[parent]["viasat_case"] == "oui"
                           and graph.nodes[child]["viasat_case"] == "oui")
        fig.add_trace(go.Scatter(
            x=[x0, x1], y=[y0, y1], mode="lines",
            line=dict(color="#c0392b" if is_viasat_edge else "#bdc3c7",
                      width=3 if is_viasat_edge else 1),
            hoverinfo="skip", showlegend=False,
        ))

    node_x = [pos[n][0] for n in graph.nodes()]
    node_y = [pos[n][1] for n in graph.nodes()]
    node_colors = [SEGMENT_COLORS.get(graph.nodes[n]["segment"], "#95a5a6") for n in graph.nodes()]
    node_line_colors = ["#c0392b" if graph.nodes[n]["viasat_case"] == "oui" else "white"
                         for n in graph.nodes()]
    node_line_widths = [3 if graph.nodes[n]["viasat_case"] == "oui" else 1
                         for n in graph.nodes()]
    node_labels = [graph.nodes[n]["label"] for n in graph.nodes()]
    node_hover = [
        f"<b>{graph.nodes[n]['label']}</b><br>Segment: {graph.nodes[n]['segment']}<br>"
        f"{graph.nodes[n].get('description', '')}<br>"
        f"<i>Mitigation: {graph.nodes[n].get('mitigation', 'N/A')}</i>"
        for n in graph.nodes()
    ]

    fig.add_trace(go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        marker=dict(size=22, color=node_colors,
                    line=dict(color=node_line_colors, width=node_line_widths)),
        text=[label[:22] + "…" if len(label) > 22 else label for label in node_labels],
        textposition="bottom center", textfont=dict(size=9),
        hovertext=node_hover, hoverinfo="text",
        showlegend=False,
    ))

    fig.update_layout(
        title="Arbre d'attaque : systèmes LEO (branche réelle Viasat KA-SAT en rouge)",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        height=650, plot_bgcolor="white",
    )
    return fig


# --- D : Matrice STRIDE (heatmap) -------------------------------------------

def stride_heatmap(stride_df: pd.DataFrame) -> go.Figure:
    """Heatmap composant x catégorie STRIDE, couleur = sévérité."""
    df = stride_df.copy()
    df["severity_rank"] = df["severity"].map(SEVERITY_ORDER)

    pivot = df.pivot_table(index="component", columns="stride_category",
                            values="severity_rank", aggfunc="max")

    hover_text = df.pivot_table(index="component", columns="stride_category",
                                 values="threat_description", aggfunc="first")

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values, x=pivot.columns, y=pivot.index,
        colorscale=[[0, "#d5f5e3"], [0.33, "#f9e79f"], [0.66, "#f5b041"], [1, "#c0392b"]],
        text=hover_text.reindex(index=pivot.index, columns=pivot.columns).values,
        hovertemplate="<b>%{y}</b><br>%{x}<br>%{text}<extra></extra>",
        colorbar=dict(title="Sévérité", tickvals=[0, 1, 2, 3],
                      ticktext=["Faible", "Moyenne", "Élevée", "Critique"]),
    ))
    fig.update_layout(title="Matrice STRIDE par composant du système LEO", height=450)
    return fig


# --- D : Frise chronologique Viasat -----------------------------------------

PHASE_COLORS = {
    "Contexte": "#95a5a6",
    "Accès initial": "#e67e22",
    "Découverte / Mouvement latéral": "#f39c12",
    "Impact": "#c0392b",
    "Attribution": "#3498db",
    "Communication officielle": "#2980b9",
    "Réponse gouvernementale": "#8e44ad",
    "Suivi": "#7f8c8d",
}


def viasat_timeline(case_df: pd.DataFrame) -> go.Figure:
    """Frise chronologique de l'incident Viasat KA-SAT, colorée par phase."""
    df = case_df.sort_values("event_datetime").copy()
    colors = df["phase"].map(PHASE_COLORS).fillna("#95a5a6")

    fig = go.Figure(data=go.Scatter(
        x=df["event_datetime"], y=[1] * len(df), mode="markers",
        marker=dict(size=18, color=colors, line=dict(color="white", width=1)),
        customdata=df[["phase", "event", "ttp_mitre"]],
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>"
                      "TTP: %{customdata[2]}<extra></extra>",
    ))
    fig.update_layout(
        title="Chronologie de l'incident Viasat KA-SAT (février-mars 2022)",
        yaxis=dict(visible=False, range=[0, 2]),
        xaxis_title="Date", height=300,
    )
    return fig
