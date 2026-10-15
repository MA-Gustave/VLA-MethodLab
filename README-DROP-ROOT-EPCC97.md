# Studio — Test 97 EPCC dans « Tests simples » (15 octobre 2026)

## Installation directe
1. **Fermer les deux Studios** (Cloud-V et EPCC). Les campagnes distantes détachées ne sont pas arrêtées.
2. Sauvegarder les 4 fichiers Studio qui seront remplacés (ou le dossier `studio`).
3. Décompresser ce ZIP **dans** `C:\mycode\Simdjson\VLA-MethodLab\` en acceptant la fusion des dossiers.
4. Relancer Studio EPCC et établir la connexion SSH.
5. Dans `Tests simples`, sélectionner `97`, puis `Actualiser état`. `Run` lance le Test97 **EPCC v5 officiel, 3 h**. Quand le ZIP final et `validated=true` sont disponibles, `Download` récupère le résultat via le synchroniseur EPCC avec SHA-256.

## Modifications et portée
- Affiche Test97 sous EPCC (94/96/97) sans retirer Test97 Cloud-V (94/95/97).
- Routage par couple **numéro + cible** ; sélectionne `test97-epcc-v5-3h` sur EPCC et `test97-cloudv-8h` sur Cloud-V.
- Détection dans `test97-epcc-runs`, cas compilation/préparation, état final validé et ZIP vérifié.
- `Run selected` conserve le contrôle anti-doublon et le filtrage par machine.
- Liste unifiée : distingue les deux Test97 et propose Sync results sans lancer de job.
- Aucun changement aux scripts de benchmarks, sources moteur, variables .env, résultats distants ou architecture du timer 60 s.

## Contenu
- `studio/rvvlab_simple_tests.py`
- `studio/rvvlab_test_runner.py`
- `studio/rvvlab_unified_campaigns.py`
- `studio/tests/test_97_workflow.py` (régression adaptée aux deux cibles)

## Validation et limites
- 20 tests hors connexion réussis (y compris validation de l'archive EPCC, traitement du cas incomplet, chemins des résultats).
- Tests d'ouverture Tk et de routage réel du manifeste en environnement graphique virtuel réussis.
- Compilation, permissions Slurm et SSH réels **non testés ici**. Aucun benchmark n'est lancé par l'installation.
- Ce patch suppose le snapshot du 2026-10-15 16:10, qui contient déjà `studio/test_scripts/97_epcc_v5_compare.py`, `97_epcc_v5_recover.py` et `studio/rvvlab_epcc_results.py`.
