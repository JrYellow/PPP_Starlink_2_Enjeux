"""
Simulateur de traînées lumineuses : visibilité depuis un observatoire,
angle 
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List

import numpy as np
from skyfield.api import EarthSatellite, wgs84

from modules.orbital import OrbitalPropagator, is_sunlit_cylindrical, _TS
from modules.solar import solar_elevation_deg, sun_position_eci_km

# Fenêtre de crépuscule (élévation solaire, en degrés) où les traînées de
# satellites sont typiquement visibles : Soleil sous l'horizon (ciel qui
# s'assombrit) mais pas encore en pleine nuit noire (crépuscule astronomique).
TWILIGHT_SUN_ELEVATION_MIN_DEG = -18.0  # crépuscule astronomique
TWILIGHT_SUN_ELEVATION_MAX_DEG = -6.0   # crépuscule civil

# Élévation minimale du satellite au-dessus de l'horizon de l'observateur pour
# être considéré comme "observable" (au-delà, trop d'extinction atmosphérique).
MIN_SATELLITE_ELEVATION_DEG = 20.0

# Magnitude intrinsèque à 1000 km pour un Starlink v1.5/v2-mini (valeur
# empirique moyenne publiée dans la littérature -- à ajuster/sourcer plus
# finement par génération si vous approfondissez cette partie).
DEFAULT_INTRINSIC_MAGNITUDE_AT_1000KM = 5.9


@dataclass
class Observatory:
    name: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float = 0.0


@dataclass
class VisibleTrail:
    """Une traînée observable : un satellite visible à un instant donné."""
    satellite_name: str
    time_utc: datetime
    satellite_elevation_deg: float
    satellite_azimuth_deg: float
    distance_km: float
    apparent_magnitude: float
    sun_elevation_deg: float


# Observatoires de référence, utiles pour vos tests de validation (étape 9)
KNOWN_OBSERVATORIES = {
    "mauna_kea": Observatory("Mauna Kea Observatory (Hawaii)", 19.8207, -155.4681, 4207),
    "paranal": Observatory("ESO Paranal Observatory (Chili)", -24.6272, -70.4039, 2635),
    "la_palma": Observatory("Observatorio del Roque de los Muchachos", 28.7606, -17.8850, 2396),
    "dakar": Observatory("Dakar, Sénégal (Faculté des Sciences et Techniques, UCAD)", 14.6928, -17.4467, 24),
}


def custom_observatory(name: str, latitude_deg: float, longitude_deg: float,
                        elevation_m: float = 0.0) -> Observatory:
    """
    Construit un observatoire personnalisé à partir de coordonnées saisies par
    l'utilisateur (latitude/longitude/altitude), pour permettre l'analyse
    depuis n'importe quel site -- pas seulement les observatoires de référence
    prédéfinis ci-dessus.
    """
    if not (-90 <= latitude_deg <= 90):
        raise ValueError(f"Latitude invalide : {latitude_deg} (doit être entre -90 et 90)")
    if not (-180 <= longitude_deg <= 180):
        raise ValueError(f"Longitude invalide : {longitude_deg} (doit être entre -180 et 180)")
    return Observatory(name, latitude_deg, longitude_deg, elevation_m)


def _phase_function(phase_angle_rad: float) -> float:
    """
    Fonction de phase pour une sphère diffuse lambertienne.
    beta = angle de phase Soleil-satellite-observateur (radians).
    """
    beta = phase_angle_rad
    return (math.sin(beta) + (math.pi - beta) * math.cos(beta)) / math.pi


def apparent_magnitude(distance_km: float, phase_angle_rad: float,
                        intrinsic_mag_at_1000km: float = DEFAULT_INTRINSIC_MAGNITUDE_AT_1000KM
                        ) -> float:
    """
    Magnitude visuelle apparente d'un satellite, modèle sphère diffuse.
    m(d, beta) = m1000 - 5*log10(1000/d) - 2.5*log10(phi(beta))
    Plus la magnitude est faible (voire négative), plus l'objet est brillant.
    """
    phi = _phase_function(phase_angle_rad)
    phi = max(phi, 1e-6)  # évite log(0) en phase quasi nulle
    return (intrinsic_mag_at_1000km
            - 5 * math.log10(1000.0 / distance_km)
            - 2.5 * math.log10(phi))


def _observer_topocentric(observatory: Observatory, satellite: EarthSatellite, when: datetime):
    """Retourne (élévation_deg, azimut_deg, distance_km) du satellite vu de l'observatoire."""
    topocentric_observer = wgs84.latlon(
        observatory.latitude_deg, observatory.longitude_deg, observatory.elevation_m
    )
    t = _TS.from_datetime(when if when.tzinfo else when.replace(tzinfo=timezone.utc))
    difference = satellite - topocentric_observer
    topocentric = difference.at(t)
    alt, az, distance = topocentric.altaz()
    return alt.degrees, az.degrees, distance.km


def _phase_angle(sat_eci_km: np.ndarray, sun_eci_km: np.ndarray,
                  observer_eci_km: np.ndarray) -> float:
    """Angle de phase Soleil-satellite-observateur, en radians."""
    v_sat_to_sun = np.array(sun_eci_km) - np.array(sat_eci_km)
    v_sat_to_obs = np.array(observer_eci_km) - np.array(sat_eci_km)
    cos_beta = np.dot(v_sat_to_sun, v_sat_to_obs) / (
        np.linalg.norm(v_sat_to_sun) * np.linalg.norm(v_sat_to_obs) + 1e-12
    )
    cos_beta = max(-1.0, min(1.0, cos_beta))
    return math.acos(cos_beta)


def simulate_trails(propagator: OrbitalPropagator, observatory: Observatory,
                     start: datetime, end: datetime, step_seconds: int = 30
                     ) -> List[VisibleTrail]:
    """
    Parcourt la fenêtre [start, end] par pas de step_seconds et détecte les
    traînées observables : Soleil sous l'horizon de l'observatoire (crépuscule),
    satellite éclairé, satellite au-dessus de l'élévation minimale.
    """
    trails: List[VisibleTrail] = []
    current = start
    observer_geoc = wgs84.latlon(
        observatory.latitude_deg, observatory.longitude_deg, observatory.elevation_m
    )

    while current <= end:
        sun_elev = solar_elevation_deg(current, observatory.latitude_deg, observatory.longitude_deg)

        if TWILIGHT_SUN_ELEVATION_MIN_DEG <= sun_elev <= TWILIGHT_SUN_ELEVATION_MAX_DEG:
            sun_eci = sun_position_eci_km(current)
            t = _TS.from_datetime(current if current.tzinfo else current.replace(tzinfo=timezone.utc))
            observer_eci = observer_geoc.at(t).position.km

            for sat in propagator.satellites:
                sat_eci = sat.at(t).position.km

                if not is_sunlit_cylindrical(np.array(sat_eci), np.array(sun_eci)):
                    continue  # satellite dans l'ombre terrestre : invisible

                elev_deg, az_deg, distance_km = _observer_topocentric(observatory, sat, current)
                if elev_deg < MIN_SATELLITE_ELEVATION_DEG:
                    continue  # trop bas sur l'horizon (extinction atmosphérique)

                beta = _phase_angle(np.array(sat_eci), np.array(sun_eci), np.array(observer_eci))
                mag = apparent_magnitude(distance_km, beta)

                trails.append(VisibleTrail(
                    satellite_name=sat.name,
                    time_utc=current,
                    satellite_elevation_deg=elev_deg,
                    satellite_azimuth_deg=az_deg,
                    distance_km=distance_km,
                    apparent_magnitude=mag,
                    sun_elevation_deg=sun_elev,
                ))

        current += timedelta(seconds=step_seconds)

    return trails


if __name__ == "__main__":
    from modules.tle_fetcher import TLEFetcher

    fetcher = TLEFetcher()
    records = fetcher.load_from_file("data/samples/test_fixtures.tle")
    propagator = OrbitalPropagator(records)

    obs = KNOWN_OBSERVATORIES["mauna_kea"]
    start = datetime(2026, 1, 30, 4, 30, 0, tzinfo=timezone.utc)  # ~ crépuscule du soir à Hawaii
    end = start + timedelta(hours=1)

    results = simulate_trails(propagator, obs, start, end, step_seconds=60)
    print(f"{len(results)} détections de traînées sur la fenêtre testée à {obs.name}")
    for r in results[:5]:
        print(f"  {r.time_utc} - {r.satellite_name} - mag={r.apparent_magnitude:.2f} "
              f"- elev={r.satellite_elevation_deg:.1f} - sun_elev={r.sun_elevation_deg:.1f}")
