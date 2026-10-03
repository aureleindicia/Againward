"""Synthetic lifecycle and delivery integration; approvals here are test fixtures only."""
import json

import pytest

from againward.core.artifact_store import read_json, write_json
from againward.core.workflow import prepare_investigation
from againward.core.client_lifecycle import record_existing_data_exhaustion, mark_finalizable
from againward.core.delivery import evaluate_delivery_gate
from againward.entrypoints import get_domain
from againward.domains.rental.workflow import record_assessments, recalculate
from againward.domains.rental.review_policy import RentalDeliveryPolicy, validate_current_review
from againward.domains.rental.reporting import render_report
from againward.domains.rental.pdf_report import render_rental_pdf, validate_synthesis
from tests.test_rental_ingestion import write_packet
from benchmarking.rental_review import synthetic_review


def test_synthesis_allows_only_reviewed_asset_identifiers_not_free_numbers():
    pack = {"charge_groups": [], "findings": {"findings": []}, "document_lineage": {"facts": [
        {"candidate": {"semantic_type": "asset_id", "value": "LIFT-5"}},
        {"candidate": {"semantic_type": "asset_id", "value": "LIFT-50"}}]}}
    validate_synthesis("LIFT-5 differs from LIFT-50 in the supplied rental records.", pack)
    with pytest.raises(ValueError, match="Free numeric"):
        validate_synthesis("LIFT-500 differs from LIFT-5.", pack)
    with pytest.raises(ValueError, match="Free numeric"):
        validate_synthesis("LIFT-5 returned on 2026-09-05.", pack)


def test_client_pdf_can_layout_concise_long_synthesis(tmp_path):
    pack = {"charge_groups": [], "findings": {"findings": []}, "documents": []}
    synthesis = "The supplied documents require a written reconciliation. " * 22
    result = render_rental_pdf(pack, synthesis, tmp_path / "report.pdf")
    assert result["page_count"] == 5
    assert (tmp_path / "report.pdf").read_bytes().startswith(b"%PDF-1.4")
    render_rental_pdf(pack, synthesis, tmp_path / "evaluation.pdf", evaluation_only=True)
    assert b"SYNTHETIC EVALUATION" in (tmp_path / "evaluation.pdf").read_bytes()


@pytest.mark.parametrize("unit_days,expected_basis", [(None, "7 days × 4 units"), ("28", "28 asset-days")])
def test_pdf_basis_and_unexplained_difference_are_not_misrepresented(tmp_path, unit_days, expected_basis):
    from pypdf import PdfReader

    pack = {"documents": [], "findings": {"findings": []}, "charge_groups": [
        {"period_id": "p", "charge_key": "rental", "charge_ids": ["line"],
         "currency": "EUR", "expected_amount": "2100.00", "actual_amount": "2250.00",
         "difference": "150.00"}],
        "expected_ledger": {"entries": [{"period_id": "p", "charge_key": "rental",
            "units": "7", "unit_days": unit_days, "quantity": "4", "billing_unit": "DAY", "rate": "75"}]},
        "actual_ledger": {"entries": [{"charge_id": "line", "issued_credit": "0.00",
            "invoiced_amount": "2250.00"}]}}
    target = tmp_path / "report.pdf"
    render_rental_pdf(pack, "The documentary difference requires clarification.", target)
    text = " ".join(" ".join(page.extract_text().split()) for page in PdfReader(target).pages)
    assert expected_basis in text
    assert "28 asset-days ×" not in text
    assert "no credit document supplied" not in text
    assert "no issued credit applied to this line" in text
    assert "A documentary difference appears" in text
    assert "No supported client-facing discrepancy was established" not in text


def test_review_report_and_human_approval_bound_to_current_evidence(tmp_path):
    source, _ = write_packet(tmp_path / "source")
    root = tmp_path / "case"
    prepare_investigation(source, root, domain=get_domain("rental"))
    synthetic_review(root)
    validate_current_review(root)
    record_existing_data_exhaustion(root, analysis_inventory_ref="artifact_inventory.json", reviewed_sources=["agreement.txt", "invoice.csv"])
    mark_finalizable(root, conclusion_ref="investigation.json")
    report = render_report(root, "Synthetic analyst synthesis: EUR 150 discrepancy; no guaranteed recovery.")
    assert report["pdf"]["page_count"] == 5
    rendered = (root / "rental_client_report.pdf").read_bytes()
    assert rendered.startswith(b"%PDF-1.4")
    assert b"Source types:" in rendered
    assert b"ask the supplier in writing" in rendered
    assert b"source SHA-256" not in rendered
    assert b"The owner must inspect" not in rendered
    assert b"Claim/abstention" not in rendered
    assert b"Best reason this may be false" not in rendered
    assert "rental_client_report.pdf" in report["reviewed_artifact_hashes"]
    gate = evaluate_delivery_gate(root, policy=RentalDeliveryPolicy())
    assert not gate["ready_for_delivery"]
    write_json(root / "human_review.json", {"status": "approved", "approved_for_delivery": True,
        "reviewer_role": "SYNTHETIC TEST REVIEWER", "reviewed_at_utc": "2026-09-18T08:00:00Z",
        "reviewed_artifact_hashes": report["reviewed_artifact_hashes"]})
    gate = evaluate_delivery_gate(root, policy=RentalDeliveryPolicy())
    assert gate["ready_for_delivery"], gate["blocking_reasons"]
    pdf = root / "rental_client_report.pdf"
    pdf.write_bytes(pdf.read_bytes() + b"tampered")
    assert not evaluate_delivery_gate(root, policy=RentalDeliveryPolicy())["ready_for_delivery"]
    render_report(root, "Synthetic analyst synthesis: EUR 150 discrepancy; no guaranteed recovery.")
    assert evaluate_delivery_gate(root, policy=RentalDeliveryPolicy())["ready_for_delivery"]
    (root / "report.md").write_text("Altered claim")
    assert not evaluate_delivery_gate(root, policy=RentalDeliveryPolicy())["ready_for_delivery"]
    assert read_json(root / "investigation_state.json")["client_lifecycle"]["state"] == "FINALIZABLE"


def test_rental_report_refuses_unvalidated_free_amount(tmp_path):
    source, _ = write_packet(tmp_path / "source")
    root = tmp_path / "case"
    prepare_investigation(source, root, domain=get_domain("rental"))
    synthetic_review(root)
    record_existing_data_exhaustion(root, analysis_inventory_ref="artifact_inventory.json",
                                    reviewed_sources=["agreement.txt", "invoice.csv"])
    mark_finalizable(root, conclusion_ref="investigation.json")
    with pytest.raises(ValueError, match="not present in validated"):
        render_report(root, "Synthetic claim: EUR 9999 is recoverable.")


def test_recalculation_archives_and_preserves_remaining_query_budget(tmp_path):
    source, packet = write_packet(tmp_path / "source")
    root = tmp_path / "case"
    prepare_investigation(source, root, domain=get_domain("rental"))
    synthetic_review(root)
    old_session = read_json(root / "evidence_query_session.json")
    packet["actual_charges"][0]["net_amount"] = "800.00"
    revised = source.with_name("revised.json")
    revised.write_text(json.dumps(packet))
    result = recalculate(root, revised)
    assert result["review_required"]
    new_session = read_json(root / "evidence_query_session.json")
    assert new_session["budget"]["maximum_calls"] == old_session["budget"]["maximum_calls"] - 1
    assert list((root / "evidence_revisions").glob("*/rental_findings.json"))
    with pytest.raises(ValueError, match="stale"):
        validate_current_review(root)
    synthetic_review(root, query_id="q2")
    validate_current_review(root)
    with pytest.raises(ValueError, match="Unchanged"):
        recalculate(root, revised)


def test_stale_or_tampered_calculations_and_source_refuse_review(tmp_path):
    source, _ = write_packet(tmp_path / "source")
    root = tmp_path / "case"
    prepare_investigation(source, root, domain=get_domain("rental"))
    result = read_json(root / "prepared_analysis.json")
    result["groups"][0]["difference"] = "999.00"
    write_json(root / "prepared_analysis.json", result)
    with pytest.raises(ValueError, match="stale or altered"):
        record_assessments(root, [])
