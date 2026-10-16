# VLA-MethodLab — Correctif Corpus JSON (15 octobre 2026)

## Installation DROP ROOT

1. Fermer les Studios Cloud-V et EPCC.
2. Sauvegarder `studio/rvvlab_corpus_panel.py` si des modifications personnelles y ont été apportées.
3. Extraire le ZIP **dans `C:\mycode\Simdjson\VLA-MethodLab\`** et accepter le remplacement de ce seul fichier.
4. Relancer Studio, se connecter à Cloud-V, ouvrir Corpus JSON, sélectionner Stress RVV.
5. La ligne **PC : Vérifié** doit rester présente. Si une lecture SSH des tests est en cours, le message « Vérification automatique des tests en cours » apparaît sous les boutons; **Synchroniser** et **Vérifier serveur** se réactivent automatiquement dès que cette lecture se termine.
6. Cliquer sur **Synchroniser la machine** puis sur **Vérifier serveur**. Le serveur passera à « Vérifié » si le transfert et les contrôles aboutissent.
7. Refaire l'opération pour les autres corpus et pour EPCC, si désiré.

## Modification

Le code initial désactivait les actions distantes pendant les rafraîchissements SSH d'autres panneaux, puis n'actualisait pas leur état une fois ces lectures terminées. Le correctif ajoute une réévaluation **locale des boutons toutes les 1,1 seconde**, sans aucune requête SSH supplémentaire. Les protections empêchant la concurrence avec les opérations SSH existantes sont maintenues.

## Limites

- « Non vérifié » ne signifie pas « absent » : l'état serveur est inconnu jusqu'à une vérification ou une synchronisation.
- Le correctif ne lance aucun benchmark, ne modifie pas le registre de corpus et ne remplace aucun fichier JSON.
- Les boutons restent désactivés pendant une opération SSH ou un lanceur réellement occupé. Si le message reste bloqué, consulter le statut de connexion ou des tests avant toute autre opération.
- Comportement testé localement, **pas encore validé en SSH réel avec les serveurs de l'utilisateur**.

## Vérifications

- 9 tests de non-régression des corpus : OK.
- Test graphique du changement d'état polling SSH -> disponible : OK.
- Test graphique déconnexion / lanceur occupé / retour disponible : OK.
- Compilation syntaxique du fichier Python : OK.
