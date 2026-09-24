"""Model challenger receipts cannot substitute for original-source QA."""
import pytest


def test_original_source_images_do_not_overwrite_other_sources(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from againward.domains.rental import autonomous_review as module

    documents = [SimpleNamespace(source_id=name, sha256=name * 64) for name in ("a", "b")]
    monkeypatch.setattr(module, "read_json", lambda path: (
        {"extraction": {"path": str(tmp_path / "packages" / "case.json")}}
        if path.name == "artifact_inventory.json" else
        {"schema_version": "againward-rental-document-case-v1", "batch": {}}))
    monkeypatch.setattr(module.SourceBatch, "from_dict", lambda body: SimpleNamespace(documents=documents))
    monkeypatch.setattr(module, "verify_batch", lambda *args: None)
    monkeypatch.setattr(module, "read_document", lambda *args: SimpleNamespace(units=[]))

    def render(document, parsed, root, directory):
        target = directory / "page-1.png"
        target.write_bytes(document.source_id.encode())
        return [target]

    monkeypatch.setattr(module, "_images", render)
    _, images = module._source_context(tmp_path, tmp_path)
    assert len(set(images)) == 2
    assert [path.read_bytes() for path in images] == [b"a", b"b"]

from againward.domains.rental.autonomous_review import (
    _adopt_qa_alternatives, _cite_originals, _evidence_requests,
    _materialize_assessments, _validate_challenge,
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


def test_visual_source_citations_require_attested_observations_not_ocr_guesses():
    sources = [{"source_id": "scan", "units": [{"location": "page:1/visual",
        "route": "VISUAL", "text": "", "attested_quotes": ["Signed return asset LIFT-5"],
        "attached_image_index": 1}]}]
    citation = [{"source_id": "scan", "location": "page:1/visual", "quote": "Signed return asset LIFT-5"}]
    _cite_originals(sources, citation)
    sources[0]["units"][0]["attested_quotes"] = []
    with pytest.raises(ValueError, match="exact original-source quote"):
        _cite_originals(sources, citation)


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
                                      ["q1"], ["handle1"])
    assert result[0]["alternative_tests"][0]["evidence_refs"] == refs
    assert result[0]["evidence_query_ids"] == ["q1"]
    item["alternative_tests"][0]["evidence_ref_indices"] = [1]
    with pytest.raises(ValueError, match="evidence_ref_indices"):
        _materialize_assessments([item], [{"finding_id": "F1", "evidence_refs": refs}],
                                 ["q1"], ["handle1"])


def test_evidence_plane_requests_page_normal_dossiers_without_crossing_budget():
    dataset = {"dataset_id": "rental-case", "dataset_sha256": "a" * 64,
               "fields": [{"key": "record_type"}], "rows": [{}] * 401}
    requests = _evidence_requests(dataset)
    assert [row["arguments"]["start"] for row in requests] == [0, 200, 400]
    assert [row["arguments"]["limit"] for row in requests] == [200, 200, 1]
    assert len({row["query_id"] for row in requests}) == 3
    dataset["rows"] = [{}] * 601
    with pytest.raises(ValueError, match="over 600"):
        _evidence_requests(dataset)


def test_independent_alternative_replaces_misleading_primary_in_final_assessment():
    primary = [{"finding_id": "F1", "best_reason_false": "The second unit remained hired."}]
    challenge = {"reviewed_findings": [{"finding_id": "F1",
                  "best_reason_false": "A documented replacement may explain continued billing."}]}
    final, corrections = _adopt_qa_alternatives(primary, challenge)
    assert final[0]["best_reason_false"] == challenge["reviewed_findings"][0]["best_reason_false"]
    assert corrections[0]["before"] == primary[0]["best_reason_false"]
    assert primary[0]["best_reason_false"] == "The second unit remained hired."
