# Test 94 — Cloud-V versus EPCC, 1 h par machine

**Point de départ conseillé : A2 (RVV VLA, `-O3`, packed désactivé).** Test 93 a mesuré en holdout `packed_plain` à **0,955× A2** et la meilleure composition expérimentale à **0,723× A2**. Le nouveau Test 94 confronte A2 à `A2_LTO` (hypothèse) et `packed_plain` (témoin), avec des données JSON appariées, validation différentielle et rapport matériel complet.

**Deux fichiers téléchargeables :**

- `RVV-VLA-Lab_Test94_1H_DROP_ROOT.zip` : ajout de scripts dans les dossiers existants du projet Windows, sans modification de Studio.
- `RVV-VLA-Lab_Test94_SERVER_BUNDLE.tar.gz` : **bundle complet autonome** avec moteur simdjson 5.0.3 du snapshot du 13 octobre à 10:11 et scripts Test94 ; transférer une seule fois sur Cloud-V/EPCC. Il ne contient pas de mots de passe, `.env` ou clés SSH.

## Cloud-V (RISC-V direct)

Après transfert du bundle et extraction sur le serveur :

```bash
mkdir -p ~/test94-kit
cd ~/test94-kit
tar -xzf ~/RVV-VLA-Lab_Test94_SERVER_BUNDLE.tar.gz
python3 tools/test94_native.py all --source engine --output "$HOME/test94-cloudv-$(date -u +%Y%m%dT%H%M%SZ)" --seconds 3600
```

La compilation, les tests de correction JSON et les mesures partagent une limite totale d'une heure. Les trois variantes sont `A2_O3` (obligatoire), `A2_LTO` et `packed_plain` (optionnelles si le compilateur refuse une option).

## EPCC (frontal Intel puis noeud RISC-V via Slurm)

Après transfert du même bundle dans ton répertoire personnel et extraction :

```bash
mkdir -p ~/test94-kit
cd ~/test94-kit
tar -xzf ~/RVV-VLA-Lab_Test94_SERVER_BUNDLE.tar.gz
module load riscv64-linux/gnu-12.2
python3 tools/test94_native.py build-only --source engine \
 --output "$HOME/test94-epcc-prebuilt" \
 --cxx riscv64-unknown-linux-gnu-g++
sinfo -N -o '%N %P %t %f'
```

**Ne pas lancer le benchmark sur `riscv-login` : c'est un frontal x86.** Pour le travail Slurm, choisir un nœud **Milk-V Jupiter / K1-M1 à RVV 1.0**, puis vérifier avec EPCC son nom réel et les droits d'accès. L'exemple ci-dessous nécessite de remplacer la valeur factice :

```bash
export TEST94_SOURCE="$PWD/engine"
export TEST94_OUTPUT="$HOME/test94-epcc-prebuilt"
sbatch --nodelist=NOM_NOEUD_RVV10 \
 --export=ALL,TEST94_SOURCE="$TEST94_SOURCE",TEST94_OUTPUT="$TEST94_OUTPUT" \
 tools/test94_epcc.sbatch
squeue -u "$USER"
```

La mesure native dure **3600 secondes** sur la machine RISC-V (la compilation croisée x86 est faite au préalable). Le job Slurm réserve **1 h 08 min** pour que la génération finale du ZIP puisse se terminer. Selon la configuration du site, ajouter `--account=...` et/ou `--partition=...` à la commande `sbatch`.

## Résultats

Chaque exécution produit `test94_results.zip`, `test94_results.sha256`, `REPORT_94.md`, `machine94.json`, `status94.json`, `results94.csv` et `summary94.json` dans son répertoire de sortie.

Sur Windows, après récupération des deux ZIP de résultats :

```powershell
python tools\test94_native.py compare .\cloudv_test94_results.zip .\epcc_test94_results.zip
```

Résultat : `TEST94_COMPARISON.md`. Les mesures absolues sont comparées uniquement sur des corpus aux **SHA256 identiques** ; les ratios A2/LTO et A2/packed sont calculés sur des mesures appariées au sein de chaque machine. Pour l'analyse, transmet-moi les **deux ZIP de résultats**, jamais ton `.env.epcc`.

Pour les détails et limites, lire `README-TEST94-1H.md`. **L'accès SSH/MFA et le choix exact du noeud Slurm doivent toujours être effectués de façon interactive.**
