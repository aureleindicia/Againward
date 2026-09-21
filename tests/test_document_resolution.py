"""Counterexamples for explicit links; these fixtures do not measure a model."""
from copy import deepcopy
from dataclasses import replace

import pytest

from againward.documents.contracts import DocumentError
from againward.documents.extraction import CanonicalFact, FactCandidate
from againward.documents.resolution import (
    MatchPolicy, RelationshipState, entities_from_facts, resolve_entities, review_relationships,
)


POLICY = MatchPolicy(
    "SAME_RENTAL", (("INVOICE_LINE", "RENTAL_SCOPE"), ("RETURN", "RENTAL_SCOPE")),
    blocking_keys=("agreement", "asset", "serial"),
    anchor_keys=(("agreement", "asset"), ("agreement", "serial")),
    contradiction_keys=("supplier", "agreement", "asset", "serial"),
    required_scope_keys=("supplier",),
    exclusive_left_kinds=("INVOICE_LINE", "RETURN"),
    prefix_blocking_keys=("agreement",),
)


def facts(source, local="record", **values):
    return tuple(CanonicalFact(
        f"fact-{source}-{local}-{key}",
        FactCandidate(f"candidate-{source}-{local}-{key}", local, key, "TEXT", value,
                      value, "line:1", source, "a" * 64, "", (), (0, len(value)), None),
        "b" * 64, "c" * 64, "SYNTHETIC already reviewed fixture")
        for key, value in values.items())


def pair(**changes):
    baseline = dict(supplier="SUPPLIER", agreement="77182", asset="AB-4928", description="Lift")
    return entities_from_facts((
        *facts("contract", entity_kind="RENTAL_SCOPE", **baseline),
        *facts("invoice", entity_kind="INVOICE_LINE", **{**baseline, **changes}),
    ))


def test_exact_reviewed_anchors_confirm_without_copying_attributes():
    entities = pair()
    result = resolve_entities(entities, POLICY)
    relationship = result.relationships[0]
    assert relationship.state == RelationshipState.CONFIRMED
    assert relationship.authority == "EXACT_REVIEWED_IDENTIFIERS"
    assert "asset" in relationship.support and relationship.supporting_fact_ids
    assert result.entities == tuple(sorted(entities, key=lambda e: e.entity_id))
    assert result.considered_pairs == 1


def test_same_local_model_label_does_not_merge_source_entities():
    entities = pair()
    assert len(entities) == 2
    assert entities[0].local_id == entities[1].local_id
    assert entities[0].entity_id != entities[1].entity_id
    assert {e.source_id for e in entities} == {"contract", "invoice"}


@pytest.mark.parametrize("field,value", [("serial", "SERIAL-WRONG"), ("asset", "OTHER"),
                                        ("supplier", "OTHER"), ("agreement", "77128")])
def test_matching_description_never_overrides_conflicting_identifier(field, value):
    base = dict(supplier="SUPPLIER", agreement="77182", asset="AB-4928", serial="SERIAL-RIGHT", description="Lift")
    entities = entities_from_facts((*facts("contract", entity_kind="RENTAL_SCOPE", **base),
                                   *facts("invoice", entity_kind="INVOICE_LINE", **{**base, field: value})))
    result = resolve_entities(entities, POLICY)
    assert result.relationships[0].state == RelationshipState.CONTRADICTED
    assert field in result.relationships[0].contradictions
    assert result.relationships[0].contradicting_fact_ids


def test_shared_agreement_without_asset_remains_candidate_no_manufactured_id():
    entities = entities_from_facts((
        *facts("contract", entity_kind="RENTAL_SCOPE", agreement="77182", supplier="S", asset="A"),
        *facts("invoice", entity_kind="INVOICE_LINE", agreement="77182", supplier="S"),
    ))
    result = resolve_entities(entities, POLICY)
    assert result.relationships[0].state == RelationshipState.CANDIDATE
    invoice = next(e for e in result.entities if e.kind == "INVOICE_LINE")
    assert "asset" not in invoice.values


def test_two_plausible_rentals_abstain_and_do_not_raise_grade_with_more_evidence():
    common = dict(supplier="S", agreement="77182", asset="A")
    initial = entities_from_facts((*facts("contract-1", entity_kind="RENTAL_SCOPE", **common),
                                  *facts("invoice", entity_kind="INVOICE_LINE", **common)))
    assert resolve_entities(initial, POLICY).relationships[0].state == RelationshipState.CONFIRMED
    additional = entities_from_facts(facts("contract-2", entity_kind="RENTAL_SCOPE", **common))
    result = resolve_entities((*initial, *additional), POLICY)
    assert len(result.relationships) == 2
    assert all(r.state == RelationshipState.AMBIGUOUS for r in result.relationships)


def test_multiple_invoices_can_link_to_one_rental_but_one_invoice_cannot_link_twice():
    common = dict(supplier="S", agreement="77182", asset="A")
    entities = entities_from_facts((*facts("contract", entity_kind="RENTAL_SCOPE", **common),
                                   *facts("invoice-1", entity_kind="INVOICE_LINE", **common),
                                   *facts("invoice-2", entity_kind="INVOICE_LINE", **common)))
    result = resolve_entities(entities, POLICY)
    assert len(result.relationships) == 2
    assert all(r.state == RelationshipState.CONFIRMED for r in result.relationships)


def test_order_and_irrelevant_evidence_do_not_increase_relationship_authority():
    entities = pair()
    first = resolve_entities(entities, POLICY)
    assert first.to_dict() == resolve_entities(tuple(reversed(entities)), POLICY).to_dict()
    noise = entities_from_facts(facts("noise", entity_kind="IRRELEVANT", description="Lift"))
    second = resolve_entities((*entities, *noise), POLICY)
    assert second.relationships == first.relationships


def test_sparse_blocking_has_complete_true_pairs_and_bounded_comparisons():
    values = []
    for i in range(100):
        common = dict(supplier="S", agreement=f"A{i}", asset=f"X{i}")
        values.extend(facts(f"c{i}", entity_kind="RENTAL_SCOPE", **common))
        values.extend(facts(f"i{i}", entity_kind="INVOICE_LINE", **common))
    result = resolve_entities(entities_from_facts(tuple(values)), POLICY)
    assert result.theoretical_pairs == 19900
    assert result.considered_pairs == 100
    assert sum(r.state == RelationshipState.CONFIRMED for r in result.relationships) == 100
    with pytest.raises(DocumentError, match="pair budget"):
        resolve_entities(entities_from_facts(tuple(values)), replace(POLICY, maximum_pairs=99))


def test_prefix_blocking_recovers_partial_reference_as_unconfirmed_candidate():
    entities = entities_from_facts((
        *facts("contract", entity_kind="RENTAL_SCOPE", agreement="77182-B", supplier="S"),
        *facts("invoice", entity_kind="INVOICE_LINE", agreement="77182", supplier="S")))
    result = resolve_entities(entities, POLICY)
    assert result.considered_pairs == 1
    assert result.relationships[0].state != RelationshipState.CONFIRMED


def test_resolution_review_is_hash_bound_preserves_history_and_requires_supplied_human_role():
    entities = entities_from_facts((
        *facts("contract", entity_kind="RENTAL_SCOPE", agreement="77182", supplier="S", asset="A"),
        *facts("invoice", entity_kind="INVOICE_LINE", agreement="77182", supplier="S")))
    result = resolve_entities(entities, POLICY)
    relationship = result.relationships[0]
    review = {"schema_version": "againward-resolution-review-v1",
              "resolution_sha256": result.to_dict()["resolution_sha256"],
              "reviewer_role": "HUMAN", "reviewed_at": "2026-09-21T12:00:00Z", "decisions": [{
                  "relationship_id": relationship.relationship_id, "state": "CONFIRMED",
                  "reason": "SYNTHETIC fixture of a supplied human source inspection",
                  "supporting_fact_ids": list(relationship.supporting_fact_ids)}]}
    revised = review_relationships(result, review)
    assert revised.relationships[0].state == RelationshipState.CONFIRMED
    assert len(revised.relationships[0].history) == 2
    assert result.relationships[0].state == RelationshipState.CANDIDATE
    for change in ({"reviewer_role": "ANALYST"}, {"resolution_sha256": "0" * 64}):
        with pytest.raises(DocumentError):
            review_relationships(result, {**review, **change})
    altered = deepcopy(review)
    altered["decisions"][0]["supporting_fact_ids"] = ["imaginary"]
    with pytest.raises(DocumentError):
        review_relationships(result, altered)
