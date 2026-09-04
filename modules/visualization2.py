"""
Visualisations du Module 2 : matrice réglementaire interactive, graphiques
économiques, course aux constellations, frise géopolitique, KPIs.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# --- D5 : Matrice réglementaire interactive ---------------------------------

def regulatory_matrix_table(df: pd.DataFrame) -> go.Figure:
    """Tableau interactif de la matrice réglementaire, coloré par statut."""
    status_colors = {
        "Autorisé": "#2ecc71",
        "Coordonné": "#2ecc71",
        "En déploiement (souverain)": "#3498db",
        "Dépôt concurrent": "#f1c40f",
        "Marketing suspendu / licence en attente": "#e74c3c",
    }
    colors = df["starlink_status"].map(status_colors).fillna("#95a5a6")

    fig = go.Figure(data=go.Table(
        header=dict(values=["Régulateur", "Pays/Zone", "Statut Starlink", "Conditions imposées"],
                    fill_color="#2c3e50", font=dict(color="white"), align="left"),
        cells=dict(
            values=[df["regulator"], df["country_zone"], df["starlink_status"],
                    df["conditions_imposed"]],
            fill_color=[colors] * 4, align="left",
        ),
    ))
    fig.update_layout(title="Matrice réglementaire comparée (UIT, FCC, ARCEP, ARTP, OFCOM)")
    return fig


# --- D6 : Graphiques économiques --------------------------------------------

def revenue_evolution_chart(df: pd.DataFrame) -> go.Figure:
    """Évolution du CA par opérateur dans le temps (ligne), Starlink vs GEO/MEO classiques."""
    fig = px.line(df.sort_values("year"), x="year", y="revenue_musd", color="operator",
                   markers=True,
                   labels={"year": "Année", "revenue_musd": "Chiffre d'affaires (M$)",
                           "operator": "Opérateur"})
    fig.update_layout(title="Évolution du chiffre d'affaires : Starlink vs opérateurs GEO/MEO")
    return fig


def cost_comparison_chart(df: pd.DataFrame) -> go.Figure:
    """Comparaison des coûts d'abonnement mensuel par offre/zone (bar chart)."""
    fig = px.bar(df.sort_values("subscription_price_usd_month"),
                 x="offer", y="subscription_price_usd_month", color="country_zone",
                 labels={"offer": "Offre", "subscription_price_usd_month": "Abonnement (USD/mois)",
                         "country_zone": "Pays/Zone"})
    fig.update_layout(title="Comparaison des coûts d'abonnement (Starlink vs VSAT classique)")
    return fig


# --- D7 : Course aux constellations -----------------------------------------

def constellation_race_chart(df: pd.DataFrame) -> go.Figure:
    """Satellites actifs vs prévus, par constellation (barres groupées)."""
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Satellites actifs", x=df["constellation"], y=df["satellites_active"],
                          marker_color="#2ecc71"))
    fig.add_trace(go.Bar(name="Satellites prévus (total)", x=df["constellation"],
                          y=df["satellites_planned"], marker_color="#95a5a6", opacity=0.6))
    fig.update_layout(
        title="La course aux constellations : satellites actifs vs prévus",
        barmode="overlay", yaxis_title="Nombre de satellites", yaxis_type="log",
    )
    return fig


def constellation_budget_chart(df: pd.DataFrame) -> go.Figure:
    """Budget des projets institutionnels (là où le chiffre est public)."""
    df_budget = df.dropna(subset=["budget_musd"])
    fig = px.bar(df_budget, x="constellation", y="budget_musd", color="country_bloc",
                 labels={"budget_musd": "Budget (M$)", "constellation": "Constellation"})
    fig.update_layout(title="Budget des constellations (données publiques disponibles)")
    return fig


# --- D8 : Frise géopolitique -------------------------------------------------

def geopolitical_timeline(df: pd.DataFrame) -> go.Figure:
    """Frise chronologique des événements militaires/souveraineté."""
    category_colors = {
        "Militaire": "#e74c3c",
        "Militaire / Souveraineté": "#c0392b",
        "Militaire / Contrat": "#e67e22",
        "Souveraineté / Réponse institutionnelle": "#3498db",
    }
    df = df.sort_values("event_date").copy()
    colors = df["category"].map(category_colors).fillna("#95a5a6")

    fig = go.Figure(data=go.Scatter(
        x=df["event_date"], y=[1] * len(df), mode="markers+text",
        marker=dict(size=16, color=colors),
        text=df["event"], textposition="top center",
        hovertext=df["description_courte"], hoverinfo="text",
    ))
    fig.update_layout(
        title="Frise chronologique : Starlink, usages militaires et souveraineté",
        yaxis=dict(visible=False, range=[0, 2]),
        xaxis_title="Date",
        height=350,
    )
    return fig


# --- D9 : Indicateurs clés (KPIs) -------------------------------------------

def subscribers_growth_chart(df: pd.DataFrame) -> go.Figure:
    """Croissance des abonnés Starlink et de la couverture pays dans le temps."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["year"], y=df["subscribers_millions"], name="Abonnés (millions)",
                              yaxis="y1", mode="lines+markers", line=dict(color="#3498db")))
    fig.add_trace(go.Scatter(x=df["year"], y=df["countries_covered"], name="Pays couverts",
                              yaxis="y2", mode="lines+markers", line=dict(color="#2ecc71")))
    fig.update_layout(
        title="Croissance Starlink : abonnés et couverture géographique",
        yaxis=dict(title="Abonnés (millions)"),
        yaxis2=dict(title="Pays couverts", overlaying="y", side="right"),
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


def kpi_summary(subscribers_df: pd.DataFrame, restricted_df: pd.DataFrame) -> dict:
    """Résumé chiffré pour affichage en cartes KPI (st.metric)."""
    latest = subscribers_df.sort_values("year").iloc[-1]
    return {
        "subscribers_millions": latest["subscribers_millions"],
        "countries_covered": int(latest["countries_covered"]),
        "countries_restricted": restricted_df["country"].nunique(),
        "year": int(latest["year"]),
    }
