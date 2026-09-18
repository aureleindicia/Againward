# Vérification du Goal Domain Kernel / Rental

Cette matrice relie les 22 critères de fin du document demandé aux implémentations
et aux preuves vérifiables. Les tests ne démontrent pas la qualité sémantique de
toute future interprétation documentaire ; cette responsabilité reste à l'analyste.

| Critère | Implémentation / preuve |
|---|---|
| 1. Mécanismes communs séparés | `againward/core`, test AST et imports transitifs dans `test_domain_boundaries.py` |
| 2. Evidence neutre | `evidence/dataset.py`, v2 typé, hashes et provenance ; `test_generic_evidence.py` |
| 3. Contrat explicite | `core/domain.py` et `entrypoints.py`, rejet du domaine inconnu |
| 4. Energy utilise le noyau | Wrapper `energy_mvp/workflow.py` → `EnergyDomainPack` → `core/workflow.py` ; `test_domain_routing.py` |
| 5. Régressions Energy | Fixtures SHA-256 JSON/Markdown/v1, suite Energy complète conservée |
| 6. Rental générique | Modèle sans classe d'engin obligatoire ; `models.py`, fixtures d'actifs génériques |
| 7. Construction est un profil | `profiles/construction.py` ; test d'identité des ledgers et du dataset entre profils |
| 8. Ingestion représentative | Canonique, textes sourcés, mapping CSV et XLSX ; `test_rental_ingestion.py`, `test_rental_adversarial.py` |
| 9. Expected ledger | `pricing.py` ; calendrier, minimum, remises, frais et dépendances en tests |
| 10. Actual ledger | `reconciliation.py` ; avoirs émis/promis, devises, identités et surallocations testés |
| 11. Investigation | Assessments explicites, alternatives, review, abstention ; `test_rental_workflow.py` |
| 12. Provenance | Source → extraction → ligne/groupe → finding → requête matérialisée ; hashes revalidés à la livraison |
| 13. Familles initiales | Registre `FINDING_FAMILIES`, candidats utiles et limites décrites dans `RENTAL.md` |
| 14. Résistance aux faux positifs | Sept variantes adversariales ; `benchmarks/rental/validation.json` |
| 15. R06 WAIT/RESUME | `benchmarking/rental.py::exercise_resume` ; nouveau lot privacy aussi testé dans un workspace REAL_CLIENT de test |
| 16. Double comptage | Un montant par groupe, plusieurs familles ; L3 agrégé une fois ; test dédié |
| 17. Privacy | Post-check commun, politiques injectées, JSON métier préservé, nouveaux lots soumis à une nouvelle clearance |
| 18. Documentation | `ARCHITECTURE.md`, `RENTAL.md`, `RENTAL_BENCHMARKS.md`, README et catalogue d'outils |
| 19. Suite complète | Exécution en worktree immuable, résultats finaux dans `DOMAIN_KERNEL_MIGRATION.md` |
| 20. Commits incrémentaux | Historique `main..refactor/domain-kernel`, étapes extraction/adaptation/Rental/benchmarks/corrections/docs |
| 21. Branche distante | `git ls-remote origin refs/heads/refactor/domain-kernel`, vérifié après push final |
| 22. Main préservé | Main local et distant à `c27f261`, travail prospecting initial laissé dans son worktree ; PR sans merge |

Le benchmark mesure les mécanismes et les montants sur 13 cas explicites. Il ne
prétend pas généraliser une précision parfaite à des contrats inconnus. Le modèle
ne livre ni OCR/PDF automatique, ni fiscalité/FX, ni ventilation automatique des
retours partiels. Les données insuffisantes restent inconnues. Les tests de revue
utilisent des fixtures identifiées comme synthétiques ; aucune approbation réelle
ni créance juridiquement garantie n'est fabriquée.
