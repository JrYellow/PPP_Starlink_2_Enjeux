# L'impact de Starlink, mesuré et cartographié

Projet Télécommunications — EC2LT — PPP Starlink 2 — Groupe 2

Application Python locale (Streamlit) à 3 modules analysant l'impact de
Starlink : environnement/orbital (calcul), stratégique/réglementaire/économique
(dashboard), cybersécurité (modèle de menace).

## Statut du développement

- **Module 1 — Environnement & Orbital** (Sprint 1, ce dépôt)
- Module 2 — Stratégique / Réglementaire / Économique (sprint suivant)
- Module 3 — Cybersécurité (sprint suivant)

## Installation

```bash
python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

## Structure du projet

```
starlink-impact/
├── app.py                  # Point d'entrée Streamlit (3 onglets)
├── requirements.txt
├── modules/
│   ├── tle_fetcher.py      # Récupération + cache des TLE (CelesTrak)
│   ├── orbital.py          # Propagation SGP4 (position satellites)
│   ├── solar.py            # Position solaire approchée (sans dépendance externe)
│   ├── visibility.py       # Simulateur de traînées (crépuscule, magnitude)
│   ├── conjunctions.py     # Densité débris par altitude + conjonctions
│   └── visualization.py    # Graphiques Plotly (carte, histogramme, alertes)
├── data/
│   ├── cache/               # Cache local des TLE téléchargés (auto-généré)
│   └── samples/
│       └── test_fixtures.tle  # TLE synthétiques pour tests hors-ligne
├── tests/
│   └── test_orbital.py      # Suite de validation (11 tests, cas Mauna Kea)
├── assets/
└── docs/                     # Documentation académique (PDF, diagrammes)
```

## Méthodologie de calcul (Module 1)

### Simulateur de traînées lumineuses

1. Propagation orbitale SGP4 à partir des TLE (`skyfield`/`sgp4`)
2. Filtrage sur la fenêtre de crépuscule (élévation solaire entre -18° et -6°,
   `modules/solar.py` — algorithme basse précision, sans fichier d'éphéméride
   externe, pour un fonctionnement 100% local et hors-ligne)
3. Test d'ombre terrestre (modèle cylindrique, `is_sunlit_cylindrical`)
4. Élévation apparente du satellite > 20° (extinction atmosphérique)
5. Magnitude apparente (modèle sphère diffuse lambertienne, cf. Hainaut &
   Williams 2020, *A&A*)

### Densité de débris et conjonctions

1. Altitude moyenne dérivée du demi-grand axe (troisième loi de Kepler)
2. Binning par tranche d'altitude (50 km par défaut) + densité volumique
   (nombre d'objets / volume de coquille sphérique)
3. Screening pairwise limité aux objets de même régime d'altitude (± 50 km),
   pour un coût de calcul réaliste sur un poste local
4. Seuils de risque indicatifs : < 1 km (élevé), 1-5 km (modéré)

## Sources de données

- TLE : [CelesTrak](https://celestrak.org/NORAD/elements/) (gratuit, mise à jour
  régulière). Mi-2026, CelesTrak est passé aux catalogues à 6 chiffres pour les
  nouveaux objets ; le format TLE classique (5 chiffres) reste valide pour Starlink.
- Référence magnitude : Hainaut & Williams (2020), *A&A*, impact des
  constellations sur les observations astronomiques ESO.
- Rapport IAU "Dark and Quiet Skies".

## Tests

```bash
pytest tests/ -v
```

11 tests de validation couvrant : géométrie solaire (cas connus Mauna Kea),
propagation SGP4, détection de traînées, densité de débris, détection de
conjonctions.

## Note sur les données d'exemple

`data/samples/test_fixtures.tle` contient des **TLE synthétiques** (checksum
valide, mais pas de vrais satellites) utilisés pour les tests automatisés et
la démo hors-ligne. Pour une analyse réelle, décochez l'option "données
d'exemple" dans l'application (nécessite un accès internet à CelesTrak).

## Groupe en charge du projet — EC2LT

-- Exode NGAMENEDE-OMOYEN
-- Tchedre TCHAPO
-- Junior ATIPO
-- Francky Fara MENDY 
-- Dieu Merci Geoffroy Wesley NAM YONA
-- Dieynaba BA
-- Taoufiki HAIROUNISSAOU
