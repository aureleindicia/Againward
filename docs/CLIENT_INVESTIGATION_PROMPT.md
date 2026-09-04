# Prompt standard de production — dossier client INDICIA

Copier le bloc et remplacer `<CHEMIN_DOSSIER_CLIENT>` si connu. Ce n'est pas un `/goal`.

```text
Utilise la skill $indicia-client-workflow et travaille dans le dépôt courant INDICIA / Energy Analyzer.

Reconstruis le contexte sans mémoire conversationnelle depuis l'intégralité du dépôt courant et tout `/storage/emulated/0/Download`. Les objectifs, handoffs, R&D, benchmarks et pièces client peuvent être répartis entre ces emplacements. Le dépôt courant est la source de vérité du code; Download sert de contexte et d'entrée locale. Ne suppose pas qu'un ancien clone de Download est plus récent et ne versionne pas les données client.

Dossier client : <CHEMIN_DOSSIER_CLIENT>. Si le placeholder subsiste, localise le dossier pertinent dans le dépôt et Download; ne demande le chemin que si le mauvais choix reste un risque réel.

Détermine le mode depuis les artefacts : INITIAL, ou REPRISE si investigation_state.json.client_lifecycle.state vaut RESUMING.

INITIAL : analyse exhaustivement toutes les données et documents existants avant toute demande; trace les sources examinées. Conduis observations, hypothèses concurrentes, tests Python, falsification, quantification, décision et review adversariale. Préserve strictement détection → signature reproductible → composant anonyme → compatibilité → attribution → mécanisme physique → pronostic. Utilise l'intégration MinimalEvidenceAttribution/EvidenceLedger si applicable, sinon consigne not_applicable.

Ne demande rien qui serait seulement intéressant. Rassemble toutes les demandes candidates Goal A, attribution et Goal B et utilise le sélecteur canonique global. Chaque demande doit avoir des réponses plausibles modifiant matériellement preuve, attribution, hypothèse concurrente, économie, priorité, action ou risque de fausse conclusion. Zéro question par défaut, trois au plus par cycle, deux cycles au plus. Préfère inférence locale, micro-question, document existant, observation ponctuelle, vérification terrain, export, puis instrumentation. Écris pour une personne connaissant le site sans expertise data science et précise ce que la demande confirme, infirme ou départage.

Si une demande BLOCKING est publiée, présente uniquement la demande ciblée et son utilité, persiste WAITING_FOR_REQUIRED_INFORMATION, puis ARRÊTE COMPLÈTEMENT. N'invente aucune réponse, ne promeus pas les hypothèses suspendues, ne finalise pas leur économie/action et ne génère pas le rapport.

REPRISE : relis questions.json, investigation_state.json et les ledgers. Pour chaque réponse, vérifie demande exacte, auteur/rôle, date, provenance, source, contradiction/correction. Une absence n'est jamais une confirmation. Une CLIENT_DECLARATION ou un EXISTING_DOCUMENT n'est pas une validation terrain. Mets à jour l'EvidenceLedger, recalcule avec Python, réexamine alternatives, attribution, confiance, économie, priorité/action, trace avant/après et refais la review. Ferme via le lifecycle. N'ouvre un second cycle que pour une branche décisionnelle matérielle nouvelle; ne repose jamais un équivalent.

Sans information justifiant l'effort, ou après deux cycles, finalise honnêtement avec le niveau atteint : unknown, non identifiable, cause non démontrée ou information insuffisante. Marque FINALIZABLE avant rapport et respecte la revue humaine avant DELIVERABLE.

N'utilise aucune architecture parallèle : questions.json et investigation_state.json.client_lifecycle sont canoniques. Conserve le dépôt local-first, propre, testé et reproductible. Si tu attends une réponse, dis-le explicitement et fais-en la dernière action de la session.
```
