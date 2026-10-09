"""
orbital.py
==========
Calcul de la position des satellites à une date/heure donnée (propagation SGP4).

"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from skyfield.api import EarthSatellite, load, wgs84

from modules.tle_fetcher import TLERecord
from modules.solar import sun_position_eci_km

EARTH_RADIUS_KM = 6378.137  # rayon équatorial WGS84

# Chargement unique de l'échelle de temps (coûteux, à ne faire qu'une fois).
# builtin=True : utilise les fichiers de temps embarqués dans skyfield, sans
# téléchargement réseau (contrairement à load.timescale() par défaut qui peut
# tenter de récupérer les dernières données IERS en ligne).
_TS = load.timescale(builtin=True)


def is_sunlit_cylindrical(sat_position_km: np.ndarray, sun_position_km: np.ndarray) -> bool:
    """
    Test d'ombre terrestre (modèle cylindrique), sans dépendance à une éphéméride
    externe. Suffisant à l'échelle LEO/MEO (cf. méthodologie du projet).

    Le satellite est éclipsé si :
    - il est du côté nuit de la Terre (projection sur l'axe Terre->Soleil négative)
    - ET sa distance perpendiculaire à cet axe est inférieure au rayon terrestre.
    """
    sun_dir = np.array(sun_position_km, dtype=float)
    sun_dir_unit = sun_dir / np.linalg.norm(sun_dir)

    sat = np.array(sat_position_km, dtype=float)
    d_proj = np.dot(sat, sun_dir_unit)  # >0 si côté jour, <0 si côté nuit

    if d_proj > 0:
        return True  # côté jour : forcément éclairé

    r_perp = np.linalg.norm(sat - d_proj * sun_dir_unit)
    eclipsed = r_perp < EARTH_RADIUS_KM
    return not eclipsed


@dataclass
class SatellitePosition:
    """Position calculée d'un satellite à un instant donné."""
    name: str
    norad_id: str
    time_utc: datetime
    latitude_deg: float
    longitude_deg: float
    altitude_km: float
    eci_position_km: tuple  # (x, y, z) géocentrique inertiel
    is_sunlit: bool


class OrbitalPropagator:
    """Encapsule la propagation SGP4 pour une liste de TLE donnée."""

    def __init__(self, tle_records: List[TLERecord]):
        self.satellites: List[EarthSatellite] = [
            EarthSatellite(r.line1, r.line2, r.name, _TS) for r in tle_records
        ]

    @property
    def satrecs(self):
        """
        Objets sgp4 bas niveau, utilisés par modules/conjunctions.py pour la
        propagation vectorisée (SatrecArray). Calculé à la demande (plutôt que
        figé à l'initialisation) pour rester cohérent même si .satellites est
        filtré ou tronqué après la création du propagateur (ex. limitation du
        nombre de satellites dans l'interface Streamlit).
        """
        return [sat.model for sat in self.satellites]

    def position_at(self, satellite: EarthSatellite, when: datetime) -> SatellitePosition:
        """Calcule la position d'un satellite à un instant UTC donné."""
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        t = _TS.from_datetime(when)

        geocentric = satellite.at(t)
        subpoint = wgs84.subpoint(geocentric)
        eci_km = tuple(geocentric.position.km)

        sun_km = sun_position_eci_km(when)
        sunlit = is_sunlit_cylindrical(np.array(eci_km), np.array(sun_km))

        return SatellitePosition(
            name=satellite.name,
            norad_id=str(satellite.model.satnum),
            time_utc=when,
            latitude_deg=subpoint.latitude.degrees,
            longitude_deg=subpoint.longitude.degrees,
            altitude_km=subpoint.elevation.km,
            eci_position_km=eci_km,
            is_sunlit=bool(sunlit),
        )

    def all_positions_at(self, when: datetime) -> List[SatellitePosition]:
        """Calcule la position de tous les satellites chargés à un instant donné."""
        return [self.position_at(sat, when) for sat in self.satellites]


if __name__ == "__main__":
    from modules.tle_fetcher import TLEFetcher

    fetcher = TLEFetcher()
    records = fetcher.load_from_file("data/samples/test_fixtures.tle")
    propagator = OrbitalPropagator(records)

    now = datetime(2026, 1, 30, 12, 0, 0, tzinfo=timezone.utc)
    for pos in propagator.all_positions_at(now):
        print(f"{pos.name}: lat={pos.latitude_deg:.2f} lon={pos.longitude_deg:.2f} "
              f"alt={pos.altitude_km:.1f} km, éclairé={pos.is_sunlit}")
