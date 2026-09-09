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

## Identité visuelle

A4, marges confortables, Helvetica, fond blanc, encre bleu sombre, accent vert industriel discret.
Titres courts et contrastés, corps lisible, chiffres avec statut explicite, peu de cadres. Pas de
jauges, scores décoratifs, gradients, icônes gratuites ou tableau de bord imprimé. Les tailles,
espacements et compositions restent choisis par l’agent dans ces limites de lisibilité.

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

Un bloc peut aussi porter `heading_ref`, qui résout un claim
`EDITORIAL_HEADING` sourcé dans `CLIENT_REPORT_MODEL.editorial_headings`.
Le titre est qualitatif et entre dans le hash sémantique. Les libellés des
chiffres économiques, de la Value Map, des décisions et des graphiques ne
peuvent pas être remplacés par ce mécanisme.
