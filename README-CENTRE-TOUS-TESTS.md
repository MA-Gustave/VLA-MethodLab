# RVV-VLA Lab Studio — Centre des tests (81–94) · Cloud-V & EPCC

## Objectif

Un écran d'accueil pour **tous les 15 profils de test**. L'ancienne interface présentait principalement Test94, sans preuve claire de fin distante pour les expériences plus anciennes.

### Installation sur Windows

1. Fermer Lab Studio Cloud-V et EPCC. Cela ne stoppe pas les processus distants déjà lancés.
2. Extraire `RVV-VLA-Lab_CENTRE_TOUS_TESTS_DROP_ROOT.zip` dans `C:\mycode\Simdjson\RVV-VLA-Lab\`, en acceptant les remplacements.
3. Ouvrir les deux fenêtres avec `LANCER_STUDIO_CLOUDV.pyw` et `LANCER_STUDIO_EPCC.pyw`. Les lanceurs font partie du ZIP ; **aucun clonage du dépôt** n'est requis.
4. Connecter SSH dans chaque fenêtre. Le centre essaie de vérifier les anciens runs en lecture seule peu après la connexion. Cliquer à volonté sur **Vérifier le serveur** pour obtenir un état à jour.

### Actions dans le nouvel écran d'accueil

- **Rechercher** : numéro de test (81–94), mot-clé ou nom de fichier.
- **Filtrer** : tous, téléchargés, terminés sur le serveur, en cours, échecs, à vérifier.
- **Vérifier le serveur** : détecte les tests 81–93 depuis les `night-runs` et les campagnes identifiées par leurs métadonnées `campaign`, puis Test94 depuis ses `test94-runs`. Aucune modification distante.
- **Télécharger / synchroniser** : pour Test94, récupérer le ZIP via la routine de contrôle SHA256 existante ; pour les tests 81–93 associés sans ambiguïté à un `night-run`, utiliser `rvvlab_night.sync` (ZIP/manifestes SHA256). Si aucune correspondance sûre n'est disponible, guider vers Server Storage sans supposer un ID.
- **Ouvrir les résultats** : ouvre le dossier du test ou du snapshot local lorsqu'il existe.
- **Lancer le test sélectionné…** : confirmation explicite. Pour Test94, une nouvelle interrogation distante précède le lancement et bloque un doublon confirmé `completed`, `running` ou `queued`. Une tentative incertaine exige une confirmation supplémentaire.

### Signification des états

| Indicateur | Preuve / limite |
|---|---|
| **TÉLÉCHARGÉ** | Archive locale existante (Test94), ou marqueur `SYNC_OK.txt` de snapshot NightRuns vérifié par SHA256 ; lire les détails pour savoir si la campagne est partielle. |
| **TERMINÉ · distant** | État `completed` reçu du serveur (pour Test94 avec nombre de mesures positif et archive distante). |
| **EN COURS / EN ATTENTE** | Processus ou job présent lors de la dernière vérification. Ce statut peut être périmé après deux minutes ou après déconnexion. |
| **ARRÊTÉ · partiel** | Campagne interrompue volontairement ou par le budget, pas nécessairement un échec ou une validation complète. Les résultats existants peuvent être synchronisés. |
| **PASS local (à vérifier)** | Studio a terminé le script localement, mais la campagne distante et/ou la validité scientifique nécessitent une vérification distincte. |
| **À VÉRIFIER** | Aucun élément fiable sur le serveur, ou résultat ambigu. **Ne signifie pas « jamais exécuté ».** |

Les Tests **91 pilote** et **91 8 h** utilisent le même champ de campagne distant : si aucun `night-run` exact n'a été relié au profil local, Studio les laisse « À vérifier » plutôt que de confondre les deux.

### Limitations et sécurité

- Aucun serveur réel ne peut être interrogé pendant les tests locaux du correctif ; les tests hors ligne utilisent une simulation SFTP et des statuts fictifs.
- « Terminé » n'implique pas que la validité JSON ou la pertinence statistique ont été évaluées. Inspecter les CSV/rapports après récupération.
- Les observations distantes sont des **instantanés** : un second processus indépendant pourrait modifier le serveur après vérification. Aucun lancement automatique et jamais de purge automatique.
- Les anciens résultats se trouvent parfois sous un autre dossier Windows ; changer **Results directory** pour le bon dossier et actualiser le catalogue.
- Les fenêtres Cloud-V et EPCC ont des réglages, résultats et connexions distincts ; un verrou interprocessus refuse deux fenêtres sur la même machine.
- Aucun `.env` ni secret SSH n'est fourni dans ce ZIP. Le fichier `C:\mycode\Simdjson\.env.epcc` existant n'est ni modifié ni déplacé.
- Correctifs EPCC LLVM16 de compilation RVV maintenus dans le snapshot complet ; Cloud-V continue d'utiliser le chemin précédent pour les intrinsics.
