# Test91 — validation locale de livraison

Date : 12 octobre 2026. Aucun accès SSH, aucune mesure native RVV.

| Vérification exécutée | Résultat |
|---|---|
| `tools/test_exploration_91.py --full --cpp` | PASS |
| 242 configurations, encodage strict, règles C++, hystérésis et compteurs | PASS |
| 2 304 géométries générées à taille bornée, JSON valides et hashes distincts | PASS |
| Un document original de 64 Mio, JSON valide | PASS |
| Simulation des vagues screen/explore/repeat/holdout et absence de fuite du holdout vers la sélection | PASS |
| Simulation paires incomplètes, candidat rejeté, STOP, seuil disque 199 Mio, archives corrompues | PASS |
| Deux synchroniseurs Studio/CLI sur les nouveaux fichiers | PASS |
| `tools/verify_release.py` | PASS |
| `tools/test_adaptive_v2.py` — A0/A1/A2 et plan forcé | PASS |
| `tools/test_holdout_90.py --full` | PASS |
| `tools/test_snapshot_89_sync.py` — synchronisation simulée SFTP | PASS |
| Harness compilé avec g++ sur l’hôte local, configuration expérimentale et backend fallback | PASS : 215 valides / 80 invalides |
| Archive source du déploiement incluant les dépendances Test91 | PASS |
| Compilation Python des nouveaux fichiers | PASS |

Ces tests ne compilent pas la boucle RVV ni ne prouvent ses performances. Le premier pilote natif doit compiler les trois binaires, passer les smokes et contrôler chaque composition avant ses mesures. La vérification GUI porte sur la découverte des profils et leur intégration ; aucune session graphique Windows réelle n’a été exécutée ici.

Le manifeste SHA256 de la livraison est vérifiable avec `python tools/verify_release.py --hashes`. Les résultats du Test90 sont archivés séparément sous `results/runs/2026-10-12-holdout90/` et ne sont pas des résultats du Test91.
