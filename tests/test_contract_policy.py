import copy
import json
from pathlib import Path
import pytest
from energy_mvp.client_workspace import create_client_workspace
from energy_mvp.privacy import stage_incoming_drop, validate_codex_privacy_review
from energy_mvp.contract_policy import record_contract_policy, contract_policy_digest, inspect_contract_status
from energy_mvp.workflow_paths import inspect_case_status
from tests.contract_fixtures import contract_packet


@pytest.fixture
def staged_case(tmp_path):
    create_client_workspace('case', root=tmp_path)
    case=tmp_path/'case';drop=tmp_path/'drop';drop.mkdir();(drop/'energy.csv').write_text('power_kw\n10\n')
    return case,drop


def test_first_real_drop_fails_before_copy_without_agreement(staged_case):
    case,drop=staged_case
    with pytest.raises(ValueError,match='CONTRACT_GATE'):stage_incoming_drop(drop,case)
    assert list((case/'incoming').iterdir())==[]
    assert inspect_case_status(case)['next_action']=='RESOLVE_CONTRACT_POLICY_BEFORE_REAL_DATA'


@pytest.mark.parametrize('permission',[None,False])
def test_active_agreement_without_processing_permission_is_blocked(staged_case,permission):
    case,drop=staged_case;p=contract_packet(case);p['policy']['client_data_processing_allowed']=permission
    p['human_review']['policy_sha256']=contract_policy_digest(p['policy']);record_contract_policy(case,**p)
    with pytest.raises(ValueError,match='explicitement'):stage_incoming_drop(drop,case)
    assert json.loads((case/'contracts/contract_policy.json').read_text())['client_data_processing_allowed'] is permission


def test_ambiguous_clause_requires_review(staged_case):
    case,drop=staged_case;p=contract_packet(case);p['policy']['ambiguity_codes']=['EXTERNAL_PROCESSING_SCOPE']
    p.pop('human_review');record_contract_policy(case,**p)
    assert json.loads((case/'contracts/contract_policy.json').read_text())['review_status']=='HUMAN_LEGAL_REVIEW_REQUIRED'
    assert not inspect_contract_status(case)['allowed']
    with pytest.raises(ValueError):stage_incoming_drop(drop,case)


def test_authorized_staging_traces_policy_not_raw_agreement(staged_case):
    case,drop=staged_case;p=contract_packet(case);record_contract_policy(case,**p)
    receipt=stage_incoming_drop(drop,case)
    assert receipt['contract_policy_sha256']==contract_policy_digest(p['policy'])
    assert (case/'incoming/energy.csv').exists()
    assert not (case/'incoming/test_agreement.txt').exists()
    assert 'Fictional agreement' not in json.dumps(receipt)


def test_modified_policy_or_contract_invalidates_permission(staged_case):
    case,drop=staged_case;p=contract_packet(case);record_contract_policy(case,**p)
    source=case/'contracts/test_agreement.txt';source.write_text('Changed agreement')
    with pytest.raises(ValueError,match='modifiée'):stage_incoming_drop(drop,case)
    p=contract_packet(case);record_contract_policy(case,**p)
    policy=case/'contracts/contract_policy.json';changed=copy.deepcopy(p['policy']);changed['portfolio_use_authorized']=True
    policy.write_text(json.dumps(changed))
    with pytest.raises(ValueError,match='périmée'):stage_incoming_drop(drop,case)


def test_raw_fields_not_allowed_and_direct_privacy_promotion_blocked(staged_case):
    case,drop=staged_case;p=contract_packet(case);p['policy']['bank_account']='not allowed'
    with pytest.raises(ValueError,match='fermé'):record_contract_policy(case,**p)
    (case/'incoming/energy.csv').write_bytes((drop/'energy.csv').read_bytes())
    with pytest.raises(ValueError,match='CONTRACT_GATE'):validate_codex_privacy_review(case,case/'privacy/review.json')
    assert not (case/'sanitized/energy.csv').exists()


def test_retention_cannot_create_contractual_permission(staged_case):
    from energy_mvp.privacy import configure_retention, RETENTION_SCHEMA
    case,_=staged_case;p=contract_packet(case);record_contract_policy(case,**p)
    retention={'schema_version':RETENTION_SCHEMA,'configured':True,
        'purge_after_utc':p['policy']['purge_after_utc'],'mission_closed':False,
        'derived_retention_authorized':True,'retained_paths':[],'retained_derived_paths':[]}
    with pytest.raises(ValueError,match='dérivés'):configure_retention(case,retention)
    retention.update(derived_retention_authorized=False,retained_paths=['outputs/unapproved.pdf'])
    with pytest.raises(ValueError,match='fichier retenu'):configure_retention(case,retention)
    retention.update(retained_paths=[],purge_after_utc='2100-01-01T00:00:00+00:00')
    with pytest.raises(ValueError,match='échéance'):configure_retention(case,retention)


def test_delivery_requires_contract_bound_retention(staged_case):
    from energy_mvp.contract_policy import assert_contract_permission
    from energy_mvp.privacy import configure_retention, RETENTION_SCHEMA
    case,_=staged_case;p=contract_packet(case);record_contract_policy(case,**p)
    with pytest.raises(ValueError):assert_contract_permission(case,operation='delivery')
    extraction=json.loads((case/'contracts/contract_extraction.json').read_text())
    (case/'privacy/privacy_manifest.json').write_text(json.dumps({'contract_authorization_ref':extraction['authorization_ref'],
        'validated_at_utc':'2026-09-09T00:00:00+00:00'}))
    configure_retention(case,{'schema_version':RETENTION_SCHEMA,'configured':True,
        'purge_after_utc':p['policy']['purge_after_utc'],'mission_closed':False,
        'derived_retention_authorized':False,'retained_paths':[],'retained_derived_paths':[]})
    assert assert_contract_permission(case,operation='delivery')['agreement_active'] is True


@pytest.mark.parametrize('instant',['2019-01-01T00:00:00+00:00','2100-01-01T00:00:00+00:00'])
def test_processing_outside_agreement_period_is_blocked(staged_case,instant):
    from datetime import datetime
    from energy_mvp.contract_policy import assert_contract_permission
    case,_=staged_case;record_contract_policy(case,**contract_packet(case))
    with pytest.raises(ValueError,match='période'):
        assert_contract_permission(case,now=datetime.fromisoformat(instant))


def test_closed_mission_and_unknown_operation_cannot_admit_new_data(staged_case):
    from energy_mvp.contract_policy import assert_contract_permission
    from energy_mvp.privacy import configure_retention, RETENTION_SCHEMA
    case,drop=staged_case;p=contract_packet(case);record_contract_policy(case,**p)
    with pytest.raises(ValueError,match='opération inconnue'):
        assert_contract_permission(case,operation='processng')
    configure_retention(case,{'schema_version':RETENTION_SCHEMA,'configured':True,
        'purge_after_utc':p['policy']['purge_after_utc'],'mission_closed':True,
        'derived_retention_authorized':False,'retained_paths':[],'retained_derived_paths':[]})
    with pytest.raises(ValueError,match='mission close'):stage_incoming_drop(drop,case)
    assert list((case/'incoming').iterdir())==[]
