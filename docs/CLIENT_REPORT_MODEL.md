# Client Report Model

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
