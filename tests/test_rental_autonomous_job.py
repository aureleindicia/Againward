"""The reviewed-package job is resumable and cannot hide a changed source."""
from pathlib import Path

import pytest

from againward.cli import main
from againward.core.artifact_store import write_json
from againward.core.workflow import fingerprint
from againward.domains.rental.autonomous_job import _completed_report, run_reviewed_package_job
from againward.domains.rental.autonomous_report import current_report_versions
from againward.evidence.hashing import stable_hash


def test_job_refuses_package_mutation_before_resuming(tmp_path):
    package = tmp_path / "reviewed-package.json"
    package.write_text("{}", encoding="utf-8")
    root = tmp_path / "case"
    write_json(root / "investigation_state.json", {"source": {"sha256": "0" * 64}})
    with pytest.raises(ValueError, match="changed"):
        run_reviewed_package_job(package, root, model="test-model")


def test_cli_routes_to_one_rental_job_without_delivery_approval(tmp_path, monkeypatch, capsys):
    def job(package, output, *, model, timeout_seconds, evaluation_only):
        assert Path(package) == tmp_path / "package.json"
        assert Path(output) == tmp_path / "output"
        assert model == "test-model" and timeout_seconds == 300
        assert evaluation_only is True
        return {"status": "EVALUATION_ONLY_QA_PASSED", "approved_for_delivery": False}

    monkeypatch.setattr("againward.domains.rental.autonomous_job.run_reviewed_package_job", job)
    code = main(["rental-autonomous", str(tmp_path / "package.json"), "--output-dir",
                 str(tmp_path / "output"), "--model", "test-model",
                 "--timeout-seconds", "300", "--evaluation-only"])
    assert code == 0
    assert "EVALUATION_ONLY_QA_PASSED" in capsys.readouterr().out


def test_completed_job_replay_is_hash_bound_and_never_approves(tmp_path):
    root = tmp_path / "case"
    root.mkdir()
    for name in ("rental_client_report.pdf", "rental_evidence_pack.json", "report.md"):
        (root / name).write_bytes(name.encode())
    receipt = {"status": "EVALUATION_ONLY_QA_PASSED", "binding": {"versions": current_report_versions()}, "attempts": [{
        "pdf_sha256": fingerprint(root / "rental_client_report.pdf"),
        "evidence_pack_sha256": fingerprint(root / "rental_evidence_pack.json"),
        "report_md_sha256": fingerprint(root / "report.md")}]}
    receipt["receipt_sha256"] = stable_hash(receipt)
    path = root / "autonomous_report" / "receipt.json"
    write_json(path, receipt)
    job = {"state": "EVALUATION_ONLY_QA_PASSED", "events": [{"receipt": str(path)}]}
    result = _completed_report(root, job)
    assert result["status"] == "EVALUATION_ONLY_QA_PASSED"
    assert result["approved_for_delivery"] is False
    (root / "rental_client_report.pdf").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="artifacts changed"):
        _completed_report(root, job)
