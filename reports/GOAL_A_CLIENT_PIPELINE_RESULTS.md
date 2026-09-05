# Goal A — résultats du pipeline client

## Architecture livrée

La nouvelle couche hors moteur analytique gelé est client_intake_pipeline.py avec la CLI intake_client_case.py. Elle crée un cas client isolé, copie les originaux sans les modifier, inventorie les artefacts, inspecte les CSV/XLSX feuille par feuille, extrait les tables, normalise uniquement les transformations sûres, construit une provenance machine-readable et prépare un cas canonique pour Codex.

Elle ne produit jamais un diagnostic, une cause, une recommandation ou une question client à partir de règles. Le handoff explicite donne à Codex les jeux normalisés qu’il peut choisir d’explorer avec l’outillage existant.

## Résultat E2E : messy-client drop synthétique

Fixture : examples/goal_a_messy_client_drop/.
Cas généré : examples/goal_a_e2e_case/messy_shop/.

- 6 fichiers hétérogènes inventoriés : XLSX multi-feuilles, deux CSV, planning, note tarifaire et fichier marketing ;
- 3 datasets extraits : énergie exploitable, série énergie sans unité matériellement ambiguë et production contexte ;
- la feuille utile a été trouvée hors feuille 1 après lignes décoratives ;
- virgules décimales, TOTAL et doublon strict ont été tracés ;
- aucune correction de la seconde série ambiguë : elle reste hors calcul énergétique ;
- le paquet canonique, le résumé qualité, la provenance, le handoff et le brief Codex sont présents ;
- un seul exemple de question simple, contextualisée et non bloquante est enregistré ;
- l’exemple final est un no-finding structuré : période trop courte, aucune anomalie inventée.

## Exemples d’artefacts

- Inventaire : examples/goal_a_e2e_case/messy_shop/evidence/intake_inventory.json
- Cas normalisé : examples/goal_a_e2e_case/messy_shop/derived/canonical_case.json
- Provenance : examples/goal_a_e2e_case/messy_shop/evidence/dataset_provenance.json
- Question batch : examples/goal_a_e2e_case/messy_shop/investigation/question_batch.json
- No-finding : examples/goal_a_e2e_case/messy_shop/investigation/structured_findings.json

## Tests

Les 11 tests Goal A couvrent les cas A–J de la spécification ainsi que l’immuabilité des réponses et l’exception de second batch. Ils s’ajoutent à la suite existante. Le résultat final est consigné dans le bundle.

## Limites avant un premier pilote supervisé

- Les fichiers XLS legacy sont inventoriés mais exigent encore conversion ou une dépendance optionnelle de lecture.
- Les PDF sont classés/inventoriés, sans extraction OCR ou analyse de tableaux PDF.
- L’inférence d’unité reste volontairement conservatrice ; toute interprétation décisionnelle concurrente est bloquée.
- Le premier passage reste réalisé par Codex : ce dépôt prépare son contexte, il ne lance pas un LLM ni ne remplace la revue humaine.
- Une politique juridique de rétention, le chiffrement au repos et les procédures d’effacement client restent à formaliser.
- Goal B devra traiter économie opérationnelle et validation de valeur ; Goal C le rapport client, la livraison et le monitoring.
