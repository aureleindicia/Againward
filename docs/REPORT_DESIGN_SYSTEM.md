# Composition éditoriale AGAINWARD

Le design system fournit des primitives de document. Codex choisit les pages, leur ordre, les
findings, les comparaisons, les graphiques et la hiérarchie ; Python ne choisit aucun plan par défaut.
`report_design.py` réutilise le modèle client et le sérialiseur PDF de `client_delivery.py`.

## Contenu et composition

1. Construire le `CLIENT_REPORT_MODEL` avec le narratif sourcé existant.
2. Consulter `content_catalog(case, model, model_path)` pour les fragments autorisés.
3. Concevoir `REPORT_DESIGN_MODEL.json`, puis appeler `render_designed_report` ou la CLI avec `--design`.
4. Rasteriser chaque page, inspecter et recomposer jusqu’à un document lisible.

Le plan contient exactement : `schema_version=againward-report-design-v1`, `selected_findings`,
`omitted_actions` (motifs qualitatifs explicites), `pages`. Une page contient `intent` et `blocks`.
Un bloc contient `component`, `content_ref`, `box=[x,y,width,height]`, `font_size`, `emphasis`.
Les coordonnées sont en points PDF depuis le haut gauche d’une page A4. Elles sont des paramètres
de présentation, pas des données économiques. Les boîtes ne doivent ni se recouvrir ni sortir des
marges ; un texte trop long provoque un refus, jamais une troncature silencieuse.

Composants disponibles : COVER, EXECUTIVE_SUMMARY, FINDING, SECONDARY_FINDING, METRIC_CARD,
EVIDENCE_CHART, COMPARISON, DECISION, LIMITATION, ECONOMIC_RANGE, INVESTIGATION_VALUE, NEXT_STEP,
METHODOLOGY, TECHNICAL_APPENDIX. Un composant ne permet pas de changer le type de son contenu :
une métrique doit référencer un claim économique, un graphique sa preuve reproductible.

Références de catalogue : `cover`, `executive`, `notice`, `method`, `sources`, `limitations`,
`checked:<index>`, `no_action:<index>`, `<action_id>:what_we_found`, `:why_this_matters`,
`:contextual_rationale`, `:uncertainty`, `:decision`, `:constraints`, `:next_step`, `:economics`,
`value:<value_id>`, `chart:<chart_id>`. Elles restent internes, sans imprimer les IDs au client.
Aucun pointeur arbitraire dans un JSON interne n’est accepté comme fragment client.

Les titres et textes métier proviennent du narratif validé ; les montants proviennent des calculs
économiques revalidés. Les prochains contrôles conservent leurs libellés explicites. Les chiffres
de titre/période ne peuvent pas être saisis librement : utiliser un texte qualitatif ou les dates
provenant des sources graphiques. Si une information quantitative n’existe pas dans les artefacts,
l’agent demande un calcul/relevé sourcé avant de la mettre en avant.

Exemple de bloc de composition (le contenu doit exister dans le dossier) :

```json
{"component":"ECONOMIC_RANGE","content_ref":"ACTION_EXISTANTE:economics",
 "box":[45,440,500,230],"font_size":13,"emphasis":"PRIMARY"}
```

Cet exemple ne prescrit ni une page type ni un plan de rapport. L’agent peut employer plusieurs
colonnes, réunir des pistes secondaires ou consacrer davantage d’espace à une preuve importante.
La cible est de quelques pages utiles ; une petite mission ne doit pas être allongée artificiellement.
La limite technique de douze pages prévient un dump accidentel, sans imposer une longueur cible.

## Fidélité et graphiques

Pour chaque action visible, observation, incertitude, décision et contraintes matérielles restent
présentes. Une omission est explicite et soumise à revue. Les graphiques existants sont reconstruits
à partir des séries canoniques et comparés aux pixels/metadata ; fournir finding_refs, source_refs,
méthode, unités et légende. En l’absence de finding, utiliser le no_finding canonique, sans inventer
un finding pour pouvoir dessiner.

Les séries utilisent toute la fenêtre, une origine zéro pour les valeurs positives, la moyenne
par colonne de pixels **avec enveloppe min/max** pour préserver les événements courts. Les extrêmes
et la méthode sont reproductibles ; la résolution visuelle n’est pas une nouvelle analyse.
L’activité reste représentée séparément, y compris les inconnus. Cette première bibliothèque de
graphiques reste limitée aux séries et au contexte opérationnel ; des graphiques supplémentaires
nécessitent un calcul/source et un adaptateur de validation reproductible, pas une image libre.

## Doctrine visuelle AGAINWARD

La direction recherchée est celle d’un **industrial editorial consulting** : environ 70 %
intelligence industrielle moderne et 30 % cabinet de conseil premium. Le rapport doit sembler
préparé pour la décision d’un site réel, avec une forme calme au service de ce qui est prouvé.
Cette doctrine guide le jugement de Codex ; elle ne transforme pas la composition en template fixe.

Chaque page a une fonction décisionnelle et raconte une mini-histoire. La hiérarchie à privilégier
est : **conclusion → preuve → économie → incertitude → action**. Selon le dossier, une page peut
s’arrêter après la preuve et l’incertitude, ou mettre l’accent sur une abstention : l’ordre ne doit
jamais rendre une économie ou une action plus certaine que les données ne le permettent.

Les titres sont conclusifs : ils portent le message à retenir plutôt qu’un nom de rubrique générique.
« Vérifier avant investissement » est préférable à « Analyse économique » lorsqu’il exprime la
décision sourcée. Un titre ne doit toutefois pas créer de causalité, chiffre, finding ou niveau de
preuve absent des artefacts canoniques.

Viser des pages denses mais lisibles. L’espace blanc doit séparer des idées, mettre une preuve en
respiration ou rendre une décision immédiatement repérable ; il ne sert pas à simuler une esthétique
premium par le vide. Ne jamais entasser du texte ou des micro-blocs pour remplir une page. Codex règle
librement marges, colonnes, tailles et regroupements selon la matière réelle, avec des marges nettes
et une typographie sobre.

Utiliser peu de KPI, mais des KPI forts : un chiffre n’est mis en avant que s’il répond directement
à la décision et porte son statut et sa provenance. Il n’y a pas de quota de KPI. Une abstention,
contrainte opérationnelle ou hypothèse éliminée peut être le message principal sans KPI artificiel.

La couleur est fonctionnelle, jamais décorative. La palette de base est limitée à l’encre bleu sombre
AGAINWARD, à un accent vert industriel de marque et à quelques couleurs sémantiques discrètes pour
différencier preuve, réserve, activité ou état. Conserver un contraste lisible en impression. Pas de
violet, gradient futuriste, emoji, icône gratuite, série de cartes arrondies ni esthétique SaaS/AI
générique.

Le choix d’un graphique répond à une question analytique : courbe pour tendance ou rupture dans le
temps ; barres pour comparer des régimes ; waterfall pour décomposer un calcul économique ; camembert
uniquement pour une répartition réelle d’un total ; matrice pour relier preuves, hypothèses ou
alternatives. Une autre représentation est acceptable si elle éclaire mieux les données. Aucun
graphique n’est ajouté pour meubler une page, et aucun type n’est imposé par son numéro de page.

A4, fond blanc, Helvetica, encre bleu sombre et accent vert industriel discret restent les briques
par défaut. Les tailles, espacements et compositions restent choisis par l’agent dans ces limites de
lisibilité et de fidélité.

## Revue et livraison

`semantic_sha256` couvre les fragments, leur ordre, sélection, décisions, sources et images
analytiques. Les coordonnées, tailles et changements de pagination sans changement d’ordre n’en
font pas partie. Le gate revalide les sources et reproduit le PDF : changer son reçu ne suffit pas.

Après inspection réelle, appeler `record_visual_review` avec l’empreinte PDF et tous les contrôles
`VISUAL_CHECKS`. Une nouvelle version graphique demande une nouvelle inspection. La revue humaine
approuve `report_semantic_sha256` ; une nouvelle substance exige une nouvelle approbation, conservant
la précédente dans les traces plutôt que la réinterprétant.

Question de qualité obligatoire : **si ce PDF était envoyé demain au directeur d’une PME industrielle
ayant payé l’analyse, aurait-il l’impression de recevoir un livrable professionnel préparé
spécialement pour son entreprise ?** Si non, recomposer. Python ne peut pas répondre à cette question.

La revue visuelle finale doit aussi examiner explicitement :

- la densité de chaque page et tout excès de vide sans fonction ;
- la hiérarchie conclusion, preuve, économie, incertitude et action ;
- la lisibilité de la typographie, des chiffres, légendes et unités ;
- la pertinence de chaque graphique pour la question posée ;
- l’usage cohérent et fonctionnel de la couleur ;
- la qualité professionnelle globale, y compris la cohérence entre pages.

Ces critères complètent les contrôles techniques d’absence de coupure, de débordement et de contraste.
Ils appellent un jugement de Codex et une revue humaine du dossier réel ; ils ne deviennent pas des
quotas ni des règles de pagination.

Un bloc peut aussi porter `heading_ref`, qui résout un claim
`EDITORIAL_HEADING` sourcé dans `CLIENT_REPORT_MODEL.editorial_headings`.
Le titre est qualitatif et entre dans le hash sémantique. Les libellés des
chiffres économiques, de la Value Map, des décisions et des graphiques ne
peuvent pas être remplacés par ce mécanisme.
