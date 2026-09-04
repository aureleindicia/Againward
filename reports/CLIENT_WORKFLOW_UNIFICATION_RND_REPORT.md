# Rapport R&D — workflow client unifié

Le code unifie lifecycle et questions autour de `client_lifecycle`, `client_requests` et
`questions.json`. Il impose les cinq états, STOP BLOCKING, deux cycles/trois demandes, provenance
typée, reprise avec recalcul/review/avant-après et finalisation honnête.

`attribution_workflow` active MEA conditionnellement (`not_applicable` valide), utilise
`guarded_evidence`, persiste EvidenceLedger et recalcule après réponse. Déclaration/document ne sont
pas des ancres. Détection, signature, composant, compatibilité, attribution, mécanisme et pronostic
restent séparés.

Falsifications : faible valeur, doublon, export/instrumentation contre micro-question, batch mixte,
réponse absente/contradictoire, troisième cycle, état incohérent, surconfiance opérateur et reprise
nouvelle instance. 27 tests dédiés dont deux E2E synthétiques. Le benchmark 10/100/1000 est dans
`benchmarks/client_workflow/RESULTS.json`.

Limites : aucun pilote réel, VOI/fiabilité non calibrées terrain, compréhension linguistique relue
par Codex/humain, compatibilité non probabiliste, attribution mécanique non démontrée sans terrain.
