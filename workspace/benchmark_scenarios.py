#!/usr/bin/env python3
"""Mesure les signaux candidats sur plusieurs profils, seeds et cas sans anomalie."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from energy_mvp.demo import SCENARIOS, generate_demo
from energy_mvp.io import load_data
from energy_mvp.signals import detect_candidate_events
from energy_mvp.validation import validate_events


def main() -> int:
    seeds = (1, 7, 42)
    results = []
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for scenario in sorted(SCENARIOS):
            cases = [(seed, True) for seed in seeds] + [(101, False)]
            for seed, anomalies_enabled in cases:
                stem = f"{scenario}-{seed}-{'events' if anomalies_enabled else 'normal'}"
                csv_path = root / f"{stem}.csv"
                truth_path = root / f"{stem}.json"
                truth = generate_demo(
                    csv_path,
                    truth_path,
                    days=120,
                    seed=seed,
                    scenario_name=scenario,
                    include_data_issues=True,
                    include_anomalies=anomalies_enabled,
                )
                case_started = time.perf_counter()
                candidates = detect_candidate_events(load_data(csv_path))
                metrics = validate_events(
                    truth["anomalies"], candidates["events"], minimum_iou=0.3
                )
                results.append(
                    {
                        "scenario": scenario,
                        "seed": seed,
                        "anomalies_enabled": anomalies_enabled,
                        "rows": truth["written_rows"],
                        "runtime_seconds": time.perf_counter() - case_started,
                        **{
                            key: metrics[key]
                            for key in (
                                "injected_events", "detected_events", "true_positives",
                                "false_positives", "false_negatives", "precision", "recall", "f1",
                            )
                        },
                        "detected_types": [item["type"] for item in candidates["events"]],
                        "unmatched_injected": metrics["unmatched_injected"],
                    }
                )
    true_positives = sum(item["true_positives"] for item in results)
    false_positives = sum(item["false_positives"] for item in results)
    false_negatives = sum(item["false_negatives"] for item in results)
    precision = true_positives / (true_positives + false_positives) if true_positives + false_positives else 1.0
    recall = true_positives / (true_positives + false_negatives) if true_positives + false_negatives else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    normal_cases = [item for item in results if not item["anomalies_enabled"]]
    payload = {
        "schema_version": 1,
        "validation_target": "automatic_candidate_signals_not_confirmed_opportunities",
        "scenarios": sorted(SCENARIOS),
        "event_seeds": list(seeds),
        "normal_case_seed": 101,
        "cases": len(results),
        "total_rows": sum(item["rows"] for item in results),
        "runtime_seconds": time.perf_counter() - started,
        "micro_metrics": {
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
        "normal_cases": {
            "cases": len(normal_cases),
            "false_positive_events": sum(item["false_positives"] for item in normal_cases),
            "cases_without_false_positive": sum(
                item["false_positives"] == 0 for item in normal_cases
            ),
        },
        "results": results,
        "limitations": [
            "Les dates et amplitudes injectees sont communes aux seeds de cette version.",
            "Les sorties sont des signaux candidats ; Codex doit encore les falsifier.",
            "La matrice synthetique ne remplace pas une validation sur des procedes varies."
        ],
    }
    Path("reports/validation_scenarios.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Validation multi-scenarios ecrite: reports/validation_scenarios.json")
    print(json.dumps({
        "cases": payload["cases"],
        "total_rows": payload["total_rows"],
        "runtime_seconds": payload["runtime_seconds"],
        "micro_metrics": payload["micro_metrics"],
        "normal_cases": payload["normal_cases"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
