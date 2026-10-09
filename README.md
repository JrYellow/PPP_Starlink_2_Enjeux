# L'impact de Starlink, mesuré et cartographié

Projet Télécommunications — EC2LT — PPP Starlink 2 — Groupe 2

Application Python locale (Streamlit) à 3 modules analysant l'impact de
Starlink : environnement/orbital (calcul), stratégique/réglementaire/économique
(dashboard), cybersécurité (modèle de menace structuré avec STRIDE + SPARTA).

## Démarrage rapide (5 commandes)

Testé avec **Python 3.11 et 3.12** sur Linux et macOS (Windows : adapter la
commande d'activation du venv, voir ci-dessous).

```bash
git clone https://github.com/JrYellow/PPP_Starlink_2_Enjeux.git
cd PPP_Starlink_2_Enjeux
python3 -m venv venv && source venv/bin/activate   # Windows : venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

L'application s'ouvre automatiquement dans votre navigateur à l'adresse
`http://localhost:8501`. Aucune clé API, aucun compte, aucune donnée sensible
n'est nécessaire : tout fonctionne en local avec des données publiques.

## Statut du développement

- **Module 1 — Environnement & Orbital** (traînées lumineuses, débris, conjonctions)
- **Module 2 — Stratégique / Réglementaire / Économique** (réglementation, revenus, géopolitique)
- **Module 3 — Cybersécurité** (arbre d'attaque, STRIDE, référentiel SPARTA, cas Viasat KA-SAT)

Les 3 modules du cahier des charges sont implémentés et intégrés dans une
application Streamlit unique (`app.py`, 3 onglets).

## Utilisation du Module 1 (Environnement & Orbital)

1. Choisissez un **site d'observation** : un observatoire de référence (Mauna
   Kea, Paranal, La Palma, **Dakar**) ou un **site personnalisé** (saisissez
   latitude/longitude/altitude de n'importe quel lieu).
2. Choisissez une date et une fenêtre d'analyse.
3. Décochez "données d'exemple" pour utiliser le vrai catalogue Starlink
   (nécessite un accès réseau à CelesTrak — voir la section Dépannage
   ci-dessous si vous obtenez une erreur 403).
4. Cliquez sur **Lancer la simulation**.

## Dépannage

**Erreur HTTP 403 sur CelesTrak** : CelesTrak limite les groupes
`active`/`starlink` à un téléchargement par cycle de 2 heures. Si vous avez
déjà testé récemment, soit attendez le prochain cycle, soit précaration le
cache une fois pour toutes :
```bash
python -m modules.tle_fetcher --register-file <fichier_tle.tle> --group starlink
```
Une fois ce cache enregistré, décochez "données d'exemple" dans l'application
: elle utilisera ce cache sans repasser par le réseau.

**L'application est lente sur la détection de conjonctions** : si vous
constatez un ralentissement important, vérifiez que `modules/conjunctions.py`
utilise bien `SatrecArray` et `scipy.spatial.cKDTree` (voir section "Choix
techniques" ci-dessous) — le catalogue complet Starlink (7000+ satellites)
doit se traiter en moins d'une seconde par pas de temps.

## Structure du projet

```
starlink-impact/
├── app.py                  # Point d'entrée Streamlit (3 onglets)
├── requirements.txt
├── modules/
│   ├── tle_fetcher.py       # Récupération + cache des TLE (CelesTrak)
│   ├── orbital.py           # Propagation SGP4 (position satellites)
│   ├── solar.py             # Position solaire approchée (sans dépendance externe)
│   ├── visibility.py        # Simulateur de traînées (crépuscule, magnitude)
│   ├── conjunctions.py      # Densité débris par altitude + conjonctions (vectorisé)
│   ├── visualization.py     # Graphiques Module 1 (carte, histogramme, alertes)
│   ├── regulatory.py        # Chargement/validation matrice réglementaire
│   ├── economic.py          # Chargement/validation données économiques
│   ├── geopolitics.py       # Chargement/validation constellations + événements
│   ├── visualization2.py    # Graphiques Module 2 (matrice, éco, course, frise, KPIs)
│   ├── threat_model.py      # Chargement/validation arbre d'attaque + STRIDE + SPARTA
│   ├── case_study.py        # Chargement/validation chronologie Viasat KA-SAT
│   └── visualization3.py    # Graphiques Module 3 (arbre, STRIDE, matrice de risque SPARTA, frise)
├── data/
│   ├── cache/                # Cache local des TLE téléchargés (auto-généré)
│   ├── samples/
│   │   └── test_fixtures.tle # TLE synthétiques pour tests hors-ligne
│   ├── regulatory/
│   │   └── regulatory_matrix.csv
│   ├── economic/
│   │   ├── operators_financials.csv
│   │   ├── starlink_pricing.csv
│   │   ├── starlink_subscribers.csv
│   │   └── NOTES.md           # Traçabilité/fiabilité des données économiques
│   ├── geopolitical/
│   │   ├── constellations_comparison.csv
│   │   ├── military_soft_power_events.csv
│   │   └── restricted_countries.csv
│   └── cyber/
│       ├── attack_tree.csv      # Arbre d'attaque (19 nœuds, branche Viasat)
│       ├── stride_matrix.csv    # Matrice STRIDE (18 entrées)
│       ├── sparta_mapping.csv   # Référentiel SPARTA (14 vecteurs, score NRS, contrôles NIST)
│       └── viasat_case_study.csv # Chronologie incident Viasat (9 événements, TTP MITRE)
├── tests/
│   ├── test_orbital.py      # Module 1 : 11 tests (cas Mauna Kea)
│   ├── test_module2.py      # Module 2 : 13 tests
│   └── test_module3.py      # Module 3 : 22 tests (dont 6 SPARTA)
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

## Méthodologie Module 2 (Stratégique/Réglementaire/Économique)

Données figées en CSV versionnés (pas d'API live, contrairement aux TLE) :
réglementaire (UIT/FCC/ARCEP/ARTP/OFCOM), économique (revenus opérateurs,
tarification Starlink, croissance abonnés), géopolitique (comparatif des 4
méga-constellations, chronologie des usages militaires/souveraineté).
Chaque ligne porte une colonne `source_url` et `date_maj`. Voir
`data/economic/NOTES.md` pour le niveau de fiabilité de chaque jeu de données
(certains chiffres d'opérateurs GEO restent des ordres de grandeur à recouper
avec leurs rapports annuels officiels avant la soutenance).

## Méthodologie Module 3 (Cybersécurité)

- **Arbre d'attaque** (`data/cyber/attack_tree.csv`) : modèle générique
  couvrant les 4 segments d'un système LEO (sol/gestion, liaison RF, spatial,
  utilisateur), avec la branche réellement empruntée lors de l'incident
  Viasat KA-SAT identifiée (colonne `viasat_case`). Intégrité validée
  automatiquement : racine unique, pas de cycle, pas de `parent_id` orphelin.
- **Matrice STRIDE** (`data/cyber/stride_matrix.csv`) : 6 catégories
  (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of
  Service, Elevation of Privilege) croisées avec les composants système,
  référencées aux nœuds de l'arbre d'attaque.
- **Étude de cas Viasat KA-SAT** (`data/cyber/viasat_case_study.csv`) :
  chronologie de l'incident de février 2022 (accès initial via VPN mal
  configuré → pivot vers le réseau de gestion → déploiement du wiper
  AcidRain), avec TTP MITRE ATT&CK et sources CISA/SentinelOne.
- **Référentiel SPARTA** (`data/cyber/sparta_mapping.csv`) : les 14 vecteurs
  d'attaque de l'arbre sont mappés sur les 9 tactiques officielles de SPARTA
  (*Space Attack Research and Tactic Analysis*, Aerospace Corporation —
  l'équivalent de MITRE ATT&CK pour le spatial), avec un score de risque NRS
  (probabilité × impact, grille 5×5 : Faible/Modéré/Élevé/Critique) et les
  contrôles de sécurité NIST SP 800-53 associés. Les 4 nœuds du chemin
  d'attaque réel Viasat ressortent systématiquement en catégorie "Élevé"
  (vérifié par un test automatisé dédié).

## Sources de données

- TLE : [CelesTrak](https://celestrak.org/NORAD/elements/) (gratuit, mise à jour
  régulière). ! Mi-2026, CelesTrak est passé aux catalogues à 6 chiffres pour les
  nouveaux objets ; le format TLE classique (5 chiffres) reste valide pour Starlink.
  ! CelesTrak limite les groupes `active`/`starlink` à un téléchargement par
  cycle de 2h (HTTP 403 sinon) — utilisez `python -m modules.tle_fetcher
  --register-file <fichier> --group starlink` pour précharger le cache avant
  une démo, sans dépendre du réseau au moment critique.
- Référence magnitude : Hainaut & Williams (2020), *A&A*, impact des
  constellations sur les observations astronomiques ESO.
- Rapport IAU "Dark and Quiet Skies".
- Cybersécurité : CISA/FBI AA22-076, analyses SentinelOne (AcidRain/AcidPour),
  rapport d'intervention Viasat, MITRE ATT&CK, référentiel SPARTA
  (sparta.aerospace.org), NIST SP 800-53 (contrôles de sécurité).

## Tests

```bash
pytest tests/ -v
```

**46 tests** couvrant les 3 modules : géométrie solaire, propagation SGP4,
traînées, débris/conjonctions (Module 1, 11 tests) ; réglementaire, économique,
géopolitique (Module 2, 13 tests) ; arbre d'attaque, STRIDE, SPARTA, étude de
cas Viasat (Module 3, 22 tests).

## Note sur les données d'exemple

`data/samples/test_fixtures.tle` contient des **TLE synthétiques** (checksum
valide, mais pas de vrais satellites) utilisés pour les tests automatisés et
la démo hors-ligne. Pour une analyse réelle, décochez l'option "données
d'exemple" dans l'application (nécessite un accès internet à CelesTrak).

