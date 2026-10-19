# Organisation en deux dépôts simples

**VLA-MethodLab** contient Studio, le Test Runner (81–94), l'orchestration,
les rapports, les expériences et une copie autonome `engine/` nécessaire pour
l'exécution immédiate. **VectorPath-RVV** contient le moteur en tant que
projet C++ à la racine. Cette livraison copie le même code moteur dans les
deux emplacements au lieu de créer un sous-module Git.

Installer en décompressant chaque ZIP dans la racine du dépôt correspondant.
Les deux `LICENSE` de GitHub restent intacts. Les licences tierces Apache-2.0 /
MIT sont fournies. Une modification future dans VectorPath-RVV doit être
reportée dans MethodLab/engine avant d'utiliser le Studio avec cette révision.
