# EPCC - connexion Lab Studio avec informations locales dans `.env.epcc`

Cette mise à jour concerne uniquement l'authentification EPCC. Les tests 91–94 et la connexion Cloud-V ne sont pas modifiés.

## Installation

1. **Fermer Lab Studio.** Extraire `RVV-VLA-Lab_EPCC_ENV_CREDENTIALS_DROP_ROOT.zip` directement dans `C:\mycode\Simdjson\RVV-VLA-Lab\`, conserver les sous-dossiers et remplacer les fichiers.
2. **Séparément** copier le fichier `.env.epcc` téléchargé dans `C:\mycode\Simdjson\.env.epcc` (hors dépôt Git).
3. Ouvrir ce `.env.epcc` en local et remplir `RVVLAB_JUMP_KEY_PASSPHRASE=` avec la **passphrase actuelle de ta clé SSH**. Cette valeur ne m'a pas été fournie ; ne l'envoie pas dans la conversation.
4. Relancer Studio, sélectionner EPCC et vérifier que le champ `.env` vaut `C:\mycode\Simdjson\.env.epcc`. Cliquer SSH Connect.

Le fichier de configuration fourni comprend la passerelle et le serveur interne, la clé privée ED25519 dédiée et les empreintes de serveur observées dans tes journaux OpenSSH. Il contient également le mot de passe interne que tu as demandé à enregistrer. **Il ne contient pas ta passphrase privée** ; celle-ci doit être saisie localement.

Quand les deux secrets sont correctement renseignés, Lab Studio ne doit plus demander **la passphrase de la clé SSH** ni **le mot de passe du serveur interne**. Le **code TOTP MFA de la passerelle** reste nécessaire pour ouvrir une nouvelle session EPCC ; le fonctionnement d'EPCC ne permet pas de le supprimer avec le `.env`.

## Sécurité

Ce choix conserve le mot de passe de la VM et la passphrase de la clé SSH **en clair sur le PC**. Ne jamais ajouter `.env.epcc` à Git ni à une archive du code. Limiter l'accès au fichier au compte Windows autorisé. Étant donné que le mot de passe de la VM a été partagé dans un chat, change-le quand cela sera possible et mets aussi le fichier à jour. Le ZIP du correctif ne contient **aucun secret** : le fichier `.env.epcc` est fourni séparément.

Si `RVVLAB_JUMP_KEY_PASSPHRASE` est vide, Studio demandera toujours la passphrase. Si elle est incorrecte, un message indiquera de vérifier cette variable. Une session SSH restée ouverte permet de lancer plusieurs tests sans ressaisir le TOTP.
