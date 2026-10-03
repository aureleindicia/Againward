"""Original native data + real reducers; scripted review is not model quality."""
import json

import pytest

from againward.documents.sources import inventory_sources
from againward.domains.energy_billing import disposition as disp
from againward.domains.energy_billing.calculation import calculate, readiness
from againward.domains.energy_billing.investigator import semantic_hash, semantic_progress
from againward.domains.energy_billing.loop import investigate
from againward.domains.energy_billing.protocol import ACTION_SCHEMA, DISPOSITION_REVIEW_SCHEMA, BillingFailure
from againward.domains.energy_billing.provider import ModelBoundary
from againward.domains.energy_billing.reader import read_source
from againward.domains.energy_billing.review import current_review
from againward.domains.energy_billing.state import initialize, commit_event, load_state, REQUIRED
from tests.test_energy_billing_loop import context, scripted
from tests.test_energy_billing_state import case, action, receipt


def proposal(target, decision='SUPERSEDED', replacements=(), evidence=()):
    return {'type': 'REQUEST_DISPOSITION', 'target': target, 'disposition': decision,
            'replacement_ids': list(replacements), 'evidence_ids': list(evidence), 'reason': 'Challenge this exact local evidence.'}


def settle(state, root, proposed, *, verdict='SUPPORTED', basis='EXTRACTION_ERROR', **changes):
    deps = disp.dependencies(state, proposed)
    originals = disp.contexts(deps, state, root)
    response = {'verdict': verdict, 'basis': basis, 'coverage': 'ALL_MATERIAL_FACTS_ACCOUNTED' if verdict == 'SUPPORTED' else 'INCOMPLETE',
                'reason': 'Scripted original-source independent check.',
                'proofs': [{'source_id': c['source_id'], 'location': c['units'][0]['location'], 'quote': c['units'][0]['text']}
                           for c in originals] if verdict == 'SUPPORTED' else []}
    response.update(changes)
    digest = disp.request_disposition(state, proposed, root, model='SCRIPTED', boundary=ModelBoundary(
        lambda *_: json.dumps(response).encode()))
    return commit_event(state, {'type': 'DISPOSITION', 'receipt_sha256': digest}, root)


def refresh(state, root):
    for key in disp.active_occurrences(state):
        state = receipt(state, key, root)
    active = disp.active_occurrences(state)
    iid = next(k for k, r in active.items() if r['kind'] == 'INVOICE')
    tid = next(k for k, r in active.items() if r['kind'] == 'TARIFF')
    state = action(state, root, 'LINK_TARIFF', invoice_id=iid, tariff_id=tid,
                   evidence_ids=[active[iid]['evidence_ids'][0], active[tid]['evidence_ids'][0]])
    rid = next(k for k, r in state['relations'].items() if r['invoice_id'] == iid and r['tariff_id'] == tid)
    return receipt(state, rid, root)


def multi_source(tmp_path, name, content):
    case(tmp_path, reviews=False)
    (tmp_path / 'input' / name).write_text(content)
    root = tmp_path / 'multi-state'
    batch = inventory_sources(tmp_path / 'input', root)
    state = initialize(batch, root)
    for document in batch.documents:
        digest = read_source(batch, document.source_id, root, model='SCRIPTED', boundary=ModelBoundary(scripted), role='PRIMARY')
        state = commit_event(state, {'type': 'READ', 'receipt_sha256': digest}, root)
        ids = [key for key, row in state['observations'].items() if row['source_id'] == document.source_id]
        names = {state['observations'][key]['field'] for key in ids}
        for kind, required in REQUIRED.items():
            if set(required) <= names:
                try:
                    state = action(state, root, 'DECLARE_' + kind, evidence_ids=ids)
                except BillingFailure as exc:
                    assert exc.code == 'OCCURRENCE_AMBIGUOUS'
    sid = next(d.source_id for d in batch.documents if name in d.original_names)
    return state, root, sid


def test_material_quarantine_resolved_independently_without_deleting_any_evidence(tmp_path):
    bad = {'field': 'quantity', 'value': '999', 'group': 'bad', 'location': 'line:999', 'quote': 'Invented 999'}
    state, root, iid, tid, rid = case(tmp_path, bad_atom=bad)
    before = state
    assert not readiness(state, root)['ready']
    qid = next(iter(state['quarantine']))
    replacement = next(k for k, r in state['observations'].items() if r['field'] == 'quantity')
    state = settle(state, root, proposal(qid, replacements=[replacement], evidence=[replacement]))
    assert semantic_progress(before, state)
    assert state['observations'] == before['observations'] and state['quarantine'] == before['quarantine']
    assert current_review(state, tid, root)['verdict'] == 'SUPPORTED'
    for key in (iid, rid):
        with pytest.raises(BillingFailure, match='REVIEW_STALE'):
            current_review(state, key, root)
    state = receipt(state, iid, root)
    state = receipt(state, rid, root)
    result = calculate(state, root)
    assert result['expected_cents'] == 18462 and result['discrepancy_cents'] == 3838
    assert result['disposition_receipts'][qid] == state['dispositions'][qid]['receipt_sha256']
    assert all(row['disposition'] != 'UNRESOLVED' for row in result['material_frontier'])
    assert load_state(root) == state


def test_wrong_normalized_scalar_replaced_locally_with_old_objects_preserved(tmp_path):
    from againward.documents.contracts import SourceBatch
    state, root, iid, tid, _ = case(tmp_path, reader_changes={'quantity': {'value': '1502'}})
    wrong = next(k for k, r in state['observations'].items() if r['field'] == 'quantity')
    atom = state['observations'][wrong]
    response = {'observations': [{'field': 'quantity', 'group': 'corrected', 'value': '1501',
                                 'quote': atom['quote'], 'location': atom['location']}], 'limitations': []}
    digest = read_source(SourceBatch.from_dict(state['batch']), atom['source_id'], root, model='SCRIPTED',
                         boundary=ModelBoundary(lambda *_: json.dumps(response).encode()), role='RECOVERY')
    state = commit_event(state, {'type': 'READ', 'receipt_sha256': digest}, root)
    correct = next(k for k, r in state['observations'].items() if r['field'] == 'quantity' and r['value'] == '1501')
    with pytest.raises(BillingFailure, match='OCCURRENCE_AMBIGUOUS'):
        action(state, root, 'DECLARE_INVOICE', evidence_ids=[correct if k == wrong else k for k in state['occurrences'][iid]['evidence_ids']])
    state = settle(state, root, proposal(wrong, replacements=[correct], evidence=[correct]))
    ids = [correct if k == wrong else k for k in state['occurrences'][iid]['evidence_ids']]
    state = action(state, root, 'DECLARE_INVOICE', evidence_ids=ids)
    assert len(state['occurrences']) == 3 and iid not in disp.active_occurrences(state)
    assert state['observations'][wrong]['value'] == '1502'
    assert current_review(state, tid, root)['verdict'] == 'SUPPORTED'
    state = refresh(state, root)
    assert calculate(state, root)['expected_cents'] == 18462


def test_decorative_source_disposition_allows_scoped_calculation_and_preserves_bytes(tmp_path):
    state, root, sid = multi_source(tmp_path, 'memo.txt', 'Internal logistics memo, no commercial terms.')
    state = refresh(state, root)
    assert not readiness(state, root)['ready']
    original = next(d for d in state['batch']['documents'] if d['source_id'] == sid)
    body = (root / original['blob_path']).read_bytes()
    state = settle(state, root, proposal(sid, 'IRRELEVANT'), basis='DECORATIVE')
    assert readiness(state, root)['ready']
    assert (root / original['blob_path']).read_bytes() == body
    result = calculate(state, root)
    assert result['expected_cents'] == 18462
    assert next(r for r in result['material_frontier'] if r['target'] == sid)['disposition'] == 'IRRELEVANT'
    (root / original['blob_path']).write_text('Changed memo now contains a tariff')
    assert load_state(root) == state
    assert readiness(state, root)['root_issues'][0]['code'] == 'SOURCE_CHANGED'


def test_semantic_duplicate_source_is_not_double_counted(tmp_path):
    prep = tmp_path / 'prep'
    prep.mkdir()
    case(prep)
    content = (prep / 'input/invoice.txt').read_text() + '\nCopy exported by accounts department.'
    state, root, duplicate = multi_source(tmp_path, 'copy.txt', content)
    invoice_sources = [r['source_id'] for r in state['occurrences'].values() if r['kind'] == 'INVOICE']
    other = next(s for s in invoice_sources if s != duplicate)
    state = settle(state, root, proposal(duplicate, 'DUPLICATE', replacements=[other]), basis='DUPLICATE_CONTENT')
    state = refresh(state, root)
    assert len(state['occurrences']) == 3 and len(disp.active_occurrences(state)) == 2
    result = calculate(state, root)
    assert result['expected_cents'] == 18462 and result['billed_cents'] == 22300


def test_competing_accepted_tariffs_stay_unresolved_and_cannot_be_declared_duplicates(tmp_path):
    prep = tmp_path / 'prep'
    prep.mkdir()
    case(prep)
    content = (prep / 'input/tariff.txt').read_text().replace('TERMS-Generic', 'TERMS-Other').replace('0.123', '0.148')
    state, root, competing = multi_source(tmp_path, 'other-tariff.txt', content)
    other = next(r['source_id'] for r in state['occurrences'].values() if r['kind'] == 'TARIFF' and r['source_id'] != competing)
    with pytest.raises(BillingFailure, match='BUSINESS_AMBIGUITY'):
        settle(state, root, proposal(competing, 'DUPLICATE', replacements=[other]), basis='DUPLICATE_CONTENT')
    state = settle(state, root, proposal(competing, 'SUPERSEDED', replacements=[other]), verdict='AMBIGUOUS', basis='UNRESOLVED')
    assert not readiness(state, root)['ready'] and len(disp.active_occurrences(state)) == 3
    assert competing not in disp.excluded_ids(state)


def test_explicit_accepted_amendment_supersedes_old_source_without_erasing_it(tmp_path):
    from decimal import Decimal, ROUND_HALF_UP
    prep = tmp_path / 'prep'
    prep.mkdir()
    case(prep)
    content = (prep / 'input/tariff.txt').read_text().replace('TERMS-Generic', 'TERMS-Revision').replace('0.123', '0.110')
    content += '\nAccepted amendment explicitly replaces TERMS-Generic for the same PDL throughout the stated period.'
    state, root, replacement = multi_source(tmp_path, 'amendment.txt', content)
    previous = next(r['source_id'] for r in state['occurrences'].values() if r['kind'] == 'TARIFF' and r['source_id'] != replacement)
    p = proposal(previous, replacements=[replacement])
    originals = disp.contexts(disp.dependencies(state, p), state, root)
    proof_rows = [{'source_id': c['source_id'], 'location': u['location'], 'quote': u['text']}
                  for c in originals for u in c['units'] if 'Authority:' in u['text'] or 'explicitly replaces' in u['text']]
    state = settle(state, root, p, basis='EXPLICIT_SUPERSESSION', proofs=proof_rows)
    state = refresh(state, root)
    expected = int((Decimal('1501') * Decimal('0.110')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) * 100)
    result = calculate(state, root)
    assert result['expected_cents'] == expected and len(state['occurrences']) == 3
    assert result['readiness']['tariff']['contract_id'] == 'TERMS-Revision'
    assert previous in disp.excluded_ids(state)


def test_duplicate_atom_can_refresh_same_occurrence_identity(tmp_path):
    from againward.documents.contracts import SourceBatch
    state, root, iid, *_ = case(tmp_path)
    original = next(k for k, r in state['observations'].items() if r['field'] == 'quantity')
    atom = state['observations'][original]
    body = {'observations': [{'field': 'quantity', 'value': '1501', 'group': 'copy',
                             'location': atom['location'], 'quote': '1501'}], 'limitations': []}
    digest = read_source(SourceBatch.from_dict(state['batch']), atom['source_id'], root, model='SCRIPTED',
                         boundary=ModelBoundary(lambda *_: json.dumps(body).encode()), role='RECOVERY')
    state = commit_event(state, {'type': 'READ', 'receipt_sha256': digest}, root)
    replacement = next(k for k, r in state['observations'].items() if r['field'] == 'quantity' and k != original)
    state = settle(state, root, proposal(original, 'DUPLICATE', replacements=[replacement]), basis='DUPLICATE_CONTENT')
    ids = [replacement if k == original else k for k in state['occurrences'][iid]['evidence_ids']]
    state = action(state, root, 'DECLARE_INVOICE', evidence_ids=ids)
    assert iid in disp.active_occurrences(state) and original not in state['occurrences'][iid]['evidence_ids']
    assert len(state['occurrences']) == 2 and original in state['observations']
    state = refresh(state, root)
    assert calculate(state, root)['expected_cents'] == 18462


def test_two_delivery_points_never_become_decorative_or_an_arbitrary_single_selection(tmp_path):
    prep = tmp_path / 'prep'
    prep.mkdir()
    case(prep)
    content = (prep / 'input/invoice.txt').read_text() + '\npdl: 98765432109876'
    state, root, sid = multi_source(tmp_path, 'two-points.txt', content)
    ids = [k for k, r in state['observations'].items() if r['source_id'] == sid and
           not (r['field'] == 'pdl' and r['value'] == '98765432109876')]
    with pytest.raises(BillingFailure, match='OCCURRENCE_AMBIGUOUS'):
        action(state, root, 'DECLARE_INVOICE', evidence_ids=ids)
    pdl = next(k for k, r in state['observations'].items() if r['source_id'] == sid and r['field'] == 'pdl')
    with pytest.raises(BillingFailure, match='BUSINESS_AMBIGUITY'):
        settle(state, root, proposal(pdl, 'IRRELEVANT'), basis='DECORATIVE')
    assert not readiness(state, root)['ready']


def test_disposition_native_proof_error_has_one_repair_without_domain_mutation(tmp_path):
    state, root, sid = multi_source(tmp_path, 'memo.txt', 'Decorative logistics memo.')
    p = proposal(sid, 'IRRELEVANT')
    originals = disp.contexts(disp.dependencies(state, p), state, root)
    unit = originals[0]['units'][0]
    calls = 0

    def transport(prompt, schema):
        nonlocal calls
        calls += 1
        assert load_state(root) == state
        return json.dumps({'verdict': 'SUPPORTED', 'basis': 'DECORATIVE', 'coverage': 'ALL_MATERIAL_FACTS_ACCOUNTED',
            'reason': 'Original decorative-only memo.', 'proofs': [{'source_id': sid,
                'location': 'line:999' if calls == 1 else unit['location'], 'quote': unit['text']}]}).encode()

    boundary = ModelBoundary(transport)
    digest = disp.request_disposition(state, p, root, model='SCRIPTED', boundary=boundary)
    assert calls == 2 and boundary.diagnostics[0]['path'] == '$.proofs'
    assert load_state(root) == state
    updated = commit_event(state, {'type': 'DISPOSITION', 'receipt_sha256': digest}, root)
    assert sid in disp.excluded_ids(updated)


def test_disposition_receipt_tampering_refuses_replay(tmp_path):
    state, root, sid = multi_source(tmp_path, 'memo.txt', 'Decorative logistics memo.')
    state = settle(state, root, proposal(sid, 'IRRELEVANT'), basis='DECORATIVE')
    digest = state['dispositions'][sid]['receipt_sha256']
    path = root / 'energy_billing/dispositions' / (digest + '.json')
    row = json.loads(path.read_text())
    row['proofs'][0]['start'] += 1
    path.write_text(json.dumps(row))
    with pytest.raises(BillingFailure, match='EVIDENCE_BINDING_INVALID'):
        load_state(root)


@pytest.mark.parametrize('which', ['source', 'observation'])
def test_financial_content_cannot_be_dismissed_as_decorative(tmp_path, which):
    state, root, iid, *_ = case(tmp_path)
    key = state['occurrences'][iid]['source_id'] if which == 'source' else next(k for k, r in state['observations'].items() if r['field'] == 'quantity')
    original = (root / 'energy_billing/state.json').read_bytes()
    with pytest.raises(BillingFailure, match='BUSINESS_AMBIGUITY'):
        settle(state, root, proposal(key, 'IRRELEVANT'), basis='DECORATIVE')
    assert (root / 'energy_billing/state.json').read_bytes() == original


def test_later_positive_facts_review_cannot_erase_pending_disposition(tmp_path):
    bad = {'field': 'note', 'value': 'possible credit', 'group': 'bad', 'location': 'line:999', 'quote': 'Unbound financial text'}
    state, root, iid, _, rid = case(tmp_path, bad_atom=bad)
    qid = next(iter(state['quarantine']))
    state = settle(state, root, proposal(qid, 'IRRELEVANT'), verdict='AMBIGUOUS', basis='UNRESOLVED')
    state = receipt(state, iid, root)
    state = receipt(state, rid, root)
    assert not readiness(state, root)['ready']
    assert readiness(state, root)['root_issues'][0]['stage'] == 'DISPOSITION'


def test_reworded_decision_does_not_stale_review_or_count_as_progress(tmp_path):
    bad = {'field': 'quantity', 'value': '999', 'group': 'bad', 'location': 'line:999', 'quote': 'Invented 999'}
    state, root, iid, tid, rid = case(tmp_path, bad_atom=bad)
    qid = next(iter(state['quarantine']))
    good = next(k for k, r in state['observations'].items() if r['field'] == 'quantity')
    p = proposal(qid, replacements=[good])
    before = settle(state, root, p)
    before = receipt(before, iid, root)
    before = receipt(before, rid, root)
    after = settle(before, root, {**p, 'reason': 'A different proposal formulation.'}, reason='Same decision, new words.')
    assert semantic_hash(before) == semantic_hash(after) and not semantic_progress(before, after)
    assert current_review(after, iid, root)['verdict'] == current_review(after, tid, root)['verdict'] == 'SUPPORTED'


def test_same_material_receipt_is_idempotent(tmp_path):
    q = {'field': 'quantity', 'value': '999', 'group': 'bad', 'location': 'line:999', 'quote': 'Invented 999'}
    state, root, *_ = case(tmp_path, bad_atom=q)
    qid = next(iter(state['quarantine']))
    good = next(k for k, r in state['observations'].items() if r['field'] == 'quantity')
    state = settle(state, root, proposal(qid, replacements=[good]))
    digest = state['dispositions'][qid]['receipt_sha256']
    assert commit_event(state, {'type': 'DISPOSITION', 'receipt_sha256': digest}, root) == state


@pytest.mark.parametrize('decision,basis', [('IRRELEVANT', 'DECORATIVE'), ('REJECTED_WITH_EVIDENCE', 'EXTRACTION_ERROR')])
def test_one_invalid_atom_cannot_justify_discarding_source(tmp_path, decision, basis):
    bad = {'field': 'quantity', 'value': '999', 'group': 'bad', 'location': 'line:999', 'quote': 'Invented 999'}
    state, root, iid, *_ = case(tmp_path, bad_atom=bad)
    sid = state['occurrences'][iid]['source_id']
    with pytest.raises(BillingFailure, match='BUSINESS_AMBIGUITY'):
        settle(state, root, proposal(sid, decision), basis=basis)


def test_wrong_field_replacement_and_direct_intent_are_nonmutating(tmp_path):
    bad = {'field': 'quantity', 'value': '999', 'group': 'bad', 'location': 'line:999', 'quote': 'Invented 999'}
    state, root, *_ = case(tmp_path, bad_atom=bad)
    qid = next(iter(state['quarantine']))
    price = next(k for k, r in state['observations'].items() if r['field'] == 'tariff_price')
    original = (root / 'energy_billing/state.json').read_bytes()
    with pytest.raises(BillingFailure, match='MODEL_PROTOCOL_INVALID'):
        settle(state, root, proposal(qid, replacements=[price]))
    good = next(k for k, r in state['observations'].items() if r['field'] == 'quantity')
    with pytest.raises(BillingFailure, match='MODEL_PROTOCOL_INVALID'):
        action(state, root, 'REQUEST_DISPOSITION', **{k: v for k, v in proposal(qid, replacements=[good]).items() if k != 'type'})
    assert (root / 'energy_billing/state.json').read_bytes() == original


def test_loop_routes_material_quarantine_to_independent_decision(tmp_path):
    bad = {'field': 'quantity', 'value': '999', 'group': 'bad', 'location': 'line:999', 'quote': 'Invented 999'}
    state, root, *_ = case(tmp_path, bad_atom=bad, reviews=False)
    qid = next(iter(state['quarantine']))

    def transport(prompt, schema):
        data = context(prompt)
        if schema == ACTION_SCHEMA and data['issue']['code'] == 'MATERIAL_QUARANTINE':
            good = next(k for k, r in data['observations'].items() if r['field'] == 'quantity')
            return json.dumps({'issue_id': data['issue']['issue_id'], 'action': proposal(qid, replacements=[good], evidence=[good])}).encode()
        if schema == DISPOSITION_REVIEW_SCHEMA:
            unit = next(u for c in data['original_sources'] for u in c['units'] if u['text'].startswith('quantity:'))
            return json.dumps({'verdict': 'SUPPORTED', 'basis': 'EXTRACTION_ERROR', 'coverage': 'ALL_MATERIAL_FACTS_ACCOUNTED',
                               'reason': 'The invalid row is replaced by the original exact quantity.',
                               'proofs': [{'source_id': unit['source_id'], 'location': unit['location'], 'quote': unit['text']}]}).encode()
        return scripted(prompt, schema)

    result = investigate(root, model='SCRIPTED', transport=transport)
    assert result['terminal_reason']['code'] == 'CALCULATION_CREATED'
    assert result['steps'][0]['action']['type'] == 'REQUEST_DISPOSITION'
    assert result['steps'][0]['progress'] is True
    assert load_state(root)['quarantine'] == state['quarantine']
    assert result['calculation']['expected_cents'] == 18462


def test_decorative_source_requires_individual_resolution_of_wrong_financial_atom(tmp_path):
    from againward.documents.contracts import SourceBatch
    state, root, sid = multi_source(tmp_path, 'memo.txt', 'note: Logistics meeting at 15:00.')
    body = {'observations': [{'field': 'quantity', 'value': '15', 'group': 'wrong',
                             'quote': '15:00', 'location': 'line:1'}], 'limitations': []}
    digest = read_source(SourceBatch.from_dict(state['batch']), sid, root, model='SCRIPTED',
                         boundary=ModelBoundary(lambda *_: json.dumps(body).encode()), role='RECOVERY')
    state = commit_event(state, {'type': 'READ', 'receipt_sha256': digest}, root)
    wrong = next(k for k, r in state['observations'].items() if r['source_id'] == sid and r['field'] == 'quantity')
    with pytest.raises(BillingFailure, match='BUSINESS_AMBIGUITY'):
        settle(state, root, proposal(sid, 'IRRELEVANT'), basis='DECORATIVE')
    state = settle(state, root, proposal(wrong, 'REJECTED_WITH_EVIDENCE'))
    state = settle(state, root, proposal(sid, 'IRRELEVANT'), basis='DECORATIVE')
    state = refresh(state, root)
    assert calculate(state, root)['expected_cents'] == 18462
    assert {sid, wrong} <= disp.excluded_ids(state)
    assert load_state(root) == state
    # Reopening the atom removes the source decision's dependency, locally.
    state = settle(state, root, proposal(wrong, 'UNRESOLVED'), verdict='AMBIGUOUS', basis='UNRESOLVED')
    assert sid not in disp.excluded_ids(state) and not readiness(state, root)['ready']
    assert state['observations'][wrong]['value'] == '15'


def test_explicit_supersession_never_replaces_a_different_delivery_point(tmp_path):
    prep = tmp_path / 'prep'
    prep.mkdir()
    case(prep)
    content = (prep / 'input/tariff.txt').read_text().replace('TERMS-Generic', 'TERMS-New').replace('12345678901234', '98765432109876')
    state, root, replacement = multi_source(tmp_path, 'different-site.txt', content)
    previous = next(r['source_id'] for r in state['occurrences'].values() if r['kind'] == 'TARIFF' and r['source_id'] != replacement)
    with pytest.raises(BillingFailure, match='BUSINESS_AMBIGUITY'):
        settle(state, root, proposal(previous, replacements=[replacement]), basis='EXPLICIT_SUPERSESSION')
    assert not state.get('dispositions') and len(disp.active_occurrences(state)) == 3
