# Deux ZIP, directement dans deux racines

1. Décompresser **VLA-MethodLab_DROP_ROOT_OVERWRITE.zip** à la racine du dépôt
   `VLA-MethodLab` et répondre **Remplacer tout**.
2. Décompresser **VectorPath-RVV_DROP_ROOT_OVERWRITE.zip** à la racine du dépôt
   `VectorPath-RVV` et répondre **Remplacer tout**.

Il n'y a **aucun sous-dossier wrapper**, aucune commande Git, aucun sous-module
et aucun lien symbolique à préparer. Les ZIP ne contiennent **pas** `LICENSE`
à leur racine : les licences GitHub préexistantes ne seront pas écrasées.

Le Lab contient temporairement son propre `engine/` pour rester fonctionnel
dès la décompression ; VectorPath-RVV contient le moteur directement à sa
racine. Ces deux versions du moteur sont alignées dans cette livraison.
Lors de futures modifications, synchroniser les sources avant les benchmarks.

Les deux raccourcis de Studio (Cloud-V et EPCC) fonctionnent dans MethodLab.
Les fichiers `.env` et les résultats privés restent hors de ces ZIP.

**Rappel :** déposer les fichiers sur disque n'effectue pas un `git push` et ne
publie rien sur GitHub. La licence choisie sur GitHub et les notices tierces
Apache-2.0 / MIT doivent être vérifiées avant une publication publique.
