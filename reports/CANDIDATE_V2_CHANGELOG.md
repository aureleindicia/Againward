# Candidate V2 — changelog analytique

## Version et périmètre

- tag : `expert-benchmark-candidate-v2` ;
- commit analytique : `7acc43fc00007af87c459fd60cc89d972515c59a` ;
- empreinte moteur :
  `dd2211e2ea0ad26b49c6ec8399dc362282b8be633ae9a3a244908c8bdac53cdd` ;
- baseline V1 conservée sous `expert-benchmark-baseline-v1` au commit
  `6ba8ebbdefac68caa3b2debb24f9b141472f0a9d`.

Aucune ground truth, réponse oracle privée ou donnée cachée des cas DEV n'a été utilisée
pour concevoir ces changements. Les exemples de faiblesse fournis par la revue externe
ont été traduits en principes physiques transversaux, pas en réponses par cas.

## Contrat Physical Differential

**Problème visé.** Une hypothèse pouvait être plausible sans expliciter son mécanisme,
ses prédictions, les preuves contraires ou la mesure qui la falsifierait.

**Solution générique.** `energy_mvp/physical_diagnostics.py` fournit un canevas et un
validateur de forme pour documenter chaîne énergétique, demande de service,
commande/feedback et trois causes concurrentes lorsqu'une piste importante reste
ouverte. Le validateur contrôle la complétude du raisonnement, jamais la vérité d'une
cause.

**Tests.** `tests/test_physical_diagnostics.py` vérifie notamment qu'une cause absente de
la knowledge layer et un protocole non prévu restent valides.

**Risque de régression.** Le canevas peut encourager du remplissage artificiel ou trois
hypothèses faibles. Il doit rester réservé aux pistes importantes ouvertes et ne remplace
pas l'abstention.

**Pourquoi ce n'est pas du hardcoding.** Aucun identifiant, timestamp, seuil ou organe
d'un cas DEV n'est présent. La structure s'applique à toute famille physique.

## Demande de service avant efficacité

**Problème visé.** Une hausse énergétique pouvait être qualifiée trop tôt comme défaut
sans vérifier si le procédé demandait davantage de service utile.

**Solution générique.** Le contrat exige `SERVICE_DEMAND_CHANGED?` avant
`SYSTEM_EFFICIENCY_CHANGED?` et rend explicite la variable de demande manquante. Le code
ne décide ni si la demande a changé ni si un défaut existe.

**Tests.** Hausse proportionnelle au service, hausse à service constant et blocage d'une
affirmation d'efficacité lorsque la demande essentielle reste inconnue.

**Risque de régression.** Une variable métier mal choisie peut donner une fausse
impression de normalisation. Codex doit justifier que la grandeur représente le service
physique utile.

**Pourquoi ce n'est pas du hardcoding.** Le principe vaut pour production, débit,
pression, chaleur, humidité, occupation ou tout autre service choisi par l'analyste.

## Commande versus état physique réel

**Problème visé.** Un planning ou une consigne correcte pouvait être traité comme preuve
du fonctionnement de l'actionneur ou de l'équipement.

**Solution générique.** Le contrat distingue commande et feedback. Le calculateur
`command_feedback_comparison` mesure les quatre quadrants et leur durée sans attribuer la
discordance à un capteur, une sécurité, un délai ou une panne.

**Tests.** Commande inactive avec feedback actif et commande active avec feedback inactif
sont quantifiés sans décision automatique.

**Risque de régression.** Un pseudo-feedback recopié de la commande ne constitue pas un
état réel ; cette limite est explicitement renvoyée.

**Pourquoi ce n'est pas du hardcoding.** La comparaison vaut pour vannes, registres,
moteurs, pressions, températures et tout système commandé.

## Mesures discriminantes et valeur d'information

**Problème visé.** Une demande générique ou un sous-comptage coûteux pouvait être préféré
à un test physique direct plus simple.

**Solution générique.** `DiscriminatingMeasurement` décrit variable, lieu, moment,
effort, technicien, risque, hypothèses et prédictions. Un classement qualitatif
consultatif combine nature de la mesure, effort et risque. Codex peut le déroger, l'ignorer
ou proposer une mesure absente ; aucune prochaine question n'est sélectionnée.

**Tests.** Priorité indicative d'un discriminant direct, dérogation explicite en faveur
d'un sous-compteur déjà disponible, et vérification que les champs de décision restent
`null`.

**Risque de régression.** Les poids peuvent ancrer l'analyste ou sous-estimer une
contrainte de site. Ils ne doivent jamais être présentés comme information théorique ni
comme politique obligatoire.

**Pourquoi ce n'est pas du hardcoding.** Les classes portent sur la qualité et le coût
d'une mesure, pas sur un symptôme ou une cause.

## Knowledge layer physique

**Problème visé.** Les variables et mécanismes physiques utiles étaient dispersés et peu
auditables.

**Solution générique.** Six fiches locales couvrent froid, thermique/fours, air comprimé,
moteurs/pompes/ventilateurs, blanchisserie/eau chaude/vapeur et CVC. Elles décrivent
chaîne énergétique, demande, commande, feedback, environnement, mécanismes possibles,
prédictions, discriminants, tests et sécurité.

**Fichiers.** `knowledge/physical_diagnostics/*.json`,
`docs/PHYSICAL_DIAGNOSTICS.md` et leur chargeur validé.

**Tests.** Les six familles sont chargées, les documents sont validés et aucune
probabilité ou conclusion causale automatique n'est acceptée.

**Risque de régression.** Toute liste de mécanismes peut produire un biais d'ancrage ou
sembler exhaustive. La documentation et le runner indiquent explicitement que les causes,
variables et protocoles non listés restent autorisés.

**Pourquoi ce n'est pas du hardcoding.** Les fiches décrivent des relations physiques et
leurs limites, jamais `observation X => cause Y`.

## Calculateurs physiques déterministes

**Problème visé.** Codex devait réimplémenter des opérations quantitatives transversales,
avec un risque d'erreur d'unité ou de calcul mental.

**Solution générique.** `energy_mvp/physical_tools.py` ajoute : énergie spécifique,
régimes appariés, avant/après normalisé, commande/feedback, duty cycle, degré-heures,
décroissance de pression, chaleur sensible, bilan de récupération et scénario de lois
d'affinité pompe/ventilateur.

**Tests.** Cas synthétiques indépendants vérifient unités, hypothèses, erreurs d'entrée,
limites et absence de décision métier.

**Risque de régression.** Les lois d'affinité, l'appariement et le bilan thermique peuvent
être physiquement inapplicables malgré un calcul exact. Les sorties portent des
avertissements ; Codex choisit les régimes et interprète.

**Pourquoi ce n'est pas du hardcoding.** Les fonctions retournent mesures, comparaisons,
incertitudes et métadonnées, jamais `cause`, `question` ou `action`.

## Oracle `semantic-v3-blind-fallback`

**Problème visé.** Le matcher automatique pouvait être juge final d'un apparent
`NO_MATCH` lexical malgré une question métier structurée et physiquement discriminante.

**Solution générique.** Les matchs très sûrs restent automatiques. Les cas ambigus et les
apparents non-matchs physiques structurés passent en `PENDING_BLIND_ORACLE_REVIEW`. Les
demandes vagues, hors sujet, non discriminantes ou déjà répondues restent seules éligibles
au non-match automatique. La réponse et les payloads ne participent jamais au matching.

**Tests.** Corpus indépendant : précision automatique 1,0, rappel automatique 0,923077,
zéro faux positif et deux routes aveugles. Les tests V2 couvrent fallback sans recouvrement
lexical, hors sujet, double demande, paquet minimal, absence de révélation et décision
indépendante reproductible.

**Risque de régression.** Un oracle volumineux peut avoir plus de huit catégories faibles ;
le bon candidat pourrait être absent du paquet de fallback. À l'inverse, des formulations
physiques artificiellement longues peuvent augmenter le coût de revue, mais jamais
révéler seules une réponse.

**Pourquoi ce n'est pas du hardcoding.** Le lexique et le routage sont génériques ; aucun
contenu privé ni identifiant DEV n'a servi à les concevoir.

## Garde anti-contamination

`tests/test_candidate_v2_hardcoding.py` recherche les 18 identifiants DEV connus dans les
nouveaux fichiers analytiques, de connaissance et de documentation. Les tests complets
passaient à **171/171** avant gel. `case_a17` est exclu de la campagne et des agrégats sous
le statut `EXCLUDED_PENDING_CASE_VALIDATION`, sans adaptation du moteur.
