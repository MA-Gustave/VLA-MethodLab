# RVV-VLA Lab Studio — mise à jour consolidée du snapshot 10131514

Cette mise à jour est construite **sur ton propre snapshot** `znapshot_RVV-VLA-Lab_10131514.zip`, avec les fonctions **Dual Machine Cloud-V / EPCC** et le **Test 94** déjà intégrées. Elle n'utilise pas l'ancien patch Dual Machine pour remplacer les versions plus récentes de tes fichiers.

## Installation, sans terminal

1. **Ferme RVV-VLA Lab Studio**. Les campagnes distantes détachées ne sont pas arrêtées par cette fermeture.
2. Extrais **`RVV-VLA-Lab_10131514_MAJ_DROP_ROOT.zip`** à `C:\mycode\Simdjson\RVV-VLA-Lab\` en conservant les sous-dossiers et en acceptant les remplacements.
3. Relance Studio normalement et ouvre l'onglet **Test Runner**.

Il existe aussi **`RVV-VLA-Lab_10131514_FULL_UPDATED.zip`**, qui contient le projet complet et non seulement les fichiers modifiés. Il ne faut **pas** écraser un autre répertoire de travail sans avoir sauvegardé les modifications faites après ce snapshot.

## Interface corrigée

- **Test 94** reste en haut de la liste des tests; les anciens tests 91/92/93 sont inchangés.
- Le tableau des scripts ne montre plus la colonne **SHA256 (prefix)** (mais la vérification SHA256 des scripts est toujours réalisée).
- Les campagnes affichent **Test / profile, State, Start time (PC), Elapsed, Phase, Measurements, Last update (PC)**.
- Les heures sont converties depuis les timestamps UTC en heure du PC; **`≈` indique une heure de démarrage estimée** depuis l'identifiant d'une ancienne campagne lorsque le serveur ne donne pas `started_utc`.
- Le bouton **Details** donne accès aux informations techniques complètes : ID, variante courante, disque, corpus, temps, raison d'arrêt. L'ID véritable reste la clé technique utilisée pour Stop / Sync / Open Results.
- Les **options de nœud Slurm EPCC** (`rvc02` par défaut) ne s'affichent que lorsque le profil **EPCC** est sélectionné.
- La **barre de défilement globale** et les **scrollbars des listes** du snapshot sont conservées.

## Réseau et Test 94

- Cloud-V : reprise des transferts SFTP interrompus déjà prévue dans ton snapshot, sans relancer automatiquement une campagne.
- EPCC : connexion par passerelle SSH et MFA, compilation croisée LLVM16 avec contrôle `riscv_vector.h`, choix de nœud Slurm, lancement et récupération automatique des mesures — comme dans ton snapshot.
- Une interruption SSH pendant le **rafraîchissement en lecture seule des campagnes** (ex. `WinError 10054` dans ton journal Test 92) affiche maintenant un message clair : **Reconnect / Refresh**. Les résultats précédemment synchronisés restent valables. Aucune boucle de reconnexion MFA silencieuse n'est tentée.
- Le compte Slurm n'est pas deviné; `rvc02` reste un **choix préféré**, pas une garantie matérielle sans validation sur EPCC.
- Aucune connexion aux serveurs réels n'a été effectuée pour produire cette archive. Les essais de connexion et de compilation natives devront être validés dans Studio.

## Tests et sécurité

La mise à jour a été testée **hors ligne** avec la GUI Tkinter, les scripts de tests 91–94, le simulateur Cloud-V/Slurm EPCC, le mécanisme MFA, la reprise SFTP et les dates des campagnes. Les deux manifestes SHA256 de release sont recalculés.

**Aucun `.env`, mot de passe, code MFA, clé privée ou donnée d'authentification n'est inclus.** Les rapports historiques déjà présents dans le snapshot sont conservés tels quels. Ne publie pas tes `.env` personnels ou les résultats contenant des secrets.
