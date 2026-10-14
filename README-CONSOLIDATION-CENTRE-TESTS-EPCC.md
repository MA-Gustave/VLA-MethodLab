# Correctif consolidé : Centre de tous les tests + EPCC RVV Clang 16

Cette livraison combine :

1. Le Centre de tous les tests (15 profils 81–94), affichage des statuts et
   preuves d’exécution, actions de vérification, téléchargement/récupération,
   lancement confirmé, deux fenêtres autonomes Cloud-V et EPCC.
2. Le correctif EPCC fourni le 14 octobre :
   `engine/include/simdjson/rvv/intrinsics.h`, la régression hors ligne
   `tools/test94_rvv_lookup_clang16.py` et
   `README-TEST94-EPCC-LLVM16-LOOKUP.md`.

Le changement entre les deux versions de `intrinsics.h` est uniquement dans
les commentaires expliquant la compatibilité LLVM 16. L’implémentation des
intrinsics est inchangée. La compilation croisée EPCC réelle, la validation
JSON native et la soumission Slurm restent à vérifier sur le serveur.

## Installation : DROP ROOT & OVERWRITE

1. Fermer les deux fenêtres Lab Studio. Les jobs déjà détachés à distance
   ne sont pas arrêtés.
2. Décompresser `RVV-VLA-Lab_CENTRE_TESTS_EPCC_CLANG16_CONSOLIDE_DROP_ROOT.zip`
   directement dans `C:\mycode\Simdjson\RVV-VLA-Lab\` et remplacer les
   fichiers existants.
3. Ouvrir `LANCER_STUDIO_CLOUDV.pyw` et `LANCER_STUDIO_EPCC.pyw` séparément.
4. Dans chaque fenêtre, connecter SSH, vérifier les tests, puis récupérer
   les résultats ou démarrer le test requis après confirmation.

La vérification hors ligne `tools/test_dual_ssh_profiles.py` a été ajustée :
les backends Studio et orchestrateur partagent le même code SSH, mais Studio
utilise volontairement des chemins de préférences différents selon la machine.

Le correctif ne modifie pas les fichiers `.env` en dehors du projet, les clés
SSH, les résultats déjà téléchargés ni les jobs des serveurs. Aucun secret
n’est inclus.

Les fichiers `SHA256SUMS.txt`, `OVERLAY_SHA256SUMS.txt` et
`SNAPSHOT_INDEX.txt` sont ceux de l’ensemble consolidé. Ne pas réinstaller
l’ancien correctif EPCC par-dessus celui-ci : les manifestes redeviendraient
incohérents.
