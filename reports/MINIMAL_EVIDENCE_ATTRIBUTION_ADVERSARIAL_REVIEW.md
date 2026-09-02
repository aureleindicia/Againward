# Review adversariale — MinimalEvidenceAttribution

## Question obligatoire

**Quelle est la meilleure raison de penser que la conclusion pourrait être fausse ?**

Le benchmark synthétique encode les mêmes catégories de variables que le moteur. Les seeds
HOLDOUT changent le bruit mais pas la structure causale ni les erreurs possibles d'un site réel.
Une performance parfaite dans ce corpus peut donc mesurer la cohérence entre générateur et
garde-fous, pas la validité d'une attribution industrielle.

Cette objection ne peut pas être éliminée avec davantage du même benchmark. Elle impose une
validation prospective multi-sites et limite le statut à `research_only_requires_field_validation`.

## Tentatives de réfutation

### 1. Agrégation et charges simultanées

Deux charges de 5 kW ont été combinées pour imiter un actif de 10 kW. Sans information de
chevauchement, une méthode d'amplitude peut nommer le faux actif. Le garde-fou
`overlap_ambiguous` force `insufficient_evidence` et interdit le nom sans ancre.

Décision : **CONFIRMÉ pour le garde-fou logiciel**, mais la détection automatique de tout
chevauchement reste **INSUFFISAMMENT ÉTAYÉE**.

### 2. Horaires et puissance nominale trompeurs

Des identités de profils ont été permutées dans le registre. Le contexte brut produit trois
fausses attributions sur les six cas adversariaux ; l'amplitude seule en produit une. Avec
25 % de permutations non signalées sur 2 500 cas par méthode, le contexte atteint 24,8 % de
fausses attributions. À 50 %, il atteint 51,0 %.

Décision : l'utilisation de `contextual` ou `evidence_aware` comme politique automatique est
**REJETÉE**. Ces méthodes restent des outils de shortlist. `guarded_evidence` est
**À CONSERVER AVEC RÉSERVES** : aucune fausse attribution observée, au prix d'une couverture
égale au taux d'ancres vérifiées.

### 3. Information terrain erronée ou contradictoire

Une déclaration non vérifiée, même assortie d'une fiabilité numérique élevée, ne peut plus
éliminer durement un candidat. Deux éléments favorables/défavorables concurrents font baisser
la confiance et empêchent la sélection. Une correction du ledger supersède l'élément initial
sans l'effacer.

Décision : **CONFIRMÉ sur les fixtures synthétiques**. La fiabilité déclarée n'est pas une
garantie de vérité ; cette limite reste ouverte.

### 4. Événement naturel trompeur

Un arrêt apparemment isolé mais comportant un co-événement non journalisé a provoqué une fausse
attribution dans le prototype brut. L'événement ne devient discriminant qu'avec
`confounder_audit_status=verified_scope`. Un événement non discriminant ne promeut rien.

Décision : promotion brute **REJETÉE** ; événement à portée vérifiée **À CONSERVER AVEC
RÉSERVES**. L'exhaustivité du journal ne peut pas être prouvée par l'algorithme lui-même.

### 5. Ancre temporaire mal étiquetée

Une pince présentée sur le mauvais actif crée une attribution robuste mais fausse si l'identité
du canal est acceptée sans contrôle. Le champ séparé `anchor_verified` est maintenant requis
pour casser une équivalence ou atteindre l'attribution robuste.

Décision : ancre non vérifiée **REJETÉE comme discriminateur**. Une ancre vérifiée reste
**À CONSERVER AVEC RÉSERVES**, car son contrôle est un protocole humain/terrain.

### 6. Dérive et réutilisation historique

La distance moyenne initiale acceptait une forte dérive de puissance diluée par des dimensions
stables. Elle a été remplacée par un double seuil moyen/par dimension. Sur 25 cas synthétiques,
le seuil moyen 0,10 donne 10 vrais réemplois, 15 vrais refus et aucun faux ; à 0,15, cinq
changements multivariés sont acceptés à tort.

Décision : distance moyenne seule **REJETÉE** ; règle 0,10 + plafond 0,25 par dimension
**À CONSERVER AVEC RÉSERVES**, sans prétendre à une calibration terrain universelle.

### 7. Micro-question mal spécifiée

La stratégie VOI bat l'information gain pure sur les questions disponibles du benchmark
(100 % contre 33,3 % de choix cible). Mais lorsque la partition candidat→réponse est fausse et
que le risque n'est pas déclaré, elle continue de choisir la question fragile. À 50 % d'erreurs
déclarées, elle bascule vers la question robuste ; une erreur cachée reste indétectable.

Décision : stratégie VOI **CONFIRMÉE comme classement sous hypothèses explicites**, mais toute
capacité d'auto-correction d'une mauvaise partition est **REJETÉE**.

### 8. Surconfiance et calibration

Les compatibilités n'ont pas de définition probabiliste et aucun corpus terrain calibré n'existe.
Le système expose donc `posterior_probability=null`. Les tableaux par niveau de confiance sont
des diagnostics empiriques, non une calibration d'actif responsable.

Décision : toute présentation des scores comme probabilité est **REJETÉE**.

### 9. Généralisation

DEVELOPMENT et HOLDOUT obtiennent chacun 75 décisions correctes sur 100 pour la politique
gardée, sans faux positif. Leur égalité est attendue, car les scénarios partagent le même
générateur. Elle ne démontre ni transfert entre secteurs, ni robustesse aux conventions locales,
ni efficacité sur des signatures extraites imparfaitement.

Décision : généralisation inter-sites **INSUFFISAMMENT ÉTAYÉE**.

### 10. PX-201

Le scanner Python n'a trouvé aucune fixture de données PX-201 parmi 2 154 fichiers ou archives
candidats. Toute reproduction de `+2.7 kW` ou d'une plage 06:00–22:00 serait inventée.

Décision : étude réelle PX-201 **NON RÉALISABLE avec le dépôt courant** ; aucune donnée réelle
n'a été simulée sous son nom.

## Vérification des frontières

- détection : hors de la nouvelle couche, conservée dans les moteurs existants ;
- signature : objet anonyme avec provenance et incertitude ;
- actif : seulement probable/robuste selon le garde-fou ;
- mécanisme physique : interdit dans le schema et le validator ;
- pronostic : interdit dans le schema et le validator ;
- économie : aucune valeur produite par cette couche ;
- double comptage : non applicable, aucune énergie ni économie agrégée ici.

## Verdict final

La couche est **À CONSERVER AVEC RÉSERVES en shadow mode**. Ce qui est confirmé est son
comportement déterministe sur les scénarios contrôlés : représentation de l'inconnu,
abstention, provenance, révision, sélection de question et plafonnement des claims. Une capacité
d'attribution industrielle autonome, un mécanisme et un pronostic restent non démontrés.

