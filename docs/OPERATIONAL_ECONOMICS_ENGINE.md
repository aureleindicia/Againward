# Moteur opérationnel-économique

Goal B ajoute une couche de décision interne après les findings techniques de Goal A.
Elle n'est ni un calculateur de promesses d'économie ni un moteur de recommandations.

```text
finding technique Codex
→ action candidate Codex
→ contraintes / hypothèses explicites
→ calculs Python de scénarios
→ relation entre actions déclarée par Codex
→ décision et priorité Codex
→ plan de validation
```

Le module `operational_economics.py` valide les contrats, calcule les tableaux
LOW/BASE/HIGH, les bénéfices annuels nets, le payback simple seulement lorsqu'il
est significatif, et l'arithmétique d'un portefeuille explicitement déclaré.
Il ne sélectionne aucune action ni aucune décision.

Les décisions valides sont : `ACT_NOW`, `INVESTIGATE_FIRST`, `MONITOR`,
`DEFER`, `DO_NOTHING`, `NO_ECONOMIC_CASE`, `OPERATIONALLY_NOT_JUSTIFIED` et
`INSUFFICIENT_FOR_ECONOMIC_DECISION`.

`ACT_NOW` signifie passer à une validation professionnelle normale, jamais une
commande automatique. `INVESTIGATE_FIRST` exige une preuve ciblée, son coût ou
effort, la décision susceptible de changer et la raison économique de l'obtenir.

Le résultat est advisory. Il ne garantit ni économie, ni payback, ni cause
physique; les économies ne sont considérées réalisées qu'après validation.
