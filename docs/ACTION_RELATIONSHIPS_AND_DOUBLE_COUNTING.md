# Relations d'actions et double comptage

Codex déclare la relation entre actions : `INDEPENDENT`, `OVERLAPPING`,
`MUTUALLY_EXCLUSIVE`, `DEPENDENT`, `SEQUENTIAL`, `ALTERNATIVE` ou `UNKNOWN`.
Python vérifie ensuite l'arithmétique; il ne déduit jamais la relation physique.

- Les options `MUTUALLY_EXCLUSIVE` et `ALTERNATIVE` ne sont jamais sommées.
- Un `OVERLAPPING` exige un effet combiné explicite ; sans cela le portefeuille
  est refusé plutôt que de sommer deux économies possibles.
- Les relations `DEPENDENT`, `SEQUENTIAL` ou `UNKNOWN` nécessitent un modèle
  combiné ou une séquence explicite avant agrégation.
- Une paire sans relation déclarée vaut `UNKNOWN`, pas `INDEPENDENT` : le
  portefeuille échoue en mode fail-closed. Seule une relation `INDEPENDENT`
  explicitement déclarée permet l'addition directe.

## B.1 — baselines et effets combinés typés

Deux calculs portant des baselines différentes ne sont jamais agrégés
automatiquement. Codex peut déclarer une `baseline_resolution` traçable
(`COMPATIBLE_DECLARED` ou `RECONCILED`), mais Python ne l'infère pas.

Un `combined_effect` n'est jamais un nombre nu. Il est soit un effet `ENERGY`
avec unité/période/baseline/provenance et tableau économique recalculé, soit un
effet `ECONOMIC` avec devise, `EUR/year`, période annualisée, baseline,
scénarios et provenance explicites. Les unités, devises, périodes ou baselines
incompatibles sont refusées.

Chaque effet réclame sa baseline : comportement observé, période saine,
baseline production/météo normalisée ou scénario. Des économies issues de
baselines incompatibles ne doivent pas être agrégées sans modèle explicite.
