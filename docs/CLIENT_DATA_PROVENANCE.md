# Provenance des données client

## Privacy lineage

Chaque fichier temporaire `incoming/` reçoit un `file_id` non sémantique. Le
`privacy/privacy_manifest.json` conserve son hash SHA-256, son type, le statut PASS/SANITIZED/
BLOCKED, les catégories et transformations agrégées, puis le hash de la version `sanitized/`.
Il ne conserve ni valeur personnelle retirée, ni nom logique susceptible de la recréer.

Après validation et suppression du brut temporaire, `sanitized/` devient la source canonique. La
chaîne recherchée est :

```text
finding Codex → calcul Python → table normalisée → dataset DS → artefact ART
→ hash sanitized → file_id + hash original dans privacy_manifest
```

Le hash original permet de prouver quel objet a été reçu sans en garder une copie durable. La
review Codex de travail et le reçu de staging sont supprimés après succès ; les transformations
agrégées restent dans le manifest.

## Provenance d’intake

L’inventaire `evidence/intake_inventory.json` enregistre pour chaque artefact sanitized son type,
taille, hash, date d’ingestion, rôle probable, preuve de classement, parsing, utilisabilité et
relations avec les tables extraites. `evidence/dataset_provenance.json` conserve :

- fichier/feuille et ligne d’en-tête ;
- correspondances de colonnes ;
- lineage de timestamp, mesure et production ;
- unité déclarée ou inférée et justification ;
- transformations de qualité, anomalies et limitations ;
- fichier normalisé associé.

La granularité reste table/colonne/ligne source plutôt que cellule par cellule. Le privacy cleanup
et la normalisation qualité sont deux journaux distincts : la première ne corrige aucun signal ; la
seconde ne peut réintroduire une donnée rejetée.

## Statuts qualité

- `AUTO_FIX_SAFE` : correction déterministe réversible et documentée.
- `FLAG_ONLY` : valeur conservée et signalée.
- `MATERIAL_AMBIGUITY` : interprétations capables de changer une décision.
- `UNUSABLE` : aucune transformation défendable.

Après purge, le reçu ne contient que des catégories, logical IDs opaques, hashes et statuts. Il ne
permet pas de reconstruire les données supprimées.
