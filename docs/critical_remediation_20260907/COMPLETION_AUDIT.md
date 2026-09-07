# Audit de complétion

## 1. Le bug de dépendance aux labels est-il réellement éliminé ?

**Oui dans le chemin nominal.** A/B et recette_1/recette_2 donnent le même RMSE
(1,1654e-12 kW) et les mêmes prédictions. Bijections, permutations, Unicode, plusieurs modalités,
catégories nouvelles/manquantes et vocabulaire passé sont testés. Les deux anciens prédicteurs
explicitement nommés B restent pour compatibilité des anciens appels, documentés et signalés ;
ils ne sont plus sélectionnés par le détecteur nominal. Ce n'est pas une exception spéciale B.

## 2. Une rupture majeure de régime est-elle détectable avec compteur seul ?

**Oui sur le cas exact et les contre-exemples gelés.** Le 10→20 plat produit un candidat à la
frontière du 10 février, observé jusqu'au 1er avril. Les variantes 10→12, baisse, rampe et palier
avec retour sont distinguées. Cela n'identifie ni actif, ni cause, ni économie récupérable.
Une rupture dans la référence initiale ou trop proche de la fin peut encore être manquée.

## 3. Les faux candidats ont-ils diminué sans destruction du recall ?

**Oui sur les mêmes cas gelés, pas démontré universellement.** Benchmark indépendant historique :
4 TP / 8 FP / 5 FN → 4 TP / 4 FP / 5 FN ; F1 0,3810 → 0,4706. Démonstrations multi-scénarios :
81 TP / 0 FP / 9 FN → 87 TP / 0 FP / 3 FN. Aucun scoreur ni truth historique n'a été changé.
Les cas production/météo à support insuffisant doivent être lus comme abstentions, pas vrais
négatifs. La couverture est désormais visible.

## 4. Le workflow complet filtre-t-il suffisamment le bruit ?

**Non tranchable avec les preuves actuelles.** Un nouveau harnais distingue candidats, rejets,
constats finaux, abstentions et quantification. Une exécution non aveugle de cinq dossiers donne
2 candidats, 2 constats agrégés corrects, 0 faux constat, 1 abstention nécessaire et 2 cas sans
constat ; 7 hypothèses/interprétations rejetées. Elle ne démontre pas le filtrage des quatre FP
historiques restants ni la capacité autonome d'une session indépendante. Les tests de contrats
et d'intégrité ne sont jamais comptés comme une performance agentique. Les gates de livraison
restent bloqués sans instruction complète et approbation humaine réelle.

## 5. Les quantifications sont-elles mieux calibrées ou mieux abstentionnées ?

**Mieux définies et mieux abstentionnées ; pas calibrées terrain.** L'aire positive est distinguée
du bilan signé. Le contrôle de couverture/support/chronologie et la sensibilité entre références
empêchent certains chiffres injustifiés. Les deux observations chiffrées de l'exécution non aveugle
restent dans la tolérance de 25 % gelée avant score. Cette tolérance numérique n'établit pas la
validité du contrefactuel. Aucun chiffre n'est présenté comme économie récupérable.

## 6. Quelles faiblesses critiques subsistent ?

Intermittences/cyclage manqués ou mal caractérisés, références initiales non garanties saines,
colinéarité/extrapolation, données contextuelles insuffisantes, vérité sémantique des preuves
non vérifiée automatiquement, filtrage agentique indépendant insuffisamment mesuré. Détails,
conséquences et frontières dans [REMAINING_FAILURES.md](REMAINING_FAILURES.md).

## 7. Existe-t-il encore un problème technique assez grave pour déconseiller un premier pilote supervisé ?

**Pas de blocage universel démontré pour un pilote supervisé et qualifié ; oui pour une promesse
autonome large.** Un dossier avec historique exploitable, contrôle de couverture, vérification
humaine des références et conclusions limitées à la preuve peut maintenant servir de pilote.
Un dossier sans référence comparable ou dont toute la période utile est hors support doit être
refusé ou limité à l'observation descriptive. Les corrections ne justifient pas une promesse de
trouver des économies chez chaque client, ni de diagnostiquer une panne.

La décision de lancer un pilote doit dépendre de ces données réelles ; le score synthétique ne
suffit pas à l'autoriser intellectuellement. La validation indépendante des constats finaux et
la mesure économique terrain restent ouvertes, explicitement hors des résultats démontrés ici.

Validation finale sur le moteur commité `4df0359` : **452 tests passent en 87,84 s**,
contre 410 avant modification. Les contrôles HOLDOUT restent actifs.
Voir [VALIDATION_LOG.txt](VALIDATION_LOG.txt).
