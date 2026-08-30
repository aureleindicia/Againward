# Politique de demandes d’information

La valeur par défaut est **zéro question client**. Le système doit d’abord utiliser les fichiers déjà reçus, l’horodatage, les unités visibles, les séries comparables, les totaux, les notes et les documents disponibles.

Une demande est justifiée seulement si elle distingue des hypothèses plausibles et peut changer une décision matérielle. Un batch normal contient une à trois demandes. Un second batch requiert une justification explicite dans l’état du cas.

## Types

- `INFER_AUTOMATICALLY` : aucune demande ; l’inférence est traçable.
- `ASK_CLIENT` : fait simple que le responsable connaît.
- `REQUEST_EXISTING_DOCUMENT` : facture, planning ou facture de maintenance déjà disponible.
- `REQUEST_TECHNICAL_EVIDENCE` : élément à demander à un technicien compétent pendant une visite.
- `OPTIONAL_FUTURE_INSTRUMENTATION` : seulement après avoir démontré que le gain décisionnel le justifie.

Les questions client doivent être courtes et liées à une période observée. Exemple : « La préparation commençait-elle plus tôt autour du 7 avril ? » plutôt que « Avez-vous changé vos horaires ? ». Ne pas demander par défaut une pression, une vibration ou une trace BMS à un dirigeant.

## Contrat machine-readable

`investigation/question_batch.json` conserve pour chaque demande : texte client, type, rôle cible, raison interne, hypothèses départagées, décision susceptible de changer, effort attendu, importance `BLOCKING/NON_BLOCKING/OPTIONAL` et possibilité de continuer sans réponse.

Une absence de réponse ne stoppe pas l’analyse : seules les conclusions qui en dépendent sont dégradées. Les réponses sont ajoutées une seule fois dans `case_state.json`; elles ne sont jamais réécrites silencieusement.
