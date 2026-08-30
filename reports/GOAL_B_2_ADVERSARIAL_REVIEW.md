# Goal B.2 — revue adversariale

## Attaques vérifiées

1. **Tarif/capex fictif avec référence réelle.** Rejeté : chaque scénario doit
   pointer vers une source unique dont la valeur, l'unité, la devise et la
   période correspondent exactement.
2. **Finding Goal A inventé.** Rejeté : les identifiants sont résolus contre
   `structured_findings.json` du cas, pas seulement comparés à l'intérieur du
   packet.
3. **Effet économique combiné arbitraire.** Rejeté si sa source est absente,
   si son montant ne correspond pas à la source, ou si unité/devise/période ne
   sont pas `EUR/year`, `EUR`, `annual`.
4. **Double comptage par omission.** Rejeté : une relation manquante vaut
   `UNKNOWN`, jamais `INDEPENDENT`; des baselines distinctes exigent une
   réconciliation explicitement déclarée par Codex.
5. **Handoff pré-raisonnement écrasé.** Empêché : les artefacts pré-raisonnement
   et reprise ont des noms distincts et le test E2E vérifie leur coexistence.
6. **Décision automatique cachée dans Python.** Absente : les validateurs
   acceptent ou refusent un contrat, sans sélectionner ni classer d'action.

## Limites restantes assumées

- Python ne peut pas établir la compatibilité physique de deux baselines :
  Codex doit la déclarer et la justifier; Python refuse l'absence de résolution.
- Une source client peut être authentique mais factuellement erronée. Goal B.2
  garantit la traçabilité/reproductibilité, non la vérité externe du document.
- Les scénarios économiques restent des hypothèses lorsqu'ils sont marqués
  comme tels; le système ne les transforme pas en fait client.

## Conclusion

Les protections B.2 sont génériques et ne contiennent ni IDs, ni valeurs, ni
logique de décision propre aux fixtures B-A→B-O. Aucun changement n'a été fait
aux chemins V2.1 ou Goal A pendant cette revue.
