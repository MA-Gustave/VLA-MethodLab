# Test 89 — Rapport d’analyse native exploratoire (1 h)

**Source :** `night-20261012T133100Z-5a6468-evidence.zip` (SHA256 `b807ca6d7bb16a232c890e11b5849350604189ebdd87611830aa1c2e428215e8`).
**Exécution :** `night-20261012T133100Z-5a6468` sur matériel RISC-V, VLEN 256, GCC Bianbu 14.2.0, compilation `-O3`.
**État :** `stopped` — `1-hour budget reached`, 2 453 observations, aucun échec dans `failures.csv`.
**Portée :** tendances de préqualification uniquement; la campagne ne démontre ni significativité statistique, ni gains sur d’autres machines, ni vitesse d’un routeur runtime entre backends.

## 1. Couverture et fiabilité de la collecte

Six configurations natives ont compilé et franchi les tests de validité (`169` JSON valides + `24` volontairement invalides) et les smoke natifs (`256`, `4095`, `4096`, `4097` octets).
Les 767 scénarios prédéfinis ont produit 751 contenus SHA256 distincts : 16 paires de noms « single » de tailles cibles voisines ont en réalité le même contenu. Les 51 cas « exact » ont tous leurs tailles réelles exactes.
380 identifiants de scénarios ont été mesurés (378 contenus SHA256 uniques), dont 379 avec les six moteurs. Les 81 scénarios prioritaires ont été mesurés une première fois, et 29 d’entre eux ont été répétés. Une seule vague exploratoire a été partiellement couverte (`fixed_round_completed = 0`).

| Design | Mesurés | Prévus | Couverture |
|---|---:|---:|---:|
| exact | 34 | 51 | 66.7% |
| heavy | 12 | 20 | 60.0% |
| pair | 166 | 352 | 47.2% |
| single | 65 | 128 | 50.8% |
| skew | 40 | 72 | 55.6% |
| triple | 63 | 144 | 43.8% |

Les comparaisons se font **sur les mêmes corpus et essais**, et non sur la moyenne arithmétique des débits. Les ratios de vitesse sont des moyennes géométriques de rapports appariés. Un ratio > 1 signifie que le numérateur est plus rapide.

## 2. Classement apparié au témoin officiel

| Backend | DOM vs officiel | Stage 1 vs officiel | Stage 2 vs officiel | N DOM |
|---|---:|---:|---:|---:|
| `A2_quick_dispatch` | 1.641× | 1.905× | 1.368× | 408 |
| `sparse8_escape8_reference` | 1.586× | 1.830× | 1.357× | 409 |
| `A1_size_gate` | 1.469× | 1.574× | 1.369× | 409 |
| `A0_E14_original` | 1.290× | 1.271× | 1.369× | 409 |
| `E01_adaptive` | 1.231× | 1.175× | 1.372× | 409 |
| Officiel VLS256 | 1,000× | 1,000× | 1,000× | 409 |

## 3. Comparaisons directes — importants pour éviter les faux écarts de classement

| Comparaison directe | DOM | Stage 1 | Stage 2 | Part DOM gagnante | Paires |
|---|---:|---:|---:|---:|---:|
| `A2_quick_dispatch` / `sparse8_escape8_reference` | 1.033× | 1.039× | 1.008× | 67.9% | 408 |
| `A2_quick_dispatch` / `A1_size_gate` | 1.117× | 1.210× | 0.999× | 77.9% | 408 |
| `A2_quick_dispatch` / `A0_E14_original` | 1.268× | 1.493× | 0.999× | 89.0% | 408 |
| `A1_size_gate` / `A0_E14_original` | 1.138× | 1.238× | 1.000× | 78.5% | 409 |

**Lecture :** A2 n’excède sparse8 que de ~3,3 % sur DOM avec les paires enregistrées (408). Son avantage sur A0 est nettement plus marqué au Stage 1 qu’au Stage 2. Il ne faut donc pas proclamer un gagnant général sur 3,3 % de données exploratoires non répliquées indépendamment.

## 4. Signaux qui valent un test ciblé

### Rupture vers 4 Kio — vrais fichiers aux tailles exactes

| JSON ASCII (taille réelle) | Répétitions | A1 / A0 DOM | A2 / A0 DOM | A2 / sparse8 DOM | A2 / officiel DOM |
|---|---:|---:|---:|---:|---:|
| 4095 octets | 2 | 4.738× | 4.701× | 1.703× | 1.244× |
| 4096 octets | 2 | 1.006× | 3.184× | 1.021× | 0.828× |

**Hypothèse :** le bypass A1 sur les très petits JSON et le classifieur rapide A2 produisent des changements de chemin autour de 4 Kio. Sur l’ASCII de 4 096 octets, A2 demeure moins rapide que l’officiel dans les deux essais (~0,828×), malgré son avantage sur A0. Cela exige un balayage continu des longueurs avec plusieurs jeux de données indépendants, pas seulement une comparaison des deux fichiers sélectionnés.

### Effet de la taille réelle — A2 directement contre A0 et sparse8

| Taille réelle | Paires A2/A0 | A2 / A0 DOM | A2 / sparse8 DOM |
|---|---:|---:|---:|
| ≤4 Kio | 95 | 1.742× | 1.071× |
| 4–8 Kio | 27 | 1.779× | 1.032× |
| 8–256 Kio | 182 | 1.170× | 1.018× |
| 256 Kio–1 Mio | 60 | 1.001× | 1.026× |
| >1 Mio | 44 | 0.997× | 1.029× |

**Hypothèse :** A1 répare surtout les petites entrées, tandis que le bénéfice A2 par rapport à A0 persiste entre 4 et 256 Kio; au-delà de 256 Kio, A2 et A0 sont beaucoup plus proches. La différence entre A2 et sparse8 reste modeste dans la plupart des tranches.

### Cas mixtes à inclure comme contre-exemples

Ces cas isolés sont des points de départ, **pas** des tendances fiables :

| Scénario | Octets | A2 / sparse8 DOM |
|---|---:|---:|
| `0498_triple_dense+numbers+utf8_front_262144.json` | 262,285 | 0.831× |
| `0259_pair_dense+unicode_escape_alternating_2048.json` | 2,211 | 0.872× |
| `0090_single_boolnull_uniform_4095.json` | 4,131 | 0.893× |
| `0078_single_many_keys_uniform_131072.json` | 131,445 | 0.897× |
| `0669_skew_numbers+ascii_front_1048576.json` | 1,048,648 | 0.907× |
| `0705_exact_ascii_threshold_4095.json` | 4,095 | 1.703× |
| `0702_exact_ascii_threshold_2047.json` | 2,047 | 1.453× |
| `0712_exact_ascii_threshold_16384.json` | 16,384 | 1.405× |
| `0701_exact_ascii_threshold_1024.json` | 1,024 | 1.379× |
| `0071_single_long_strings_uniform_1048576.json` | 1,049,500 | 1.372× |

### Stabilité locale et limites

Pour les 29 corpus prioritaires répétés, l’évolution du débit DOM essai 1 / essai 0 est de ~0,996× pour A2, ~1,000× pour A0 et ~1,003× pour l’officiel (moyenne géométrique). C’est rassurant sur ce court intervalle, mais insuffisant pour valider la reproductibilité entre sessions, gouverneurs et machines.
La compilation de six configurations a consommé environ 15,3 minutes du budget de 60 minutes. Le projet doit distinguer les coûts de compilation des mesures, surtout dans un pilote de 1 h.
**Important :** Stage 1 et Stage 2 ont été chronométrés directement et indépendamment; leurs durées ne s’additionnent pas nécessairement au DOM public. Le fait que le différentiel A2/A0 soit au Stage 1 est un indice, pas une attribution causale complète.

## 5. Plan de validation recommandé

1. **Test indépendant de seuil 4 Kio.** Générer plusieurs graines indépendantes ASCII, UTF-8, chaînes échappées et mélanges de 3 840 à 4 352 octets (pas rapprochés autour de 4 095, 4 096, 4 097). Répéter 5 à 10 fois les mêmes paires avec rotation de l’ordre; capturer les options d’exécution réellement prises par A1/A2.
2. **A2 contre sparse8.** Comparaison appariée sur des JSON *non utilisés dans Test 89*, en séparant les cas où A2 mène (UTF-8, chaînes longues, Unicode échappé) et les contre-exemples (scientific, whitespace+punctuation, certaines structures denses). Évaluer DOM et Stage 1 séparément.
3. **Confirmer les vrais grands JSON et la sélection sur préfixe.** Pour les mélanges front/middle/back, fixer la composition globale puis déplacer exclusivement la portion difficile derrière 512 / 4 096 octets, en contrôlant la taille finale et les caches.
4. **Reproductibilité et méthodologie.** Prévoir plusieurs sessions indépendantes sur la même machine, puis une autre configuration RVV si possible; conserver fichiers d’entrée, binaires, flags, SHA256, cycles si disponibles et journaux de température/fréquence.
5. **Corriger le générateur « single » nominal.** Éviter les 16 paires identiques SHA256 pour les tailles cibles 4 095/4 096; seules les familles `exact` garantissent aujourd’hui les tailles exactes. Ne pas traiter les réplications internes ou les doublons comme des observations indépendantes.

## 6. Éléments de preuve et réserves de publication

- Fichiers étudiés : `map.csv`, `prequal_pairwise.csv`, `ranking.csv`, `coverage_by_design.csv`, `corpus_manifest.json`, `metadata.json`, `status.json`, `failures.csv` et rapports du worker.
- La présence de `SYNC_OK.txt` indique que la récupération du Lab a été marquée SHA256 vérifiée; la présente analyse vérifie les rapports arithmétiques dans le ZIP, mais **ne constitue pas** une attestation cryptographique indépendante du serveur.
- `source_git_sha.git.commit` rapporte le commit du projet local; l’archive de résultats ne contient pas les fichiers source eux-mêmes. Le lien exact source/compilation ne peut donc pas être établi indépendamment avec ce seul ZIP.
- Aucun test 90 ni lancement natif supplémentaire n’a été effectué dans cette analyse.
