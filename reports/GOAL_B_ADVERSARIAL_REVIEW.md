# Goal B — revue adversariale

## Résultats des contrôles

- Surpromesse d'économie : les effets énergie portent base, baseline, scénarios
  et références; les économies réalisées restent à valider.
- Fausse précision : LOW/BASE/HIGH remplacent les chiffres uniques non justifiés.
- Mauvais tarif : sans série temporelle le calcul signale l'approximation; avec
  série horodatée, un plan tarifaire existant est appliqué déterministement.
- Double comptage : un recouvrement sans effet combiné explicite est refusé.
- Options exclusives : elles ne peuvent pas être agrégées.
- Coûts récurrents : ils diminuent le bénéfice net, et un bénéfice nul/négatif ne
  produit pas de payback.
- Coût déjà engagé : le contrat accepte uniquement des coûts incrémentaux que
  Codex/source ont distingués; il ne les invente pas.
- Downtime, production, sécurité : sont représentables comme contraintes. Une
  contrainte dure affectant une action choisie exige une évaluation explicite.
- Panne/RUL : aucun calcul de probabilité de défaillance ni valeur monétaire de
  panne n'est introduit.
- CAPEX/tarif inconnus : restent `UNKNOWN`; aucune valeur par défaut n'est créée.
- Questions : un batch est limité à trois demandes et `REQUEST_QUOTE` est une
  demande de document existant, non une enquête comptable.
- Evidence non décisive : `INVESTIGATE_FIRST` exige de montrer quelle décision
  peut changer; le code ne prétend pas savoir si l'achat de preuve est rentable.
- Non-action : les décisions `DO_NOTHING` et `NO_ECONOMIC_CASE` ont des contrats
  explicites et des fixtures.

## Limites résiduelles

Le module ne sait pas établir qu'une contrainte est réellement bloquante, qu'un
devis est complet, ni qu'un effet combiné est physiquement crédible : ce sont des
jugements Codex/professionnel. La protection contre double comptage dépend donc
de la relation déclarée, mais refuse l'addition lorsque cette relation est connue
et insuffisamment modélisée.

Cette revue ne constitue pas une preuve de valeur commerciale réelle : les
fixtures valident l'architecture et non les économies obtenues chez des PME.

## Auto-revue finale

- Goal B est-il devenu un tableur avec un LLM en façade : **non**.
- Goal B est-il devenu un moteur de recommandation déterministe : **non**.
- Distingue-t-il gain techniquement possible et action économiquement/
  opérationnellement justifiée : **oui**.
- Peut-il recommander une preuve peu coûteuse avant un CAPEX incertain : **oui**.
- Peut-il dire « ne rien faire » : **oui**.
- Peut-il empêcher le double comptage évident : **oui**.
