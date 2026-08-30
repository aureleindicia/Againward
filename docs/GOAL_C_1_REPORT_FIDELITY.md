# Goal C.1 — Fidélité, décisions multiples et présentation

Goal C.1 maintient la séparation architecturale : Codex choisit les sujets,
les explications et les décisions déjà persistées par Goal B ; Python résout
les références, contrôle les chiffres et rend le PDF. Python ne choisit pas
une action, ne comprend pas librement les phrases françaises et ne produit pas
de diagnostic.

## Plusieurs décisions

`persist_economic_packet()` accepte toujours le champ historique `decision`.
Un packet peut désormais utiliser `decisions`, une liste de records Goal B
validés. Chaque action considérée appartient à un seul record client; les
records conservent les findings, actions, calculs, contraintes et plans de
validation. Cette extension est rétrocompatible et ne modifie aucune
sémantique de décision existante.

Goal C affiche une carte par action sélectionnée pour les décisions positives,
et par action considérée pour `NO_ECONOMIC_CASE` ou
`OPERATIONALLY_NOT_JUSTIFIED`. Une carte négative conserve donc explicitement
`decision_ref`, `considered_action_ref`, `finding_refs`, les calculs et les
contraintes qui expliquent l'absence de recommandation.

## Claims narratifs

Le texte de Codex est placé dans des claims structurés. Une carte porte quatre
claims : `OBSERVATION`, `WHY_THIS_MATTERS`, une recommandation dont le type est
contraint par la décision Goal B, et `UNCERTAINTY`. Par exemple une décision
`ACT_NOW` exige `ACTION_RECOMMENDED`; elle ne peut pas devenir
structurellement un claim `NO_ACTION_OPERATIONAL`.

Python ne fait pas d'analyse sémantique du texte libre. Il garantit plutôt que
le claim est attaché à la bonne décision, action, finding, contrainte, calcul
ou preuve. Les no-action items et « ce que nous avons vérifié » obéissent au
même principe : un texte sans référence réelle est rejeté.

## Rendu et confidentialité

`render_client_report_pdf(..., case_directory=...)` revalide le modèle exact
juste avant le rendu. Les métadonnées, textes, contraintes, alternatives,
protocoles de validation, graphiques et sources visibles sont soumis à la
politique anti-chemins et anti-identifiants internes.

La mise en page est dynamique : les sections et options d'alternatives ne sont
pas forcées à une page, les blocs ne sont pas laissés orphelins et aucune page
« À retenir » redondante n'est ajoutée. Les rapports simples peuvent être plus
courts. Les alternatives rendent, quand les données existent, bénéfice annuel,
coût, retour, arrêt, charge opérationnelle, incertitude et préférence déjà
déclarée par Goal B.

Les graphiques sont toujours issus de datasets Goal A réels. Le bloc PDF rend
leur titre, la question expliquée, les axes, la légende et le contexte
d'activité; ce contexte ne crée pas un nouveau finding.
