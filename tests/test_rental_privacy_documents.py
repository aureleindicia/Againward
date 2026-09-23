"""Synthetic privacy checks: real-case gate exercised, never a human approval claim."""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

import pytest

from againward.core.privacy import inspect_privacy_status, validate_codex_privacy_review
from againward.core.privacy_inspection import INSPECTION_VERSION
from againward.core.visual_review import attest_visual_packet, prepare_visual_packet
from againward.core.workspace import create_client_workspace
from againward.domains.rental.privacy_policy import RENTAL_PRESERVATION
from benchmarking.document_renderers import pdf
from pypdf import PdfReader, PdfWriter
from tests.contract_fixtures import authorize_test_case
from tests.test_privacy_gate import _category, _file_spec, _review, _transform


def rental_case(tmp_path: Path, name="rental") -> Path:
    create_client_workspace(name, root=tmp_path, domain_name="rental", intake_payload={"profile": "generic"})
    case = tmp_path / name
    authorize_test_case(case)
    return case


def visual_review(path: Path, location="page:1", categories=()):
    return {"location": location, "source_sha256": sha256(path.read_bytes()).hexdigest(),
            "inspection_version": INSPECTION_VERSION, "reviewer_role": "HUMAN",
            "reviewed_at_utc": "2026-09-23T08:00:00Z", "decision": "PASS",
            "detected_categories": list(categories), "business_evidence_preserved": True,
            "prompt_injection_ignored": True}


def metadata(path: Path, value: str):
    writer = PdfWriter()
    for page in PdfReader(BytesIO(path.read_bytes())).pages:
        writer.add_page(page)
    writer.add_metadata({"/Subject": value})
    writer.write(path)


def scripted_visual(case: Path, review: Path, *, categories=()):
    """Exercise the operator protocol with fixtures; never evidence of a human."""
    packet = prepare_visual_packet(case, review)
    responses = []
    for component in packet["components"]:
        responses.extend(["INSPECTED " + component["source_sha256"][:12], "PASS",
                          ",".join(categories), "YES"])
    answers = iter(responses)
    attest_visual_packet(case, review, actor_id="TEST_FIXTURE_ONLY",
                         ask=lambda _: next(answers), interactive=True)


def clearance(case: Path, source: str, *, spec=None, status="PASS", categories=(), visual_categories=None):
    spec = spec or _file_spec("incoming/" + source)
    review = _review(case, [spec], status=status, categories=list(categories))
    if visual_categories is not None:
        scripted_visual(case, review, categories=visual_categories)
    return validate_codex_privacy_review(case, review, preservation_policy=RENTAL_PRESERVATION)


def test_native_rental_pdf_passes_with_source_bound_inspection(tmp_path):
    case = rental_case(tmp_path)
    pdf(case / "incoming/contract.pdf", ["Agreement AG-12. Rental EUR 50.00 per day."])
    manifest = clearance(case, "contract.pdf")
    entry = manifest["files"][0]
    assert manifest["approved_for_analysis"]
    assert entry["privacy_assessment"]["inspection"]["source_sha256"] == entry["original_sha256"]
    assert entry["privacy_assessment"]["inspection"]["inspection_version"] == INSPECTION_VERSION
    assert (case / "sanitized/contract.pdf").is_file()


def test_professional_contact_and_confidential_rate_are_not_blanket_blocked(tmp_path):
    case = rental_case(tmp_path)
    pdf(case / "incoming/invoice.pdf", ["Invoice INV-7. Net EUR 700.00.",
                                        "Contact Jean Dupont jean.dupont@supplier.example +33 1 23 45 67 89."])
    spec = _file_spec("incoming/invoice.pdf")
    spec["business_confidentiality"] = "BUSINESS_CONFIDENTIAL"
    manifest = clearance(case, "invoice.pdf", spec=spec)
    entry = manifest["files"][0]
    assert manifest["approved_for_analysis"]
    assert {"EMAIL", "PHONE"} <= set(entry["detected_categories"])
    assert entry["privacy_assessment"]["business_confidentiality"] == "BUSINESS_CONFIDENTIAL"


def test_business_contact_at_consumer_mail_provider_is_not_assumed_private(tmp_path):
    case = rental_case(tmp_path)
    pdf(case / "incoming/invoice.pdf", ["Invoice INV-8. Net EUR 700.00.",
                                        "Supplier contact: jean.dupont@gmail.com."])
    manifest = clearance(case, "invoice.pdf")
    assert manifest["approved_for_analysis"]
    assert "EMAIL" in manifest["files"][0]["detected_categories"]
    assert "PERSONAL_EMAIL" not in manifest["files"][0]["detected_categories"]


def test_reviewed_professional_name_is_an_allowed_rental_category(tmp_path):
    case = rental_case(tmp_path)
    pdf(case / "incoming/invoice.pdf", ["Invoice INV-8. Supplier contact Jean Dupont."])
    spec = _file_spec("incoming/invoice.pdf")
    spec["categories"] = [_category("PROFESSIONAL_NAME", "PASS")]
    manifest = clearance(case, "invoice.pdf", spec=spec,
                         categories=[_category("PROFESSIONAL_NAME", "PASS")])
    assert manifest["approved_for_analysis"]
    assert "PROFESSIONAL_NAME" in manifest["files"][0]["detected_categories"]


def test_business_scan_needs_exact_human_visual_review_and_then_passes(tmp_path):
    case = rental_case(tmp_path)
    path = case / "incoming/return.pdf"
    pdf(path, ["Signed return agreement AG-12 asset LIFT-5 on 2026-09-05."], scan=True)
    spec = _file_spec("incoming/return.pdf")
    manifest = clearance(case, "return.pdf", spec=spec,
                         visual_categories=("PROFESSIONAL_SIGNATURE",))
    assert manifest["approved_for_analysis"]
    assert manifest["files"][0]["privacy_assessment"]["inspectability"] == "HUMAN_VISUAL_REVIEWED"
    assert "PROFESSIONAL_SIGNATURE" in manifest["files"][0]["detected_categories"]


@pytest.mark.parametrize("alter", ["missing", "wrong_hash", "model_only"])
def test_visual_scan_without_valid_human_source_binding_blocks(tmp_path, alter):
    case = rental_case(tmp_path)
    path = case / "incoming/return.pdf"
    pdf(path, ["Signed return agreement AG-12 asset LIFT-5."], scan=True)
    spec = _file_spec("incoming/return.pdf")
    review = visual_review(path)
    if alter == "wrong_hash":
        review["source_sha256"] = "0" * 64
    elif alter == "model_only":
        review["reviewer_role"] = "MODEL"
    if alter != "missing":
        spec["visual_reviews"] = [review]
    with pytest.raises(ValueError):
        clearance(case, "return.pdf", spec=spec)
    assert not inspect_privacy_status(case)["approved_for_analysis"]


def test_hybrid_pdf_requires_visual_component_review(tmp_path):
    case = rental_case(tmp_path)
    path = case / "incoming/hybrid.pdf"
    pdf(path, ["Invoice INV-7. Net EUR 700.00."], hybrid=True)
    spec = _file_spec("incoming/hybrid.pdf")
    assert clearance(case, "hybrid.pdf", spec=spec, visual_categories=())["approved_for_analysis"]


def test_sensitive_scan_declared_by_visual_review_cannot_pass(tmp_path):
    case = rental_case(tmp_path)
    path = case / "incoming/medical.pdf"
    pdf(path, ["Medical diagnosis for an employee."], scan=True)
    spec = _file_spec("incoming/medical.pdf")
    with pytest.raises(ValueError, match="HIGH_RISK_PERSONAL_DATA"):
        clearance(case, "medical.pdf", spec=spec, visual_categories=("MEDICAL_DATA",))
    assert inspect_privacy_status(case)["state"] == "PRIVACY_BLOCKED"


@pytest.mark.parametrize("text", ["API key: sk-live-1234567890abcdef", "Medical diagnosis for employee",
                                         "Passport scan for employee", "Personnel file: disciplinary action"])
def test_native_high_risk_pdf_cannot_pass(tmp_path, text):
    case = rental_case(tmp_path)
    pdf(case / "incoming/unrelated.pdf", [text])
    with pytest.raises(ValueError):
        clearance(case, "unrelated.pdf")
    assert inspect_privacy_status(case)["state"] == "PRIVACY_BLOCKED"


def test_corrupt_pdf_blocks_for_inspection_failure_not_extension(tmp_path):
    case = rental_case(tmp_path)
    (case / "incoming/corrupt.pdf").write_bytes(b"not a PDF")
    with pytest.raises(ValueError):
        clearance(case, "corrupt.pdf")
    assert not inspect_privacy_status(case)["approved_for_analysis"]


def test_pdf_metadata_secret_cannot_hide_outside_visible_page_text(tmp_path):
    case = rental_case(tmp_path)
    path = case / "incoming/contract.pdf"
    pdf(path, ["Agreement AG-12. Rental EUR 50.00 per day."])
    metadata(path, "api_key=sk-live-1234567890abcdef")
    with pytest.raises(ValueError):
        clearance(case, "contract.pdf")
    assert inspect_privacy_status(case)["state"] == "PRIVACY_BLOCKED"


def test_sanitized_pdf_removes_contact_but_preserves_invoice_amount(tmp_path):
    case = rental_case(tmp_path)
    pdf(case / "incoming/invoice.pdf", ["Invoice INV-7. Net EUR 700.00.",
                                        "Personal email jean.dupont@gmail.com."])
    pdf(case / "privacy/candidate/invoice.pdf", ["Invoice INV-7. Net EUR 700.00."])
    spec = _file_spec("incoming/invoice.pdf", action="SANITIZED",
                      sanitized="privacy/candidate/invoice.pdf",
                      transformations=[_transform("PERSONAL_EMAIL", "REMOVED")])
    manifest = clearance(case, "invoice.pdf", spec=spec, status="SANITIZED",
                         categories=[_category("PERSONAL_EMAIL", "REMOVED")])
    assert manifest["approved_for_analysis"]
    assert (case / "sanitized/invoice.pdf").is_file()
    assert manifest["files"][0]["original_sha256"] != manifest["files"][0]["sanitized_sha256"]


def test_pdf_sanitization_cannot_change_money(tmp_path):
    case = rental_case(tmp_path)
    pdf(case / "incoming/invoice.pdf", ["Invoice INV-7. Net EUR 700.00.",
                                        "Personal email jean.dupont@gmail.com."])
    pdf(case / "privacy/candidate/invoice.pdf", ["Invoice INV-7. Net EUR 900.00."])
    spec = _file_spec("incoming/invoice.pdf", action="SANITIZED",
                      sanitized="privacy/candidate/invoice.pdf",
                      transformations=[_transform("PERSONAL_EMAIL", "REMOVED")])
    with pytest.raises(ValueError, match="marqueur industriel"):
        clearance(case, "invoice.pdf", spec=spec, status="SANITIZED",
                  categories=[_category("PERSONAL_EMAIL", "REMOVED")])


def test_pdf_redaction_cannot_hide_removed_email_in_metadata(tmp_path):
    case = rental_case(tmp_path)
    pdf(case / "incoming/invoice.pdf", ["Invoice INV-7. Net EUR 700.00.",
                                        "Personal email jean.dupont@gmail.com."])
    candidate = case / "privacy/candidate/invoice.pdf"
    pdf(candidate, ["Invoice INV-7. Net EUR 700.00."])
    metadata(candidate, "jean.dupont@gmail.com")
    spec = _file_spec("incoming/invoice.pdf", action="SANITIZED",
                      sanitized="privacy/candidate/invoice.pdf",
                      transformations=[_transform("PERSONAL_EMAIL", "REMOVED")])
    with pytest.raises(ValueError, match="SANITIZATION_FAILED"):
        clearance(case, "invoice.pdf", spec=spec, status="SANITIZED",
                  categories=[_category("PERSONAL_EMAIL", "REMOVED")])


def test_pdf_redaction_cannot_hide_residential_address_value_in_metadata(tmp_path):
    case = rental_case(tmp_path)
    pdf(case / "incoming/invoice.pdf", ["Invoice INV-7. Net EUR 700.00.",
                                        "Residential address: 5 Example Street."])
    candidate = case / "privacy/candidate/invoice.pdf"
    pdf(candidate, ["Invoice INV-7. Net EUR 700.00."])
    metadata(candidate, "5 Example Street")
    spec = _file_spec("incoming/invoice.pdf", action="SANITIZED",
                      sanitized="privacy/candidate/invoice.pdf",
                      transformations=[_transform("RESIDENTIAL_ADDRESS", "REMOVED")])
    with pytest.raises(ValueError, match="SANITIZATION_FAILED"):
        clearance(case, "invoice.pdf", spec=spec, status="SANITIZED",
                  categories=[_category("RESIDENTIAL_ADDRESS", "REMOVED")])


def test_irrelevant_residential_address_needs_minimization(tmp_path):
    case = rental_case(tmp_path)
    pdf(case / "incoming/invoice.pdf", ["Invoice INV-7. Net EUR 700.00.",
                                        "Residential address: 5 Example Street."])
    with pytest.raises(ValueError):
        clearance(case, "invoice.pdf")
    assert inspect_privacy_status(case)["state"] == "PRIVACY_BLOCKED"


def test_rental_policy_version_change_invalidates_cleared_source(tmp_path):
    from againward.core.privacy import assert_source_approved_for_analysis

    case = rental_case(tmp_path)
    pdf(case / "incoming/contract.pdf", ["Agreement AG-12. Rental EUR 50.00 per day."])
    clearance(case, "contract.pdf")
    path = case / "privacy/privacy_manifest.json"
    manifest = json.loads(path.read_text())
    manifest["risk_policy_version"] = "obsolete"
    path.write_text(json.dumps(manifest))
    assert inspect_privacy_status(case)["state"] == "PRIVACY_MIGRATION_REQUIRED"
    with pytest.raises(ValueError, match="PRIVACY GATE"):
        assert_source_approved_for_analysis(case / "sanitized/contract.pdf")


def test_supplemental_scan_requires_new_source_bound_review(tmp_path):
    from againward.core.privacy import assert_source_approved_for_analysis

    case = rental_case(tmp_path)
    pdf(case / "incoming/contract.pdf", ["Agreement AG-12. Rental EUR 50.00 per day."])
    clearance(case, "contract.pdf")
    extra = case / "incoming/return.pdf"
    pdf(extra, ["Signed return of asset LIFT-5 on 2026-09-05."], scan=True)
    assert inspect_privacy_status(case)["state"] == "AWAITING_PRIVACY_REVIEW"
    with pytest.raises(ValueError, match="PRIVACY GATE"):
        assert_source_approved_for_analysis(case / "sanitized/contract.pdf")
    spec = _file_spec("incoming/return.pdf", file_id="FILE-100")
    review = _review(case, [spec], status="PASS")
    scripted_visual(case, review)
    result = validate_codex_privacy_review(case, review, preservation_policy=RENTAL_PRESERVATION,
                                           supplemental=True)
    assert result["approved_for_analysis"] and len(result["previous_reviews"]) == 1


def test_energy_strict_policy_still_refuses_contact_pdf(tmp_path):
    from againward.core.privacy_rules import LEGACY_PRESERVATION
    create_client_workspace("energy", root=tmp_path, domain_name="energy", intake_payload={})
    case = tmp_path / "energy"
    authorize_test_case(case)
    pdf(case / "incoming/invoice.pdf", ["Contact jean.dupont@supplier.example; power 100 kW."])
    review = _review(case, [_file_spec("incoming/invoice.pdf")], status="PASS")
    with pytest.raises(ValueError):
        validate_codex_privacy_review(case, review, preservation_policy=LEGACY_PRESERVATION)
