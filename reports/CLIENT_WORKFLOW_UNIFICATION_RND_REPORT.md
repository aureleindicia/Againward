# Rapport R&D — workflow client unifié

Le code unifie lifecycle et questions autour de `client_lifecycle`, `client_requests` et
`questions.json`. Il impose les cinq états, STOP BLOCKING, deux cycles/trois demandes, provenance
typée, reprise avec recalcul/review/avant-après et finalisation honnête.

`attribution_workflow` active MEA conditionnellement (`not_applicable` valide), utilise
`guarded_evidence`, persiste EvidenceLedger et recalcule après réponse. Déclaration/document ne sont
pas des ancres. Détection, signature, composant, compatibilité, attribution, mécanisme et pronostic
restent séparés.

Falsifications : faible valeur, doublon, export/instrumentation contre micro-question, micro-question
surévaluée par son seul type, batch mixte,
réponse absente/contradictoire, troisième cycle, état incohérent, surconfiance opérateur et reprise
nouvelle instance. Les états valides mais incohérents, les budgets falsifiés et les divergences
lifecycle/questions échouent désormais aussi de manière sûre. La validation ciblée compte 39 tests,
dont deux E2E synthétiques; la suite complète passe à 350 tests. Le benchmark 10/100/1000 est dans
`benchmarks/client_workflow/RESULTS.json`.

Le seuil VOI de production est explicite (`0.05`) : la valeur ajustée par disponibilité, fiabilité,
effort et coût précède la préférence de type de source. Ce seuil est conservateur et reste à
calibrer sur plusieurs pilotes, jamais sur un cas unique.

L'organisation ajoutée reconnaît workspace standard, cas Goal A et dossier direct avec un seul
propriétaire d'artefacts. La commande `manage_investigation.py status` est en lecture seule. Les
nouveaux workspaces ne créent plus de copies concurrentes de questions/revue et `workspaces/*` est
privé par défaut pour une future publication GitHub.

Limites : aucun pilote réel, VOI/fiabilité non calibrées terrain, compréhension linguistique relue
par Codex/humain, compatibilité non probabiliste, attribution mécanique non démontrée sans terrain.
