from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import benchmarking.physical_expertise as benchmark
from benchmarking.physical_expertise import (
    BenchmarkError,
    BenchmarkIntegrityError,
    apply_blind_oracle_review,
    evaluate_oracle_matcher_fixture,
    list_pending_blind_oracle_reviews,
    oracle_match_decision,
    validate_blind_oracle_review,
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
TEST_SYSTEM_REF = "HEAD"


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
        system_ref=TEST_SYSTEM_REF,
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
    assert (participant / "protocol" / "requests.schema.json").is_file()
    assert (participant / "protocol" / "response.schema.json").is_file()
    assert (participant / "protocol" / "requests.template.json").is_file()
    assert (participant / "protocol" / "response.template.json").is_file()
    accessible = set(context["accessible_files"])
    assert "protocol/requests.schema.json" in accessible
    assert "protocol/response.template.json" in accessible


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
            system_ref=TEST_SYSTEM_REF,
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
    run_a = prepare_run(case, tmp_path / "runs", run_id="run_101", repository=REPOSITORY, system_ref=TEST_SYSTEM_REF, model="model-x", reasoning_effort="high", run_index=1)
    run_b = prepare_run(case, tmp_path / "runs", run_id="run_102", repository=REPOSITORY, system_ref=TEST_SYSTEM_REF, model="model-x", reasoning_effort="high", run_index=2)
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


def _borderline_maintenance_request(request_id: str) -> dict:
    return _request(
        request_id,
        concept="maintenance records",
        question="Could you provide maintenance information?",
    )


def test_semantic_matcher_handles_paraphrase_accents_abbreviations_and_order() -> None:
    corpus = json.loads(
        (REPOSITORY / "tests" / "fixtures" / "oracle_matcher_independent_v1.json")
        .read_text(encoding="utf-8")
    )
    result = evaluate_oracle_matcher_fixture(corpus)

    assert result["fixtures"] == 22
    assert result["true_positives"] == 12
    assert result["false_positives"] == 0
    assert result["true_negatives"] == 9
    assert result["false_negatives"] == 1
    assert result["pending_blind_review"] == 2
    assert result["precision"] == 1.0
    assert result["recall"] == pytest.approx(12 / 13, abs=1e-6)


def test_matcher_decision_is_independent_of_private_response_and_payload_fields() -> None:
    request = _request(
        "request_safe_projection",
        concept="shipment timetable",
        question="Could the dispatcher share the timetable for shipments?",
    )
    metadata = {
        "oracle_id": "item_projection",
        "accepted_concepts": ["delivery schedule"],
        "question_terms": ["delivery", "schedule"],
        "minimum_term_matches": 2,
    }
    first = {
        **metadata,
        "response": "SECRET_ANSWER_ONE",
        "availability": "available",
        "payload_files": ["payloads/payload_001.txt"],
        "cost": 1,
        "responder_role": "manager",
    }
    second = {
        **metadata,
        "response": "COMPLETELY_DIFFERENT_SECRET",
        "availability": "unavailable",
        "payload_files": [],
        "cost": 5,
        "responder_role": "different role",
    }

    assert oracle_match_decision(request, [first]) == oracle_match_decision(request, [second])
    rendered = json.dumps(oracle_match_decision(request, [first]))
    assert "SECRET" not in rendered and "payload" not in rendered


def test_vague_or_false_friend_request_does_not_reveal_exact_declared_concept() -> None:
    entry = {
        "oracle_id": "item_guard",
        "accepted_concepts": ["equipment schedule"],
        "question_terms": ["equipment", "schedule"],
        "minimum_term_matches": 2,
    }
    vague = _request(
        "request_guard",
        concept="equipment schedule",
        question="Any details?",
    )
    decision = oracle_match_decision(vague, [entry])
    assert decision["status"] == "NO_MATCH"
    assert decision["selected_oracle_id"] is None


def test_competing_semantic_candidates_require_blind_review() -> None:
    request = _request(
        "request_ambiguous",
        concept="supplier records",
        question="Please provide the supplier records.",
    )
    entries = [
        {
            "oracle_id": identifier,
            "accepted_concepts": ["supplier records"],
            "question_terms": ["supplier", "records"],
            "minimum_term_matches": 2,
        }
        for identifier in ("item_candidate_a", "item_candidate_b")
    ]
    decision = oracle_match_decision(request, entries)
    assert decision["status"] == "PENDING_BLIND_ORACLE_REVIEW"
    assert decision["selected_oracle_id"] is None
    assert len(decision["candidates"]) == 2


def test_blind_review_packet_excludes_answer_and_reveals_only_after_independent_decision(tmp_path: Path) -> None:
    case, run = _prepare(tmp_path)
    requests = tmp_path / "borderline.json"
    _write_json(requests, {
        "schema_version": 1,
        "requests": [_borderline_maintenance_request("request_pending")],
    })
    first = reveal_followups(run, case, requests)
    assert first["results"][0] == {
        "request_id": "request_pending",
        "status": "PENDING_BLIND_ORACLE_REVIEW",
        "matched": False,
        "reason": "independent_review_required",
    }
    assert "item_002" not in json.dumps(first)
    participant = run / "participant_workspace"
    visible = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in participant.rglob("*") if path.is_file()
    )
    assert "private future note" not in visible
    pending = list_pending_blind_oracle_reviews(run)
    packet = pending["pending_reviews"][0]
    serialized_packet = json.dumps(packet)
    assert "private future note" not in serialized_packet
    assert "The maintenance history is attached" not in serialized_packet
    assert "payload_002" not in serialized_packet
    assert packet["candidates"] == [{
        "oracle_id": "item_002",
        "abstract_information_types": ["maintenance history"],
    }]

    decision = {
        "schema_version": 1,
        "review_id": packet["review_id"],
        "reviewer_id": "independent_reviewer_001",
        "reviewer_independent": True,
        "decision": "MATCH",
        "oracle_id": "item_002",
        "justification": "The request explicitly asks for the available maintenance record category.",
    }
    validate_blind_oracle_review(decision)
    participant_decision = participant / "output" / "forbidden_review.json"
    _write_json(participant_decision, decision)
    with pytest.raises(BenchmarkIntegrityError, match="participant"):
        apply_blind_oracle_review(run, case, participant_decision)

    decision_path = tmp_path / "independent_review.json"
    _write_json(decision_path, decision)
    resolved = apply_blind_oracle_review(run, case, decision_path)
    assert resolved["status"] == "MATCHED"
    response = participant / "revealed" / "cycle_001" / "item_002" / "response.json"
    assert response.is_file()
    assert "maintenance history" in response.read_text(encoding="utf-8").lower()
    manifest = run_manifest_for(run)
    assert manifest["pending_blind_oracle_reviews"] == []
    assert manifest["blind_oracle_review_history"][0]["decision"] == "MATCH"
    assert verify_event_log(run / "private_run" / "events.jsonl")["events"] == 3


def test_unresolved_blind_review_blocks_probe_cycle_and_finalization(tmp_path: Path) -> None:
    case, run = _prepare(tmp_path)
    request_path = tmp_path / "pending.json"
    _write_json(request_path, {
        "schema_version": 1,
        "requests": [_borderline_maintenance_request("request_pending_2")],
    })
    reveal_followups(run, case, request_path)
    second = tmp_path / "second.json"
    _write_json(second, {
        "schema_version": 1,
        "requests": [_request(
            "request_probe",
            concept="equipment schedule",
            question="Can the manager provide the equipment schedule?",
        )],
    })
    with pytest.raises(BenchmarkError, match="revue aveugle"):
        reveal_followups(run, case, second)
    response_path = run / "participant_workspace" / "output" / "response.json"
    _write_json(response_path, _valid_response("case_900", "INSUFFICIENT_INFORMATION"))
    with pytest.raises(BenchmarkError, match="revues aveugles"):
        finalize_run(run, response_path, repository=REPOSITORY)


def test_blind_review_private_records_are_integrity_protected(tmp_path: Path) -> None:
    case, run = _prepare(tmp_path)
    request_path = tmp_path / "pending_integrity.json"
    _write_json(request_path, {
        "schema_version": 1,
        "requests": [_borderline_maintenance_request("request_integrity")],
    })
    reveal_followups(run, case, request_path)
    packet = list_pending_blind_oracle_reviews(run)["pending_reviews"][0]
    decision_path = tmp_path / "integrity_review.json"
    _write_json(decision_path, {
        "schema_version": 1,
        "review_id": packet["review_id"],
        "reviewer_id": "independent_reviewer_003",
        "reviewer_independent": True,
        "decision": "NO_MATCH",
        "oracle_id": None,
        "justification": "The request remains too broad for an unambiguous category match.",
    })
    apply_blind_oracle_review(run, case, decision_path)
    manifest = run_manifest_for(run)
    decision_copy = (
        run / "private_run" /
        manifest["blind_oracle_review_history"][0]["decision_path"]
    )
    original = decision_copy.read_text(encoding="utf-8")
    decision_copy.chmod(0o600)
    decision_copy.write_text(original.replace("too broad", "tampered"), encoding="utf-8")

    with pytest.raises(BenchmarkIntegrityError, match="décision aveugle modifiée"):
        verify_run_integrity(run)


def test_pending_blind_review_packet_is_integrity_protected(tmp_path: Path) -> None:
    case, run = _prepare(tmp_path)
    request_path = tmp_path / "pending_packet_integrity.json"
    _write_json(request_path, {
        "schema_version": 1,
        "requests": [_borderline_maintenance_request("request_packet_integrity")],
    })
    reveal_followups(run, case, request_path)
    manifest = run_manifest_for(run)
    packet_path = run / "private_run" / manifest["pending_blind_oracle_reviews"][0]["packet_path"]
    packet_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(BenchmarkIntegrityError, match="Paquet de revue aveugle modifié"):
        verify_run_integrity(run)


def test_blind_review_no_match_reveals_nothing_and_is_reproducible(tmp_path: Path) -> None:
    case, run = _prepare(tmp_path)
    request_path = tmp_path / "pending_no_match.json"
    _write_json(request_path, {
        "schema_version": 1,
        "requests": [_borderline_maintenance_request("request_pending_no_match")],
    })
    reveal_followups(run, case, request_path)
    packet = list_pending_blind_oracle_reviews(run)["pending_reviews"][0]
    invalid = {
        "schema_version": 1,
        "review_id": packet["review_id"],
        "reviewer_id": "independent_reviewer_002",
        "reviewer_independent": True,
        "decision": "MATCH",
        "oracle_id": "item_999",
        "justification": "Invalid candidate used to test the guard.",
    }
    invalid_path = tmp_path / "invalid_review.json"
    _write_json(invalid_path, invalid)
    with pytest.raises(BenchmarkIntegrityError, match="hors candidats"):
        apply_blind_oracle_review(run, case, invalid_path)

    decision = {
        "schema_version": 1,
        "review_id": packet["review_id"],
        "reviewer_id": "independent_reviewer_002",
        "reviewer_independent": True,
        "decision": "NO_MATCH",
        "oracle_id": None,
        "justification": "The abstract category is not sufficiently identified by the request.",
    }
    decision_path = tmp_path / "no_match_review.json"
    _write_json(decision_path, decision)
    result = apply_blind_oracle_review(run, case, decision_path)
    assert result["status"] == "NO_MATCH"
    participant = run / "participant_workspace"
    assert not (participant / "revealed" / "cycle_001" / "item_002").exists()
    public = json.loads(
        (participant / "revealed" / "cycle_001" / "request_results.json")
        .read_text(encoding="utf-8")
    )
    assert public["results"][0]["reason"] == "independent_blind_review_no_match"
    assert "item_002" not in json.dumps(public)
    manifest = run_manifest_for(run)
    history = manifest["blind_oracle_review_history"][0]
    assert history["decision"] == "NO_MATCH"
    assert history["selected_oracle_id"] is None
    assert history["decision_sha256"] == benchmark.sha256_file(decision_path)



def test_candidate_v2_structured_physical_no_lexical_match_requires_blind_review() -> None:
    request = _request(
        "request_direct_physics",
        concept="bearing vibration trend",
        question="Can maintenance measure bearing vibration during loaded and unloaded operation?",
    )
    entries = [{
        "oracle_id": "item_process_observation",
        "accepted_concepts": ["process observation record"],
        "question_terms": ["process", "observation"],
        "minimum_term_matches": 2,
    }]

    decision = oracle_match_decision(request, entries)

    assert decision["status"] == "PENDING_BLIND_ORACLE_REVIEW"
    assert decision["reason"] == "structured_physical_request_needs_blind_review"
    assert decision["selected_oracle_id"] is None
    assert decision["candidates"][0]["oracle_id"] == "item_process_observation"
    assert decision["candidates"][0]["fallback_blind_review"] is True


def test_candidate_v2_structured_but_off_topic_request_is_automatic_no_match() -> None:
    request = _request(
        "request_off_topic",
        concept="cafeteria menu preference",
        question="Can human resources survey cafeteria menu preferences next Tuesday?",
    )
    request["why"] = "This separates vegetarian preference from dessert preference in the survey."
    entries = [{
        "oracle_id": "item_equipment_schedule",
        "accepted_concepts": ["equipment schedule"],
        "question_terms": ["equipment", "schedule"],
        "minimum_term_matches": 2,
    }]

    decision = oracle_match_decision(request, entries)

    assert decision["status"] == "NO_MATCH"
    assert decision["reason"] == "clearly_off_topic_or_non_discriminating"
    assert decision["candidates"] == []


def test_candidate_v2_answered_entry_is_not_revealed_twice() -> None:
    request = _request(
        "request_answered",
        concept="equipment schedule",
        question="Can the site manager provide the equipment schedule?",
    )
    entry = {
        "oracle_id": "item_equipment_schedule",
        "accepted_concepts": ["equipment schedule"],
        "question_terms": ["equipment", "schedule"],
        "minimum_term_matches": 2,
    }

    decision = oracle_match_decision(request, [], answered_entries=[entry])

    assert decision == {
        "matcher_version": benchmark.ORACLE_MATCHER_VERSION,
        "status": "NO_MATCH",
        "reason": "already_answered",
        "selected_oracle_id": None,
        "candidates": [],
    }


def test_candidate_v2_same_cycle_duplicate_question_reveals_once(tmp_path: Path) -> None:
    case, run = _prepare(tmp_path)
    requests = tmp_path / "duplicate_requests.json"
    _write_json(requests, {
        "schema_version": 1,
        "requests": [
            _request(
                "request_schedule_first",
                concept="equipment schedule",
                question="Can the site manager provide the equipment schedule?",
            ),
            _request(
                "request_schedule_repeat",
                concept="equipment schedule",
                question="Can the site manager provide the equipment schedule?",
            ),
        ],
    })

    result = reveal_followups(run, case, requests)

    assert [item["status"] for item in result["results"]] == ["MATCHED", "NO_MATCH"]
    assert result["cycle_oracle_cost"] == 1
    manifest = run_manifest_for(run)
    assert manifest["revealed_oracle_ids"] == ["item_001"]
    assert manifest["question_cycles"][0]["requests"][1]["matcher_reason"] == "already_answered"
    assert result["results"][1]["reason"] == "no_sufficient_match"


def test_candidate_v2_fallback_packet_is_minimal_and_does_not_auto_reveal(tmp_path: Path) -> None:
    case, run = _prepare(tmp_path)
    request_path = tmp_path / "physical_fallback.json"
    _write_json(request_path, {
        "schema_version": 1,
        "requests": [_request(
            "request_bearing_measurement",
            concept="bearing vibration trend",
            question="Can maintenance measure bearing vibration during loaded and unloaded operation?",
        )],
    })

    public = reveal_followups(run, case, request_path)

    assert public["results"][0]["status"] == "PENDING_BLIND_ORACLE_REVIEW"
    assert public["cycle_oracle_cost"] == 0
    assert "item_" not in json.dumps(public)
    packet = list_pending_blind_oracle_reviews(run)["pending_reviews"][0]
    serialized = json.dumps(packet)
    assert "intention principale matériellement discriminante" in packet["review_question"]
    assert len(packet["candidates"]) == 3
    assert set(packet["candidates"][0]) == {"oracle_id", "abstract_information_types"}
    assert "The equipment schedule is attached" not in serialized
    assert "The maintenance history is attached" not in serialized
    assert "private future note" not in serialized
    assert "payload_" not in serialized
    assert not any(
        path.is_file()
        for path in (run / "participant_workspace" / "revealed" / "cycle_001").glob("item_*")
    )


def test_primary_discriminating_intent_with_related_detail_reaches_blind_review() -> None:
    request = _request(
        "request_primary_intent",
        concept="equipment schedule",
        question="Provide the equipment schedule and related operator notes for the same period.",
    )
    entry = {
        "oracle_id": "item_schedule",
        "accepted_concepts": ["equipment schedule"],
        "question_terms": ["timetable", "operator roster", "maintenance ticket"],
        "minimum_term_matches": 3,
    }
    decision = oracle_match_decision(request, [entry])
    assert decision["status"] == "PENDING_BLIND_ORACLE_REVIEW"
    assert decision["candidates"][0]["oracle_id"] == "item_schedule"
    assert decision["selected_oracle_id"] is None


def test_intent_review_does_not_auto_reveal_genuinely_ambiguous_payloads() -> None:
    request = _request(
        "request_multi_intent",
        concept="equipment schedule",
        question="Provide the equipment schedule and related operator notes for the same period.",
    )
    entries = [
        {
            "oracle_id": identifier,
            "accepted_concepts": ["equipment schedule"],
            "question_terms": ["equipment", "schedule", "timetable"],
            "minimum_term_matches": 3,
        }
        for identifier in ("item_schedule_a", "item_schedule_b")
    ]
    decision = oracle_match_decision(request, entries)
    assert decision["status"] == "PENDING_BLIND_ORACLE_REVIEW"
    assert decision["selected_oracle_id"] is None
    assert len(decision["candidates"]) == 2
