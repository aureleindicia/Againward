# Checkpoint — Candidate V2

## Phase terminée

État initial figé et audit documentaire/architectural de référence terminé.

- HEAD initial : `a37018d29ad214cd41ed7adb0a059797ac20735b`
- branche Candidate V2 : `candidate-v2`
- commit de checkpoint sans changement fonctionnel :
  `ccf9e4eff0cbb9a0735ebab1559a906dcbf425bc`
- baseline analytique : `expert-benchmark-baseline-v1`, commit
  `6ba8ebbdefac68caa3b2debb24f9b141472f0a9d`
- empreinte baseline du moteur (32 fichiers) :
  `e7261871cd3ff7203bf5cf6bb986bc2102bec00f9c63f63319ead7430084613a`
- diff des chemins analytiques protégés avant V2 : vide
- aucune ground truth, aucun payload oracle privé et aucun fichier `revealed/`
  n'a été lu pendant cet audit.

## Fichiers modifiés

- `CODEX_GOAL_CHECKPOINT.md` (nouveau journal de reprise)
- `reports/CANDIDATE_V2_DIAGNOSTIC_PLAN.md` (diagnostic préalable)

Les fichiers utilisateur non suivis présents au départ restent hors périmètre et intacts :
`ENERGY_ANALYZER_MEGA_GOAL.md`, `PROSPECTION_VEILLE_GOAL.md` et
`reports/REALISTIC_CLIENT_TEST_POSTMORTEM.md`.

## Tests

- `pytest -q` : **147 passed** en 15,12 s
- `pytest -q tests/test_physical_expertise_benchmark.py` : **24 passed** en 11,05 s

## Commit courant

`ccf9e4eff0cbb9a0735ebab1559a906dcbf425bc`

## Prochaine action

Concevoir puis implémenter, sans règle par cas, le contrat de raisonnement physique,
la knowledge layer auditable et les outils déterministes à forte valeur générale.

## Tâches restantes

- implémenter la couche de raisonnement et la connaissance par famille ;
- ajouter les calculateurs physiques génériques ;
- durcir le fallback `NO_MATCH` de l'oracle ;
- ajouter les tests synthétiques et la garde anti-hardcoding ;
- documenter et tester Candidate V2 ;
- geler/taguer Candidate V2 ;
- exécuter une seule campagne DEV V2, avec `a17` exclu des agrégats ;
- produire les deux rapports finaux et la revue adversariale ;
- vérifier les empreintes, commits et l'intégrité de V1.


## Contrainte d architecture ajoutee

Le code Candidate V2 ne doit produire ni cause, ni question, ni intervention, ni decision
analytique. Codex reste l enqueteur principal ; Python mesure ; les fiches physiques sont
des references non exhaustives. La revue finale doit inclure un AGENTICITY AUDIT et
considerer comme regression toute amelioration DEV obtenue par un moteur a regles.


## Checkpoint phase 2 — couche physique et oracle V3

### Phase terminée

- couche de raisonnement physique générique et non décisionnelle pour six familles ;
- knowledge layer locale, structurée et non exhaustive ;
- calculateurs Python physiques retournant mesures/limites sans cause ni action ;
- canevas Physical Differential, chaîne énergétique, demande de service et commande/feedback ;
- matcher `semantic-v3-blind-fallback` : un apparent non-match structuré et physiquement
  pertinent passe en revue aveugle ; demandes vagues, hors sujet, non discriminantes ou
  déjà répondues seulement en `NO_MATCH` automatique ;
- protection contre une double révélation dans un même cycle ;
- tests synthétiques de principes, d'agenticité, d'anti-hardcoding et d'oracle ajoutés.

### Fichiers modifiés

- `energy_mvp/physical_diagnostics.py`, `energy_mvp/physical_tools.py`,
  `energy_mvp/workflow.py`, `energy_mvp/__init__.py` ;
- `knowledge/physical_diagnostics/` (six familles et README) ;
- `docs/PHYSICAL_DIAGNOSTICS.md`, `docs/ANALYSIS_TOOLS.md`,
  `docs/CLIENT_WORKFLOW.md`, `docs/PHYSICAL_EXPERTISE_BENCHMARK_IMPLEMENTATION.md` ;
- `benchmarking/physical_expertise.py` ;
- tests Candidate V2 et oracle ;
- `reports/CANDIDATE_V2_DIAGNOSTIC_PLAN.md`.

### Tests

- ciblés Candidate V2/oracle/workflow : **51 passed, 1 deselected** ;
- suite presque complète : **170 passed, 1 deselected** ;
- le test HOLDOUT temporairement exclu exige que les nouveaux chemins moteur soient
  d'abord commités, ce qui est précisément le prochain checkpoint.
- corpus oracle indépendant historique : précision **1.0**, rappel automatique **0.923077**,
  2 cas routés en revue aveugle, 0 faux positif automatique.

### Prochaine action

Créer un commit propre de cette implémentation, exécuter la suite complète y compris la
protection HOLDOUT, corriger uniquement les défauts génériques éventuels, puis figer et
taguer Candidate V2 avant l'unique rerun DEV.

## Checkpoint phase 3 — Candidate V2 gelée et campagne DEV démarrée

### Version gelée

- tag analytique : `expert-benchmark-candidate-v2` ;
- commit analytique : `7acc43fc00007af87c459fd60cc89d972515c59a` ;
- empreinte moteur Candidate V2, 42 fichiers :
  `dd2211e2ea0ad26b49c6ec8399dc362282b8be633ae9a3a244908c8bdac53cdd` ;
- baseline V1 toujours inchangée : tag `expert-benchmark-baseline-v1`, commit
  `6ba8ebbdefac68caa3b2debb24f9b141472f0a9d`, empreinte
  `e7261871cd3ff7203bf5cf6bb986bc2102bec00f9c63f63319ead7430084613a`.

### Tests avant campagne

- suite complète : **171 passed** ;
- tests benchmark/oracle : **29 passed** ;
- corpus indépendant du matcher : précision automatique **1.0**, rappel automatique
  **0.923077**, 0 faux positif, 2 routes vers revue aveugle.

### Campagne DEV

- racine privée de campagne :
  `/data/data/com.termux/files/usr/tmp/energy-dev-candidate-v2-7acc43f` ;
- 17 runs valides préparés avec `gpt-5.6-sol`, raisonnement `high` ;
- `case_a17` non préparé et marqué `EXCLUDED_PENDING_CASE_VALIDATION` ;
- `case_b42` terminé et scellé avec intégrité valide : décision
  `INSUFFICIENT_INFORMATION`, 2 demandes, 1 follow-up, coût oracle 2, une revue aveugle
  indépendante ;
- `case_c08` et `case_d31` ont été interrompus avant sortie par la limite d'usage Codex ;
  leurs sessions restent identifiées et seront reprises sans modifier le moteur ni le
  protocole après remise à zéro annoncée à 20:12.

### Incident et prochaine action

L'incident est externe à l'infrastructure et n'a révélé aucune donnée privée. Ne pas
changer de modèle ou de niveau de raisonnement au milieu de la campagne. Reprendre `c08`
et `d31`, poursuivre les 14 autres cas, résoudre chaque revue aveugle dans une session
indépendante, puis sceller/vérifier tous les runs avant les rapports.

## Checkpoint phase 4 — campagne partiellement exécutée, quota externe épuisé

### Runs scellés et vérifiés

- `b42` : `INSUFFICIENT_INFORMATION`, 2 cycles, 2 demandes, 1 follow-up, coût oracle 2,
  1 revue aveugle `MATCH` ;
- `c08` : `INSUFFICIENT_INFORMATION`, 2 cycles, 2 demandes, 0 follow-up, coût oracle 0,
  2 revues aveugles `NO_MATCH` ; durée murale contaminée par la première interruption de
  quota, donc non interprétable comme durée analytique ;
- `d31` : `CAUSE_PROBABLE`, 3 cycles, 3 demandes, 2 follow-ups, coût oracle 2,
  2 revues aveugles `MATCH`, 1 non-match automatique.

Les trois runs ont une empreinte moteur identique à Candidate V2 et `verify` valide leurs
journaux. Les décisions sont non scorées et aucune ground truth n'a été consultée.

### Blocage courant

Les nouvelles sessions `e55` et `f63` ont atteint le quota Codex avant toute demande ou
réponse finale. Elles ont seulement des artefacts de scratch participant et peuvent être
reprises à leurs identifiants d'origine ; elles ne doivent pas être considérées terminées.
Le CLI annonce une disponibilité le **3 septembre 2026 à 20:11**. Aucun changement de
moteur, modèle, raisonnement, prompt participant ou protocole n'est effectué au milieu de
campagne.

### Décision nécessaire avant reprise

Pour préserver une comparaison expérimentale cohérente, choisir explicitement l'une des
options suivantes : attendre/reprendre `gpt-5.6-sol` high après le quota ; ou abandonner
la campagne Candidate V2 actuelle, la conserver comme incident non scoré, et relancer les
17 cas depuis zéro avec un nouveau modèle/niveau de raisonnement déclaré. Un mélange de
modèles ou de niveaux de raisonnement dans les 17 cas invaliderait l'agrégat.

## Checkpoint phase 5 — campagne Sol abandonnée, campagne Terra autorisée

### Décision expérimentale

Le changement de plan a été explicitement autorisé. La campagne partielle
`gpt-5.6-sol` est donc **interrompue et non scorée**. Elle est conservée sans
suppression ni modification à
`/data/data/com.termux/files/usr/tmp/energy-dev-candidate-v2-7acc43f` comme
archive/sanity-check séparé : ses trois runs scellés (`b42`, `c08`, `d31`) ne
seront jamais agrégés avec la nouvelle campagne.

La nouvelle campagne s'appelle **`CANDIDATE_V2_DEV_TERRA`**. Elle utilisera
17 sessions participantes fraîches avec `gpt-5.6-terra`, effort de raisonnement
`high`, le même tag Candidate V2, le même oracle et le même protocole. `a17`
reste explicitement exclu : `EXCLUDED_PENDING_CASE_VALIDATION`.

### Précondition vérifiée

Une sonde Codex éphémère, hors campagne et sans accès aux cas, a démarré avec
succès le 29 août 2026 : `gpt-5.6-terra`, effort `high`, réponse
`TERRA_QUOTA_READY`. Le quota Terra est donc disponible au démarrage. Aucun
run Terra n'a encore été créé à ce checkpoint.

### Prochaine action

Créer le manifeste public de `CANDIDATE_V2_DEV_TERRA`, préparer les 17
workspaces participants isolés et les exécuter sans changer le moteur.


## Checkpoint phase 6 — campagne Terra exécutée

- Les 17 cas valides de `CANDIDATE_V2_DEV_TERRA` sont scellés et vérifiés.
- Tous les participants sont `gpt-5.6-terra`, effort `high`; `a17` est
  `EXCLUDED_PENDING_CASE_VALIDATION`.
- Les runs Sol restent une archive séparée non scorée.
- `pytest -q` après campagne : **171 passed**.

### Prochaine action

Effectuer le contrôle final d'intégrité/empreinte, commiter les rapports de
clôture et publier le checkpoint `READY_FOR_INDEPENDENT_CANDIDATE_V2_SCORING`.


## Checkpoint Candidate V2.1 — frozen epistemic protocol patch

- Commit moteur/protocole : `41ff9d6ab88f7581978ad08210f96f1859c83f14`.
- Commit documentaire de clôture : `e2bace9e032ae3617a71d762903a4893d0038917`.
- Tag : `expert-benchmark-candidate-v2.1`.
- Portée : calibration générique de la conclusion maximale justifiée, sémantique
  des décisions et revue aveugle par intention discriminante principale.
- Aucune campagne DEV V2 n'a été relancée; aucun ground truth n'a été consulté.
- Tests : `pytest -q` **177 passed** ; tests benchmark/oracle **31 passed**.

### Prochaine action

Préparer un HOLDOUT frais, indépendant et jamais utilisé pour mesurer Candidate V2.1.

READY_FOR_FRESH_HOLDOUT

## Checkpoint Goal B.1 — correctif opérationnel-économique

- Portée : contrats Goal B uniquement; aucun chemin analytique V2.1 ni module
  Goal A n'a été modifié.
- Correctifs : handoff pré-raisonnement, calculs reproductibles/provenancés,
  agrégation fail-closed, baselines explicites, effets combinés typés,
  vocabulaire de demandes contrôlé, distinction actions considérées/sélectionnées.
- E2E : `examples/goal_b_1_e2e_case/artisan_sme/` démontre Goal A evidence →
  handoff → contrat Codex → calcul Python → état Goal B.
- Fixtures : `examples/goal_b_1_fixtures.json`, B-A à B-O, testées comme
  contrats structurés; aucune règle de production ne les référence.
- Tests avant freeze : `pytest -q` **205 passed** en 29,35 s; tests Goal B
  spécifiques **17 passed**.
- Vérification métadonnée Goal A : `909196…` est l'objet tag annoté;
  `3c62fdff2a7dedd7c8d75042243933234a1ff78c` est le commit pelé attendu.

### Clôture

- Freeze Goal B.1 : commit et tag `energy-analyzer-operational-economics-goal-b.1`.
- Bundle de revue indépendant :
  `/storage/emulated/0/Download/ENERGY_ANALYZER_GOAL_B_1_REVIEW.zip`.
- Le bundle contient les rapports, tests, fixtures, E2E, diff Git, empreintes,
  provenance Goal A corrigée et logs de test. Aucun secret, ground truth ou
  donnée client réelle n'y est inclus.

READY_FOR_INDEPENDENT_GOAL_B_1_REVIEW

## Checkpoint Goal B.2 — durcissement final de provenance économique

- Portée limitée aux contrats Goal B : provenance numérique exacte, références
  réelles aux findings Goal A, effets combinés validés et handoffs E2E séparés.
- Les générateurs E2E historiques Goal B/B.1 ont été rendus compatibles avec
  le contrat durci sans modifier leurs artefacts historiques.
- Les fixtures B-A à B-O sont désormais testées sur leurs propriétés
  économiques/opérationnelles distinctes, pas seulement sur une décision
  attendue.
- Tests avant freeze : `pytest -q` **204 passed** en 28,87 s ; tests Goal B.2
  ciblés **16 passed**.
- Contrôles adversariaux : valeur-source incohérente rejetée, finding Goal A
  inexistant rejeté, effet économique combiné arbitraire rejeté.
- Candidate V2.1 et Goal A sont restés hors du diff B.2; leurs tags de
  référence restent respectivement `expert-benchmark-candidate-v2.1` et
  `energy-analyzer-client-pipeline-goal-a` (commit pelé Goal A
  `3c62fdff2a7dedd7c8d75042243933234a1ff78c`).

### Prochaine étape autorisée

Revue indépendante du bundle Goal B.2. Goal C n'est pas déclaré prêt ici.

READY_FOR_INDEPENDENT_GOAL_B_2_REVIEW

## Checkpoint Goal B.3 — fermeture finale de provenance

- Portée : validation de références réelles, sans changement Goal A/V2.1 ni
  moteur déterministe de recommandation.
- EconomicInput factuel : source Goal A canonique obligatoire.
- Contrainte factuelle : une ou plusieurs sources Goal A canoniques obligatoires.
- Finding technique : statut/confiance résolus depuis Goal A et non modifiables
  par Goal B.
- `recommendation_provenance` matérialise décision → action → finding →
  calcul → source économique/contrainte.
- L'E2E synthétique utilise les IDs d'artefacts réels de son propre cas.

### Prochaine étape autorisée

Revue indépendante du bundle Goal B.3. Goal C n'est pas déclaré prêt par ce
checkpoint.

READY_FOR_INDEPENDENT_GOAL_B_3_REVIEW

## Checkpoint Goal B.4 — fermeture fonctionnelle finale

- Portée : support strict du vrai `no_finding` Goal A et provenance native des
  réponses obtenues pendant Goal B; aucun changement à Goal A ou Candidate V2.1.
- `findings=[]` autorise `DO_NOTHING` uniquement avec un `no_finding` canonique
  complet, sans action, action considérée ni calcul.
- État Goal B schéma 5 : `goal_b_evidence` persiste les réponses client et
  documentaires, leurs liens aux demandes et leurs valeurs structurées.
- La reprise expose ces preuves à Codex; Python vérifie les références et les
  valeurs mais ne décide ni action ni recommandation.
- Les artefacts Goal A explicitement `IRRELEVANT` ne peuvent pas soutenir
  silencieusement un tarif ou une contrainte factuelle.
- Validation : `pytest -q` **213 passed**; benchmark/oracle **31 passed**;
  opérationnel-économique **25 passed**.
- E2E : `examples/goal_b_4_e2e_case/` trace demande → réponse → preuve Goal B
  → input/contrainte → reprise → calcul → décision.
- Freeze : commit Goal B.4 et tag
  `energy-analyzer-operational-economics-goal-b.4` (provenance Git du bundle).

### Prochaine étape autorisée

Revue indépendante du bundle Goal B.4. Goal C n'est pas déclaré prêt ici.

READY_FOR_INDEPENDENT_GOAL_B_4_REVIEW

## Checkpoint Goal C — Client Decision Delivery

- Portée : couche client indépendante construite au-dessus des états Goal A/B;
  aucun changement de `client_intake_pipeline.py`, `operational_economics.py`
  ou Candidate V2.1.
- `client_delivery.py` sépare le narratif sélectionné par Codex du modèle de
  report, des calculs, de la fidélité des claims et du renderer PDF Python.
- Les décisions, chiffres, fourchettes, contraintes et alternatives restent
  fidèles aux artefacts Goal A/B. Les nombres libres dans le narratif sont
  refusés pour éviter les claims inventés.
- E2E : action recommandée + alternative non cumulative + contrainte + chart;
  rapport no-finding séparé avec `DO_NOTHING` réel.
- Validation : `pytest -q` **220 passed**; PDF principal 5 pages; PDF
  no-finding 4 pages; absence d'IDs internes et chemins locaux vérifiée.

### Prochaine étape autorisée

Revue indépendante du bundle Goal C. Aucun goal ultérieur n'est déclaré prêt.

READY_FOR_INDEPENDENT_GOAL_C_REVIEW
