# Goal C.2 — Adversarial review

## Chemins recherchés

1. Une phrase libre inverse une décision structurée.
2. Une carte emprunte un calcul, une contrainte ou un finding d'une autre
   action.
3. Une décision négative reçoit une consigne de validation post-action.
4. Un état binaire est représenté comme une grandeur continue.
5. Goal C augmente une économie, une confiance ou une directive Goal B.
6. Les protections Goal A, Goal B et Candidate V2.1 sont modifiées.

## Résultat

- Le premier chemin est fermé par `client_directive`, qui est dérivé au rendu
  et revalidé avant PDF; le récit n'occupe plus le slot de directive.
- Les références locales sont contrôlées dans les claims, les `claim_refs` et
  les contraintes affichées; les attaques croisées sont couvertes par tests.
- `next_step` est une projection déterministe de la classe de décision et ne
  produit rien pour les décisions négatives.
- Le graphe binaire utilise des bandes de contexte et conserve la courbe
  énergétique séparée.
- Les tests de fidélité existants continuent de refuser les valeurs économiques
  falsifiées, les décisions renforcées et les IDs/chemins internes.
- Le diff C.2 ne modifie ni le moteur Goal A, ni Goal B, ni Candidate V2.1.

Risque restant : une explication contextuelle peut signaler une réserve avec
une formulation maladroite. Elle ne peut toutefois pas modifier la directive,
ni les nombres, ni les prochaines étapes rendues. La qualité rédactionnelle
reste une responsabilité de Codex et de la revue humaine.
