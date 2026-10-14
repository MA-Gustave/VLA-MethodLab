# Test 92 — exploration progressive 8 h (Stage 1 et surcoût expérimental)

Le **Test 92** est une nouvelle campagne autonome. **Les tests 91 Pilot 1h et Broad 8h restent disponibles et inchangés dans leurs paramètres**, et leurs résultats historiques ne sont jamais modifiés. Le Test 92 réutilise les mêmes trois binaires, les 242 compositions natives, les 2 304 designs JSON, les contrôles de validité et le corpus jusqu'à 64 Mio.

## Pourquoi un nouveau test ?

Le Test 91 Pilot a validé les trois compilations, les 242 configurations et les mesures appariées, mais il a surtout exécuté le premier passage de screening : 281 groupes `screen` et 42 groupes `holdout`. Aucune composition n'a dépassé A2 dédié en débit DOM sur les groupes complets. Stage 1 et le surcoût du binaire d'exploration méritent d'être isolés. Le Test 92 réalloue les huit heures vers les configurations prometteuses et les cas difficiles, sans modifier le parser de production.

## Plan de recherche

L'horloge inclut compilation et validations natives. Les budgets de phase sont **des plafonds temporels**, pas des garanties de couverture :

1. **Screening initial (jusqu'à 34 % du temps restant après compilation)** : une mesure appariée (candidat / A2 dédié / officiel VLS256) par composition, sur six corpus ancres partagés et tournants. Les deux compositions de contrôle sont testées en premier. Si une étape dure trop longtemps, le screening reste partiel.
2. **Raffinement (jusqu'à 57 % du temps restant)** : au maximum 48 compositions retenues après classement *au sein de chaque corpus ancre*, avec au moins un contingent par politique native et la conservation des deux contrôles. Deux mesures additionnelles sur des corpus ancres **distincts** sont prévues par composition. Les classements demeurent exploratoires : une mesure par candidat ne donne pas une preuve de supériorité.
3. **Exploration adaptative (jusqu'à 85 % du temps restant)** : variations de tailles pondérées, familles UTF-8, échappements et longues chaînes davantage diagnostiquées ; études de spécialistes (DOM comme mesure principale, Stage 1 comme diagnostic à poids 15 %), répétitions et **contrôle périodique `policy=0`** mesurant le surcoût du binaire expérimental relativement à A2 dédié, toujours sur le même JSON.
4. **Holdout final (15 % du temps post-compilation)** : au plus six finalistes, chacun avec au moins deux corpus d'entraînement distincts. Leurs jeux de validation utilisent de **nouvelles graines**, partagées par tous les finalistes lors d'un même tour. Les mesures de holdout n'alimentent *jamais* le scheduler ni le choix des finalistes.

Les 242 plans originaux restent dans le catalogue ; les propositions générées par combinaison sont conservées comme recherches expérimentales. Aucune promotion automatique vers la production. Les résultats sont de type **parser et document chauds** ; les timings Stage 1 et Stage 2 ne s'additionnent pas directement au temps DOM public. Les tris multi-familles, l'exploration orientée Stage 1 et les scores composites doivent être revalidés sur corpus de production indépendants.

## Lancement depuis Windows Studio

1. Fermer Studio ; extraire l'archive complète dans `C:\mycode\Simdjson\` pour mettre à jour `RVV-VLA-Lab`. Ne pas supprimer `.env` ni `.venv` de votre installation ; ils ne figurent pas dans ce paquet.
2. Relancer `C:\mycode\Simdjson\RVV-VLA-Lab\LAUNCH_RVV_VLA_LAB.bat`.
3. Ouvrir **Test Runner**, cliquer **Refresh**, choisir **Test 92 — Adaptive 8h**, puis cliquer **Run selected**. **Le lancement n'est jamais automatique.**
4. Après la campagne, sélectionner sa ligne dans **RVV Lab campaigns**, cliquer **Sync results**, et récupérer son archive pour interprétation.

Une colonne **Test / profil** montre maintenant `Test 91 — Pilote 1h`, `Test 91 — Exploration 8h` ou `Test 92 — Adaptatif 8h` pour les campagnes dont la métadonnée correspondante est enregistrée. Les anciennes campagnes non identifiées restent affichées comme telles, sans déduction risquée à partir de leurs horodatages.

Alternative CLI (dans le dépôt, après confirmation explicite) :

```powershell
.\.venv\Scripts\python.exe tools\test_exploration_92.py
.\.venv\Scripts\python.exe tools\rvvlab.py run explore-92-8h --wait
```

Raccourci Windows facultatif : `RUN_TEST_92_8H.bat` (validation locale puis confirmation Y/N).

## Sécurité, intégrité et résultats

* Un run unique dans son dossier `night-*`, verrou exclusif contre deux campagnes simultanées, et interdiction d'écraser une campagne existante.
* STOP contrôlé et plancher disque à 200 Mio, contrôle périodique toutes les 15 minutes ; budget de travail à 2 Gio, snapshots à somme SHA256.
* Portes natives : JSON valides et invalides, accords DOM complets avec fallback et vérification de chaque corpus concret avant chronométrage.
* Les comparaisons sont toujours appariées sur un même corpus et des itérations identiques. Ordre des trois moteurs mélangé pour limiter les biais d'ordre.
* La compilation reste réalisée sur le serveur RISC-V ; la validation Python locale **ne prouve pas les performances ou la correction native de ce nouveau scheduler sur cette machine**.
* `EXPLORATION_92.md`, `map.csv`, `schedule.json`, `diagnostics.csv`, `ranking.csv`, `policy_candidates.json`, `metadata.json`, `composition_catalog.json` et le manifeste SHA256 sont produits et synchronisés.
* Les anciens profils Test 91, tous les fichiers de résultats historiques et le code natif de simdjson restent préservés.

### Tests locaux hors ligne

```powershell
.\.venv\Scripts\python.exe tools\test_exploration_91.py
.\.venv\Scripts\python.exe tools\test_exploration_92.py
.\.venv\Scripts\python.exe tools\verify_release.py --hashes
```

Ces tests simulés vérifient l'ordre des phases, la diversité des politiques, le holdout exclu du classement d'entraînement, l'intégrité des profils Studio/CLI et le contrôle SHA256 du snapshot. Le lancement distant est à faire explicitement depuis Studio.
