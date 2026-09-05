from __future__ import annotations

import json
import csv
import math
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytest

import benchmarking.physical_expertise as physical
import benchmarking.signal_intelligence_cli as signal_cli
from benchmarking.signal_deterministic_baseline import (
    METHOD_TAGS,
    deterministic_baseline_response,
    run_deterministic_baseline_suite,
)
from benchmarking.signal_intelligence import (
    ACTION_CODES,
    SignalBenchmarkError,
    aggregate_scorecards,
    finalize_signal_run,
    null_baseline_response,
    prepare_signal_run,
    reveal_signal_followups,
    run_null_baseline_suite,
    score_signal_run,
    validate_signal_case,
    validate_signal_response,
    verify_signal_run,
)
from benchmarking.signal_intelligence_generator import (
    SCENARIOS,
    TIERS,
    _simulate,
    generate_case,
    generate_suite,
)


REPOSITORY = Path(__file__).resolve().parents[1]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def paired_cases(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("signal_v2_cases")
    scenario = SCENARIOS[0]
    simulation = _simulate(scenario, 9026)
    result = {}
    for tier in TIERS:
        record = generate_case(root, scenario, tier, seed=9026, simulation=simulation)
        result[tier] = Path(record["case_path"])
    return result


@pytest.fixture(scope="module")
def normal_case(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("signal_v2_normal_case")
    scenario = SCENARIOS[3]
    simulation = _simulate(scenario, 19026)
    record = generate_case(root, scenario, "L0_E15", seed=19026, simulation=simulation)
    return Path(record["case_path"])


def _reference_response(case: Path) -> dict:
    manifest = json.loads((case / "case_manifest.json").read_text(encoding="utf-8"))
    truth = json.loads((case / "ground_truth" / "truth.json").read_text(encoding="utf-8"))
    event = truth["primary_event"]
    abnormal = event["event_class"] != "NO_ABNORMALITY"
    target_assets = []
    if event["target_asset_id"]:
        target_assets = [{
            "asset_id": event["target_asset_id"],
            "probability": 0.95,
            "rationale": "Correspondance de signature testée.",
            "falsification_test": "Comparer aux états réels synchronisés.",
        }]
    mechanisms = [{
        "mechanism_code": event["mechanism"],
        "probability": 0.95,
        "rationale": "Mécanisme de référence de la fixture de scoring.",
        "falsification_test": "Contrôle physique indépendant.",
    }]
    signature_candidate_assets = target_assets
    signature_event_refs = ["event:EV-000001"]
    if manifest["measurement_tier"] == "L2_EDGE":
        with (case / "ground_truth" / "event_sources.csv").open("r", encoding="utf-8", newline="") as stream:
            source_rows = list(csv.DictReader(stream))
        groups: dict[str, list[str]] = {}
        for row in source_rows:
            groups.setdefault(row["dominant_asset_id"], []).append(row["event_id"])
        signature_asset, signature_events = next(
            (asset_id, events) for asset_id, events in groups.items() if len(events) >= 3
        )
        signature_candidate_assets = [{
            "asset_id": signature_asset,
            "probability": 0.95,
            "rationale": "Morphologie répétée de la fixture de scoring.",
            "falsification_test": "Comparer aux sources d'événements cachées.",
        }]
        signature_event_refs = [f"event:{event_id}" for event_id in signature_events[:3]]
    finding = {
        "finding_id": "F-001",
        "event_class": event["event_class"],
        "start": event["onset"],
        "end": None,
        "abnormal_probability": 1.0 if abnormal else 0.0,
        "target_assets": target_assets,
        "mechanisms": mechanisms,
        "evidence_refs": [
            "initial_client_pack/05_aggregate_energy_15min.csv",
            "initial_client_pack/04_daily_operations.csv",
        ],
        "observed_excess_energy_kwh": event["expected_excess_energy_kwh"],
        "recoverable_energy_kwh": None,
        "interpretation": "Fixture exacte destinée à vérifier le scorer.",
        "alternative_explanations": ["Fonctionnement normal", "Artefact de mesure"],
    }
    outcome = bool(event["outcome_within_horizon"])
    return {
        "schema_version": 2,
        "case_id": manifest["case_id"],
        "analysis_cutoff": manifest["analysis_cutoff"],
        "data_assessment": {
            "usable": True,
            "measurement_tier": manifest["measurement_tier"],
            "quality_issues": [],
            "limitations": ["Fixture de validation."],
            "coverage_summary": "Couverture contrôlée par le générateur.",
        },
        "signatures": [{
            "signature_id": "S-001",
            "description": "Signature de la cible de référence.",
            "event_refs": signature_event_refs,
            "candidate_assets": signature_candidate_assets,
            "confidence": 0.95,
        }],
        "findings": [finding],
        "primary_assessment": {
            "finding_id": "F-001",
            "event_class": event["event_class"],
            "abnormal_probability": 1.0 if abnormal else 0.0,
            "onset": event["onset"],
            "target_assets": target_assets,
            "mechanisms": mechanisms,
            "observed_excess_energy_kwh": event["expected_excess_energy_kwh"],
            "evidence_refs": [
                "initial_client_pack/05_aggregate_energy_15min.csv",
                "initial_client_pack/04_daily_operations.csv",
            ],
        },
        "prognosis": {
            "issued": outcome,
            "target_asset_id": event["target_asset_id"] if outcome else None,
            "outcome_code": event["outcome_code"],
            "horizon_days": 14,
            "outcome_within_horizon_probability": 1.0 if outcome else 0.0,
            "evidence_refs": ["finding:F-001", "signature:S-001"],
            "abstention_reason": "" if outcome else "Aucun précurseur d'événement futur.",
        },
        "next_action": {
            "action_code": event["acceptable_actions"][0],
            "target_asset_id": event["target_asset_id"],
            "priority": "HIGH" if outcome else "LOW",
            "action": "Effectuer la vérification de référence.",
            "competent_person": "Technicien compétent.",
            "preconditions": ["Production informée."],
            "risks": ["Interruption du procédé."],
            "stop_conditions": ["Alarme ou risque sécurité."],
            "validation": "Comparer avant et après à service équivalent.",
        },
        "overall_decision": "MAINTENANCE_CHECK" if outcome else "NO_ACTION",
        "adversarial_review": {
            "best_reason_wrong": "Une variation de contexte pourrait expliquer le signal.",
            "test_performed": "Comparaison conditionnelle avec les opérations.",
            "result": "Le signal résiste au contrôle dans la fixture.",
            "decision_after_review": "Conclusion conservée.",
        },
    }


def test_scenario_catalog_covers_sectors_outcomes_and_holdout() -> None:
    assert {scenario.sector for scenario in SCENARIOS} == {
        "plasturgie", "froid_industriel", "blanchisserie"
    }
    classes = {scenario.event_class for scenario in SCENARIOS}
    assert {"NO_ABNORMALITY", "ENERGY_WASTE", "PROGRESSIVE_DEGRADATION", "METER_ARTIFACT"} <= classes
    assert {scenario.stage for scenario in SCENARIOS} == {"DEV", "HOLDOUT"}
    assert sum(scenario.outcome_day is not None for scenario in SCENARIOS) >= 3
    assert {
        scenario.stage for scenario in SCENARIOS if scenario.outcome_day is not None
    } == {"DEV", "HOLDOUT"}
    assert len({
        scenario.outcome_code for scenario in SCENARIOS if scenario.outcome_day is not None
    }) >= 2
    assert {
        code
        for scenario in SCENARIOS
        for code in (*scenario.acceptable_actions, *scenario.dangerous_actions)
    } <= ACTION_CODES


def test_measurement_tiers_are_true_ablations_of_same_signal(paired_cases: dict[str, Path]) -> None:
    l0 = paired_cases["L0_E15"] / "initial_client_pack"
    l1 = paired_cases["L1_PQ1"] / "initial_client_pack"
    l2 = paired_cases["L2_EDGE"] / "initial_client_pack"
    assert physical.sha256_file(l0 / "05_aggregate_energy_15min.csv") == physical.sha256_file(
        l1 / "05_aggregate_energy_15min.csv"
    )
    assert physical.sha256_file(l1 / "06_aggregate_power_1min.csv") == physical.sha256_file(
        l2 / "06_aggregate_power_1min.csv"
    )
    assert not (l0 / "06_aggregate_power_1min.csv").exists()
    assert not (l1 / "07_central_electrical_events.csv").exists()
    assert (l2 / "07_central_electrical_events.csv").is_file()


def test_exports_include_realistic_quality_defects_and_dst(paired_cases: dict[str, Path]) -> None:
    pack = paired_cases["L2_EDGE"] / "initial_client_pack"
    with (pack / "06_aggregate_power_1min.csv").open("r", encoding="utf-8", newline="") as stream:
        timestamps = [row["timestamp"] for row in csv.DictReader(stream)]
    counts = Counter(timestamps)
    assert sum(value - 1 for value in counts.values() if value > 1) == 1
    # Forty-two local calendar days cross the spring DST transition (one hour absent).
    # Three logger omissions and one duplicate are then injected deliberately.
    assert len(timestamps) == 60418
    local_day_counts = Counter(datetime.fromisoformat(value).date().isoformat() for value in timestamps)
    assert local_day_counts["2026-03-29"] == 1380
    with (pack / "05_aggregate_energy_15min.csv").open("r", encoding="utf-8", newline="") as stream:
        energy_timestamps = [row["timestamp"] for row in csv.DictReader(stream)]
    assert len(energy_timestamps) == 4028
    assert len(set(energy_timestamps)) == 4027


def test_simulation_period_matches_complete_local_operating_calendar() -> None:
    simulation = _simulate(SCENARIOS[0], 260902)
    energy_dates = {
        datetime.fromisoformat(row["timestamp"]).date().isoformat()
        for row in simulation["public_energy_rows"]
    }
    context_dates = {simulation["context"][day]["date"] for day in range(42)}
    assert simulation["analysis_cutoff"] == "2026-04-13T00:00:00+02:00"
    assert energy_dates == context_dates
    assert simulation["public_energy_rows"][-1]["timestamp"] == "2026-04-12T23:45:00+02:00"


def test_case_validation_never_reads_ground_truth(
    paired_cases: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    original = physical.file_manifest

    def guarded(path: str | Path):
        if Path(path).name == "ground_truth":
            raise AssertionError("ground truth read during public validation")
        return original(path)

    monkeypatch.setattr(physical, "file_manifest", guarded)
    validated = validate_signal_case(paired_cases["L1_PQ1"])
    assert validated["manifest"]["measurement_tier"] == "L1_PQ1"


def test_case_validation_rejects_public_numeric_corruption_with_valid_commitment(
    paired_cases: dict[str, Path], tmp_path: Path
) -> None:
    source_case = paired_cases["L0_E15"]
    case = tmp_path / "corrupt_case" / source_case.name
    shutil.copytree(source_case, case)
    energy_path = case / "initial_client_pack" / "05_aggregate_energy_15min.csv"
    rows = energy_path.read_text(encoding="utf-8").splitlines()
    rows[1] = rows[1].split(",", 1)[0] + ",NaN"
    energy_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    manifest_path = case / "case_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["initial_pack_commitment_sha256"] = physical.tree_commitment(
        case / "initial_client_pack"
    )
    _write_json(manifest_path, manifest)
    with pytest.raises(SignalBenchmarkError, match="nombre fini"):
        validate_signal_case(case)


def test_response_contract_is_strict_and_probability_ordered(paired_cases: dict[str, Path]) -> None:
    response = _reference_response(paired_cases["L2_EDGE"])
    validate_signal_response(response, expected_case_id=response["case_id"])
    response["invented_field"] = 42
    with pytest.raises(SignalBenchmarkError, match="inattendu"):
        validate_signal_response(response)
    response = _reference_response(paired_cases["L2_EDGE"])
    response["primary_assessment"]["target_assets"].append({
        "asset_id": "OTHER",
        "probability": 0.2,
        "rationale": "Second.",
        "falsification_test": "Test.",
    })
    response["primary_assessment"]["target_assets"][0]["probability"] = 0.1
    with pytest.raises(SignalBenchmarkError, match="trié"):
        validate_signal_response(response)


def test_response_rejects_duplicate_signature_events_and_incoherent_claims(
    paired_cases: dict[str, Path],
) -> None:
    response = _reference_response(paired_cases["L2_EDGE"])
    response["signatures"][0]["event_refs"] *= 2
    with pytest.raises(SignalBenchmarkError, match="dupliquée"):
        validate_signal_response(response)

    response = _reference_response(paired_cases["L2_EDGE"])
    response["findings"][0]["start"] = "2026-03-20T00:00:00+01:00"
    response["findings"][0]["end"] = "2026-03-19T00:00:00+01:00"
    with pytest.raises(SignalBenchmarkError, match="antérieure"):
        validate_signal_response(response)

    response = _reference_response(paired_cases["L2_EDGE"])
    response["findings"][0]["observed_excess_energy_kwh"] = None
    response["findings"][0]["recoverable_energy_kwh"] = 1.0
    with pytest.raises(SignalBenchmarkError, match="sans excès observé"):
        validate_signal_response(response)

    response = _reference_response(paired_cases["L2_EDGE"])
    response["findings"][0]["observed_excess_energy_kwh"] = math.nan
    with pytest.raises(SignalBenchmarkError, match="fini"):
        validate_signal_response(response)

    response = _reference_response(paired_cases["L2_EDGE"])
    response["primary_assessment"]["event_class"] = "NO_ABNORMALITY"
    with pytest.raises(SignalBenchmarkError, match="incohérent"):
        validate_signal_response(response)

    response = _reference_response(paired_cases["L2_EDGE"])
    response["prognosis"]["outcome_code"] = "NONE"
    with pytest.raises(SignalBenchmarkError, match="pronostic émis"):
        validate_signal_response(response)

    response = _reference_response(paired_cases["L2_EDGE"])
    response["next_action"]["action_code"] = "FREE_TEXT_ESCAPE"
    with pytest.raises(SignalBenchmarkError, match="action_code inconnu"):
        validate_signal_response(response)


def test_generate_suite_rejects_unknown_profile(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="profile"):
        generate_suite(tmp_path / "invalid", seed=1, profile="typo")


def test_cli_routes_deterministic_ablation_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_runner(*args, **kwargs):
        captured.update(kwargs)
        return {
            "baseline": "fixture",
            "case_count": 0,
            "aggregate": {"overall": {"mean_score": 0.0}},
        }

    monkeypatch.setattr(signal_cli, "run_deterministic_baseline_suite", fake_runner)
    assert signal_cli.main([
        "run-deterministic-suite",
        "suite",
        "runs",
        "--tier", "L0_E15",
        "--detection-method", "production",
        "--energy-method", "unconditional",
        "--signature-method", "pq",
    ]) == 0
    assert captured["measurement_tiers"] == ("L0_E15",)
    assert captured["detection_method"] == "production"
    assert captured["energy_method"] == "unconditional"
    assert captured["signature_method"] == "pq"


def test_null_baseline_is_valid_and_pre_registered(paired_cases: dict[str, Path]) -> None:
    response = null_baseline_response(paired_cases["L0_E15"])
    validate_signal_response(response, expected_case_id=response["case_id"])
    assert response["primary_assessment"]["abnormal_probability"] == 0.1
    assert response["prognosis"]["issued"] is False


def test_null_baseline_suite_uses_finalize_before_truth_scoring(
    paired_cases: dict[str, Path], tmp_path: Path
) -> None:
    source = paired_cases["L0_E15"]
    suite = tmp_path / "private_suite"
    case = suite / "cases" / "DEV" / source.name
    shutil.copytree(source, case)
    _write_json(suite / "suite_manifest.json", {
        "schema_version": 2,
        "benchmark_version": "2.0",
        "seed": 9026,
        "case_count": 1,
        "cases": [{
            "case_id": source.name,
            "stage": "DEV",
            "measurement_tier": "L0_E15",
            "case_path": f"cases/DEV/{source.name}",
        }],
    })
    result = run_null_baseline_suite(
        suite,
        tmp_path / "null_runs",
        repository=REPOSITORY,
        stages=("DEV",),
    )
    assert result["case_count"] == 1
    assert result["pre_truth_lock_enforced"] is True
    assert result["aggregate"]["by_system_variant"]["NULL_BASELINE"]["count"] == 1


def test_deterministic_control_separates_detection_signature_and_attribution(
    paired_cases: dict[str, Path],
) -> None:
    responses = {
        tier: deterministic_baseline_response(case)
        for tier, case in paired_cases.items()
    }
    for tier, response in responses.items():
        validate_signal_response(response, expected_case_id=response["case_id"])
        assert response["data_assessment"]["measurement_tier"] == tier
        assert response["primary_assessment"]["target_assets"] == []
        assert response["prognosis"]["issued"] is False
    assert responses["L0_E15"]["signatures"] == []
    assert responses["L1_PQ1"]["signatures"] == []
    assert responses["L2_EDGE"]["signatures"]
    assert len({
        response["primary_assessment"]["abnormal_probability"]
        for response in responses.values()
    }) == 1
    assert len(
        f"det-{METHOD_TAGS['production_temperature']}-"
        f"{METHOD_TAGS['production_temperature']}-{METHOD_TAGS['morphology']}-"
        f"{responses['L2_EDGE']['case_id'].lower()}"
    ) < 64


def test_detection_is_distinct_from_event_classification(
    paired_cases: dict[str, Path], tmp_path: Path
) -> None:
    case = paired_cases["L0_E15"]
    response = _reference_response(case)
    response["findings"][0]["event_class"] = "UNRESOLVED"
    response["primary_assessment"]["event_class"] = "UNRESOLVED"
    response["findings"][0]["abnormal_probability"] = 0.9
    response["primary_assessment"]["abnormal_probability"] = 0.9
    response["signatures"] = []
    response["prognosis"]["evidence_refs"] = ["finding:F-001"]
    assert response["primary_assessment"]["event_class"] == "UNRESOLVED"
    assert response["primary_assessment"]["abnormal_probability"] >= 0.5
    run = prepare_signal_run(
        case,
        tmp_path / "runs_unresolved_detection",
        repository=REPOSITORY,
        system_ref="HEAD",
        model="detection-and-motif-v1",
        reasoning_effort="none",
        variant="DETERMINISTIC",
        run_id="signal-v2-unresolved-detection-001",
    )
    response_path = run / "participant_workspace" / "output" / "response.json"
    _write_json(response_path, response)
    finalize_signal_run(run, response_path, repository=REPOSITORY)
    metrics = score_signal_run(run, case)["metrics"]
    assert metrics["layer_passes"]["detection"] is True
    assert metrics["layer_passes"]["event_classification"] is False
    assert metrics["capability_pass"] is False


def test_deterministic_suite_locks_response_before_truth(
    paired_cases: dict[str, Path], tmp_path: Path
) -> None:
    source = paired_cases["L2_EDGE"]
    suite = tmp_path / "private_deterministic_suite"
    case = suite / "cases" / "DEV" / source.name
    shutil.copytree(source, case)
    _write_json(suite / "suite_manifest.json", {
        "schema_version": 2,
        "benchmark_version": "2.0",
        "seed": 9026,
        "case_count": 1,
        "cases": [{
            "case_id": source.name,
            "stage": "DEV",
            "measurement_tier": "L2_EDGE",
            "case_path": f"cases/DEV/{source.name}",
        }],
    })
    result = run_deterministic_baseline_suite(
        suite,
        tmp_path / "deterministic_runs",
        repository=REPOSITORY,
        stages=("DEV",),
    )
    assert result["case_count"] == 1
    assert result["pre_truth_lock_enforced"] is True
    assert result["aggregate"]["by_system_variant"]["DETERMINISTIC"]["count"] == 1
    assert result["excluded_claims"] == [
        "asset_attribution", "physical_mechanism", "prognosis"
    ]


def test_prepare_isolated_workspace_contains_v2_contract_without_truth(
    paired_cases: dict[str, Path], tmp_path: Path
) -> None:
    run = prepare_signal_run(
        paired_cases["L0_E15"],
        tmp_path / "runs",
        repository=REPOSITORY,
        system_ref="HEAD",
        model="fixture-model",
        reasoning_effort="fixture-high",
        variant="AGENTIC",
        run_id="signal-v2-isolation-001",
    )
    participant = run / "participant_workspace"
    assert (participant / "SIGNAL_INTELLIGENCE_INSTRUCTIONS.md").is_file()
    assert (participant / "protocol" / "signal_response.schema.json").is_file()
    names = [path.name.casefold() for path in participant.rglob("*")]
    assert "ground_truth" not in names
    content = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in participant.rglob("*") if path.is_file()
    )
    assert "Encrassement progressif du groupe froid" not in content
    verified = verify_signal_run(run, repository=REPOSITORY)
    assert verified["signal_finalized"] is False


def test_oracle_cycle_reveals_only_requested_payload(
    paired_cases: dict[str, Path], tmp_path: Path
) -> None:
    case = paired_cases["L1_PQ1"]
    run = prepare_signal_run(
        case,
        tmp_path / "runs_oracle",
        repository=REPOSITORY,
        system_ref="HEAD",
        model="fixture-model",
        reasoning_effort="fixture-high",
        variant="AGENTIC",
        run_id="signal-v2-cycle-001",
    )
    request_path = tmp_path / "requests.json"
    _write_json(request_path, {
        "schema_version": 1,
        "requests": [{
            "request_id": "runtime-request-001",
            "question": "Le responsable maintenance peut-il fournir les états et durées de marche des équipements ?",
            "requested_concepts": ["equipment runtime status logs"],
            "best_responder": "Responsable maintenance",
            "why": "Distinguer une durée accrue d'une hausse de puissance à durée égale.",
            "hypotheses_distinguished": ["durée de marche accrue", "rendement dégradé"],
            "expected_effort": "Export des journaux existants.",
        }],
    })
    result = reveal_signal_followups(run, case, request_path)
    assert result["results"][0]["matched"] is True
    revealed = run / "participant_workspace" / "revealed"
    assert any(path.name == "payload_001.csv" for path in revealed.rglob("*"))
    assert not any(path.name == "payload_002.md" for path in revealed.rglob("*"))


def test_finalize_then_score_exact_reference_and_detect_tampering(
    paired_cases: dict[str, Path], tmp_path: Path
) -> None:
    case = paired_cases["L2_EDGE"]
    run = prepare_signal_run(
        case,
        tmp_path / "runs_score",
        repository=REPOSITORY,
        system_ref="HEAD",
        model="fixture-model",
        reasoning_effort="fixture-high",
        variant="AGENTIC",
        run_id="signal-v2-score-001",
    )
    with pytest.raises(SignalBenchmarkError, match="finalisé"):
        score_signal_run(run, case)
    response_path = run / "participant_workspace" / "output" / "response.json"
    invalid = _reference_response(case)
    invalid["prognosis"]["horizon_days"] = 30
    _write_json(response_path, invalid)
    with pytest.raises(SignalBenchmarkError, match="horizon pré-enregistré"):
        finalize_signal_run(run, response_path, repository=REPOSITORY)
    valid = _reference_response(case)
    valid["primary_assessment"]["evidence_refs"].append("scratch/invented.json")
    valid["findings"][0]["evidence_refs"].append("scratch/invented.json")
    _write_json(response_path, valid)
    with pytest.raises(SignalBenchmarkError, match="absent"):
        finalize_signal_run(run, response_path, repository=REPOSITORY)
    _write_json(response_path, _reference_response(case))
    final = finalize_signal_run(run, response_path, repository=REPOSITORY)
    assert final["ground_truth_read"] is False
    assert verify_signal_run(run, repository=REPOSITORY)["signal_finalized"] is True
    score = score_signal_run(run, case)
    assert score["total_score"] == 100.0
    assert score["metrics"]["asset_top1"] is True
    assert score["metrics"]["capability_pass"] is True
    assert score["metrics"]["signature_discovery"]["event_asset_top1_accuracy"] == 1.0
    assert score["metrics"]["signature_discovery"]["weighted_cluster_purity"] == 1.0
    response_path.chmod(0o644)
    response_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(SignalBenchmarkError, match="modifiée"):
        verify_signal_run(run, repository=REPOSITORY)


def test_wrong_prognosis_outcome_code_cannot_receive_full_capability_credit(
    paired_cases: dict[str, Path], tmp_path: Path
) -> None:
    case = paired_cases["L2_EDGE"]
    run = prepare_signal_run(
        case,
        tmp_path / "runs_wrong_outcome",
        repository=REPOSITORY,
        system_ref="HEAD",
        model="fixture-model",
        reasoning_effort="fixture-high",
        variant="AGENTIC",
        run_id="signal-v2-wrong-outcome-001",
    )
    response = _reference_response(case)
    response["prognosis"]["outcome_code"] = "FAILURE"
    response_path = run / "participant_workspace" / "output" / "response.json"
    _write_json(response_path, response)
    finalize_signal_run(run, response_path, repository=REPOSITORY)
    score = score_signal_run(run, case)
    assert score["total_score"] < 100.0
    assert score["metrics"]["outcome_code_correct"] is False
    assert score["metrics"]["capability_pass"] is False


def test_reproducible_signature_does_not_require_asset_attribution(
    paired_cases: dict[str, Path], tmp_path: Path
) -> None:
    case = paired_cases["L2_EDGE"]
    run = prepare_signal_run(
        case,
        tmp_path / "runs_signature_without_identity",
        repository=REPOSITORY,
        system_ref="HEAD",
        model="fixture-model",
        reasoning_effort="fixture-high",
        variant="AGENTIC",
        run_id="signal-v2-signature-without-identity-001",
    )
    response = _reference_response(case)
    response["signatures"][0]["candidate_assets"] = []
    response_path = run / "participant_workspace" / "output" / "response.json"
    _write_json(response_path, response)
    finalize_signal_run(run, response_path, repository=REPOSITORY)
    metrics = score_signal_run(run, case)["metrics"]
    assert metrics["layer_passes"]["reproducible_signature"] is True
    assert metrics["signature_discovery"]["event_asset_top3_accuracy"] == 0.0


def test_correct_negative_abstention_is_not_counted_as_attribution_or_quantification(
    normal_case: Path, tmp_path: Path
) -> None:
    run = prepare_signal_run(
        normal_case,
        tmp_path / "runs_normal",
        repository=REPOSITORY,
        system_ref="HEAD",
        model="pre_registered_null_v2",
        reasoning_effort="none",
        variant="NULL_BASELINE",
        run_id="signal-v2-normal-abstention-001",
    )
    response_path = run / "participant_workspace" / "output" / "response.json"
    _write_json(response_path, null_baseline_response(normal_case))
    finalize_signal_run(run, response_path, repository=REPOSITORY)
    metrics = score_signal_run(run, normal_case)["metrics"]
    assert metrics["layer_passes"]["detection"] is True
    assert metrics["asset_top1"] is None
    assert metrics["mechanism_top1"] is None
    assert metrics["layer_passes"]["asset_attribution"] is None
    assert metrics["layer_passes"]["physical_mechanism"] is None
    assert metrics["layer_passes"]["energy_quantification"] is None
    assert metrics["layer_passes"]["prognosis"] is None
    assert metrics["capability_pass"] is False


def test_aggregate_exposes_calibration_coverage_and_data_frontier(tmp_path: Path) -> None:
    cards = []
    for index, (tier, probability, truth, passed) in enumerate((
        ("L0_E15", 0.95, True, False),
        ("L1_PQ1", 0.92, True, True),
        ("L2_EDGE", 0.96, False, True),
    )):
        card = {
            "schema_version": 2,
            "benchmark_profile": "SIGNAL_INTELLIGENCE_V2",
            "case_id": f"case-{index}",
            "run_id": f"run-{index}",
            "system_variant": "AGENTIC",
            "model": "fixture",
            "reasoning_effort": "high",
            "stage": "HOLDOUT",
            "sector": "plasturgie",
            "measurement_tier": tier,
            "scenario_family_id": "FAMILY-1",
            "response_sha256": "0" * 64,
            "ground_truth_commitment_sha256": "1" * 64,
            "components": {},
            "total_score": 70 + index,
            "critical_fail": False,
            "critical_fail_reasons": [],
            "metrics": {
                "truth_event_class": "ENERGY_WASTE" if truth else "NO_ABNORMALITY",
                "predicted_event_class": "ENERGY_WASTE" if truth else "NO_ABNORMALITY",
                "abnormal_truth": truth,
                "abnormal_probability": probability,
                "alert_at_90": True,
                "asset_rank": 1,
                "asset_top1": True,
                "asset_top3": True,
                "mechanism_rank": 1,
                "mechanism_top1": True,
                "mechanism_top3": True,
                "onset_error_days": 0,
                "energy_relative_error": 0.1,
                "outcome_truth": truth,
                "prognosis_probability": probability,
                "prognosis_issued": truth,
                "prognosis_issued_correct": True,
                "truth_outcome_code": "MAINTENANCE_INTERVENTION" if truth else "NONE",
                "predicted_outcome_code": "MAINTENANCE_INTERVENTION" if truth else "NONE",
                "outcome_code_correct": True,
                "prognosis_target_correct": True,
                "truth_mechanism": "FIXTURE_MECHANISM",
                "lead_time_days": 7 if truth else None,
                "capability_pass": passed,
            },
            "scored_at_utc": "2026-01-01T00:00:00+00:00",
        }
        path = tmp_path / f"card_{index}" / "signal_scorecard.json"
        _write_json(path, card)
        cards.append(card)
    report = aggregate_scorecards(tmp_path)
    assert report["scorecard_count"] == 3
    assert report["threshold_0_90"]["alerts"] == 3
    assert report["threshold_0_90"]["true_alerts"] == 2
    assert report["threshold_0_90"]["coverage"] == 1.0
    assert report["threshold_0_90"]["precision_wilson_lower_95"] is None
    assert report["threshold_0_90"]["independence_status"] == "CLUSTERED_REPEATS_PRESENT"
    assert report["overall"]["alert_detection"]["precision_wilson_lower_95"] is None
    assert "mechanism:FIXTURE_MECHANISM" in report["by_mechanism"]
    assert len(report["minimum_data_frontier"]) == 1
    assert report["minimum_data_frontier"][0]["minimum_passing_tier"] == "L1_PQ1"


def test_aggregate_compares_non_agentic_variants_without_overwriting_repeats(
    tmp_path: Path,
) -> None:
    template = {
        "schema_version": 2,
        "benchmark_profile": "SIGNAL_INTELLIGENCE_V2",
        "case_id": "case",
        "run_id": "run",
        "model": "fixture",
        "reasoning_effort": "none",
        "stage": "DEV",
        "sector": "plasturgie",
        "site_kind": "fixture",
        "measurement_tier": "L0_E15",
        "scenario_family_id": "FAMILY-PAIR",
        "response_sha256": "0" * 64,
        "ground_truth_commitment_sha256": "1" * 64,
        "components": {},
        "critical_fail": False,
        "critical_fail_reasons": [],
        "metrics": {
            "truth_event_class": "NO_ABNORMALITY",
            "predicted_event_class": "NO_ABNORMALITY",
            "abnormal_truth": False,
            "abnormal_probability": 0.1,
            "alert_at_90": False,
            "asset_top1": None,
            "asset_top3": None,
            "mechanism_top1": None,
            "mechanism_top3": None,
            "onset_error_days": None,
            "energy_relative_error": None,
            "outcome_truth": False,
            "prognosis_probability": 0.1,
            "prognosis_issued_correct": True,
            "outcome_code_correct": True,
            "prognosis_target_correct": True,
            "truth_mechanism": "NORMAL_OPERATION",
            "capability_pass": False,
            "layer_passes": {"detection": True},
            "signature_discovery": {"applicable": False},
        },
        "scored_at_utc": "2026-01-01T00:00:00+00:00",
    }
    for index, (variant, score) in enumerate((
        ("NULL_BASELINE", 30.0),
        ("DETERMINISTIC", 40.0),
        ("DETERMINISTIC", 50.0),
    )):
        card = {**template, "run_id": f"run-{index}", "system_variant": variant, "total_score": score}
        _write_json(tmp_path / f"card-{index}" / "signal_scorecard.json", card)
    comparison = aggregate_scorecards(tmp_path)["paired_variant_comparisons"][0]
    assert comparison["system_mean_scores"] == {
        "NULL_BASELINE|fixture|none": 30.0,
        "DETERMINISTIC|fixture|none": 45.0,
    }
    assert comparison["system_run_counts"]["DETERMINISTIC|fixture|none"] == 2
    assert comparison["pairwise_score_deltas"] == [{
        "comparison": "DETERMINISTIC|fixture|none_minus_NULL_BASELINE|fixture|none",
        "delta": 15.0,
    }]
