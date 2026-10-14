# Installation — Test 89 corrigé (1 heure)

Décompresser **le contenu de cet overlay directement à la racine de RVV-VLA-Lab**. Aucun `.env` n’est inclus; conserve `C:\mycode\Simdjson\.env`.

Depuis PowerShell Windows (chemins compatibles avec les espaces) :

```powershell
$repo = 'C:\mycode\Simdjson\RVV-VLA-Lab'
$zip = "$env:USERPROFILE\Downloads\RVV-VLA-Lab_Test89_Corrected_60m_Overlay.zip"
Expand-Archive -LiteralPath $zip -DestinationPath $repo -Force
& "$repo\.venv\Scripts\python.exe" "$repo\tools\test_prequal_89.py"
& "$repo\RUN_TEST_89.bat"
```

Le `.bat` demande **ton autorisation avant de déployer ou lancer quoi que ce soit sur le serveur**. Le Test Runner du Studio découvre aussi **Test 89** automatiquement.

Test 89 ne réécrit pas l'ancien test 88 : sa défaillance `rc=6` et ses données restent inchangées. Test 89 comprend six configurations, 767 JSON générés, une première sélection équilibrée, et un vrai smoke natif pour prévenir une nouvelle campagne à 0 observation causée par une erreur d'itérations.

La limite d'une heure **inclut les compilations et contrôles sur le serveur**. Les résultats peuvent être partiels; `stopped` pour limite de temps est normal. Ne publie pas les résultats comme des gains confirmés.

Pour récupérer ensuite : `python tools\rvvlab.py status` puis `python tools\rvvlab.py sync <identifiant>`.

Voir `docs/TEST89_CORRECTED_PREQUAL_60M.md` pour le protocole, les fichiers générés, les contrôles et les limites.
