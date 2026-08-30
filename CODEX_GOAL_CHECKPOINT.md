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
