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
    "2. Stratégique / Réglementaire / Éco (à venir)",
    "3. Cybersécurité (à venir)",
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
    st.info("Module 2 (dashboard stratégique/réglementaire/économique) : "
            "à implémenter au sprint suivant.")

with tab3:
    st.info("Module 3 (cybersécurité, arbre d'attaque, cas Viasat) : "
            "à implémenter au sprint suivant.")