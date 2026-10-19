# Test 97 — EPCC RISC-V : A2 RVV vs simdjson officiel v5

**Statut : préparé, pas exécuté sur EPCC dans la session de développement.**

## Objectif

Mesurer le *gain total* du moteur RVV-VLA par rapport à la version publiée et non modifiée du projet officiel [simdjson/simdjson](https://github.com/simdjson/simdjson), sur **le même nœud EPCC rvc02**.

Ce test évite l'erreur de comparer seulement A2_G8192 à A2_REF, qui permettait de mesurer +1,87 % additionnel dans le Test96 mais pas le gain total vs simdjson de base.

## Quatre compilations obligatoires

1. `OFFICIAL_503` : tag officiel GitHub `v5.0.3` (HEAD commence par `bf89ddd`), backend `fallback`.
2. `OFFICIAL_504` : tag officiel GitHub `v5.0.4` (HEAD commence par `3b0b2b5`), backend `fallback` ; **référence principale**.
3. `A2_REF` : moteur labo v5.0.3, A2 RVV seuil 4096.
4. `A2_G8192` : même moteur labo v5.0.3, A2 RVV seuil 8192 (*meilleur candidat du Test96*).

**Important** : simdjson officiel en version 5.0.4 n'inclut pas le chemin RVV expérimental du laboratoire, et la référence sélectionne explicitement `fallback`. Le gain mesuré combine l'avantage d'utiliser un backend RVV au lieu du backend scalaire officiel, plus les optimisations A2. Ce n'est pas l'estimation d'un gain pur "à algorithme identique".

**Aucune version officielle n'est substituée par du code labo.** Les deux sources officielles sont clonées directement depuis GitHub sur le nœud login EPCC *avant* la compilation, leurs tags et empreintes Git sont vérifiés et consignés dans `builds97.json`. Si GitHub est inaccessible, aucune soumission Slurm n'est faite.

## Protocole

- Build croisé sur login x86_64 avec Clang16/LLVM16 RISC-V ; quatre binaires ELF64 validés ; mêmes options `-O3`, `-DNDEBUG`, `-march=rv64gcv`, `-mabi=lp64d`, `-std=c++17`.
- Exécution sur un nœud RISC-V via Slurm, 3 heures de mesures (`03:10:00` de réservation) avec 45 dernières minutes en holdout à graines indépendantes.
- **Même API publique DOM `parser.parse`, même C++ source de benchmark et mêmes documents**. Mesure médiane sur cinq séries, randomisation de l'ordre des quatre exécutables par groupe. Cache de fichier hors chronométrage.
- Jeux de données déjà définis dans Test96 (anchors, tailles limites, mélange). Chaque document doit être accepté et produire la même sérialisation DOM entre les quatre variantes avant tout calcul de débit.
- Ratios géométriques appariés par groupe, phase et scénario. Rapport principal `A2_G8192 / OFFICIAL_504`. Contrôle `A2_G8192 / A2_REF` pour suivre l'évolution intra-labo ; comparaison `OFFICIAL_504 / OFFICIAL_503` pour quantifier la dérive de version officielle.
- Pas de promotion automatique, de mise à jour des sources de production, de modification des jobs en cours ou de commande sudo.

## Lancement manuel

1. Faire une sauvegarde du dossier Studio et installer l'archive corrigée, en conservant `.env.epcc` et les dossiers de résultats existants.
2. Ouvrir Studio, choisir **EPCC** et se connecter.
3. Dans **Test Runner**, sélectionner `Test 97 — EPCC RVV A2 optimisé vs simdjson officiel v5 (3h)` puis cliquer sur **Run selected**. Cela déclenche explicitement le build puis, si tout est correct, la soumission Slurm.
4. Ne pas sélectionner **Run enabled queue** pour un lancement simultané de plusieurs tests : les manifestes sont `manual_only`, mais seul **Run selected** est recommandé.
5. Après l'exécution : **Refresh campaigns** puis **Sync results**, ou le script manuel `Test 97 — EPCC : statut et récupération résultats v5`.

## Fichiers produits

`test97_results.zip` vérifié par SHA256, contenant `builds97.json`, `machine97.json`, `status97.json`, `results97.csv`, `summary97.json`, `REPORT_97.md`, `manifest97.json`.

## Limites et conditions d'échec

- EPCC doit autoriser le clonage HTTPS des tags officiels depuis GitHub sur le login node. Pas de fallback vers une copie non vérifiée.
- Les quatre binaires doivent compiler avec Clang16 et lier sur la même plateforme EPCC. En cas d'échec de build, **aucune réservation Slurm n'est lancée**.
- La comparaison ne suppose pas que simdjson officiel possède un backend RVV. Le backend `fallback` est indiqué honnêtement dans le rapport.
- Une amélioration sur ces corpus synthétiques ne garantit pas le même gain sur des données de production. Analyser les familles et répéter les tests avant toute promotion.
