# Audit du Test 99 EPCC et conception du Test 100

## Fichiers et portée de l'analyse

Source principale : archive intégrale fournie `test99-20261016T031241Z-839a48-FULL.zip`. Elle contient cinq binaires ELF RISC-V, les deux arbres source officiels clonés, le script natif, le lanceur Slurm, les paramètres de build et les journaux. Les chiffres des tests antérieurs proviennent des deux archives Test95 et du rapport/CSV Test97 fournis dans cette conversation.

**Aucune mesure de performance n'a été produite par le Test99 EPCC.** Tous les chiffres de débit mentionnés comme résultats de Tests 95/97 sont des observations Cloud-V antérieures, pas des résultats de Test99.

## 1. Diagnostic factuel EPCC

- Slurm job **14724**, `return_code=1` ; aucune mesure `results99.csv`, aucun résultat ZIP, ni `status99.json` final.
- `studio99-build.log`: **5 compilations PASS**, sans messages d'erreur dans les journaux `build99_*.log` (ces journaux sont vides en cas de succès).
- Cinq binaires ELF64 pour RISC-V, interpréteur `/lib/ld-linux-riscv64-lp64d.so.1` : deux officiels de 186 656 octets et trois A2 de 259 512 octets.
- `test99_OFFICIAL_503` et `test99_OFFICIAL_504` sont **strictement identiques par SHA-256** `6e9c2f191f97836f56ca83b319ad7d761aa507129f5b277da8b2738d51be127e`. Cela n'implique pas que leurs sources sont identiques ; cela constate l'identité de ces **exécutables** avec ces options de compilation.
- Les trois A2 sont distincts : `A2_REF` commence par `6be8b171...`, `A2_G6144` par `786636b6...`, `A2_G8192` par `594e0ef7...`.
- Versions officielles enregistrées : v5.0.3 commit `bf89ddd00ef5fcb6a7f20611ea8853d258b67249` et v5.0.4 commit `3b0b2b53aaffb46208817821dce2cd47a5e6bb2a`.
- Compilation EPCC enregistrée : LLVM Clang 16, `--target=riscv64-unknown-linux-gnu`, `-march=rv64gcv`, `-mabi=lp64d`, `-O3` ; `fallback` pour officiels et `rvv` pour A2.

## 2. Cause démontrée de l'échec

Le Test99 vérifie dans `test99_native.py` à la ligne 168 :

`4197c425e857f0ec38e89922fdd0bd9ea21f4daf`

Mais `tools/corpus98.py`, qui prépare le corpus réel partagé, épingle :

`4197c425e857f0ec38e89822fdd0bd9ea21f4daf`

**Une seule position diffère : `e89922` contre `e89822`.** Le script rejette donc le corpus vérifié, *avant toute mesure*. La vérification doit réutiliser la provenance de la bibliothèque commune, et avoir lieu **avant** de réserver le nœud Slurm.

## 3. Défauts supplémentaires détectés

1. `test99_epcc.sbatch` efface `status99.json` avant l'exécution. Comme l'erreur de commit survient avant l'initialisation de l'état natif, Studio ne trouve plus de statut et affiche `Unknown` pendant des heures.
2. Le paquet de résultats était conditionné aux fichiers d'une campagne avec mesures. Après un échec précoce, aucun ZIP de diagnostic n'était publié automatiquement.
3. Les deux exécutables officiels sont identiques, mais le protocole leur réservait deux séries de benchmark : aucun gain d'information sur EPCC.
4. Les 18 fichiers publics sont surtout des documents de grande taille. Des changements du seuil 4–10 Kio ne peuvent pas être évalués de façon pertinente uniquement avec eux, puisqu'ils passent souvent par le même chemin d'exécution.
5. L'itération fixe dans Test99 `2_000_000//bytes` ne calibrant pas le temps réel pouvait produire de courtes fenêtres sur petits JSON et des comparaisons plus bruitées.
6. Le Test99 tournait pendant une période fixe de huit heures, sans critère quantitatif d'arrêt en fonction de la précision ; sa confirmation réutilisait les mêmes fichiers (correctement indiquée comme temporelle).

## 4. Résultats pertinents des campagnes antérieures

- Tests95 : le seuil 8192 était supérieur au 4096 sur le holdout de **+2,57%** et **+1,39%**, mais les deux campagnes Cloud-V se chevauchaient sur le CPU0 et réutilisaient principalement les mêmes documents.
- Test97 Cloud-V : meilleure variante globale dans le holdout **A2_G10240 +1,68%**, suivie de 7168 **+1,27%**, 8192 **+1,21%**, 6144 **+0,99%** ; les gains étaient surtout liés aux documents synthétiques près du seuil. Sur le sous-ensemble réel, l'effet est faible.
- Par conséquent, **ni 8192 ni 10240 n'est validé pour la production** sur la seule base de ces tests. Il faut isoler les tailles et documenter les écarts sur des documents publics non modifiés.

## 5. Choix du Test100

- **Reference**: `OFFICIAL_504` (`fallback`) ; A2 control `A2_REF` 4096 et candidats 7168, 8192 et 10240 (`rvv`). Packed reste OFF. Nous ne gaspillons pas de temps à mesurer une deuxième fois `OFFICIAL_503` sur EPCC où il est bit-identique à la 504.
- **Corpus public immuable :** les 18 fichiers existants, vérifiés individuellement par SHA-256 et par révision Git. C'est la seule base de comparaison pour une différence globale avec le simdjson officiel.
- **Stress dispatch, classé séparément :** 57 JSON synthétiques déterministes couvrant 19 tailles autour de 4/6/7/8/10/16 Kio, trois familles de contenus. Ce stratum éclaire le dispatch, mais ne doit jamais être présenté comme représentatif de la production.
- **Validation avant mesure :** provenance sur login EPCC avant Slurm ; sur nœud RISC-V, intégrité des exécutables et contrôle DOM avant chaque campagne.
- **Convergence adaptative :** ≥45 minutes, ≥8 tours complets, ≥20 minutes de confirmation, demi-largeur indicative IC95 ≤1% sur les deux strates, deux tours consécutifs et dérive faible ; plafond de mesure 4h, limite Slurm 5h. Le test peut finir bien avant 8h s'il est concluant, ou annoncer explicitement qu'il n'a pas convergé.
- **Robustesse :** statut jamais supprimé, diagnostics ZIP SHA-256 même en cas d'erreur précoce, résultat enregistré par campagne sous un identifiant unique, prévention de concurrence, téléchargement depuis Studio.

## 6. Décision expérimentale

Ne pas modifier le moteur à l'avance. Sur EPCC, lancer Test100 après une pré-vérification du corpus de performance ; faire ensuite une campagne indépendante sur Cloud-V, sans autre benchmark actif. Les rapports doivent présenter séparément le classement sur documents publics, le classement de dispatch synthétique, la variabilité/les dérives et la reproductibilité entre machines. La réussite sur les exemples publics n'est pas une preuve universelle de vitesse ou de représentativité.

## Validation de ce paquet

Les validations locales portent sur la syntaxe, les chemins, la génération des entrées, la bonne révision Git et une simulation graphique du Lab. **Aucun benchmark natif Test100 n'a encore été lancé** sur EPCC ou Cloud-V ; l'exécution finale reste à valider sur ces machines.
