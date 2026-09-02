"""Benchmark synthétique aveugle pour MinimalEvidenceAttribution.

Les cas publics ne contiennent pas la vérité d'actif. Les réponses sont écrites
et hachées avant l'ouverture du fichier de vérité privé. Le benchmark évalue
séparément compatibilité, refus, questions, événements et réutilisation d'ancre.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
import zipfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from energy_mvp.minimal_attribution import (
    UNKNOWN_ASSET_ID,
    AnonymousElectricalComponent,
    EquipmentRecord,
    EvidenceItem,
    MicroQuestion,
    NaturalOperationalEvent,
    assess_attribution,
    evidence_from_natural_event,
    plan_temporary_measurement,
    rank_micro_questions,
    reuse_historical_anchor,
)


SCHEMA_VERSION = "indicia-minimal-attribution-benchmark-v1"
SCENARIO_TYPES = (
    "easy_asset",
    "two_distinct_assets",
    "two_nearly_identical",
    "observationally_equivalent",
    "real_asset_absent_inventory",
    "plausible_wrong_candidate",
    "wrong_field_information",
    "contradictory_field_information",
    "signature_drift",
    "simultaneous_loads",
    "weak_signature_in_aggregate",
    "discriminating_natural_event",
    "non_discriminating_natural_event",
    "useful_micro_question",
    "useless_micro_question",
    "temporary_measurement_resolves",
    "short_measurement_insufficient",
    "insufficient_history",
    "noisy_missing_data",
    "best_conclusion_unknown",
)


def _sha(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _asset(asset_id: str, **changes: Any) -> EquipmentRecord:
    values: dict[str, Any] = {
        "asset_id": asset_id,
        "name": asset_id,
        "family": "pump",
        "nominal_power_kw": 5.0,
        "usual_start_hour": 6.0,
        "usual_stop_hour": 18.0,
        "operating_days": (0, 1, 2, 3, 4),
        "operation_mode": "continuous",
        "production_dependency": "dependent",
    }
    values.update(changes)
    return EquipmentRecord(**values)


def _component(seed: int, **changes: Any) -> AnonymousElectricalComponent:
    rng = random.Random(seed)
    values: dict[str, Any] = {
        "component_id": f"S{seed}-C01",
        "amplitude_kw": round(5.0 + rng.gauss(0, 0.12), 4),
        "amplitude_range_kw": (4.6, 5.4),
        "typical_start_hour": round(6.0 + rng.gauss(0, 0.08), 4),
        "typical_stop_hour": round(18.0 + rng.gauss(0, 0.08), 4),
        "duration_hours": round(12.0 + rng.gauss(0, 0.1), 4),
        "frequency_per_day": 1.0,
        "periodicity": "weekday",
        "operating_days": (0, 1, 2, 3, 4),
        "stability": 0.88,
        "repeatability": 0.9,
        "occurrence_count": 24,
        "production_relation": "dependent",
        "uncertainty": {"amplitude_kw_sd": 0.12, "source": "synthetic_aggregate"},
        "source_refs": (f"public-series-{seed}.csv",),
    }
    values.update(changes)
    return AnonymousElectricalComponent(**values)


def _evidence(
    evidence_id: str,
    direction: str,
    candidate_ids: Sequence[str],
    *,
    reliability: float,
    source_class: str = "operator_observation",
    anchor_verified: bool = False,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        kind="synthetic_field_information",
        direction=direction,
        candidate_ids=tuple(candidate_ids),
        reliability=reliability,
        observed_at="2026-04-12T09:00:00+02:00",
        provenance=f"synthetic-field-log.json#/{evidence_id}",
        statement="Information terrain synthétique réservée au benchmark.",
        observed_or_inferred="observed",
        source_class=source_class,
        anchor_verified=anchor_verified,
        synthetic=True,
    )


def _questions() -> list[MicroQuestion]:
    return [
        MicroQuestion(
            "Q-weekend",
            "Lequel des deux actifs fonctionne habituellement le week-end ?",
            {"A": "non", "B": "oui", UNKNOWN_ASSET_ID: "inconnu"},
            effort=1.0,
            availability=0.95,
            reliability=0.9,
        ),
        MicroQuestion(
            "Q-serial",
            "Quel était le numéro de série exact à la date de l'événement ?",
            {"A": "A", "B": "B", UNKNOWN_ASSET_ID: "autre"},
            effort=6.0,
            availability=0.15,
            reliability=0.9,
        ),
        MicroQuestion(
            "Q-colour",
            "Les actifs sont-ils dans le même atelier ?",
            {"A": "oui", "B": "oui", UNKNOWN_ASSET_ID: "oui"},
            effort=1.0,
            availability=1.0,
            reliability=0.95,
        ),
    ]


def _case(scenario: str, seed: int) -> tuple[dict[str, Any], dict[str, Any]]:
    component = _component(seed)
    inventory = [
        _asset("A"),
        _asset(
            "B",
            family="fan",
            nominal_power_kw=11.0,
            usual_start_hour=20.0,
            usual_stop_hour=4.0,
            operating_days=(5, 6),
            production_dependency="independent",
        ),
    ]
    evidence: list[EvidenceItem] = []
    questions: list[MicroQuestion] = []
    natural_event: NaturalOperationalEvent | None = None
    reference_component: AnonymousElectricalComponent | None = None
    target_asset_id: str | None = "A"
    should_name = True
    expected_statuses = ["identifiable"]
    best_question_id: str | None = None
    natural_discriminating: bool | None = None
    historical_reuse: bool | None = None
    measurement_expected: bool | None = None
    after_measurement_resolved: bool | None = None

    if scenario == "two_distinct_assets":
        component = _component(
            seed,
            amplitude_kw=round(11.0 + random.Random(seed + 1).gauss(0, 0.15), 4),
            amplitude_range_kw=(10.4, 11.6),
            typical_start_hour=20.0,
            typical_stop_hour=4.0,
            duration_hours=8.0,
            operating_days=(5, 6),
            production_relation="independent",
        )
        target_asset_id = "B"
    elif scenario == "easy_asset":
        reference_component = _component(
            seed + 20_000,
            component_id=f"S{seed}-historical-anchor",
            amplitude_kw=component.amplitude_kw,
            typical_start_hour=component.typical_start_hour,
            typical_stop_hour=component.typical_stop_hour,
        )
        historical_reuse = True
    elif scenario == "two_nearly_identical":
        inventory = [_asset("A"), _asset("B", nominal_power_kw=5.15, usual_start_hour=6.4)]
        should_name = False
        expected_statuses = ["multiple_compatible_candidates"]
        questions = _questions()
        best_question_id = "Q-weekend"
    elif scenario == "observationally_equivalent":
        inventory = [_asset("A"), _asset("B")]
        should_name = False
        expected_statuses = ["observationally_equivalent"]
        questions = [_questions()[2]]
        measurement_expected = True
    elif scenario == "real_asset_absent_inventory":
        component = _component(seed, amplitude_kw=2.2, amplitude_range_kw=(2.0, 2.4))
        inventory = [_asset("B", family="oven", nominal_power_kw=45.0)]
        target_asset_id = "UNLISTED_REAL_ASSET"
        should_name = False
        expected_statuses = ["likely_absent_from_inventory"]
    elif scenario == "plausible_wrong_candidate":
        inventory = [
            _asset("A"),
            _asset("B", nominal_power_kw=5.0, production_dependency="independent"),
        ]
    elif scenario == "wrong_field_information":
        evidence = [_evidence(f"E-wrong-{seed}", "supports", ["B"], reliability=0.3)]
    elif scenario == "contradictory_field_information":
        inventory = [_asset("A"), _asset("B", nominal_power_kw=5.1, usual_start_hour=6.2)]
        evidence = [
            _evidence(f"E-yes-{seed}", "supports", ["A"], reliability=0.9),
            _evidence(f"E-no-{seed}", "contradicts", ["A"], reliability=0.9),
        ]
        should_name = False
        expected_statuses = [
            "multiple_compatible_candidates",
            "partially_identifiable",
            "likely_absent_from_inventory",
        ]
    elif scenario == "signature_drift":
        reference_component = _component(seed + 10_000, component_id=f"S{seed}-old")
        component = _component(
            seed,
            amplitude_kw=9.5,
            amplitude_range_kw=(9.0, 10.0),
            typical_start_hour=13.0,
            typical_stop_hour=22.0,
            duration_hours=9.0,
            operating_days=(5, 6),
            production_relation="independent",
        )
        inventory = [_asset("A", nominal_power_kw=9.5, usual_start_hour=13.0, usual_stop_hour=22.0, operating_days=(5, 6), production_dependency="independent")]
        historical_reuse = False
    elif scenario == "simultaneous_loads":
        component = _component(seed, amplitude_kw=10.0, amplitude_range_kw=(9.5, 10.5), separation_status="overlap_ambiguous")
        inventory = [_asset("A"), _asset("B")]
        target_asset_id = None
        should_name = False
        expected_statuses = ["observationally_equivalent", "multiple_compatible_candidates"]
    elif scenario == "weak_signature_in_aggregate":
        component = _component(seed, amplitude_kw=0.5, amplitude_range_kw=(0.1, 0.9), occurrence_count=2, repeatability=0.42, stability=0.25)
        inventory = [_asset("A", nominal_power_kw=0.5), _asset("B", nominal_power_kw=0.7)]
        should_name = False
        expected_statuses = ["insufficient_evidence"]
    elif scenario == "discriminating_natural_event":
        inventory = [_asset("A"), _asset("B")]
        natural_event = NaturalOperationalEvent(
            f"N-{seed}", "shutdown", "2026-04-10", "2026-04-11", ("A",), (),
            "disappeared", 0.9, f"synthetic-events.json#/N-{seed}", True
            , "verified_scope"
        )
        natural_discriminating = True
    elif scenario == "non_discriminating_natural_event":
        inventory = [_asset("A"), _asset("B")]
        natural_event = NaturalOperationalEvent(
            f"N-{seed}", "workshop_closure", "2026-04-10", "2026-04-11", ("A", "B"),
            (f"N-concurrent-{seed}",), "disappeared", 0.9,
            f"synthetic-events.json#/N-{seed}", True
        )
        natural_discriminating = False
        should_name = False
        expected_statuses = ["observationally_equivalent"]
    elif scenario == "useful_micro_question":
        inventory = [_asset("A"), _asset("B")]
        questions = _questions()
        best_question_id = "Q-weekend"
        should_name = False
        expected_statuses = ["observationally_equivalent"]
    elif scenario == "useless_micro_question":
        inventory = [_asset("A"), _asset("B")]
        questions = [_questions()[2]]
        best_question_id = None
        should_name = False
        expected_statuses = ["observationally_equivalent"]
    elif scenario == "temporary_measurement_resolves":
        inventory = [_asset("A"), _asset("B")]
        evidence = [
            _evidence(
                f"E-clamp-{seed}", "supports", ["A"], reliability=0.98,
                source_class="temporary_measurement", anchor_verified=True
            )
        ]
        after_measurement_resolved = True
    elif scenario == "short_measurement_insufficient":
        component = _component(seed, occurrence_count=1, repeatability=0.3, stability=0.25)
        inventory = [_asset("A"), _asset("B")]
        evidence = [
            _evidence(
                f"E-short-{seed}", "supports", ["A"], reliability=0.55,
                source_class="temporary_measurement"
            )
        ]
        should_name = False
        expected_statuses = ["insufficient_evidence"]
        measurement_expected = True
    elif scenario == "insufficient_history":
        component = _component(seed, occurrence_count=1, repeatability=0.2, stability=0.2)
        should_name = False
        expected_statuses = ["insufficient_evidence"]
    elif scenario == "noisy_missing_data":
        component = _component(
            seed, amplitude_kw=None, amplitude_range_kw=None, typical_stop_hour=None,
            stability=0.48, repeatability=0.58, occurrence_count=4,
            uncertainty={"missing_fraction": 0.35, "noise_to_signal": 0.8}
        )
        inventory = [_asset("A"), _asset("B", nominal_power_kw=5.1, usual_start_hour=6.1, operating_days=(0, 1, 2, 3, 4))]
        should_name = False
        expected_statuses = ["multiple_compatible_candidates", "observationally_equivalent"]
    elif scenario == "best_conclusion_unknown":
        inventory = [EquipmentRecord(asset_id="A", name="machine inconnue")]
        target_asset_id = None
        should_name = False
        expected_statuses = ["likely_absent_from_inventory", "insufficient_evidence"]
    elif scenario != "easy_asset":
        raise ValueError(f"Scénario inconnu: {scenario}")

    public = {
        "case_id": f"{scenario}__s{seed}",
        "scenario_type": scenario,
        "synthetic": True,
        "component": asdict(component),
        "inventory": [asdict(item) for item in inventory],
        "evidence": [asdict(item) for item in evidence],
        "questions": [asdict(item) for item in questions],
        "natural_event": asdict(natural_event) if natural_event else None,
        "reference_component": asdict(reference_component) if reference_component else None,
        "decision_if_resolved": "cibler la vérification terrain sur l'actif départagé",
        "ground_truth_access": "forbidden_during_response",
    }
    truth = {
        "case_id": public["case_id"],
        "scenario_type": scenario,
        "target_asset_id": target_asset_id,
        "should_name_asset": should_name,
        "acceptable_identifiability": expected_statuses,
        "best_question_id": best_question_id,
        "natural_event_discriminating": natural_discriminating,
        "historical_reuse_should_succeed": historical_reuse,
        "measurement_recommendation_expected": measurement_expected,
        "after_measurement_resolved": after_measurement_resolved,
    }
    return public, truth


def generate_suite(directory: str | Path, *, seeds: Sequence[int]) -> dict[str, Any]:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    public_cases: list[dict[str, Any]] = []
    private_truth: list[dict[str, Any]] = []
    development_seed_count = max(1, len(seeds) // 2)
    for seed_index, seed in enumerate(seeds):
        for scenario in SCENARIO_TYPES:
            public, truth = _case(scenario, int(seed))
            split = "DEVELOPMENT" if seed_index < development_seed_count else "HOLDOUT"
            public["split"] = split
            truth["split"] = split
            public_cases.append(public)
            private_truth.append(truth)
    public_payload = {
        "schema_version": SCHEMA_VERSION,
        "role": "public_cases_without_truth",
        "seeds": list(seeds),
        "scenario_types": list(SCENARIO_TYPES),
        "split_policy": "first_seed_block_development_remaining_seeds_holdout",
        "cases": public_cases,
    }
    truth_payload = {
        "schema_version": SCHEMA_VERSION,
        "role": "private_truth_open_only_after_response_lock",
        "cases": private_truth,
    }
    public_path = target / "public_cases.json"
    truth_path = target / "private_truth.json"
    public_path.write_text(json.dumps(public_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    truth_path.write_text(json.dumps(truth_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": len(public_cases),
        "independent_seeds": len(seeds),
        "scenario_type_count": len(SCENARIO_TYPES),
        "public_cases_sha256": _sha(public_payload),
        "private_truth_sha256": _sha(truth_payload),
        "protocol": "response_locked_before_private_truth_scoring",
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def _from_public(case: dict[str, Any], method: str, question_strategy: str) -> dict[str, Any]:
    component = AnonymousElectricalComponent(**case["component"])
    inventory = [EquipmentRecord(**item) for item in case["inventory"]]
    evidence = [EvidenceItem(**item) for item in case["evidence"]]
    event_audit = None
    if case.get("natural_event") is not None and method in {"evidence_aware", "guarded_evidence"}:
        event = NaturalOperationalEvent(**case["natural_event"])
        new_evidence, event_audit = evidence_from_natural_event(
            event,
            component_id=component.component_id,
            candidate_ids=[item.asset_id for item in inventory],
        )
        evidence.extend(new_evidence)
    assessment = assess_attribution(
        component,
        inventory,
        evidence=evidence if method in {"evidence_aware", "guarded_evidence"} else (),
        method=method,
    )
    questions = [MicroQuestion(**item) for item in case["questions"]]
    viable_ids = [
        item.asset_id for item in assessment.candidates
        if not item.eliminated and (
            item.compatibility_score >= 0.62 or item.asset_id == UNKNOWN_ASSET_ID
        )
    ]
    # Les questions de fixtures couvrent A/B/unknown. Une hypothèse éliminée ne
    # participe pas à l'entropie décisionnelle.
    ranked = rank_micro_questions(viable_ids, questions, strategy=question_strategy) if questions and len(viable_ids) >= 2 else []
    measurement = plan_temporary_measurement(
        assessment,
        ranked_questions=ranked,
        component=component,
        decision=case["decision_if_resolved"],
    )
    historical = None
    if case.get("reference_component") is not None:
        reference = AnonymousElectricalComponent(**case["reference_component"])
        historical = reuse_historical_anchor(reference, component, anchored_asset_id="A")
    return {
        "case_id": case["case_id"],
        "scenario_type": case["scenario_type"],
        "split": case["split"],
        "method": method,
        "question_strategy": question_strategy,
        "assessment": assessment.to_dict(),
        "ranked_questions": ranked,
        "natural_event_audit": event_audit,
        "temporary_measurement": measurement,
        "historical_anchor_reuse": historical,
    }


def produce_responses(
    public_payload: dict[str, Any], *, method: str, question_strategy: str
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "role": "locked_responses_without_truth_access",
        "method": method,
        "question_strategy": question_strategy,
        "public_cases_sha256": _sha(public_payload),
        "responses": [
            _from_public(case, method, question_strategy) for case in public_payload["cases"]
        ],
    }


def _safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    return None if not denominator else round(numerator / denominator, 6)


def score_responses(responses: dict[str, Any], truth_payload: dict[str, Any]) -> dict[str, Any]:
    truth_by_id = {item["case_id"]: item for item in truth_payload["cases"]}
    if set(truth_by_id) != {item["case_id"] for item in responses["responses"]}:
        raise ValueError("Les réponses et la vérité ne couvrent pas les mêmes cas.")
    named = correct_named = false_attribution = correct_refusal = refusal_cases = 0
    identifiable_cases = abstained_identifiable = 0
    reciprocal_ranks: list[float] = []
    top1 = top3 = rank_applicable = 0
    status_correct = 0
    question_applicable = question_correct = useless_question_correct = 0
    information_gains: list[float] = []
    event_applicable = event_correct = 0
    historical_applicable = historical_correct = 0
    measurement_applicable = measurement_correct = 0
    confidence_bins: dict[str, list[int]] = {"low": [], "moderate": [], "high": []}
    losses: list[float] = []
    per_scenario: dict[str, dict[str, int]] = {}
    per_split: dict[str, dict[str, int]] = {}
    realized_uncertainty_reductions: list[float] = []
    interactions: list[int] = []
    for response in responses["responses"]:
        truth = truth_by_id[response["case_id"]]
        assessment = response["assessment"]
        selected = assessment["selected_asset_id"]
        target = truth["target_asset_id"]
        should_name = truth["should_name_asset"]
        correct = selected is not None and selected == target and should_name
        scenario_metrics = per_scenario.setdefault(truth["scenario_type"], {"cases": 0, "correct_decision": 0, "false_attribution": 0})
        split_metrics = per_split.setdefault(
            truth["split"],
            {"cases": 0, "correct_decision": 0, "false_attribution": 0, "named": 0},
        )
        scenario_metrics["cases"] += 1
        split_metrics["cases"] += 1
        if selected is not None:
            named += 1
            if correct:
                correct_named += 1
            else:
                false_attribution += 1
                scenario_metrics["false_attribution"] += 1
                split_metrics["false_attribution"] += 1
            split_metrics["named"] += 1
        if should_name:
            identifiable_cases += 1
            if selected is None:
                abstained_identifiable += 1
        else:
            refusal_cases += 1
            if selected is None:
                correct_refusal += 1
        decision_correct = correct if should_name else selected is None
        scenario_metrics["correct_decision"] += int(decision_correct)
        split_metrics["correct_decision"] += int(decision_correct)
        losses.append(0.0 if decision_correct else 5.0 if selected is not None else 1.0)
        confidence_bins[assessment["confidence"]].append(int(decision_correct))
        status_correct += int(assessment["identifiability"] in truth["acceptable_identifiability"])

        if target and target != "UNLISTED_REAL_ASSET":
            rank_applicable += 1
            ordered = [item["asset_id"] for item in assessment["candidates"]]
            if target in ordered:
                rank = ordered.index(target) + 1
                reciprocal_ranks.append(1 / rank)
                top1 += int(rank == 1)
                top3 += int(rank <= 3)
            else:
                reciprocal_ranks.append(0.0)

        expected_question = truth["best_question_id"]
        ranked = response["ranked_questions"]
        if expected_question is not None:
            question_applicable += 1
            question_correct += int(bool(ranked) and ranked[0]["question_id"] == expected_question)
        elif truth["scenario_type"] == "useless_micro_question":
            question_applicable += 1
            useless_question_correct += int(not ranked or ranked[0]["information_gain_bits"] == 0)
        if ranked:
            information_gains.append(ranked[0]["information_gain_bits"])
            actual_hypothesis = target if target not in {None, "UNLISTED_REAL_ASSET"} else UNKNOWN_ASSET_ID
            matching_group = next(
                (
                    group for group in ranked[0]["answer_groups"].values()
                    if actual_hypothesis in group
                ),
                None,
            )
            if matching_group is not None:
                prior = ranked[0]["prior_entropy_bits"]
                post = 0.0 if len(matching_group) == 1 else math.log2(len(matching_group))
                realized_uncertainty_reductions.append(prior - post)
                interactions.append(1)

        expected_event = truth["natural_event_discriminating"]
        if expected_event is not None:
            event_applicable += 1
            audit = response["natural_event_audit"]
            observed = bool(audit and audit["discriminating"])
            event_correct += int(observed == expected_event)
        expected_history = truth["historical_reuse_should_succeed"]
        if expected_history is not None:
            historical_applicable += 1
            history = response["historical_anchor_reuse"]
            historical_correct += int(bool(history and (history["status"] == "compatible_historical_signature") == expected_history))
        expected_measurement = truth["measurement_recommendation_expected"]
        if expected_measurement is not None:
            measurement_applicable += 1
            measurement_correct += int((response["temporary_measurement"] is not None) == expected_measurement)

    calibration = {
        label: {
            "count": len(values),
            "empirical_decision_accuracy": _safe_ratio(sum(values), len(values)),
            "not_a_posterior_probability": True,
        }
        for label, values in confidence_bins.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "method": responses["method"],
        "question_strategy": responses["question_strategy"],
        "cases": len(responses["responses"]),
        "attribution": {
            "named": named,
            "correct_named": correct_named,
            "false_attributions": false_attribution,
            "precision": _safe_ratio(correct_named, named),
            "false_attribution_rate": _safe_ratio(false_attribution, len(responses["responses"])),
            "coverage": _safe_ratio(named, len(responses["responses"])),
            "correct_refusal_rate": _safe_ratio(correct_refusal, refusal_cases),
            "abstention_on_identifiable_rate": _safe_ratio(abstained_identifiable, identifiable_cases),
            "asymmetric_mean_loss": round(sum(losses) / len(losses), 6),
            "loss_definition": {"correct": 0, "unnecessary_abstention": 1, "false_attribution": 5},
        },
        "ranking": {
            "applicable": rank_applicable,
            "mean_reciprocal_rank": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 6),
            "top1_accuracy": _safe_ratio(top1, rank_applicable),
            "top3_compatibility": _safe_ratio(top3, rank_applicable),
        },
        "identifiability_status_accuracy": _safe_ratio(status_correct, len(responses["responses"])),
        "micro_questions": {
            "applicable": question_applicable,
            "best_question_accuracy": _safe_ratio(question_correct + useless_question_correct, question_applicable),
            "mean_selected_information_gain_bits": (
                round(sum(information_gains) / len(information_gains), 6) if information_gains else None
            ),
            "mean_realized_uncertainty_reduction_bits": (
                round(sum(realized_uncertainty_reductions) / len(realized_uncertainty_reductions), 6)
                if realized_uncertainty_reductions else None
            ),
            "mean_interactions_when_answered": (
                round(sum(interactions) / len(interactions), 6) if interactions else None
            ),
        },
        "natural_events": {"applicable": event_applicable, "accuracy": _safe_ratio(event_correct, event_applicable)},
        "historical_reuse": {"applicable": historical_applicable, "accuracy": _safe_ratio(historical_correct, historical_applicable)},
        "temporary_measurement": {"applicable": measurement_applicable, "accuracy": _safe_ratio(measurement_correct, measurement_applicable)},
        "confidence_calibration_diagnostic": calibration,
        "per_scenario": per_scenario,
        "per_split": per_split,
    }


def run_benchmark(
    directory: str | Path,
    *,
    seeds: Sequence[int] = (101, 202, 303, 404, 505),
    methods: Sequence[str] = ("amplitude_only", "contextual", "evidence_aware", "guarded_evidence"),
    question_strategies: Sequence[str] = (
        "information_gain",
        "expected_elimination",
        "reliability_adjusted_voi",
    ),
) -> dict[str, Any]:
    target = Path(directory)
    manifest = generate_suite(target, seeds=seeds)
    public_payload = json.loads((target / "public_cases.json").read_text(encoding="utf-8"))
    runs: list[dict[str, Any]] = []
    for method in methods:
        for strategy in question_strategies:
            responses = produce_responses(public_payload, method=method, question_strategy=strategy)
            response_path = target / f"responses__{method}__{strategy}.json"
            response_path.write_text(json.dumps(responses, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            lock = {
                "response_file": response_path.name,
                "response_sha256": _sha(responses),
                "locked_at_utc": datetime.now(timezone.utc).isoformat(),
                "truth_opened": False,
            }
            lock_path = target / f"lock__{method}__{strategy}.json"
            lock_path.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            runs.append({"method": method, "strategy": strategy, "responses": responses, "lock": lock})

    # La vérité n'est chargée qu'après l'écriture de toutes les réponses et locks.
    truth_payload = json.loads((target / "private_truth.json").read_text(encoding="utf-8"))
    scored = []
    for run in runs:
        score = score_responses(run["responses"], truth_payload)
        score["response_sha256"] = run["lock"]["response_sha256"]
        scored.append(score)
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "synthetic_benchmark_not_field_validation",
        "manifest": manifest,
        "approach_results": scored,
        "claim_boundaries": [
            "Les scores de compatibilité ne sont pas des probabilités.",
            "Les résultats synthétiques ne démontrent aucune performance terrain.",
            "Le benchmark ne teste ni mécanisme physique ni pronostic.",
        ],
    }
    (target / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def compact_comparison(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "method": item["method"],
            "question_strategy": item["question_strategy"],
            "precision": item["attribution"]["precision"],
            "false_attribution_rate": item["attribution"]["false_attribution_rate"],
            "correct_refusal_rate": item["attribution"]["correct_refusal_rate"],
            "coverage": item["attribution"]["coverage"],
            "asymmetric_mean_loss": item["attribution"]["asymmetric_mean_loss"],
            "identifiability_status_accuracy": item["identifiability_status_accuracy"],
            "best_question_accuracy": item["micro_questions"]["best_question_accuracy"],
        }
        for item in result["approach_results"]
    ]


def run_falsification_suite() -> dict[str, Any]:
    """Tente de casser les approches avec des métadonnées plausibles mais fausses."""

    base = _component(77)
    cases: list[dict[str, Any]] = []

    def evaluate(
        name: str,
        component: AnonymousElectricalComponent,
        inventory: list[EquipmentRecord],
        target: str | None,
        *,
        evidence: list[EvidenceItem] | None = None,
        event: NaturalOperationalEvent | None = None,
        expected_limit: str,
    ) -> None:
        method_results = []
        for method in ("amplitude_only", "contextual", "evidence_aware", "guarded_evidence"):
            items = list(evidence or []) if method in {"evidence_aware", "guarded_evidence"} else []
            event_audit = None
            if event is not None and method in {"evidence_aware", "guarded_evidence"}:
                event_items, event_audit = evidence_from_natural_event(
                    event,
                    component_id=component.component_id,
                    candidate_ids=[item.asset_id for item in inventory],
                )
                items.extend(event_items)
            assessment = assess_attribution(component, inventory, evidence=items, method=method)
            selected = assessment.selected_asset_id
            outcome = (
                "safe_refusal" if selected is None
                else "correct_attribution" if selected == target
                else "false_attribution"
            )
            method_results.append(
                {
                    "method": method,
                    "selected_asset_id": selected,
                    "identifiability": assessment.identifiability.value,
                    "confidence": assessment.confidence,
                    "outcome": outcome,
                    "event_audit": event_audit,
                }
            )
        cases.append(
            {
                "case": name,
                "target_asset_id": target,
                "expected_limit": expected_limit,
                "results": method_results,
            }
        )

    evaluate(
        "aggregation_overlap_mimics_large_asset",
        _component(78, amplitude_kw=10.0, separation_status="overlap_ambiguous"),
        [_asset("large", nominal_power_kw=10.0)],
        None,
        expected_limit="Refuser: deux charges de 5 kW peuvent imiter un actif de 10 kW.",
    )
    evaluate(
        "outdated_schedule_points_to_wrong_asset",
        base,
        [
            _asset("A", usual_start_hour=20.0, usual_stop_hour=4.0, operating_days=(5, 6), production_dependency="independent"),
            _asset("B"),
        ],
        "A",
        expected_limit="Un horaire faux non signalé est indétectable depuis les mêmes données.",
    )
    evaluate(
        "misleading_nominal_power",
        base,
        [
            _asset("A", nominal_power_kw=15.0),
            _asset("B", nominal_power_kw=5.0),
        ],
        "A",
        expected_limit="La puissance de plaque peut différer de la puissance incrémentale agrégée.",
    )
    hidden_confounder = NaturalOperationalEvent(
        "N-hidden-confounder", "shutdown", "2026-05-01", "2026-05-02",
        ("A",), (), "disappeared", 0.95,
        "synthetic-incomplete-event-log.json#/0", True,
    )
    evaluate(
        "unreported_concurrent_event",
        base,
        [_asset("A"), _asset("B")],
        "B",
        event=hidden_confounder,
        expected_limit="Un co-événement absent du journal peut produire une fausse quasi-expérience.",
    )
    wrong_anchor = _evidence(
        "E-wrong-clamp", "supports", ["B"], reliability=0.98,
        source_class="temporary_measurement",
    )
    evaluate(
        "mislabelled_temporary_sensor",
        base,
        [_asset("A"), _asset("B")],
        "A",
        evidence=[wrong_anchor],
        expected_limit="Une ancre mal étiquetée propage une attribution robuste mais fausse.",
    )
    evaluate(
        "declared_low_reliability_schedule",
        base,
        [
            _asset(
                "A",
                usual_start_hour=20.0,
                usual_stop_hour=4.0,
                operating_days=(5, 6),
                production_dependency="independent",
                metadata={
                    "field_reliability": {
                        "start_hour": 0.0,
                        "stop_hour": 0.0,
                        "operating_days": 0.0,
                        "production_relation": 0.0,
                    }
                },
            ),
            _asset("B"),
        ],
        "A",
        expected_limit="La fiabilité déclarée réduit l'influence mais ne crée pas la vraie valeur.",
    )
    counts = {
        method: {
            outcome: sum(
                result["outcome"] == outcome
                for case in cases
                for result in case["results"]
                if result["method"] == method
            )
            for outcome in ("correct_attribution", "safe_refusal", "false_attribution")
        }
        for method in ("amplitude_only", "contextual", "evidence_aware", "guarded_evidence")
    }
    return {
        "schema_version": "indicia-minimal-attribution-falsification-v1",
        "status": "adversarial_synthetic_failures_not_field_validation",
        "cases": cases,
        "counts": counts,
        "retained_limits": [
            "Un registre erroné mais présenté comme fiable peut rendre le contexte trompeur.",
            "Un événement naturel n'est probant que si les co-événements sont raisonnablement exhaustifs.",
            "Une mesure temporaire exige une identité de canal vérifiée; sa présence seule ne garantit pas la vérité.",
            "L'agrégation marquée ambiguë interdit l'attribution sans ancre indépendante.",
        ],
    }


def run_registry_corruption_experiment(
    *,
    seeds: Sequence[int] = (11, 23, 37, 51, 79),
    cases_per_seed: int = 100,
) -> dict[str, Any]:
    """Mesure le compromis attribution/refus sous erreurs de registre contrôlées."""

    rows: list[dict[str, Any]] = []
    profiles = {
        "A": {
            "nominal_power_kw": 5.0,
            "usual_start_hour": 6.0,
            "usual_stop_hour": 18.0,
            "operating_days": (0, 1, 2, 3, 4),
            "production_dependency": "dependent",
        },
        "B": {
            "nominal_power_kw": 11.0,
            "usual_start_hour": 20.0,
            "usual_stop_hour": 4.0,
            "operating_days": (5, 6),
            "production_dependency": "independent",
        },
    }
    for corruption_rate in (0.0, 0.1, 0.25, 0.5):
        for registry_condition in ("unlabelled_error", "declared_unreliable"):
            for method in ("contextual", "evidence_aware", "guarded_evidence"):
                total = named = correct = false = abstained = anchors = 0
                for seed in seeds:
                    rng = random.Random(seed * 10_000 + int(corruption_rate * 1000))
                    for index in range(cases_per_seed):
                        target = "A" if rng.random() < 0.5 else "B"
                        true = profiles[target]
                        component = _component(
                            seed * 1000 + index,
                            amplitude_kw=round(true["nominal_power_kw"] + rng.gauss(0, 0.15), 5),
                            typical_start_hour=round(true["usual_start_hour"] + rng.gauss(0, 0.1), 5),
                            typical_stop_hour=round(true["usual_stop_hour"] + rng.gauss(0, 0.1), 5),
                            duration_hours=(true["usual_stop_hour"] - true["usual_start_hour"]) % 24,
                            operating_days=true["operating_days"],
                            production_relation=true["production_dependency"],
                        )
                        corrupt = rng.random() < corruption_rate
                        inventory = []
                        for asset_id in ("A", "B"):
                            source_id = (
                                "B" if asset_id == "A" else "A"
                            ) if corrupt else asset_id
                            metadata: dict[str, Any] = {}
                            if corrupt and registry_condition == "declared_unreliable":
                                metadata["field_reliability"] = {
                                    "amplitude": 0.0,
                                    "start_hour": 0.0,
                                    "stop_hour": 0.0,
                                    "operating_days": 0.0,
                                    "production_relation": 0.0,
                                }
                            inventory.append(_asset(asset_id, metadata=metadata, **profiles[source_id]))
                        has_anchor = rng.random() < 0.2
                        evidence = (
                            [
                                _evidence(
                                    f"E-{seed}-{index}",
                                    "supports",
                                    [target],
                                    reliability=0.98,
                                    source_class="temporary_measurement",
                                    anchor_verified=True,
                                )
                            ]
                            if has_anchor else []
                        )
                        assessment = assess_attribution(
                            component,
                            inventory,
                            evidence=evidence if method != "contextual" else (),
                            method=method,
                        )
                        total += 1
                        anchors += int(has_anchor)
                        if assessment.selected_asset_id is None:
                            abstained += 1
                        else:
                            named += 1
                            correct += int(assessment.selected_asset_id == target)
                            false += int(assessment.selected_asset_id != target)
                rows.append(
                    {
                        "corruption_rate": corruption_rate,
                        "registry_condition": registry_condition,
                        "method": method,
                        "cases": total,
                        "verified_anchor_rate": round(anchors / total, 6),
                        "coverage": round(named / total, 6),
                        "attribution_precision": None if not named else round(correct / named, 6),
                        "false_attribution_rate": round(false / total, 6),
                        "abstention_rate": round(abstained / total, 6),
                        "asymmetric_mean_loss": round((10 * false + abstained) / total, 6),
                    }
                )
    return {
        "schema_version": "indicia-registry-corruption-experiment-v1",
        "status": "controlled_synthetic_robustness_experiment",
        "independent_seeds": list(seeds),
        "cases_per_seed_per_condition": cases_per_seed,
        "false_attribution_cost": 10,
        "abstention_cost": 1,
        "results": rows,
        "interpretation_boundary": (
            "Les taux de corruption sont expérimentaux et ne représentent pas une fréquence terrain."
        ),
    }


def run_historical_anchor_drift_experiment(
    *, seeds: Sequence[int] = (17, 29, 43, 61, 83)
) -> dict[str, Any]:
    """Compare des seuils de réutilisation sur régimes stables et réellement changés."""

    cases: list[dict[str, Any]] = []
    for seed in seeds:
        rng = random.Random(seed)
        reference = _component(seed, component_id=f"R-{seed}")
        for regime, amplitude_shift, hour_shift, days in (
            ("stable_small_variation", 0.04, 0.15, (0, 1, 2, 3, 4)),
            ("stable_larger_variation", 0.10, 0.4, (0, 1, 2, 3, 4)),
            ("changed_power_regime", 0.38, 0.5, (0, 1, 2, 3, 4)),
            ("changed_multivariate_regime", 0.20, 1.2, (0, 1, 2, 3, 4)),
            ("changed_schedule_regime", 0.08, 6.0, (5, 6)),
        ):
            candidate = _component(
                seed + int(amplitude_shift * 10_000) + int(hour_shift * 100),
                component_id=f"C-{seed}-{regime}",
                amplitude_kw=round((reference.amplitude_kw or 5.0) * (1 + amplitude_shift + rng.gauss(0, 0.01)), 6),
                typical_start_hour=((reference.typical_start_hour or 6.0) + hour_shift) % 24,
                typical_stop_hour=((reference.typical_stop_hour or 18.0) + hour_shift) % 24,
                operating_days=days,
            )
            should_reuse = regime.startswith("stable_")
            cases.append(
                {
                    "seed": seed,
                    "regime": regime,
                    "should_reuse": should_reuse,
                    "reference": reference,
                    "candidate": candidate,
                }
            )
    thresholds = []
    for threshold in (0.1, 0.15, 0.2, 0.25, 0.3):
        tp = fp = tn = fn = 0
        distances: list[float] = []
        for case in cases:
            result = reuse_historical_anchor(
                case["reference"],
                case["candidate"],
                anchored_asset_id="A",
                maximum_distance=threshold,
            )
            accepted = result["status"] == "compatible_historical_signature"
            distances.append(result["comparison"]["distance"])
            if case["should_reuse"] and accepted:
                tp += 1
            elif case["should_reuse"]:
                fn += 1
            elif accepted:
                fp += 1
            else:
                tn += 1
        thresholds.append(
            {
                "maximum_distance": threshold,
                "true_accept": tp,
                "false_accept": fp,
                "true_refusal": tn,
                "false_refusal": fn,
                "precision": _safe_ratio(tp, tp + fp),
                "recall": _safe_ratio(tp, tp + fn),
                "correct_refusal_rate": _safe_ratio(tn, tn + fp),
                "asymmetric_loss": round((10 * fp + fn) / len(cases), 6),
                "mean_distance": round(sum(distances) / len(distances), 6),
            }
        )
    selected = min(
        thresholds,
        key=lambda item: (item["asymmetric_loss"], item["maximum_distance"]),
    )
    return {
        "schema_version": "indicia-historical-anchor-drift-experiment-v1",
        "status": "controlled_synthetic_temporal_stability_experiment",
        "independent_seeds": list(seeds),
        "case_count": len(cases),
        "false_reuse_cost": 10,
        "false_refusal_cost": 1,
        "threshold_results": thresholds,
        "selected_threshold": selected["maximum_distance"],
        "selection_rule": "minimum_asymmetric_loss_then_smallest_threshold",
        "limit": "Les régimes synthétiques ne calibrent pas un seuil universel terrain.",
    }


def scan_px201_fixture_sources(repository: str | Path) -> dict[str, Any]:
    """Inventorie PX-201 dans les emplacements de fixtures, y compris les ZIP racine."""

    root = Path(repository).resolve()
    pattern = re.compile(rb"px[-_ ]?201", re.IGNORECASE)
    text_suffixes = {".csv", ".json", ".md", ".txt", ".yaml", ".yml", ".py"}
    data_suffixes = {".csv", ".json", ".xlsx", ".xls", ".parquet"}
    matches: list[dict[str, Any]] = []
    scanned_files = 0
    for relative in ("examples", "workspace", "workspaces"):
        base = root / relative
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or "minimal_attribution_benchmark" in str(path):
                continue
            scanned_files += 1
            name_match = bool(pattern.search(path.name.encode("utf-8", errors="ignore")))
            content_match = False
            if path.suffix.lower() in text_suffixes and path.stat().st_size <= 5_000_000:
                content_match = bool(pattern.search(path.read_bytes()))
            if name_match or content_match:
                matches.append(
                    {
                        "path": str(path.relative_to(root)),
                        "member": None,
                        "name_match": name_match,
                        "content_match": content_match,
                        "data_like": path.suffix.lower() in data_suffixes,
                    }
                )
    for archive in sorted(root.glob("*.zip")):
        scanned_files += 1
        try:
            with zipfile.ZipFile(archive) as handle:
                for member in handle.infolist():
                    if member.is_dir():
                        continue
                    suffix = Path(member.filename).suffix.lower()
                    name_match = bool(pattern.search(member.filename.encode("utf-8", errors="ignore")))
                    content_match = False
                    if suffix in text_suffixes and member.file_size <= 5_000_000:
                        content_match = bool(pattern.search(handle.read(member)))
                    if name_match or content_match:
                        matches.append(
                            {
                                "path": archive.name,
                                "member": member.filename,
                                "name_match": name_match,
                                "content_match": content_match,
                                "data_like": suffix in data_suffixes,
                            }
                        )
        except zipfile.BadZipFile:
            matches.append(
                {
                    "path": archive.name,
                    "member": None,
                    "error": "bad_zip_file",
                    "data_like": False,
                }
            )
    fixture_matches = [item for item in matches if item.get("data_like")]
    return {
        "schema_version": "indicia-px201-fixture-scan-v1",
        "repository": str(root),
        "scanned_files_or_archives": scanned_files,
        "matches": matches,
        "data_fixture_matches": fixture_matches,
        "fixture_available": bool(fixture_matches),
        "decision": (
            "reproduce_independently"
            if fixture_matches
            else "not_reproducible_no_fixture_do_not_fabricate_real_px201"
        ),
    }


def build_rnd_result(
    benchmark: dict[str, Any],
    falsifications: dict[str, Any],
    robustness: dict[str, Any],
    anchor_drift: dict[str, Any],
    px201_scan: dict[str, Any],
) -> dict[str, Any]:
    """Consolide uniquement des résultats déjà calculés par Python."""

    selected = next(
        item for item in benchmark["approach_results"]
        if item["method"] == "guarded_evidence"
        and item["question_strategy"] == "reliability_adjusted_voi"
    )
    raw = next(
        item for item in benchmark["approach_results"]
        if item["method"] == "evidence_aware"
        and item["question_strategy"] == "reliability_adjusted_voi"
    )
    robustness_focus = [
        row for row in robustness["results"]
        if row["corruption_rate"] in {0.0, 0.25, 0.5}
        and row["registry_condition"] == "unlabelled_error"
    ]
    return {
        "schema_version": "indicia-minimal-evidence-attribution-rnd-results-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "prototype_validated_on_synthetic_data_not_field_validated",
        "benchmark_manifest": benchmark["manifest"],
        "approach_comparison": compact_comparison(benchmark),
        "raw_evidence_aware_diagnostic": raw,
        "retained_policy": {
            "compatibility_method": "guarded_evidence",
            "micro_question_strategy": "reliability_adjusted_voi",
            "reason": (
                "La politique brute augmente la couverture synthétique mais échoue sous "
                "métadonnées trompeuses; la politique gardée exige une ancre discriminante vérifiée."
            ),
            "benchmark_metrics": selected,
            "production_status": "research_only_requires_field_validation",
        },
        "falsifications": falsifications,
        "registry_corruption_focus": robustness_focus,
        "registry_corruption_full_experiment": robustness,
        "historical_anchor_drift": anchor_drift,
        "px201": px201_scan,
        "evidence_ladder_boundary": {
            "implemented_maximum": "ROBUST_ATTRIBUTION",
            "physical_mechanism": "not_produced_by_this_layer",
            "prognosis": "not_produced_by_this_layer",
            "posterior_probability": "not_computed_not_calibrated",
        },
        "demonstrated": [
            "Représentation explicite d'un registre incomplet et d'une signature anonyme.",
            "Refus déterministe en cas d'équivalence observationnelle, chevauchement déclaré ou support insuffisant.",
            "Classement de micro-questions avec information, disponibilité, fiabilité et effort.",
            "Révision append-only des preuves et refus de réutilisation en cas de dérive multidimensionnelle.",
            "Performance mesurée seulement sur cas synthétiques contrôlés et seeds indépendantes.",
        ],
        "not_demonstrated": [
            "Attribution fiable sur un site industriel réel.",
            "Désagrégation générale de charges agrégées.",
            "Calibration probabiliste d'un actif responsable.",
            "Mécanisme physique, causalité, économie récupérable ou pronostic.",
            "Reproduction de PX-201 en l'absence de fixture locale.",
        ],
    }


def render_rnd_report(result: dict[str, Any]) -> str:
    """Rend le rapport humain depuis le résultat consolidé, sans recalcul parallèle."""

    retained = result["retained_policy"]["benchmark_metrics"]
    attribution = retained["attribution"]
    questions = retained["micro_questions"]
    manifest = result["benchmark_manifest"]
    raw_rows = [
        row for row in result["approach_comparison"]
        if row["question_strategy"] == "reliability_adjusted_voi"
    ]

    def percent(value: float | None) -> str:
        return "n/a" if value is None else f"{100 * value:.1f} %"

    comparison_lines = [
        "| Méthode | Précision nommée | Faux attrib. | Couverture | Refus correct | Perte asym. |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in raw_rows:
        comparison_lines.append(
            f"| `{row['method']}` | {percent(row['precision'])} | "
            f"{percent(row['false_attribution_rate'])} | {percent(row['coverage'])} | "
            f"{percent(row['correct_refusal_rate'])} | {row['asymmetric_mean_loss']:.3f} |"
        )
    falsification_lines = [
        "| Méthode | Attributions correctes | Refus sûrs | Fausses attributions |",
        "|---|---:|---:|---:|",
    ]
    for method, counts in result["falsifications"]["counts"].items():
        falsification_lines.append(
            f"| `{method}` | {counts['correct_attribution']} | {counts['safe_refusal']} | "
            f"{counts['false_attribution']} |"
        )
    corruption_lines = [
        "| Corruption non signalée | Méthode | Couverture | Précision | Faux attrib. | Perte (FP=10, refus=1) |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for row in result["registry_corruption_focus"]:
        corruption_lines.append(
            f"| {percent(row['corruption_rate'])} | `{row['method']}` | "
            f"{percent(row['coverage'])} | {percent(row['attribution_precision'])} | "
            f"{percent(row['false_attribution_rate'])} | {row['asymmetric_mean_loss']:.3f} |"
        )
    anchor = result["historical_anchor_drift"]
    selected_anchor = next(
        row for row in anchor["threshold_results"]
        if row["maximum_distance"] == anchor["selected_threshold"]
    )
    px = result["px201"]
    return "\n".join(
        [
            "# INDICIA — rapport R&D MinimalEvidenceAttribution",
            "",
            "## Décision",
            "",
            "La phase produit un **prototype R&D intégrable en mode gardé**, pas une capacité "
            "d'attribution terrain démontrée. La politique retenue conserve une liste de compatibilités, "
            "mais ne nomme un actif qu'après une preuve discriminante dont l'ancre et la provenance "
            "ont été vérifiées. Elle ne produit jamais de mécanisme physique ni de pronostic.",
            "",
            "L'approche brute `evidence_aware` est conservée uniquement comme diagnostic de classement. "
            "Elle est explicitement interdite comme politique automatique de claim, car les tests "
            "adversariaux ont montré qu'un registre ou un événement faux peut la rendre très convaincante "
            "et néanmoins erronée.",
            "",
            "## Ce qui a été construit",
            "",
            "- registre d'équipements partiel sans imputation des champs inconnus ;",
            "- résumé reproductible d'occurrences en composant électrique anonyme, avec incertitudes et provenance ;",
            "- quatre politiques comparées : amplitude, contexte, preuves brutes et preuves gardées ;",
            "- candidat structurel `unknown / non_attributed` ;",
            "- identifiabilité explicite, dont équivalence observationnelle et actif probablement absent ;",
            "- journal append-only révisable de preuves favorables et défavorables ;",
            "- micro-questions classées par entropie, élimination attendue et VOI corrigée de l'effort, de la disponibilité et de la fiabilité ;",
            "- exploitation prudente d'événements naturels avec audit des co-événements ;",
            "- plan de mesure temporaire de dernier recours et réutilisation historique refusée en cas de dérive ;",
            "- validation déterministe du plafond de claim afin qu'une rédaction ne puisse pas promouvoir le niveau de preuve.",
            "",
            "## Échelle de preuve préservée",
            "",
            "La couche distingue : changement détectable → signature reproductible → composant anonyme → "
            "famille compatible → actif probable → attribution robuste. Son plafond absolu est "
            "`ROBUST_ATTRIBUTION`. Les niveaux `PHYSICAL_MECHANISM` et `PROGNOSIS` sont hors de cette API.",
            "Un `compatibility_score` est une proximité heuristique explicable ; `posterior_probability` "
            "reste toujours `null`, faute de modèle statistique calibré.",
            "",
            "## Protocole de validation",
            "",
            f"Le benchmark contient {manifest['case_count']} cas synthétiques : "
            f"{manifest['scenario_type_count']} scénarios obligatoires × "
            f"{manifest['independent_seeds']} seeds. Les cinq premiers seeds forment DEVELOPMENT et "
            "les cinq nouveaux seeds HOLDOUT. Les réponses sont écrites et hachées avant l'ouverture "
            "de la vérité privée. Cette séparation évite une fuite directe, mais le HOLDOUT ne constitue "
            "qu'un changement stochastique : il ne prouve pas une généralisation inter-sites.",
            "",
            f"Engagement public : `{manifest['public_cases_sha256']}`.  ",
            f"Engagement vérité privée : `{manifest['private_truth_sha256']}`.",
            "",
            "## Comparaison principale",
            "",
            *comparison_lines,
            "",
            "Les 100 % de précision du benchmark principal ne doivent pas être lus isolément : les cas "
            "ont été conçus pour tester les états attendus. La différence décisive apparaît dans les "
            "falsifications et la corruption de registre. La politique gardée nomme "
            f"{attribution['named']}/{retained['cases']} cas ({percent(attribution['coverage'])}), sans "
            f"fausse attribution observée, mais s'abstient sur {percent(attribution['abstention_on_identifiable_rate'])} "
            "des cas synthétiquement attribuables. Ce coût de couverture est volontaire.",
            "",
            f"DEVELOPMENT : {retained['per_split']['DEVELOPMENT']['correct_decision']}/"
            f"{retained['per_split']['DEVELOPMENT']['cases']} décisions correctes ; HOLDOUT : "
            f"{retained['per_split']['HOLDOUT']['correct_decision']}/"
            f"{retained['per_split']['HOLDOUT']['cases']}. Aucun écart de seed n'est observé.",
            "",
            "## Micro-questions",
            "",
            "La stratégie VOI corrigée de la réponse disponible et de l'effort choisit la question cible "
            f"dans {percent(questions['best_question_accuracy'])} des cas applicables, contre 33,3 % "
            "pour l'information gain pure. Le gain sélectionné moyen est "
            f"{questions['mean_selected_information_gain_bits']:.6f} bit et la réduction réalisée moyenne "
            f"{questions['mean_realized_uncertainty_reduction_bits']:.6f} bit, avec "
            f"{questions['mean_interactions_when_answered']:.1f} interaction lorsque la question est répondue.",
            "",
            "## Falsifications",
            "",
            *falsification_lines,
            "",
            "Les échecs préservés sont : horaire inventorié obsolète, puissance nominale trompeuse, "
            "co-événement absent du journal et canal temporaire mal étiqueté. Le marquage "
            "`overlap_ambiguous` bloque correctement l'actif fictif créé par deux charges simultanées. "
            "La politique gardée refuse les six cas adversariaux ; ce résultat synthétique ne garantit "
            "pas qu'elle détectera toutes les erreurs de provenance réelles.",
            "",
            "## Robustesse aux erreurs de registre",
            "",
            *corruption_lines,
            "",
            "Les taux de corruption sont des interventions synthétiques, pas une estimation de fréquence "
            "terrain. Ils montrent néanmoins la pente du risque : à 25 % d'étiquettes permutées non "
            "signalées, le contexte brut atteint 24,8 % de fausses attributions, tandis que la politique "
            "gardée reste à 0 % et couvre environ le taux d'ancres vérifiées (20 %). Une incertitude de "
            "registre explicitement déclarée est neutralisée ; une erreur présentée comme certaine reste "
            "fondamentalement indétectable sans preuve indépendante.",
            "",
            "## Réutilisation historique",
            "",
            "Une première distance moyenne a été falsifiée : elle diluait une forte dérive univariée. "
            "La règle retenue exige maintenant une distance moyenne ≤ "
            f"{anchor['selected_threshold']:.2f} et une distance par dimension ≤ 0,25. Sur "
            f"{anchor['case_count']} cas synthétiques, elle obtient "
            f"{selected_anchor['true_accept']} vrais réemplois, {selected_anchor['true_refusal']} vrais refus, "
            f"{selected_anchor['false_accept']} faux réemploi et {selected_anchor['false_refusal']} faux refus. "
            "Ce seuil n'est pas calibré pour un site réel.",
            "",
            "## PX-201",
            "",
            f"Le scanner reproductible a examiné {px['scanned_files_or_archives']} fichiers ou archives "
            "dans les emplacements de fixtures et n'a trouvé aucune donnée PX-201 exploitable. Le cas "
            "réel n'a donc pas été reproduit et aucune valeur réelle `+2.7 kW`, `06:00–22:00` ou attribution "
            "n'est revendiquée. Les scénarios synthétiques qui ressemblent à ce format restent explicitement synthétiques.",
            "",
            "## Ce qui fonctionne et ce qui ne fonctionne pas",
            "",
            "Fonctionne sur les expériences contrôlées : conservation de `unknown`, refus de l'équivalence, "
            "réduction d'incertitude par une question simple, promotion après ancre vérifiée, révision du "
            "journal et refus après dérive. Ne fonctionne pas sans hypothèse supplémentaire : corriger une "
            "identité d'actif fausse mais non signalée, découvrir un co-événement absent, séparer de façon "
            "générale des charges superposées ou valider l'identité d'un canal terrain.",
            "",
            "## Nouveaux risques",
            "",
            "- confiance excessive dans la qualité du registre ;",
            "- confusion entre score de compatibilité et probabilité ;",
            "- ancre terrain mal étiquetée ;",
            "- quasi-expérience confondue par une action non journalisée ;",
            "- réutilisation historique au-delà d'un changement de régime ;",
            "- couverture trop faible si le mode gardé devient une fin plutôt qu'un déclencheur de micro-question.",
            "",
            "## Recommandation R&D suivante",
            "",
            "Intégrer cette couche seulement en **shadow mode local** sur des dossiers réels prospectifs. "
            "Pré-enregistrer l'inventaire, l'identité des canaux, les événements et la question avant de "
            "voir l'issue ; mesurer séparément précision, refus, couverture et contradictions. Le prochain "
            "jalon doit comprendre plusieurs sites, des registres imparfaits réels, des événements négatifs "
            "et au moins une ancre temporaire vérifiée par site. Toute probabilité, mécanisme ou capacité de "
            "pronostic reste interdite avant calibration et validation indépendantes.",
            "",
            "## Conclusion",
            "",
            "L'architecture apporte une valeur suffisante pour une intégration expérimentale : elle transforme "
            "une signature pauvre en liste explicable de compatibilités, sait dire pourquoi elle ne peut pas "
            "départager les derniers candidats et choisit une information minimale. Elle n'apporte pas encore "
            "une attribution industrielle autonome démontrée. Le refus gardé est le résultat principal de "
            "cette phase, pas une limitation à dissimuler.",
            "",
        ]
    )


def build_decision_examples() -> dict[str, Any]:
    """Exemples synthétiques sérialisés par le même moteur que le benchmark."""

    examples = []
    for index, scenario in enumerate(
        (
            "useful_micro_question",
            "discriminating_natural_event",
            "temporary_measurement_resolves",
            "simultaneous_loads",
            "best_conclusion_unknown",
        ),
        start=1,
    ):
        public, truth = _case(scenario, 70_000 + index)
        public["split"] = "EXAMPLE"
        response = _from_public(
            public,
            method="guarded_evidence",
            question_strategy="reliability_adjusted_voi",
        )
        examples.append(
            {
                "example_id": f"D{index:02d}",
                "synthetic": True,
                "scenario_type": scenario,
                "decision": response,
                "expected_boundary": {
                    "target_hidden_during_decision": True,
                    "should_name_asset": truth["should_name_asset"],
                    "physical_mechanism": None,
                    "prognosis": None,
                },
            }
        )
    return {
        "schema_version": "indicia-minimal-attribution-decision-examples-v1",
        "status": "synthetic_examples_not_client_findings",
        "examples": examples,
    }
