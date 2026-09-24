"""Report QA must challenge the actual PDF against original source quotes."""
import pytest

from againward.core.artifact_store import write_json
from againward.domains.rental.autonomous_report import _validate_report_qa, _verified_pack_manifest


def _sources():
    return [{"source_id": "agreement", "units": [{"location": "page:1", "route": "NATIVE",
              "text": "Billing stops on signed return."}]},
            {"source_id": "invoice", "units": [{"location": "page:1", "route": "NATIVE",
              "text": "Net rental charge EUR 800."}]}]


def _qa():
    return {"verdict": "PASS", "source_citations": [
        {"source_id": "agreement", "location": "page:1", "quote": "signed return"},
        {"source_id": "invoice", "location": "page:1", "quote": "Net rental charge"}],
        "unsupported_claims": [], "missed_discrepancies": [],
        "financial_check": "Source amounts and one disjoint group checked against the report.",
        "correction_guidance": ""}


def test_report_qa_rejects_unsupported_claims_and_uncited_sources():
    assert _validate_report_qa(_qa(), _sources())
    unsupported = _qa()
    unsupported["unsupported_claims"] = ["Report calls the difference a guaranteed refund."]
    with pytest.raises(ValueError, match="cannot pass"):
        _validate_report_qa(unsupported, _sources())
    missing = _qa()
    missing["source_citations"] = missing["source_citations"][:1]
    with pytest.raises(ValueError, match="omitted an original"):
        _validate_report_qa(missing, _sources())
    revise = _qa()
    revise["verdict"] = "REVISE"
    revise["unsupported_claims"] = ["Overstated claim"]
    assert not _validate_report_qa(revise, _sources())


def test_pack_manifest_claims_only_contents_present_in_verified_pack(tmp_path):
    pack = {"schema_version": "test", "documents": [{"sha256": "a" * 64}],
            "document_lineage": {"facts": [{"candidate": {"location": "page:1",
                                  "raw_observed_value": "accepted term"}}],
                                 "rental_resolution": {"decision": "LINKED"}},
            "charge_groups": [{}], "expected_ledger": {"entries": [{}]},
            "actual_ledger": {"entries": [{}]}, "review_sha256": "b" * 64,
            "investigation_sha256": "c" * 64,
            "findings": {"findings": [{"unresolved_questions": ["Later credit?"]}]}}
    write_json(tmp_path / "rental_evidence_pack.json", pack)
    manifest = _verified_pack_manifest(pack, tmp_path)
    assert manifest["source_integrity_hashes_retained"] is True
    assert manifest["quoted_spans_retained"] == 1
    assert manifest["entity_link_decisions_retained"] is True
    assert manifest["open_questions_retained"] == 1
    altered = {**pack, "review_sha256": "d" * 64}
    with pytest.raises(ValueError, match="differs"):
        _verified_pack_manifest(altered, tmp_path)
