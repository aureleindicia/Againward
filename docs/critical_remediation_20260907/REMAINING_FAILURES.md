# Faiblesses restantes

## Techniques encore présentes

1. **Recall incomplet sur effets intermittents.** Quatre événements `intermittent_unknown`
   restent sans candidat. Le seuil de pic minimum et les familles de durée ne couvrent pas tous
   les effets modérés. Un cyclage agrégé n'est toujours pas identifié comme tel. Ce n'est pas
   résolu en renommant la vérité. Voir les sorties historiques détaillées du JSON comparatif.
2. **Quatre faux candidats historiques subsistent.** Maintenance légitime (1), vue supplémentaire
   sur changements superposés (1), vues nuit/week-end d'un cycling (2). Le compteur seul ne
   tranche pas la nécessité d'une consommation. Aucun de ces candidats ne devient automatiquement
   un constat final. La consolidation n'est pas une garantie universelle de non-double-comptage.
3. **Régimes non supportés.** Recette nouvelle, prédicteur constant déplacé, trop peu de données :
   abstention plutôt qu'extrapolation arbitraire. La couverture peut devenir faible. Le cas gelé
   production/météo avec production nuisance constante puis mobile illustre une perte de couverture,
   pas une normalisation réussie. L'analyste peut tester un modèle mieux justifié ; le détecteur
   n'en invente pas automatiquement un.
4. **Référence initiale potentiellement contaminée.** Les 30–45 premiers jours sont une hypothèse
   de référence, pas une période certifiée saine. Une dérive déjà installée, une rupture très
   précoce, une queue de moins de 14 jours, des changements multiples rapprochés ou une forte
   saisonnalité non observée peuvent échapper au dispositif. Pas de promesse de détection universelle.
5. **Identifiabilité multivariée.** Le garde-fou de prédicteur constant ne résout pas la colinéarité
   entre plusieurs facteurs variables, le produit toujours associé à un shift, les extrapolations
   non linéaires ni la représentativité saisonnière. Les minima de lignes ne remplacent pas des
   cycles indépendants. Vérifier les alternatives par segmentation et références comparables.
6. **Confiance sémantique des constats.** `validate_finding_provenance` atteste des références,
   pas leur sens. Le probe de phrase causale non fondée reste accepté par ce validateur isolé.
   Cela ne démontre pas un contournement de tous les gates, mais interdit de présenter un gate
   structurel comme une preuve de vérité. Revue humaine et examen des contre-explications requis.
7. **Quantification encore dépendante du jugement.** Le nouvel outil peut refuser une estimation
   injustifiée déclarativement ; il ne sait pas si la justification fournie par l'analyste est
   vraie. Les anciens calculs d'aire positive restent disponibles et demandent une interprétation
   correcte. La dispersion de référence n'est pas un intervalle de confiance calibré terrain.

## Structurellement non résoluble avec le compteur seul

Attribution certaine à un actif, mécanisme mécanique, nécessité du procédé, économie récupérable
et causalité d'une correction ne découlent pas d'une marche de puissance. Un contexte journalier
ne résout pas une ambiguïté quart-horaire. Des machines corrélées et un changement simultané de
production/maintenance peuvent rester non identifiables. Le contraste 944,61 / 1 731,81 kWh ne
peut être arbitré sans référence mieux défendue ; ne pas en choisir un pour rendre le rapport net.

## Ce qui exige maintenant une preuve indépendante ou terrain

- Fréquence de constats utiles chez des PME non sélectionnées et valeur économique récupérable.
- Taux de faux constats finaux, stabilité inter-sessions, capacité à trouver une piste absente
  des candidats et à rejeter une maintenance légitime grâce à une information client.
- Temps réel d'obtention/nettoyage des données, nombre d'échanges et coût d'accompagnement.
- Validation du contrefactuel par une intervention documentée et mesures avant/après comparables.

L'exécution non aveugle de cinq dossiers mesure le raccordement des étapes ; elle n'est pas une
estimation de performance commerciale ou agentique. Coût modèle et temps humain : non mesurés.
Les sorties restent non livrables tant qu'une revue humaine réelle n'a pas approuvé un dossier
réel correctement instruit. Aucune approbation n'a été simulée pour embellir le résultat.
