# Audit de complétion Stage 4

Statut : **COMPLETE — production integration with bounded nominal path and rollback**.

## Références et baseline

- Charte lue : `/storage/emulated/0/Download/INDICIA_STAGE4_EVIDENCE_PLANE_PRODUCTION_INTEGRATION.md`.
- SHA-256 de la charte :
  `ccb469764f2497a8dc529b69e630727b0dea9fb0253d27d3fb38e9d149975eab`.
- Commit initial : `0d4ff75999f715ca179d872f0e4c283dc1be23e8`.
- Arbre initial : `0cf8f4a25c59f765238e57da99da3edf45e6f640`.
- Baseline avant changement : **283 passed in 121.73s**.
- Commande avant et après :

```sh
python -m pytest -q tests prospecting/tests \
  research/indicia_rnd research/indicia_rnd_stage2 research/indicia_rnd_stage3
```

- Résultat final : **312 passed in 106.51s** ; 254 tests production sont collectés sous `tests/`.
- Commits Stage 4 :
  - `33ee73c feat(stage4): integrate agentic evidence plane` ;
  - `dbfda45 test(stage4): harden evidence gates and benchmark matrix`.

## Préservation des preuves gelées

Les empreintes agrégées, calculées avant puis après l’intégration en excluant seulement les caches
Python, sont identiques :

- Stage 1 `research/indicia_rnd` :
  `373044afa1bcfabb2775f42599c8ef47a2982a609352799f4b8811054c185af3` ;
- Stage 2 `research/indicia_rnd_stage2` :
  `d6a2e4653d642f643540cf1ddda1eae60bac6e03eac3e229ef5a6d2f41ad3b1d` ;
- Stage 3 `research/indicia_rnd_stage3` :
  `0accc9203f15dd0947726d2d3ffc130d17318d9a370381d9ddea7e560c1f7582`.

Aucun fichier sous ces arbres n’a été modifié, supprimé ou promu par import direct. Les résultats
Stage 3 restent classés recherche/régression, jamais preuve de fiabilité production.

## Audit des phases et portes d’acceptation

| Exigence | Preuve autoritative | Verdict |
|---|---|---|
| Plan avant gros changements | `IMPLEMENTATION_PLAN.md`, baseline et cartographie datées avant le code production | PASS |
| Noyau typé inchangé | `Reading`, conversions et 254 tests production ; tests d’unités historiques verts | PASS |
| Colonnes inconnues conservées | `ContextualFieldStore`, intégration `io.load_data`, `tests/test_contextual.py` | PASS |
| Typage/missing/malformed/cardinalité | tests booléen, numérique, catégoriel, datetime, mixed, absent, haute cardinalité | PASS |
| Sérialisation/provenance | round-trip magasin v2/v1, `source_rows`, raw/typed columns, hash EvidenceDataset | PASS |
| Pas de contamination physique | auxiliaire séparé, jamais utilisé sans champ explicitement demandé ; rollback testé | PASS |
| Contrast Surface | inversion signée et missingness testées ; sortie `decision: null` | PASS |
| Support Atlas | vues full/séquentiel/isolé/leave-one-out, outcome interdit, borne de paires testée | PASS |
| Boundary Ledger | localisation, missingness, confondeur contextuel, démarrage et arrêt distincts testés | PASS |
| Perte relationnelle | certificat dans carte et chaque enveloppe ; pair counts/omissions/retrieval testés | PASS |
| Handles de récupération | sélecteurs typés, raw slice exact, source rows et représentation brute testés | PASS |
| Protocole fini et sûr | six opérations Enum, clés/arguments inconnus refusés, aucun code arbitraire | PASS |
| Budgets et répétition | appels/lignes/octets/paires/handles bornés, répétition sémantique refusée et auditée | PASS |
| Incertitude/suffisance | chaque réponse laisse la suffisance à l’agent, expose claim boundary et abstention | PASS |
| Boucle agentique | Evidence Card initiale, CLI, session persistée, hypothèses/alternatives/arrêts dans state | PASS |
| Provenance finale | `agent_findings.json`, validation query IDs/handles, delivery gate et tests E2E | PASS |
| Abstention | statuts `ABSTAIN`/`INSUFFISAMMENT_ETAYE` et `evidence_gap` obligatoires | PASS |
| Evidence Card v2 | compacte, sans lignes brutes, missingness, relation loss, retrieval et legacy classifié | PASS |
| Coexistence legacy | candidats copiés sans décision ; H01/H02/H03/H05 classifiés explicitement | PASS |
| Shadow | trois cas, aucune perte candidat, preuves supplémentaires, désaccords et `NOT_MEASURED` honnête | PASS |
| Preferred/fallback/rollback | modes `preferred`, `shadow`, `legacy`; rollback restaure aussi déduplication ancienne | PASS |
| Rapport client simple | renderer non couplé ; exécution CLI réelle produit rapport Markdown/JSON non vides | PASS |
| Performance bornée | probe 10k/100k/500k ; fenêtre capée ; O(n²) Support refusé hors budget | PASS |
| Benchmark modèle | matrice 8 conditions préparée/testée ; statut `PREPARED_NOT_RUN`, scores nuls | PASS |
| Suite historique | 312/312 verte, verrou HOLDOUT compris | PASS |

## Changements de production

- `energy_mvp.models` ajoute les schémas du magasin auxiliaire sans casser les constructeurs
  historiques de `LoadedData`.
- `energy_mvp.io` préserve le contexte inconnu, renforce la déduplication et offre un rollback
  explicite de l’ancienne sémantique.
- `energy_mvp.evidence_plane` contient snapshot, Contrast Surface, Support Atlas, Boundary Ledger
  et certificat de perte relationnelle.
- `energy_mvp.evidence_protocol` contient requêtes typées, enveloppes partagées, budgets, handles,
  répétitions, hash de session et validation des constats.
- `energy_mvp.evidence_card`, `energy_mvp.evidence_cli` et `energy_mvp.shadow` intègrent
  représentation, boucle exécutable et migration.
- `energy_mvp.workflow` rend le chemin `preferred` nominal tout en conservant les fichiers legacy ;
  `case_lifecycle` impose la provenance Stage 4 au verrou de livraison.
- `query_evidence.py` est le point d’entrée agent ; les réponses et la session sont écrites
  atomiquement dans le workspace.
- Le rapport client et les calculateurs de coûts/énergie n’ont pas été remplacés.

## Fichiers suivis modifiés

- `README.md`
- `docs/ANALYSIS_TOOLS.md`
- `energy_mvp/case_lifecycle.py`
- `energy_mvp/io.py`
- `energy_mvp/models.py`
- `energy_mvp/toolbox.py`
- `energy_mvp/workflow.py`
- `energy_mvp/workflow_cli.py`
- `tests/test_case_lifecycle.py`
- `tests/test_workflow.py`

## Nouveaux fichiers

- `benchmarking/stage4_model_harness.py`
- `energy_mvp/contextual.py`
- `energy_mvp/evidence_card.py`
- `energy_mvp/evidence_cli.py`
- `energy_mvp/evidence_plane.py`
- `energy_mvp/evidence_protocol.py`
- `energy_mvp/shadow.py`
- `prepare_stage4_model_benchmark.py`
- `query_evidence.py`
- `run_stage4_performance.py`
- `run_stage4_shadow.py`
- `tests/test_contextual.py`
- `tests/test_evidence_cli.py`
- `tests/test_evidence_plane.py`
- `tests/test_stage4_model_harness.py`
- tous les fichiers de `docs/stage4_evidence_plane/`.

## Shadow et désaccords

`SHADOW_COMPARISON.json` couvre une fixture mensuelle, la démo 15 minutes et une fixture à champs
opérationnels inconnus. Résultat : 0 perte de candidat legacy, 0 finding automatique nouveau,
0 échec. Le nouveau chemin apporte inventaire auxiliaire, pertes relationnelles et récupération.

Les catégories « même conclusion », « abstention correcte » et « désaccord de findings » restent
`NOT_MEASURED`, car aucun vrai modèle n’a exécuté les deux investigations. C’est l’unique désaccord
non résolu important : la qualité décisionnelle comparative nécessite encore une campagne modèle
aveugle et une adjudication. Aucun résultat déterministe n’est utilisé comme proxy.

## Performance finale

Mesure locale Termux avec deux colonnes auxiliaires et trois requêtes :

| Lignes | Snapshot | Pic Python tracé | Ingestion | Build + sérialisation | Contraste | Boundary |
|---:|---:|---:|---:|---:|---:|---:|
| 10 000 | 2,81 Mo | 17,3 Mo | 1,98 s | 0,95 s | 0,07 s | 0,26 s |
| 100 000 | 28,25 Mo | 171,7 Mo | 22,04 s | 11,33 s | 0,79 s | 0,35 s |
| 500 000 | 142,12 Mo | 862,0 Mo | 120,97 s | 56,13 s | 4,22 s | 0,52 s |

Le stockage colonnaire et la fenêtre de frontière capée rendent les requêtes pratiques. La
préparation 500 000 lignes reste un traitement batch lourd sur Android et non une interaction
fréquente recommandée. `tracemalloc` ne mesure que les allocations Python.

## Limites connues

- Aucune donnée client indépendante et aucun transcript modèle aveugle nouveau ne valident encore
  un gain de qualité décisionnelle ; les preuves Stage 4 sont production/regression/engineering.
- Le snapshot JSON augmente le stockage local et peut contenir du contexte sensible ; il doit rester
  dans les workspaces ignorés et n’est jamais uploadé.
- Les valeurs physiques brutes pré-normalisation ne sont pas dupliquées dans le snapshot.
- Une valeur auxiliaire très longue est tronquée selon la limite déclarée et signalée.
- Support Atlas exige que l’agent réduise des cohortes dont le produit dépasse le budget.
- Boundary Ledger reste exploratoire et doit être attaqué par saison, régime et qualité de données.
- Le benchmark modèle est préparé mais **NOT_RUN** ; aucun score modèle n’existe.

## Rollback

Statut : **VERIFIED**.

`--evidence-plane-mode legacy` crée un nouveau dossier sans snapshot, carte ni session et conserve
les artefacts legacy. Les fichiers `prepared_analysis.json` et `candidate_signals.json` ont été
comparés byte-for-byte entre `preferred` et `legacy` sur la fixture mensuelle. Le mode legacy
désactive aussi la conservation auxiliaire afin de restaurer l’ancienne déduplication. Les dossiers
existants ne sont jamais écrasés ; aucune migration destructive ou downgrade n’est requis.

## Validation et portée de preuve

- Développement/régression : 312 tests, shadow sur fixtures du dépôt, tests Stage 3 réutilisés
  uniquement comme régressions historiques.
- Ingénierie : rapport client E2E, comparaison preferred/legacy, probe 10k/100k/500k.
- Genuinely unseen : **aucune nouvelle preuve Stage 4**.
- Modèle : **PREPARED_NOT_RUN**.

La productionisation est donc prouvée au niveau architecture, contrats, calculs, migration et
régression. Elle ne constitue pas une preuve que l’Evidence Plane améliore déjà les décisions d’un
modèle ou la fiabilité sur des données client indépendantes.
