"""
Visualisations du Module 1 : carte des traînées, histogramme densité débris,
alertes de conjonction.

"""

from __future__ import annotations

from typing import List

import pandas as pd
import plotly.graph_objects as go

from modules.conjunctions import AltitudeShell, ConjunctionAlert
from modules.visibility import VisibleTrail


def trails_polar_chart(trails: List[VisibleTrail], observatory_name: str = "") -> go.Figure:
    """
    Carte polaire (azimut/élévation) des traînées observées, façon "vue du ciel"
    depuis l'observatoire. Chaque point = une détection ; la couleur encode la
    magnitude apparente (plus sombre/plus petit = plus brillant = plus gênant).
    """
    if not trails:
        fig = go.Figure()
        fig.update_layout(title=f"Aucune traînée détectée ({observatory_name})")
        return fig

    df = pd.DataFrame([{
        "azimuth": t.satellite_azimuth_deg,
        "elevation": t.satellite_elevation_deg,
        "magnitude": t.apparent_magnitude,
        "satellite": t.satellite_name,
        "time": t.time_utc,
    } for t in trails])

    # En coordonnées polaires astronomiques, le rayon représente 90-élévation
    # (zénith au centre, horizon en bord de cercle).
    df["r"] = 90 - df["elevation"]

    fig = go.Figure(data=go.Scatterpolar(
        r=df["r"], theta=df["azimuth"], mode="markers",
        marker=dict(
            size=8, color=df["magnitude"], colorscale="Viridis_r",
            colorbar=dict(title="Magnitude apparente"),
        ),
        text=[f"{row.satellite}<br>{row.time}<br>mag={row.magnitude:.2f}"
              for row in df.itertuples()],
        hoverinfo="text",
    ))
    fig.update_layout(
        title=f"Traînées de satellites observées - {observatory_name}",
        polar=dict(radialaxis=dict(range=[0, 90], showticklabels=True,
                                    ticksuffix="° du zénith")),
    )
    return fig


def debris_density_histogram(shells: List[AltitudeShell]) -> go.Figure:
    """Histogramme de la densité d'objets par tranche d'altitude."""
    df = pd.DataFrame([{
        "altitude_label": f"{s.altitude_min_km:.0f}-{s.altitude_max_km:.0f} km",
        "altitude_mid": (s.altitude_min_km + s.altitude_max_km) / 2,
        "count": s.object_count,
        "density": s.density_per_km3,
    } for s in shells])

    fig = go.Figure(data=go.Bar(
        x=df["altitude_mid"], y=df["density"],
        text=df["count"], hovertemplate="Altitude ~%{x} km<br>Densité: %{y:.2e}/km³"
                                          "<br>Objets: %{text}<extra></extra>",
    ))
    fig.update_layout(
        title="Densité d'objets par tranche d'altitude (LEO)",
        xaxis_title="Altitude (km)",
        yaxis_title="Densité (objets / km³)",
    )
    return fig


def conjunction_alert_table(alerts: List[ConjunctionAlert]) -> go.Figure:
    """Tableau des alertes de conjonction, coloré par niveau de risque."""
    if not alerts:
        fig = go.Figure()
        fig.update_layout(title="Aucune conjonction détectée sur la fenêtre analysée")
        return fig

    df = pd.DataFrame([{
        "Objet A": a.object_a, "Objet B": a.object_b,
        "Date/heure (UTC)": a.time_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "Distance min (km)": round(a.min_distance_km, 3),
        "Risque": a.risk_level,
    } for a in sorted(alerts, key=lambda x: x.min_distance_km)])

    colors = df["Risque"].map({"high": "#ff4d4d", "moderate": "#ffd24d"}).tolist()

    fig = go.Figure(data=go.Table(
        header=dict(values=list(df.columns), fill_color="#2c3e50",
                    font=dict(color="white"), align="left"),
        cells=dict(values=[df[c] for c in df.columns],
                   fill_color=[colors] * len(df.columns), align="left"),
    ))
    fig.update_layout(title="Alertes de conjonction")
    return fig
