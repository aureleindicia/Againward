# Preuves par exigence — spécification de mission finale

La spécification autoritative est `AGAINWARD_FINAL_CLIENT_MISSION_GOAL.md`, lue
intégralement depuis Download. Les références ci-dessous désignent le code nominal,
les tests exécutables et les artefacts synthétiques ; elles ne constituent pas une
validation commerciale ni un avis juridique.

| Exigence | Autorité / preuve concrète | Portée et limite |
|---|---|---|
| Audit préalable et réutilisation | ARCHITECTURE_AUDIT.md ; baseline 82dcb54, 491 tests | Inventaire EXISTING/PARTIAL/MISSING/REDUNDANT avant extension |
| A : accord avant données | privacy.stage_incoming_drop ; contract_policy.assert_contract_permission ; tests/test_contract_policy.py | Les entrées supportées échouent avant copie ; une copie manuelle hors API reste physiquement possible |
| B : policy canonique | contract_policy.py, template fermé, permissions tri-state | UNKNOWN conservé ; sources et dates vérifiées |
| C : extraction Codex / humain | record_contract_policy, reviewed_contract_policy | Projection minimale ; aucune qualification juridique automatique ; hash des sources sans réinterprétation sémantique |
| D : gates et traces existants | privacy.py, workflow_paths.py, case_lifecycle.py | Aucun nouveau lifecycle ; autorisation historique dans privacy manifest |
| E–F : conception / production PDF par agent | report_design.py ; deliver_client_report.py --design ; quatre plans authored | L’agent choisit pages, positions, ordre, taille et emphase ; Python sérialise les choix locaux |
| G : liberté factuelle interdite | client_delivery.validate_client_report_model ; report_design.content_catalog | Références et chiffres revalidés ; vérité sémantique du texte reste contrôlée par agent et humain |
| H–I : composition / composants | REPORT_DESIGN_SYSTEM.md ; REPORT_DESIGN_MODEL des exemples | Quinze catégories de composants ; aucune sélection déterministe des findings ou des pages |
| J–L : identité / lisibilité / longueur | Quatre PDF exemples ; VISUAL_REVIEW.md | Deux, trois et cinq pages adaptées à la matière synthétique ; pas de remplissage |
| M : finding client | Claims observation, importance, contexte, incertitude ; décisions résolues et contraintes obligatoirement visibles | Les exemples explicitent alternatives et implications ; l’humain vérifie que la sélection raconte correctement le cas |
| N–O : graphiques | _safe_chart ; _resolve_chart_requests ; test_chart_pixels_sources_findings_and_method_must_be_reproducible ; test_display_reduction_preserves_a_short_peak | Source, finding, méthode, unités, période et pixels recalculés ; enveloppe min/max préserve les pics ; pas de causalité déduite |
| P : économie et Value Map | content_catalog appelle build_value_map ; modèle économique validé avant rendu | Aucun total hétérogène ; renderer ne refait pas les scénarios |
| Q : delivery et approbation | case_lifecycle.evaluate_delivery_gate ; validate_report_delivery_artifacts ; test_existing_delivery_gate_accepts_only_current_semantic_and_visual_review | Approbation humaine exacte + revue visuelle + reproduction PDF ; contenu changé invalide, esthétique conserve hash |
| R : revue visuelle réelle | REPORT_VISUAL_REVIEW.json liés aux SHA PDF ; VISUAL_REVIEW.md | Inspection raster de toutes les pages, correction et réinspection ; aucune human approval inventée |
| S : report.md | Conservé par lifecycle ; aucune lecture du Markdown pour imposer la composition | PDF nominal distinct ; ancien renderer seulement compatibilité fixtures |
| T–X : post-mortem scientifique | pilot_learning._scientific_review, persist_pilot_learning_review ; tests/test_scientific_pilot_learning.py | Vingt sections, trois questions, cinq verdicts, sept types d’énoncés ; métriques résolues et UNKNOWN explicite |
| Y : confidentialité du learning | TEMPORARY_CONFIDENTIAL ; test_full_confidential_review_is_purged_only_approved_whitelist_survives | Revue dans le dossier client ; pas d’export automatique du Markdown |
| Z–AC : dérivé, finalité, réidentification | create_retention_candidate ; validate_retained_learning_projection ; approve_retention_candidate ; privacy._retained_derived_allowed | CSV à whitelist fermée, métriques en plages, droit de finalité et revue LOW liée au hash ; ce n’est pas une anonymisation juridique |
| AD : clôture / purge | mission-close ; configure_retention ; purge_client_case ; tests privacy + scientific | Date contractuelle, refus mission ouverte, revalidation des retenus, suppression de la revue complète, tombstones minimaux |
| AE : tests | Tableau détaillé ci-dessous ; VALIDATION_RESULTS.json | Tests nouveaux + non-régression globale, sans modification des critères de scoring |
| AF–AG : quatre PDF et qualité | examples/final_client_mission_reports/MANIFEST.json ; VISUAL_REVIEW.md | Quatre histoires éditoriales inspectées, pas quatre pilotes terrain |
| AH : limites | Contrats existants findings/OE/Value Map, tests de renforcement interdit et prose revue | L’esthétique n’augmente ni le niveau de preuve ni la récupérabilité |
| AI : audit final | COMPLETION_AUDIT.md ; résultats ; Git | Points un à onze répondus explicitement |

## Tests AE, un par un

Les noms courts ci-dessous se trouvent dans `tests/`. Les tests existants restent
inchangés dans leurs assertions, à l’exception de la précondition contractuelle
ajoutée aux fixtures REAL_CLIENT et des assertions de rétention désormais explicite.

| AE | Preuve exécutable |
|---|---|
| 1 | test_contract_policy.test_first_real_drop_fails_before_copy_without_agreement |
| 2 | test_active_agreement_without_processing_permission_is_blocked[False] |
| 3 | même test [None], conservation du null relue sur disque |
| 4 | test_ambiguous_clause_requires_review |
| 5 | test_authorized_staging_traces_policy_not_raw_agreement ; test_raw_fields_not_allowed_and_direct_privacy_promotion_blocked |
| 6 | test_report_design.test_agent_composition_changes_geometry_not_semantic_hash |
| 7 | test_design_cannot_introduce_or_strengthen_claims[free_number] ; test_editorial_heading_is_sourced_and_substantive |
| 8 | même test [unknown_finding] et [unknown_ref] |
| 9 | même test [verified_saving] ; tests client_delivery existants |
| 10 | test_chart_pixels_sources_findings_and_method_must_be_reproducible |
| 11 | même test, mutation de méthode et de bytes ; test_receipt_cannot_launder_an_arbitrary_pdf |
| 12 | validation client_delivery du total vs portefeuille ; tests Value Map d’overlap et non-addition conservés |
| 13 | test_substantive_content_change_invalidates_human_review ; test_existing_delivery_gate_accepts_only_current_semantic_and_visual_review |
| 14 | test_agent_composition_changes_geometry_not_semantic_hash ; retouche et nouvelle revue visuelle dans le test du gate complet |
| 15 | test_agent_composition_changes_geometry_not_semantic_hash vérifie bytes %PDF ; quatre PDF réels inspectés |
| 16 | tests/test_scientific_pilot_learning.py : persist et rendu des vingt sections |
| 17 | même suite : statut TEMPORARY_CONFIDENTIAL explicite |
| 18 | même suite : purge du dossier réel autorisé et absence du post-mortem complet après purge |
| 19 | même suite : rejet Markdown et schéma CSV libre |
| 20 | même suite : droits contractuels distincts de l’autorisation technique |
| 21 | même suite : hash/revue LOW ; test_privacy_gate : dimensions interdites et réidentification |
| 22 | même suite : refus d’export de métriques et de candidat sans R&D autorisée |
| 23 | tests/test_pilot_learning.py conservés |
| 24 | tests/test_value_map.py ; contenu client issu de client_value_section et revalidation build_value_map |
| 25 | suites operational_economics et economic associées dans la suite globale |
| 26 | tests/test_value_map.py |
| 27 | tests/test_pilot_learning.py et nouveaux tests scientifiques |
| 28 | tests/test_privacy_gate.py ; benchmark privacy jusqu’à cinq cent mille lignes |
| 29 | tests/test_case_lifecycle.py, test_client_workflow_unification.py, test_workflow_paths.py |
| 30 | suites Evidence Plane existantes, sans modification de leurs assertions |
| 31 | tests/test_client_delivery.py et tests/test_report_design.py |
| 32 | python -m pytest -q ; journal et résultat copiés dans VALIDATION_RESULTS.json |

## Frontière de preuve

Un test qui enregistre une attestation fictionnelle teste un gate ; il ne produit
pas une revue humaine réelle. Les attestations visuelles des exemples sont celles
réellement effectuées par Codex. Le dossier d’exemples ne prétend jamais être
DELIVERABLE pour un client. Les fixtures Goal A/B ne sont ni une nouvelle ground
truth industrielle ni une mesure de recall.
