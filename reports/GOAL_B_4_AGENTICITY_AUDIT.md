# Goal B.4 — audit d'agenticité

Goal B.4 ajoute des contrats de persistance et de provenance. Il ne choisit ni
l'investigation ni une recommandation.

1. **Codex décide-t-il toujours quoi investiguer ?** Oui : il formule les
   demandes économiques et opérationnelles, puis juge leur effet sur la suite.
2. **Codex génère-t-il et hiérarchise-t-il les hypothèses/actions ?** Oui : les
   actions, relations, contraintes matérielles et décisions restent des objets
   fournis par Codex et validés structurellement seulement.
3. **Codex choisit-il les informations à demander ?** Oui : Python valide le
   vocabulaire et le budget, sans créer de question.
4. **Codex décide-t-il si l'évidence suffit ?** Oui : le code accepte et
   conserve une réponse; il ne déduit pas `ACT_NOW`, `INVESTIGATE_FIRST` ou
   une cause.
5. **Python reste-t-il quantitatif ?** Oui : il résout les références,
   vérifie valeur/unité/devise/période, conserve l'historique et recalcule les
   chiffres. Il ne comprend pas librement le texte d'un devis ou d'une réponse.
6. **Si Codex était retiré, le code pourrait-il produire sensiblement la même
   investigation et le même diagnostic ?** **NON.** Il manquerait les
   hypothèses, la demande, l'action, la contrainte interprétée et la décision.

Conclusion : les nouveaux contrôles automatisent la traçabilité et les
opérations de validation nécessaires au raisonnement; ils ne l'automatisent
pas lui-même.
