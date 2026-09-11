import copy
import json
import pytest
from tests.test_value_map import case_packet, save, time_record
from pilot_learning import (POST_MORTEM_SECTIONS, MANDATORY_QUESTIONS, SIMPLICITY_DIMENSIONS,
    build_pilot_learning_review, persist_pilot_learning_review, render_pilot_learning_review)


def post_mortem():
    unknown={'statement_type':'INCONNU','text':'Les preuves actuelles ne permettent pas de trancher.'}
    observed={'statement_type':'FAIT_OBSERVE','text':'Le journal du pilote documente cette comparaison.',
              'source_refs':['GBE-V']}
    counterfactual={key:{'outcome':'INCONCLUSIVE','evidence':[copy.deepcopy(observed)]} for key in (
        'raw_plus_python','tool_value','workflow_friction','deterministic_python',
        'architecture_rationalization','unique_againward_capability',
        'architecture_workarounds','minimal_design')}
    counterfactual['dimensions']={key:{'outcome':'INCONCLUSIVE','evidence':[copy.deepcopy(observed)]}
                                  for key in SIMPLICITY_DIMENSIONS}
    counterfactual['verdict']={'classification':'INCONCLUSIVE','rationale':[copy.deepcopy(observed)]}
    return {'sections':{key:[copy.deepcopy(unknown)] for key in POST_MORTEM_SECTIONS},
        'mandatory_answers':{key:copy.deepcopy(unknown) for key in MANDATORY_QUESTIONS},
        'simplicity_counterfactual':counterfactual,
        'contribution_dimensions':['UNKNOWN'],
        'verdict':{'classification':'NEUTRE',**{key:[copy.deepcopy(unknown)] for key in
            ('arguments_for','arguments_against','new_elements','known_elements','generalization_limits')}}}


def test_complete_internal_review_is_confidential_and_preserves_unknown(case_packet):
    case,p=case_packet;save(case,p,time_record())
    review=persist_pilot_learning_review(case,{'post_mortem':post_mortem()})
    assert review['classification']=='TEMPORARY_CONFIDENTIAL'
    text=(case/'investigation/PILOT_LEARNING_REVIEW.md').read_text()
    assert 'TEMPORARY_CONFIDENTIAL' in text and 'Verdict : NEUTRE' in text
    for question in MANDATORY_QUESTIONS.values():assert question in text
    assert not review['scientific_post_mortem']['general_validation_demonstrated']


def test_calculated_result_requires_existing_metric_not_free_number(case_packet):
    case,p=case_packet;save(case,p,time_record());post=post_mortem()
    post['sections']['value_produced']=[{'statement_type':'RESULTAT_CALCULE','text':'Temps potentiellement évité selon la déclaration.',
        'metric_ref':'client_hours_potentially_avoided'}]
    assessment={'investigation_value_ref':'V1','post_mortem':post}
    review=build_pilot_learning_review(case,assessment)
    item=review['scientific_post_mortem']['sections']['value_produced'][0]
    assert item['resolved_metric']['value']==8
    post['sections']['value_produced'][0]['text']='Valeur inventée de 999 euros.'
    with pytest.raises(ValueError,match='qualitatif'):build_pilot_learning_review(case,assessment)


def test_no_automatic_verdict_or_complete_review_from_missing_sections(case_packet):
    case,p=case_packet;save(case,p,time_record());post=post_mortem();post['sections'].pop('falsification')
    with pytest.raises(ValueError,match='vingt'):persist_pilot_learning_review(case,{'post_mortem':post})
    with pytest.raises(ValueError,match='post-mortem final'):persist_pilot_learning_review(case,{})
    assert not (case/'investigation/PILOT_LEARNING_REVIEW.md').exists()


def test_simplicity_counterfactual_requires_all_axes_evidence_and_closed_verdict(case_packet):
    case,p=case_packet;save(case,p,time_record());post=post_mortem()
    post.pop('simplicity_counterfactual')
    with pytest.raises(ValueError,match='comparaison de simplicité'):persist_pilot_learning_review(case,{'post_mortem':post})
    post=post_mortem();counter=post['simplicity_counterfactual']
    counter['tool_value']['evidence']=[{'statement_type':'INCONNU','text':'Les preuves actuelles ne permettent pas de trancher.'}]
    with pytest.raises(ValueError,match='seulement INCONNU'):persist_pilot_learning_review(case,{'post_mortem':post})
    post=post_mortem();counter=post['simplicity_counterfactual']
    counter['tool_value'].pop('outcome')
    with pytest.raises(ValueError,match='résultat fermé'):persist_pilot_learning_review(case,{'post_mortem':post})
    post=post_mortem();counter=post['simplicity_counterfactual']
    counter['verdict']['classification']='Againward semble meilleur'
    with pytest.raises(ValueError,match='Verdict fermé'):persist_pilot_learning_review(case,{'post_mortem':post})


def test_simplicity_counterfactual_is_rendered_by_dimension(case_packet):
    case,p=case_packet;save(case,p,time_record());review=persist_pilot_learning_review(case,{'post_mortem':post_mortem()})
    counter=review['scientific_post_mortem']['simplicity_counterfactual']
    assert counter['verdict']['classification']=='INCONCLUSIVE'
    text=render_pilot_learning_review(review)
    assert 'Comparaison contrefactuelle de simplicité' in text
    assert 'raw_plus_python'.replace('_',' ') not in text
    assert 'Dimensions comparées' in text and 'final_client_value : INCONCLUSIVE' in text


def test_retained_markdown_or_precise_industrial_data_is_rejected(case_packet):
    from pilot_learning import create_retention_candidate, validate_retained_learning_projection
    case,p=case_packet;save(case,p,time_record());review=build_pilot_learning_review(case,{'investigation_value_ref':'V1'})
    candidate=create_retention_candidate(case,review)
    path=case/candidate['path'];row=validate_retained_learning_projection(path)
    assert row['client_hours_potentially_avoided']=='LT_10'
    assert 'GBE' not in path.read_text() and str(case) not in path.read_text()
    markdown=case/'retained_derived/review.md';markdown.write_text('An allegedly anonymous report')
    with pytest.raises(ValueError,match='Markdown'):validate_retained_learning_projection(markdown)
    path.write_text(path.read_text().replace('LT_10','8.0001'))
    with pytest.raises(ValueError,match='précise'):validate_retained_learning_projection(path)


def test_low_risk_human_review_is_required_for_retention(case_packet):
    from pilot_learning import create_retention_candidate, approve_retention_candidate
    case,p=case_packet;save(case,p,time_record());review=build_pilot_learning_review(case,{})
    candidate=create_retention_candidate(case,review)
    human={key:True for key in ('approved_for_long_term_retention','site_identity_removed',
        'unique_asset_combinations_generalized','volumes_generalized','timestamps_generalized',
        'no_personal_data_remaining','no_forbidden_industrial_dimensions')}
    human.update(reidentification_risk='MEDIUM',reviewer_role='TEST_HUMAN',reviewed_at_utc='2026-09-09T00:00:00+00:00',
        artifact_sha256={candidate['path']:candidate['sha256']})
    with pytest.raises(ValueError,match='LOW'):approve_retention_candidate(case,human)
    human['reidentification_risk']='LOW'
    assert approve_retention_candidate(case,human)['status']=='RETENTION_APPROVED'


def test_real_contract_without_rnd_authorization_blocks_learning_export(case_packet):
    from tests.contract_fixtures import authorize_test_case
    from energy_mvp.privacy import POLICY_VERSION
    from pilot_learning import create_retention_candidate, export_authorized_pilot_metrics
    case,p=case_packet;save(case,p,time_record());review=build_pilot_learning_review(case,{})
    path=case/'case_manifest.json';manifest=json.loads(path.read_text())
    manifest.update(case_kind='REAL_CLIENT',privacy={'required':True,'policy_version':POLICY_VERSION})
    path.write_text(json.dumps(manifest))
    authorize_test_case(case,derived_retention_authorized=True,internal_rnd_use_authorized=None)
    with pytest.raises(ValueError,match='finalité'):create_retention_candidate(case,review)
    with pytest.raises(ValueError,match='finalité'):
        export_authorized_pilot_metrics(review,authorization={'authorized':True,'deidentification_reviewed':True,
            'authorization_ref':'provided','reviewer':'provided'},pilot_id='PILOT-1234567890abcdef')
    assert not (case/'retained_derived/pilot_learning.csv').exists()


def test_full_confidential_review_is_purged_only_approved_whitelist_survives(case_packet):
    from datetime import datetime,timezone
    from tests.contract_fixtures import authorize_test_case
    from energy_mvp.privacy import POLICY_VERSION, RETENTION_SCHEMA, configure_retention, purge_client_case
    from pilot_learning import create_retention_candidate, approve_retention_candidate
    case,p=case_packet;save(case,p,time_record());review=persist_pilot_learning_review(case,{'post_mortem':post_mortem()})
    path=case/'case_manifest.json';manifest=json.loads(path.read_text())
    manifest.update(case_kind='REAL_CLIENT',privacy={'required':True,'policy_version':POLICY_VERSION})
    path.write_text(json.dumps(manifest))
    authorize_test_case(case,derived_retention_authorized=True,internal_rnd_use_authorized=True)
    candidate=create_retention_candidate(case,review)
    human={key:True for key in ('approved_for_long_term_retention','site_identity_removed',
        'unique_asset_combinations_generalized','volumes_generalized','timestamps_generalized',
        'no_personal_data_remaining','no_forbidden_industrial_dimensions')}
    human.update(reidentification_risk='LOW',reviewer_role='TEST_HUMAN',reviewed_at_utc='2026-09-09T00:00:00+00:00',
        artifact_sha256={candidate['path']:candidate['sha256']})
    approve_retention_candidate(case,human)
    configure_retention(case,{'schema_version':RETENTION_SCHEMA,'configured':True,
        'purge_after_utc':'2099-01-01T00:00:00+00:00','mission_closed':True,
        'derived_retention_authorized':True,'retained_paths':[],
        'retained_derived_paths':[candidate['path']]})
    receipt=purge_client_case(case,now=datetime(2100,1,1,tzinfo=timezone.utc))
    assert receipt['status']=='complete' and (case/candidate['path']).exists()
    assert not (case/'investigation/PILOT_LEARNING_REVIEW.md').exists()
    assert not (case/'investigation/economic_decision_state.json').exists()
    assert not (case/'contracts/test_agreement.txt').exists()
    assert all(not f.is_file() for f in (case/'normalized').rglob('*'))
