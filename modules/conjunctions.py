"""
Comptage de conjonctions (alertes si distance < seuil) et densité de débris
par tranche d'altitude.

"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List

import numpy as np
from skyfield.api import EarthSatellite

from modules.orbital import EARTH_RADIUS_KM, OrbitalPropagator, _TS

# Seuils de criticité (km), alignés indicativement sur les pratiques
# opérationnelles "red/yellow/green" utilisées par les opérateurs de
# constellations et le suivi du 18th Space Defense Squadron.
CONJUNCTION_THRESHOLD_HIGH_RISK_KM = 1.0
CONJUNCTION_THRESHOLD_MODERATE_RISK_KM = 5.0

# Marge d'altitude (km) pour ne comparer que des objets du même régime,
# afin de limiter le coût du screening pairwise.
ALTITUDE_BAND_MARGIN_KM = 50.0


@dataclass
class ConjunctionAlert:
    object_a: str
    object_b: str
    time_utc: datetime
    min_distance_km: float
    risk_level: str  # "high", "moderate"


@dataclass
class AltitudeShell:
    altitude_min_km: float
    altitude_max_km: float
    object_count: int
    density_per_km3: float


def _mean_altitude_km(satellite: EarthSatellite) -> float:
    """Altitude moyenne approximative à partir des éléments orbitaux (a, e)."""
    mean_motion_rad_per_min = satellite.model.no_kozai  # rad/min
    mu_earth = 398600.4418  # km^3/s^2 (paramètre gravitationnel terrestre)
    n_rad_per_s = mean_motion_rad_per_min / 60.0
    semi_major_axis_km = (mu_earth / (n_rad_per_s ** 2)) ** (1.0 / 3.0)
    return semi_major_axis_km - EARTH_RADIUS_KM


def altitude_density_by_shell(propagator: OrbitalPropagator,
                               shell_width_km: float = 50.0,
                               min_altitude_km: float = 200.0,
                               max_altitude_km: float = 2000.0) -> List[AltitudeShell]:
    """
    Densité volumique d'objets par tranche d'altitude (shell binning).
    Densité = nombre d'objets dans la tranche / volume de la coquille sphérique.
    """
    shells: List[AltitudeShell] = []
    altitudes = [_mean_altitude_km(sat) for sat in propagator.satellites]

    bounds = np.arange(min_altitude_km, max_altitude_km + shell_width_km, shell_width_km)
    for low, high in zip(bounds[:-1], bounds[1:]):
        count = sum(1 for alt in altitudes if low <= alt < high)
        r_low = EARTH_RADIUS_KM + low
        r_high = EARTH_RADIUS_KM + high
        volume_km3 = (4.0 / 3.0) * np.pi * (r_high ** 3 - r_low ** 3)
        density = count / volume_km3 if volume_km3 > 0 else 0.0
        shells.append(AltitudeShell(
            altitude_min_km=float(low), altitude_max_km=float(high),
            object_count=count, density_per_km3=density,
        ))
    return shells


def detect_conjunctions(propagator: OrbitalPropagator, start: datetime, end: datetime,
                         step_seconds: int = 60,
                         threshold_km: float = CONJUNCTION_THRESHOLD_MODERATE_RISK_KM
                         ) -> List[ConjunctionAlert]:
    """
    Détecte les rapprochements (conjonctions) entre paires de satellites dont
    l'altitude moyenne est proche (même régime, cf. ALTITUDE_BAND_MARGIN_KM),
    sur la fenêtre temporelle donnée.
    """
    satellites = propagator.satellites
    altitudes = {sat.name: _mean_altitude_km(sat) for sat in satellites}

    candidate_pairs = [
        (a, b) for a, b in itertools.combinations(satellites, 2)
        if abs(altitudes[a.name] - altitudes[b.name]) <= ALTITUDE_BAND_MARGIN_KM
    ]

    best_by_pair = {}  # (name_a, name_b) -> ConjunctionAlert (plus proche approche)

    current = start
    while current <= end:
        t = _TS.from_datetime(current if current.tzinfo else current.replace(tzinfo=timezone.utc))
        for sat_a, sat_b in candidate_pairs:
            pos_a = sat_a.at(t).position.km
            pos_b = sat_b.at(t).position.km
            distance_km = float(np.linalg.norm(np.array(pos_a) - np.array(pos_b)))

            if distance_km <= threshold_km:
                key = (sat_a.name, sat_b.name)
                if key not in best_by_pair or distance_km < best_by_pair[key].min_distance_km:
                    risk = ("high" if distance_km <= CONJUNCTION_THRESHOLD_HIGH_RISK_KM
                            else "moderate")
                    best_by_pair[key] = ConjunctionAlert(
                        object_a=sat_a.name, object_b=sat_b.name,
                        time_utc=current, min_distance_km=distance_km, risk_level=risk,
                    )
        current += timedelta(seconds=step_seconds)

    return list(best_by_pair.values())


if __name__ == "__main__":
    from modules.tle_fetcher import TLEFetcher

    fetcher = TLEFetcher()
    records = fetcher.load_from_file("data/samples/test_fixtures.tle")
    propagator = OrbitalPropagator(records)

    print("--- Densité par tranche d'altitude ---")
    for shell in altitude_density_by_shell(propagator, shell_width_km=100):
        if shell.object_count > 0:
            print(f"  {shell.altitude_min_km:.0f}-{shell.altitude_max_km:.0f} km : "
                  f"{shell.object_count} objet(s), densité={shell.density_per_km3:.3e} /km3")

    print("--- Conjonctions détectées ---")
    start = datetime(2026, 1, 30, 0, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=6)
    # seuil volontairement large pour démontrer la détection sur les sats de test
    alerts = detect_conjunctions(propagator, start, end, step_seconds=30, threshold_km=50.0)
    for a in alerts:
        print(f"  {a.object_a} <-> {a.object_b} @ {a.time_utc} : "
              f"{a.min_distance_km:.2f} km ({a.risk_level})")
