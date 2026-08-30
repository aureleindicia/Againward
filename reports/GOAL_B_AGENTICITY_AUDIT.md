# Goal B — audit d'agenticité

## Conclusion

Le code déterministe ne peut pas reproduire seul le jugement opérationnel-
économique. Il manipule une décision déjà fournie par Codex et refuse seulement
les états arithmétiquement ou structurellement incohérents.

1. Politique de recommandation cachée : **non**. Aucune fonction ne choisit une
   classe de décision à partir d'un seuil, coût ou payback.
2. Python peut-il choisir `ACT_NOW` plutôt que `INVESTIGATE_FIRST` : **non**.
3. Les actions candidates sont-elles générées par lookup : **non**. Elles sont
   persistées après formulation Codex et validation de schéma.
4. Les contraintes opérationnelles sont-elles interprétées par des règles fixes :
   **non**. Codex déclare leur matérialité, leur effet et leur disposition. Python
   exige simplement qu'une contrainte dure affectant une action sélectionnée ne
   soit pas oubliée.
5. La priorité est-elle un score pondéré déguisé : **non**. `priority_reasoning`
   est un champ d'argumentation Codex; aucun score n'est calculé.
6. Python calcule-t-il seulement les opérations nécessaires : **oui** : unités,
   scénarios, bénéfice net, payback significatif, tarifs time-aligned et
   arithmétique de portefeuille déclarée.
7. Sans Codex, les mêmes recommandations seraient-elles produites : **non**.

Le test architectural permanent reste donc satisfait : Python produit la vérité
quantitative, Codex décide de son sens opérationnel et économique.
