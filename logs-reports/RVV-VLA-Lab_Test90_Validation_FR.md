# RVV-VLA Lab — Test 90 : rapport de validation indépendante

**Exécution :** `night-20261012T172225Z-1942f9` · **statut :** `stopped`, `2-hour budget reached` · **RISC-V RVV VLEN256** · GCC Bianbu 14.2.0 · simdjson 5.0.3.

**Données reçues :** `map(3).csv`, `prequal_pairwise.csv`, `ranking(3).csv`, `status(3).json`, `metadata(3).json`, `VALIDATION_2H.md`, `corpus_manifest.json`, `coverage_by_design.csv`, `failures(3).csv`, `SYNC_OK(3).txt` et rapports auxiliaires.

## Résumé exécutif

- **Test 90 : +28,1 % de débit DOM pour A2 par rapport à l'officiel VLS256**, moyenne géométrique de **1 680** paires essai × JSON (incluant les répétitions des 88 JSON prioritaires). Sur **496 corpus nouveaux pondérés également**, le résultat est **+27.3 %** (bootstrap descriptif 90 % **+24.8 % à +29.9 %**, rééchantillonnage par fichier, un seul matériel).
- **88 JSON prioritaires**, chacun mesuré trois fois dans la phase primaire : A2 vs officiel **+33,4 %** (rapport 1,334×; IC bootstrap descriptif à 90 % **1,281–1,390×** tel que déclaré par le worker). A2 vs sparse8 **+16,5 %** sur ces mêmes 88 JSON.
- **Test 89 : +64,1 %**, mesuré sur une autre distribution de JSON exploratoires. **Ne pas fusionner ces pourcentages ni les présenter comme une perte de performance du binaire** : ils décrivent des jeux de données différents.
- Les cinq moteurs ont compilé et passé les contrôles, **8 402 lignes natives** sans échec enregistré, **496/496 corpus mesurés sur les cinq variantes**, 496 empreintes SHA256 de contenus distinctes et **aucune empreinte en commun avec les 751 JSON distincts du Test 89**. Phase primaire complète (88 × 3 × 5 = 1 320 lignes), puis 7 082 mesures secondaires jusqu'à l'échéance.

## Méthodologie et classement

Valeurs ci-dessous : **moyennes géométriques des ratios de débit DOM appariés** (même document, même essai). Plus grand que 1× = plus rapide. Les répétitions sont corrélées.

| Moteur | DOM vs officiel, tous les essais | Gain en débit |
|---|---:|---:|
| A2 Quick Dispatch | **1,281×** | **+28,1 %** |
| sparse8 | 1,096× | +9,6 % |
| Officiel VLS256 | 1,000× | Référence |
| A1 Size Gate | 0,937× | −6,3 % |
| A0 original | 0,686× | −31,4 % |

**Comparaisons A2 directes, sans changement de corpus :**

| Échantillon | A2 / officiel | A2 / sparse8 | A2 / A0 |
|---|---:|---:|---:|
| 88 corpus prioritaires, 3 essais chacun | 1,334× | 1,165× | 1,851× |
| 496 corpus, poids égal par corpus (phase secondaire) | 1.273× | 1.170× | 1.872× |

Les 88 corpus prioritaires sont aussi présents dans la phase secondaire : le classement global à 1 680 essais pondère donc davantage ces 88 corpus. **L'estimation pondérée par fichier (496) est plus appropriée pour une synthèse équilibrée du holdout**, sans pour autant représenter l'ensemble des JSON du monde réel.

## Résultats par famille — A2 contre officiel (496 corpus secondaires)

| Famille synthétique | Corpus | Débit A2 / officiel | Documents où A2 gagne |
|---|---:|---:|---:|
| `deceptive_prefix` | 160 | 1.036× | 76.9% |
| `gate4096` | 136 | 1.073× | 47.8% |
| `gate512` | 104 | 1.581× | 100.0% |
| `sparse_challenge` | 96 | 1.809× | 100.0% |

### Hypothèse H1 — fenêtre de 512 octets

Sur de nouveaux corpus, le rapport A1/A0 est environ **1,13× à 511 octets** et **2,38× à 512 octets** dans les cas prioritaires du seuil. Cette frontière est reproductible dans les données reçues, **mais le nombre d'itérations du benchmark change entre 512 et 513 octets**; le modèle causal doit être confirmé avec un budget de mesure constant. **512 octets est une fenêtre d'inspection du classifieur, pas le seuil de dispatch de 4 096 octets.**

### Hypothèse H2 — rupture à 4 096 octets

Comparaison sur **les quatre familles conservées**, deux corpus inédits par taille et par famille, en phase secondaire. Toutes les valeurs sont des rapports de débit DOM ; les mêmes familles sont comparées des deux côtés du seuil.

| Famille | A2 / officiel à 4 095 | A2 / officiel à 4 096 | A1 / A0 à 4 095 | A1 / A0 à 4 096 |
|---|---:|---:|---:|---:|
| `ascii` | 1.338× | 0.922× | 4.301× | 1.006× |
| `escaped` | 1.297× | 0.927× | 4.012× | 1.004× |
| `dense` | 1.381× | 0.959× | 4.191× | 1.004× |
| `unicode_escape` | 1.112× | 0.845× | 3.396× | 1.005× |

**Interprétation :** c'est la découverte technique la plus nette. Sur 4 Kio exacts, A2 **devient moins rapide que l'officiel** dans ces quatre familles, malgré un avantage immédiatement sous le seuil. Le très grand gain A1/A0 sous 4 096 retombe autour de 1× à 4 096 : cela correspond au changement de chemin attendu. La qualité du routage à cette frontière mérite un benchmark dédié et une inspection du chemin de code choisi.

### Hypothèse H3 — A2 contre sparse8

Sur les 88 cas prioritaires : **A2 +16,5 %** en moyenne géométrique. Sur les 496 cas à poids égal : **A2 +17,0 %**. Sur la famille `sparse_challenge` seule (96 JSON), A2 dépasse sparse8 d'environ **+2,3 %**; ce gain de faible amplitude ne démontre pas qu'A2 domine sparse8 sur toute charge spécialisée.

### Hypothèse H4 — préfixe trompeur

Lorsque la partie difficile est décalée après les premiers 512 octets, A2 reste proche de l'officiel pour les cas prioritaires `prefix_after512` (rapport DOM environ **1,039×**, 16 JSON). Dans les cas où le préfixe trompeur n'est pas situé après cette limite, le résultat est **1,003×**, seulement quatre JSON. Les effectifs sont modestes; ils servent à orienter le prochain test, pas à trancher une causalité.

### Hypothèse H5 — Stage 1 et Stage 2

Sur les 88 corpus prioritaires, A2 contre A0 est **1,851× en DOM**, **2,257× en Stage 1** et **0,999× en Stage 2**. Le différentiel A2/A0 se manifeste donc surtout au **Stage 1**, cohérent avec Test 89. Les tests Stage 1 et Stage 2 sont chronométrés séparément; leurs débits ne s'additionnent pas au débit DOM public.

## Limites scientifiques

1. Une seule machine et un seul compilateur; les intervalles bootstrap par corpus ne remplacent pas des essais indépendants sur plusieurs machines.
2. JSON **synthétiques et présélectionnés** à partir des surprises du Test 89. Le +28,1 % n'est pas un gain universel de simdjson en production ni la promesse d'un adaptateur runtime capable de router correctement chaque JSON.
3. Répétitions de la phase primaire et secondaire corrélées : toujours regrouper les essais par fichier JSON avant d'estimer une incertitude.
4. Un changement d'itérations autour de 512/513 et la structure artificielle des corpus peuvent influer sur certaines mesures; contrôler ces paramètres avant de conclure à un seuil optimal.
5. Un test `stopped` par budget n'est pas une validation intégrale de tous les tours secondaires. Tous les 496 corpus ont cependant été couverts par cinq moteurs selon `coverage_by_design.csv`.

## Suite conseillée

- **Test 91 — profil ciblé de décision vers 4 096 octets**, de 3 840 à 4 352 octets, mêmes familles, tailles contrôlées, plusieurs graines et ordres alternés. Mesurer A2, sparse8, officiel et un hybride potentiel : chemin officiel ou spécialisé au-dessus de 4 Kio seulement quand un vrai signal de préqualification justifie son coût.
- **Tests réels** : jeux de données JSON publics non synthétiques, couvrant plusieurs tailles et styles, puis comparaison sur une autre machine RVV si disponible.
- **Mesure de la surcharge** : budget temporel constant autour de 512/513 octets, et coût isolé de l'inspection du préfixe et de la décision.

## Provenance

Les données proviennent des fichiers transmis et du `SYNC_OK(3).txt`, qui signale une synchronisation SHA256 validée par Lab. La présence de cet indicateur ne constitue pas une vérification cryptographique indépendante du serveur. Aucune expérience distante supplémentaire n'a été lancée pour ce rapport.
