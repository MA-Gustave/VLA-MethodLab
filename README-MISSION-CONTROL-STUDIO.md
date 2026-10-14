# RVV-VLA Lab Studio — Mission Control (Cloud-V + EPCC)

## Installation : deux clics, un seul dépôt

1. Fermer les deux fenêtres Lab Studio pour remplacer les fichiers Python (les benchmarks distants déjà détachés continuent).
2. Extraire **`RVV-VLA-Lab_STUDIO_MISSION_CONTROL_DROP_ROOT.zip`** dans `C:\mycode\Simdjson\RVV-VLA-Lab\`, en conservant les dossiers et en acceptant l'écrasement.
3. Double-cliquer sur `LANCER_STUDIO_CLOUDV.pyw` et sur `LANCER_STUDIO_EPCC.pyw` pour ouvrir les deux instances indépendantes.
4. Dans **Dashboard / Mission Control**, cliquer **Connect SSH**, puis **Check Test 94**. Lire le statut confirmé avant d'utiliser **Run if needed**.

Il n'est **pas nécessaire de cloner le dépôt**. Les deux fenêtres possèdent déjà des paramètres, des historiques, des caches, des connexions et des racines de résultats distincts, avec un verrou par cible. Ne pas lancer deux fenêtres pour le même serveur.

## Nouveau tableau de bord

- **This Studio instance** : connexion de cette instance, dernier état connu du Test 94 et indication temporelle ; un état ancien ne reçoit pas la mention « live ».
- **Other server — cached, read-only** : dernier inventaire local conservé par l'autre instance. Jamais annoncé comme une interrogation SSH en temps réel.
- **What to do next** : recommandation contextuelle `Connect / Check / Wait / Recover / Retry`, fondée sur la dernière vérification disponible.
- **Connect SSH** → **Check Test 94** → **Run if needed** : actions distinctes et explicites. `Run if needed` effectue toujours une **nouvelle** vérification à distance avant toute tentative et demande confirmation. Aucun job ne démarre à la connexion.
- **Recover results** : récupération vérifiée par le Test Runner, sans effacer les fichiers des serveurs.
- **Copy safe status summary** : copie uniquement le nom du profil et les états génériques, sans mot de passe, clé SSH, chemin `.env`, nom d'hôte ni sortie console.

Le suivi à distance déjà présent reste actif (~35 secondes quand la session est disponible et que le canal SSH est libre). Mission Control rafraîchit aussi toutes les ~12 secondes **le cache local de l'autre serveur** sans créer de connexion SSH supplémentaire. Un état de plus de ~105 secondes est présenté comme **Last:**, même si la fenêtre SSH est toujours ouverte.

## Console SSH — raccourcis de diagnostic

Sous l'onglet **SSH Console**, choisir un raccourci et cliquer **Insert** (inspecter/modifier la ligne avant envoi) ou **Run command** (exécuter immédiatement le diagnostic choisi). Raccourcis : états Test 94, processus Test 94 / job Slurm, système/architecture, disque, `squeue` et `sinfo` sur EPCC. Aucun raccourci ne démarre ou n'annule un benchmark et aucune commande destructive n'est incluse.

## Test Runner — rechercher sans tout parcourir

La liste des tests est filtrable en direct par numéro, nom et fichier. Le menu **Show** affiche `All`, `Ready`, `PASS` ou `Disabled`. Le tri du plus récent au plus ancien est conservé ; le filtrage ne modifie aucun manifeste ni historique et ne lance jamais de test.

## Notes et limites

- Les états `Completed` sont liés à la présence d'un statut et d'un paquet de résultats sur le serveur ; la récupération vérifie les octets avant de les publier en local.
- L'inventaire est une photographie du serveur. Il ne remplace pas un verrou distant atomique entre des clients totalement indépendants.
- En cas de SSH indisponible ou de statut incertain, rien n'est lancé sans nouvelle vérification et, selon le cas, confirmation renforcée.
- Toutes les anciennes fonctions de Studio, les deux lanceurs parallèles et les Tests 81 à 94 sont conservés ; le moteur RVV, les intrinsics Clang 16 et les scripts des benchmarks ne sont **pas modifiés** par cette mise à jour ergonomique.
- Les tests locaux Tkinter et les simulations SSH/Slurm ne constituent pas une validation de la connexion réelle à EPCC/Cloud-V.
- Ne pas copier les fichiers `.env` ni les clés privées dans les ZIP de partage. Cette distribution n'inclut aucun de ces secrets.
