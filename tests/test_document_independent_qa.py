"""Independent QA must find omissions and swapped entity fields, not bless a pass."""
from __future__ import annotations

from copy import deepcopy

import pytest

from againward.documents.codex_provider import assemble_proposal
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal
from againward.documents.independent_qa import compare_extractions
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources


def _case(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    (public / "invoice.txt").write_text("Invoice I-1 line A net 100; line B net 200.")
    root = tmp_path / "documents"
    batch = inventory_sources(public, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    raw = {"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": entity, "semantic_type": field, "value_type": kind,
         "value": value, "raw_observed_value": quote, "location": parsed.units[0].location,
         "normalization_notes": "Exact source value", "ambiguity_flags": []}
        for entity, field, kind, value, quote in (
            ("line-A", "invoice_line_id", "IDENTIFIER", "A", "line A"),
            ("line-A", "net_amount", "DECIMAL", "100", "100"),
            ("line-B", "invoice_line_id", "IDENTIFIER", "B", "line B"),
            ("line-B", "net_amount", "DECIMAL", "200", "200"),
        )]}

    def validate(body):
        return validate_proposal(assemble_proposal(body, document, parsed, batch.batch_id,
                                                   "synthetic-model"), batch, root)
    return root, batch, raw, validate


def test_independent_qa_agreement_is_non_authoritative(tmp_path):
    root, batch, raw, validate = _case(tmp_path)
    first = validate(raw)
    second = validate(deepcopy(raw))
    body = compare_extractions(batch, (first,), (second,), root)
    assert body["status"] == "AGREEMENT"
    assert body["delivery_approved"] is False
    assert "Same model family" in body["limitations"][0]
    assert body["source_results"][0]["needs_reconciliation"] is False


def test_independent_qa_finds_omission_and_entity_swap(tmp_path):
    root, batch, raw, validate = _case(tmp_path)
    first = validate(raw)
    omitted = deepcopy(raw)
    omitted["candidates"].pop()
    missing = compare_extractions(batch, (first,), (validate(omitted),), root)
    assert missing["status"] == "RECONCILIATION_REQUIRED"
    assert missing["source_results"][0]["primary_only_entity_bundles"] == 1

    swapped = deepcopy(raw)
    swapped["candidates"][1]["entity_id"] = "line-B"
    swapped["candidates"][3]["entity_id"] = "line-A"
    mismatch = compare_extractions(batch, (first,), (validate(swapped),), root)
    assert mismatch["status"] == "RECONCILIATION_REQUIRED"
    assert mismatch["source_results"][0]["primary_only_entity_bundles"] == 2


def test_independent_qa_requires_complete_current_source_set(tmp_path):
    root, batch, raw, validate = _case(tmp_path)
    first = validate(raw)
    with pytest.raises(DocumentError, match="EXTRACTION_INCOMPLETE"):
        compare_extractions(batch, (first,), (), root)
    source = root / batch.documents[0].blob_path
    source.write_text("tampered")
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        compare_extractions(batch, (first,), (first,), root)
