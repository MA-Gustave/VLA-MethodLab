# EPCC Test 94 — supprimer le faux « état ambigu » (14 octobre 2026)

## Pourquoi Studio disait « réponse serveur ambiguë »

La tentative `test94-20261013T233735Z-728f3a` a transféré les sources sur EPCC,
a trouvé LLVM16, puis a échoué à la compilation des intrinsics RVV. La
soumission Slurm n'a pas été effectuée (`job_id: null`, zéro mesure). L'ancien
Centre des tests ne consultait que `status94.json`, produit par le benchmark
**après** la compilation. Quand ce fichier manquait, il affichait « ambigu ».
En parallèle, l'ancien bandeau utilisait un statut local `build` qui était
représenté comme « Waiting for Slurm submission », même après échec.

## Ce que change ce correctif

- Dans **Centre des tests → Vérifier le serveur**, Studio examine maintenant,
  pour un Test94 EPCC sans statut final, le **journal de cross-compilation**
  `studio94-build.log`, les processus de compilation réels et la file Slurm.
- Des erreurs de compilation observées après arrêt du compilateur sont
  présentées comme **ÉCHEC — compilation avant Slurm** avec une courte cause
  technique (lecture seule, pas d'exécution distante supplémentaire).
- Un processus de compilation réellement actif devient **COMPILATION EPCC**.
- **EN ATTENTE Slurm** exige un job correspondant à `squeue` ; un nom de phase
  `build/queued` ou un `job_id: null` n'est PAS une preuve de job soumis.
- Si rien ne permet de conclure, l'écran indique concrètement **aucun job
  actif confirmé / état de la compilation non prouvé**, plutôt que le texte
  générique « réponse ambiguë ».
- Le petit statut en haut de la fenêtre EPCC et le tableau de 15 tests sont
  alignés après une vérification du serveur. Une tentative échouée ne reste
  plus indéfiniment en « Building ».
- **Lancer le test sélectionné** continue de passer par une vérification
  distante et une confirmation. Aucune action n'est automatique.

**Installation :** fermer Cloud-V et EPCC Studio (pas les jobs distants),
extraire `RVV-VLA-Lab_EPCC94_STATUS_CLAIR_DROP_ROOT.zip` dans
`C:\mycode\Simdjson\RVV-VLA-Lab\` en écrasant les fichiers, relancer
`LANCER_STUDIO_EPCC.pyw`, connecter SSH puis cliquer **Vérifier le serveur**.
Consulter la colonne Preuve et les détails du Test 94.

**Important :** si le log de la tentative reste absent/inaccessible, Studio ne
peut pas démontrer une compilation échouée : il affichera un statut inconnu et
conservateur. Il faut alors consulter `studio94-build.log` dans le Test Runner.
Il ne s'agit pas d'un correctif du compilateur lui-même : le mécanisme de
compatibilité Clang16 précédemment consolidé reste inchangé. Une nouvelle
compilation EPCC réussie et la soumission Slurm doivent toujours être vérifiées
sur le serveur réel.

Les tests locaux couvrent l'ancien échec Clang16, un build réellement actif,
un job Slurm PENDING, une absence de job, la séparation des deux fenêtres,
et l'interface Tkinter. Aucun hôte réel n'a été contacté pour ce correctif.
