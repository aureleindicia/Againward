# Politique des graphiques client

Chaque graphique doit être choisi par Codex avec une question décisionnelle,
une source Goal A exploitable et une légende client. Goal C accepte actuellement
une série énergétique explicitement référencée et la génère depuis le dataset
normalisé; il ne crée aucun graphique décoratif par défaut.

Le PDF contient peu de graphiques. Les IDs et chemins internes restent dans le
modèle, pas dans le document destiné au client.

## Intégrité du contexte opérationnel — Goal C.2.1

Une bande activité/inactivité exige une source opérationnelle Goal A explicite
et une couverture suffisante. Une colonne normalisée vide ou une valeur manquante
ne signifie jamais « inactive » : l'absence de source bloque le graphique
opérationnel, et un statut manquant reste visuellement inconnu.
