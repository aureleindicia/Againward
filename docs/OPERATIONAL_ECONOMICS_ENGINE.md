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

## Correctif B.1 : handoff et vérité quantitative

`economic_handoff()` peut être appelé **avant** la création de tout paquet
économique. Il transmet alors les findings Goal A, leur statut et leurs limites,
le contexte opérationnel déjà disponible, les documents tarif/coût/maintenance
repérés et les ambiguïtés matérielles. Il n'en déduit ni action, ni priorité, ni
décision. L'ordre E2E est donc : preuves Goal A → handoff pré-raisonnement →
contrat de raisonnement Codex → calcul Python → état Goal B persistant.

Les tableaux LOW/BASE/HIGH persistés sont refusés s'ils ne peuvent pas être
reproduits par `calculate_economic_scenarios`. Chaque valeur matérielle cite
des `EconomicInput`, une hypothèse de scénario explicitement persistée, ou la
preuve de l'effet énergie. Un nombre de bénéfice, de coût ou de payback soumis
par l'agent ne peut donc pas devenir une vérité quantitative sans recalcul.

## B.2 : artefacts de handoff séparés

Le handoff initial est écrit dans
`investigation/economic_handoff_pre_reasoning.json`. Après persistance d'un
packet, le contexte de reprise est écrit séparément dans
`investigation/economic_handoff_resume.json`. Le premier n'est donc jamais
écrasé par le second, ce qui préserve l'audit de l'information disponible avant
le raisonnement économique.
