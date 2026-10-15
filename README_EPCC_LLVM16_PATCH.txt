EPCC LLVM16 — Correctif minimal (15 octobre 2026)
====================================================

Le diagnostic EPCC a établi :
- le test de compilation des intrinsics corrigés passe (RVV_PROBE_RC=0);
- les anciens déploiements du 13 octobre n'utilisent pas le correctif;
- aucune soumission Slurm n'a été observée pour ces essais.

Ce ZIP contient un seul fichier source corrigé, extrait du snapshot
znapshot_VLA-MethodLab_10141753.zip, compatible avec l'ancien mode LLVM16 :
  engine/include/simdjson/rvv/intrinsics.h

SHA-256 attendu du header: bece482e4923a79dfba674d2a82993ec3cfd5f6bf272e3791dc5ec219dac526b

INSTALLATION SUR LE PC LOCAL, PAS DANS LA CONSOLE SSH EPCC :
1. Fermer Lab Studio sur Windows.
2. Sauvegarder le fichier engine/include/simdjson/rvv/intrinsics.h
   s'il comporte des modifications locales à conserver.
3. Décompresser ce ZIP à la racine de C:\mycode\Simdjson\RVV-VLA-Lab\
   avec conservation de l'arborescence. Remplacer seulement le header indiqué.
4. Relancer LANCER_STUDIO_EPCC.pyw.
5. Vérifier que le champ moteur/repo pointe sur la version corrigée. Le script
   94_machine_1h.py utilise le dossier moteur sélectionné dans Studio quand
   celui-ci présente les chemins attendus; sinon il retombe sur engine/.
6. Lancer Test94 depuis Studio. Attendre un message "Slurm job submitted".
7. Après le nouveau déploiement, vérifier dans SSH Console que le header
   source déployé comporte __riscv_vlmul_ext_v_u8m1_u8m2. L'ancien dossier
   reste ancien : ne pas le modifier ni supprimer les anciens essais.

IMPORTANT :
Ce ZIP ne modifie ni le lanceur, ni Slurm, ni les benchs Cloud-V,
ni les configurations EPCC. Compiler != test réussi : un job Slurm et des
résultats de validité JSON seront nécessaires pour valider la campagne.
Si le dépôt local contient déjà le header corrigé, aucun ZIP n'est nécessaire.
Le diagnostic précédent sur EPCC porte UNIQUEMENT sur d'anciens déploiements.
