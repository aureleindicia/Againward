from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import benchmarking.physical_expertise as benchmark
from benchmarking.physical_expertise import (
    BenchmarkError,
    BenchmarkIntegrityError,
    finalize_run,
    prepare_run,
    reveal_followups,
    run_manifest_for,
    tree_commitment,
    validate_case_directory,
    validate_response,
    validate_scorecard,
    verify_event_log,
    verify_run_integrity,
)


REPOSITORY = Path(__file__).resolve().parents[1]
BASELINE = "expert-benchmark-baseline-v1"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _make_case(tmp_path: Path, *, stage: str = "DEV") -> Path:
    case = tmp_path / "private_cases" / "case_900"
    initial = case / "initial_client_pack"
    oracle_root = case / "followup_oracle"
    payloads = oracle_root / "payloads"
    truth = case / "ground_truth"
    for directory in (initial, payloads, truth):
        directory.mkdir(parents=True)
    (initial / "client_readings.csv").write_text(
        "timestamp,power_kw\n2026-01-01T00:00:00+01:00,10\n", encoding="utf-8"
    )
    (payloads / "payload_001.csv").write_text(
        "timestamp,state\n2026-01-01T00:00:00+01:00,on\n", encoding="utf-8"
    )
    (payloads / "payload_002.txt").write_text("private future note\n", encoding="utf-8")
    _write_json(oracle_root / "oracle.json", {
        "schema_version": 1,
        "case_id": "case_900",
        "entries": [
            {
                "oracle_id": "item_001",
                "accepted_concepts": ["equipment schedule"],
                "question_terms": ["schedule", "equipment"],
                "minimum_term_matches": 2,
                "availability": "available",
                "cost": 1,
                "response": "The equipment schedule is attached.",
                "responder_role": "site manager",
                "payload_files": ["payloads/payload_001.csv"],
            },
            {
                "oracle_id": "item_002",
                "accepted_concepts": ["maintenance history"],
                "question_terms": ["maintenance", "history"],
                "minimum_term_matches": 2,
                "availability": "available",
                "cost": 2,
                "response": "The maintenance history is attached.",
                "responder_role": "maintenance manager",
                "payload_files": ["payloads/payload_002.txt"],
            },
            {
                "oracle_id": "item_003",
                "accepted_concepts": ["meter verification"],
                "question_terms": ["meter", "verification"],
                "minimum_term_matches": 2,
                "availability": "unavailable",
                "cost": 0,
                "response": "The client cannot verify the meter during this run.",
                "responder_role": "site manager",
                "payload_files": [],
            },
        ],
    })
    _write_json(truth / "truth.json", {
        "secret_marker": "THIS_MUST_NEVER_REACH_THE_PARTICIPANT",
        "reference_decision": "NORMAL_OPERATION",
    })
    manifest = {
        "schema_version": 1,
        "case_id": "case_900",
        "case_revision": 1,
        "stage": stage,
        "track": "CONTROLLED_OPEN_BOOK",
        "difficulty": "D2",
        "truth_level": "SYNTHETIC",
        "sector": "test fixture only",
        "initial_pack_commitment_sha256": tree_commitment(initial),
        "oracle_commitment_sha256": tree_commitment(oracle_root),
        "ground_truth_commitment_sha256": tree_commitment(truth),
        "max_question_cycles": 3,
        "efficiency_penalty_after_requests": 5,
        "allowed_references": [],
    }
    _write_json(case / "case_manifest.json", manifest)
    return case


def _prepare(tmp_path: Path, *, stage: str = "DEV", run_id: str = "run_001", run_index: int = 1) -> tuple[Path, Path]:
    case = _make_case(tmp_path, stage=stage)
    run = prepare_run(
        case,
        tmp_path / "runs",
        run_id=run_id,
        repository=REPOSITORY,
        system_ref=BASELINE,
        model="test-model-exact",
        reasoning_effort="test-reasoning-exact",
        run_index=run_index,
    )
    return case, run


def _request(request_id: str, *, concept: str, question: str) -> dict:
    return {
        "request_id": request_id,
        "question": question,
        "requested_concepts": [concept],
        "best_responder": "site manager",
        "why": "This separates an operating explanation from an equipment explanation.",
        "hypotheses_distinguished": ["operating cause", "equipment cause"],
        "expected_effort": "ten minutes",
    }


def _valid_response(case_id: str, decision: str) -> dict:
    return {
        "schema_version": 1,
        "case_id": case_id,
        "observation": {
            "facts": ["Only the supplied measurements were used."],
            "data_quality": ["The sample is short."],
            "phenomenon_to_explain": "No physical cause can be established from this sample.",
        },
        "differential_diagnosis": [],
        "current_decision": decision,
        "next_information": {
            "needed": False,
            "question": "",
            "best_responder": "",
            "why": "",
            "hypotheses_distinguished": [],
            "expected_effort": "",
        },
        "intervention": {
            "class": "OBSERVE",
            "action": "Keep the installation unchanged.",
            "competent_person": "site manager",
            "preconditions": [],
            "risks": [],
            "stop_conditions": [],
            "expected_result": "Preserve a comparable reference period.",
        },
        "validation": {
            "metric": "daily energy",
            "period": "next comparable week",
            "controls": ["production schedule"],
            "confirming_result": "The same pattern recurs.",
            "falsifying_result": "The pattern does not recur.",
        },
        "economics": {
            "observed_abnormal_energy": "unknown",
            "energy_attributable_to_cause": "unknown",
            "recoverable_fraction": "unknown",
            "financial_savings": "unknown",
        },
        "confidence": {
            "main_cause": 0.0,
            "intervention": 0.2,
            "justification": "There is not enough evidence for a physical cause.",
        },
    }


def test_case_validation_never_reads_or_hashes_ground_truth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    case = _make_case(tmp_path)
    original = benchmark.file_manifest
    observed: list[Path] = []

    def recording_manifest(root: str | Path) -> list[dict]:
        observed.append(Path(root).resolve())
        return original(root)

    monkeypatch.setattr(benchmark, "file_manifest", recording_manifest)
    result = validate_case_directory(case)

    assert result["manifest"]["case_id"] == "case_900"
    assert (case / "ground_truth").resolve() not in observed


def test_prepare_exposes_only_initial_pack_and_committed_engine(tmp_path: Path) -> None:
    _, run = _prepare(tmp_path)
    participant = run / "participant_workspace"
    names = [path.relative_to(participant).as_posix() for path in participant.rglob("*")]
    joined_content = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in participant.rglob("*") if path.is_file()
    )

    assert not any("ground_truth" in name or "followup_oracle" in name or "private_run" in name for name in names)
    assert "THIS_MUST_NEVER_REACH_THE_PARTICIPANT" not in joined_content
    assert not (participant / "engine" / "examples").exists()
    assert not (participant / "engine" / "reports").exists()
    assert not (participant / "engine" / "tests").exists()
    context = json.loads((participant / "run_context.json").read_text(encoding="utf-8"))
    assert context["ground_truth_available"] is False
    assert context["previous_run_outputs_available"] is False


def test_followup_requires_a_specific_matching_request_and_reveals_only_one_item(tmp_path: Path) -> None:
    case, run = _prepare(tmp_path)
    vague = tmp_path / "vague.json"
    _write_json(vague, {"schema_version": 1, "requests": [
        _request("request_001", concept="equipment schedule", question="Please send more data now")
    ]})
    first = reveal_followups(run, case, vague)
    assert first["results"][0]["matched"] is False

    targeted = tmp_path / "targeted.json"
    _write_json(targeted, {"schema_version": 1, "requests": [
        _request("request_002", concept="equipment schedule", question="Can the site manager provide the equipment schedule for this period?")
    ]})
    second = reveal_followups(run, case, targeted)
    assert second["results"][0]["matched"] is True
    revealed = run / "participant_workspace" / "revealed"
    assert (revealed / "cycle_002" / "item_001" / "payload_001.csv").is_file()
    assert not any(path.name == "payload_002.txt" for path in revealed.rglob("*"))
    assert "private future note" not in "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in revealed.rglob("*") if path.is_file()
    )
    private_request = run / "private_run" / "requests" / "cycle_002.json"
    assert json.loads(private_request.read_text(encoding="utf-8")) == json.loads(
        targeted.read_text(encoding="utf-8")
    )
    assert run_manifest_for(run)["question_cycles"][1]["private_requests_path"] == "requests/cycle_002.json"


def test_unavailable_followup_is_a_normal_oracle_result(tmp_path: Path) -> None:
    case, run = _prepare(tmp_path)
    requests = tmp_path / "requests.json"
    _write_json(requests, {"schema_version": 1, "requests": [
        _request("request_003", concept="meter verification", question="Can the site manager perform a meter verification during the period?")
    ]})
    result = reveal_followups(run, case, requests)
    assert result["results"][0]["availability"] == "unavailable"
    assert result["results"][0]["payload_files"] == []


@pytest.mark.parametrize("decision", ["NORMAL_OPERATION", "INSUFFICIENT_INFORMATION"])
def test_normal_and_insufficient_decisions_finalize_normally(tmp_path: Path, decision: str) -> None:
    _, run = _prepare(tmp_path)
    response_path = run / "participant_workspace" / "output" / "response.json"
    _write_json(response_path, _valid_response("case_900", decision))

    result = finalize_run(run, response_path, repository=REPOSITORY)

    assert result["status"] == "completed_unscored"
    assert result["current_decision"] == decision
    assert result["critical_fail_assessed"] is False
    assert result["duration_seconds"] >= 0
    assert run_manifest_for(run)["duration_seconds"] == result["duration_seconds"]


def test_response_contract_rejects_missing_or_invented_structure() -> None:
    response = _valid_response("case_900", "INSUFFICIENT_INFORMATION")
    del response["validation"]
    with pytest.raises(BenchmarkError, match="validation"):
        validate_response(response)
    response = _valid_response("case_900", "INSUFFICIENT_INFORMATION")
    response["invented_score"] = 99
    with pytest.raises(BenchmarkError, match="inattendu"):
        validate_response(response)


def test_holdout_engine_mutation_invalidates_the_run(tmp_path: Path) -> None:
    _, run = _prepare(tmp_path, stage="HOLDOUT")
    engine_file = run / "participant_workspace" / "engine" / "analyze.py"
    engine_file.chmod(0o600)
    engine_file.write_text(engine_file.read_text(encoding="utf-8") + "\n# forbidden mutation\n", encoding="utf-8")

    with pytest.raises(BenchmarkIntegrityError, match="moteur"):
        verify_run_integrity(run, repository=REPOSITORY)


def test_holdout_refuses_an_untracked_engine_extension(tmp_path: Path) -> None:
    case = _make_case(tmp_path, stage="HOLDOUT")
    repository_copy = tmp_path / "repository_copy"
    subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(REPOSITORY), str(repository_copy)],
        check=True,
    )
    (repository_copy / "energy_mvp" / "holdout_extension.py").write_text(
        "# forbidden untracked engine extension\n", encoding="utf-8"
    )

    with pytest.raises(BenchmarkIntegrityError, match="non suivi"):
        prepare_run(
            case,
            tmp_path / "runs",
            run_id="run_untracked",
            repository=repository_copy,
            system_ref=BASELINE,
            model="test-model-exact",
            reasoning_effort="test-reasoning-exact",
        )


def test_final_response_must_be_inside_output(tmp_path: Path) -> None:
    _, run = _prepare(tmp_path)
    outside = tmp_path / "response.json"
    _write_json(outside, _valid_response("case_900", "NORMAL_OPERATION"))
    with pytest.raises(BenchmarkIntegrityError, match="sort de la racine"):
        finalize_run(run, outside)


def test_multiple_runs_are_independent_and_reproducible(tmp_path: Path) -> None:
    case = _make_case(tmp_path)
    run_a = prepare_run(case, tmp_path / "runs", run_id="run_101", repository=REPOSITORY, system_ref=BASELINE, model="model-x", reasoning_effort="high", run_index=1)
    run_b = prepare_run(case, tmp_path / "runs", run_id="run_102", repository=REPOSITORY, system_ref=BASELINE, model="model-x", reasoning_effort="high", run_index=2)
    manifest_a = run_manifest_for(run_a)
    manifest_b = run_manifest_for(run_b)

    assert run_a != run_b
    assert manifest_a["system_git_commit"] == manifest_b["system_git_commit"]
    assert manifest_a["engine_commitment_sha256"] == manifest_b["engine_commitment_sha256"]
    assert manifest_a["initial_pack_commitment_sha256"] == manifest_b["initial_pack_commitment_sha256"]
    assert manifest_a["previous_run_outputs_copied"] is False
    assert manifest_b["previous_run_outputs_copied"] is False
    assert manifest_a["model"] == "model-x" and manifest_a["reasoning_effort"] == "high"
    assert manifest_a["run_index"] == 1 and manifest_b["run_index"] == 2


def test_tampered_event_log_is_detected(tmp_path: Path) -> None:
    _, run = _prepare(tmp_path)
    log = run / "private_run" / "events.jsonl"
    event = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    event["details"]["model"] = "tampered"
    log.write_text(json.dumps(event) + "\n", encoding="utf-8")
    with pytest.raises(BenchmarkIntegrityError, match="Empreinte"):
        verify_event_log(log)


def test_scorecard_requires_all_nine_weighted_components() -> None:
    maxima = benchmark.SCORE_COMPONENT_MAXIMA
    payload = {
        "schema_version": 1,
        "case_id": "case_900",
        "run_id": "run_900",
        "scorer_id": "scorer_900",
        "blinded_scoring": True,
        "components": {
            name: {"score": maximum, "evidence": "Independent blinded evidence."}
            for name, maximum in maxima.items()
        },
        "total_score": 100,
        "critical_fail": False,
        "critical_fail_reasons": [],
        "response_sha256": "a" * 64,
        "ground_truth_commitment_sha256": "b" * 64,
        "predicted_decision": "NORMAL_OPERATION",
        "reference_decision": "NORMAL_OPERATION",
    }
    validate_scorecard(payload)
    del payload["components"]["safety_continuity"]
    with pytest.raises(BenchmarkError, match="neuf"):
        validate_scorecard(payload)


def test_protected_names_and_symlinks_are_rejected_from_initial_pack(tmp_path: Path) -> None:
    case = _make_case(tmp_path)
    protected = case / "initial_client_pack" / "ground_truth_notes.txt"
    protected.write_text("forbidden", encoding="utf-8")
    manifest = json.loads((case / "case_manifest.json").read_text(encoding="utf-8"))
    manifest["initial_pack_commitment_sha256"] = tree_commitment(case / "initial_client_pack")
    _write_json(case / "case_manifest.json", manifest)
    with pytest.raises(BenchmarkIntegrityError, match="nom protégé"):
        validate_case_directory(case)


def test_reproduction_log_contains_exact_run_inputs(tmp_path: Path) -> None:
    _, run = _prepare(tmp_path)
    reproduction = json.loads((run / "private_run" / "reproduction.json").read_text(encoding="utf-8"))
    manifest = run_manifest_for(run)
    for field in (
        "protocol_version", "baseline_label", "case_id", "case_revision", "stage", "track",
        "model", "reasoning_effort", "system_git_commit", "runner_sha256",
        "initial_pack_commitment_sha256", "oracle_commitment_sha256",
        "ground_truth_commitment_sha256", "engine_commitment_sha256",
    ):
        assert reproduction[field] == manifest[field]
    assert verify_run_integrity(run)["status"] == "valid"
