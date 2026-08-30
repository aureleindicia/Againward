# Relations d'actions et double comptage

Codex déclare la relation entre actions : `INDEPENDENT`, `OVERLAPPING`,
`MUTUALLY_EXCLUSIVE`, `DEPENDENT`, `SEQUENTIAL`, `ALTERNATIVE` ou `UNKNOWN`.
Python vérifie ensuite l'arithmétique; il ne déduit jamais la relation physique.

- Les options `MUTUALLY_EXCLUSIVE` et `ALTERNATIVE` ne sont jamais sommées.
- Un `OVERLAPPING` exige un effet combiné explicite ; sans cela le portefeuille
  est refusé plutôt que de sommer deux économies possibles.
- Les relations `DEPENDENT`, `SEQUENTIAL` ou `UNKNOWN` nécessitent un modèle
  combiné ou une séquence explicite avant agrégation.
- Seules les actions sans relation déclarée ou `INDEPENDENT` peuvent être
  additionnées directement.

Chaque effet réclame sa baseline : comportement observé, période saine,
baseline production/météo normalisée ou scénario. Des économies issues de
baselines incompatibles ne doivent pas être agrégées sans modèle explicite.
