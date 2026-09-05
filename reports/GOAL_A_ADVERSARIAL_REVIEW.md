# Goal A — revue contradictoire

## Conclusion

La couche Goal A améliore les opérations autour de Codex sans transformer le produit en moteur expert à règles. Les risques ci-dessous restent explicitement visibles.

## Contrôles adversariaux

- Questions excessives : contrôlé par zéro question par défaut, batch 1–3, second batch justifié.
- Raisonnement coûteux sur détail banal : contrôlé par parsing/inférences ordinaires déterministes ; seules ambiguïtés matérielles remontent.
- Corruption silencieuse : transformations AUTO_FIX_SAFE, FLAG_ONLY, MATERIAL_AMBIGUITY journalisées.
- Inférence d’unité trop confiante : unité explicite ou contexte régulier cohérent ; sinon blocage matériel.
- Sous-usage de données rares : un meter seul reste handoff exploitable si l’unité est défendable.
- Client transformé en technicien : séparation ASK_CLIENT, document existant, evidence technique et instrumentation.
- Diagnostic fixe accidentel : absent ; aucun mapping symptôme vers cause dans le code intake.
- Gaps de provenance : ART vers DS vers table/feuille/colonne/transformation.
- Échec no-finding : contrat structured_findings avec no_finding.
- Termux : acceptable ; Python stdlib et openpyxl déjà requis, aucun service, Docker ou modèle local ajouté.

## Risques résiduels

1. Une feuille Excel très exotique, des cellules fusionnées complexes ou un XLS ancien peuvent rester non lisibles : le système doit les déclarer partiellement utilisables plutôt que deviner.
2. Le classement documentaire fondé sur structure, en-têtes et nom de fichier peut rester UNKNOWN ; ce n’est pas une erreur.
3. Un court jeu de données peut appuyer une observation forte, mais ne rend pas une cause physique automatique : Codex doit encore mener le différentiel.
4. Un dossier peut contenir des informations personnelles dans les notes. Le pipeline n’envoie rien, mais les pratiques de rétention et d’accès doivent être établies avant pilote.

## Audit d’agenticité

1. Codex décide les preuves importantes : oui.
2. Codex décide quoi investiguer : oui.
3. Codex formule et compare les hypothèses : oui.
4. Codex décide si l’incertitude est matérielle : oui ; le code expose des ambiguïtés de mesure mais ne choisit pas leur impact métier.
5. Codex décide si une question est nécessaire : oui ; l’API ne fait que valider un batch déjà formulé.
6. Codex formule la demande : oui.
7. Les outils déterministes lisent, normalisent, tracent et calculent : oui.
8. Un moteur diagnostic à règles est-il apparu : non.
9. Sans Codex, le code produirait-il sensiblement la même investigation : non.

La séparation Candidate V2.1 a été vérifiée : aucun chemin analytique protégé n’a changé depuis le tag gelé.
