"""
test_orbital.py
===============
Tests de validation du Module 1 (Environnement & Orbital).

Sprint 1, étape 9 : Tester et valider les calculs avec des cas connus
(ex. observatoire de Mauna Kea).

Ces tests utilisent des fixtures TLE synthétiques (data/samples/test_fixtures.tle)
générées avec un checksum TLE valide, mais ne représentant PAS de vrais
satellites. Ils valident la CORRECTION DES CALCULS (SGP4, géométrie solaire,
détection de traînées/conjonctions), pas l'exactitude d'une position Starlink
réelle -- pour cela, il faut lancer les mêmes fonctions avec un TLE CelesTrak
à jour (cf. modules/tle_fetcher.py).
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from modules.tle_fetcher import TLEFetcher
from modules.orbital import OrbitalPropagator, EARTH_RADIUS_KM
from modules.solar import solar_elevation_deg, sun_position_eci_km
from modules.visibility import (
    KNOWN_OBSERVATORIES, simulate_trails, apparent_magnitude, _phase_function,
)
from modules.conjunctions import altitude_density_by_shell, detect_conjunctions

FIXTURES_PATH = Path(__file__).resolve().parent.parent / "data" / "samples" / "test_fixtures.tle"


@pytest.fixture(scope="module")
def propagator():
    fetcher = TLEFetcher()
    records = fetcher.load_from_file(FIXTURES_PATH)
    assert len(records) == 3, "Les 3 fixtures TLE de test doivent être chargées"
    return OrbitalPropagator(records)


# --- Tests géométrie solaire ------------------------------------------------

def test_sun_distance_within_realistic_range():
    """La distance Terre-Soleil doit rester proche de 1 UA (149.6M km ± 3%)."""
    when = datetime(2026, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
    x, y, z = sun_position_eci_km(when)
    distance = (x**2 + y**2 + z**2) ** 0.5
    assert 146_000_000 < distance < 153_000_000  # périhélie ~147.1M, aphélie ~152.1M km


def test_mauna_kea_known_dark_hour():
    """
    Validation avec un cas connu : à minuit local (~10:00 UTC) à Mauna Kea,
    le Soleil doit être largement sous l'horizon (nuit noire, pas crépuscule).
    Mauna Kea (UTC-10) : minuit local = 10:00 UTC.
    """
    obs = KNOWN_OBSERVATORIES["mauna_kea"]
    midnight_utc = datetime(2026, 3, 20, 10, 0, 0, tzinfo=timezone.utc)  # ~équinoxe
    elevation = solar_elevation_deg(midnight_utc, obs.latitude_deg, obs.longitude_deg)
    assert elevation < -30, (
        f"À minuit local par équinoxe, le Soleil doit être bien sous l'horizon "
        f"(obtenu : {elevation:.1f}°)"
    )


def test_mauna_kea_known_noon_hour():
    """À midi local (~22:00 UTC la veille / 20:00 UTC selon saison) le Soleil
    doit être haut dans le ciel (élévation positive et significative)."""
    obs = KNOWN_OBSERVATORIES["mauna_kea"]
    noon_utc = datetime(2026, 3, 20, 20, 0, 0, tzinfo=timezone.utc)  # ~midi local
    elevation = solar_elevation_deg(noon_utc, obs.latitude_deg, obs.longitude_deg)
    assert elevation > 40, f"Le Soleil doit être haut à midi local (obtenu : {elevation:.1f}°)"


# --- Tests propagation SGP4 --------------------------------------------------

def test_propagated_altitude_matches_leo_range(propagator):
    """Les satellites de test LEO doivent rester dans une plage d'altitude réaliste."""
    when = datetime(2026, 1, 30, 12, 0, 0, tzinfo=timezone.utc)
    positions = propagator.all_positions_at(when)
    for pos in positions:
        assert 150 < pos.altitude_km < 2000, (
            f"{pos.name} : altitude hors plage LEO ({pos.altitude_km:.0f} km)"
        )


def test_position_is_deterministic(propagator):
    """Deux appels à la même date doivent donner exactement la même position
    (propriété de base d'un propagateur déterministe)."""
    when = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
    pos1 = propagator.position_at(propagator.satellites[0], when)
    pos2 = propagator.position_at(propagator.satellites[0], when)
    assert pos1.eci_position_km == pos2.eci_position_km


# --- Tests visibilité / magnitude -------------------------------------------

def test_phase_function_bounds():
    """La fonction de phase doit valoir 1 en phase nulle (pleine illumination)
    et tendre vers 0 en contre-jour (phase = pi)."""
    import math
    assert _phase_function(0.0) == pytest.approx(1.0, abs=1e-6)
    assert _phase_function(math.pi) == pytest.approx(0.0, abs=1e-6)


def test_apparent_magnitude_brighter_when_closer():
    """Un satellite plus proche doit apparaître plus brillant (magnitude plus faible)."""
    import math
    mag_close = apparent_magnitude(distance_km=500, phase_angle_rad=math.radians(30))
    mag_far = apparent_magnitude(distance_km=1500, phase_angle_rad=math.radians(30))
    assert mag_close < mag_far


def test_simulate_trails_detects_known_pass(propagator):
    """
    Cas de validation Mauna Kea : sur la fenêtre où un passage a été identifié
    manuellement (05:09-05:11 UTC le 30/01/2026), le simulateur doit détecter
    au moins une traînée pour TEST-SAT-1.
    """
    obs = KNOWN_OBSERVATORIES["mauna_kea"]
    start = datetime(2026, 1, 30, 5, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=20)
    trails = simulate_trails(propagator, obs, start, end, step_seconds=30)
    assert len(trails) > 0, "Le passage connu au-dessus de Mauna Kea doit être détecté"
    assert any("TEST-SAT-1" in t.satellite_name for t in trails)


# --- Tests débris / conjonctions --------------------------------------------

def test_altitude_density_shells_sum_to_total_count(propagator):
    """La somme des objets sur toutes les tranches doit égaler le nombre total
    de satellites chargés (aucune perte/duplication dans le binning)."""
    shells = altitude_density_by_shell(propagator, shell_width_km=50,
                                        min_altitude_km=0, max_altitude_km=3000)
    total_binned = sum(s.object_count for s in shells)
    assert total_binned == len(propagator.satellites)


def test_conjunction_detected_between_close_satellites(propagator):
    """
    TEST-SAT-1 et TEST-SAT-2 ont été construits pour rester proches (même
    inclinaison/altitude, RAAN décalé de 0.05°) : une conjonction doit être
    détectée avec un seuil suffisamment large.
    """
    start = datetime(2026, 1, 30, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=6)
    alerts = detect_conjunctions(propagator, start, end, step_seconds=30, threshold_km=50.0)
    assert len(alerts) >= 1
    pair_names = {alerts[0].object_a, alerts[0].object_b}
    assert any("TEST-SAT-1" in n for n in pair_names)
    assert any("TEST-SAT-2" in n for n in pair_names)


def test_conjunction_alert_risk_level_consistent_with_distance(propagator):
    """Le niveau de risque retourné doit être cohérent avec les seuils définis."""
    from modules.conjunctions import (
        CONJUNCTION_THRESHOLD_HIGH_RISK_KM, CONJUNCTION_THRESHOLD_MODERATE_RISK_KM,
    )
    start = datetime(2026, 1, 30, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=6)
    alerts = detect_conjunctions(propagator, start, end, step_seconds=30, threshold_km=50.0)
    for a in alerts:
        if a.min_distance_km <= CONJUNCTION_THRESHOLD_HIGH_RISK_KM:
            assert a.risk_level == "high"
        elif a.min_distance_km <= CONJUNCTION_THRESHOLD_MODERATE_RISK_KM:
            assert a.risk_level == "moderate"
