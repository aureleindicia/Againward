# Goal B.4 — revue adversariale

## Tentatives de contournement vérifiées

| Risque | Contrôle / résultat |
|---|---|
| Tableau Goal A vide utilisé comme raccourci | Refusé sans `no_finding` canonique complet. |
| No-finding transformé en action cachée | Refusé : aucune action, action considérée ou calcul n'est admis avec ce `DO_NOTHING`. |
| Faux ID de preuve Goal B | Refusé avant persistance du packet. |
| Devis inventé derrière une référence valide | Refusé si `structured_value` et l'`EconomicInput` ne correspondent pas exactement. |
| Réponse client perdue à la reprise | Testée : l'état et le handoff resume conservent les deux preuves B.4. |
| Artefact explicitement sans pertinence invoqué comme tarif/contrainte | Refusé sans justification structurée explicite. |
| Python choisit la décision | Absent : il valide les contrats et ne produit aucun verdict économique. |

## Limites assumées

- Une preuve client peut être factuellement inexacte : Goal B conserve sa
  provenance et sa confiance, mais ne peut pas authentifier la réalité d'un
  devis ou d'une déclaration sans source supplémentaire.
- Une justification `source_justification` reste un jugement Codex auditable;
  elle n'est pas une validation sémantique automatique du contenu libre.
- L'immuabilité est assurée au niveau de l'API et de l'historique d'état. La
  sécurité du stockage local reste celle du workspace client.

## Conclusion

Les nouveaux chemins ne contournent ni la provenance quantitative B.2/B.3, ni
les protections Goal A, ni l'architecture agentique. Aucun réglage par fixture
ou décision automatique n'a été ajouté.
