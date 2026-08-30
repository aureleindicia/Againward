# Sémantique des décisions économiques

La décision est écrite par Codex et contrôlée comme contrat, pas choisie par
Python. La confiance technique et l'importance économique sont séparées.

| Décision | Sens |
|---|---|
| ACT_NOW | Action suffisamment étayée, faisable et favorable, sous validation humaine. |
| INVESTIGATE_FIRST | La preuve supplémentaire réaliste peut changer une décision matérielle. |
| MONITOR | Intervention non justifiée maintenant mais tendance utile à suivre. |
| DEFER | Action potentielle, mauvais moment opérationnel. |
| DO_NOTHING | Comportement légitime ou aucune action proportionnée. |
| NO_ECONOMIC_CASE | Finding technique réel mais bénéfice net insuffisant. |
| OPERATIONALLY_NOT_JUSTIFIED | Gain théorique bloqué par une contrainte opérationnelle explicite. |
| INSUFFICIENT_FOR_ECONOMIC_DECISION | Blocage réellement matériel, sans décision responsable disponible. |

Une décision de non-action ne cache pas une action sélectionnée. Une non-
justification opérationnelle cite la contrainte qui bloque l'action. Une action
de preuve pour `INVESTIGATE_FIRST` précise ce qu'elle départage et quelle
décision peut changer.
