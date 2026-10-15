# Test 96 EPCC — correctif de sélection du dépôt moteur

## Constat

Le lanceur précédent utilisait le chemin de moteur mémorisé dans Studio
(`C:\mycode\Simdjson\RVV-VLA-Lab\engine` dans le message observé) sans solution
de repli lorsque ce dossier ne contenait pas `src\simdjson.cpp`.

## Installation

1. Fermer le Lab Studio EPCC sur Windows.
2. Sauvegarder, si modifié localement, `studio\test_scripts\96_epcc_8h.py`.
3. Extraire ce ZIP **à la racine du VLA-MethodLab**, le dossier qui contient
   déjà `studio` et `engine`. Accepter le remplacement du seul fichier Python.
4. Relancer `LANCER_STUDIO_EPCC.pyw`, se connecter à EPCC et relancer
   `Test 96 — EPCC A2 packed + seuil 4K (8h, Slurm)` depuis Test Runner.

## Comportement

- Si le dépôt sélectionné dans Studio est complet, le script l'utilise.
- Si le chemin est absent ou incomplet, le script cherche uniquement le moteur
  intégré dans `VLA-MethodLab\engine` et consigne clairement ce repli.
- Si aucun moteur complet n'est disponible, il arrête le lancement avec les
  chemins inspectés. **Pas de suppression ni de modification du moteur**.
- Le contrôle de version simdjson 5.0.3 et le correctif Clang/LLVM16 restent
  obligatoires même après repli. Aucun job n'est soumis en cas d'échec.
- Aucun changement à Cloud-V, EPCC/SSH, Slurm ou aux résultats antérieurs.

## Repères attendus dans la console Studio

`EPCC Test96 WARNING: configured engine missing/incomplete: ...`

`EPCC Test96: using installed Lab engine instead: ...\VLA-MethodLab\engine`

Puis seulement après cela : vérification LLVM16, 7 compilations croisées,
et éventuellement `EPCC Test96 Slurm job submitted: <numéro>`.

## Solution alternative sans installer le ZIP

Dans les paramètres Studio, corriger le chemin du dépôt moteur vers
`C:\mycode\Simdjson\VLA-MethodLab\engine` **si ce dossier existe sur le PC**.
L'ancien Test 96 fonctionnera alors pour ce premier contrôle de chemin.

## Vérification réalisée

Syntaxe Python OK. Tests locaux simulés : chemin périmé avec repli, chemin
correct vers dépôt, chemin correct vers racine Lab, refus de moteur non patché,
refus en absence de moteur. Pas de compilation EPCC distante exécutée ici.
