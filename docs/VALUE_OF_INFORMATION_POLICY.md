# Politique de valeur d'information

La question par défaut est l'absence de question. Codex demande de l'information
économique seulement si elle peut changer une décision matérielle et si son coût
ou effort est proportionné à l'enjeu.

Types contrôlés : `INFER_AUTOMATICALLY`, `ASK_CLIENT`,
`REQUEST_EXISTING_DOCUMENT`, `REQUEST_TECHNICAL_EVIDENCE`,
`OPTIONAL_FUTURE_INSTRUMENTATION` et `REQUEST_QUOTE`. Le premier est une
opération interne : il peut être journalisé avec son motif et son impact, mais
ne comporte aucune question client. Un batch normal est limité à trois demandes
externes ; tout type inconnu est rejeté.

Une demande `INVESTIGATE_FIRST` doit expliciter : ce qu'elle peut départager,
la décision qui pourrait changer, son coût/effort et pourquoi elle est justifiée.
Une facture ou un devis existant est préféré à une demande de calcul technique au
dirigeant. Si aucun résultat plausible ne modifierait la décision, ne pas demander
la donnée.
