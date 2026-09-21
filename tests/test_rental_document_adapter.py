"""Synthetic source-to-ledger integration, not extraction/model accuracy metrics."""
from copy import deepcopy
import json

import pytest

from againward.core.artifact_store import read_json, write_json
from againward.core.workflow import prepare_investigation
from againward.documents.contracts import DocumentError
from againward.documents.extraction import SCHEMA, validate_proposal
from againward.documents.readers import read_batch
from againward.documents.sources import inventory_sources
from againward.domains.rental.document_adapter import DOCUMENT_CASE_SCHEMA, load_document_case
from againward.domains.rental.ingestion import build_evidence_dataset, load_rental_case
from againward.domains.rental.reconciliation import reconcile
from againward.domains.rental.workflow import current_calculations
from againward.entrypoints import get_domain


CONTRACT = """Synthetic rental agreement A-781, accepted by VENDOR and CLIENT.
Asset LIFT-92: electric lift, quantity 2.
Hire from 2026-09-01 up to but excluding 2026-09-08.
Rental EUR 50.00 per day and per asset; weekends charged.
Minimum duration 0 days; no discount (0.00).
Charging stops at contract end.
"""
INVOICE = """Synthetic invoice INV-83 from VENDOR, accepted.
Line L1: rental for agreement A-781 and asset LIFT-92.
Net amount EUR 850.00 excluding tax.
"""


def packet(tmp_path, *, invoice_text=INVOICE):
    """Manual semantic annotations of prose, reviewed solely as test fixtures."""
    incoming, root = tmp_path / "input", tmp_path / "documents"
    incoming.mkdir(parents=True)
    (incoming / "agreement.txt").write_text(CONTRACT)
    (incoming / "invoice.txt").write_text(invoice_text)
    batch = inventory_sources(incoming, root)
    parsed = {p.source_id: p for p in read_batch(batch, root)}
    shared = {
        "supplier_id": ("VENDOR", "VENDOR", "TEXT"),
        "agreement_id": ("A-781", "A-781", "TEXT"),
        "asset_id": ("LIFT-92", "LIFT-92", "TEXT"),
        "document_status": ("ACCEPTED", "accepted", "TEXT"),
        "currency": ("EUR", "EUR", "CURRENCY"),
    }
    annotations = {
        "agreement.txt": {**shared,
            "entity_kind": ("RENTAL_SCOPE", "rental agreement", "TEXT"),
            "document_role": ("RENTAL_AGREEMENT", "rental agreement", "TEXT"),
            "client_id": ("CLIENT", "CLIENT", "TEXT"),
            "description": ("electric lift", "electric lift", "TEXT"),
            "quantity": ("2", "2.", "DECIMAL"),
            "start": ("2026-09-01", "2026-09-01", "DATE"),
            "end": ("2026-09-08", "2026-09-08", "DATE"),
            "rate": ("50.00", "50.00", "DECIMAL"),
            "charge_key": ("hire", "Rental", "TEXT"),
            "charge_type": ("RENTAL", "Rental", "TEXT"),
            "billing_unit": ("DAY", "per day", "TEXT"),
            "weekends_billable": (True, "weekends charged", "BOOLEAN"),
            "minimum_days": (0, "0 days", "INTEGER"),
            "discount_fraction": ("0.00", "0.00", "DECIMAL"),
            "stop_event": ("CONTRACT_END", "contract end", "TEXT"),
        },
        "invoice.txt": {**shared,
            "entity_kind": ("INVOICE_LINE", "Line L1", "TEXT"),
            "document_role": ("INVOICE", "invoice", "TEXT"),
            "invoice_id": ("INV-83", "INV-83", "TEXT"),
            "invoice_line_id": ("L1", "L1", "TEXT"),
            "charge_key": ("hire", "rental", "TEXT"),
            "charge_type": ("RENTAL", "rental", "TEXT"),
            "net_amount": ("850.00", "850.00", "DECIMAL"),
        },
    }
    extractions = []
    decisions = []
    for doc in batch.documents:
        p = parsed[doc.source_id]
        candidates = []
        for field, (value, quote, value_type) in annotations[doc.original_names[0]].items():
            unit = next(u for u in p.units if quote in u.text)
            start = unit.text.index(quote)
            candidates.append({"candidate_id": doc.source_id + ":" + field,
                               "entity_id": "local-record", "semantic_type": field,
                               "value_type": value_type, "value": value, "raw_observed_value": quote,
                               "location": unit.location, "unit_sha256": unit.unit_sha256,
                               "source_span": [start, start + len(quote)], "ambiguity_flags": [],
                               "normalization_notes": "Synthetic manual interpretation of quoted clause",
                               "confidence": None})
        e = validate_proposal({"schema_version": SCHEMA, "source_id": doc.source_id,
                              "source_sha256": doc.sha256, "batch_id": batch.batch_id,
                              "reader_version": p.reader_version, "extractor_version": "test-annotations-v1",
                              "model": "MANUAL_SYNTHETIC_ANNOTATIONS_NOT_MODEL_BENCHMARK",
                              "prompt_version": "test-v1", "created_at": "2026-09-22T08:00:00Z",
                              "status": "SUCCESS", "limitations": [], "candidates": candidates}, batch, root)
        extractions.append(e.to_dict())
        decisions.extend({"candidate_id": c.candidate_id, "decision": "ACCEPT",
                          "reason": "Synthetic supplied annotation review, no actual human approval",
                          "resolved_flags": list(c.ambiguity_flags)} for c in e.candidates)
    package = {"schema_version": DOCUMENT_CASE_SCHEMA, "batch": batch.to_dict(), "extractions": extractions,
               "fact_review": {"schema_version": "againward-fact-review-v1",
                               "extraction_hashes": [e["extraction_sha256"] for e in extractions],
                               "reviewer_role": "ANALYST", "reviewed_at": "2026-09-22T09:00:00Z",
                               "limitations_acknowledged": True, "decisions": decisions},
               "rental_relationship_review": None, "credit_relationship_review": None}
    source = root / "rental.json"
    source.write_text(json.dumps(package))
    return source, package


def test_reviewed_native_facts_resolve_to_exact_rental_ledgers_and_query_rows(tmp_path):
    source, package = packet(tmp_path)
    case, inventory = load_rental_case(source)
    result = reconcile(case)
    assert result["groups"][0]["difference"] == "150.00"
    assert result["expected_ledger"]["entries"][0]["amount"] == "700.00"
    lineage = inventory["document_lineage"]
    assert not lineage["human_delivery_approval"]
    assert lineage["rental_resolution"]["relationships"][0]["state"] == "CONFIRMED"
    assert len(lineage["entities"]) == 2  # same model-local label is not a global entity ID
    dataset = build_evidence_dataset(case, document_lineage=lineage)
    assert sum(r["record_type"] == "document_fact" for r in dataset.rows) == len(lineage["facts"])
    assert sum(r["record_type"] == "document_relationship" for r in dataset.rows) == 1
    assert any(r.get("raw_quote") == "850.00" for r in dataset.rows)
    assert all("/chars:" in ref.location for c in case.actual_charges for ref in c.evidence_refs)
    assert load_document_case(package, source.parent)[1] == lineage


def test_lineage_integrates_with_kernel_and_inventory_tamper_invalidates_replay(tmp_path):
    source, _ = packet(tmp_path)
    root = tmp_path / "case"
    prepare_investigation(source, root, domain=get_domain("rental"))
    current_calculations(root)
    inventory = read_json(root / "artifact_inventory.json")
    inventory["document_lineage"]["facts"][0]["review_sha256"] = "0" * 64
    write_json(root / "artifact_inventory.json", inventory)
    with pytest.raises(ValueError, match="provenance changed"):
        current_calculations(root)


def test_review_and_report_keep_full_document_chain_without_delivery_approval(tmp_path):
    from benchmarking.rental_review import synthetic_review
    from againward.core.client_lifecycle import record_existing_data_exhaustion, mark_finalizable
    from againward.core.delivery import evaluate_delivery_gate
    from againward.domains.rental.review_policy import validate_current_review, RentalDeliveryPolicy
    from againward.domains.rental.reporting import render_report

    source, _ = packet(tmp_path)
    root = tmp_path / "case"
    prepare_investigation(source, root, domain=get_domain("rental"))
    synthetic_review(root)
    validate_current_review(root)
    record_existing_data_exhaustion(root, analysis_inventory_ref="artifact_inventory.json",
                                   reviewed_sources=["agreement.txt", "invoice.txt"])
    mark_finalizable(root, conclusion_ref="investigation.json")
    report = render_report(root, "Synthetic EUR 150 discrepancy; contractual entitlement not established.")
    pack = read_json(root / "rental_evidence_pack.json")
    assert pack["document_lineage"]["facts"]
    assert pack["document_lineage"]["rental_resolution"]["relationships"]
    assert not report["approved_for_delivery"]
    assert not evaluate_delivery_gate(root, policy=RentalDeliveryPolicy())["ready_for_delivery"]


def test_unknown_scope_identifier_cannot_be_inferred_from_other_document(tmp_path):
    source, package = packet(tmp_path)
    changed = deepcopy(package)
    invoice = next(e for e in changed["extractions"] if any(c["semantic_type"] == "invoice_id" for c in e["candidates"]))
    candidate = next(c for c in invoice["candidates"] if c["semantic_type"] == "asset_id")
    decision = next(d for d in changed["fact_review"]["decisions"] if d["candidate_id"] == candidate["candidate_id"])
    decision["decision"] = "DEFER"
    with pytest.raises(DocumentError, match="ENTITY_AMBIGUOUS"):
        load_document_case(changed, source.parent)


def test_missing_rate_abstains_instead_of_copying_invoice_price(tmp_path):
    source, package = packet(tmp_path)
    rate_id = next(c["candidate_id"] for e in package["extractions"] for c in e["candidates"]
                   if c["semantic_type"] == "rate")
    next(d for d in package["fact_review"]["decisions"] if d["candidate_id"] == rate_id)["decision"] = "DEFER"
    case, _ = load_document_case(package, source.parent)
    assert reconcile(case)["groups"][0]["difference"] is None


def test_lineage_cannot_attach_to_different_canonical_case(tmp_path):
    source, _ = packet(tmp_path)
    case, inventory = load_rental_case(source)
    lineage = inventory["document_lineage"]
    lineage["canonical_case_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="does not support"):
        build_evidence_dataset(case, document_lineage=lineage)
