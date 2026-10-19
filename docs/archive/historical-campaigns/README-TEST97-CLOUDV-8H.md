# Test 97 — Cloud-V · validation ciblée du seuil A2 (8 heures)

## Installation DROP ROOT (aucun installateur)

1. **Fermer Studio Cloud-V et EPCC**.
2. Faire une sauvegarde de `VLA-MethodLab/studio/rvvlab_simple_tests.py` si vous avez des modifications locales non partagées.
3. Décompresser **le contenu** du ZIP directement dans `C:\mycode\Simdjson\VLA-MethodLab\`, en fusionnant `studio/` et `tools/` et en acceptant le remplacement du seul module d'UI `studio/rvvlab_simple_tests.py`.
4. Relancer Studio, connecter **Cloud-V**, ouvrir **Tests simples**, choisir **97**, cliquer sur **Run** puis confirmer.
5. La campagne continue **sur Cloud-V après fermeture de Studio**. Une fois l'état **Terminé — ZIP prêt**, cliquer sur **Download**. Le ZIP sera dans le dossier local de résultats Studio sous `TestRunner/test97-cloudv-8h/simple-<id>/test97_results.zip`.

EPCC / Test 96 et Cloud-V / Test 95 sont conservés. Ne pas lancer une autre campagne en parallèle sur Cloud-V.

## Pourquoi ce protocole remplace le Test 95

Les deux campagnes Test 95 (80 717 lignes) ont trouvé un avantage du seuil 8 Kio par rapport à 4 Kio sur 4096–8191 octets, mais elles ont tourné sur le **même CPU en parallèle** et réutilisé beaucoup de documents similaires. Un test identique aurait reproduit cette limitation.

Le Test 97 mesure uniquement les six seuils `4096` (A2_REF), `5120`, `6144`, `7168`, `8192` et `10240` octets. Toutes les autres optimisations packed sont désactivées. Chaque groupe exécute **A2_REF d'abord**, les cinq candidats dans un ordre aléatoire, puis **A2_REF à nouveau**, sur le même document avec les mêmes itérations. Le rapport compare chaque débit au **moyen géométrique des deux références**, pour limiter l'effet d'une dérive lente de fréquence/température.

Échantillonnage : 50 % de cas aux tailles exactes (30 seuils et voisinages × 4 familles), 25 % d'ancrages synthétiques de diverses tailles, 12,5 % de régions mixtes et 12,5 % de JSON réels du moteur si présents. Les fichiers réels d'exploration (`recipe_book`, `example_config`) diffèrent des fichiers réels de holdout (`twitter`, `citm_catalog`). Les JSON synthétiques ont des graines nouvelles, et différentes entre exploration et holdout. Des fichiers JSON réels de production demeurent nécessaires avant promotion.

**Durée totale 8 heures (28 800 s), compilation incluse**. Holdout réservé à la dernière période de 2 heures (7 200 s), si la compilation et les validations se terminent à temps. Les six binaires sont compilés en `-O3 -march=rv64gcv`, sans LTO et sans toucher aux sources du moteur. Validation RVV vs fallback requise pour chaque JSON avant mesure. CPU fixé par `taskset` (par défaut CPU 0). Vérification des autres processus Test 94/95/96/97, avant et pendant l'exécution, et verrou entre campagnes Test 97 sur le serveur ; ces contrôles ne peuvent pas exclure des tâches étrangères au Lab.

Archives partielles toutes les 10 minutes (si espace suffisant) ; arrêt si moins de 200 Mio libres, préflight à 650 Mio ; somme de contrôle SHA-256 à l'envoi et au téléchargement. Les résultats ne sont **jamais promus automatiquement**.

## Résultats

Sur le serveur : `~/rvvlab-v5/test97-runs/test97-*/`. Fichiers :

- `status97.json` — état final, validation, nombre de mesures.
- `results97.csv` — DOM, Stage1, Stage2, mesure avant/après.
- `REPORT_97.md`, `summary97.json` — comparaison appariée.
- `manifest97.json`, `builds97.json`, `machine97.json` — protocole et provenance.
- `test97_results.zip` et `test97_results.sha256` — archive et empreinte.

Analyse hors connexion : `python tools/analyze97.py test97_results.zip --output DECISIONS_97.md` ; les intervalles bootstrap par type de cas sont exploratoires et n'impliquent pas une généralisation aux workloads réels.

## Limitations et vérification

Tests effectués dans l'environnement de préparation : syntaxe Python, simulation du workflow Studio, sélection de machine, validation de 120 cas JSON exact-size, génération du plan contre le snapshot du Lab, simulation d'analyse d'un jeu apparié, 13 tests de Studio hors connexion. **Aucune compilation GCC RISC-V ni mesure de performance sur Cloud-V n'a été exécutée pour ce nouveau paquet.**

**Remarque :** cette mise à jour `rvvlab_simple_tests.py` est basée sur le dernier ZIP consolidé `RVV-VLA-Lab_DROP_ROOT_EPCC_TESTS_SIMPLES_20261015.zip`. Si vous avez installé d'autres modifications de Studio depuis, il faut fusionner ce module avec celles-ci.
