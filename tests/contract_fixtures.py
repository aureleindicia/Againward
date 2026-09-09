"""Explicit fictional agreements for tests of REAL_CLIENT software gates only."""
import hashlib
from energy_mvp.contract_policy import contract_policy_template, contract_policy_digest, record_contract_policy


def contract_packet(case, **updates):
    source = case / 'contracts/test_agreement.txt'
    source.parent.mkdir(exist_ok=True)
    source.write_text('Fictional agreement for software tests. No real client authorization.')
    policy = contract_policy_template()
    policy.update(agreement_active=True, client_data_processing_allowed=True,
        confidentiality_applies=True, effective_at='2020-01-01T00:00:00+00:00',
        purge_after_utc='2099-01-01T00:00:00+00:00', contract_ref='contracts/test_agreement.txt',
        source_refs=[{'path':'contracts/test_agreement.txt','sha256':hashlib.sha256(source.read_bytes()).hexdigest()}],
        review_status='REVIEWED', external_processing_constraints=[])
    policy.update(updates)
    return {'policy':policy, 'semantic_extraction':{'completed':True,'extractor_role':'CODEX'},
        'human_review':{'approved':True,'policy_sha256':contract_policy_digest(policy),
            'reviewer_role':'TEST_FIXTURE_ONLY','reviewed_at_utc':'2026-09-09T00:00:00+00:00',
            'external_processing_constraints_satisfied':True}}


def authorize_test_case(case, **updates):
    packet=contract_packet(case, **updates)
    return record_contract_policy(case, **packet)
