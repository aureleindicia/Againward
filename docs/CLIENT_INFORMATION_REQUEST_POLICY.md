# Politique de demandes d’information

La valeur par défaut est **zéro question client**. Le système doit d’abord utiliser les fichiers déjà reçus, l’horodatage, les unités visibles, les séries comparables, les totaux, les notes et les documents disponibles.

Une demande est justifiée seulement si au moins deux réponses plausibles changent une décision matérielle (preuve, attribution, économie, priorité, action ou risque). `client_requests` valide ce contrefactuel, déduplique et sélectionne globalement. Un cycle contient une à trois demandes, cible une; deux cycles maximum, le second lié à une réponse créant une branche matérielle.

## Types

- `INFER_AUTOMATICALLY` : aucune demande ; l’inférence est traçable.
- `MICRO_QUESTION` : fait simple que le responsable connaît.
- `REQUEST_EXISTING_DOCUMENT` : facture, planning ou facture de maintenance déjà disponible.
- `FIELD_OBSERVATION` / `FIELD_VERIFICATION` : observation ou test terrain précis et sûr.
- `REQUEST_DATA_EXPORT` : export ciblé seulement si une source légère ne suffit pas.
- `TEMPORARY_INSTRUMENTATION` : dernier recours justifié.

Les questions client doivent être courtes et liées à une période observée. Exemple : « La préparation commençait-elle plus tôt autour du 7 avril ? » plutôt que « Avez-vous changé vos horaires ? ». Ne pas demander par défaut une pression, une vibration ou une trace BMS à un dirigeant.

## Contrat machine-readable

`questions.json` est canonique; `question_batch.json` et `economic_requests` sont dépréciés. Chaque demande conserve liens, réponses plausibles, effets décisionnels, effort, disponibilité, fiabilité, coût, source et importance.

Un BLOCKING passe en `WAITING_FOR_REQUIRED_INFORMATION` et bloque promotion, rapport/livraison. Après réponse, `RESUMING` impose recalcul/review. Une absence n'est jamais confirmation. Après budget : unknown/non identifiable/insuffisant. Sources typées; déclaration/document ne deviennent pas automatiquement ancre terrain.
