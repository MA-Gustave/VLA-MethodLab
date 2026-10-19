# RVV-VLA Lab Studio — suivi simple des tests

Ce correctif modifie seulement l'interface graphique et la récupération des résultats. Il **ne modifie pas** le moteur simdjson, les workers des tests 81–90, les résultats déjà obtenus ni la connexion SSH.

## Installation sur Windows

1. Fermer RVV-VLA Lab Studio (les tests distants déjà lancés continuent).
2. Télécharger `RVV-VLA-Lab_Studio_Suivi_Simple_Overlay.zip` dans Téléchargements.
3. Dans PowerShell :

```powershell
$repo = 'C:\mycode\Simdjson\RVV-VLA-Lab'
$zip = "$env:USERPROFILE\Downloads\RVV-VLA-Lab_Studio_Suivi_Simple_Overlay.zip"
Expand-Archive -LiteralPath $zip -DestinationPath $repo -Force
& "$repo\.venv\Scripts\python.exe" "$repo\tools\test_studio_simple_ui.py"
& "$repo\LAUNCH_RVV_VLA_LAB.bat"
```

## Test Runner

- **1. Choisir le test à lancer** : Test 89, Test 90, etc. avec noms courts et durées.
- **2. Suivre un test lancé** : mêmes noms courts, états compréhensibles et heures de ton PC.
- Cliquer sur un test en haut retrouve sa dernière exécution en bas lorsque la provenance a été enregistrée.
- **En cours** = le serveur travaille; **Terminé** = il est possible de récupérer les résultats; **Erreur** = récupérer les diagnostics.
- Sélectionner une exécution terminée et cliquer sur **Récupérer les résultats**. Studio contrôle l'archive SHA256 distante et crée un fichier `Test-90_Resultats_YYYYMMDD_HHMMSS.zip` dans le dossier de partage. Un bouton ouvre ce dossier.
- **Détails techniques** et **Journal technique** conservent les codes d'exécution, métriques, horodatages UTC, diagnostics et détails RISC-V pour les personnes qui en ont besoin.

### Correspondance vérifiée, pas devinée

Le nom du test provient du champ `campaign` dans le `launcher.json` **de la campagne exacte**, et non de l'heure, de la position dans la liste ou de l'élément sélectionné en haut. Les anciens runs sans ce champ sont intitulés « Ancienne campagne — test non identifié » au lieu d'une attribution incertaine.

### Vie privée et sécurité

Le fichier SSH `.env` reste à sa place (`C:\mycode\Simdjson\.env`) et **n'est jamais inclus** dans l'archive de partage. Les données de mesures gardent leurs horodatages UTC originaux. Le ZIP partageable peut contenir des chemins du serveur dans les rapports : vérifie-le avant publication publique. Pas de démarrage ni de suppression automatique à l'ouverture.

Tests locaux : `tools/test_studio_simple_ui.py`, `tools/test_studio_clock.py`, `tools/test_snapshot_89_sync.py`. L'ouverture graphique Windows doit être vérifiée par l'utilisateur.
