# ICP initial — Investigation de performance énergétique sur données

Version : 2026-08-28. Ce profil est une hypothèse de travail modifiable à partir des retours
réels ; il n’est ni un score ni une règle de classement.

## Cœur de cible

Petite ou moyenne organisation française disposant d’un site de production, laboratoire ou atelier
identifiable, avec un fonctionnement répétitif et un procédé susceptible de produire une courbe de
charge exploitable. La taille recherchée est généralement de 15 à 150 salariés pour le site ou
l’entreprise, avec exceptions seulement lorsqu’un élément public justifie le périmètre.

Les secteurs prioritaires à surveiller sont :

- blanchisserie ou laverie professionnelle ;
- boulangerie-pâtisserie avec laboratoire central et plusieurs points de vente ;
- transformation agroalimentaire à petite ou moyenne échelle ;
- fabrication de produits surgelés, glaces ou activité avec froid important ;
- usinage, fonderie, frappe, moteurs, compresseurs ou ventilation de production ;
- toute autre PME où un procédé et une répétition opérationnelle sont effectivement documentés.

L’appartenance sectorielle seule ne suffit jamais. Au minimum, une fiche utile doit contenir un
fait sur l’activité ou le procédé et un fait sur la taille, le site, la croissance ou l’organisation.

## Signaux positifs à documenter

- site de production, laboratoire, atelier ou plusieurs boutiques alimentées par une même unité ;
- production en série, horaires étendus, équipes, nuit ou fonctionnement récurrent ;
- fours, froid, presses, compresseurs, moteurs, ventilation ou procédé thermique explicitement
  publiés ;
- extension, nouvel équipement, modernisation, changement de capacité ou recrutement de production ;
- effectif compatible avec une discussion directe avec direction, maintenance ou production ;
- indice, jamais une supposition déguisée, qu’un compteur ou des données temporelles peuvent exister.

## Signaux négatifs et limites

- microstructure dont la taille publique rend une mission initiale probablement disproportionnée ;
- groupe très grand, multi-sites ou site sans autonomie démontrée ;
- activité de service sans procédé ou site identifiable ;
- informations publiques trop pauvres pour distinguer l’organisation d’un simple nom de secteur ;
- société fermée, doublon ou opposition explicite à être contactée.

Une absence d’information déclenche de préférence `UNCERTAIN`, pas un rejet. Un rejet exige un fait
public explicite, par exemple une taille très faible, une fermeture ou un périmètre manifestement
hors cible.

## Données minimales à demander seulement après un accord

Energy Analyzer n’affirme pas avoir analysé une entreprise avant réception de données. Pour une
investigation utile, rechercher ensuite une période de mesures énergie ou puissance avec timestamp,
la nature et l’unité de la mesure, le périmètre du compteur, et si possible production, horaires,
maintenance, température et tarif. Les données restent locales et ne sont jamais réutilisées entre
clients.
