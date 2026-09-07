# Causes racines — AGAINWARD, 7 septembre 2026

Référence avant : `55eaaf30224a66cfec22aa701e05a2ebbad2f1ad`. Rapport lu :
`scratch/againward_adversarial_20260907/RAPPORT_ADVERSARIAL_AGAINWARD.md`, ses probes,
rapports reproduits et artefacts de validation. Résultats détaillés avant/après dans
[BEFORE_AFTER_RESULTS.json](BEFORE_AFTER_RESULTS.json). Le [protocole](PROTOCOL.md)
et `scratch/critical_remediation_20260907/capture.py` ont été gelés avant correction.
La suite de référence passe : 410 tests en 89,14 s. Aucun générateur, vérité ou scoreur
historique n'a été modifié.

## 1. Noms des produits : bug du modèle et du chemin nominal

**Reproduction.** Probe original `normal_AB` versus `normal_recipes`, mêmes mesures et mêmes
régimes, renommés. RMSE 8,85e-13 versus 5,9833 kW avant. Le problème n'est pas un changement
physique et ne vient pas du benchmark.

**Cause.** `_predictor_value` dans `energy_mvp/toolbox.py` code les indicatrices littérales
`product_type_b` et `production_product_b`. `energy_mvp/signals.py` les demandait pour tout
produit. Une recette inconnue devenait ainsi implicitement « pas B », comme la référence.
Les fixtures historiques A/B et leurs benchmarks partageaient cette hypothèse ; les tests
mesuraient la restitution de ces fixtures, pas l'invariance de représentation.

**Correction.** Encodage catégoriel appris uniquement sur la calibration, intercepts et
interactions de production pour plusieurs produits, vocabulaire sérialisé, ordre de première
apparition invariant au renommage bijectif. Support minimal et plafond explicites ; absence,
modalité rare ou nouvelle exclue de la prédiction et comptée. Validation sans vocabulaire futur.
Le chemin nominal demande désormais `product_type` et `production_by_product`.

**Inventaire des autres labels.** Recherche des comparaisons A/B et des noms de shifts dans les
modules énergétiques : les générateurs synthétiques ont légitimement des recettes A/B ; les deux
anciens prédicteurs explicites restent lisibles pour compatibilité des démonstrations/modèles
historiques. Leur usage est exposé dans `legacy_label_predictors` et exclu du chemin nominal.
`shift` dispose du même encodage générique lorsqu'il est demandé à la toolbox. Les seuils de
degrés-jours sont des hypothèses physiques candidates, pas des noms de catégories cachés.

**Alternatives rejetées.** Remplacer B par « deuxième label trié » sans vocabulaire persistant,
une exception recette_2, encoder les noms par un ordinal numérique, apprendre les catégories
sur toute la période : aucune n'assure la généralisation demandée.

## 2. Rupture majeure manquée : détecteur incomplet, puis erreurs de segmentation

**Reproduction exacte.** `persistent_flat_meter_only`, 90 jours à 15 minutes, 10 puis 20 kW,
aucun contexte : zéro candidat avant. Ce n'était pas seulement un seuil trop élevé.

**Causes.** Le chemin agrégé avait des pics et des groupes temporaires demandant un retour ;
la recherche de dérive/niveau dépendait des périodes inactives connues. Un niveau sans retour
et sans activité déclarée n'avait donc pas de chemin utile. L'ancienne recherche de queue
stable appliquait aussi une deuxième exclusion `reference_days` à des dates déjà postérieures
à la référence ; sa sélection pouvait privilégier une frontière tardive. Une régression de
pente sur une marche pouvait donner assez de R² pour l'étiqueter « dérive ».

**Correction.** Série journalière agrégée de résidus pondérés par durée lorsque l'inactivité
n'est pas connue ; comparaison avec une référence passée, dispersion robuste et plancher
relatif/absolu. Recherche de queue stable dès la première frontière admissible. Une pente doit
mieux expliquer la fenêtre qu'une marche unique. Le transitoire exige retour observé et histoire
stable. Calendrier hebdomadaire pour compteur seul, jours incomplets exclus, dates réellement
écoulées pour la pente, jours locaux et DST pour les durées.

**Pourquoi non testé.** La démo fournit activité/production ; trouver ses injections ne prouve
pas la détection compteur seul. Les anciens tests n'imposaient pas la distinction marche/pente.

**Alternatives rejetées.** Seuil 10→20 codé en dur, abaissement global des pics, utilisation du
futur pour nettoyer la référence, transformation de chaque anomalie en conclusion client.

## 3. Faux candidats : doublons et confusion de forme, mais aussi information manquante

**Reproduction.** 14 scénarios, seeds 700+i, mêmes CSV et IoU/type : 4 TP, 8 FP, 5 FN.
Les familles précises, avant/après, figurent dans le JSON joint.

**Causes génériques corrigées.** La même dérive commune active/inactive donnait trois vues
(dérive, nuit, week-end). Une marche donnait aussi une pente. Consolidation des facettes
seulement si fort recouvrement temporel et variation commune active/inactive ; preuves
subordonnées conservées. Un effet propre aux arrêts n'est pas éliminé arbitrairement.

**Causes restantes.** Maintenance ponctuelle légitime : une observation électrique réelle,
classée FP contre une vérité « pas anomalie utile » ; le compteur ne peut connaître sa nécessité.
`intermittent_unknown` : quatre événements modérés manqués, seuil de pic et durée/structure
inadaptés. `short_cycling_unknown` : deux vues nocturnes/week-end, sans signature de cycling
correcte. `overlapping_changes` conserve une vue supplémentaire. La couche agentique doit
consulter le contexte et explorer au-delà des candidats ; elle ne reçoit pas magiquement la
vérité privée. Son filtrage industriel suffisant reste non tranchable avec les preuves actuelles.

**Alternatives rejetées.** Réduire les seuils pour les seules injections connues, cacher les
candidats de maintenance en reconnaissant le dataset, changer la typologie de la vérité,
substituer le score temporel au score historique exact.

## 4. Baselines : fuite de validation et identification insuffisante

**Défaut supplémentaire critique.** `_fit_robust_reference` retirait les grands résidus de toute
la référence, validation comprise, puis refaisait le split. Le score pouvait s'améliorer en
supprimant précisément les lignes qu'il devait expliquer. Le trimming est maintenant limité
à la calibration, frontière gelée, validation intégralement conservée. Un test injecte un
outlier en apprentissage et un autre en validation : seul le premier peut être retiré.

**Contre-exemple apparu pendant correction.** Une production constante à 5 en calibration puis
10 ne permet pas d'apprendre une pente. Le solveur régularisé donnait pourtant une extrapolation.
Les prédicteurs constants sont maintenant persistés et une valeur nouvelle rend la ligne non
supportée. Un second test avec production effectivement variable vérifie que la normalisation
fonctionne sans simplement supprimer toutes les lignes futures.

Les scénarios gelés `production_explained` et `weather_explained` contiennent justement cette
production constante puis mobile, y compris comme variable nuisance météo. Leur zéro candidat
après correction est **en partie une abstention de support**, pas une preuve de régression météo
réussie. Ce compromis est publié ; il ne faut pas le compter comme un vrai négatif industriel.
La colinéarité multivariée, la non-linéarité et le contrefactuel physique restent des limites.

## 5. Quantification : des questions différentes, pas un chiffre magique

**Reproduction.** Probe `[9,11]` alterné autour de 10 kW : 12 kWh d'aire positive, 0 kWh signé.
Le calcul positif est exact ; l'interpréter en économie est faux. Le postmortem terrain réaliste
rapporte 944,61 contre 1 731,81 kWh selon la référence : aucune preuve ne désigne l'une comme
vérité physique. Ce cas n'a pas été « corrigé » en choisissant le nombre le plus favorable.

**Correction.** Nouvel outil séparant estimands ; comparateur de références sur les mêmes
intervalles, support et chronologie vérifiés, justifications explicites, fourchette de sensibilité
et abstention si signes contradictoires/justification ou couverture insuffisantes. NaN/inf refusés
également dans les anciens helpers excès/coût. La fonction historique d'aire positive garde sa
sémantique pour compatibilité. Le brief et la documentation imposent d'en expliquer l'estimand.

**Alternatives rejetées.** Imposer une baseline universelle, inventer un intervalle de confiance
entre deux modèles, convertir automatiquement un coût associé en économie, prétendre qu'un
validateur de provenance prouve la causalité d'une phrase.

## 6. Workflow complet : manque de mesure, pas preuve de succès agentique

Les scores initiaux portent sur les candidats, ceux des sessions Codex historiques sur des
reviews déjà écrites. Le nouveau harnais `benchmarking/final_workflow.py` engage protocole,
cohorte et hash de vérité, scelle les investigations effectivement fournies et leurs preuves,
puis évalue constats finaux/abstentions/quantification séparément. Il refuse omissions et
mutations. Une fourchette immense contenant la vérité ne reçoit aucun crédit numérique.

Une exécution non aveugle de cinq dossiers passe réellement par préparation, requête Evidence
Plane, calculs, contre-explications, décisions, scellement et score. Les gates de livraison
restent bloqués : aucune approbation humaine n'est inventée et ces dossiers d'évaluation connus
ne sont pas présentés comme des analyses client aveugles. Ce test de bout en bout ne remplace
ni une répétition indépendante par plusieurs sessions ni un pilote terrain.
