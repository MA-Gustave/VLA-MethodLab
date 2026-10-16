# Test 100 — Correctif du précontrôle de corpus (DROP ROOT)

**Pourquoi:** le manifeste `100_adaptive_public.test.json` imposait `requires_shared_corpus: performance`. Le lanceur général Studio appelle alors `require_remote` avant de charger le script Test 100. Sur une nouvelle machine, il échoue avec `Sync the corpus from the JSON Corpus tab.`, et le chemin de synchronisation déjà intégré à Test 100 ne s'exécute pas.

**Correction:** retirer ce précontrôle redondant **pour Test 100 uniquement**. Quand l'utilisateur clique Run, `100_adaptive_public.py` continue de valider le corpus local épinglé (18 JSON), synchronise et revérifie le corpus distant via `rvvlab_corpus_service.sync_remote`, puis déclenche `test100_native.py preflight` qui valide la provenance et les SHA-256 **avant toute compilation ou soumission Slurm**. Aucun assouplissement des validations.

Ce correctif ne touche pas aux fichiers des autres tests, aux sources du moteur ni aux données sur le serveur. Il ne lance rien automatiquement : Run reste manuel, et la protection anti-doublon existante demeure.

## Installer
1. Fermer Studio.
2. Extraire ce ZIP directement dans `C:\mycode\Simdjson\VLA-MethodLab\` et autoriser le remplacement du manifeste Test 100.
3. Relancer Studio, se connecter à Cloud-V, ouvrir JSON Corpus > Performance et vérifier **PC: Verified, 18 files**.
4. Dans Tests, sélectionner 100, faire Refresh, puis cliquer Run **une seule fois**. L'envoi des 18 fichiers peut prendre plusieurs minutes si Cloud-V ne les possède pas.
5. Vérifier que l'état passe à Starting/Building/Running; en cas d'échec, envoyer le nouveau `runner.log` et `last_failure.json`.

Alternative sans patch : JSON Corpus > Performance > Prepare / Verify > Sync to server > Check server, puis Tests > 100 > Run.

### Limites
Les seuls diagnostics inclus dans l'archive fournie par l'utilisateur sont le manifeste, le début du journal et le dernier échec local du 2026-10-16 12:27:06 UTC. Ils ne prouvent pas l'état actuel du corpus Cloud-V ; le correctif évite la dépendance au précontrôle et laisse le flux de synchronisation vérifié s'exécuter.
