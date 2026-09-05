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

## B.3 : vérité technique et contraintes factuelles

`technical_finding_refs` est résolu contre
`investigation/structured_findings.json`. Goal B peut référencer le statut et
la confiance issus de Goal A, mais ne peut ni les renforcer ni les réécrire; la
version résolue est celle qui est persistée.

Une contrainte `EXPLICIT` ou `INFERRED` cite `source_refs` (un ou plusieurs
artefacts/datasets canoniques). Python vérifie qu'ils existent. Codex reste le
seul responsable de l'interprétation de la contrainte et de la décision : le
résolveur ne choisit aucune action ni verdict.

## B.4 : no-finding réel et réponses post-Goal A

Un résultat `DO_NOTHING` sans finding est accepté seulement lorsque
`investigation/structured_findings.json` contient réellement `findings: []` et
un `no_finding` canonique complet Goal A. Dans ce cas précis, il doit aussi
rester sans action sélectionnée ou considérée, sans calcul ni référence
technique. Un tableau vide seul ne contourne donc jamais le contrat.

Après une demande économique, `record_goal_b_evidence()` enregistre une réponse
client ou documentaire native Goal B. Le handoff de reprise expose ces preuves
à Codex avec les inputs, contraintes et demandes déjà persistés. Python valide
les liens et les valeurs structurées; Codex décide toujours si la réponse
modifie l'action, l'hypothèse, la contrainte ou la décision.
