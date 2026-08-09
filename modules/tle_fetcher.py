"""
Récupération et mise en cache locale des éléments orbitaux (TLE) depuis CelesTrak.

"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import requests

CELESTRAK_BASE_URL = "https://celestrak.org/NORAD/elements/gp.php"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache"
# CelesTrak met à jour les données Starlink/Active toutes les 2h et bloque
# (HTTP 403) toute requête répétée avant la prochaine mise à jour. On aligne
# donc notre fenêtre de cache sur cette politique pour ne jamais redemander
# inutilement (cf. https://celestrak.org/NORAD/documentation/gp-data-formats.php).
CACHE_MAX_AGE_HOURS = 2
USER_AGENT = "PPP-Starlink2-EC2LT/1.0 (projet academique; contact: groupe2@ec2lt)"


@dataclass
class TLERecord:
    """Un jeu d'éléments orbitaux à deux lignes (TLE), avec le nom de l'objet."""
    name: str
    line1: str
    line2: str

    @property
    def norad_id(self) -> str:
        return self.line1[2:7].strip()

    def as_3le(self) -> str:
        return f"{self.name}\n{self.line1}\n{self.line2}"


class TLEFetcher:
    """Récupère et met en cache les TLE d'un groupe CelesTrak (ex. 'starlink')."""

    def __init__(self, cache_dir: Path = DEFAULT_CACHE_DIR,
                 cache_max_age_hours: float = CACHE_MAX_AGE_HOURS):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_max_age_hours = cache_max_age_hours

    def _cache_path(self, group: str) -> Path:
        return self.cache_dir / f"{group}.tle"

    def _meta_path(self, group: str) -> Path:
        return self.cache_dir / f"{group}.meta.json"

    def _is_cache_fresh(self, group: str) -> bool:
        meta_path = self._meta_path(group)
        if not meta_path.exists():
            return False
        try:
            meta = json.loads(meta_path.read_text())
            fetched_at = meta.get("fetched_at_epoch", 0)
        except (json.JSONDecodeError, OSError):
            return False
        age_hours = (time.time() - fetched_at) / 3600.0
        return age_hours < self.cache_max_age_hours

    def _save_cache(self, group: str, raw_text: str) -> None:
        self._cache_path(group).write_text(raw_text, encoding="utf-8")
        meta = {
            "group": group,
            "fetched_at_epoch": time.time(),
            "fetched_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": CELESTRAK_BASE_URL,
        }
        self._meta_path(group).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def fetch(self, group: str = "starlink", force_refresh: bool = False) -> List[TLERecord]:
        """
        Récupère les TLE d'un groupe CelesTrak.

        Ordre de priorité :
        1. Cache local frais (< cache_max_age_hours) sauf si force_refresh=True
        2. Requête réseau à CelesTrak
        3. Cache local même périmé, en dernier recours (résilience hors-ligne)
        """
        if not force_refresh and self._is_cache_fresh(group):
            return self._parse_tle_text(self._cache_path(group).read_text(encoding="utf-8"))

        try:
            response = requests.get(
                CELESTRAK_BASE_URL,
                params={"GROUP": group, "FORMAT": "tle"},
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )

            if response.status_code == 403:
                cache_path = self._cache_path(group)
                message = (
                    f"CelesTrak a renvoyé une erreur 403 pour le groupe '{group}'. "
                    f"Cause la plus probable : CelesTrak limite les groupes "
                    f"'active'/'starlink' à UN téléchargement par cycle de mise à "
                    f"jour (2h) et bloque toute requête supplémentaire avant la "
                    f"prochaine mise à jour -- ou votre IP a été temporairement "
                    f"bannie pour requêtes trop fréquentes. "
                    f"Attendez le prochain cycle (jusqu'à 2h) avant de réessayer."
                )
                if cache_path.exists():
                    print(f"[tle_fetcher] {message} Repli sur le cache local existant.")
                    return self._parse_tle_text(cache_path.read_text(encoding="utf-8"))
                raise RuntimeError(
                    f"{message} Aucun cache local disponible pour '{group}' : "
                    f"utilisez les données d'exemple hors-ligne "
                    f"(data/samples/test_fixtures.tle) en attendant."
                )

            response.raise_for_status()
            raw_text = response.text
            if not raw_text.strip():
                raise ValueError("Réponse CelesTrak vide")
            self._save_cache(group, raw_text)
            return self._parse_tle_text(raw_text)

        except (requests.RequestException, ValueError) as exc:
            cache_path = self._cache_path(group)
            if cache_path.exists():
                print(f"[tle_fetcher] Réseau indisponible ({exc}). "
                      f"Repli sur le cache local ({cache_path}).")
                return self._parse_tle_text(cache_path.read_text(encoding="utf-8"))
            raise RuntimeError(
                f"Impossible de récupérer les TLE pour '{group}' : ni réseau ni "
                f"cache local disponible. Détail : {exc}"
            ) from exc

    @staticmethod
    def _parse_tle_text(raw_text: str) -> List[TLERecord]:
        """Parse un flux TLE (3 lignes par objet : nom, ligne 1, ligne 2)."""
        lines = [l.rstrip("\n") for l in raw_text.strip().splitlines() if l.strip()]
        records: List[TLERecord] = []
        for i in range(0, len(lines) - 2, 3):
            name, line1, line2 = lines[i], lines[i + 1], lines[i + 2]
            if line1.startswith("1 ") and line2.startswith("2 "):
                records.append(TLERecord(name=name.strip(), line1=line1, line2=line2))
        return records

    def load_from_file(self, path: Path) -> List[TLERecord]:
        """Charge des TLE depuis un fichier local arbitraire (ex. données d'exemple)."""
        return self._parse_tle_text(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Récupère et met en cache les TLE CelesTrak (usage normal), "
                    "ou enregistre un fichier TLE existant comme cache 'frais' "
                    "(--register-file), utile avant une démo/présentation pour "
                    "ne dépendre d'aucun accès réseau au moment critique."
    )
    parser.add_argument("--group", default="starlink",
                         help="Groupe CelesTrak (starlink, active, debris...)")
    parser.add_argument("--register-file", metavar="PATH",
                         help="Enregistre ce fichier TLE local comme cache pour "
                              "--group, avec un .meta.json à jour, SANS requête "
                              "réseau. Utile si vous avez déjà un fichier "
                              "data/cache/starlink.tle téléchargé manuellement.")
    args = parser.parse_args()

    fetcher = TLEFetcher()

    if args.register_file:
        raw_text = Path(args.register_file).read_text(encoding="utf-8")
        records = fetcher._parse_tle_text(raw_text)
        if not records:
            raise SystemExit(f"Aucun TLE valide trouvé dans {args.register_file}")
        fetcher._save_cache(args.group, raw_text)
        print(f"{len(records)} satellites enregistrés comme cache '{args.group}' "
              f"(frais pendant {fetcher.cache_max_age_hours}h, "
              f"soit jusqu'à {time.strftime('%Y-%m-%d %H:%M', time.localtime(time.time() + fetcher.cache_max_age_hours*3600))}). "
              f"L'application n'ira PAS taper CelesTrak tant que ce cache est frais.")
    else:
        try:
            sats = fetcher.fetch(args.group)
            print(f"{len(sats)} satellites '{args.group}' récupérés / mis en cache.")
            if sats:
                print("Exemple :", sats[0].as_3le())
        except RuntimeError as e:
            print(e)
