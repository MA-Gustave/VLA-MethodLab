# Test 94 — Cloud-V / EPCC : tout depuis Lab Studio

## Installation

1. Fermer RVV-VLA Lab Studio.
2. Extraire l'archive **DROP ROOT** dans `C:\mycode\Simdjson\RVV-VLA-Lab\`, en écrasant les fichiers proposés.
3. Relancer Studio avec son raccourci habituel. Aucun terminal, `cd`, `tar`, `scp` ou `sbatch` n'est nécessaire.

## Cloud-V (1 heure)

1. Dans Studio, choisir **Cloud-V**, puis cliquer **SSH Connect**.
2. Ouvrir **Test Runner** et cliquer **Run Test 94 (1h)**.
3. Confirmer. Studio transfère automatiquement une version SHA256 du moteur (reprise SFTP si le serveur coupe un canal), compile trois variantes natives et lance la campagne.
4. Rester dans Studio pour le suivi et le téléchargement automatique ; le test distant survit à la fermeture de Studio.

## EPCC (1 heure de calcul sur RISC-V)

1. Choisir **EPCC** et cliquer **SSH Connect** dans Studio. La passphrase de `id_ed25519_epcc` (si la clé est protégée), le code TOTP et le mot de passe du serveur `riscv-login` peuvent être demandés **dans Studio**. Le code TOTP est nécessaire pour la nouvelle connexion SSH ; une seule connexion ouverte permet de lancer plusieurs tests sans le ressaisir.
2. Dans **Test Runner**, cliquer **Detect nodes**. Studio récupère la liste depuis Slurm.
3. **`rvc02` est présélectionné par défaut** quand il est disponible ; contrôler le type RVV 1.0 avant la première campagne. Sinon choisir un autre nœud validé. Attention : le frontal `riscv-login` est x86, et certains nœuds du cluster ont seulement RVV 0.7.1 ou pas de RVV. Ne pas supposer que n'importe quel nom Slurm est RVV 1.0.
4. Laisser **Slurm account** vide, sauf si EPCC a confirmé un compte Slurm spécifique, puis cliquer **Run Test 94 (1h)**.
5. Studio essaie une compilation croisée **LLVM16 RVV 1.0** sur le frontal x86, valide `riscv_vector.h`, le lien C++ et le format binaire RISC-V avant de compiler A2, soumet le job `sbatch` au nœud sélectionné et surveille son état jusqu'à la récupération SHA256 des résultats. GCC 12.2 seul est RV64GC et ne fournit pas l'en-tête vectoriel requis dans l'environnement observé. La campagne mesure 3600 secondes **sur le nœud de calcul**, hors compilation préalable et attente dans la queue.

Les dépendances techniques doivent être disponibles sur EPCC : Slurm (`sinfo`, `sbatch`, `squeue`), modules `riscv64-linux/gnu-12.2` et `riscv64-linux/llvm-16.0`, `python3` sur le frontal et le nœud de calcul, et répertoire personnel partagé entre les deux. Studio présente un message d'erreur si un prérequis manque. Aucun serveur distant n'a été testé depuis ce paquet.

## Suivi, récupération et comparaison

- **Stop local monitoring** arrête seulement la surveillance côté PC ; il **n'annule pas** le processus distant ni un job Slurm.
- Après reconnexion à la même machine : **Recover Test94 results** télécharge les résultats lorsqu'ils sont disponibles.
- Quand les deux machines ont terminé : **Compare Cloud-V / EPCC** produit `TEST94_COMPARISON.md` localement. Chaque machine conserve ses résultats séparés.
- Dans Studio : **Open results** ouvre le dossier des mesures du profil courant.
- Les résultats comprennent `test94_results.zip`, `REPORT_94.md`, `machine94.json`, `results94.csv`, `summary94.json` et le statut de la campagne.

## Variantes et garde-fous

| Variante | Objectif |
|---|---|
| A2 `-O3` | Référence optimale présumée du Test 93 |
| A2 `-O3 -flto` | Hypothèse : optimisation LTO |
| `packed_plain` | Témoin sans exploration adaptative |

Validation native JSON, résultats appariés, holdout final, VLEN mesuré sur le nœud, refus d'un lancement sur architecture non RISC-V et vérification des fichiers transférés. Pas de promotion automatique de variante.

## Authentification et sécurité

- Ce ZIP ne contient ni fichier `.env`, ni clé privée, ni passphrase, ni mot de passe, ni code MFA.
- Studio recherche automatiquement la clé locale `~/.ssh/id_ed25519_epcc` pour EPCC si le chemin manque dans `.env.epcc`.
- Le MFA demandé par EPCC **ne peut pas être désactivé** : il est demandé à l'ouverture d'une nouvelle session Studio SSH, pas pour chaque opération tant que la session reste active.
- Pour un environnement hors test, utiliser les empreintes de clés d'hôte **vérifiées** et désactiver `RVVLAB_INSECURE_EPCC_TEST_MODE` dans ton propre `.env.epcc`.
- La commande Slurm n'est générée qu'après sélection explicite du nœud; la sécurité du compte et les quotas restent gérés par EPCC.

## Interface et diagnostic — mise à jour corrective du 13 octobre

- Barre de défilement verticale sur **toute la fenêtre Studio** ; molette conservée pour les zones de texte et les listes individuelles.
- Barres verticale et horizontale dans les listes **Test Runner**, **Campaigns**, **Server Storage** et ancienne liste d'exploration.
- Tests triés par numéro décroissant : **Test94 en premier**, puis Test93, etc.
- EPCC : **rvc02 par défaut**, remplacé seulement si indisponible lors de la détection.
- Cloud-V : le transfert SFTP du moteur est repris jusqu'à 5 tentatives avec taille et SHA256 du ZIP vérifiés. Une déconnexion complète SSH nécessite encore une reconnexion dans Studio.
- EPCC : précontrôle compilateur RVV 1.0 ; un manque de `riscv_vector.h` produit un diagnostic exploitable au lieu d'un job Slurm invalide.
- Le frontend EPCC x86 n'est jamais utilisé pour mesurer le benchmark, seul un nœud `riscv64` reçoit la charge.
- Les connexions réelles Cloud-V / EPCC ne sont pas disponibles pour les tests hors ligne ; aucune performance serveur n'est annoncée.

## Correctif du 13 octobre — EPCC LLVM16 (prétendu échec du précontrôle)

La tentative EPCC à 21:32 UTC a transféré les 762 fichiers (SHA256 OK) et a identifié
`rvc02` en `idle`, puis a échoué **avant** la soumission Slurm. LLVM 16 chargeait
`riscv_vector.h` correctement mais notre ancien précontrôle appelait le nom
obsolète `vsetvl_e8m1`. Il appelle maintenant **`__riscv_vsetvl_e8m1`** et
`__riscv_vsetvlmax_e8m1`, en accord avec l'API RVV 1.0 utilisée par simdjson.
Le précontrôle vérifie toujours le lien C++ et un binaire ELF RISC-V.

Le correctif n'altère pas le moteur simdjson ni les tests 91–93. Aucun job
Slurm n'a été lancé lors de la tentative EPCC en échec. L'utilisateur peut
relancer depuis Studio après remplacement de `tools/test94_epcc_build.py`.
Si une erreur différente apparaît pendant la compilation effective, transmettre
le nouveau log `EPCC build` pour diagnostiquer le compilateur ou la bibliothèque.
