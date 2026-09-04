"""
Point d'entrée Streamlit - "L'impact de Starlink, mesuré et cartographié"
Lancement : streamlit run app.py
"""

from datetime import datetime, timedelta, timezone

import streamlit as st

from modules.tle_fetcher import TLEFetcher
from modules.orbital import OrbitalPropagator
from modules.visibility import KNOWN_OBSERVATORIES, simulate_trails
from modules.conjunctions import altitude_density_by_shell, detect_conjunctions
from modules.visualization import (
    trails_polar_chart, debris_density_histogram, conjunction_alert_table,
)

st.set_page_config(page_title="Starlink", layout="wide")
st.title("L'impact de Starlink, mesuré et cartographié")

tab1, tab2, tab3 = st.tabs([
    "1. Environnement & Orbital",
    "2. Stratégique / Réglementaire / Éco",
    "3. Cybersécurité"
])

with tab1:
    st.header("Simulateur de traînées et de débris orbitaux")

    col_params, col_results = st.columns([1, 2])

    with col_params:
        st.subheader("Paramètres")

        group = st.selectbox("Groupe de satellites (CelesTrak)",
                              ["starlink", "active", "debris"], index=0)
        use_sample_data = st.checkbox(
            "Utiliser les données d'exemple hors-ligne (recommandé si pas d'accès "
            "internet ou premier test)", value=True,
        )

        obs_key = st.selectbox("Observatoire", list(KNOWN_OBSERVATORIES.keys()),
                                format_func=lambda k: KNOWN_OBSERVATORIES[k].name)
        observatory = KNOWN_OBSERVATORIES[obs_key]

        date = st.date_input("Date (UTC)", value=datetime(2026, 8, 3))  # Date mise à jour par défaut pour aujourd'hui
        start_hour = st.slider("Heure de début (UTC)", 0, 23, 17)       # Crépuscule pour Brazzaville par défaut
        window_hours = st.slider("Fenêtre d'analyse (heures)", 1, 12, 2)

        st.markdown("---")
        st.caption("Optimisation de la vitesse :")
        
        # NOUVEAU : Curseur pour limiter le nombre de satellites
        max_sats = st.slider(
            "Nombre max de satellites (pour test rapide)", 
            min_value=50, max_value=1000, value=200, step=50
        )
        
        # NOUVEAU : Curseur pour le pas de temps
        step_seconds = st.slider(
            "Pas de temps (secondes)", 
            min_value=15, max_value=300, value=30, step=15
        )
        
        st.caption(f"*Calcul ≈ {int(window_hours * 3600 / step_seconds)} itérations. Réduisez le pas et le nombre pour aller plus vite.*")

        run = st.button("Lancer la simulation", type="primary")

    if run:
        with st.spinner("Récupération des TLE et propagation SGP4..."):
            fetcher = TLEFetcher()
            if use_sample_data:
                records = fetcher.load_from_file("data/samples/test_fixtures.tle")
                st.info("Données d'exemple utilisées (satellites synthétiques de test).")
            else:
                try:
                    records = fetcher.fetch(group)
                except RuntimeError as e:
                    st.error(str(e))
                    st.warning(
                        "CelesTrak limite les groupes 'active'/'starlink' à un "
                        "téléchargement par cycle de 2h. Si vous avez déjà testé "
                        "récemment, cochez la case des données d'exemple en "
                        "attendant, ou réessayez plus tard."
                    )
                    st.stop()

            propagator = OrbitalPropagator(records)

            # NOUVEAU : Application de la limite max de satellites pour le test rapide
            if len(propagator.satellites) > max_sats:
                propagator.satellites = propagator.satellites[:max_sats]
                st.info(f"Simulation limitée à {max_sats} satellites pour accélérer le calcul. (Total disponible : {len(records)})")

            start = datetime(date.year, date.month, date.day, start_hour, 0, 0,
                              tzinfo=timezone.utc)
            end = start + timedelta(hours=window_hours)

            # NOUVEAU : Utilisation du pas de temps personnalisé
            trails = simulate_trails(propagator, observatory, start, end, step_seconds=step_seconds)
            shells = altitude_density_by_shell(propagator, shell_width_km=50)
            alerts = detect_conjunctions(propagator, start, end, step_seconds=step_seconds)

        with col_results:
            st.subheader(f"{len(trails)} traînées détectées")
            st.plotly_chart(trails_polar_chart(trails, observatory.name),
                             use_container_width=True)

            st.subheader("Densité de débris par altitude")
            st.plotly_chart(debris_density_histogram(shells), use_container_width=True)

            st.subheader(f"{len(alerts)} alerte(s) de conjonction")
            st.plotly_chart(conjunction_alert_table(alerts), use_container_width=True)
    else:
        with col_results:
            st.info("Configurez les paramètres puis cliquez sur **Lancer la simulation**.")

with tab2:
    st.header("Enjeux stratégiques, réglementaires et économiques")

    from modules.regulatory import load_regulatory_matrix, filter_matrix
    from modules.economic import (
        load_operators_financials, load_starlink_pricing, filter_financials,
    )
    from modules.geopolitics import load_constellations, load_events, filter_events
    import pandas as pd
    from modules.visualization2 import (
        regulatory_matrix_table, revenue_evolution_chart, cost_comparison_chart,
        constellation_race_chart, constellation_budget_chart, geopolitical_timeline,
        subscribers_growth_chart, kpi_summary,
    )

    reg_df = load_regulatory_matrix()
    fin_df = load_operators_financials()
    pricing_df = load_starlink_pricing()
    const_df = load_constellations()
    events_df = load_events()
    subs_df = pd.read_csv("data/economic/starlink_subscribers.csv")
    restricted_df = pd.read_csv("data/geopolitical/restricted_countries.csv")

    # --- D9 : KPIs en tête de page ---
    kpis = kpi_summary(subs_df, restricted_df)
    kcol1, kcol2, kcol3 = st.columns(3)
    kcol1.metric("Abonnés Starlink", f"{kpis['subscribers_millions']} M",
                 help=f"Données {kpis['year']}")
    kcol2.metric("Pays couverts", kpis["countries_covered"])
    kcol3.metric("Pays restreints/interdits", kpis["countries_restricted"])

    st.plotly_chart(subscribers_growth_chart(subs_df), use_container_width=True)

    st.divider()

    # --- D10 : Filtres interactifs (sidebar dédiée au module) ---
    st.subheader("Filtres")
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        selected_regulators = st.multiselect(
            "Régulateur", options=sorted(reg_df["regulator"].unique()))
    with fcol2:
        year_range = st.slider(
            "Plage d'années (données économiques/géopolitiques)",
            min_value=int(fin_df["year"].min()), max_value=int(fin_df["year"].max()),
            value=(int(fin_df["year"].min()), int(fin_df["year"].max())))
    with fcol3:
        selected_constellations = st.multiselect(
            "Constellation", options=sorted(const_df["constellation"].unique()))

    st.divider()

    # --- D5 : Matrice réglementaire ---
    st.subheader("Matrice réglementaire comparée")
    filtered_reg = filter_matrix(reg_df, regulators=selected_regulators or None)
    st.plotly_chart(regulatory_matrix_table(filtered_reg), use_container_width=True)

    # --- D6 : Graphiques économiques ---
    st.subheader("Impact économique")
    filtered_fin = filter_financials(fin_df, year_min=year_range[0], year_max=year_range[1])
    ecol1, ecol2 = st.columns(2)
    with ecol1:
        st.plotly_chart(revenue_evolution_chart(filtered_fin), use_container_width=True)
    with ecol2:
        st.plotly_chart(cost_comparison_chart(pricing_df), use_container_width=True)

    # --- D7 : Course aux constellations ---
    st.subheader("La course aux constellations")
    filtered_const = (const_df[const_df["constellation"].isin(selected_constellations)]
                       if selected_constellations else const_df)
    ccol1, ccol2 = st.columns(2)
    with ccol1:
        st.plotly_chart(constellation_race_chart(filtered_const), use_container_width=True)
    with ccol2:
        st.plotly_chart(constellation_budget_chart(filtered_const), use_container_width=True)
    st.dataframe(filtered_const, use_container_width=True)

    # --- D8 : Frise géopolitique ---
    st.subheader("Frise géopolitique : usages militaires et souveraineté")
    filtered_events = filter_events(events_df, year_min=year_range[0], year_max=year_range[1])
    st.plotly_chart(geopolitical_timeline(filtered_events), use_container_width=True)

    with st.expander("Zones non desservies / restreintes (détail par pays)"):
        st.dataframe(restricted_df, use_container_width=True)


with tab3:
    st.header("Cybersécurité des systèmes LEO")

    from modules.threat_model import (
        load_attack_tree, load_stride_matrix, get_viasat_path, filter_stride,
    )
    from modules.case_study import load_viasat_case_study, filter_case_study
    from modules.visualization3 import attack_tree_diagram, stride_heatmap, viasat_timeline

    tree_df = load_attack_tree()
    stride_df = load_stride_matrix()
    case_df = load_viasat_case_study()

    st.subheader("Arbre d'attaque : systèmes LEO")
    st.caption("Survolez un nœud pour voir sa description et sa mitigation. "
               "La branche en rouge/gras est le chemin réellement emprunté lors "
               "de l'incident Viasat KA-SAT (février 2022).")
    st.plotly_chart(attack_tree_diagram(tree_df), use_container_width=True)

    with st.expander("Détail du chemin d'attaque réel (cas Viasat)"):
        viasat_path = get_viasat_path(tree_df)
        for _, row in viasat_path.iterrows():
            st.markdown(f"{'　' * row['depth']}**→ {row['label']}**  \n"
                        f"{'　' * row['depth']}*{row['description']}*")

    st.divider()

    st.subheader("Matrice STRIDE")
    scol1, scol2 = st.columns(2)
    with scol1:
        selected_components = st.multiselect(
            "Composant", options=sorted(stride_df["component"].unique()))
    with scol2:
        selected_categories = st.multiselect(
            "Catégorie STRIDE", options=sorted(stride_df["stride_category"].unique()))

    filtered_stride = filter_stride(stride_df, components=selected_components or None,
                                     categories=selected_categories or None)
    st.plotly_chart(stride_heatmap(filtered_stride), use_container_width=True)
    st.dataframe(filtered_stride, use_container_width=True)

    st.divider()

    st.subheader("Étude de cas : Viasat KA-SAT (février 2022)")
    selected_phases = st.multiselect("Filtrer par phase", options=sorted(case_df["phase"].unique()))
    filtered_case = filter_case_study(case_df, phases=selected_phases or None)
    st.plotly_chart(viasat_timeline(filtered_case), use_container_width=True)
    st.dataframe(filtered_case[["event_datetime", "phase", "event", "ttp_mitre"]],
                 use_container_width=True)
