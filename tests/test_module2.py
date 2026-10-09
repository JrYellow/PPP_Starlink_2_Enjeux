"""
test_module2.py
================
Tests de validation du Module 2 (Stratégique, Réglementaire & Économique).

Sprint 2, tâche E : vérifie l'intégrité des CSV et la cohérence des
fonctions de traitement (chargement, filtres, visualisations).
"""

import pandas as pd
import pytest

from modules.regulatory import load_regulatory_matrix, filter_matrix
from modules.economic import (
    load_operators_financials, load_starlink_pricing, filter_financials,
    revenue_growth_summary,
)
from modules.geopolitics import load_constellations, load_events, filter_events
from modules.visualization2 import (
    regulatory_matrix_table, revenue_evolution_chart, cost_comparison_chart,
    constellation_race_chart, constellation_budget_chart, geopolitical_timeline,
    subscribers_growth_chart, kpi_summary,
)


# --- Chargement / intégrité des données -------------------------------------

def test_regulatory_matrix_loads_and_validates():
    df = load_regulatory_matrix()
    assert len(df) >= 5
    assert df["regulator"].notna().all()
    assert set(["UIT", "FCC", "ARCEP", "ARTP", "OFCOM"]).issubset(set(df["regulator"]))


def test_operators_financials_years_are_plausible():
    df = load_operators_financials()
    assert df["year"].between(2015, 2030).all()
    assert (df["revenue_musd"] > 0).all()


def test_starlink_pricing_loads():
    df = load_starlink_pricing()
    assert len(df) >= 5
    assert (df["subscription_price_usd_month"] > 0).all()


def test_constellations_data_internally_consistent():
    """Le nombre de satellites actifs ne doit jamais dépasser le nombre prévu."""
    df = load_constellations()
    assert (df["satellites_active"] <= df["satellites_planned"]).all()
    assert set(["Starlink", "Guowang", "IRIS²"]).issubset(set(df["constellation"]))


def test_events_are_chronologically_sorted_after_load():
    df = load_events()
    assert df["event_date"].is_monotonic_increasing


def test_subscribers_data_is_monotonically_increasing():
    """Le nombre d'abonnés Starlink doit croître dans le temps (pas de régression)."""
    df = pd.read_csv("data/economic/starlink_subscribers.csv")
    df_sorted = df.sort_values("year")
    assert df_sorted["subscribers_millions"].is_monotonic_increasing
    assert df_sorted["countries_covered"].is_monotonic_increasing


# --- Filtres ------------------------------------------------------------

def test_filter_matrix_by_regulator():
    df = load_regulatory_matrix()
    filtered = filter_matrix(df, regulators=["FCC"])
    assert len(filtered) == 1
    assert filtered.iloc[0]["regulator"] == "FCC"


def test_filter_financials_by_year_range():
    df = load_operators_financials()
    filtered = filter_financials(df, year_min=2023, year_max=2024)
    assert filtered["year"].between(2023, 2024).all()


def test_filter_events_by_category():
    df = load_events()
    filtered = filter_events(df, categories=["Militaire"])
    assert (filtered["category"] == "Militaire").all()
    assert len(filtered) >= 1


# --- Cohérence métier -----------------------------------------------------

def test_revenue_growth_starlink_is_positive_and_largest():
    """Starlink doit afficher la plus forte croissance relative du secteur
    (argument central du Module 2)."""
    df = load_operators_financials()
    summary = revenue_growth_summary(df)
    starlink_growth = summary.loc[summary["operator"] == "SpaceX Starlink", "growth_pct"].iloc[0]
    other_growths = summary.loc[summary["operator"] != "SpaceX Starlink", "growth_pct"]
    assert starlink_growth > 0
    assert starlink_growth > other_growths.max()


def test_starlink_has_more_active_satellites_than_any_competitor():
    df = load_constellations()
    starlink_active = df.loc[df["constellation"] == "Starlink", "satellites_active"].iloc[0]
    others_active = df.loc[df["constellation"] != "Starlink", "satellites_active"]
    assert starlink_active > others_active.max()


# --- Visualisations (ne doivent pas lever d'exception, doivent avoir des données) ---

def test_all_visualizations_render_without_error():
    reg_df = load_regulatory_matrix()
    fin_df = load_operators_financials()
    pricing_df = load_starlink_pricing()
    const_df = load_constellations()
    events_df = load_events()
    subs_df = pd.read_csv("data/economic/starlink_subscribers.csv")
    restricted_df = pd.read_csv("data/geopolitical/restricted_countries.csv")

    figs = [
        regulatory_matrix_table(reg_df),
        revenue_evolution_chart(fin_df),
        cost_comparison_chart(pricing_df),
        constellation_race_chart(const_df),
        constellation_budget_chart(const_df),
        geopolitical_timeline(events_df),
        subscribers_growth_chart(subs_df),
    ]
    for fig in figs:
        assert len(fig.data) >= 1

    kpis = kpi_summary(subs_df, restricted_df)
    assert kpis["subscribers_millions"] > 0
    assert kpis["countries_covered"] > 0
    assert kpis["countries_restricted"] > 0


def test_regulatory_matrix_handles_empty_filter_gracefully():
    """Un filtre qui ne matche rien ne doit pas planter la visualisation."""
    df = load_regulatory_matrix()
    filtered = filter_matrix(df, regulators=["Régulateur inexistant"])
    assert len(filtered) == 0
    fig = regulatory_matrix_table(filtered)  # ne doit pas lever d'exception
    assert fig is not None
