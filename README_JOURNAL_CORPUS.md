# Correctif Studio — fenêtre de journal + Copier tout

Ce correctif est destiné à **VLA-MethodLab**, après l'installation du patch « JSONTESTSUITE_DIAGNOSTIC » du 15 octobre.

## Installation DROP ROOT

1. Fermez Studio Cloud-V et EPCC.
2. Sauvegardez `studio/rvvlab_corpus_panel.py`.
3. Décompressez ce ZIP à la racine de `C:\mycode\Simdjson\VLA-MethodLab\` en acceptant la fusion/remplacement.
4. Relancez Studio, ouvrez **Corpus JSON → Conformité**, puis cliquez sur **Voir journal / Copier**.

## Comportement

- L'état **PC** affiche un résumé succinct. Les tracebacks ne sont plus affichés sur la page.
- Au moment d'une erreur de préparation, Studio affiche automatiquement la fenêtre **Journal de préparation** (fenêtre non modale et redimensionnable).
- La fenêtre montre le journal texte durable, avec défilement horizontal et vertical, les boutons **Copier tout**, **Actualiser**, **Fermer**. La copie va au presse-papiers Windows.
- L'affichage du journal ouvert est réactualisé localement toutes les 1,5 s sans lancer de requête SSH.
- La fenêtre montre les 8 derniers Mio si un journal dépasse cette taille, avec un avertissement explicite ; le journal complet reste sur disque.

Journal de conformité : `.cache/corpus-library/preparation-conformance.log`.

## Limites

- Le correctif répare **l'affichage et la copie** du diagnostic, pas la cause de l'échec du téléchargement JSONTestSuite.
- Ne prétend pas avoir téléchargé ou synchronisé de fichiers nouveaux.
- Aucun script de benchmark, aucun moteur, aucun cache ni résultat historique n'est remplacé.

## Validation hors connexion

50 tests automatisés réussis dans un environnement graphique virtuel, dont copie presse-papiers et présentation d'une erreur sans traceback sur la page principale. Installation sur votre poste à confirmer.
