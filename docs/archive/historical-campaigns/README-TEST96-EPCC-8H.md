# Test 96 — EPCC / Slurm / LLVM 16 — 8 heures

**Préparé pour le VLA-MethodLab actuel.** Paquet additionnel au Test 95 Cloud-V. Rien n'est lancé par la simple installation du ZIP. Le Test Runner garde le **lancement manuel et confirmé**.

## Objectif

Tester sur **EPCC RISC-V** les sept variantes de Test 95 : `A2_REF`, `A2_CTL`, `A2_IDX`, `A2_BOTH`, `A2_ESC`, `A2_G2048`, `A2_G8192`. Mesures JSON DOM / Stage 1 / Stage 2, validité différentielle contre `fallback`, cas frontières `2047/2048/2049`, `4095/4096/4097`, `8191/8192/8193` notamment.

### Différence fondamentale avec Cloud-V

1. **Sur EPCC login x86_64 (`riscv-login`) :** déployer le moteur et les scripts par le SSH de Studio, charger les modules `riscv64-linux/gnu-12.2` et `riscv64-linux/llvm-16.0`, compiler **en croisé** les sept binaires RVV 1.0. Vérifier les intrinsics corrigés et le lien avec la libc++/libstdc++ cible par sonde. Vérifier les binaires `ELF64` RISC-V et les chemins d'inclusion overlay. **Aucun benchmark natif ici**.
2. **Sur nœud EPCC RISC-V (`rvc02` par défaut) :** soumettre **un seul job Slurm** `rvvlab-t96`, qui lance le runner natif seulement après allocation. `--time=08:10:00` (8 h mesures, 10 min marge), 1 tâche, 2 CPU demandés ; 7 variantes exécutées séquentiellement, jamais sept jobs parallèles.
3. **Durée :** les **28 800 secondes** sont comptées à partir du lancement du runner sur le nœud **après** l'attente en file et **après** la cross-compilation. Environ six heures d'exploration et deux dernières heures de *holdout*. Les opérations de cross-compilation et l'attente Slurm ajoutent du temps total, sans diminuer les huit heures de mesure. Il faut pouvoir réserver 8 h 10 sur la partition ; si la limite Slurm est inférieure, le programme refuse la soumission avec une explication.
4. **Sur le PC :** suivi périodique via SSH de Studio, récupération d'une archive ZIP de résultats avec vérification SHA256. La déconnexion/fermeture de Studio ne tue **pas** le job Slurm. La fonction « Récupérer Test 96 EPCC » permet de retrouver le dernier job enregistré dans le répertoire de résultats du même Studio.

## Installation Windows

1. Fermer **Lab Studio** (pas nécessaire d'arrêter les jobs distants en cours).
2. Extraire **`RVV-VLA-Lab_TEST96_EPCC_8H_DROP_ROOT.zip`** à la **racine réelle du Lab**, celle qui contient `studio/` et `tools/`. Selon le snapshot analysé et la capture d'écran, il peut s'agir de `C:\mycode\Simdjson\VLA-MethodLab\` (ou d'un dossier équivalent chez toi). **NE PAS** extraire directement dans `studio/test_scripts/`.
3. L'installation ajoute seulement `tools/test96_*`, `tools/analyze96.py`, `studio/test_scripts/96_epcc_*` et ce README : **elle n'écrase pas le moteur**, les Tests 81–95, les anciens résultats ni les profils SSH.
4. Le moteur sélectionné dans Studio **doit** contenir le correctif du fichier `engine/include/simdjson/rvv/intrinsics.h` pour Clang 16, qui utilise `__riscv_vlmul_ext_v_u8m1_u8m2` et `_u8m4`. En cas de message `PATCH_CLANG16_ABSENT`, installer le correctif LLVM16 précédemment fourni, **vérifier le chemin du moteur**, puis relancer le Test 96. Le paquet Test96 refuse de compiler d'anciennes sources EPCC.
5. Relancer **`LANCER_STUDIO_EPCC.pyw`**, sélectionner EPCC et établir la connexion SSH.
6. Dans **Test Runner** : `Refresh`, `Detect nodes` pour vérifier `rvc02`, sélectionner **`Test 96 — EPCC A2 packed + seuil 4K (8h, Slurm)`**, puis `Run selected` avec confirmation. **Ne pas sélectionner** une entrée `Test 95 — Cloud-V`.
7. Vérifier dans la console Studio la séquence :

   - `EPCC Test96: compiler verification and 7 cross-builds...`
   - `EPCC LLVM16 cross-toolchain OK...`
   - `EPCC Test96 Slurm job submitted: <numéro> on rvc02`
   - `EPCC Test96 job=<numéro> Slurm=RUNNING ...`

En cas d'arrêt **avant** `Slurm job submitted`, aucun job n'a été confirmé : examiner le journal `studio96-build.log`, qui est rapatrié automatiquement en cas d'erreur de compilation.

## Fichiers de résultat

Récupération vers `<Studio results>/TestRunner/test96-epcc-8h/<date>/` :

- `launch96.json` : ID du job Slurm, répertoire EPCC, empreinte SHA de la source et du runner.
- `test96_results.zip` : vérifié par SHA256 distant/local, dont `results96.csv`, `status96.json`, `REPORT_96.md`, `summary96.json`, `manifest96.json`, `builds96.json`, `machine96.json`.
- `studio96-build.log`, `slurm96-<jobid>.out` et `.err`, `slurm96-exit.json` : récupérés lors du diagnostic/à la fin quand disponibles.

Analyse locale (Python standard) :

```bash
python tools/analyze96.py "CHEMIN_VERS/test96_results.zip" --output DECISIONS_96.md
```

## Détails des protections

- **EPCC uniquement** : le lanceur et la récupération vérifient `active_profile == EPCC`. Pas d'envoi sur Cloud-V.
- L'exécution refuse `uname -m != riscv64` et exige une affectation Slurm. Le build refuse un hôte non x86_64.
- Le compilateur doit produire des binaires `ELF64 / e_machine=243 (RISC-V)` ; sept constructions valides obligatoires avant `sbatch`.
- Le correctif Clang16 doit être présent **localement puis dans la source déployée**. Aucun patch silencieux du moteur.
- Le runner originel Test95 est reproduit avec noms isolés `96`, et l'overlay n'est utilisé que par les candidats packed (pas par la référence) ; empreintes et dépendances compilateur sont enregistrées.
- **Disque** : 700 Mio libres prérequis côté EPCC ; arrêt sous 200 Mio. **Aucune suppression** automatique de sources ou résultats antérieurs ; pas de `sudo`.
- Les JSON passent des validations avant mesure et sont comparés au backend `fallback` avant chaque série ; un échec empêche toute promotion automatique.
- Les dernières 2 h ont d'autres graines que l'exploration, mais sont composées de données de synthèse : ne pas extrapoler sans nouveaux JSON réels.
- En cas de déconnexion Studio : sélectionner `Test 96 — EPCC : statut et récupération Slurm` puis `Run selected`; cela ne soumet **pas** un second job.
- `sacct` n'est pas nécessaire. La surveillance utilise `squeue`, `status96.json`, un marqueur de sortie `slurm96-exit.json` et les journaux Slurm. Un état absent est déclaré **incertain**, pas « terminé ».

## Vérifications réalisées avant livraison

Syntaxe Python et Bash vérifiées, manifestes reconnus par le Test Runner existant, rendu du plan `58` cas, validité des `44` corpus frontières et forme de l'overlay confirmés dans le snapshot local x86.

**Non vérifié à distance :** lien LLVM16 complet des sept variantes sur EPCC, exécution réelle sur `rvc02`, disponibilité des huit heures Slurm, validité RVV sur le nœud. Un échec du probe/build/jobbing doit être diagnostiqué avant toute autre campagne. Aucune mesure EPCC n'a été inventée.
