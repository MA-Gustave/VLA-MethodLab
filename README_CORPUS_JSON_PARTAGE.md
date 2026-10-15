# MethodLab — bibliothèque JSON commune (Cloud-V / EPCC)

## But

Un **seul paquet de JSON épinglé**, préparé sur le PC et réutilisé sur les deux serveurs et par tous les **nouveaux protocoles qui optent pour ce corpus**. Ce patch ne remplace pas silencieusement les entrées des Tests historiques 81–97 : leurs comparaisons et résultats restent interprétables.

## Installation « DROP ROOT »

1. Fermer les instances Studio Cloud-V et EPCC (les campagnes distantes détachées continuent).
2. Sauvegarder `studio/` si vous avez des modifications locales.
3. Extraire le ZIP **dans `C:\mycode\Simdjson\VLA-MethodLab\`** en fusionnant les dossiers.
4. Relancer Studio. Le nouvel onglet **Corpus JSON** est à côté de **Tests**.

## Utilisation (une fois par machine)

1. Onglet **Corpus JSON** → **1. Préparer / vérifier les JSON**. Internet requis au premier téléchargement sur le PC seulement. La source est `simdjson/simdjson-data` à un commit immuable. Les 18 fichiers du Test 98 sont téléchargés et validés (JSON, taille, SHA-256, archive ZIP). Aucun JSON factice n'est utilisé.
2. Connecter **Cloud-V** → **2. Synchroniser la machine**. Le transfert SFTP inclut une vérification SHA-256 et une validation à l'extraction sur le serveur.
3. Changer de profil / ouvrir Studio **EPCC**, se connecter et cliquer **2. Synchroniser la machine**. Les deux machines reçoivent le même SHA-256 ; aucun accès Internet serveur n'est requis pour le JSON.
4. **Vérifier serveur** contrôle l'archive, le manifeste et les fichiers JSON extraits (lecture seule, sauf le vérificateur distant qui confirme un répertoire déjà extrait).
5. **Ouvrir cache** donne accès au ZIP portable : `.cache/corpus-library/simdjson-data-4197c425-test98.zip`. Ne pas confondre ce ZIP de données avec les ZIP de résultats des tests.

Si le Test 98 avait déjà téléchargé son ZIP dans `engine/.cache/test98-corpus`, le gestionnaire peut le réutiliser après validation, sans nouveau téléchargement HTTPS.

## Organisation

- PC : `VLA-MethodLab/.cache/corpus-library/<corpus-id>.zip` (cache ignoré lors des déploiements de code)
- Cloud-V ou EPCC : `~/rvvlab-v5/corpora/shared/<corpus-id>/<zip-sha256-prefix>/` ; le chemin `data/<corpus-id>/files/` contient les fichiers JSON validés
- Identité : `simdjson-data-4197c425-test98`, commit complet `4197c425e857f0ec38e89822fdd0bd9ea21f4daf`, 18 JSON, manifeste de tailles et SHA-256 fichier par fichier
- Les JSON sont des documents complets, pas du NDJSON ; ce n'est pas un corpus de conformité JSON invalide.

## Pour tous les **nouveaux tests**

Les scripts du Test Runner disposent d'une API commune (pas de secret ou de chemin codé en dur) :

```python
# Dans execute(ctx, params) d'un script de test approuvé :
corpus = ctx.shared_json_corpus()  # vérifie archive et fichiers sur la machine cible
input_dir = corpus['path'] + '/files'
# Enregistrer corpus['corpus_id'] et corpus['archive_sha256'] dans votre rapport.
```

Pour imposer le corpus sans devoir ajouter vous-même la vérification à chaque nouveau script, ajouter au fichier `*.test.json` :

```json
"requires_shared_corpus": true
```

L'exécuteur vérifie alors le corpus **avant `execute()`**, échoue clairement s'il est absent, et enregistre `shared_corpus_used.json` avec son identifiant, son chemin distant et son SHA-256. L'option est `false` par défaut, afin de ne pas modifier les tests historiques. **Le Test 98** utilise le cache commun automatiquement, même sans cette option, car il installe le corpus la première fois.

## Sécurité et limites

- ZIP téléchargé à partir d'une liste figée et d'un commit figé ; vérification complète JSON/SHA-256 à chaque synchronisation, rejet des entrées ZIP inattendues.
- Installation distante par contenu immuable : ne supprime pas les anciens corpus ou les résultats. Les transferts temporaires sont contrôlés et n'exécutent **aucun** benchmark.
- L'interface ne stocke pas de clés SSH : elle utilise uniquement la connexion existante et le profil actif.
- Si l'archive ou les JSON distants ont été modifiés, le contrôle échoue ; aucune réparation destructrice n'est automatique.
- La préparation locale et le transfert sont déclenchés manuellement, pas à l'ouverture de Studio.
- **Tests vérifiés hors connexion seulement.** Le premier téléchargement HTTPS réel et la première synchronisation SFTP Cloud-V/EPCC doivent être vérifiés sur les machines réelles.
- Vérifier les droits et licences par fichier auprès du projet amont avant de redistribuer les données elles-mêmes ; le patch ne contient aucun jeu de données tiers.

## Retour arrière

Fermer Studio, puis restaurer les fichiers `studio/` que vous avez sauvegardés. Le cache local et le corpus distant restent intactes et peuvent être conservés ou archivés séparément. Aucune suppression automatique.
