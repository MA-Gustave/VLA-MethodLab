# Installation des deux dépôts — revue des licences requise

1. Examiner et extraire l'archive `VLA-MethodLab_licences_renforcees_REVUE.zip` dans la racine `VLA-MethodLab`.
2. Examiner et extraire `VectorPath-RVV_licences_renforcees_REVUE.zip` dans la racine `VectorPath-RVV`.

**Ces archives incluent désormais chacune un fichier `LICENSE` de périmètre mixte.** Il ne remplace pas les permissions Apache/MIT historiques et n'annule pas les licences précédemment consenties. Les textes tiers de simdjson sont préservés dans `engine/LICENSE` / `engine/LICENSE-MIT` pour MethodLab et dans `THIRD_PARTY_LICENSES/` / `LICENSE-MIT` pour VectorPath.

Le répertoire `engine/` est **bien distribué et versionné** dans MethodLab. Ce moteur embarqué est techniquement identique aux chemins communs du moteur VectorPath dans les snapshots audités ; conserver cet alignement lors des essais.

Aucun fichier ZIP ne publie quoi que ce soit sur GitHub : relire les modifications, consulter les preuves de provenance et obtenir une revue juridique avant fusion sur les branches publiques. Ne pas publier de `.env`, clés ou autres secrets.
