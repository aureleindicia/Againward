import json
import multiprocessing

import pytest

from energy_mvp import artifact_store as store
from energy_mvp.client_lifecycle import (
    initialize_client_lifecycle, publish_client_requests, record_canonical_answers,
    validate_client_lifecycle_artifacts,
)
from energy_mvp.workflow_paths import inspect_case_status
from benchmarking.architecture_probe import ready, request, answer


@pytest.mark.parametrize("interrupt_at", [1, 2, 3])
def test_interrupted_publish_is_recoverable_without_losing_questions(tmp_path, monkeypatch, interrupt_at):
    ready(tmp_path)
    original = store.atomic_write_json
    calls = 0

    def interrupted(path, value):
        nonlocal calls
        calls += 1
        original(path, value)
        if calls == interrupt_at:
            raise OSError("simulated power interruption")

    with monkeypatch.context() as patch:
        patch.setattr(store, "atomic_write_json", interrupted)
        with pytest.raises(OSError):
            publish_client_requests(tmp_path, [request()])
    assert inspect_case_status(tmp_path)["next_action"] == "RECOVER_ARTIFACT_TRANSACTION"
    with pytest.raises(ValueError, match="RECOVERY_REQUIRED"):
        validate_client_lifecycle_artifacts(tmp_path)
    assert store.recover_artifacts(tmp_path)["recovered"]
    life = validate_client_lifecycle_artifacts(tmp_path)
    assert life["state"] == "WAITING_FOR_REQUIRED_INFORMATION"
    assert life["blocking_request_ids"] == ["Q1"]
    assert not store.recover_artifacts(tmp_path)["recovered"]


def test_invalid_answer_batch_has_no_partial_write(tmp_path):
    ready(tmp_path)
    publish_client_requests(tmp_path, [request()])
    before = (tmp_path / "questions.json").read_bytes()
    with pytest.raises(ValueError):
        record_canonical_answers(tmp_path,[answer(),{**answer(),"request_id":"unknown"}])
    assert (tmp_path / "questions.json").read_bytes() == before


def test_optional_answer_requires_reanalysis_and_blocks_finalization(tmp_path):
    ready(tmp_path)
    publish_client_requests(tmp_path, [request(blocking=False)])
    assert record_canonical_answers(tmp_path, [answer()])["state"] == "RESUMING"
    life = validate_client_lifecycle_artifacts(tmp_path)
    assert life["suspended_hypothesis_ids"] == ["H1"]


def test_recovery_refuses_external_changes(tmp_path, monkeypatch):
    ready(tmp_path)
    original = store._replay
    count = 0

    def fail(root):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError("interrupt after durable commit")
        return original(root)

    with monkeypatch.context() as patch:
        patch.setattr(store, "_replay", fail)
        with pytest.raises(OSError):
            publish_client_requests(tmp_path, [request()])
    (tmp_path / "questions.json").write_text('{"external":"change"}')
    with pytest.raises(ValueError, match="outside transaction"):
        store.recover_artifacts(tmp_path)
    assert json.loads((tmp_path / "questions.json").read_text()) == {"external":"change"}


def _try_publish(path, queue):
    try:
        publish_client_requests(path, [request()])
        queue.put("unexpected success")
    except ValueError as exc:
        queue.put(str(exc))


def test_concurrent_process_cannot_overwrite_active_transaction(tmp_path):
    ready(tmp_path)
    # spawn avoids inheriting the transaction ContextVar or lock descriptor.
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    with store.transaction(tmp_path):
        child = context.Process(target=_try_publish,args=(tmp_path,queue))
        child.start()
        child.join(timeout=10)
        assert child.exitcode == 0
        assert "another process" in queue.get(timeout=1)
    assert validate_client_lifecycle_artifacts(tmp_path)["cycle_count"] == 0


def test_path_escape_and_nonfinite_data_rollback(tmp_path):
    initialize_client_lifecycle(tmp_path)
    with pytest.raises(ValueError):
        with store.transaction(tmp_path):
            store.write_json(tmp_path / "../outside.json", {"x":1})
    with pytest.raises(ValueError):
        with store.transaction(tmp_path):
            store.write_json(tmp_path / "invalid.json", {"x":float("nan")})
    assert not (tmp_path / "invalid.json").exists()
