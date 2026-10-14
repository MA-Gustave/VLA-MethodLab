# Deux Lab Studio en parallèle — Cloud-V + EPCC

**Un seul dépôt est nécessaire.** Ne clonez pas `RVV-VLA-Lab` pour ouvrir les deux fenêtres : le code et les essais restent identiques. Utilisez les **deux nouveaux lanceurs `.pyw`** situés à la racine du projet.

## Lancement en deux clics (Windows, sans console)

1. Fermez les anciennes fenêtres Studio avant l'installation de cette mise à jour. Cela n'arrête pas les benchmarks déjà détachés sur les serveurs.
2. Extrayez le ZIP *DROP ROOT & OVERWRITE* à `C:\mycode\Simdjson\RVV-VLA-Lab\`.
3. Double-cliquez **`LANCER_STUDIO_CLOUDV.pyw`**. Cette fenêtre est réservée à Cloud-V.
4. Double-cliquez **`LANCER_STUDIO_EPCC.pyw`**. Cette fenêtre est réservée à EPCC.
5. Cliquez **SSH Connect** séparément dans chaque fenêtre, puis lancez, surveillez ou récupérez les résultats du Test 94 depuis le Studio correspondant.

L'accès EPCC requiert toujours MFA/TOTP lorsque le serveur le demande. Les fichiers SSH `.env` restent à leur emplacement actuel et ne sont pas copiés ni modifiés par cette mise à jour.

## Ce qui est isolé

| Élément | Fenêtre Cloud-V | Fenêtre EPCC |
|---|---|---|
| Réglages locaux | `%USERPROFILE%\.rvvlab_lab_v3\settings_cloudv.json` | `%USERPROFILE%\.rvvlab_lab_v3\settings_epcc.json` |
| Fichier SSH initial | `.env` Cloud-V habituel | `C:\mycode\Simdjson\.env.epcc` |
| Résultats par défaut | `%USERPROFILE%\RVV_Lab_results` | `%USERPROFILE%\RVV_Lab_results\EPCC` |
| Historique Test Runner | Dossier Cloud-V distinct | Dossier EPCC distinct |
| SSH, SFTP, logs et suivi | Propres à ce processus | Propres à ce processus |
| Verrou local | `cloudv.lock` | `epcc.lock` |

Les deux fenêtres partagent **uniquement le code source du projet**, consulté pour créer les snapshots, pas une session SSH ni un fichier de préférences. Les répertoires de travail distants sont sur deux serveurs différents. Les archives sources/Test 94 sont identifiées par des IDs uniques.

## Sécurité et garde-fous

- Le sélecteur de machine est verrouillé sur la cible du lanceur (pas de basculement accidentel de Cloud-V à EPCC).
- Deux fenêtres pour deux serveurs : **autorisé** ; une troisième fenêtre sur un serveur déjà contrôlé : **refusée** par un verrou du système d'exploitation. Les verrous sont relâchés même si le processus meurt ; **ne supprimez pas les fichiers `.lock`**.
- L'ancien lanceur `LAUNCH_RVV_VLA_LAB.bat` / `START_STUDIO.ps1` continue de fonctionner, mais participe aux mêmes verrous ; pour travailler en parallèle, privilégiez les deux `.pyw` ci-dessus.
- Les chemins de résultats des deux machines ne peuvent pas être exactement identiques. Conservez les dossiers séparés. Les campagnes et données historiques présentes dans `RVV_Lab_results` ne sont ni déplacées ni effacées.
- Les deux connexions sont indépendantes ; laisser tourner la fenêtre EPCC ne déconnecte pas Cloud-V, et inversement.
- N'éditez pas les fichiers `engine/` pendant qu'une des fenêtres prépare un snapshot source. Pour comparer strictement les performances, utilisez le même snapshot moteur sur les deux serveurs.
- Avant de démarrer Test 94 depuis **Run if needed (1h)** ou **Run selected**, Studio interroge l'historique distant, les processus Cloud-V ou les jobs Slurm EPCC. Il bloque les doublons confirmés **Completed**, **Running** et **Queued**. En cas de statut incertain il demande une confirmation renforcée ; si SSH échoue, aucun lancement n'est effectué.
- La découverte couvre les 60 dossiers Test94 distants les plus récents sous `rvvlab-v5/test94-runs`. Un statut inconnu n'est jamais considéré comme une réussite ni comme une preuve d'inactivité.
- Aucun serveur distant n'a été contacté pendant les tests hors ligne de la mise à jour.

## Résumé technique

La variable `RVVLAB_STUDIO_TARGET` est définie par chaque lanceur (Cloud-V ou EPCC). Studio route ses préférences sur un `settings_<machine>.json` propre, lit l'ancien `settings.json` uniquement comme source initiale de réglages non secrets, conserve les résultats historiques par cible et refuse une seconde prise de contrôle du même serveur par verrou inter-processus (`msvcrt.locking` sur Windows, `fcntl.flock` sur Linux).

Les essais locaux ont couvert le lancement GUI des deux profils simultanément, le verrou inter-processus, la séparation des fichiers de préférences, les régressions du Test 94 et le démarrage des widgets Tkinter. La disponibilité réelle des hôtes et la validité de leur toolchain RVV doivent être confirmées depuis Studio.

## Test 94 — vérifier avant de lancer

Dans **chaque fenêtre** indépendante :

1. Cliquer **SSH Connect** : Studio inspecte les dossiers de Test 94 sur la machine sélectionnée (Cloud-V ou EPCC), même si aucun lancement n'a été conservé sur Windows.
2. Dans **Test Runner**, cliquer **Check Test 94** pour une nouvelle vérification, sans démarrer de test.
3. Lire le statut **OK Completed**, **IN PROCESS Running**, **WAIT Queued**, **FAILED**, **NOT RUN**, ou **WARNING**.
4. Cliquer **Run if needed (1h)**. Studio vérifie **encore une fois à distance avant de lancer**. Il bloque l'exécution si elle est déjà terminée ou active ; sinon, il demande confirmation. Sur EPCC, choisir `rvc02` via **Detect nodes** avant de lancer.
5. Si le serveur a déjà produit une archive de résultats mais que le dossier local a été perdu, **Recover Test94 results** peut reconstruire la référence du lancement à partir du statut distant confirmé.

Rien ne démarre automatiquement à la connexion : une campagne d'une heure exige toujours un clic explicite et une confirmation. **WARNING** signifie qu'un ancien lancement existe, mais que ni fin validée ni activité actuelle ne sont certaines. Une nouvelle tentative nécessite alors une confirmation supplémentaire et peut dupliquer un travail non visible.

**Limites :** la vérification des processus reste un instantané et ne constitue pas un verrou Slurm/global côté serveur. Le compte SSH doit pouvoir lire les dossiers Test94 du serveur choisi. Les archives « completed » sont reconnues si le statut distant annonce des mesures et qu'une archive de résultats est présente ; la vérification SHA256 des octets téléchargés est réalisée par le bouton **Recover**. L'outil n'efface ni n'arrête aucun job distant.
