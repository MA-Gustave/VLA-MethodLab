# RVV-VLA Lab Studio — suivi du Test 94 près du choix Cloud-V / EPCC

**Installation (DROP ROOT & OVERWRITE)**

1. Fermer Lab Studio. Un Test94 déjà détaché continue sur le serveur distant.
2. Extraire `RVV-VLA-Lab_TEST94_MACHINE_STATUS_DROP_ROOT.zip` directement dans `C:\mycode\Simdjson\RVV-VLA-Lab\`, en conservant les sous-répertoires et en acceptant les remplacements.
3. Rouvrir Lab Studio. Les deux étiquettes d'état sont à côté des boutons radio Cloud-V et EPCC.

## Affichage par machine

- `○ No Test 94` : aucun lancement enregistré pour ce profil local.
- `● Uploading` / `Preparing` / `Building` / `Starting` : préparation et transfert en cours dans Studio.
- `● Queued` : job EPCC Slurm soumis, en attente de nœud disponible.
- `● Running · train · 125 rows` : benchmark distant confirmé par `status94.json`.
- `● Completed` : état final confirmé (le message précise quand le résultat ZIP est vérifié).
- `● Warning` / `Failed` : erreur de connexion ou défaillance confirmée, selon le détail.
- `Last: Running · ... · 16:56` : **dernière information connue** quand ce profil n'est pas connecté ; **ce n'est pas une vérification de l'état en temps réel**.
- `Last: Monitoring off` : tu as arrêté le monitoring local ; le job distant n'a **pas** été arrêté.

Les états sont propres à chaque profil et sauvegardés localement sous `TestRunner/machine-compare-94-1h/<exécution>/status_pc94.json`. Au redémarrage, Studio retrouve la dernière campagne enregistrée et son dernier état. Il peut aussi afficher `Last: Starting` pour un lancement connu mais non revérifié.

Quand Studio est connecté, il interroge seulement **le serveur actuellement sélectionné**, environ toutes les 35 secondes **en lecture seule**, à condition qu'aucune autre opération SSH intensive (benchmark, synchronisation, inventaire) ne soit en cours. Durant un Test94 actif, le moniteur de test publie ses propres événements plus fréquents. Sur EPCC, Studio vérifie `squeue` pour distinguer un job `PENDING` d'un job `RUNNING`. Aucun compte SSH supplémentaire n'est ouvert, et aucune reconnexion MFA silencieuse n'est tentée.

## Tu peux lancer les deux tests

1. Connecte Cloud-V, démarre Test94 et attends `Cloud-V Test94 started PID ...`.
2. Clique **Stop local monitoring**. Cela n'annule pas le processus distant.
3. Sélectionne EPCC et connecte-toi ; démarre Test94 après vérification du nœud RVV1.0.
4. Le statut Cloud-V devient `Last: ...` car Studio ne vérifie pas cette machine pendant la connexion EPCC.
5. Reconnecte chaque profil pour reprendre sa vérification et utiliser **Recover Test94 results** lorsque les résultats sont disponibles.

## Limites et sécurité

- Les états non revérifiés ne sont jamais affichés comme « OK maintenant ». Un PID lancé seul ne prouve pas que la compilation a réussi.
- Une perte du canal SSH pendant la surveillance devient **Warning**, sans déclarer faussement le benchmark distant comme échoué.
- Aucun mot de passe, clé privée, `.env`, TOTP ou accès permanent à un second serveur n'est introduit.
- Les tests natifs, la compilation EPCC, le déploiement et les Tests 91–93 ne sont pas modifiés.
- Tests locaux réalisés pour le cache et le rendu Tkinter, les états Slurm simulés et les anciens tests. Aucun accès aux serveurs réels n'a été effectué lors de la génération du paquet.
