"""Scripted first-reader tests validate control flow, not model accuracy."""
import json

import pytest

from againward.core.workspace import create_client_workspace
from againward.documents.contracts import DocumentError
from againward.domains.rental import privacy_job
from againward.domains.rental.source_job import _source_snapshot
from benchmarking.rental_privacy import _case


def _scripted_answer(prompt, images, **kwargs):
    data = json.loads(prompt.rsplit("\n", 1)[1])
    from pathlib import Path
    review = data["review_template"]
    review["codex_semantic_review"] = {"completed": True, "first_substantive_reader_attested": True}
    return {"status": "REVIEWED", "review": review,
            "source_hashes": _source_snapshot(Path(data["workspace"]) / "incoming")}, 0.01


def test_raw_privacy_never_calls_model_without_contract_authority(tmp_path, monkeypatch):
    create_client_workspace("case", root=tmp_path, synthetic=False, domain_name="rental", intake_payload={})
    monkeypatch.setattr(privacy_job, "_ask", lambda *a, **k: pytest.fail("unauthorized model call"))
    result = privacy_job.run_privacy_intake(tmp_path / "case", model="test", timeout_seconds=30)
    assert result["reason_code"] == "CONTRACT_AUTHORITY_REQUIRED"


def test_native_postcheck_follows_first_reader_and_promotes_exact_bytes(tmp_path, monkeypatch):
    case = _case(tmp_path, "native")
    original = b"Accepted rental agreement AG-12. Rate EUR 50.00 per day."
    (case / "incoming/agreement.txt").write_bytes(original)
    called = []

    def answer(*args, **kwargs):
        assert not list((case / "sanitized").iterdir())
        called.append(True)
        return _scripted_answer(*args, **kwargs)

    prepare = privacy_job.prepare_visual_packet

    def after_reader(*args):
        assert called
        return prepare(*args)

    monkeypatch.setattr(privacy_job, "_ask", answer)
    monkeypatch.setattr(privacy_job, "prepare_visual_packet", after_reader)
    result = privacy_job.run_privacy_intake(case, model="test", timeout_seconds=30)
    assert result["approved_for_analysis"] is True
    assert [p.read_bytes() for p in (case / "sanitized").iterdir()] == [original]
    assert not list((case / "incoming").iterdir())


def test_model_pass_cannot_override_high_risk_postcheck(tmp_path, monkeypatch):
    case = _case(tmp_path, "unsafe")
    (case / "incoming/hr.txt").write_text("Personnel file: disciplinary action.")
    monkeypatch.setattr(privacy_job, "_ask", _scripted_answer)
    with pytest.raises(ValueError):
        privacy_job.run_privacy_intake(case, model="test", timeout_seconds=30)
    assert not privacy_job.inspect_privacy_status(case)["approved_for_analysis"]
    assert not list((case / "sanitized").iterdir())


def test_model_cannot_fabricate_visual_attestation(tmp_path, monkeypatch):
    case = _case(tmp_path, "forgery")
    (case / "incoming/agreement.txt").write_text("Rental EUR 50.00 per day.")

    def forged(*args, **kwargs):
        payload, seconds = _scripted_answer(*args, **kwargs)
        payload["review"]["files"][0]["visual_reviews"] = [{"reviewer_role": "HUMAN"}]
        return payload, seconds

    monkeypatch.setattr(privacy_job, "_ask", forged)
    with pytest.raises(DocumentError, match="cannot fabricate"):
        privacy_job.run_privacy_intake(case, model="test", timeout_seconds=30)
    assert not (case / "privacy/autonomous_review.json").exists()


def test_scan_waits_for_actual_visual_attestation_and_reuses_first_read(tmp_path, monkeypatch):
    from benchmarking.document_renderers import pdf
    case = _case(tmp_path, "scan")
    pdf(case / "incoming/return.pdf", ["Signed return asset LIFT-5."], scan=True)
    monkeypatch.setattr(privacy_job, "_ask", _scripted_answer)
    result = privacy_job.run_privacy_intake(case, model="test", timeout_seconds=30)
    assert result["status"] == "WAITING_FOR_VISUAL_ATTESTATION"
    monkeypatch.setattr(privacy_job, "_ask", lambda *a, **k: pytest.fail("unnecessary repeated model call"))
    assert privacy_job.run_privacy_intake(case, model="test", timeout_seconds=30)["status"] == result["status"]
    assert not list((case / "sanitized").iterdir())


def test_hash_order_is_not_a_material_source_difference(tmp_path, monkeypatch):
    case = _case(tmp_path, "order")
    for name in ("a.txt", "b.txt"):
        (case / "incoming" / name).write_text("Agreement AG-12 EUR 50.00 per day.")

    def reordered(*args, **kwargs):
        payload, seconds = _scripted_answer(*args, **kwargs)
        payload["source_hashes"].reverse()
        return payload, seconds

    monkeypatch.setattr(privacy_job, "_ask", reordered)
    assert privacy_job.run_privacy_intake(case, model="test", timeout_seconds=30)["approved_for_analysis"]
