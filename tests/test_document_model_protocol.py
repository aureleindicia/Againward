"""Generic protocol variance must not create authority or bypass evidence review."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from againward.documents.model_protocol import load_model_json, normalize_read, normalize_decision
from againward.documents.codex_provider import assemble_proposal, CodexCliProvider
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal, promote_facts, replay_extraction
from againward.documents.adjudication import bind_model_citations, validate_adjudication
from againward.documents.independent_qa import compare_extractions
from againward.documents.analyst_review import build_analyst_review
from againward.domains.rental.entity_contract import normalize_document_envelopes
from againward.domains.rental.extraction_validation import validate_rental_extraction, package_source_gaps
from againward.domains.rental.semantic_guidance import guidance
from tests.test_document_codex_provider import _source, _raw
from tests.test_rental_architecture import _fixture, CONTENT
from tests.test_document_analyst_review import _native_decisions


@pytest.mark.parametrize('alias', ['DAY', 'day', 'daily', 'calendar_day', 'calendar-day', 'DAYS'])
def test_unit_aliases_have_identical_canonical_meaning_and_unchanged_evidence(alias):
    row = {'entity_id': 'scope', 'semantic_type': 'billing_unit', 'value_type': 'TEXT',
           'value': alias, 'raw_observed_value': 'per calendar day', 'location': 'line:1'}
    parsed = SimpleNamespace(units=[SimpleNamespace(route='NATIVE', location='line:1', text='per calendar day')])
    normalized = normalize_read({'candidates': [row]}, parsed, rental=True)['candidates'][0]
    assert normalized['value'] == 'DAY' and normalized['value_type'] == 'ENUM'
    assert normalized['raw_observed_value'] == row['raw_observed_value']
    assert normalized['location'] == row['location']


@pytest.mark.parametrize('visual', [False, True])
def test_composite_rate_projection_matches_exact_wording_for_native_and_visual(visual):
    quote = 'EUR 50.00 per asset per calendar day'
    parsed = SimpleNamespace(units=[SimpleNamespace(
        route='VISUAL' if visual else 'NATIVE', location='page:1' if visual else 'line:1', text=quote)])
    row = {'entity_hint': 'term', 'semantic_type': 'billing_unit',
        'value': 'per calendar day', 'raw_observed_value': quote,
        'visible_text': quote, 'location': 'page:1' if visual else 'line:1', 'page': 1}
    key = 'observations' if visual else 'candidates'
    result = normalize_read({key: [row]}, parsed, rental=True)[key]
    assert {item['semantic_type']: item['value'] for item in result} == {
        'billing_unit': 'DAY', 'quantity_basis': 'PER_ITEM', 'weekends_billable': True}
    assert all(item.get('visible_text', item.get('raw_observed_value')) == quote for item in result)


@pytest.mark.parametrize('visual', [False, True])
def test_split_rate_dimensions_are_reconciled_from_their_same_exact_quote(visual):
    quote = 'per asset per calendar day'
    group_key = 'entity_hint'
    rows = [
        {group_key: 'commercial-term', 'semantic_type': 'billing_unit', 'value': 'DAY',
         'raw_observed_value': quote, 'visible_text': quote, 'location': 'line:4', 'page': 1},
        {group_key: 'commercial-term', 'semantic_type': 'quantity_basis', 'value': 'PER_ASSET',
         'raw_observed_value': quote, 'visible_text': quote, 'location': 'line:4', 'page': 1},
    ]
    if visual:
        raw, parsed = {'observations': rows}, SimpleNamespace(units=[
            SimpleNamespace(route='VISUAL', location='page:1', text='')])
        key = 'observations'
    else:
        raw, parsed = {'candidates': rows}, SimpleNamespace(units=[
            SimpleNamespace(route='NATIVE', location='line:4', text=quote)])
        key = 'candidates'
    normalized = normalize_read(raw, parsed, rental=True)[key]
    dimensions = {row['semantic_type']: row['value'] for row in normalized}
    assert dimensions == {'billing_unit': 'DAY', 'quantity_basis': 'PER_ITEM',
                          'weekends_billable': True}
    assert all(row.get('visible_text', row.get('raw_observed_value')) == quote for row in normalized)
    assert all(row.get('page') == 1 for row in normalized) if visual else all(
        row.get('location') == 'line:4' for row in normalized)


def test_conflicting_rate_basis_is_quarantined_and_quote_dimensions_survive():
    parsed = SimpleNamespace(units=[SimpleNamespace(route='NATIVE', location='line:4',
                                                      text='per asset per calendar day')])
    raw = {'candidates': [
        {'entity_hint': 'term', 'semantic_type': 'billing_unit', 'value': 'DAY',
         'raw_observed_value': 'per asset per calendar day', 'location': 'line:4'},
        {'entity_hint': 'term', 'semantic_type': 'quantity_basis', 'value': 'PER_SCOPE',
         'raw_observed_value': 'per asset per calendar day', 'location': 'line:4'},
    ]}
    normalized = normalize_read(raw, parsed, rental=True)
    assert normalized['status'] == 'NEEDS_REVIEW'
    assert {row['semantic_type']: row['value'] for row in normalized['candidates']} == {
        'billing_unit': 'DAY', 'quantity_basis': 'PER_ITEM', 'weekends_billable': True}
    assert normalized['_againward_rejected_observations'][0]['rejection_code'] == (
        'RATE_DIMENSION_EVIDENCE_CONFLICT')
    assert normalized['_againward_rejected_observations'][0]['quote_dimensions_recovered'] is True
    assert 'value_sha256' in normalized['_againward_rejected_observations'][0]
    assert 'raw_observed_value' not in normalized['_againward_rejected_observations'][0]


def test_conflicting_model_rate_value_is_rebuilt_from_exact_native_quote_before_binding(tmp_path):
    quote = 'Rental rate EUR 12 per asset per calendar day'
    root, batch, document, parsed = _source(tmp_path, quote)
    raw = {'status': 'SUCCESS', 'limitations': [], 'candidates': [{
        'entity_id': 'local-term', 'semantic_type': 'billing_unit', 'value_type': 'ENUM',
        'value': 'WEEK', 'raw_observed_value': quote,
        'location': parsed.units[0].location, 'normalization_notes': '', 'ambiguity_flags': []}]}
    normalized = normalize_read(raw, parsed, rental=True)
    normalized.pop('_againward_rejected_observations')
    proposal = assemble_proposal(normalized, document, parsed, batch.batch_id, 'synthetic-model')
    extraction = validate_proposal(proposal, batch, root)
    dimensions = {candidate.semantic_type: candidate.value for candidate in extraction.candidates}
    assert dimensions == {'billing_unit': 'DAY', 'quantity_basis': 'PER_ITEM',
                         'weekends_billable': True}
    assert all(candidate.raw_observed_value == quote for candidate in extraction.candidates)
    assert all(candidate.source_span == (0, len(quote)) for candidate in extraction.candidates)


def test_composite_basis_conflict_isolated_without_overriding_source_quote():
    quote = 'per fleet per calendar day'
    parsed = SimpleNamespace(units=[SimpleNamespace(route='NATIVE', location='line:8', text=quote)])
    raw = {'candidates': [{'entity_id': 'term', 'semantic_type': 'billing_unit',
        'value': 'per item per calendar day', 'raw_observed_value': quote, 'location': 'line:8'}]}
    normalized = normalize_read(raw, parsed, rental=True)
    assert normalized['status'] == 'NEEDS_REVIEW'
    assert {row['semantic_type']: row['value'] for row in normalized['candidates']} == {
        'billing_unit': 'DAY', 'quantity_basis': 'PER_SCOPE', 'weekends_billable': True}
    assert normalized['_againward_rejected_observations'][0]['rejection_code'] == (
        'RATE_DIMENSION_EVIDENCE_CONFLICT')
    assert normalized['_againward_rejected_observations'][0]['quote_dimensions_recovered'] is True


def test_multiple_explicit_rate_expressions_remain_ambiguous_and_incomplete():
    quote = 'EUR 12 per asset per day or EUR 300 per asset per month'
    parsed = SimpleNamespace(units=[SimpleNamespace(route='NATIVE', location='line:9', text=quote)])
    row = {'entity_id': 'term', 'semantic_type': 'billing_unit', 'value': 'DAY',
           'raw_observed_value': quote, 'location': 'line:9'}
    normalized = normalize_read({'candidates': [row]}, parsed, rental=True)
    assert normalized['status'] == 'PARTIAL'
    assert normalized['candidates'] == []
    rejected = normalized['_againward_rejected_observations'][0]
    assert rejected['rejection_code'] == 'AMBIGUOUS_RATE_DIMENSION_EVIDENCE'
    assert rejected['quote_dimensions_recovered'] is False


@pytest.mark.parametrize('visual', [False, True])
def test_unsupported_calendar_week_convention_fails_closed_even_if_model_decomposes_it(visual):
    quote = 'per asset per calendar week'
    rows = [
        {'entity_hint': 'term', 'semantic_type': 'billing_unit', 'value': 'WEEK',
         'raw_observed_value': quote, 'visible_text': quote, 'location': 'line:8', 'page': 1},
        {'entity_hint': 'term', 'semantic_type': 'quantity_basis', 'value': 'PER_ITEM',
         'raw_observed_value': quote, 'visible_text': quote, 'location': 'line:8', 'page': 1},
        {'entity_hint': 'term', 'semantic_type': 'weekends_billable', 'value': True,
         'raw_observed_value': quote, 'visible_text': quote, 'location': 'line:8', 'page': 1},
    ]
    key = 'observations' if visual else 'candidates'
    parsed = SimpleNamespace(units=[SimpleNamespace(
        route='VISUAL' if visual else 'NATIVE', location='line:8', text=quote)])
    with pytest.raises(DocumentError, match='unsupported calendar rate convention'):
        normalize_read({key: rows}, parsed, rental=True)


def test_unparsed_per_asset_enum_is_not_a_global_alias():
    parsed = SimpleNamespace(units=[SimpleNamespace(route='NATIVE', location='line:4', text='per asset')])
    raw = {'candidates': [{'entity_hint': 'term', 'semantic_type': 'quantity_basis',
        'value': 'PER_ASSET', 'raw_observed_value': 'per asset', 'location': 'line:4'}]}
    normalized = normalize_read(raw, parsed, rental=True)['candidates'][0]
    assert normalized['value'] == 'PER_ASSET'


@pytest.mark.parametrize(('field', 'value', 'quote', 'expected'), [
    ('billing_unit', 'DAY', 'per fleet per calendar day',
     {'billing_unit': 'DAY', 'quantity_basis': 'PER_SCOPE', 'weekends_billable': True}),
    ('quantity_basis', 'PER_SCOPE', 'per lot per month',
     {'billing_unit': 'MONTH', 'quantity_basis': 'PER_SCOPE'}),
])
def test_single_rate_observation_recovers_only_dimensions_in_its_exact_quote(
        field, value, quote, expected):
    parsed = SimpleNamespace(units=[SimpleNamespace(route='NATIVE', location='line:8', text=quote)])
    normalized = normalize_read({'candidates': [{
        'entity_id': 'term', 'semantic_type': field, 'value': value,
        'raw_observed_value': quote, 'location': 'line:8'}]}, parsed, rental=True)['candidates']
    assert {row['semantic_type']: row['value'] for row in normalized} == expected
    assert all(row['raw_observed_value'] == quote and row['location'] == 'line:8'
               for row in normalized)


def test_rate_dimension_normalization_is_idempotent_and_preserves_source_evidence():
    quote = 'Rental rate EUR 12 per asset per calendar day'
    parsed = SimpleNamespace(units=[SimpleNamespace(route='NATIVE', location='line:8', text=quote)])
    initial = {'candidates': [{'entity_hint': 'local-term', 'semantic_type': 'billing_unit',
        'value': 'per asset per calendar day', 'raw_observed_value': quote, 'location': 'line:8'}]}
    once = normalize_read(initial, parsed, rental=True)
    twice = normalize_read(once, parsed, rental=True)
    def important(result):
        return [(row['semantic_type'], row['value'], row['location'], row['raw_observed_value'],
                 row.get('unit_sha256')) for row in result['candidates']]
    assert important(once) == important(twice)
    assert {row['semantic_type']: row['value'] for row in once['candidates']} == {
        'billing_unit': 'DAY', 'quantity_basis': 'PER_ITEM', 'weekends_billable': True}


@pytest.mark.parametrize('alias,canonical', [('credit_memo', 'CREDIT_NOTE'), ('rate-sheet', 'RATE_CARD'),
                                          ('email', 'EMAIL_EVIDENCE'), ('correspondence', 'EMAIL_EVIDENCE')])
def test_document_role_synonyms_never_infer_acceptance(alias, canonical):
    p = SimpleNamespace(units=[])
    raw = {'candidates': [{'semantic_type': 'document_role', 'value': alias}]}
    row = normalize_read(raw, p, rental=True)['candidates'][0]
    assert row['value'] == canonical and row['semantic_type'] == 'document_role'
    assert 'document_status' not in json.dumps(row)


@pytest.mark.parametrize('raw', [b'{"x":1,}', b'```json\n{"x":1}\n```', b'{"x":1}'])
def test_unambiguous_serialization_is_recovered(raw):
    assert load_model_json(raw, maximum=1000) == {'x': 1}


@pytest.mark.parametrize('raw', [b'{"x":1,"x":2}', b'{"x":1', b'{"x":NaN}', b'{"x":1}{"x":2}'])
def test_ambiguous_or_truncated_serialization_fails_closed(raw):
    with pytest.raises(DocumentError):
        load_model_json(raw, maximum=1000)


def test_json_recovery_never_edits_quotes_or_rounds_decimal_tokens():
    raw = b'{"quote":"a,] b,}","amount":123456789012345678.123456789,}'
    parsed = load_model_json(raw, maximum=1000)
    assert parsed == {'quote': 'a,] b,}', 'amount': '123456789012345678.123456789'}


def test_native_binding_recovers_omitted_locator_but_never_paraphrase(tmp_path):
    root, batch, doc, parsed = _source(tmp_path)
    raw = _raw('line:1', '850.00')
    del raw['candidates'][0]['location']
    del raw['candidates'][0]['value_type']
    normalized = normalize_read(raw, parsed, rental=True)
    result = validate_proposal(assemble_proposal(normalized, doc, parsed, batch.batch_id, 'test'), batch, root)
    assert result.candidates[0].source_span == (23, 29)
    assert result.candidates[0].value == '850.00'
    raw['candidates'][0]['raw_observed_value'] = 'a net amount of 850 euros'
    bad = normalize_read(raw, parsed, rental=True)
    assert 'location' not in bad['candidates'][0]


def test_native_type_and_technical_group_are_runtime_owned(tmp_path):
    root, batch, doc, parsed = _source(tmp_path)
    raw = _raw('line:1', '850.00')
    row = raw['candidates'][0]
    row['entity_hint'] = row.pop('entity_id')
    row['value_type'] = 'CURRENCY'
    normalized = normalize_read(raw, parsed, rental=True)
    proposal = validate_proposal(assemble_proposal(normalized, doc, parsed, batch.batch_id, 'test'), batch, root)
    c = proposal.candidates[0]
    assert c.value_type == 'DECIMAL' and c.value == '850.00'
    assert c.entity_id.startswith('group-')
    assert proposal.status == 'SUCCESS'  # representation validity, no fact authority
    with pytest.raises(DocumentError):
        promote_facts((proposal,), {}, batch, root)


def test_optional_null_amount_is_withheld_not_zero_and_required_null_still_blocks(tmp_path):
    root, batch, read = _fixture(tmp_path)
    complete = read(range(7))
    parsed = SimpleNamespace(units=[])
    raw = {'candidates': [{'semantic_type': 'allocated_amount', 'value_type': 'UNKNOWN', 'value': None}]}
    assert normalize_read(raw, parsed, rental=True)['candidates'] == []
    missing = replace(complete, candidates=tuple(c for c in complete.candidates if c.semantic_type != 'net_amount'))
    with pytest.raises(DocumentError, match='STRUCTURAL_INCOMPLETE'):
        validate_rental_extraction(missing, require_package_facts=True)


def test_unknown_authority_survives_intermediate_read_but_cannot_be_selected(tmp_path):
    _root, _batch, read = _fixture(tmp_path)
    current = read(range(7))
    unknown = replace(current, candidates=tuple(replace(c, value='DECLARED') if c.semantic_type == 'document_status'
                                               else c for c in current.candidates))
    validate_rental_extraction(unknown, provisional=True, allow_incomplete=True)
    with pytest.raises(DocumentError, match='EXTRACTION_SCHEMA_INVALID'):
        validate_rental_extraction(unknown, require_package_facts=True)


@pytest.mark.parametrize('envelope', ['direct', 'singular', 'array', 'object'])
def test_single_source_decision_envelopes_bind_without_model_ids(envelope):
    row = {'selection': 'challenger', 'rationale': 'Original source supports this reading.'}
    raw = row if envelope == 'direct' else {'decision': row} if envelope == 'singular' else {
        'decisions': [row] if envelope == 'array' else row}
    result = normalize_decision(raw, source_id='source-current')
    assert result['decisions'][0]['source_id'] == 'source-current'
    assert result['decisions'][0]['selection'] == 'CHALLENGER'
    assert result['decisions'][0]['citations'] == []  # still rejected by evidence gate


def test_decision_normalization_does_not_choose_conflicting_decisions():
    raw = {'decisions': [{'selection': 'PRIMARY'}, {'selection': 'CHALLENGER'}]}
    assert normalize_decision(raw, source_id='current') == raw


def test_complementary_sparse_assembly_is_explicit_complete_and_re_reviewed(tmp_path):
    root, batch, read = _fixture(tmp_path)
    p, q = read(range(5)), read([0, 1, 2, 5, 6], 'peer')
    qa = compare_extractions(batch, (p,), (q,), root)
    includes = [{'reader': reader, 'candidate_index': i + 1, 'decision': 'INCLUDE', 'entity_id': 'joined'}
                for reader, parent in [('PRIMARY', p), ('CHALLENGER', q)]
                for i, c in enumerate(parent.candidates)
                if reader == 'PRIMARY' or c.semantic_type in {'charge_type', 'currency'}]
    raw = {'decisions': [{'source_id': p.source_id, 'selection': 'ASSEMBLE', 'rationale': 'Complementary source facts',
        'citations': [{'source_id': p.source_id, 'location': 'line:1', 'quote': CONTENT}],
        'observations': [], 'candidate_selections': includes}]}
    bound = bind_model_citations(raw, [], primary=(p,), challenger=(q,), sparse_assembly=True)
    dispositions = bound['decisions'][0]['candidate_selections']
    assert len(dispositions) == len(p.candidates) + len(q.candidates)
    assert sum(r['decision'] == 'DEFER' for r in dispositions) == 3
    result = validate_adjudication(batch, (p,), (q,), qa, bound, root, required_source_facts=package_source_gaps)
    assembled = replay_extraction(result['assembly_proposals'][p.source_id], batch, root)
    validate_rental_extraction(assembled, require_package_facts=True)
    assert result['facts_approved'] == 0
    old = build_analyst_review(batch, (p,), _native_decisions((p,)), root)['review']
    with pytest.raises(DocumentError):
        promote_facts((assembled,), old, batch, root)
    fresh_qa = compare_extractions(batch, (assembled,), (q,), root)
    assert fresh_qa['qa_sha256'] != qa['qa_sha256']
    assert fresh_qa['material_status'] == 'RECONCILIATION_REQUIRED'


def test_native_recovery_can_fill_both_readers_omission_without_approving(tmp_path):
    root, batch, read = _fixture(tmp_path)
    p, q, complete = read(range(5)), read(range(5), 'peer'), read(range(7))
    qa = compare_extractions(batch, (p,), (q,), root)
    selected = [{'reader': 'PRIMARY', 'candidate_index': i + 1, 'decision': 'INCLUDE', 'entity_id': 'joined'}
                for i in range(len(p.candidates))]
    recover = []
    for c in complete.candidates:
        if c.semantic_type in {'charge_type', 'currency'}:
            recover.append({'entity_id': 'joined', 'semantic_type': c.semantic_type, 'value_type': c.value_type,
                'value': c.value, 'location': c.location, 'raw_observed_value': c.raw_observed_value,
                'ambiguity_flags': [], 'normalization_notes': 'Reopened original source'})
    raw = {'decisions': [{'source_id': p.source_id, 'selection': 'ASSEMBLE', 'rationale': 'Reopened original text',
        'citations': [{'source_id': p.source_id, 'location': 'line:1', 'quote': CONTENT}],
        'observations': [], 'native_observations': recover, 'candidate_selections': selected}]}
    bound = bind_model_citations(raw, [], primary=(p,), challenger=(q,), sparse_assembly=True)
    result = validate_adjudication(batch, (p,), (q,), qa, bound, root, required_source_facts=package_source_gaps)
    assembled = replay_extraction(result['assembly_proposals'][p.source_id], batch, root)
    validate_rental_extraction(assembled, require_package_facts=True)
    recovered = [c for c in assembled.candidates if 'ADJUDICATOR_NATIVE_OBSERVATION' in c.ambiguity_flags]
    assert len(recovered) == 2 and all(c.source_span for c in recovered)
    assert result['facts_approved'] == 0 and not result['selected_extractions']
    assert [c.value for c in assembled.candidates if c.semantic_type == 'net_amount'] == ['730.00']
    with pytest.raises(DocumentError):
        promote_facts((assembled,), {}, batch, root)
    bad = deepcopy(bound)
    bad['decisions'][0]['native_observations'][0]['raw_observed_value'] = 'nonexistent source statement'
    partial = validate_adjudication(batch, (p,), (q,), qa, bad, root,
                                    required_source_facts=package_source_gaps)
    assert len(partial['rejected_native_recoveries']) == 1
    assert partial['rejected_native_recoveries'][0]['rejection_code'] == 'NATIVE_QUOTE_NOT_EXACT_UNIQUE'
    incomplete = replay_extraction(partial['assembly_proposals'][p.source_id], batch, root)
    # charge_type is package-relational, so source-local completeness correctly
    # defers it; the quarantined paraphrase must still create no candidate/fact.
    assert not any(c.semantic_type == 'charge_type' and c.value == 'RENTAL'
                   and 'ADJUDICATOR_NATIVE_OBSERVATION' in c.ambiguity_flags
                   for c in incomplete.candidates)
    assert package_source_gaps(incomplete) == {}
    assert partial['facts_approved'] == 0 and not partial['selected_extractions']
    # Existing package-scope gates separately require reviewed evidence before
    # canonicalization; this response is still only an unapproved assembly.


def test_redundancy_and_candidate_order_do_not_change_material_comparison(tmp_path):
    root, batch, read = _fixture(tmp_path)
    p = read(range(7))
    q = replace(p, candidates=tuple(reversed(p.candidates)) + (replace(p.candidates[-1], candidate_id='redundant'),))
    qa = compare_extractions(batch, (p,), (q,), root)
    assert not qa['source_results'][0]['material_needs_reconciliation']


def test_true_commercial_conflict_is_never_normalized_away(tmp_path):
    root, batch, read = _fixture(tmp_path)
    p = read(range(7))
    q = replace(p, candidates=tuple(replace(c, value='PROPOSED') if c.semantic_type == 'document_status'
                                   else c for c in p.candidates))
    qa = compare_extractions(batch, (p,), (q,), root)
    assert qa['source_results'][0]['material_needs_reconciliation']


def test_generic_document_envelope_cannot_merge_distinct_accounting_rows():
    rows = [{'entity_id': group, 'semantic_type': field, 'value': value}
            for group, fields in [('invoice-row', [('entity_kind', 'SUPPORTING_DOCUMENT'), ('invoice_id', 'ZX')]),
                                  ('credit-row', [('entity_kind', 'SUPPORTING_DOCUMENT'), ('credit_id', 'CY'),
                                                  ('net_amount', '20')])]
            for field, value in fields]
    assert normalize_document_envelopes({'candidates': rows}, visual=False)['candidates'] == rows


def test_native_and_visual_share_semantic_normalization_without_pixel_authority():
    n = SimpleNamespace(units=[SimpleNamespace(route='NATIVE', location='line:1', text='calendar day')])
    v = SimpleNamespace(units=[SimpleNamespace(route='VISUAL', location='page:1', text='')])
    common = {'semantic_type': 'billing_unit', 'value': 'calendar_day'}
    native = normalize_read({'candidates': [{**common, 'raw_observed_value': 'calendar day'}]}, n, rental=True)
    visual = normalize_read({'observations': [{**common, 'visible_text': 'calendar day', 'page': 1}]}, v, rental=True)
    assert native['candidates'][0]['value'] == visual['observations'][0]['value'] == 'DAY'
    assert 'source_span' not in visual['observations'][0] and 'render_sha256' not in visual['observations'][0]
    impossible = normalize_read({'observations': [{**common, 'visible_text': 'calendar day', 'page': 999}]}, v, rental=True)
    assert impossible['observations'][0]['page'] == 999  # binding must reject; never choose page 1


def test_provider_runtime_normalization_is_wired_before_exact_validation(tmp_path, monkeypatch):
    root, batch, doc, parsed = _source(tmp_path)
    raw = _raw('line:1', '850.00')
    raw['candidates'][0]['value_type'] = 'CURRENCY'
    raw['candidates'][0]['entity_hint'] = raw['candidates'][0].pop('entity_id')
    def respond(command, **kwargs):
        from pathlib import Path
        Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps(raw))
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr('againward.documents.codex_provider.subprocess.run', respond)
    proposal = CodexCliProvider(root, model='test').propose(doc, parsed,
        {'batch': batch, 'semantic_guidance': guidance()})
    accepted = validate_proposal(proposal, batch, root)
    assert accepted.candidates[0].value_type == 'DECIMAL'
    assert accepted.candidates[0].value == '850.00'


@pytest.mark.parametrize('model_value', ['9 asset-days', 'asset-days'])
def test_billed_units_wording_normalizes_from_its_unique_exact_native_quote(
    tmp_path, monkeypatch, model_value
):
    from againward.documents.codex_provider import CodexCliProvider

    quote = '9 asset-days x EUR 30.00'
    content = f'Invoice INV-9: {quote}; net EUR 270.00.'
    root, batch, doc, parsed = _source(tmp_path, content)
    response = {
        'status': 'SUCCESS', 'limitations': [], 'candidates': [{
            'entity_id': 'line-1', 'semantic_type': 'billed_units', 'value_type': 'DECIMAL',
            'value': model_value, 'raw_observed_value': quote, 'location': 'line:1',
            'normalization_notes': '', 'ambiguity_flags': [],
        }],
    }

    def fake_codex(command, **kwargs):
        Path(command[command.index('--output-last-message') + 1]).write_text(json.dumps(response))
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr('againward.documents.codex_provider.subprocess.run', fake_codex)
    proposal = CodexCliProvider(root, model='test').propose(doc, parsed,
        {'batch': batch, 'semantic_guidance': guidance()})
    accepted = validate_proposal(proposal, batch, root)
    billed_units = accepted.candidates[0]
    assert billed_units.semantic_type == 'billed_units'
    assert billed_units.value_type == 'DECIMAL' and billed_units.value == '9'
    assert billed_units.raw_observed_value == quote
    assert billed_units.source_span is not None
    assert 'unique quoted unit expression' in billed_units.normalization_notes


@pytest.mark.parametrize(('model_value', 'quote'), [
    ('10 asset-days', '9 asset-days x EUR 30.00'),
    ('asset-days', '9 asset-days and 10 asset-days'),
])
def test_billed_units_normalization_rejects_mismatched_or_ambiguous_quote(tmp_path, model_value, quote):
    root, batch, doc, parsed = _source(tmp_path, f'Invoice INV-9: {quote}.')
    raw = {'status': 'SUCCESS', 'limitations': [], 'candidates': [{
        'entity_id': 'line-1', 'semantic_type': 'billed_units', 'value_type': 'DECIMAL',
        'value': model_value, 'raw_observed_value': quote, 'location': 'line:1',
        'normalization_notes': '', 'ambiguity_flags': [],
    }]}
    normalized = normalize_read(raw, parsed, rental=True)
    assert normalized['candidates'][0]['value'] == model_value
    with pytest.raises(DocumentError, match='EXTRACTION_SCHEMA_INVALID'):
        validate_proposal(assemble_proposal(normalized, doc, parsed, batch.batch_id, 'test'), batch, root)


def test_recovered_native_assembly_requires_current_qa_review_and_source(tmp_path):
    from againward.documents.reconciliation import assemble_observations, complete_dispositions
    root, batch, read = _fixture(tmp_path)
    p, q, full = read(range(5)), read(range(5), 'peer'), read(range(7))
    selections = [{'extraction_sha256': p.to_dict()['extraction_sha256'], 'candidate_id': c.candidate_id,
                   'decision': 'INCLUDE', 'entity_id': 'line'} for c in p.candidates]
    observations = [c.to_dict() for c in full.candidates if c.semantic_type in {'charge_type', 'currency'}]
    assembled = assemble_observations(p, q, complete_dispositions(p, q, selections), batch, root,
                                     native_observations=observations)
    qa = compare_extractions(batch, (assembled,), (q,), root)
    raw = {'decisions': [{'source_id': p.source_id, 'selection': 'PRIMARY', 'rationale': 'Reviewed current original',
        'citations': [{'source_id': p.source_id, 'location': 'line:1', 'quote': CONTENT, 'preview_sha256': ''}],
        'observations': []}]}
    selected = validate_adjudication(batch, (assembled,), (q,), qa, raw, root,
                                    required_source_facts=package_source_gaps)
    assert selected['selected_extractions'][p.source_id] == assembled.to_dict()['extraction_sha256']
    decisions = _native_decisions((assembled,))
    with pytest.raises(DocumentError, match='UNSUPPORTED_PROMOTION'):
        build_analyst_review(batch, (assembled,), decisions, root)
    flags = {c.candidate_id: list(c.ambiguity_flags) for c in assembled.candidates}
    for response in decisions.values():
        for row in response['decisions']:
            row['resolved_flags'] = flags[row['candidate_id']]
    review = build_analyst_review(batch, (assembled,), decisions, root)
    facts = promote_facts((assembled,), review['review'], batch, root)
    assert len(facts) == 7 and all(f.candidate.source_id == p.source_id for f in facts)
    (root / batch.documents[0].blob_path).write_text('source mutation')
    with pytest.raises(DocumentError, match='SOURCE_CHANGED'):
        replay_extraction(assembled.to_dict(), batch, root)


def test_new_pixel_facts_in_assembly_have_lineage_but_no_attestation(tmp_path):
    root, batch, read = _fixture(tmp_path, visual=True)
    p, q = read(range(5)), read(range(5), 'peer')
    from againward.documents.visual_fact_review import _render_hash
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as directory:
        preview, _, _ = _render_hash(batch.documents[0], root, 'page:1', Path(directory))
    qa = compare_extractions(batch, (p,), (q,), root)
    raw = {'decisions': [{'source_id': p.source_id, 'selection': 'ASSEMBLE', 'rationale': 'Read original pixels',
        'citations': [{'source_id': p.source_id, 'location': 'page:1', 'quote': CONTENT, 'preview_sha256': preview}],
        'candidate_selections': [{'reader': 'PRIMARY', 'candidate_index': i + 1, 'decision': 'INCLUDE',
                                  'entity_id': 'joined'} for i in range(len(p.candidates))],
        'observations': [{'semantic_type': field, 'value_type': kind, 'value': value, 'visible_text': quote,
                          'page': 1, 'ambiguity': [], 'entity_hint': 'joined'}
                         for field, kind, value, quote in [('charge_type', 'ENUM', 'RENTAL', 'rental'),
                                                           ('currency', 'CURRENCY', 'EUR', 'EUR')]]}]}
    bound = bind_model_citations(raw, [], primary=(p,), challenger=(q,), sparse_assembly=True)
    result = validate_adjudication(batch, (p,), (q,), qa, bound, root, required_source_facts=package_source_gaps)
    assembled = replay_extraction(result['assembly_proposals'][p.source_id], batch, root)
    validate_rental_extraction(assembled, require_package_facts=True)
    assert result['facts_approved'] == 0
    assert all(c.source_span is None and 'VISUAL_TRANSCRIPTION_UNVERIFIED' in c.ambiguity_flags
               for c in assembled.candidates)
    source_metadata = [c for c in assembled.candidates
                       if c.semantic_type in {'document_role', 'document_status'}]
    entity_observations = [c for c in assembled.candidates
                           if c.semantic_type not in {'document_role', 'document_status'}]
    assert source_metadata and all(c.entity_id.startswith('runtime-source-') for c in source_metadata)
    assert all(c.entity_id == 'joined' for c in entity_observations)
    with pytest.raises(DocumentError):
        promote_facts((assembled,), {}, batch, root)


@pytest.mark.parametrize('location', [[], {}, 9, False])
def test_malformed_technical_locator_never_creates_a_binding_or_crashes(location):
    parsed = SimpleNamespace(units=[SimpleNamespace(route='NATIVE', location='line:1', text='exact')])
    raw = {'candidates': [{'semantic_type': 'description', 'value': 'exact', 'location': location,
                          'raw_observed_value': 'exact'}]}
    result = normalize_read(raw, parsed, rental=True)
    assert result['candidates'][0]['location'] == location


def test_partial_readers_enter_qa_once_each_without_structural_retry(tmp_path, monkeypatch):
    from againward.core.workspace import create_client_workspace
    from againward.domains.rental.source_job import run_approved_sources_job
    create_client_workspace('probe', root=tmp_path, synthetic=True, domain_name='rental', intake_payload={})
    case = tmp_path / 'probe'
    (case / 'incoming' / 'source.txt').write_text('Invoice INV-9: net EUR 850.00.')
    calls = []
    def read(self, document, parsed, context):
        calls.append(context['invocation_phase'])
        return assemble_proposal(_raw(parsed.units[0].location, '850.00'), document, parsed,
                                 context['batch'].batch_id, 'test')
    def stop_at_adjudication(*args, **kwargs):
        assert calls == ['PRIMARY_EXTRACTION', 'INDEPENDENT_REREAD']
        raise DocumentError('EXTRACTION_INCOMPLETE', 'Scripted probe stops before any review')
    monkeypatch.setattr(CodexCliProvider, 'propose', read)
    monkeypatch.setattr('againward.domains.rental.source_job.adjudicate_with_codex', stop_at_adjudication)
    result = run_approved_sources_job(case, model='test', evaluation_only=True)
    assert result['status'] == 'WAITING_FOR_REQUIRED_INFORMATION'
    state = json.loads((case / 'processed' / 'source_job_state.json').read_text())
    reads = [e for e in state['events'] if e['phase'] in {'DOCUMENT_PARSED', 'QA_SOURCE_REREAD'}]
    assert len(reads) == 2 and all(e['model_attempts'] == 1 and e['deferred_structure'] for e in reads)
    assert not state['human_approval'] and not state['approved_for_delivery']


def test_sparse_reference_presentation_is_normalized_without_changing_its_target():
    raw = {'selection': 'assemble', 'rationale': 'Complementary observations', 'candidate_selections': [
        {'reader': 'primary', 'candidate_index': '2', 'decision': 'include', 'entity_id': 'first invoice line'}]}
    result = normalize_decision(raw, source_id='source')
    row = result['decisions'][0]['candidate_selections'][0]
    assert row['reader'] == 'PRIMARY' and row['candidate_index'] == 2 and row['decision'] == 'INCLUDE'
    assert row['entity_id'].startswith('group-')
    assert raw['candidate_selections'][0]['candidate_index'] == '2'
