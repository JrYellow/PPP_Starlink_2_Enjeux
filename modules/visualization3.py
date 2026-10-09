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


# --- SPARTA : matrice de risque 5x5 (probabilité x impact) -----------------

def sparta_risk_matrix(sparta_df: pd.DataFrame, tree_df: pd.DataFrame) -> go.Figure:
    """
    Matrice de risque 5x5 (probabilité en abscisse, impact en ordonnée),
    façon NRS (Notional Risk Score) de SPARTA. Chaque cellule affiche le
    nombre de nœuds de l'arbre d'attaque tombant dans cette combinaison.
    """
    merged = sparta_df.merge(tree_df[["node_id", "label"]], on="node_id")

    grid = pd.DataFrame(0, index=range(1, 6), columns=range(1, 6))
    labels_grid = {(l, i): [] for l in range(1, 6) for i in range(1, 6)}
    for _, row in merged.iterrows():
        grid.loc[row["impact"], row["likelihood"]] += 1
        labels_grid[(row["impact"], row["likelihood"])].append(row["label"])

    text = [[("<br>".join(labels_grid[(impact, lik)]) if labels_grid[(impact, lik)] else "")
             for lik in range(1, 6)] for impact in range(1, 6)]

    fig = go.Figure(data=go.Heatmap(
        z=grid.values, x=list(range(1, 6)), y=list(range(1, 6)),
        text=text, hovertemplate="Probabilité: %{x}<br>Impact: %{y}<br>%{text}<extra></extra>",
        colorscale=[[0, "#ecf0f1"], [0.3, "#d5f5e3"], [0.55, "#f9e79f"],
                    [0.75, "#f5b041"], [1, "#c0392b"]],
        showscale=False,
    ))
    # Annoter chaque cellule avec son score NRS et son nombre de nœuds
    annotations = []
    for impact in range(1, 6):
        for lik in range(1, 6):
            score = impact * lik
            count = grid.loc[impact, lik]
            level = "Critique" if score >= 15 else "Élevé" if score >= 10 else \
                    "Modéré" if score >= 5 else "Faible"
            txt = f"NRS={score}" + (f"<br>({count})" if count > 0 else "")
            annotations.append(dict(x=lik, y=impact, text=txt, showarrow=False,
                                     font=dict(size=10, color="#2c3e50")))
    fig.update_layout(
        title="Matrice de risque SPARTA (probabilité x impact, échelle NRS)",
        xaxis=dict(title="Probabilité (1=faible, 5=élevée)", dtick=1, range=[0.5, 5.5]),
        yaxis=dict(title="Impact (1=faible, 5=catastrophique)", dtick=1, range=[0.5, 5.5]),
        annotations=annotations, height=500,
    )
    return fig


def sparta_tactics_bar(sparta_df: pd.DataFrame) -> go.Figure:
    """Nombre de vecteurs d'attaque par tactique SPARTA, coloré par niveau de risque dominant."""
    df = sparta_df.copy()
    order = ["Faible", "Modéré", "Élevé", "Critique"]
    risk_colors = {"Faible": "#2ecc71", "Modéré": "#f1c40f", "Élevé": "#e67e22", "Critique": "#c0392b"}

    fig = go.Figure()
    for level in order:
        subset = df[df["risk_level"] == level]
        if subset.empty:
            continue
        counts = subset.groupby("sparta_tactic_name").size()
        fig.add_trace(go.Bar(name=level, x=counts.index, y=counts.values,
                              marker_color=risk_colors[level]))
    fig.update_layout(
        title="Vecteurs d'attaque par tactique SPARTA, par niveau de risque",
        barmode="stack", yaxis_title="Nombre de vecteurs", height=400,
    )
    return fig
