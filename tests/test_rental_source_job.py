"""An approved-source job cannot silently cross privacy or source mutations."""
import pytest

from againward.core.workspace import create_client_workspace
from againward.documents.contracts import DocumentError
from againward.domains.rental.source_job import _source_snapshot, run_approved_sources_job


def test_real_case_waits_for_privacy_before_source_inspection(tmp_path, monkeypatch):
    create_client_workspace("case", root=tmp_path, synthetic=False,
                            domain_name="rental", intake_payload={})
    case = tmp_path / "case"
    (case / "incoming" / "raw.pdf").write_bytes(b"unapproved source")
    monkeypatch.setattr("againward.domains.rental.source_job._source_snapshot",
                        lambda folder: pytest.fail("raw source inspected before clearance"))
    result = run_approved_sources_job(case, model="test-model")
    assert result["status"] == "WAITING_FOR_PRIVACY_REVIEW"
    assert not (case / "processed" / "source_job_state.json").exists()


def test_resume_archives_prior_state_and_restarts_after_changed_approved_bytes(tmp_path, monkeypatch):
    create_client_workspace("case", root=tmp_path, synthetic=True,
                            domain_name="rental", intake_payload={})
    case = tmp_path / "case"
    source = case / "incoming" / "invoice.txt"
    source.write_text("invoice one", encoding="utf-8")
    def interrupt(*args, **kwargs):
        raise RuntimeError("fixture interruption after intake")

    monkeypatch.setattr("againward.domains.rental.source_job.inventory_sources", interrupt)
    with pytest.raises(RuntimeError, match="fixture interruption"):
        run_approved_sources_job(case, model="test-model")
    assert (case / "processed" / "source_job_state.json").exists()
    source.write_text("invoice two", encoding="utf-8")
    with pytest.raises(RuntimeError, match="fixture interruption"):
        run_approved_sources_job(case, model="test-model")
    from againward.core.artifact_store import read_json
    archives = list((case / "scratch/rental_revisions").iterdir())
    assert len(archives) == 1
    old = read_json(archives[0] / "source_job_state.json")
    new = read_json(case / "processed/source_job_state.json")
    assert old["binding"] != new["binding"]
    assert new["primary"] == {} and new["approved_for_delivery"] is False


def test_snapshot_rejects_symlinked_source(tmp_path):
    folder = tmp_path / "approved"
    folder.mkdir()
    external = tmp_path / "outside.txt"
    external.write_text("never follow me", encoding="utf-8")
    (folder / "invoice.txt").symlink_to(external)
    with pytest.raises(DocumentError, match="SOURCE_UNSAFE_PATH"):
        _source_snapshot(folder)


def test_model_timeout_leaves_resumable_source_snapshot(tmp_path, monkeypatch):
    create_client_workspace("case", root=tmp_path, synthetic=True,
                            domain_name="rental", intake_payload={})
    case = tmp_path / "case"
    (case / "incoming" / "agreement.txt").write_text(
        "Accepted agreement A1; supplier S; client C; rental item R.", encoding="utf-8")

    def timeout(*args, **kwargs):
        raise DocumentError("MODEL_TIMEOUT", "controlled test failure")

    monkeypatch.setattr("againward.documents.codex_provider.CodexCliProvider.propose", timeout)
    result = run_approved_sources_job(case, model="test-model")
    assert result["status"] == "WAITING_MODEL_RETRY"
    assert result["reason_code"] == "MODEL_TIMEOUT"
    from againward.core.artifact_store import read_json
    state = read_json(case / "processed" / "source_job_state.json")
    assert state["phase"] == "WAITING_MODEL_RETRY"
    assert state["batch_receipt"]
    assert not state["primary"]


def test_parallel_case_invocation_does_not_start_another_reader(tmp_path, monkeypatch):
    import fcntl
    create_client_workspace("case", root=tmp_path, synthetic=True,
                            domain_name="rental", intake_payload={})
    case = tmp_path / "case"
    monkeypatch.setattr("againward.domains.rental.source_job._run_approved_sources_job",
                        lambda *a, **k: pytest.fail("second writer entered"))
    with (case / ".rental-job.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = run_approved_sources_job(case, model="test-model")
    assert result["reason_code"] == "CASE_ALREADY_RUNNING"
