# Correctif Studio — état unifié Cloud-V / EPCC (15 octobre 2026)

**Déposer à la racine de `C:\mycode\Simdjson\VLA-MethodLab\`.**

Fermer les fenêtres Studio avant l'extraction, sauvegarder les trois fichiers concernés si vous avez des modifications personnelles, puis fusionner le dossier `studio` avec remplacement des trois fichiers Python. Relancer Studio.

## Changements

- Test Runner montre désormais l'état **distant vérifié** des Tests 94, 95, 96 et 97, et non uniquement `Ready (manual)` / `PASS` du lanceur.
- Jaune : préparation, compilation, exécution, attente ; vert : `completed` **et** validation **et** archive ZIP présente ; rouge : échec confirmé. État inconnu ou SSH indisponible : **pas de vert**.
- Les lignes sélectionnées conservent leur teinte d'état, et la sélection ne disparaît plus lors du rafraîchissement.
- Le tableau des campagnes dans Test Runner comprend aussi les Tests 95 et 97 Cloud-V (et les campagnes 94/96 EPCC).
- Le **rafraîchissement automatique existant de 60 secondes** alimente les trois vues (Test Runner, Tests simples, campagnes). Il n'y a plus de second timer 45 s de Tests simples.
- **Run selected** pour les Tests 94 à 97 passe obligatoirement par le même contrôle anti-doublon du serveur que **Tests simples → Run**. Un test déjà actif ne peut pas être redémarré par cette voie.
- **Sync results** pour les campagnes modernes utilise le téléchargement validé de Tests simples ; pour les ZIP en cours ou absents, il est désactivé.

## Fichiers remplacés

- `studio/rvvlab_test_runner.py`
- `studio/rvvlab_simple_tests.py`
- `studio/rvvlab_unified_campaigns.py`

Les scripts de benchmark, les fichiers `tools/`, le moteur, les sources distantes, les campagnes et les résultats **ne sont pas modifiés**. Un job détaché peut poursuivre son exécution après fermeture de Studio.

## Important

L'interface ne sait pas que la campagne a terminé sans lecture distante réussie. En cas de déconnexion SSH, elle doit indiquer un état non vérifié plutôt que de deviner. Le vert nécessite `state=completed`, `validated=true` et une archive ZIP non vide détectée sur le serveur. Une vraie vérification Cloud-V/EPCC n'a pas été exécutée ici ; seules les vérifications locales et simulations d'interface l'ont été.

## Installation

1. Fermer **Studio Cloud-V et Studio EPCC** (cela ne stoppe pas les campagnes détachées).
2. Faire une sauvegarde du dossier `studio` ou des trois fichiers ci-dessus.
3. Extraire cette archive dans `C:\mycode\Simdjson\VLA-MethodLab\` en conservant les dossiers et en acceptant de remplacer les fichiers.
4. Relancer Studio et reconnecter Cloud-V.
5. **Tests simples → 97 → Actualiser état**. Le Test Runner et sa table des campagnes doivent reprendre le même état au prochain rafraîchissement ou immédiatement après le clic.

## Tests locaux

25 tests automatiques réussis, dont 7 simulations d'interface ciblant la campagne 97 : préparation/compilation, fin validée, échec, sélection colorée, préservation de la sélection et routage Run selected par contrôle anti-doublon. Sans installation des bibliothèques ni connexion aux serveurs.
