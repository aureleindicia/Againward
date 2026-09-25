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


def test_revision_preserves_used_evidence_budget(tmp_path):
    from againward.core.artifact_store import read_json
    from againward.core.workflow import prepare_investigation
    from againward.domains.rental.source_job import _remaining_revision_budget
    from againward.entrypoints import get_domain
    from againward.evidence.protocol import QueryBudget
    from benchmarking.rental_review import synthetic_review
    from tests.test_rental_ingestion import write_packet

    source, _ = write_packet(tmp_path / "sources")
    old = tmp_path / "old"
    prepare_investigation(source, old, domain=get_domain("rental"))
    synthetic_review(old)
    remaining = _remaining_revision_budget(old)
    assert remaining["maximum_calls"] == 15
    assert remaining["maximum_returned_rows"] < 600
    fresh = tmp_path / "fresh"
    prepare_investigation(source, fresh, domain=get_domain("rental"), evidence_budget=QueryBudget(**remaining))
    assert read_json(fresh / "evidence_query_session.json")["budget"] == remaining


def test_revision_recovers_interruption_after_archive_without_budget_reset(tmp_path):
    from againward.core.artifact_store import read_json, write_json
    from againward.domains.rental.source_job import _finish_revision, _remaining_revision_budget
    from againward.evidence.hashing import stable_hash

    case = tmp_path / "case"
    archive = case / "scratch/rental_revisions/old"
    archive.mkdir(parents=True)
    (archive / "retained.txt").write_text("Prior evidence and approvals remain archived.")
    binding = {"revision": "new"}
    origin = {"archived_directory": str(archive), "current_binding": binding,
              "remaining_evidence_budget": {"maximum_calls": 9}}
    journal = {"status": "PENDING", "origin": origin}
    journal["sha256"] = stable_hash(journal)
    write_json(case / ".rental-revision.json", journal)
    _finish_revision(case, binding)
    assert read_json(case / "processed/revision_origin.json") == origin
    assert _remaining_revision_budget(case / "processed") == {"maximum_calls": 9}
    assert read_json(case / ".rental-revision.json")["status"] == "COMPLETED"
    _finish_revision(case, binding)
    assert (archive / "retained.txt").exists()


def test_source_pass_reuse_is_limited_to_adjudication_or_visual_policy_only():
    from copy import deepcopy
    from againward.domains.rental.source_job import _only_adjudication_policy_changed
    old = {"sources": [{"sha256": "a" * 64}], "model": "fixture-model", "privacy": "old",
           "versions": ["job", "qa", "adjudication-v1", "native", "visual", "report"]}
    new = deepcopy(old)
    new["versions"][2] = "adjudication-v2"
    assert _only_adjudication_policy_changed(old, new)
    visual_only = deepcopy(old)
    visual_only["versions"][4] = "visual-model-v2"
    assert _only_adjudication_policy_changed(old, visual_only)
    for key in ("sources", "model", "privacy"):
        changed = deepcopy(new)
        changed[key] = "changed"
        assert not _only_adjudication_policy_changed(old, changed)
    for index in (0, 1, 3, 5):
        changed = deepcopy(new)
        changed["versions"][index] = "changed"
        assert not _only_adjudication_policy_changed(old, changed)
