# Test 95 — Cloud-V · 8 heures

Campagne prête à installer dans le **RVV-VLA-Lab** existant. Les scripts sont ajoutés sans écraser les tests 81–94 ni modifier l'arbre `engine/`. Aucun test n'a été exécuté sur Cloud-V depuis cette préparation : les vérifications réalisées sont statiques, syntaxiques et sur corpus JSON locaux (x86).

## Objet

Décider si les chemins *packed* réellement activés apportent un avantage sur A2 Quick Dispatch, puis explorer le seuil de dispatch autour de 4 Kio. Ne pas relancer LTO pendant ce test, puisque le Test 94 a échoué au compilateur GCC 14.2.

### Sept variantes natives

| Nom | Packed escape | Packed quote/shift | Packed index writer | Seuil A2 | Source |
|---|---:|---:|---:|---:|---|
| `A2_REF` | 0 | 0 | 0 | 4096 | **original non modifié** |
| `A2_CTL` | 1 | 1 | 0 | 4096 | overlay temporaire |
| `A2_IDX` | 0 | 0 | 1 | 4096 | overlay temporaire |
| `A2_BOTH` | 1 | 1 | 1 | 4096 | overlay temporaire |
| `A2_ESC` | 1 | 0 | 0 | 4096 | overlay temporaire |
| `A2_G2048` | 0 | 0 | 0 | 2048 | original non modifié |
| `A2_G8192` | 0 | 0 | 0 | 8192 | original non modifié |

**Point critique découvert dans le code :** en configuration A2 normale, `engines::configure(...)` remet les bits `packed_writer/escape/quote/shift` à `false` sur la plupart des documents. Changer uniquement les macros comme au Test 94 peut donc modifier l'assemblage du binaire **sans activer les algorithmes packed sur les grands JSON**. Pour lever cette ambiguïté, les variantes `CTL / IDX / BOTH / ESC` reçoivent un `engine_plan.h` **en overlay de répertoire include pendant la compilation uniquement**. `A2_REF` et les deux variantes de seuil compilent les fichiers originaux. L'overlay ne modifie pas le dépôt source et ne s'applique jamais à la référence. **Ces candidats ne sont donc pas le `packed_plain` du Test 94** ; leurs résultats ne doivent pas être assimilés aux anciens ratios.

Le sous-système `packed_control` inclut les opérations escape, quote et shift. `A2_ESC` isole escape pour pouvoir identifier une éventuelle régression provoquée par quote/shift.

## Durée et protocole

- **8 h maximum = 28 800 secondes d'horloge murale**, dont compilation des sept binaires, vérification des compilations, validation DOM et benchmarks.
- **Dernières 2 h** : holdout déterministe à nouvelles graines, non utilisé pour choisir les variantes lors du lancement.
- **Premières ~6 h** (compilation comprise) : exploratoire, ablation et frontières.
- **58 types de cas répétés** : 13 corpus de familles et grandes tailles, 1 mélange régional (UTF-8) et 44 corpus aux tailles exactes (4 familles × 11 tailles).
- **Frontières exactes** : `2047, 2048, 2049, 3584, 4095, 4096, 4097, 4608, 8191, 8192, 8193` octets, sur `ascii`, `dense`, `escaped`, `unicode_escape`.
- Les cas frontières utilisent un **champ JSON d'ajustement ASCII** afin d'obtenir exactement la taille voulue. Ils ne représentent pas automatiquement des charges de production. Ils sont volontairement surreprésentés ; lire séparément les sections `anchor` et `boundary`.
- Ordre d'exécution des sept variantes mélangé de façon déterministe à chaque groupe. Corpus, nombre d'itérations et SHA256 identiques dans chaque comparaison ; au plus 1000 itérations, y compris sur les petites tailles.
- Tests de classification JSON valides/invalides pour chaque variante ; **comparaison DOM vs le backend `fallback` pour chaque JSON et chaque variante avant de mesurer**. Un échec interrompt la campagne, sans « classement gagnant ».
- `-O3 -DNDEBUG -g0 -pthread -std=c++17 -march=rv64gcv -mabi=lp64d`, compilation native `g++` identique (hors macros spécifiques), cœur CPU fixé via `taskset` si disponible.
- Les résultats incluent `DOM`, `Stage 1`, `Stage 2`. Stage1 et Stage2 sont des mesures séparées, leur somme n'est pas confondue avec le temps DOM.

## Installation et lancement via Lab Studio (conseillé)

1. Sur le PC Windows, ouvrir la racine de `RVV-VLA-Lab` utilisée par Lab Studio (exemple historique : `C:\mycode\Simdjson\RVV-VLA-Lab\`).
2. **Extraire le ZIP à cette racine**, en conservant les chemins `tools/` et `studio/test_scripts/`. Cela ajoute les scripts Test95 et n'écrase pas les anciens.
3. Vérifier que le projet contient déjà `engine/src/rvv/engines/engine_plan.h` et que Lab Studio pointe sur le dépôt moteur local valide.
4. Relancer Lab Studio, choisir **Cloud-V**, connecter SSH comme d'habitude.
5. Dans **Test Runner**, sélectionner **Test 95 — A2 packed ablations + 4K gate (8h · Cloud-V)**, puis lancer manuellement (confirmation dans Studio). Cela téléverse le moteur par l'infrastructure SSH existante, compile sur RISC-V et lance un processus natif détaché. **Le Centre des tests 81–94 n'est pas automatiquement étendu : utiliser Test Runner.**
6. Garder Studio ouvert pour recevoir automatiquement le ZIP vérifié à la fin. Si Studio ferme ou si le suivi SSH se coupe, **le test distant continue** tant que le processus côté Cloud-V reste actif. Après reconnexion, sélectionner dans Test Runner **Test 95 — Récupérer la campagne Cloud-V**. Cela n'effectue pas un nouveau benchmark : la commande vérifie la dernière exécution connue dans le même répertoire de résultats Studio.

Aucun serveur n'est contacté par l'installation du ZIP. Le lancement nécessite une confirmation explicite dans Studio.

## Lancement direct (terminal Cloud-V, si le Lab est déjà installé sur cette machine)

Depuis le répertoire `RVV-VLA-Lab` :

```bash
python3 tools/test95_native.py plan --source engine
bash RUN_TEST95_DIRECT.sh
```

Cette commande crée un **nouveau** sous-dossier de résultats `test95-local-<UTC>` à la racine. Le script échoue si la machine ne porte pas `riscv64`. Ne pas lancer une seconde campagne de benchmark en parallèle.

Si seul le **suivi local** est interrompu, reconnecter Studio et exécuter le profil Recovery. Si le processus **distant lui-même** a été interrompu, il est possible de reprendre le même dossier **avant le délai absolu de 8 h**, sans prolonger le budget, après avoir examiné la cause :

```bash
python3 tools/test95_native.py run-only --source engine --output test95-local-<UTC> --resume
```

La reprise est refusée si la source a changé, si les SHA des binaires ne correspondent pas ou si les 8 heures sont expirées. Un échec de correction doit être diagnostiqué, pas ignoré.

## Sécurité / limites

- Vérification RISC-V native avant exécution, source moteur 5.0.3, SHA256 des binaires, de l'upload et de l'archive finale.
- Au moins **650 Mio libres avant de compiler** sept binaires ; sous **200 Mio**, arrêt de sécurité sans suppression de données hors dossier de test. Aucune commande `sudo`, aucun effacement automatique de projets, aucun remplacement de binaire production.
- Pendant une exécution, les données sont écrites en `results95.csv`, rapports et status ; le ZIP est renouvelé périodiquement et à la fin. Des groupes incomplets ne sont pas comptés comme groupes complets.
- Vérification différentielle face à `fallback` en amont du chronométrage. Les suites invalides/valides incluses ne constituent pas une preuve exhaustive de correction pour tous les JSON.
- L'expérience ne valide pas des modifications sur toutes les longueurs vectorielles ni sur EPCC. Refaire ensuite des tests indépendants sur charges réelles si un candidat sort gagnant.
- La couverture de boundary domine le mélange global (44/58 types). Ne jamais sélectionner une variante exclusivement sur le score `all`.

## Résultats et comparaison

Le paquet récupéré se nomme **`test95_results.zip`** et contient :

- `results95.csv` : mesures brutes de chaque groupe et variante, empreinte du JSON, taille exacte, nombre d'itérations.
- `builds95.json` : variantes, flags, SHA256 des binaires et preuve de l'overlay.
- `machine95.json` : profil de Cloud-V et affinité CPU.
- `status95.json` : état, budget et erreurs possibles.
- `summary95.json`, `REPORT_95.md` : premières comparaisons appariées.
- `manifest95.json` : design préenregistré, 58 types de cas et empreintes.

Analyse facultative sur le PC (Python 3 standard uniquement) :

```bash
python tools/analyze95.py chemin/vers/test95_results.zip --output DECISIONS_95.md
```

L'analyse regroupe les répétitions par types de cas et fournit ratios appariés Stage1/Stage2/DOM et IC bootstrap 95 % **exploratoires** (sans correction des comparaisons multiples). Une victoire globale doit être confirmée sur holdout, sur corpus réels et par répétition indépendante ; une variante qui gagne sur nested mais perd fortement sur UTF-8 reste spécialisée, non gagnante générale.

## Statut de préparation

- Manifestes Studio reconnus par `rvvlab_test_runner.discover()` sans erreur.
- Syntaxe de tous les modules Python validée.
- 44 corps frontières générés localement à **longueur exacte** ; JSON valide vérifié.
- Source non modifiée ; vérification locale de la priorité du header overlay via préprocesseur `g++ -E -H`.
- Script d'analyse essayé sur un CSV simulé ; aucun des débits de ce CSV de test n'est une mesure Cloud-V.
- **Non vérifié :** compilation C++ RISC-V réelle, correction et débits natifs ; seuls les 8 h sur Cloud-V les produiront.
