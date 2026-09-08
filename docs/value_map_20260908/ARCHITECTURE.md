# Extension Value Map — périmètre et choix avant implémentation

Source canonique économique conservée : `investigation/economic_decision_state.json`.
La Value Map sera une projection déterministe d'une extension de cet état, pas un second
registre d'inputs, de décisions ou de demandes client. L'artefact `value_map.json` sera régénéré
et revalidé avant le reporting ; un fichier modifié ne constituera pas une source indépendante.

Réutilisation : sources Goal A et preuves natives Goal B, EconomicInput / ScenarioAssumption,
calculs LOW/BASE/HIGH, actions/contraintes, décisions, vocabulaire de relationships et contrat
`evidence_acquisition`. Les quantités nouvelles non monétaires seront des extraits structurés
référencés de preuves persistées, pas des nombres libres dans un narratif.

Les estimations et observations post-action seront des entrées immuables distinctes. Un résultat
réalisé exigera action, dates et preuves post-action. L'absence de preuve d'un effet causal
interdira de promouvoir une estimation contrefactuelle en économie réalisée.

Aucun « total value » transversal : unités, périodes, contrefactuels et dépendances hétérogènes.
Le portefeuille économique existant reste disponible uniquement pour son périmètre et ses
relations explicites. La carte de valeur ne fournira pas une autre somme concurrente.

Le PDF recevra une section revalidée « Valeur de l'investigation ». Les scénarios seront désignés
comme hypothétiques et les faits/estimations documentés comme tels. La valeur décisionnelle
n'aura pas de monétisation automatique. Les interprétations de l'agent restent sujettes à revue.

Pilot learning : export explicite désidentifié et autorisé, observations avec références,
dénominateurs connus et inconnus séparés ; aucune conclusion commerciale automatique.
