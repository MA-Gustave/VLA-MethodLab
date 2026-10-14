# RVV-VLA — Test 90 et stratégie d’exploration

Audit du 12 octobre 2026, fondé exclusivement sur les quatre archives fournies. Aucun benchmark distant lancé et aucun code du moteur modifié.

## Verdict

Les dépôts fournis suffisent à analyser et à préparer la prochaine exploration : le Lab contient le moteur C++, les patterns, l’orchestrateur SSH, Studio et les workers. RepoDiag est le système de diagnostic externe, pas une bibliothèque supplémentaire de moteurs. Aucun ancien dépôt Studio séparé n’est nécessaire.

A2 est une bonne référence actuelle. Il n’existe pas de preuve que le système soit proche d’un optimum global. En revanche, le choix entre les cinq variantes du Test 90 offre peu de marge moyenne supplémentaire sur cet échantillon. Pour chercher de gros gains, il faut élargir les mécanismes disponibles et les contenus testés. Une nouvelle campagne centrée sur les seules frontières 512/4096 et la précision des répétitions ne répondrait pas à cet objectif.

## Résultats vérifiés

- Arrêt normal : `2-hour budget reached`, de 17:22:37 à environ 19:22:55 UTC.
- 8 402 observations ; 1 680 groupes complets de cinq moteurs et un groupe final de deux mesures.
- 496 JSON mesurés avec les cinq moteurs ; 496 SHA256 distincts.
- Reconstruction locale des 496 contenus depuis le worker fourni : tous les SHA256 correspondent au manifeste.
- Le SHA256 du programme C++ de mesure `BENCH_CPP` correspond à `metadata.code_sha256`. Ce champ ne représente pas le worker entier ni toutes les sources C++.
- Cinq compilations réussies, aucun échec dans `failures.csv`. Le journal annonce les contrôles 169 valides / 24 invalides et les smokes aux frontières réussis. Cela ne constitue pas une preuve exhaustive de conformité.
- Tailles réellement présentes : 480 à 66 310 octets. Aucun document immense dans ce Test 90.

Ratios DOM : appariement exact par phase, JSON, itérations et essai ; moyenne géométrique des ratios par JSON, puis entre JSON. Les deux dernières mesures sans groupe complet sont exclues.

| Variante | Ratio contre officiel VLS256 | Variation de débit |
|---|---:|---:|
| A2 | 1,2731× | +27,3 % |
| sparse8 | 1,0880× | +8,8 % |
| Officiel | 1× | référence |
| A1 | 0,9189× | −8,1 % |
| A0 | 0,6801× | −32,0 % |

Le `ranking.csv` fourni annonce +28,15 % pour A2 car chaque essai compte : les JSON davantage répétés pèsent davantage. Le rapport préspécifié des 88 JSON prioritaires donne +33,4 %. Ces trois chiffres ont des pondérations et populations différentes. Aucun ne reconfirme +64,1 % comme gain universel ; aucun ne prouve non plus une régression du code entre campagnes.

| Famille Test 90 | JSON | A2 / officiel |
|---|---:|---:|
| Frontière 512 | 104 | 1,5818× |
| Frontière 4096 | 136 | 1,0731× |
| Préfixe trompeur | 160 | 1,0355× |
| Mélanges concurrents de sparse8 | 96 | 1,8090× |

A2 est sous l’officiel sur 109 JSON ; 18 sont sous 0,90×. Le plus faible ratio moyen par cas est environ 0,835×, sur un document unicode_escape de 4 128 octets.

Si un sélecteur connaissait après mesure le meilleur des cinq moteurs pour chaque JSON, son ratio serait 1,2964× contre l’officiel, soit seulement **+1,83 % par rapport à A2**. C’est une enveloppe rétrospective sur ces variantes et ces mesures, optimiste car elle ignore bruit de sélection et coût de dispatch. Ce n’est ni une performance implémentée ni un plafond pour de nouveaux algorithmes ou pour des mélanges par région.

## Ce qui existe réellement

| Élément | État observé dans les sources |
|---|---|
| Orchestration | Déploiement SSH, exécution distante détachée, budget, contrôles, checkpoints, arrêt et synchronisation. À conserver. |
| Recherche historique | `rvv_night_runner.py` effectue un premier balayage puis sélectionne des finalistes parmi un catalogue fixe. |
| Campagnes 81–90 | Workers avec catalogues et protocoles codés ; le Test 90 répète cinq variantes fixes, sans création de nouvelles combinaisons. |
| Bibliothèque | `experiments/patterns.json` décrit E00–E14 ; paramètres effectifs dans `engine_plan.h`. Ce catalogue ne constitue pas à lui seul un générateur combinatoire général. |
| Caractérisation | `workload_profile.h` inspecte un préfixe, compte structures/chiffres/chaînes/échappements/UTF-8 et applique des règles manuelles. |
| Choix général | `engines::choose()` appelé une fois par parsing. A2 inspecte au plus 512 octets à partir de 4 Kio ; en dessous, configuration balanced sans inspection. |
| Adaptation locale existante | Writer choisi selon le nombre de structures du bloc ; chemins d’échappements ; raccourci pour blocs intérieurs à une chaîne ; vérification UTF-8 sur les vecteurs chargés. |
| Reconfiguration par région | Absente : `selected_` est conservé pendant le document. A3 est explicitement annoncé comme non implémenté. |
| Apprentissage | Pas de boucle observée convertissant automatiquement la carte des mesures en politique gagnante déployée. |
| Stage 2 | Tape builder générique conservé ; le bridge expose surtout une option de préchargement. |

Les familles escaped, unicode_escape et balanced ont les mêmes réglages effectifs dans `configure()` : seuil structural 8, échappement 8, fastpath actif, packed désactivé. Leur étiquette n’est pas consultée par le traitement RVV. Les sept familles non tiny représentent cinq configurations de cette fonction, pas sept algorithmes distincts.

Des macros globales sont aussi remplacées par les valeurs codées dans `configure()`. Un futur balayage de flags doit enregistrer les plans effectifs et vérifier que chaque axe modifie vraiment le code actif. Sinon, des centaines de noms peuvent mesurer le même comportement.

## Limites du corpus actuel

Le générateur des frontières met un petit contenu dans `body`, puis remplit `pad` d’ASCII. Autour de 4 Kio, **87,8 à 97,7 % des octets** sont ce remplissage. Les données restent utiles pour étudier le coût du classifieur et ses seuils, mais « dense » ou « unicode_escape » ne décrit pas nécessairement la majorité du document.

Les préfixes trompeurs contiennent un seul atome difficile entouré de remplissage. Ils ne remplacent pas des régions longues dont les proportions de structures, chiffres, chaînes et UTF-8 varient réellement. Les fenêtres head/middle/tail du manifeste sont des descriptions hors ligne ; elles ne prouvent pas le plan choisi à l’exécution.

Le benchmark réutilise un document et un parser échauffés. C’est une mesure utile de débit répété, pas une exploration de documents frais, des changements de corpus ou des grands ensembles excédant les caches. Le minutage Stage 1 / Stage 2 est direct mais ajoute des lectures d’horloge ; il ne faut pas additionner naïvement ces débits pour prédire le DOM.

## Programme proposé : exploration large avant raffinement

Les nombres suivants sont des budgets de conception à calibrer sur le serveur, pas des travaux déjà exécutés.

### 1. Composer des mécanismes, pas des noms

Première banque : environ 100–300 plans effectivement distincts, à partir d’un espace plus grand. Croiser writer (événements, compression, masques), stratégies d’échappement, quote/shift packed séparés, fastpath chaîne, politique de qualification et seuils grossiers. Exemples de seuils structuraux : 0, 4, 8, 16 ; seuils d’échappement : 0, 2, 8, 16. Garder des combinaisons complexes pour mesurer les interactions, même si leurs composants isolés sont médiocres. Dédupliquer après résolution des flags et contraintes.

Inclure un contrôle essentiel : balanced fixe sans aucun classifieur pour toutes les tailles, avec fastpath et packed identiques à A2. Cela distingue la valeur du choix de plan du seul bénéfice de supprimer une inspection coûteuse.

Certains contrôles existent déjà ; leur exposition indépendante et la composition générale demandent du code. Ce n’est pas un simple ajout de lignes JSON.

### 2. Intégrer la qualification au travail vectoriel déjà fait

Comparer qualification absente, préfixe court, échantillonnage réparti, puis qualification fusionnée aux masques déjà produits par Stage 1. Accumuler peu de statistiques et décider par région plutôt que rebalayer le document scalairement. Mesurer le coût complet de décision en DOM.

Une fenêtre prise au milieu d’une chaîne n’a pas un état JSON initial connu : ne pas réutiliser aveuglément `inspect_prefix()` avec `inside=false` à une position arbitraire. Employer des indices indépendants de cet état ou des signaux issus du parcours séquentiel réel.

### 3. Adapter les grandes régions d’un même JSON

Comparer plan global, décisions toutes les 4/16/64/256 Kio et décision déclenchée par changement de densité. Ajouter une durée minimale ou une hystérésis pour éviter les oscillations. Garder l’état de chaîne, la parité des antislashs, les suites UTF-8, les débuts de scalaires et l’ordre des indices entre régions.

Il ne s’agit pas de parser séparément des morceaux JSON arbitraires. Les régions changent la politique d’exécution d’un même parcours valide. Les compteurs de transitions doivent être mesurés dans une passe de diagnostic séparée pour ne pas déformer tous les chronométrages.

### 4. Essayer d’autres formes de boucle vectorielle

Le chemin courant charge e8m2 et écrit les indices en e32m8. Explorer un chemin e8m1/e32m4, différentes tailles de bloc ou déroulements, et des spécialisations qui retirent des branches du chemin chaud. Ces variantes nécessitent de vrais kernels compatibles, pas seulement un paramètre de plus. Leur gain est une hypothèse ; elles peuvent aussi perdre.

### 5. Élargir réellement les JSON

Viser quelques milliers de documents : familles pures, mélanges de 2–5 familles, proportions 10/50/90 %, alternances courtes et longues, transitions brutales et dérive progressive. Varier densité structurale, longueurs de chaînes/clés, profondeur, formats numériques, échappements et Unicode. Inclure des tailles de quelques dizaines d’octets jusqu’à 1/8/64 Mio, puis 256 Mio si mémoire et budget le permettent.

Les densités doivent rester contrôlées lorsque la taille augmente : agrandir en répétant ou variant les structures recherchées, pas principalement avec une chaîne de remplissage. Ajouter des documents frais en rotation et les corpus réalistes déjà disponibles. Dédupliquer par SHA256 et par géométrie effective.

### 6. Faire travailler l’orchestrateur par vagues

Conserver l’interface et le cycle de vie existants. Ajouter un worker exploratoire alimenté par un manifeste de compositions, avec graine, contraintes et cache de compilation indexé par sources/compilateur/flags. Le Test 90 a consacré environ 759 secondes aux cinq compilations ; extrapoler naïvement à 300 constructions représenterait environ 12,6 heures avant mesures. Réutiliser les builds identiques et compiler par lots est donc essentiel ; contrôler ensuite les finalistes avec des builds dédiés si le binaire multi-variantes change leur performance.

Répartition initiale proposée du budget : 65 % nouvelles combinaisons/corpus, 25 % interactions et spécialistes prometteurs, 10 % répétitions et contrôles. Une ou deux mesures courtes par point peuvent suffire au dépistage ; conserver des essais appariés à A2 et à l’officiel et mélanger l’ordre. Les comparaisons non appariées restent hors classement.

Ne pas mesurer exhaustivement chaque plan sur chaque corpus. Commencer par une couverture équilibrée des facteurs et quelques mélanges, puis allouer plus de mesures aux familles où des écarts importants apparaissent. Garder une fraction d’exploration aléatoire et les champions par famille, même si leur moyenne globale est faible. Une composition très forte sur un segment fréquent peut mériter sa place dans le moteur.

Règle de tri proposée : poursuivre les gains de l’ordre de 10–20 % ou plus sur une famille significative ; ignorer provisoirement les écarts de quelques pourcents. Ces seuils servent à orienter le budget, pas à déclarer une certitude statistique. Réserver de nouveaux seeds aux validations finales.

### 7. Relier la carte des résultats au moteur

Enregistrer configuration effective, caractéristiques du JSON, distribution par région, décisions réellement prises et débits. Construire ensuite une politique courte à partir des champions par régime, la geler et la mesurer sur des JSON nouveaux, avec son coût de sélection inclus. Conserver une référence robuste en cas de profil inconnu. Si Stage 2 devient dominant sur une famille, ouvrir alors un axe spécifique ; la suite A0/A1/A2 actuelle explore principalement Stage 1.

## Provenance et pièces éventuellement utiles

Le snapshot Lab est suffisant pour continuer. Pour prouver l’identité exacte de chaque source exécutée lors du Test 90, l’archive source déployée `20261012T172155Z-82aff0` et son manifeste détaillé seraient utiles : la provenance embarquée indique un checkout dirty et un nombre de fichiers, pas la preuve de chaque octet du moteur fourni. Ce n’est pas un dépôt manquant bloquant l’analyse. Les corpus et le programme de mesure sont, eux, recoupés comme indiqué plus haut.

Les rapports historiques sont utilisés comme contexte ; leurs classements ne sont pas fusionnés avec le Test 90. Aucune mesure RISC-V nouvelle n’a été effectuée ici. Les nouvelles compositions, kernels et politique par région restent à implémenter puis mesurer.

## Sources inspectées et recalcul

- Résultats : `map.csv`, `metadata.json`, `status.json`, `corpus_manifest.json`, `ranking.csv`, `VALIDATION_2H.md`, `failures.csv`.
- Orchestration : `orchestrator/rvv_night_runner.py`, `rvvlab_night.py`, `rvvlab_backend.py` ; workers 81 et 90.
- Plans : `experiments/patterns.json`, `PATTERN_LIBRARY.md`, `engine/src/rvv/engines/{engine_plan,workload_profile,structural_writers,stage2_bridge}.h`.
- Boucle : `engine/src/rvv/stage1.h`, `string_scanner.h` ; documentation Adaptive Dispatch v2.
- Architecture RepoDiag et rapport historique Engine Library 3 h.

`recalculate.py` utilise uniquement la bibliothèque standard Python. Exemple :

```text
python recalculate.py chemin/vers/night-20261012T172225Z-1942f9 sortie.csv
```

Le CSV joint contient les 496 ratios par JSON et le meilleur choix rétrospectif. Les micro-victoires entre moteurs quasi identiques ne doivent pas être interprétées comme des spécialisations fiables.
