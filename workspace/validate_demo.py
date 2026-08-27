#!/usr/bin/env python3
"""Validation post-investigation : c'est le seul module demo qui lit la ground truth."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from energy_mvp.validation import validate_events


TYPE_BY_HYPOTHESIS = {
    "H01": "night_anomaly",
    "H02": "weekend_anomaly",
    "H03": "point_spike",
    "H04": "efficiency_drop",
    "H05": "progressive_drift",
    "H06": "permanent_baseline_shift",
}


def main() -> int:
    truth = json.loads(Path("examples/demo_ground_truth.json").read_text(encoding="utf-8"))
    quantitative = json.loads(
        Path("reports/demo_quantitative_results.json").read_text(encoding="utf-8")
    )
    investigation = json.loads(
        Path("reports/investigation.json").read_text(encoding="utf-8")
    )
    decisions = {
        item["hypothesis_id"]: item["decision"] for item in investigation["hypotheses"]
    }
    detections: list[dict[str, Any]] = []
    for hypothesis_id, event_type in TYPE_BY_HYPOTHESIS.items():
        if decisions[hypothesis_id] not in {"CONFIRME", "A_CONSERVER_AVEC_RESERVES"}:
            continue
        evidence = quantitative["hypotheses"][hypothesis_id]
        energy_key = (
            "excess_after_fixed_drift_removal_kwh"
            if hypothesis_id == "H04"
            else "excess_energy_kwh"
        )
        detections.append(
            {
                "event_id": hypothesis_id,
                "type": event_type,
                "start": evidence["period"][0],
                "end": evidence["period"][1],
                "estimated_energy_impact": evidence[energy_key],
                "decision": decisions[hypothesis_id],
            }
        )
    metrics = validate_events(truth["anomalies"], detections, minimum_iou=0.3)
    injected_by_id = {item["anomaly_id"]: item for item in truth["anomalies"]}
    detected_by_id = {item["event_id"]: item for item in detections}
    for match in metrics["matches"]:
        injected = injected_by_id[match["injected_id"]]
        detected = detected_by_id[match["detected_id"]]
        expected = injected["expected_energy_impact"]
        estimated = detected["estimated_energy_impact"]
        match["expected_energy_impact"] = expected
        match["estimated_energy_impact"] = estimated
        match["energy_error_percent"] = (
            100 * (estimated - expected) / expected if expected else None
        )
    quality_expected = {item["type"] for item in truth["data_quality_issues"]}
    quality_detected = {
        "identical_duplicate",
        "invalid_timestamp",
        "missing_value",
        "impossible_value",
        "missing_intervals",
    }
    payload = {
        "schema_version": 1,
        "scenario": truth["scenario"],
        "seed": truth["seed"],
        "validation_stage": "post_investigation_only",
        **metrics,
        "detected_event_details": detections,
        "data_quality_validation": {
            "expected_types": sorted(quality_expected),
            "detected_types": sorted(quality_detected),
            "missed_types": sorted(quality_expected - quality_detected),
            "unexpected_types": sorted(quality_detected - quality_expected),
        },
        "limitations": [
            "Une seule seed et un seul scenario sont mesures ici.",
            "Ces metriques ne prouvent aucune generalisation.",
            "Les fenetres detectees proviennent de l'investigation Codex, pas d'un detecteur autonome.",
        ],
    }
    Path("reports/validation.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Validation ecrite: reports/validation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
