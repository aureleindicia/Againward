# Goal C.2 — Fidelity review

## Contrats fermés

- La directive client est dérivée uniquement de `decision` Goal B via
  `DECISION_LABELS`. Le report model C.2 (`schema_version: 3`) ne possède plus
  de claim libre `recommendation` susceptible de devenir l'instruction
  fondamentale.
- `contextual_rationale` reste un claim Codex sourcé, mais il est rendu comme
  contexte. Il ne peut pas modifier la directive affichée.
- Toute carte ferme maintenant la chaîne locale `card → decision → action →
  finding / calculation / constraint`. Un calcul ou une contrainte valide mais
  rattaché à une autre action est refusé.
- `next_step` est reconstruit depuis la décision et les artefacts Goal B :
  validation post-action (`ACT_NOW`), vérification préalable
  (`INVESTIGATE_FIRST`), surveillance (`MONITOR`), ou réévaluation (`DEFER`).
  Les décisions négatives n'obtiennent aucun protocole post-action inventé.

## Tests adversariaux

- Texte contextuel « ne réalisez aucune intervention » sur une décision
  `ACT_NOW` : accepté uniquement comme contexte; la directive affichée reste
  `Action recommandée`.
- Référence économique de réparation vers le calcul de remplacement : rejetée.
- Référence de contrainte d'une action horaires vers une action différente :
  rejetée.
- Références locales réellement associées à l'action : acceptées.
- Les cas `ACT_NOW`, `INVESTIGATE_FIRST`, `MONITOR` et
  `OPERATIONALLY_NOT_JUSTIFIED` produisent chacun le bloc de prochaine étape
  approprié.

## Précision et limites

Les montants exacts et les fourchettes restent reconstruits depuis les calculs
Goal B. Goal C.2 ne crée ni intervalle rhétorique, ni économie vérifiée, ni
nouvelle recommandation. La validation structurelle ne tente pas d'interpréter
le français libre : elle protège la directive, les objets référencés et les
valeurs quantitatives.
