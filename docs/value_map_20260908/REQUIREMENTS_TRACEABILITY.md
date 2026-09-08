# Traçabilité du périmètre demandé

Les preuves ci-dessous concernent les contrats logiciels et leurs protections. Aucune ne constitue une preuve de valeur commerciale réelle.

| Bloc | Implémentation et vérification |
|---|---|
| A–B : valeur non réduite à l’énergie, cinq catégories | `value_map.CATEGORIES`, `_record`, `build_value_map` ; catégories séparées, calculs Goal B conservés ; exemples C-A/C-E/C-H |
| B1 : bases énergétiques et LOW/BASE/HIGH | `validate_energy_effect` existant, `energy_observation` dans `_record`, `resolve_quantity`, effets repris des calculs revalidés ; test énergie historique sans économies automatiques |
| B2 : économie directe et coûts | calculs `operational_economics` conservés, `direct_economic_value` et `capture_costs_and_constraints` ; suite économique existante et tests de provenance/portefeuille |
| C–D : investigation et champ de recherche | `INVESTIGATION_FIELDS`, partition des hypothèses et `hypothesis_counts` ; UNKNOWN distinct d’ensemble vide ; test de réduction sans proportion de coût |
| E–F : heures et euros | `_time`, `_rate`, mesures Goal B / ScenarioAssumption ; tests heures documentées, taux absent/invalide/sourcé, scénario et nombres non finis |
| G : fausses pistes et interventions | `_avoided`, `_rate_cost`, contrefactuel dans `_record` ; action possible/documentée, coût nul inconnu sans source ; tests de réfutation et coût insuffisamment étayé |
| H : décision sans prix | `DECISION_FIELDS`, délais sourcés et accélération calculée ; tests décision sans argent et DO_NOTHING |
| I : information | extension de `validate_decision.evidence_acquisition`, résolution d’`acquisition_cost` dans `build_value_map`, projection `information_value` ; test réutilisation de l’input existant |
| J : discipline contrefactuelle | bases, statuts, confiance indépendante, scénario propagé, UNKNOWN non monétisable ; tests contrefactuel inconnu et scénario déguisé en temps documenté |
| K : réalisation | `_post_action`, `pre_action_ref`, `validate_append_only`, protection des projections passées dans `persist_economic_packet`, snapshots ; tests sources post-action et refus de réécriture |
| L–M : non-additivité / absence de ROI artificiel | relations existantes réutilisées ; `total_value=null`, aucun input total libre, relation énergie/argent intrinsèque, total PDF revalidé ; tests des six types, falsifications et recouvrements |
| N : artefact | persistance de `investigation/value_map.json` depuis le même état canonique ; tous les groupes demandés, limitations et provenance |
| O : client | `client_value_section`, intégration et revalidation dans `client_delivery`, rendu réel des trois PDF synthétiques ; textes de scénario et de contrefactuel explicites |
| P : revue pilote | `build_pilot_learning_review`, `render_pilot_learning_review`, exemples Markdown/JSON ; utilité/nouveauté/contribution explicitement annotées ou inconnues |
| Q : métriques futures | `export_authorized_pilot_metrics`, `aggregate_pilot_metrics`, schéma fermé, identifiants opaques, bases séparées, dénominateurs ; tests autorisation, inconnus, doublons et texte client interdit |
| R : provenance | `_provenance`, `_context`, `resolve_quantity`, validateurs économiques existants ; références typées, nombres référencés, refus d’injection de faux evidence dans un packet |
| S : confiance | quatre champs indépendants et NOT_CALIBRATED par défaut dans `_record` ; aucune formule transférant une confiance technique à l’économie |
| T : décisions | ensemble `DECISIONS` existant inchangé ; DO_NOTHING supporte une valeur d’investigation ; aucune détection automatique d’échec commercial |
| U : architecture | `value_assessment` étend l’état économique et son handoff ; pas de moteur de recommandation ; Python valide/calcul/représente, l’agent fournit les jugements sourcés |
| V : vingt validations | correspondance détaillée dans `COMPLETION_AUDIT.md` et résultats dans `VALIDATION_RESULTS.json` |
| W : documentation et trois exemples | `docs/VALUE_MAP.md`, générateur `workspace/generate_value_map_examples.py` ; chaque exemple expose les interdictions d’addition |
| X : livraison du code | commits, suite ciblée puis globale sur code committé, audit des seize réponses, diffusion GitHub demandée séparément par l’utilisateur |

## Préservation des frontières

Le diff par rapport à `1b799ff` ne modifie aucun détecteur, benchmark, ground truth ou module Evidence Plane. L’unique extension de `energy_mvp/case_lifecycle.py` lie la revue humaine existante à l’empreinte de la nouvelle Value Map : nécessaire pour éviter qu’un résultat ajouté ultérieurement bénéficie d’une ancienne approbation. Les tests globaux vérifient également les gates existants.
