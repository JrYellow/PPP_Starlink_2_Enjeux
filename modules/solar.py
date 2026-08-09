"""
Position géocentrique approchée du Soleil, sans dépendance à un fichier
d'éphéméride externe (de421.bsp, etc.).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Tuple

AU_KM = 149_597_870.7
J2000_EPOCH = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _days_since_j2000(when: datetime) -> float:
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = when - J2000_EPOCH
    return delta.total_seconds() / 86400.0


def sun_position_eci_km(when: datetime) -> Tuple[float, float, float]:
    """
    Position géocentrique équatoriale (ECI, équinoxe de la date) du Soleil, en km.
    Formule basse précision (Astronomical Almanac / NOAA).
    """
    n = _days_since_j2000(when)

    mean_longitude = math.radians((280.460 + 0.9856474 * n) % 360)
    mean_anomaly = math.radians((357.528 + 0.9856003 * n) % 360)

    ecliptic_longitude = mean_longitude \
        + math.radians(1.915) * math.sin(mean_anomaly) \
        + math.radians(0.020) * math.sin(2 * mean_anomaly)

    obliquity = math.radians(23.439 - 0.0000004 * n)

    distance_au = 1.00014 - 0.01671 * math.cos(mean_anomaly) \
        - 0.00014 * math.cos(2 * mean_anomaly)
    distance_km = distance_au * AU_KM

    x = distance_km * math.cos(ecliptic_longitude)
    y = distance_km * math.cos(obliquity) * math.sin(ecliptic_longitude)
    z = distance_km * math.sin(obliquity) * math.sin(ecliptic_longitude)
    return (x, y, z)


def sun_ra_dec_deg(when: datetime) -> Tuple[float, float]:
    """Ascension droite et déclinaison apparentes du Soleil, en degrés."""
    x, y, z = sun_position_eci_km(when)
    r_eq = math.hypot(x, y)
    ra = math.degrees(math.atan2(y, x)) % 360
    dec = math.degrees(math.atan2(z, r_eq))
    return ra, dec


def gmst_deg(when: datetime) -> float:
    """Temps sidéral moyen de Greenwich, en degrés (formule IAU 1982 simplifiée)."""
    n = _days_since_j2000(when)
    gmst = (280.46061837 + 360.98564736629 * n) % 360
    return gmst


def solar_elevation_deg(when: datetime, latitude_deg: float, longitude_deg: float) -> float:
    """
    Élévation apparente du Soleil au-dessus de l'horizon d'un observateur.
    Négative = Soleil sous l'horizon (nuit / crépuscule).
    """
    ra, dec = sun_ra_dec_deg(when)
    lst = (gmst_deg(when) + longitude_deg) % 360  # temps sidéral local
    hour_angle = math.radians((lst - ra) % 360)

    lat = math.radians(latitude_deg)
    dec_r = math.radians(dec)

    sin_alt = (math.sin(lat) * math.sin(dec_r)
               + math.cos(lat) * math.cos(dec_r) * math.cos(hour_angle))
    return math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))


if __name__ == "__main__":
    now = datetime(2026, 6, 21, 12, 0, 0, tzinfo=timezone.utc)  # solstice, pour test
    print("Position Soleil (km, ECI):", sun_position_eci_km(now))
    print("Élévation solaire à Mauna Kea (19.82N, -155.47) :",
          round(solar_elevation_deg(now, 19.82, -155.47), 2), "deg")
