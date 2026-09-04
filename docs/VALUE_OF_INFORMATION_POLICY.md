# Politique de valeur d'information

La question par défaut est l'absence de question. Codex demande de l'information
économique seulement si elle peut changer une décision matérielle et si son coût
ou effort est proportionné à l'enjeu.

Types contrôlés : `INFER_AUTOMATICALLY`, `MICRO_QUESTION`, `REQUEST_EXISTING_DOCUMENT`,
`FIELD_OBSERVATION`, `FIELD_VERIFICATION`, `REQUEST_DATA_EXPORT` et
`TEMPORARY_INSTRUMENTATION`. Le premier est une
opération interne : il peut être journalisé avec son motif et son impact, mais
ne comporte aucune question client. Un batch normal est limité à trois demandes
externes ; tout type inconnu est rejeté.

Chaque demande explicite réponses plausibles et effets distincts. `select_minimum_requests()`
réutilise `rank_micro_questions()` lorsque la partition est complète, puis classe et déduplique
globalement. La valeur ajustée par disponibilité, fiabilité, effort et coût est prioritaire; à
valeur comparable seulement, l'ordre est : inférence, micro-question, document, observation, test,
export, instrumentation. Le seuil de publication par défaut est `0.05`. C'est un garde-fou
conservateur non calibré sur des dossiers réels, à réévaluer après les premiers pilotes.

Une demande `INVESTIGATE_FIRST` doit expliciter : ce qu'elle peut départager,
la décision qui pourrait changer, son coût/effort et pourquoi elle est justifiée.
Une facture ou un devis existant est préféré à une demande de calcul technique au
dirigeant. Si aucun résultat plausible ne modifierait la décision, ne pas demander
la donnée.
