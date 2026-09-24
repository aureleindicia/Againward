"""Model challenger receipts cannot substitute for original-source QA."""
import pytest

from againward.domains.rental.autonomous_review import (
    _cite_originals, _materialize_assessments, _validate_challenge,
)
from againward.domains.rental.domain_pack import RentalDomainPack


def _sources():
    return [{"source_id": "contract", "units": [{"location": "page:1", "route": "NATIVE",
            "text": "One unit at the accepted weekly rate."}]},
            {"source_id": "invoice", "units": [{"location": "page:1", "route": "NATIVE",
            "text": "Two units were billed."}]}]


def _challenge():
    return {"verdict": "PASS", "missed_discrepancies": [], "source_citations": [
        {"source_id": "contract", "location": "page:1", "quote": "One unit"},
        {"source_id": "invoice", "location": "page:1", "quote": "Two units"}],
        "reviewed_findings": [{"finding_id": "F1", "best_reason_false": "A replacement unit may exist.",
             "checks": {name: {"status": "passed", "evidence": "Source and calculation reviewed."}
                        for name in RentalDomainPack.review_checks}}]}


def test_challenger_must_cite_every_original_native_source():
    _cite_originals(_sources(), _challenge()["source_citations"])
    missing = _challenge()["source_citations"][:1]
    with pytest.raises(ValueError, match="omitted an original"):
        _cite_originals(_sources(), missing)
    invented = _challenge()["source_citations"]
    invented[0]["quote"] = "Three units"
    with pytest.raises(ValueError, match="exact original-source quote"):
        _cite_originals(_sources(), invented)


def test_qa_cannot_pass_with_omission_or_failed_material_check():
    candidates = [{"finding_id": "F1", "evidence_level": "L2"}]
    assessments = [{"finding_id": "F1", "status": "A_CONSERVER_AVEC_RESERVES"}]
    assert _validate_challenge(_challenge(), candidates, _sources(), assessments)
    omitted = _challenge()
    omitted["missed_discrepancies"] = ["Unreviewed second invoice"]
    with pytest.raises(ValueError, match="cannot pass"):
        _validate_challenge(omitted, candidates, _sources(), assessments)
    skipped = _challenge()
    skipped["reviewed_findings"][0]["checks"]["contract_authority"]["status"] = "not_applicable"
    with pytest.raises(ValueError, match="cannot pass"):
        _validate_challenge(skipped, candidates, _sources(), assessments)
    stopped = _challenge()
    stopped["verdict"] = "STOP"
    assert not _validate_challenge(stopped, candidates, _sources(), assessments)
    abstained = _challenge()
    abstained["reviewed_findings"][0]["checks"]["contract_authority"]["status"] = "failed"
    assert _validate_challenge(abstained, candidates, _sources(),
                               [{"finding_id": "F1", "status": "ABSTAIN"}])


def test_model_selects_existing_source_refs_by_index_not_free_text():
    refs = [{"document_id": "contract", "location": "page:1", "field": "rate"}]
    item = {"finding_id": "F1", "alternative_tests": [{"test_id": "T1",
            "description": "Check accepted rate", "result": "REFUTED", "evidence_ref_indices": [0]}]}
    result = _materialize_assessments([item], [{"finding_id": "F1", "evidence_refs": refs}],
                                      "q1", ["handle1"])
    assert result[0]["alternative_tests"][0]["evidence_refs"] == refs
    assert result[0]["evidence_query_ids"] == ["q1"]
    item["alternative_tests"][0]["evidence_ref_indices"] = [1]
    with pytest.raises(ValueError, match="evidence_ref_indices"):
        _materialize_assessments([item], [{"finding_id": "F1", "evidence_refs": refs}],
                                 "q1", ["handle1"])
