# Audit de conformité

Date de vérification : 27 août 2026.

L'ancien audit de cette page déclarait à tort presque toutes les exigences « prouvées » à partir
de la seule démo et citait des métriques devenues obsolètes. Il est remplacé par l'audit critique
et chiffré du méga-goal :

- [`MEGA_GOAL_AUDIT.md`](MEGA_GOAL_AUDIT.md)
- `reports/validation_scenarios.json` pour la non-régression proche de la démo ;
- `reports/validation_blind.json` pour les 14 cas indépendants ;
- `reports/blind_codex_comparison.json` pour Python seul contre trois sessions Codex ;
- `reports/performance.json` pour 10k, 100k et 500k lignes.

La situation actuelle est volontairement formulée sans raccourci : 112 tests passent, la fiabilité
quantitative interne est solide et la valeur d'investigation de Codex est mesurée sur un petit
sous-ensemble synthétique. En revanche, le détecteur Python n'atteint que F1 0,381 sur la batterie
aveugle globale et aucun pilote client réel ni test terrain terminé ne justifie une maturité
commerciale élevée.

Le positionnement retenu est désormais : **service local d'analyse et d'investigation de
performance énergétique sur données**, avec Python comme vérité quantitative, Codex comme analyste
contradictoire et revue humaine obligatoire avant livraison. Le service possède une valeur
autonome et peut aussi guider les professionnels terrain. Il ne constitue pas un audit énergétique
réglementaire.
