# VLA-MethodLab — Test 98 intégré à Studio refondu (Cloud-V et EPCC)

**DROP ROOT :** fermer les deux Studio, sauvegarder le dossier `studio`, décompresser le ZIP dans `C:\mycode\Simdjson\VLA-MethodLab\` et accepter la fusion. Relancer Studio, connecter la machine, ouvrir **Tests → 98 → Actualiser → Démarrer**.

## Objet

Test 98 compare le fork RVV (A2 à 4 Kio et 8 Kio) aux versions officielles simdjson v5.0.3 / v5.0.4 (`fallback`) sur **18 fichiers JSON publics** provenant de `simdjson-data` fixé au commit `4197c425e857f0ec38e89822fdd0bd9ea21f4daf`. La collecte HTTPS se fait **depuis le PC**, avec cache local et SHA-256 ; le contenu n'est pas distribué dans le ZIP du patch.

Lancement **manuel** et durée de **60 minutes de mesure** (15 dernières minutes : répétitions sur les mêmes documents, pas un holdout indépendant), plus temps de préparation / téléchargement / compilation. EPCC utilise Slurm sur `rvc02`, Cloud-V lance un processus distant détaché. **Ne pas lancer sur les deux machines simultanément si l'on cherche une comparaison sans perturbation réseau.**

## Studio

- Le Test 98 apparaît dans l'espace **Tests** pour les deux machines ; numéros 94–97 conservés.
- `Actualiser` lit la campagne distante sans lancer de job. `Démarrer` refuse une nouvelle campagne 98 tant qu'un résultat existant est présent : utiliser **Télécharger**.
- **Jaune** = en préparation / exécution ; **vert** = `completed`, `validated: true`, archive ZIP distante présente ; **rouge** = échec confirmé.
- Téléchargement du ZIP d'une campagne précise avec vérification SHA-256 ; contrôle de contenu et CRC.
- La même cadence de **60 secondes** alimente le tableau des tests et l'historique avancé.
- Les versions officielles v5 utilisent `fallback` sur RISC-V ; le fork utilise `rvv`. Le rapport comparatif le précise ; les gains ne sont pas une comparaison iso-backend.

## Changements / corrections

- Correction d'un bug d'arrêt de boucle dans `tools/test98_native.py` fourni : avant, la mesure sautait tous les documents sauf en fin de durée.
- Gestion des inventaires EPCC et Cloud-V, résultats Test98 vérifiés, anti-doublon et affichage dans la refonte.
- Maintien de `.cache` à l'écart des archives de déploiement ; aucun fichier JSON de benchmark n'est ajouté au dépôt.
- Ne remplace ni les moteurs C++ principaux ni les scripts 94–97 ni les fichiers d'identifiants SSH.

## Première exécution / limites

- **Ancien chemin de moteur :** si Studio pointe toujours vers `RVV-VLA-Lab\engine` (ancien chemin connu), le lanceur utilise le moteur `VLA-MethodLab\engine` **avec avertissement explicite dans le journal et SHA256 de la source**. Pour comparer le checkout VectorPath courant, sélectionner explicitement son dossier valide dans les paramètres du Lab. Les autres dépôts incomplets sont refusés.
- **Internet requis depuis le PC** pour télécharger les 18 JSON originaux au premier lancement ; internet/GitHub requis aussi sur la machine distante pour cloner les deux versions officielles. Erreur explicite si indisponible, aucun corpus de substitution.
- Compiler LLVM 16 / compatibilité Clang16 nécessaires sur EPCC ; test à valider sur serveur.
- Un résultat terminé n'implique pas que les performances sont dépourvues de contention CPU : exécuter seul.
- Tests locaux ne remplacent pas une exécution native sur Cloud-V/EPCC.

**Retour arrière** : fermer Studio puis restaurer la sauvegarde du dossier `studio`. Les nouveaux fichiers de Test98 peuvent être retirés si souhaité.
