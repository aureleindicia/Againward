# Goal B.2 — audit d'agenticité

## Verdict

Goal B.2 conserve l'architecture agentique.

| Question | Réponse |
| --- | --- |
| Codex décide-t-il des actions, contraintes, relations et décision ? | Oui. |
| Python choisit-il `ACT_NOW` ou `INVESTIGATE_FIRST` ? | Non. |
| Python invente-t-il des actions candidates ou une compatibilité physique ? | Non. |
| Python calcule-t-il et valide-t-il les références, unités et nombres ? | Oui. |
| Sans Codex, le code déterministe pourrait-il reproduire sensiblement l'enquête et la décision ? | **Non.** |

`operational_economics.py` ne contient ni score pondéré de recommandation, ni
choix automatique d'action, ni règle B-A→B-O. Les fixtures alimentent les
tests; elles ne sont jamais lues par le moteur de production.

Le durcissement B.2 augmente la capacité de Python à refuser un nombre ou une
référence invérifiable. Il ne réduit pas l'espace de décision de Codex : celui-ci
peut toujours proposer une action, une hypothèse, une relation et un protocole
non prévus, sous réserve de fournir un contrat calculable et traçable.
