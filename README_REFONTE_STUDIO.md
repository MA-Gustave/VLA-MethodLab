# RVV-VLA Lab Studio — Refonte complète de la navigation (15 octobre 2026)

## Installation directe (DROP ROOT)

1. Fermer Studio Cloud-V et Studio EPCC (les jobs distants détachés continuent).
2. Faire une **copie de sauvegarde du dossier `studio`**.
3. Extraire ce ZIP **directement dans** `C:\mycode\Simdjson\VLA-MethodLab\`.
4. Accepter la fusion et le remplacement des fichiers existants.
5. Relancer `LANCER_STUDIO_CLOUDV.pyw` ou `LANCER_STUDIO_EPCC.pyw` (les lanceurs existants).
6. Connecter SSH. Dans **Tests**, sélectionner un numéro, cliquer **Actualiser**, puis **Démarrer** si le serveur ne signale aucune campagne active. Après la fin validée, **Télécharger**.

**Aucun installateur, aucune migration, aucun effacement.** Ce patch est destiné au snapshot `znapshot_VLA-MethodLab_10151610.zip` avec l'intégration EPCC Test97 effectuée depuis.

## Navigation refondue

- **Tests** est l'espace principal : machine, connexion, choix du protocole, état réel, action suivante, historique des campagnes, téléchargement vérifié.
- **Outils avancés** : connexion/profils SSH, console, benchmarks historiques, rapports, stockage, exploration, centre historique et scripts historiques. Ces fonctions sont conservées mais ne se présentent plus comme autant d'entrées concurrentes pour la tâche quotidienne.

## Tests reconnus

| Machine | Tests | Test 97 |
| --- | --- | --- |
| Cloud-V | 94, 95, 97 | 8 h, seuils A2 4/5/6/7/8/10 Kio |
| EPCC | 94, 96, 97 | 3 h, A2 vs simdjson officiel v5 |

Le moteur d'exécution **n'est pas réécrit** : les scripts/manifests et leur approbation restent ceux du TestRunner de confiance. La récupération EPCC utilise `rvvlab_epcc_results.sync_epcc_run`; le ZIP de chaque campagne est vérifié avant son affichage comme « prêt ».

## Sémantique des états

- **Jaune** = lancement ou exécution en cours, Run désactivé.
- **Vert** = serveur confirme `completed` + validation + archive distante. Download possible.
- **Rouge** = échec/arrêt confirmé.
- **Neutre** = déconnecté, non encore vérifié, impossible à vérifier, ou aucune campagne active détectée. Aucun « PASS » local n'est converti en réussite distante.
- **Anciennes campagnes** : choix explicite dans l'historique, pas de confusion avec le dernier lancement.

Actualiser et Télécharger ne soumettent aucun job. Démarrer lance un précontrôle à distance et exige ensuite confirmation explicite. Un test déjà actif sur la machine bloque toute nouvelle campagne de la liste.

## Rafraîchissement

L'unique cadence est celle du TestRunner : **60 secondes**. La vérification de l'espace principal précède le chargement des campagnes historiques pour éviter deux inventaires SSH simultanés. La mise à jour ponctuelle après connexion ou action est conservée. Aucun test n'est démarré automatiquement.

## Portée / sécurité / retour arrière

- Modifications limitées à la couche Studio (`studio/RVV_Lab_Studio.pyw`, cinq modules, tests d'interface).
- Aucun changement dans `engine/`, `tools/`, les scripts `studio/test_scripts/`, SSH `.env`, moteurs RISC-V, données, résultats et jobs distants.
- Si une régression apparaît, fermer Studio puis restaurer les fichiers du dossier `studio` sauvegardé avant l'installation.
- Ce patch a passé les contrôles de syntaxe, la suite de tests hors connexion et une ouverture graphique Tk dans un environnement de test. **Aucune validation de connexion réelle EPCC/Cloud-V depuis cet environnement** : confirmer l'état par Actualiser après installation.

## Origine de la refonte

Adapté au guide fourni `guide-architecture-interfaces-ia-v2` (en particulier UX-15 à UX-18) : parcours dominant unique, moins d'écrans concurrents, état fiable et action suivante, fonctions avancées conservées.
