# Test 91 — exploration large de compositions (Lab v6.0 expérimental)

Ce dépôt complet contient le moteur simdjson RVV-VLA, Studio, l’orchestrateur et les anciennes campagnes. Aucun autre dépôt Studio n’est requis. RepoDiag reste compatible et n’a pas besoin de modification.

## Installation et lancement depuis Studio

1. Fermer Studio. Extraire le ZIP complet dans `C:\mycode\Simdjson` : il contient le dossier `RVV-VLA-Lab`. Autoriser le remplacement des fichiers. Le ZIP ne contient ni `.env` ni `.venv`; les fichiers locaux existants ne sont pas supprimés.
2. Relancer `C:\mycode\Simdjson\RVV-VLA-Lab\LAUNCH_RVV_VLA_LAB.bat`.
3. Dans **Test Runner**, cliquer **Refresh**, sélectionner **Test 91 — Pilot 1h**, puis **Run selected**.
4. Lorsque le pilote est terminé, examiner son état et synchroniser les résultats. Si les trois builds passent et des mesures sont enregistrées, lancer **Test 91 — Broad exploration 8h** pour étendre l’exploration. Ne pas attendre une couverture complète du catalogue lors du pilote.
5. À la fin, sélectionner la campagne dans **RVV Lab campaigns**, puis **Sync results**. Envoyer le ZIP de cette campagne pour l’analyse.

Si Studio signale une source Test 91 absente, sélectionner `C:\mycode\Simdjson\RVV-VLA-Lab\engine` comme dépôt source.

Les deux profils Test 91 sont exclus de **Run enabled queue** et accessibles par **Run selected**. Aucun test n’est lancé automatiquement lors de l’ouverture de Studio. Le fichier externe `C:\mycode\Simdjson\.env` reste utilisé par le Lab.

Vérification locale facultative, sans SSH :

```powershell
$repo = 'C:\mycode\Simdjson\RVV-VLA-Lab'
& "$repo\.venv\Scripts\python.exe" "$repo\tools\test_exploration_91.py"
```

`--full` vérifie les 2 304 designs avec des tailles temporaires réduites et un véritable document de 64 Mio. `--cpp` exige un compilateur g++ local et teste la logique C++ portable ; il n’est pas nécessaire sous Windows pour lancer Studio.

## Ce qui est ajouté

- **242 configurations distinctes après normalisation** : 98 contrôles/plans fixes, 48 plans à préfixe, 48 plans régionaux, 48 plans à trois fenêtres. Les différents paramètres ne garantissent pas un comportement distinct sur chaque JSON.
- Compositions explicites de quatre banques : général, dense, texte, échappements/UTF-8. Writers, seuils d’échappements, opérations packed, chemins rapides de chaînes, fenêtre de qualification, taille de région et hystérésis sont combinés.
- Une configuration balanced sans classifieur pour toutes les tailles et une configuration A2 dans le binaire expérimental servent de contrôles.
- Jusqu’à **24 compositions supplémentaires** dérivées des spécialistes de familles, selon les résultats et les doublons. Pas de remplacement automatique du moteur de production.
- **2 304 designs** : 12 familles, mélanges de 2–5 familles, proportions équilibrées ou 9:1, alternances, régions de 4/16/64/256 Kio et dérive progressive. Cibles de 256 octets à 64 Mio, tailles réelles parfois légèrement supérieures pour terminer un atome JSON valide.
- Un seul corpus temporaire matérialisé à la fois. Chaque contenu mesuré est décrit par sa graine, ses paramètres, ses proportions réelles et son SHA256. Les résultats restent, le fichier temporaire régénérable est remplacé entre groupes.
- Trois compilations : **A2 dédié**, **officiel VLS256**, **binaire de compositions**. Les clés de cache locales à la campagne incluent les sources, le compilateur, les flags et le harness ; le hash du binaire est vérifié avant réutilisation. Il n’y a pas de cache partagé entre campagnes.

## Adaptation au sein du document

Le mode régional observe les masques produits par Stage 1, accumule des compteurs puis change de banque pour la région suivante. Une ou deux observations de région sont requises selon l’hystérésis. Le changement conserve l’état des chaînes, la parité des antislashs, l’état UTF-8 et le suivi des scalaires.

Les compteurs ajoutent du travail : ce mode n’est pas annoncé comme gratuit ni déjà plus rapide. Les traces séparées donnent les octets traités par banque et le nombre de transitions. Les parcours chronométrés désactivent les traces, tout en conservant le coût réel de qualification.

Le mode à trois fenêtres examine des indices d’octets bruts au début, au milieu et à la fin. Il ne suppose pas qu’une fenêtre intermédiaire commence hors d’une chaîne. Ces indices ne permettent jamais de sauter la validation JSON.

L’expérimentation propose également des plafonds de longueur vectorielle et le regroupement de 1/2/4 blocs dans la boucle. Elle conserve le couple e8m2/e32m8. Un kernel e8m1/e32m4 et un véritable déroulement spécialisé à la compilation ne sont pas inclus.

## Allocation des mesures

Un écran initial expose les configurations aux mêmes cas témoins, en faisant tourner les familles et tailles dès la première vague. Ensuite : environ 65 % de choix uniformes, 25 % de spécialistes et 10 % de répétitions, **en nombre de groupes**, pas en temps CPU exact. Chaque groupe comporte le candidat, A2 et l’officiel, sur le même JSON et les mêmes itérations, dans un ordre mélangé.

Les dernières 10 % du temps disponible après compilation sont réservées à des finalistes figés sur de nouvelles graines. Ces données ne servent pas à ajuster la sélection. Les classements exploratoires donnent le même poids à chaque JSON dans une famille ; ils ne fusionnent pas des populations différentes pour proclamer un gagnant global.

Le budget inclut compilation et contrôles natifs. Il est normal de terminer avec une couverture partielle. Le catalogue représente les possibilités, pas une promesse de mesurer toutes les paires configuration × document.

## Validité et arrêt

Avant toute mesure d’une composition : 215 JSON valides, 80 invalides, comparaisons complètes du DOM avec fallback, et cas traversant les frontières de blocs et de régions jusqu’à 256 Kio. Avant chaque groupe chronométré, le candidat est aussi comparé au DOM fallback sur le JSON réellement mesuré. Une composition incorrecte est exclue ; un échec de référence arrête la campagne.

Seuil disque conservé : 200 Mio. Contrôle périodique de 15 minutes, vérifications plus fréquentes pendant le travail, limite de travail de 2 Gio. **STOP** depuis Studio reste un arrêt contrôlé. Aucun historique n’est supprimé. Seul `active_corpus.json`, créé par la campagne et reproductible, est supprimé après son groupe.

Les checkpoints conservent l’état et les données pour analyse ; cette version ne reprend pas automatiquement une campagne interrompue. Elle refuse de réutiliser un répertoire qui contient déjà `status.json`.

## Résultats à examiner

- `EXPLORATION_91.md` : couverture, spécialistes exploratoires et résultats séparés sur nouvelles graines.
- `map.csv` : mesures DOM, Stage 1 et Stage 2, identifiants d’appariement.
- `composition_catalog.json` : configurations effectives, origines et exclusions.
- `corpus_manifest.json` : designs prévus et empreintes des contenus matérialisés, familles réellement présentes.
- `diagnostics.csv` : banques utilisées, régions et transitions, mesurées hors chronométrage.
- `schedule.json` : ordre réel des groupes et des moteurs.
- `policy_candidates.json` : propositions expérimentales et liste figée des finalistes ; aucune promotion automatique.
- `build_provenance.json` : empreintes des sources et binaires réellement compilés.
- `failures.csv`, `metadata.json`, `status.json` et `checkpoint.json` : contrôles et état final.

## Validation de cette livraison

Contrôles locaux : génération de toutes les géométries à taille réduite, document réel de 64 Mio, logique C++ des 242 configurations, simulation du scheduler et des paires, invalidation de candidats, arrêt/disque, vérification des deux synchroniseurs, découverte Studio et hashes. Le programme de benchmark a aussi été compilé et exécuté avec fallback sur l’hôte local ; cela ne teste pas le chemin RVV.

**La nouvelle compilation RVV et ses performances restent à vérifier sur le serveur.** Aucune campagne distante n’a été démarrée pendant la préparation de ce dépôt. Le mode expérimental exige `SIMDJSON_RVV_EXPLORATION91=1`; les builds ordinaires et anciens tests gardent leur politique existante.

Le générateur répète une banque déterministe de 16 atomes par famille : le contenu est varié entre designs mais ne prétend pas reproduire tout le trafic réel. Le benchmark chronomètre un parser et un document échauffés. Le mode documents frais/caches froids, d’autres LMUL et des kernels Stage 2 spécialisés constituent des extensions ultérieures, pas des fonctionnalités annoncées comme terminées ici.

## CLI équivalent

```text
python tools/rvvlab.py run explore-91-pilot --wait
python tools/rvvlab.py run explore-91-8h --wait
```

Deux raccourcis facultatifs : `RUN_TEST_91_PILOT.bat` et `RUN_TEST_91_8H.bat`.
