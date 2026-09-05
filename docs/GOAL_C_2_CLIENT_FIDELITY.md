# Goal C.2 — Client-fidelity hardening

Goal C.2 ne crée aucune décision ni recommandation nouvelle. Il ferme trois
contrats de livraison client autour des états gelés Goal A et Goal B.

## Directive et explication

La directive client est un libellé déterministe de la décision Goal B. Les
claims écrits par Codex expliquent le contexte, l'incertitude et l'enjeu, mais
ne constituent plus une instruction fondamentale libre. Ainsi, un texte
contextuel peut signaler une réserve sans remplacer une décision `ACT_NOW` par
une non-action dans le PDF.

## Cohérence locale

Une carte ne peut référencer que les findings, le calcul économique et les
contraintes de l'action qu'elle représente. La validation rejette une référence
valide mais appartenant à une autre action du même dossier.

## Prochaine étape

Le renderer affiche seulement une étape adaptée à la décision : validation
post-action pour `ACT_NOW`, vérification avant investissement pour
`INVESTIGATE_FIRST`, surveillance pour `MONITOR`, et réévaluation documentée
pour `DEFER`. Les décisions négatives et le no-finding n'affichent aucun faux
protocole post-intervention.

## Graphiques

Les états binaires d'activité sont rendus par bandes de fond ouvertes/fermées,
jamais par une courbe interpolée. La courbe de consommation reste séparée et
porte ses unités dans le report model.
