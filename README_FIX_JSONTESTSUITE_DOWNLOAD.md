# VLA-MethodLab — Correctif JSONTestSuite : téléchargement volumineux

## Symptôme

Le bouton **Corpus JSON → Conformité → Préparer / vérifier les JSON** renvoie :

```
ValueError: Upstream download missing/too large
```

La version précédente de `tools/corpus_jsontestsuite.py` arrêtait systématiquement le téléchargement si le ZIP *complet* de GitHub dépassait 48 Mio. Or, le dépôt `nst/JSONTestSuite` contient aussi des binaires et d'autres fichiers inutiles à notre corpus : seuls `test_parsing/*.json` et `test_transform/*.json` sont conservés dans le cache Method Lab.

## Correctif

- Limite de sécurité du téléchargement source augmentée à **256 Mio**.
- Téléchargement **en flux**, avec stockage temporaire sur disque au-delà de **8 Mio** de mémoire vive.
- Taille maximale contrôlée sur l'en-tête HTTP si présent, ainsi que sur les octets effectivement téléchargés.
- Traitement et vérification du ZIP en lecture seule, sans extraction générale du dépôt GitHub.
- Maintien des contrôles des fichiers JSON : taille maximale individuelle, taille totale, chemins autorisés, classes `y_`/`n_`/`i_`, manifestes et SHA-256.
- Fichier temporaire automatiquement fermé et supprimé même en cas d'erreur.
- Aucun changement aux corpus déjà préparés/synchronisés et aucun remplacement de script Studio.

La source reste épinglée au commit `1ef36fa01286573e846ac449e8683f8833c5b26a`.

## Installation (DROP ROOT)

1. Fermer Studio.
2. Extraire ce ZIP à la racine de `C:\mycode\Simdjson\VLA-MethodLab\`.
3. Accepter le remplacement du seul script `tools\corpus_jsontestsuite.py`.
4. Relancer Studio → **Corpus JSON** → **Conformité / JSONTestSuite** → **Préparer / vérifier les JSON**.
5. Attendre le résultat : `PC : Vérifié`, puis synchroniser vers Cloud-V et EPCC.

Aucun besoin de connexion SSH pour préparer le corpus sur le PC. Il faut en revanche une connexion Internet capable de télécharger l'archive complète du dépôt GitHub. Le ZIP définitif du corpus ne conserve que les tests JSON.

## Validation

- 52 tests automatisés locaux avec affichage virtuel : tous réussis.
- Comprend un test simulant un téléchargement de 49 Mio, au-dessus de l'ancienne limite.
- **Le téléchargement réel du dépôt GitHub n'a pas été vérifié dans l'environnement de construction** (accès externe indisponible ici).

Si la préparation échoue encore, cliquer **Voir journal / Copier**, puis **Copier tout**. L'erreur sera désormais plus précise, par exemple « Upstream ZIP exceeds safety cap 268435456 bytes », si le nouveau seuil est réellement dépassé.
