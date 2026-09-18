import json

import pytest

from againward.core.privacy import validate_codex_privacy_review, inspect_privacy_status
from againward.core.workspace import create_client_workspace
from againward.domains.rental.privacy_policy import RENTAL_PRESERVATION
from againward.entrypoints import get_case_domain
from tests.contract_fixtures import authorize_test_case
from tests.test_privacy_gate import _review, _file_spec, _category, _transform


def setup_case(tmp_path):
    create_client_workspace("rental", root=tmp_path, domain_name="rental", intake_payload={"profile": "generic"})
    case = tmp_path / "rental"
    authorize_test_case(case)
    return case


def test_json_monetary_mutation_is_blocked_during_privacy_cleanup(tmp_path):
    case = setup_case(tmp_path)
    original = {"invoice_id": "I1", "net_amount": "700.00", "email": "person@example.com"}
    (case / "incoming/invoice.json").write_text(json.dumps(original))
    (case / "privacy/candidate/invoice.json").write_text(json.dumps({"invoice_id": "I1", "net_amount": "900.00"}))
    review = _review(case, [_file_spec("incoming/invoice.json", action="SANITIZED",
        sanitized="privacy/candidate/invoice.json", transformations=[_transform("EMAIL", "REMOVED")])],
        status="SANITIZED", categories=[_category("EMAIL", "REMOVED")])
    with pytest.raises(ValueError, match="Business JSON value"):
        validate_codex_privacy_review(case, review, preservation_policy=RENTAL_PRESERVATION)
    assert inspect_privacy_status(case)["state"] == "PRIVACY_BLOCKED"


def test_rental_json_cleanup_preserves_commercial_records_and_exposes_policy(tmp_path):
    case = setup_case(tmp_path)
    cleaned = {"invoice_id": "0612345678", "net_amount": "700.00", "currency": "EUR"}
    (case / "incoming/invoice.json").write_text(json.dumps({**cleaned, "email": "person@example.com"}))
    (case / "privacy/candidate/invoice.json").write_text(json.dumps(cleaned))
    review = _review(case, [_file_spec("incoming/invoice.json", action="SANITIZED",
        sanitized="privacy/candidate/invoice.json", transformations=[_transform("EMAIL", "REMOVED")])],
        status="SANITIZED", categories=[_category("EMAIL", "REMOVED")])
    policy = get_case_domain(case).privacy_preservation
    assert policy is RENTAL_PRESERVATION
    manifest = validate_codex_privacy_review(case, review, preservation_policy=policy)
    assert manifest["approved_for_analysis"]
    assert manifest["business_preservation_policy"] == "rental-preservation-v1"
    assert json.loads((case / "sanitized/invoice.json").read_text()) == cleaned


def test_explicit_json_personal_fields_cannot_pass_without_minimization(tmp_path):
    case = setup_case(tmp_path)
    (case / "incoming/invoice.json").write_text(json.dumps({"invoice_id": "I1", "employee_name": "Example Person"}))
    review = _review(case, [_file_spec("incoming/invoice.json")], status="PASS")
    with pytest.raises(ValueError):
        validate_codex_privacy_review(case, review, preservation_policy=RENTAL_PRESERVATION)
    assert not inspect_privacy_status(case)["approved_for_analysis"]


def test_additional_document_has_its_own_privacy_gate_and_preserves_real_case_wait(tmp_path):
    from againward.core.artifact_store import read_json
    from againward.core.workflow import prepare_investigation, fingerprint
    from againward.core.client_lifecycle import (record_existing_data_exhaustion, publish_client_requests,
        record_canonical_answers, complete_resume, mark_finalizable, RESUME_DIMENSIONS)
    from againward.domains.rental.workflow import recalculate
    from againward.domains.rental.review_policy import validate_current_review
    from benchmarking.rental import _blocking_request
    from benchmarking.rental_cases import cases, write_sources
    from benchmarking.rental_review import query_sources, synthetic_review
    case = setup_case(tmp_path)
    packet = cases()[0]["R06_ambiguous_return"]
    write_sources(case / "incoming", packet)
    files = sorted((case / "incoming").iterdir())
    specs = [_file_spec("incoming/" + path.name) for path in files]
    for i, spec in enumerate(specs, 1): spec["file_id"] = f"FILE-{i:03d}"
    validate_codex_privacy_review(case, _review(case, specs, status="PASS"), preservation_policy=RENTAL_PRESERVATION)
    root = case / "processed"
    prepare_investigation(case / "sanitized/extraction.json", root, domain=get_case_domain(case))
    original = (root / "prepared_analysis.json").read_bytes()
    record_existing_data_exhaustion(root, analysis_inventory_ref="artifact_inventory.json", reviewed_sources=[p.name for p in files])
    ids = [c["finding_id"] for c in read_json(root / "prepared_analysis.json")["candidates"]]
    publish_client_requests(root, [_blocking_request(ids)])
    (case / "incoming/signed_return.txt").write_text("SYNTHETIC signed return: full quantity 1, 2026-09-05, agreement A1.")
    assert inspect_privacy_status(case)["state"] == "AWAITING_PRIVACY_REVIEW"
    with pytest.raises(ValueError, match="PRIVACY"): query_sources(root)
    spec = _file_spec("incoming/signed_return.txt"); spec["file_id"] = "FILE-100"
    manifest = validate_codex_privacy_review(case, _review(case, [spec], status="PASS"),
        preservation_policy=RENTAL_PRESERVATION, supplemental=True)
    assert manifest["approved_for_analysis"] and len(manifest["previous_reviews"]) == 1
    assert (root / "prepared_analysis.json").read_bytes() == original
    assert read_json(root / "investigation_state.json")["client_lifecycle"]["state"] == "WAITING_FOR_REQUIRED_INFORMATION"
    with pytest.raises(ValueError, match="STOP"): query_sources(root)
    revised = read_json(case / "sanitized/extraction.json")
    for doc in revised["documents"]:
        doc["path"] = "../sanitized/" + doc["path"]
    revised["documents"].append({"document_id": "SIGNED_RETURN", "role": "RETURN_NOTE", "status": "ACCEPTED",
        "path": "../sanitized/signed_return.txt", "sha256": fingerprint(case / "sanitized/signed_return.txt")})
    revised["events"][0].update(verification="DOCUMENTED", evidence_refs=[{"document_id": "SIGNED_RETURN", "location": "line:1"}])
    source = root / "revised_extraction.json"; source.write_text(json.dumps(revised))
    record_canonical_answers(root, [{"answer_id": "TEST-ANSWER", "request_id": "RETURN-PROOF",
        "answer": "Synthetic full signed return supplied.", "provided_by_role": "TEST coordinator",
        "source_or_evidence": "sanitized/signed_return.txt", "source_type": "EXISTING_DOCUMENT",
        "provided_at_utc": "2026-09-18T09:00:00Z"}])
    from againward.domains.rental.workflow import current_calculations
    with pytest.raises(ValueError, match="Privacy evidence batch changed"):
        current_calculations(root)
    recalculate(root, source)
    synthetic_review(root); validate_current_review(root)
    complete_resume(root, recalculation_refs=["prepared_analysis.json"], adversarial_review_ref="review.json",
        before_after=[{"hypothesis_id": fid, "before": "unverified", "after": "signed evidence",
            "decision_dimensions": {key: "Reviewed in the synthetic review." for key in RESUME_DIMENSIONS}} for fid in ids])
    assert mark_finalizable(root, conclusion_ref="investigation.json")["client_lifecycle"]["state"] == "FINALIZABLE"
    assert read_json(root / "prepared_analysis.json")["totals_by_currency"]["EUR"]["supported_positive_discrepancy"] == "300.00"
    (case / "incoming/context.txt").write_text("Additional synthetic supplier context; no personal details.")
    spec = _file_spec("incoming/context.txt"); spec["file_id"] = "FILE-101"
    validate_codex_privacy_review(case, _review(case, [spec], status="PASS"),
        preservation_policy=RENTAL_PRESERVATION, supplemental=True)
    life = read_json(root / "investigation_state.json")["client_lifecycle"]
    assert life["state"] == "RESUMING" and life["resume_required"]
    with pytest.raises(ValueError, match="Privacy evidence batch changed"):
        current_calculations(root)


def test_additional_privacy_refuses_to_replace_previous_source(tmp_path):
    case = setup_case(tmp_path)
    (case / "incoming/invoice.json").write_text('{"net_amount":"700.00"}')
    validate_codex_privacy_review(case, _review(case, [_file_spec("incoming/invoice.json")], status="PASS"), preservation_policy=RENTAL_PRESERVATION)
    previous = (case / "sanitized/invoice.json").read_bytes()
    (case / "incoming/invoice.json").write_text('{"net_amount":"850.00"}')
    spec = _file_spec("incoming/invoice.json"); spec["file_id"] = "FILE-100"
    with pytest.raises(FileExistsError, match="cannot replace"):
        validate_codex_privacy_review(case, _review(case, [spec], status="PASS"), preservation_policy=RENTAL_PRESERVATION, supplemental=True)
    assert (case / "sanitized/invoice.json").read_bytes() == previous
    assert not inspect_privacy_status(case)["approved_for_analysis"]
