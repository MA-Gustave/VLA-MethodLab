# Lab Studio — deux fenêtres indépendantes (Cloud-V + EPCC)

## Installation DROP ROOT

Extraire ce ZIP directement dans `C:\mycode\Simdjson\VLA-MethodLab\`.
Accepter le remplacement de `studio/RVV_Lab_Studio.pyw` ; conserver le lanceur
historique `LAUNCH_RVV_VLA_LAB.bat` et l'ensemble du répertoire `.venv`.
Aucun paquet supplémentaire n'est nécessaire.

**La fenêtre Cloud-V déjà ouverte peut rester ouverte pendant l'extraction.**
Le code Python de la fenêtre déjà démarrée est chargé en mémoire. En cas de
message Windows signalant un fichier en cours d'utilisation, fermer et
relancer seulement quand ce sera possible ; ne pas forcer l'écrasement.

## Utilisation

- Double-cliquer **`LAUNCH_STUDIO_EPCC.bat`** : fenêtre dédiée EPCC.
  Cliquer `Connect SSH`, puis compléter l'authentification EPCC comme auparavant.
- Double-cliquer **`LAUNCH_STUDIO_CLOUDV.bat`** : fenêtre dédiée Cloud-V.
  Si une fenêtre Cloud-V est déjà ouverte, le verrou empêche une deuxième
  fenêtre *pour Cloud-V*, sans toucher à EPCC.
- L'ancien `LAUNCH_RVV_VLA_LAB.bat` fonctionne toujours comme avant.

Le titre de fenêtre contient la machine. Dans une fenêtre dédiée, les boutons de
changement de machine sont désactivés intentionnellement. Les configurations et
l'historique local restent propres à chaque cible ; les deux connexions SSH et
les rafraîchissements à 60 secondes sont indépendants.

## Réutilisation des réglages

Au premier lancement dédié, Studio **lit sans le modifier** le fichier de
préférences traditionnel (`%USERPROFILE%\.rvvlab_lab_v3\settings.json`) si aucun
fichier dédié n'existe encore. Cela récupère normalement la configuration EPCC
qui fonctionnait déjà dans Studio.

Les nouveaux réglages sont ensuite enregistrés uniquement dans :

- `%USERPROFILE%\.rvvlab_lab_v3\settings_cloudv.json`
- `%USERPROFILE%\.rvvlab_lab_v3\settings_epcc.json`

Si EPCC n'affiche pas le bon fichier `.env`, ouvrir `Advanced tools`, puis choisir
le bon profil `.env.epcc` ; ne modifier ni Cloud-V ni la clé SSH partagée.

## Garanties et limites

- Les fenêtres **n'exécutent aucun test automatiquement**. Aucun processus sur
  Cloud-V/EPCC ni job Slurm n'est démarré, arrêté ou modifié par ce patch.
- Le verrou système existant protège contre **deux fenêtres pour la même
  machine**. Cela n'empêche pas d'exécuter plusieurs benchmarks par d'autres
  moyens : conserver les protections de Run/Refresh avant de lancer un test.
- La validation a été effectuée en local sur Linux/Tk (y compris la fenêtre
  EPCC), **pas encore sur ton poste Windows avec SSH réel**.

## Fichiers modifiés

- `studio/RVV_Lab_Studio.pyw` : lecture initiale sûre des préférences partagées.
- `LAUNCH_STUDIO_CLOUDV.bat` et `LAUNCH_STUDIO_EPCC.bat` : deux nouveaux lanceurs.
- `studio/tests/test_multi_instance.py` : régressions hors réseau.

Le moteur, les tests 97 à 100, le service de corpus et le lanceur original
ne sont pas modifiés.
