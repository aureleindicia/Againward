# Rental : extraction, investigation et livraison

Rental traite des actifs loués génériques : item, parties, période, contrat,
événements, factures et avoirs. Aucun engin BTP n'est requis. `construction` ajoute
du vocabulaire (nacelle, pelle, chariot, générateur…), des frais plausibles et des
vérifications opérationnelles. Ces suggestions n'autorisent aucun tarif.

## Entrées et provenance

L'entrée de `investigate.py --domain rental` est un JSON versionné :

- `againward-rental-case-v1` : listes `documents`, `parties`, `items`, `periods`,
  `terms`, `events`, `actual_charges`, `credits` ;
- ou `againward-rental-extraction-v1` : `case` au schéma précédent et `tables`
  décrivant explicitement les colonnes CSV/XLSX et constantes d'extraction.

Les dataclasses de `models.py` constituent le contrat exhaustif ; les champs
inconnus sont refusés. Les générateurs `benchmarking/rental_cases.py` produisent
des exemples lisibles avec documents sources et extractions, sans données client.

Chaque record porte `evidence_refs` (`document_id`, `location`, `field` facultatif).
Un document porte un rôle, un chemin relatif, son SHA-256 et un statut explicite.
`EXTRACTED` n'est pas `ACCEPTED`. `UNKNOWN` et `IRRELEVANT` sont permis à l'inventaire,
mais ne servent pas de justification analytique. Les liens identifient les items,
périodes et lignes, jamais seulement une description similaire.

Codex interprète les textes, emails exportés ou documents hétérogènes et produit
l'extraction canonique. Python ne prétend pas valider sémantiquement une citation
par son seul hash. Pour CSV/XLSX, le mapping explicite conserve la ligne, la feuille
et les colonnes ; les formules XLSX sont refusées en l'absence d'export revu.
Les dates de calendrier XLSX sont normalisées ; une heure non nulle est refusée.
Un lecteur PDF natif borné existe, mais il ne comprend pas seul les clauses. Le
gate privacy inspecte le texte natif et demande une revue visuelle réelle pour
les scans/pages hybrides ; les composants non inspectables restent bloqués.
L'extraction sémantique modèle produit seulement des propositions sourcées,
jamais des faits ou créances approuvés. Voir
[`SEMANTIC_EXTRACTION_EVALUATION.md`](SEMANTIC_EXTRACTION_EVALUATION.md).

Dans un dossier réel, créer le workspace, effectuer la revue privacy puis écrire
l'extraction sémantique dans `processed/` en référençant `../sanitized/...`. Les
documents sont vérifiés contre les hashes approuvés ; les dérivés restent isolés.
Ne jamais utiliser `--synthetic` pour contourner le gate d'un client réel.

## Conventions de calcul

Les périodes sont `[start, end)` en dates ISO : `2026-09-01` à `2026-09-08` signifie
sept jours. Les montants sont nets de taxes, en chaînes décimales exactes, avec
arrondi HALF_UP par charge à 0,01. EUR, USD, GBP, CHF, CAD, AUD et NZD sont acceptés,
sans conversion. Chaque devise a son total séparé. Les entrées float sont refusées
dans le modèle canonique ; le contexte Decimal interne est fixé indépendamment de
l'appelant.

Tarifs : jour, semaine, mois calendaire, forfait et pourcentage d'une autre charge.
Une semaine vaut sept jours facturables ou cinq jours ouvrés selon la convention
explicite ; un mois utilise les anniversaires calendaires. `EXACT`, `STARTED` ou
`PRORATA` définit les fractions de période. Quantité, remise, minimum et week-ends
doivent être documentés. Les paliers portent sur la durée calendaire résolue. Les
pourcentages suivent un graphe de dépendances borné à 32 niveaux.

Un avenant accepté peut remplacer explicitement un tarif ; une proposition ne le
remplace pas. Le moteur n'effectue pas automatiquement une ventilation de tarif en
cours de période : créer des périodes/allocation explicites et justifiées. Les
retours partiels, les dates contradictoires ou les conventions absentes produisent
un montant attendu inconnu. Une demande d'enlèvement ne vaut pas retour : le
contrat précise `stop_event` et si le jour de cessation est facturable.

Les avoirs émis et documentés sont soustraits une seule fois à la ligne référencée.
Une promesse n'est pas un avoir appliqué. Surallocation et devises incohérentes sont
refusées. Aucune TVA, pénalité légale ni probabilité de récupération n'est inventée.

## Commandes et artefacts

```sh
python create_workspace.py location_01 --domain rental --profile construction
# Revue contractuelle/privacy selon docs/CLIENT_WORKFLOW.md, puis extraction Codex.
python investigate.py workspaces/location_01/processed/extraction.json \
  --domain rental --profile construction --output-dir workspaces/location_01/processed
python query_evidence.py workspaces/location_01 request.json
python manage_investigation.py rental-review workspaces/location_01 assessments.json
```

La préparation écrit les deux ledgers, `rental_case.json`, `artifact_inventory.json`,
`prepared_analysis.json`, `candidate_signals.json`, le dataset et la session Evidence,
ainsi que les templates d'investigation/review. Elle pose **zéro question par défaut**.
Un dossier existant n'est pas écrasé.

L'analyste renseigne les assessments : décision, niveau L1/L2/L3, confiance justifiée,
meilleure raison d'être faux, tests d'alternatives sourcés, limites, questions non
résolues, scope commercial/opérationnel/identité vérifié et références Evidence.
Le schéma fermé n'accepte aucun montant fourni par l'agent. `rental-review` calcule
les montants admissibles et écrit `rental_findings.json` et `agent_findings.json`.

Les hypothèses de `investigation.json` utilisent les finding IDs et les résultats
exacts `group_id`, `difference`, `currency`, `recovery_grade_amount`. La review
adversariale couvre `calculations`, `data_quality`, `contract_authority`, `timeline`,
`alternative_explanations`, `recoverability`, `double_counting`, `currency`.
Une incertitude se termine par une prochaine vérification ou une limite terminale
justifiée. Une absence de candidat ne démontre pas la complétude du dossier.

## Questions, reprise et rapport

Utiliser le lifecycle partagé : `data-exhausted`, `publish-candidates`,
`record-answers`, puis `complete-resume`. Une demande BLOCKING impose un vrai STOP.
R06 montre ces étapes avec une réponse **explicitement synthétique**, jamais une
fausse réponse attribuée à un client.

Une nouvelle pièce réelle passe elle aussi par `incoming/`, revue sémantique Codex
puis `privacy-validate CASE review.json --supplemental`. Utiliser de nouveaux noms
et des `file_id` distincts : aucune pièce sanitized précédente n'est écrasée. La
présence d'un nouveau dépôt bloque l'analyse même si le premier lot était approuvé.
Le post-check conserve les lots antérieurs, les demandes et leur état WAIT. Hors
WAIT, il impose RESUMING. La nouvelle extraction reste un dérivé dans le même dossier
et le recalcul lie ses résultats à la nouvelle version du manifest privacy.

```sh
python manage_investigation.py rental-recalculate CASE revised_extraction.json
# Nouvelles requêtes, assessments, investigation et review obligatoires.
python manage_investigation.py complete-resume CASE resume.json
python manage_investigation.py finalizable CASE investigation.json
python manage_investigation.py rental-report CASE synthese_analyste.md
python manage_investigation.py check CASE
```

Le recalcul revalide la privacy et les hashes de toutes les sources. Il archive les
anciennes preuves et consomme le budget de requêtes restant. La synthèse est écrite
par Codex, puis composée avec une table calculée et `rental_evidence_pack.json`.
Le rendu n'accorde aucune approbation humaine. Une revue humaine réelle doit ensuite
fournir les hashes `reviewed_artifact_hashes` retournés par le rendu. Le gate partagé
reste l'autorité de livraison ; modifier le rapport après approbation le bloque.

## Niveaux et limites des conclusions

L1 désigne un signal, L2 un écart étayé, L3 une base de réclamation après décision
explicite, preuves suffisantes et examen des alternatives. `recoverable_amount`
reste inconnu : même L3 ne garantit pas un recouvrement. Les groupes par
`period_id/charge_key/currency` portent le montant commun aux familles qui se
chevauchent ; seul le total des groupes distincts doit être utilisé.

Le registre couvre les familles demandées. L'implémentation détecte notamment les
tarifs/paliers, durées, quantités, retours/off-hire, doublons, remises, frais et
promesses d'avoir non appliquées. `MISSING_CREDIT` reste un type disponible pour
une future règle documentée ; le moteur n'invente pas une obligation d'avoir.
Les descriptions et les tests rédigés restent soumis à l'examen contradictoire et
humain : le validateur vérifie leur structure et leurs références, pas leur vérité.
