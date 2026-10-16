# VLA-MethodLab — Bibliothèque de corpus standardisés et RVV (octobre 2026)

## Installation (DROP ROOT)

1. Fermer Studio Cloud-V et EPCC. Sauvegarder le dossier `studio/` si personnalisé.
2. Extraire le ZIP **à la racine** de `C:\mycode\Simdjson\VLA-MethodLab\` et accepter le remplacement des fichiers indiqués.
3. Relancer Studio. L'onglet **Corpus JSON** comporte une liste « Catégorie » :
   - **Performance · 18 JSON** — corpus `simdjson-data` du Test 98, *inchangé* ;
   - **Conformité · JSONTestSuite** — fichiers officiels `test_parsing` (`y_`, `n_`, `i_`) et `test_transform` ;
   - **Stress RVV · 90 JSON** — JSON **synthétiques propres à Method Lab**, 6 familles x 15 tailles exactes.
4. Pour chaque catégorie : **Préparer / vérifier les JSON**, puis sélectionner Cloud-V ou EPCC, connecter SSH et **Synchroniser la machine**. **Vérifier serveur** doit confirmer l'installation et l'empreinte SHA-256. Seule la première préparation de JSONTestSuite nécessite Internet sur le PC.

La préparation **ne lance aucun benchmark**. Les fichiers publics sont téléchargés sur le PC depuis des URL immuables, mis en cache dans `.cache/corpus-library/`, puis transférés par SFTP avec vérification SHA-256. Ils ne figurent PAS dans le ZIP de patch et ne sont pas ajoutés au dépôt git.

## Corpus, origine, classement

| Identifiant logique | Source et révision | Utilisation |
|---|---|---|
| `performance` | `simdjson-data` SHA `4197c425e857f0ec38e89822fdd0bd9ea21f4daf`, sélection existante de 18 JSON | Débits DOM, Stage 1, Stage 2 ; Test 98. |
| `conformance` | `https://github.com/nst/JSONTestSuite` SHA `1ef36fa01286573e846ac449e8683f8833c5b26a` | Valider/rejeter des JSON selon RFC 8259 ; tester les cas limites. |
| `stress` | Générateur déterministe Method Lab `rvv-stress-boundaries-v1` | Aligner/tailler les documents RVV aux frontières de dispatch : 2, 4, 6, 8 et 16 Kio environ. |

Le corpus de performance comprend déjà des documents repris dans les comparaisons `nativejson-benchmark` (ex. `canada.json`, `twitter.json`, `citm_catalog.json`). **Nous n'ajoutons pas un second jeu de doublons** : l'outil de benchmark historique du dépôt `nativejson-benchmark` n'est pas installé.

### Classification JSONTestSuite

- `test_parsing/y_*.json` : **doit être accepté** (`PASS` si code de retour 0).
- `test_parsing/n_*.json` : **doit être rejeté** (`PASS` si code de retour 1).
- `test_parsing/i_*.json` : comportement **libre** ; acceptation/rejet = `UNSCORED` (non compté comme succès ni comme échec).
- `test_transform/*.json` : uniquement examen facultatif de transformations ; **aucune vérité normative d'acceptation**.
- Crash ou timeout : **jamais PASS**, même pour `i_`. Surveiller les exigences de profondeur, taille numérique et modes des parseurs ; une divergence mérite un diagnostic, pas nécessairement une assertion de non-conformité universelle.

**Important :** ne jamais essayer de parser le corpus JSONTestSuite avec `json.loads` pendant la préparation. Certains fichiers sont invalides volontairement, avec éventuellement des octets UTF-8 invalides. Ils sont stockés octet pour octet, avec hash par fichier. La suite comporte des centaines de cas, son compte exact apparaîtra seulement après téléchargement vérifié de la révision épinglée.

## Utilisation depuis les futurs tests

Dans un manifeste de Test Runner :

```json
"requires_shared_corpus": "conformance"
```

ou (pour demander plusieurs suites) :

```json
"requires_shared_corpus": ["performance", "conformance", "stress"]
```

`true` conserve le sens historique : exige seulement le corpus **performance**. Les suites sont **facultatives pour les Tests 94–97**, dont les jeux de données historiques ne sont pas modifiés. Avant un test déclarant une dépendance, le Test Runner valide sur la machine ciblée la présence et l'intégrité du ZIP et des fichiers installés, puis trace les identifiants dans `shared_corpus_used.json`. Une suite absente provoque un échec clair *avant* lancement.

## Vérification de conformité d'un binaire

Le module indépendant `tools/run_json_conformance.py` exécute un validateur **fichier par fichier**, avec timeout configurable, et produit :

- `conformance_results.csv` : fichier, attendu, observé, PASS/FAIL/UNSCORED/CRASH/TIMEOUT ;
- `conformance_summary.json` : agrégat et provenance.

Le programme de validation doit respecter les codes de sortie : **0 accepté, 1 rejeté, 2+ erreur/crash**. Il n'a pas besoin d'émettre du JSON.

Exemple de compilation **sur une machine où le dépôt Engine est déjà disponible** (compilation native Linux x86 seulement, avec RVV désactivé, pour contrôle des API) :

```sh
g++ -std=c++17 -O3 -DNDEBUG -pthread \
  -DSIMDJSON_IMPLEMENTATION_FALLBACK=1 -DSIMDJSON_IMPLEMENTATION_RVV=0 \
  -I engine/include -I engine/src \
  tools/simdjson_validator.cpp engine/src/simdjson.cpp \
  -o validator
```

Sur Cloud-V, compiler avec la chaîne et les drapeaux RISC-V **effectivement validés sur la machine** et vérifier le backend sélectionné. Sur EPCC, utiliser LLVM16 et le correctif intrinsics local ; compiler sur `riscv-login` et exécuter sur `rvc02` via Slurm, et **non** sur le login x86_64. Aucune commande Slurm n'est lancée par ce patch.

Exemple d'exécution manuelle sur une machine disposant d'un corpus extrait et du binaire `validator` :

```sh
python3 tools/run_json_conformance.py \
  --corpus /chemin/vers/jsontestsuite-rfc8259-1ef36fa01286 \
  --output /chemin/vers/rapports/conformance \
  --timeout 5 -- ./validator '{file}'
```

Cette CLI permet la vérification mais **aucun nouveau Test 99 automatique** n'est ajouté au bouton Run. Le lien à un nouveau lanceur de benchmark RVV doit être conçu séparément pour pouvoir vérifier la correction sans consommer 8 h de CPU inutilement.

## Sécurité, état et retour arrière

- Le téléchargement JSONTestSuite est épinglé au SHA `1ef36fa...` via `codeload.github.com`, et ne substitue jamais des JSON de démonstration si Internet échoue.
- Le ZIP public est reconstruit de façon déterministe et validé avant transfert. Limites de taille, chemins sûrs et SHA-256 protègent les archives.
- L'extraction distante est vérifiée avant que Studio indique « synchronisé ».
- Aucun des binaires, scripts de benchmarks 94–98, ni les résultats historiques ne sont remplacés dans ce ZIP.
- Pour le retour arrière, restaurer les trois fichiers Studio remplacés (`rvvlab_corpus_service.py`, `rvvlab_corpus_panel.py`, `rvvlab_test_runner.py`) depuis la sauvegarde effectuée avant l'extraction ; retirer facultativement les nouvelles commandes `tools/corpus_jsontestsuite.py`, `tools/corpus_rvv_stress.py`, `tools/run_json_conformance.py`, `tools/simdjson_validator.cpp`.

## Validation effectuée

53 tests automatisés hors connexion sur une copie du Lab, dont tests graphiques via écran virtuel, réutilisation du corpus Test 98, préparation déterministe, transferts SFTP simulés, vérification des corruptions et gestion des manifestes multi-corpus. Compilation native x86 du CLI `simdjson_validator.cpp` réussie avec deux fichiers smoke (acceptation/rejet).

**Non validé ici :** téléchargement GitHub réel, contenu intégral de JSONTestSuite à ce commit, transfert réel Cloud-V/EPCC et construction/exécution native RVV. Ce sont les contrôles de la première synchronisation.
