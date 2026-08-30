# Goal C.2.1 — Operation-context chart integrity fix

Le renderer ne transforme plus l'absence de `production`/activité en état
inactif. `ENERGY_WITH_OPERATION_STATUS` exige désormais une provenance Goal A
explicite (`field_lineage.production`) et une couverture de production d'au
moins 80 %. Sans cette preuve, le type est refusé avec une erreur claire; le
client peut recevoir un `ENERGY_SERIES` sans contexte opérationnel.

Une valeur de production manquante reste `UNKNOWN` et est rendue par une bande
distincte; elle n'est jamais convertie en bande inactive. Les tests couvrent la
source valide, l'absence de source, les valeurs manquantes et le rendu énergie
seule. Contrôle visuel : le PDF valide affiche des bandes fondées sur la
production; le PDF sans source affiche uniquement la courbe énergétique.
