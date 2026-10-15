# Correctif DROP ROOT — Tests simples / Cloud-V Test 97

## Installation (aucune commande)

1. Fermer **toutes** les fenêtres Studio, Cloud-V et EPCC.
2. Faire une sauvegarde locale de `studio/rvvlab_simple_tests.py` et `studio/rvvlab_test_runner.py` si des modifications personnelles ont été ajoutées depuis le dernier patch consolidé.
3. Extraire **le contenu** de ce ZIP dans `C:\mycode\Simdjson\VLA-MethodLab\`, avec fusion/remplacement de ces deux fichiers.
4. Relancer Studio, choisir Cloud-V, connecter SSH, sélectionner **97** dans **Tests simples** et cliquer **Actualiser état**.

Le patch conserve le Test Runner, les tests 94/95/96 et tous les binaires/scripts du Test 97. Il ne modifie ni serveur ni moteur et **ne lance aucun test automatiquement**.

## Ce qui change

- `Actualiser état` consulte maintenant 3 sources : **campagnes distantes**, **processus actifs sur Cloud-V (/proc)** et **dernier journal Studio local**.
- Le suivi peut fonctionner **pendant qu’un lancement Test Runner est en cours**, sans différer systématiquement le statut jusqu'à la fin du benchmark.
- Affichage distinct de **Préparation/transfert local**, **Processus distant actif**, **Dossier distant sans statut**, **Échec du lancement local**, **Terminé avec ZIP**, et **Aucun lancement distant détecté**.
- `Run` est bloqué pendant une vérification, une préparation locale ou une campagne distante active/non confirmée. Si la vérification SSH échoue, l’onglet ne conclut pas à l’absence de test.
- Le Test Runner enregistre désormais les erreurs du lanceur dans `runner.log` et `last_failure.json`. Ces données sont affichées dans **Tests simples** lors des prochains échecs, même avant la création du dossier sur Cloud-V.
- L'heure de la dernière vérification distante est indiquée.

## Diagnostic observé le 15 octobre

La commande exécutée sur Cloud-V a répondu `AUCUN PROCESSUS TEST97` et `AUCUN DOSSIER TEST97`. **Aucun lancement distant n'a donc été observé à cette date**, sans preuve que le bouton Run soit allé jusqu'au lancement. Ce correctif permet d'identifier les échecs locaux au prochain essai, mais ne peut pas reconstituer rétroactivement une erreur qui n'a pas été journalisée.

## Vérifications

18 tests hors connexion réussis (compatibilité EPCC 94/96, Cloud-V 97, sécurité du téléchargement, statut local, absence de faux positif dans l'inventaire des processus) et affichage Tk sous Xvfb. Les connexions et workflows réels Cloud-V/EPCC ne peuvent être testés depuis cette machine.

## Précaution

Après installation, appuyer d'abord sur **Actualiser état**. Si l'onglet affiche qu'aucun test n'est présent sur Cloud-V mais une erreur de préparation locale, ouvrir **Ouvrir résultats** pour retrouver le journal indiqué. Ne jamais relancer sur la seule base d'un statut SSH non vérifié.
