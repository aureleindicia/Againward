"""Generic scoped evidence tests; no known dossier/oracle and no live E2E."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from againward.documents.contracts import DocumentError, SourceBatch
from againward.documents.extraction import promote_facts, replay_extraction
from againward.documents.resolution import entities_from_facts
from againward.domains.rental.document_adapter import load_document_case
from againward.domains.rental.scope_review import (classification_plan, make_scope_receipt,
    validate_scope_receipt, review_package_scope)
from againward.domains.rental.rate_dimensions import rate_dimensions
from againward.documents.model_protocol import normalize_read
from tests.test_rental_document_adapter import packet


def reviewed(package, root):
    batch = SourceBatch.from_dict(package['batch'])
    extractions = tuple(replay_extraction(e, batch, root) for e in package['extractions'])
    facts = promote_facts(extractions, package['fact_review'], batch, root)
    return batch, extractions, entities_from_facts(facts)


def supported(request, value='RENTAL'):
    return {'value': value, 'evidence_indices': list(range(1, len(request['facts'])+1)),
            'reason': 'Reviewed line wording and linked explicit commercial terms support this classification.'}


def test_cross_source_classification_keeps_both_provenances_and_requires_review(tmp_path):
    source, package = packet(tmp_path, omit_invoice_fields={'charge_type'})
    batch, extractions, entities = reviewed(package, source.parent)
    requests = classification_plan(entities, extractions)
    assert len(requests) == 1
    assert len({f['candidate']['source_id'] for f in requests[0]['facts']}) == 2
    with pytest.raises(DocumentError, match='EXTRACTION_INCOMPLETE'):
        load_document_case(package, source.parent)
    receipt = make_scope_receipt(requests, [[supported(requests[0])]*2], model='scripted-review')
    package['scope_review'] = receipt
    canonical, lineage = load_document_case(package, source.parent)
    assert canonical.actual_charges[0].charge_type == 'RENTAL'
    assert len({r.document_id for r in canonical.actual_charges[0].evidence_refs}) == 2
    assert lineage['package_classifications'][0]['value'] == 'RENTAL'
    invoice_source = requests[0]['source_id']
    assert not any(f['candidate']['semantic_type'] == 'charge_type' and
                   f['candidate']['source_id'] == invoice_source for f in lineage['facts'])
    assert canonical.actual_charges[0].net_amount == '850.00'
    assert receipt['human_approval'] is False and receipt['authority_granted'] is False
    from againward.domains.rental.document_evidence import append_document_evidence
    rows, refs = [], {}
    append_document_evidence(canonical, lineage, rows, refs)
    claim, = [r for r in rows if r['record_type'] == 'package_classification']
    assert {r['source_id'] for r in refs[str(claim['source_row'])]} == {
        f['candidate']['source_id'] for f in requests[0]['facts']}


def test_agreement_rate_classification_is_not_restricted_to_invoice_lines(tmp_path):
    source, package = packet(tmp_path, omit_contract_fields={'charge_type'})
    _, extractions, entities = reviewed(package, source.parent)
    request, = classification_plan(entities, extractions)
    assert request['entity_kind'] == 'RENTAL_SCOPE'
    package['scope_review'] = make_scope_receipt([request], [[supported(request)]*2], model='scripted')
    case, _ = load_document_case(package, source.parent)
    assert case.terms[0].charge_type == 'RENTAL'


@pytest.mark.parametrize('second', [None, 'TRANSPORT'])
def test_missing_or_conflicting_meaning_cannot_reach_canonical_case(tmp_path, second):
    source, package = packet(tmp_path, omit_invoice_fields={'charge_type'})
    _, es, entities = reviewed(package, source.parent)
    requests = classification_plan(entities, es)
    package['scope_review'] = make_scope_receipt(requests,
        [[supported(requests[0]), supported(requests[0], second)]], model='scripted') if second is None else None
    if second is not None:
        # Cited reviewed RENTAL cannot be normalized to TRANSPORT.
        with pytest.raises(DocumentError, match='EXTRACTION_CONTRADICTION'):
            make_scope_receipt(requests, [[supported(requests[0]), supported(requests[0], second)]], model='scripted')
    with pytest.raises(DocumentError, match='EXTRACTION_INCOMPLETE'):
        load_document_case(package, source.parent)


def test_scope_review_cannot_revive_rejected_classification(tmp_path):
    source, package = packet(tmp_path)
    for decision in package['fact_review']['decisions']:
        if decision['candidate_id'].endswith(':charge_type'):
            decision['decision'] = 'REJECT'
    _, es, entities = reviewed(package, source.parent)
    with pytest.raises(DocumentError, match='Rejected classification'):
        classification_plan(entities, es)


def test_scope_review_binds_current_evidence_and_requires_local_premise(tmp_path):
    source, package = packet(tmp_path, omit_invoice_fields={'charge_type'})
    _, es, entities = reviewed(package, source.parent)
    requests = classification_plan(entities, es)
    request = requests[0]
    foreign_only = [i+1 for i,f in enumerate(request['facts']) if f['fact_id'] not in request['local_fact_ids']]
    with pytest.raises(DocumentError, match='UNSUPPORTED_PROMOTION'):
        make_scope_receipt(requests, [[{**supported(request), 'evidence_indices': foreign_only}]*2], model='scripted')
    receipt = make_scope_receipt(requests, [[supported(request)]*2], model='scripted')
    receipt['decisions'][0]['value'] = 'FUEL'
    with pytest.raises(DocumentError, match='REVIEW_STALE'):
        validate_scope_receipt(entities, es, receipt)


def test_independent_scope_calls_do_not_see_other_answer(tmp_path, monkeypatch):
    source, package = packet(tmp_path, omit_invoice_fields={'charge_type'})
    batch, es, entities = reviewed(package, source.parent)
    request, = classification_plan(entities, es)
    prompts = []
    def ask(prompt, images, **kwargs):
        assert 'secret-first-answer' not in prompt
        assert 'request_sha256' not in prompt and 'entity_evidence_hashes' not in prompt
        assert 'fact_id' not in prompt and 'review_sha256' not in prompt
        assert '"ref": "e1"' in prompt
        prompts.append(prompt)
        return {'value': 'equipment rental', 'evidence_refs': [f'e{i}' for i in range(1,len(request['facts'])+1)],
                'reason': 'secret-first-answer'}, 0.1
    monkeypatch.setattr('againward.domains.rental.scope_review._ask', ask)
    receipt = review_package_scope(batch, es, package['fact_review'], source.parent, model='scripted', timeout_seconds=20)
    assert len(prompts) == 2 and prompts[0] == prompts[1]
    assert receipt['model_calls'] == 2


@pytest.mark.parametrize('text,unit,basis,calendar', [
    ('per asset per calendar day','DAY','PER_ITEM',True),
    ('PER_ASSET_PER_CALENDAR_DAY','DAY','PER_ITEM',True),
    ('per week and per item','WEEK','PER_ITEM',None),
    ('asset-days','DAY','PER_ITEM',None),
    ('per fleet per calendar day','DAY','PER_SCOPE',True),
    ('per lot per month','MONTH','PER_SCOPE',None),
])
def test_rate_denominator_dimensions_are_not_collapsed(text, unit, basis, calendar):
    d = rate_dimensions(text)
    assert d['billing_unit'] == unit and d['quantity_basis'] == basis
    assert d.get('weekends_billable') == calendar


@pytest.mark.parametrize('value', [None, 'per tonne per day', 'per business day', 'UNKNOWN', 'per day or per trip',
                                  'per asset per calendar week', 'per lot per calendar month'])
def test_unknown_or_ambiguous_units_are_not_guessed(value):
    assert rate_dimensions(value) is None


@pytest.mark.parametrize('visual', [False, True])
def test_native_visual_dimension_observations_keep_exact_evidence(visual):
    row = {'semantic_type': 'billing_unit', 'value': 'per item per calendar day',
           'entity_hint': 'row', 'visible_text': 'EUR 12 per item per calendar day', 'page': 1} if visual else {
           'semantic_type': 'billing_unit', 'value': 'per item per calendar day', 'entity_hint': 'row',
           'raw_observed_value': 'EUR 12 per item per calendar day', 'location': 'line:1'}
    key = 'observations' if visual else 'candidates'
    parsed = SimpleNamespace(units=[SimpleNamespace(route='VISUAL' if visual else 'NATIVE', location='line:1')])
    result = normalize_read({key:[row]}, parsed, rental=True)[key]
    assert {r['semantic_type']:r['value'] for r in result} == {
        'billing_unit':'DAY','quantity_basis':'PER_ITEM','weekends_billable':True}
    assert all(r.get('visible_text',r.get('raw_observed_value')) == 'EUR 12 per item per calendar day' for r in result)


def test_billing_unit_conflict_has_structured_package_diagnostic(tmp_path):
    source, package = packet(tmp_path)
    # Test isolated canonical boundary using a reviewed unsupported unit.
    from againward.evidence.hashing import stable_hash
    for e in package['extractions']:
        for c in e['candidates']:
            if c['semantic_type'] == 'billing_unit':
                c['value'] = 'PER_TONNE_PER_DAY'
        e['extraction_sha256'] = stable_hash({k:v for k,v in e.items() if k != 'extraction_sha256'})
    package['fact_review']['extraction_hashes'] = sorted(e['extraction_sha256'] for e in package['extractions'])
    with pytest.raises(DocumentError) as caught:
        load_document_case(package, source.parent)
    assert caught.value.diagnostic['validation_code'] == 'UNSUPPORTED_RATE_DIMENSION'
    assert caught.value.diagnostic['schema_path'] == '$.terms[0].billing_unit'


def test_source_adjudication_context_and_citation_identity_are_local(tmp_path, monkeypatch):
    from tests.test_document_adjudication import _case
    from againward.documents.adjudication import adjudicate_with_codex
    root,batch,primary,challenger,qa,raw,email = _case(tmp_path)
    def ask(command, *, input, **kwargs):
        assert 'an off-hire request alone does not stop billing.' not in input
        assert '--image' not in command
        schema = json.loads(Path(command[command.index('--output-schema')+1]).read_text())
        assert 'source_id' not in schema['properties']['citations']['items']['properties']
        answer = deepcopy(raw['decisions'][0])
        answer.pop('source_id')
        answer['citations'] = [answer['citations'][0]]
        answer['citations'][0].pop('source_id')
        answer['citations'][0].pop('preview_sha256')
        answer.update(candidate_selections=[],native_observations=[])
        Path(command[command.index('--output-last-message')+1]).write_text(json.dumps(answer))
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr('againward.documents.adjudication.subprocess.run',ask)
    receipt=adjudicate_with_codex(batch,primary,challenger,qa,root,model='scripted')
    assert receipt['decisions'][0]['citations'][0]['source_id'] == email.source_id


def test_forged_foreign_citation_is_rejected_even_if_other_source_exists(tmp_path):
    from tests.test_document_adjudication import _case
    from againward.documents.adjudication import bind_model_citations
    _, _, _, _, _, raw, email = _case(tmp_path)
    with pytest.raises(DocumentError) as caught:
        bind_model_citations(raw, [], focused_source_id=email.source_id)
    assert caught.value.code == 'SOURCE_LOCATION_INVALID'
    assert caught.value.diagnostic['validation_code'] == 'FOREIGN_SOURCE_CITATION'


def test_scope_review_source_mutation_invalidates_prior_review(tmp_path):
    source, package = packet(tmp_path, omit_invoice_fields={'charge_type'})
    batch, es, entities = reviewed(package, source.parent)
    requests = classification_plan(entities, es)
    package['scope_review'] = make_scope_receipt(requests, [[supported(requests[0])]*2], model='scripted')
    (source.parent / batch.documents[0].blob_path).write_text('changed original')
    with pytest.raises(DocumentError, match='SOURCE_CHANGED'):
        load_document_case(package, source.parent)


def test_many_invoices_can_reference_one_scope_without_combining_their_claims(tmp_path):
    source, package = packet(tmp_path, omit_invoice_fields={'charge_type'})
    _, es, entities = reviewed(package, source.parent)
    invoice = next(e for e in entities if e.kind == 'INVOICE_LINE')
    # Pure resolver unit test: a second reviewed occurrence with separate fact IDs.
    peer_facts = tuple(replace(f, fact_id=f.fact_id+'-peer', candidate=replace(f.candidate,
        candidate_id=f.candidate.candidate_id+'-peer', entity_id='peer')) for f in invoice.facts)
    peer = replace(invoice, entity_id=invoice.entity_id+'-peer', local_id='peer', facts=peer_facts)
    requests = classification_plan((*entities, peer), es)
    assert len(requests) == 2
    assert all(len(r['relationships']) == 1 for r in requests)
    assert requests[0]['relationships'][0]['right'] == requests[1]['relationships'][0]['right']
    assert not set(requests[0]['local_fact_ids']) & set(requests[1]['local_fact_ids'])
    assert classification_plan(tuple(reversed((*entities, peer))), es) == requests


def test_conflicting_entity_identifiers_do_not_supply_cross_source_proof(tmp_path):
    source, package = packet(tmp_path, omit_invoice_fields={'charge_type'})
    _, es, entities = reviewed(package, source.parent)
    revised = tuple(replace(e, facts=tuple(replace(f, candidate=replace(f.candidate, value='OTHER-VENDOR'))
                     if f.candidate.semantic_type == 'supplier_id' else f for f in e.facts))
                    if e.kind == 'INVOICE_LINE' else e for e in entities)
    request, = classification_plan(revised, es)
    assert not request['relationships']
    assert {f['candidate']['source_id'] for f in request['facts']} == {request['source_id']}


def test_distinct_quantity_bases_use_explicit_quantities_without_changing_rate():
    from tests.rental_fixtures import rental_packet
    from tests.test_rental_pricing import expected
    body = rental_packet()
    body['periods'][0]['quantity'] = '3'
    term = body['terms'][0]
    term.update(billing_unit='DAY', rate='11', quantity_basis='PER_ITEM')
    term.pop('quantity')
    entry = expected(body)[0]
    assert entry['quantity'] == '3' and entry['rate'] == '11' and entry['amount'] == '231.00'
    term['quantity_basis'] = 'PER_SCOPE'
    entry = expected(body)[0]
    assert entry['quantity'] == '1' and entry['rate'] == '11' and entry['amount'] == '77.00'
    term['quantity'] = '3'
    entry = expected(body)[0]
    assert entry['amount'] is None and 'scope_rate_quantity_conflict' in entry['limitations']


@pytest.mark.parametrize('basis', ['PER_ITEM', 'PER_SCOPE'])
def test_percentage_cannot_silently_discard_explicit_quantity_basis(basis):
    from tests.rental_fixtures import rental_packet
    from tests.test_rental_pricing import expected
    body = rental_packet()
    body['terms'].append({**body['terms'][0], 'term_id': 'fee', 'charge_key': 'fee',
        'charge_type': 'DAMAGE_WAIVER', 'billing_unit': 'PERCENT', 'rate': '8',
        'percentage_of': 'hire', 'quantity_basis': basis})
    fee = next(e for e in expected(body) if e['charge_key'] == 'fee')
    assert fee['amount'] is None
    assert 'percentage_quantity_basis_requires_review' in fee['limitations']


def test_partial_return_cannot_convert_scope_rate_to_per_item_rate():
    from tests.rental_fixtures import rental_packet
    from tests.test_rental_pricing import expected, add_return
    body = rental_packet()
    body['periods'][0]['quantity'] = '3'
    body['terms'][0].update(billing_unit='DAY', quantity_basis='PER_SCOPE', quantity='1')
    add_return(body, quantity='1')
    entry = expected(body)[0]
    assert entry['amount'] is None
    assert 'scope_rate_daily_segments_requires_review' in entry['limitations']


def test_controlled_internal_value_error_persists_sanitized_stage(tmp_path, monkeypatch):
    from againward.core.workspace import create_client_workspace
    from againward.domains.rental.source_job import run_approved_sources_job
    create_client_workspace('case', root=tmp_path, synthetic=True, domain_name='rental', intake_payload={})
    case = tmp_path/'case'
    (case/'incoming/source.txt').write_text('synthetic input')
    def broken(*args, **kwargs):
        raise ValueError('PRIVATE-RAW-SOURCE-STRING')
    monkeypatch.setattr('againward.domains.rental.source_job.inventory_sources', broken)
    result = run_approved_sources_job(case, model='scripted')
    assert result['status'] == 'FAILED' and result['diagnostic']['validation_code'] == 'INTERNAL_VALUE_ERROR'
    assert result['stage'] == 'SOURCE_INTAKE'
    saved = (case/'processed/source_job_state.json').read_text()
    assert 'PRIVATE-RAW-SOURCE-STRING' not in saved
    assert 'INTERNAL_VALUE_ERROR' in saved
