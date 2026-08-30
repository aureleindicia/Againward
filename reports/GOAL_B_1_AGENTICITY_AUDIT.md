# Goal B.1 — Audit d'agenticité

1. **Qui choisit ce qui mérite une investigation ou une action ?** Codex. Le
   handoff ne contient que les preuves Goal A disponibles et aucun choix.
2. **Qui génère et classe les hypothèses, actions et relations physiques ?**
   Codex. Aucun lookup, score pondéré ou diagnostic automatique n'a été ajouté.
3. **Qui décide si les preuves économiques sont suffisantes et s'il faut une
   demande ?** Codex. Python ne fait que vérifier le type, le budget et la
   structure de la demande.
4. **Qui choisit ACT_NOW, INVESTIGATE_FIRST, DO_NOTHING ou DEFER ?** Codex.
   Python valide que la décision est cohérente avec les références sélectionnées
   et les contraintes déclarées, sans inférer une préférence.
5. **Que fait Python ?** conversions d'unités, scénarios, bénéfice net,
   payback quand significatif, reproduction exacte des calculs et refus des
   agrégations non explicitement structurées.
6. **Python décide-t-il une compatibilité physique de baseline ou une relation
   entre actions ?** Non. Il exige seulement une déclaration Codex traçable.
7. **Si Codex était retiré, le code reproduirait-il sensiblement la même
   investigation et le même diagnostic économique ?** **NON.** Il ne saurait
   ni proposer les actions ni choisir les relations, hypothèses, contraintes,
   demandes ou décisions.

Conclusion : B.1 automatise les opérations nécessaires au raisonnement, pas le
raisonnement opérationnel-économique lui-même.
