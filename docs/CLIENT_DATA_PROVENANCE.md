# Provenance des données client

Chaque fichier reçu devient un artefact `ART-…` stable fondé sur son hash SHA-256. L’inventaire `evidence/intake_inventory.json` enregistre son nom d’origine, chemin relatif dans le drop, type, taille, hash, date d’ingestion, rôle probable, preuve de classement, statut de parsing, utilisabilité et relations avec les jeux extraits.

Chaque tableau devient un `DS-…` dans `evidence/dataset_provenance.json`. Pour chaque jeu, le système conserve :

- fichier source, feuille et ligne d’en-tête ;
- en-têtes et correspondances de colonnes ;
- lineage de timestamp, mesure et production lorsque présents ;
- unité déclarée ou inférée et sa justification ;
- transformations, anomalies et limitations ;
- fichier normalisé associé, s’il existe.

La chaîne recherchée pour un chiffre important est :

`finding Codex → calcul Python → variable/table normalisée → dataset DS → artefact ART → original raw`.

La granularité est volontairement table/colonne/ligne source plutôt que cellule par cellule : elle reste vérifiable sans créer un volume disproportionné.

## Statuts de transformation

- `AUTO_FIX_SAFE` : correction déterministe réversible et documentée.
- `FLAG_ONLY` : valeur ou condition conservée, sans correction supposée.
- `MATERIAL_AMBIGUITY` : interprétations plausibles ayant un effet potentiel sur une décision.
- `UNUSABLE` : aucune transformation défendable ne rend l’élément exploitable.

Le résumé `derived/data_quality_summary.json` n’utilise pas de note globale : une donnée imparfaite peut rester décisive pour une observation spécifique.
