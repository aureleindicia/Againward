from __future__ import annotations

import json

from benchmarking.minimal_attribution_benchmark import (
    SCENARIO_TYPES,
    compact_comparison,
    build_rnd_result,
    build_decision_examples,
    generate_suite,
    run_benchmark,
    run_falsification_suite,
    run_historical_anchor_drift_experiment,
    run_question_misspecification_experiment,
    run_registry_corruption_experiment,
    scan_px201_fixture_sources,
)


def test_suite_covers_twenty_required_scenarios_and_separates_truth(tmp_path):
    manifest = generate_suite(tmp_path, seeds=[101, 202, 303])
    public = json.loads((tmp_path / "public_cases.json").read_text())
    truth = json.loads((tmp_path / "private_truth.json").read_text())
    assert len(SCENARIO_TYPES) == 20
    assert manifest["case_count"] == 60
    assert {case["scenario_type"] for case in public["cases"]} == set(SCENARIO_TYPES)
    assert all("target_asset_id" not in case for case in public["cases"])
    assert all(case["ground_truth_access"] == "forbidden_during_response" for case in public["cases"])
    assert all("target_asset_id" in case for case in truth["cases"])


def test_benchmark_locks_responses_before_scoring_and_is_reproducible(tmp_path):
    result = run_benchmark(
        tmp_path,
        seeds=[7, 13],
        methods=["guarded_evidence"],
        question_strategies=["reliability_adjusted_voi"],
    )
    lock = json.loads(
        (tmp_path / "lock__guarded_evidence__reliability_adjusted_voi.json").read_text()
    )
    assert lock["truth_opened"] is False
    assert len(lock["response_sha256"]) == 64
    score = result["approach_results"][0]
    assert score["cases"] == 40
    assert score["response_sha256"] == lock["response_sha256"]
    assert score["attribution"]["false_attributions"] == 0
    assert result["status"] == "synthetic_benchmark_not_field_validation"


def test_voi_strategy_beats_raw_information_gain_on_answerability(tmp_path):
    result = run_benchmark(tmp_path, seeds=[19])
    rows = compact_comparison(result)
    for method in {row["method"] for row in rows}:
        by_strategy = {row["question_strategy"]: row for row in rows if row["method"] == method}
        assert by_strategy["reliability_adjusted_voi"]["best_question_accuracy"] == 1.0
        assert by_strategy["information_gain"]["best_question_accuracy"] < 1.0


def test_falsification_rejects_unsafe_raw_policy_and_preserves_failures():
    result = run_falsification_suite()
    assert result["counts"]["guarded_evidence"]["false_attribution"] == 0
    assert result["counts"]["contextual"]["false_attribution"] > 0
    assert result["counts"]["evidence_aware"]["false_attribution"] > 0
    assert any(
        item["outcome"] == "false_attribution"
        for case in result["cases"]
        for item in case["results"]
    )


def test_corruption_experiment_quantifies_coverage_safety_tradeoff():
    result = run_registry_corruption_experiment(seeds=[3, 5], cases_per_seed=30)
    rows = result["results"]
    hostile = [
        row for row in rows
        if row["corruption_rate"] == 0.5 and row["registry_condition"] == "unlabelled_error"
    ]
    by_method = {row["method"]: row for row in hostile}
    assert by_method["contextual"]["false_attribution_rate"] > 0.25
    assert by_method["guarded_evidence"]["false_attribution_rate"] == 0
    assert by_method["guarded_evidence"]["coverage"] < by_method["contextual"]["coverage"]
    assert result["interpretation_boundary"].startswith("Les taux de corruption")


def test_historical_drift_experiment_selects_threshold_without_false_reuse():
    result = run_historical_anchor_drift_experiment(seeds=[7, 11])
    selected = next(
        row for row in result["threshold_results"]
        if row["maximum_distance"] == result["selected_threshold"]
    )
    assert selected["false_accept"] == 0
    assert selected["correct_refusal_rate"] == 1.0
    assert result["limit"].startswith("Les régimes synthétiques")


def test_px201_scan_distinguishes_document_mention_from_data_fixture(tmp_path):
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "notes.md").write_text("PX-201 est mentionné ici.")
    first = scan_px201_fixture_sources(tmp_path)
    assert first["matches"]
    assert first["fixture_available"] is False
    (tmp_path / "examples" / "PX201_measurements.csv").write_text("timestamp,power_kw\n")
    second = scan_px201_fixture_sources(tmp_path)
    assert second["fixture_available"] is True
    assert second["decision"] == "reproduce_independently"


def test_decision_examples_keep_unknown_and_forbid_mechanism():
    payload = build_decision_examples()
    assert len(payload["examples"]) == 5
    for example in payload["examples"]:
        candidates = example["decision"]["assessment"]["candidates"]
        assert "unknown" in {item["asset_id"] for item in candidates}
        assert example["expected_boundary"]["physical_mechanism"] is None
        assert example["expected_boundary"]["prognosis"] is None


def test_question_partition_error_is_only_mitigated_when_risk_is_declared():
    result = run_question_misspecification_experiment(seeds=[2, 3], cases_per_seed=50)
    rows = {
        (row["mapping_error_rate"], row["risk_disclosure"], row["strategy"]): row
        for row in result["results"]
    }
    hidden = rows[(0.5, "unlabelled", "reliability_adjusted_voi")]
    declared = rows[(0.5, "declared", "reliability_adjusted_voi")]
    assert hidden["fragile_question_selection_rate"] == 1.0
    assert declared["fragile_question_selection_rate"] == 0.0
    assert declared["mean_realized_information_gain_bits"] == 1.0
    assert hidden["mean_realized_information_gain_bits"] != 2.0
    assert result["limit"].startswith("Le planificateur optimise")
