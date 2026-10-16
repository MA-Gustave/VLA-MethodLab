# Audit croisé Test 100 — EPCC et Cloud-V, puis plan Test 101

Date : 16 octobre 2026. Base : fichiers ZIP et CSV fournis par l'utilisateur. Toutes les statistiques ci-dessous proviennent des mesures Test 100, sans accès aux serveurs en direct.

## 1. Contrôles d'intégrité et traçabilité

| Champ | EPCC | Cloud-V |
|---|---:|---:|
| Campagne terminée | oui | oui |
| Mesures CSV | 13 125 | 14 625 |
| Tours complets | 35 | 39 |
| JSON publics originaux | 18 | 18 |
| JSON synthétiques | 57 | 57 |
| Variantes | 5 | 5 |
| Temps des mesures | 3997 s | 3939 s |
| Arrêt | `precision_reached` | `precision_reached` |
| Architecture | RISC-V `rvc02` | RISC-V `bpf3-16G-2` |
| Compilateur | LLVM 16 croisé | GCC natif |

Les deux campagnes ont **le même SHA-256 pour le banc d'essai, le source principal et le plan de dispatch** :

- Banc : `6a3190f0f9ce24ae06129529eb47b858625bd04c4fe39d65d946e09345089e4a`
- Fork `src/simdjson.cpp` : `fdaea284a48b30ab3e912e1cd3580e920fe186a229faabba97d9b24eed095e16`
- `engine_plan.h` : `7ebd7d2f4606c9ed9db77bcced50371e669698e5278f1afc4e5369fc5b4e7f4e`

Les exécutables ont des empreintes différentes entre machines, ce qui est attendu lorsque les chaînes de compilation et environnements matériels diffèrent. Les archives d'origine sont lisibles et tous les groupes contiennent une valeur pour chacune des cinq variantes. Les résultats sont des comparaisons de débit **DOM** appariées, pas des mesures de latence de bout en bout d'une application.

## 2. Ratios géométriques par catégorie (contre A2_REF, seuil 4096 octets)

| Seuil | EPCC — publics 18 | Cloud-V — publics 18 | EPCC — synthétiques 57 | Cloud-V — synthétiques 57 |
|---|---:|---:|---:|---:|
| 7168 octets | +0,06 % | −0,38 % | +5,88 % | +4,42 % |
| 8192 octets | +0,06 % | ≈ 0,00 % | +7,87 % | +6,30 % |
| 10240 octets | +0,44 % | −0,19 % | +9,66 % | +7,36 % |

Les moyennes géométriques sont à **poids égal par document**, séparément pour chaque corpus. Pas de score artificiel qui mélange 18 vrais documents et 57 fixtures.

### Effet du format sur les 57 fichiers synthétiques — seuil de 10 Kio

| Famille (19 fichiers) | EPCC | Cloud-V |
|---|---:|---:|
| ASCII | +26,24 % | +19,48 % |
| Structures denses | +2,66 % | +2,31 % |
| Échappements | +1,75 % | +1,22 % |

Les grands gains des benchmarks synthétiques sont tirés surtout par les chaînes ASCII entre 4 et 10 Kio. Ces gains ne doivent pas être présentés comme des gains sur le JSON réel en général.

## 3. Test des documents publics et sensibilité

- `twitter_api_compact_response.json` a une taille de **10 075 octets** et gagne **5,37 % sur EPCC** et **2,53 % sur Cloud-V** avec A2 10 Kio contre 4 Kio.
- **Si on retire ce seul document**, la moyenne des **17** autres documents passe à **+0,15 % sur EPCC** et **−0,35 % sur Cloud-V**.
- Sur le corpus complet, 10 Kio surpasse 8 Kio d'environ **+0,37 % sur EPCC** et est inférieur d'environ **−0,19 % sur Cloud-V** (ratios géométriques de ces mêmes fichiers).
- Les fichiers publics largement supérieurs à 16 Kio ne sont généralement pas discriminants pour des décisions de dispatch autour de 8–10 Kio. Le faible mouvement de leurs ratios peut refléter dérive, bruit, effets de compilation ou de placement mémoire, pas un changement effectif du chemin de dispatch.

**Interprétation :** les machines s'accordent sur le bénéfice pour les JSON synthétiques près des seuils ; elles ne permettent pas encore de promouvoir un seuil universel sur les vrais documents. Les 35/39 répétitions réduisent l'incertitude temporelle conditionnelle à ces fichiers, pas l'incertitude sur la population de documents réels. Ce sont deux machines et deux compilateurs, pas deux réplications à environnement constant.

## 4. Pourquoi un nouveau Test 101

Objectif : trancher entre **8 Kio** (référence pratique), **10 Kio** (meilleur synthétique observé), puis explorer **12 Kio et 16 Kio** sans les présumer meilleurs.

Les variantes compilées sont `OFFICIAL_504` (fallback), `A2_REF` (4096), `A2_G8192`, `A2_G10240`, `A2_G12288`, `A2_G16384`. La comparaison officielle mesure *fallback vs RVV* et non un « upstream RVV » qui n'existe pas dans ces binaires.

Trois catégories, jamais fusionnées :

1. **18 JSON originaux :** octets identiques à la sélection simdjson-data (commit `4197c425e857f0ec38e89822fdd0bd9ea21f4daf`), empreintes SHA-256 vérifiées.
2. **JSON dérivés des données publiques :** fragments structurés contigus d'objets et tableaux, sérialisés comme JSON valides; source et SHA-256 enregistrés. Ils reproduisent certaines structures observées, mais sont **transformés et ne sont pas des documents indépendants de production**. Sélection déterministe, jusqu'à trois fragments par source, contrôle d'au moins six fragments avant Slurm.
3. **87 fixtures synthétiques :** ASCII, échappements et structures denses ; tailles exactes de 3584 à 20480 octets, avec les frontières 8/10/12/16 Kio et voisins ±1.

Résumé par catégorie, moyenne géométrique par document et, pour les dérivés, moyenne donnant le même poids à chaque **source originale**. Comparaisons publiées directement contre **4 Kio et 8 Kio**, à la fois par document et globalement par catégorie. Pas d'attribution a posteriori de nouveaux niveaux à la population source.

**Protocole temporel :** au moins 60 minutes de mesures plus 30 minutes de confirmation, avec trois tours de précision consécutifs; seuil de demi-largeur environ 0,65 % par comparaison et catégorie, surveillance de la dérive de référence; plafond de 6 h de mesures, limite Slurm EPCC 7 h 30 incluant marge. Le plafond est une barrière de sécurité, **pas une promesse que des différences de 0,1 % seront tranchées**. Les résultats restent publiés comme non conclusifs si le budget est atteint sans convergence.

**Protection :** précontrôle du corpus et des dérivés avant compilation/Slurm, contrôle DOM entre les six binaires, SHA-256, CSV sauvegardé à chaque groupe, statut conservé, ZIP vérifié et archive de diagnostic récupérable même si échec avec zéro mesure. Ne lance pas une campagne concurrente sur la même machine.

## 5. Critère de choix pour la production

Un seuil n'est promu que s'il ne pénalise pas substantiellement les **originaux**, apporte un gain reproductible sur les **dérivés structurés**, et reste cohérent entre EPCC et Cloud-V. Les synthétiques sont un diagnostic utile mais ne suffisent jamais seuls à sélectionner un seuil de production. Pour valider des marges sous 1 %, prévoir des campagnes répétées sur plusieurs journées et, idéalement, davantage de documents publics originaux entre 4 et 16 Kio.

### Limites de validation actuelle

Le Test 101 a passé les tests **locaux** du Lab, mais sa compilation et ses mesures natives sur EPCC/Cloud-V n'ont pas encore été effectuées dans cet environnement. L'exécution devra confirmer la stabilité de la génération dérivée sur les véritables 18 fichiers.
