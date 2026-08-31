# Stage 4 — plan d’intégration de l’Evidence Plane

Statut initial : plan figé avant modification du code de production.

## Baseline et contraintes

- Révision initiale : `0d4ff75999f715ca179d872f0e4c283dc1be23e8`.
- Arbre Git initial : `0cf8f4a25c59f765238e57da99da3edf45e6f640`.
- Baseline exécutée : `283 passed in 121.73s` avec
  `python -m pytest -q tests prospecting/tests research/indicia_rnd research/indicia_rnd_stage2 research/indicia_rnd_stage3`.
- Charte Stage 4 : SHA-256
  `ccb469764f2497a8dc529b69e630727b0dea9fb0253d27d3fb38e9d149975eab`.
- Les arbres historiques Stage 1, 2 et 3 sont en lecture seule pendant cette intégration.
- Aucun résultat Stage 3 synthétique ne sera qualifié de preuve de fiabilité production.

## Cartographie des points d’intégration

1. `energy_mvp.io.load_data` est l’entrée canonique CSV/XLSX. Il normalise les
   colonnes physiques mais perd actuellement toute colonne non reconnue.
2. `energy_mvp.models.LoadedData` transporte les lectures physiques, la qualité
   et le schéma canonique ; il recevra un magasin contextuel séparé.
3. `energy_mvp.workflow.prepare_investigation` produit aujourd’hui un paquet
   statique et les signaux legacy. Il deviendra le point de migration contrôlée.
4. `energy_mvp.signals.detect_candidate_events` reste une source de preuves et
   de candidats legacy, jamais une source de conclusion.
5. `energy_mvp.case_lifecycle` garde les décisions et la review sous contrôle de
   Codex/humain ; la validation y exigera des références probatoires vérifiables
   lorsqu’un dossier Stage 4 les déclare.
6. `investigate.py` reste le préparateur. Un point d’entrée de requête distinct
   rendra le protocole exécutable et auditera chaque appel.

## Architecture cible et contrats

### Ingestion

- Conserver le noyau typé actuel pour timestamps, énergie, puissance,
  production, température, tarif et unités.
- Ajouter un `ContextualFieldStore` attaché à `LoadedData`, indexé par
  `source_row`, avec définition de champ, nom original, index source, type
  prudent, valeur brute JSON-compatible, valeur typée, complétude, cardinalité,
  troncatures et provenance.
- Résoudre les noms vides ou dupliqués par une clé interne stable basée sur
  l’index de colonne. Un alias canonique sélectionné n’est jamais copié dans le
  magasin auxiliaire ; une autre colonne de même nom reste distinguable.
- Inclure les valeurs auxiliaires dans la notion de doublon strict afin de ne
  pas effacer silencieusement un changement de contexte.
- Les champs auxiliaires sont exclus des calculs physiques tant qu’un outil ne
  les demande pas explicitement.

### Evidence Plane

- Introduire un snapshot déterministe et sérialisable construit depuis
  `LoadedData`, avec identifiant et hash de dataset, lignes canoniques,
  références aux lignes source et champs auxiliaires.
- Produire quatre mécanismes décisionnellement neutres : `ContrastSurface`,
  `SupportAtlas`, `BoundaryLedger` et `RelationshipLossCertificate`.
- Chaque résultat est enveloppé avec hash de requête, hash de dataset,
  provenance lignes/champs, limites de ressources, pertes relationnelles,
  handle de récupération et `decision: null`.
- Toute opération potentiellement quadratique reçoit une borne dure ; la
  comparaison de support utilise un parcours en flux et refuse le dépassement.

### Protocole de requête exécutable

- Ensemble fini d’opérations : description, récupération bornée, contraste,
  support, frontières et certificat de perte relationnelle.
- Validation stricte par opération : champs existants, types, tailles,
  tolérances, plages temporelles, limites de lignes et paramètres autorisés.
- Aucune expression, fonction, import ou exécution de code arbitraire.
- Session persistée avec budgets d’appels, de lignes retournées, d’octets de
  contexte et de comparaisons ; une requête sémantiquement répétée est refusée.
- Les handles pointent vers des sélections de lignes immuables du snapshot et
  sont résolus uniquement par l’opération de récupération bornée.

### Orchestration agentique

- `prepare_investigation` accepte `preferred`, `shadow` ou `legacy`.
- `preferred` conserve tous les artefacts legacy et ajoute snapshot, carte
  probatoire compacte, contrat de requête et session prête à dialoguer.
- `shadow` exécute les deux chemins et écrit une comparaison structurée sans
  changer le rapport client.
- `legacy` restitue le chemin historique et constitue le rollback immédiat.
- Codex reste propriétaire des hypothèses, contrastes pertinents,
  contre-explications, requêtes suivantes, abstentions et conclusions.
- Un registre de constat Stage 4 liera chaque résultat quantitatif à au moins un
  handle/résultat de requête ; l’insuffisance de preuve autorise explicitement
  `ABSTAIN`/`INSUFFISAMMENT_ETAYE`.

### Evidence Card v2

- Vue initiale compacte : noyau physique, qualité, inventaire des champs
  auxiliaires, signaux legacy clairement classés, capacités disponibles,
  couverture relationnelle résumée et chemins de récupération.
- Aucune conclusion, cause ou économie automatique.
- La carte indique explicitement quelles relations ne sont pas résumées et
  évite d’inclure les lignes brutes par défaut.

## Migration, validation et rollback

1. Ajouter d’abord les modèles et tests de round-trip auxiliaire.
2. Ajouter les primitives et tests de falsification : inversion de relation,
   manque de support, frontière de missingness et confusion saisonnière.
3. Ajouter protocole, CLI et sessions avec tests d’entrées invalides, budgets,
   répétitions, handles et provenance.
4. Intégrer le mode préféré et le shadow sans supprimer les artefacts legacy.
5. Exécuter les tests ciblés, la suite production, puis la suite historique
   complète. Vérifier les hashes Stage 1/2/3 après intégration.
6. Générer une comparaison shadow reproductible sur fixtures existantes. Elle
   mesure couverture, provenance, désaccords structurels, temps et erreurs ;
   elle ne simule pas une qualité de modèle.
7. Exécuter un probe borné de performance sur matériel local.
8. Documenter architecture, migration, rollback, shadow, benchmark modèle et
   audit de complétion.

Le rollback ne requiert aucune suppression : sélectionner `legacy`, ou retirer
les nouveaux artefacts d’un nouveau dossier de travail. Les anciens fichiers et
contrats restent générés et le rapport client ne dépend pas du nouvel Evidence
Plane pendant cette migration.

## Portes de sortie

- Baseline historique inchangée et suite production verte.
- Colonnes inconnues conservées avec provenance et round-trip.
- Primitives accessibles seulement par le protocole borné.
- Boucle d’outils persistée, répétitions stoppées, budgets visibles.
- Résultats et constats traçables jusqu’aux lignes sources.
- Comparaison shadow et procédure de rollback vérifiées.
- Benchmark modèle marqué `NOT_RUN` si aucun véritable accès modèle n’est
  disponible ; aucun score proxy ne sera inventé.
