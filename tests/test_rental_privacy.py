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
