"""Generic native sources, actual reducers and bounded scripted decisions.

These tests establish software invariants, not actual-provider quality.
"""
import json
from dataclasses import replace

import pytest

from againward.core.artifact_store import read_json
from againward.documents.sources import inventory_sources
from againward.domains.energy_billing.loop import Budget, investigate, runtime_lease
from againward.domains.energy_billing.protocol import ACTION_SCHEMA, READ_SCHEMA, FIELDS, BillingFailure
from againward.domains.energy_billing.state import initialize, load_state, REQUIRED
from againward.domains.energy_billing.investigator import semantic_hash, semantic_progress
from tests.test_energy_billing_state import case, receipt


def context(prompt):
    return json.JSONDecoder().raw_decode(prompt[prompt.index('{'):])[0]


def blank(tmp_path):
    case(tmp_path, reviews=False)
    root = tmp_path / "loop-state"
    initialize(inventory_sources(tmp_path / "input", root), root)
    return root


def scripted(prompt, schema):
    data = context(prompt)
    if schema == ACTION_SCHEMA:
        issue = data['issue']
        code, targets = issue['code'], issue['targets']
        if code == 'SOURCE_NOT_READ':
            action = {'type': 'REQUEST_REREAD', 'source_id': issue['source_id']}
        elif code == 'SOURCE_OCCURRENCE_MISSING':
            kind = 'TARIFF' if any(a['field'] == 'contract_id' for a in data['observations'].values()) else 'INVOICE'
            if not set(REQUIRED[kind]) <= {a['field'] for a in data['observations'].values()}:
                action = {'type': 'REQUEST_REREAD', 'source_id': issue['source_id']}
            else:
                action = {'type': 'DECLARE_' + kind, 'evidence_ids': list(data['observations'])}
        elif code == 'GOVERNS_MISSING':
            inv = next(k for k, r in data['occurrences'].items() if r['kind'] == 'INVOICE')
            tar = next(k for k, r in data['occurrences'].items() if r['kind'] == 'TARIFF')
            ids = [k for k, r in data['observations'].items() if r['field'] in {'pdl', 'supplier_id', 'period_start', 'effective_start'}]
            action = {'type': 'LINK_TARIFF', 'invoice_id': inv, 'tariff_id': tar, 'evidence_ids': ids}
        elif code == 'READY_PROPOSAL':
            action = {'type': 'PROPOSE_READY'}
        elif targets:
            action = {'type': 'REQUEST_REVIEW', 'target': targets[0]}
        else:
            action = {'type': 'MARK_UNRESOLVED', 'reason': 'No established source authority.'}
        return json.dumps({'issue_id': issue['issue_id'], 'action': action}).encode()
    if schema == READ_SCHEMA:
        atoms = []
        for unit in data['units']:
            if ': ' in unit['text']:
                field, value = unit['text'].split(': ', 1)
                if field in FIELDS:
                    value = value.split(' ; ')[0]
                    atoms.append({'field': field, 'value': value, 'quote': field + ': ' + value,
                                  'location': unit['location'], 'group': 'document'})
        return json.dumps({'observations': atoms, 'limitations': []}).encode()
    deps = data['local_proposal']
    subject = deps['subject']
    response = {'verdict': 'SUPPORTED', 'evidence_ids': subject['evidence_ids'],
                'reason': 'Scripted independent original-source check.'}
    if subject['kind'] == 'GOVERNS':
        sid = deps['occurrences'][subject['tariff_id']]['source_id']
        source = next(s for s in data['original_sources'] if s['source_id'] == sid)
        unit = next(u for u in source['units'] if 'Authority: Accepted commercial terms' in u['text'])
        response.update(authority_kind='ACCEPTED_CONTRACT', authority_source_id=sid, authority_location=unit['location'],
                        authority_quote='Authority: Accepted commercial terms for this contract.')
    else:
        response.update(coverage='ALL_MATERIAL_FACTS_BOUND', charge_kind='CONSUMPTION_HT', end_convention='EXCLUSIVE',
                        nonmaterial_quarantine_ids=[])
        if subject['kind'] == 'TARIFF':
            response.update(tariff_type='FIXED', rounding_rule='HALF_UP_PER_LINE')
    return json.dumps(response).encode()


def test_blank_sources_to_reviewed_calculation_and_persistent_budget(tmp_path):
    root = blank(tmp_path)
    result = investigate(root, model='SCRIPTED', transport=scripted)
    assert result['terminal_reason']['code'] == 'CALCULATION_CREATED'
    assert result['calculation']['expected_cents'] == 18462
    assert result['calculation']['discrepancy_cents'] == 3838
    assert result['turns'] == 9 and result['model_calls'] == 14 and result['rereads'] == 2
    assert len(load_state(root)['reviews']) == 3
    assert all(s['progress'] for s in result['steps'][:-1])
    assert not result['steps'][-1]['progress']  # Calculation receipt is not new domain evidence.
    assert investigate(root, model='SCRIPTED', transport=lambda *_: pytest.fail('completed runtime re-called model')) == result
    with pytest.raises(BillingFailure, match='RUNTIME_REPLAY_INVALID'):
        investigate(root, model='SCRIPTED', transport=scripted, budget=replace(Budget(), max_turns=25))


def test_missing_original_quantity_recovered_by_local_reread(tmp_path):
    root = blank(tmp_path)
    omitted = False

    def partial(prompt, schema):
        nonlocal omitted
        response = json.loads(scripted(prompt, schema))
        if schema == READ_SCHEMA and any(a['field'] == 'quantity' for a in response['observations']) and not omitted:
            response['observations'] = [a for a in response['observations'] if a['field'] != 'quantity']
            omitted = True
        return json.dumps(response).encode()

    result = investigate(root, model='SCRIPTED', transport=partial)
    assert omitted and result['calculation']['expected_cents'] == 18462
    assert result['rereads'] == 3 and result['model_calls'] == 16
    assert result['steps'][1]['issue_code'] == 'SOURCE_OCCURRENCE_MISSING' or any(
        s['issue_code'] == 'SOURCE_OCCURRENCE_MISSING' and s['action']['type'] == 'REQUEST_REREAD' for s in result['steps'])


@pytest.mark.parametrize('failure', ['MODEL_PROVIDER_FAILURE', 'MODEL_PROTOCOL_FAILURE'])
def test_execution_failures_are_not_business_unsupported(tmp_path, failure):
    state, root, *_ = case(tmp_path, reviews=False)
    calls = []

    def broken(*_):
        calls.append(1)
        if failure == 'MODEL_PROVIDER_FAILURE':
            raise BillingFailure(failure, stage='PROVIDER', cause='TIMEOUT')
        return b'not JSON'

    result = investigate(root, model='SCRIPTED', transport=broken)
    assert result['terminal_reason']['code'] == failure
    assert len(calls) == (1 if failure == 'MODEL_PROVIDER_FAILURE' else 2)
    assert load_state(root) == state and result['calculation'] is None
    assert result['protocol_repairs'] == (0 if failure == 'MODEL_PROVIDER_FAILURE' else 1)


def test_source_is_not_review_target_repaired_before_state_mutation(tmp_path):
    state, root, *_ = case(tmp_path, reviews=False)
    injected = False

    def wrong_target(prompt, schema):
        nonlocal injected
        if schema == ACTION_SCHEMA and not injected:
            injected = True
            data = context(prompt)
            target = next(iter(data['occurrences'].values()))['source_id']
            assert load_state(root) == state
            return json.dumps({'issue_id': data['issue']['issue_id'], 'action': {'type': 'REQUEST_REVIEW', 'target': target}}).encode()
        return scripted(prompt, schema)

    result = investigate(root, model='SCRIPTED', transport=wrong_target)
    assert result['terminal_reason']['code'] == 'CALCULATION_CREATED'
    assert result['protocol_repairs'] == 1
    assert result['diagnostics'][0]['path'] == '$.action.target'
    assert result['diagnostics'][0]['state_mutated'] is False


def test_premature_ready_cannot_override_python_readiness(tmp_path):
    state, root, *_ = case(tmp_path, reviews=False)

    def ready(prompt, schema):
        data = context(prompt)
        return json.dumps({'issue_id': data['issue']['issue_id'], 'action': {'type': 'PROPOSE_READY'}}).encode()

    result = investigate(root, model='SCRIPTED', transport=ready)
    assert result['terminal_reason']['code'] == 'REPEATED_REJECTION'
    assert result['terminal_reason']['root_cause']['code'] == 'MATERIAL_EVIDENCE_MISSING'
    assert result['turns'] == 2 and result['calculation'] is None and load_state(root) == state


def test_native_inspections_are_local_and_do_not_fake_progress(tmp_path):
    state, root, *_ = case(tmp_path, reviews=False)
    seen = []

    def inspect(prompt, schema):
        data = context(prompt)
        issue = data['issue']
        source = next(iter(issue['source_handles']))
        if seen:
            unit = issue['feedback']['inspection']
            assert unit['source_id'] == source and unit['text']
        seen.append(issue)
        return json.dumps({'issue_id': issue['issue_id'], 'action': {'type': 'REQUEST_INSPECTION', 'source_id': source,
                        'location': issue['source_handles'][source][0]['location']}}).encode()

    result = investigate(root, model='SCRIPTED', transport=inspect)
    assert result['terminal_reason']['code'] == 'NO_SEMANTIC_PROGRESS'
    assert len(seen) == 3 and all(not s['progress'] for s in result['steps'])
    assert all(len(i['source_handles']) == 1 for i in seen)
    assert load_state(root) == state


@pytest.mark.parametrize('budget, expected', [
    (replace(Budget(), max_model_calls=1), 'max_model_calls'),
    (replace(Budget(), max_turns=1), 'max_turns'),
    (replace(Budget(), max_rereads=1), 'max_rereads'),
])
def test_lifetime_limits_preserve_partial_evidence(tmp_path, budget, expected):
    root = blank(tmp_path)
    result = investigate(root, model='SCRIPTED', transport=scripted, budget=budget)
    assert result['terminal_reason']['code'] == 'RESOURCE_LIMIT'
    assert result['terminal_reason']['budget'] == expected
    if expected != 'max_model_calls':
        assert load_state(root)['observations']
    assert result['calculation'] is None
    assert investigate(root, model='SCRIPTED', transport=scripted, budget=budget) == result


def test_interrupted_call_reservation_is_durable_and_cannot_restart(tmp_path):
    state, root, *_ = case(tmp_path, reviews=False)

    def interrupted(*_):
        checkpoint = read_json(root / 'energy_billing/investigator.json')
        assert checkpoint['model_calls'] == 1 and checkpoint['pending'] is True
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        investigate(root, model='SCRIPTED', transport=interrupted)
    assert load_state(root) == state
    with pytest.raises(BillingFailure, match='RUNTIME_INTERRUPTED'):
        investigate(root, model='SCRIPTED', transport=scripted)


def test_concurrent_runtime_cannot_reset_budget(tmp_path):
    _, root, *_ = case(tmp_path, reviews=False)
    with runtime_lease(root), pytest.raises(BillingFailure, match='RUNTIME_BUSY'):
        investigate(root, model='SCRIPTED', transport=scripted)


def test_repeated_invalid_declaration_retains_one_causal_rejection(tmp_path):
    root = blank(tmp_path)

    def incomplete(prompt, schema):
        data = context(prompt)
        if schema == ACTION_SCHEMA and data['issue']['code'] == 'SOURCE_OCCURRENCE_MISSING':
            eid = next(iter(data['observations']))
            return json.dumps({'issue_id': data['issue']['issue_id'],
                               'action': {'type': 'DECLARE_INVOICE', 'evidence_ids': [eid]}}).encode()
        return scripted(prompt, schema)

    result = investigate(root, model='SCRIPTED', transport=incomplete)
    assert result['terminal_reason']['code'] == 'REPEATED_REJECTION'
    assert result['terminal_reason']['root_cause']['code'] == 'MATERIAL_EVIDENCE_MISSING'
    assert not load_state(root)['occurrences'] and load_state(root)['observations']
    assert len(result['rejections']) == 1 and result['protocol_repairs'] == 0


def test_wall_time_exhaustion_is_execution_limit_not_financial_answer(tmp_path):
    state, root, *_ = case(tmp_path, reviews=False)
    elapsed = [0.0]

    def slow(prompt, schema):
        raw = scripted(prompt, schema)
        elapsed[0] = 2.0
        return raw

    result = investigate(root, model='SCRIPTED', transport=slow, budget=replace(Budget(), wall_seconds=1),
                         clock=lambda: elapsed[0])
    assert result['terminal_reason']['code'] == 'RESOURCE_LIMIT'
    assert result['terminal_reason']['budget'] == 'wall_seconds'
    assert result['model_calls'] == 1 and load_state(root) == state


def test_total_protocol_repairs_are_bounded_across_turns(tmp_path):
    _, root, *_ = case(tmp_path, reviews=False)

    def bad_focus(prompt, schema):
        response = json.loads(scripted(prompt, schema))
        if schema == ACTION_SCHEMA and 'The last response was rejected without state mutation.' not in prompt:
            response['issue_id'] = 'obsolete'
        return json.dumps(response).encode()

    result = investigate(root, model='SCRIPTED', transport=bad_focus, budget=replace(Budget(), max_protocol_repairs=1))
    assert result['terminal_reason']['code'] == 'RESOURCE_LIMIT'
    assert result['terminal_reason']['budget'] == 'max_protocol_repairs'
    assert result['protocol_repairs'] == 1 and len(load_state(root)['reviews']) == 1


def test_unsupported_fixed_path_is_not_repaired_or_calculated(tmp_path):
    _, root, *_ = case(tmp_path, tariff_changes={'tariff_type': 'INDEXED'}, reviews=False)

    def indexed(prompt, schema):
        response = json.loads(scripted(prompt, schema))
        if 'tariff_type' in schema['properties']:
            response['tariff_type'] = 'INDEXED'
        return json.dumps(response).encode()

    result = investigate(root, model='SCRIPTED', transport=indexed)
    assert result['terminal_reason']['code'] == 'UNSUPPORTED_DOMAIN_RULE'
    assert result['readiness']['support_state'] == 'UNSUPPORTED'
    assert result['calculation'] is None and result['protocol_repairs'] == 0


def test_new_invalid_reread_rows_are_changes_but_never_progress(tmp_path):
    _, root, *_ = case(tmp_path, reviews=False)
    invalid = 0

    def repeated_invalid(prompt, schema):
        nonlocal invalid
        data = context(prompt)
        if schema == ACTION_SCHEMA:
            source = next(iter(data['issue']['source_handles']))
            return json.dumps({'issue_id': data['issue']['issue_id'],
                               'action': {'type': 'REQUEST_REREAD', 'source_id': source}}).encode()
        response = json.loads(scripted(prompt, schema))
        invalid += 1
        response['observations'].append({'field': 'note', 'group': f'bad-{invalid}', 'value': 'decorative',
                                        'location': 'line:999', 'quote': f'Invented quote {invalid}'})
        return json.dumps(response).encode()

    result = investigate(root, model='SCRIPTED', transport=repeated_invalid)
    assert result['terminal_reason']['code'] == 'NO_SEMANTIC_PROGRESS'
    assert result['rereads'] == 3 and len(load_state(root)['quarantine']) == 3
    assert all(not s['progress'] for s in result['steps'])
    assert all(s['before_semantic_sha256'] != s['after_semantic_sha256'] for s in result['steps'])


def test_material_review_semantics_count_but_rewording_does_not(tmp_path):
    state, root, iid, *_ = case(tmp_path)
    before = receipt(state, iid, root, coverage='INCOMPLETE')
    after = receipt(before, iid, root, coverage='ALL_MATERIAL_FACTS_BOUND')
    assert semantic_progress(before, after) and semantic_hash(before) != semantic_hash(after)
    reworded = receipt(after, iid, root, reason='A new formulation of the same independently checked facts.')
    assert not semantic_progress(after, reworded) and semantic_hash(after) == semantic_hash(reworded)


def test_removed_coverage_gap_resets_stagnation_and_reaches_calculation(tmp_path):
    state, root, iid, *_ = case(tmp_path)
    receipt(state, iid, root, coverage='INCOMPLETE')
    actions = 0

    def recover_coverage(prompt, schema):
        nonlocal actions
        if schema != ACTION_SCHEMA:
            return scripted(prompt, schema)
        data = context(prompt)
        actions += 1
        if actions <= 2:
            sid = data['occurrences'][iid]['source_id']
            action = {'type': 'REQUEST_INSPECTION', 'source_id': sid,
                      'location': data['issue']['source_handles'][sid][0]['location']}
        elif actions == 3:
            action = {'type': 'REQUEST_REVIEW', 'target': iid}
        else:
            return scripted(prompt, schema)
        return json.dumps({'issue_id': data['issue']['issue_id'], 'action': action}).encode()

    result = investigate(root, model='SCRIPTED', transport=recover_coverage)
    assert result['terminal_reason']['code'] == 'CALCULATION_CREATED'
    assert [s['progress'] for s in result['steps']] == [False, False, True, False]
