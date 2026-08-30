# Client Report Model

## Version 2 — Goal C.1

Le modèle accepte plusieurs `decision_cards` provenant de plusieurs records
Goal B. Chaque carte contient `decision_ref`, `action_ref` ou
`considered_action_ref`, ses références de findings/calculs/contraintes et les
quatre claims structurés décrits dans
[`GOAL_C_1_REPORT_FIDELITY.md`](GOAL_C_1_REPORT_FIDELITY.md). Les décisions
négatives sont donc des cartes auditables, pas de simples paragraphes.

Le renderer relance `validate_client_report_model()` avec le case courant juste
avant le rendu : un JSON validé puis modifié ne peut pas produire de PDF.

`CLIENT_REPORT_MODEL.json` est indépendant du format de sortie. Il contient les
métadonnées, résumé, cartes de décision, alternatives non additives, éléments
sans action, questions restantes, graphiques, annexe et références internes.

Un narratif Codex est requis pour chaque action sélectionnée : `headline`,
`what_we_found`, `why_this_matters`, `recommendation` et `uncertainty`.
Les nombres libres y sont interdits : les valeurs visibles proviennent des
claims structurés calculés à partir de Goal B.

Une économie porte `POTENTIAL`, `EXPECTED` ou `VERIFIED`. Goal C ne produit
actuellement que `POTENTIAL`; aucun calcul seul ne devient une économie
vérifiée.
