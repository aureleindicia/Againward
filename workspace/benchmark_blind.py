#!/usr/bin/env python3
"""Benchmark aveugle : l'étape de détection ne reçoit que les fichiers publics."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from energy_mvp.blind_suite import CASE_NAMES, generate_blind_case
from energy_mvp.io import load_data
from energy_mvp.signals import detect_candidate_events
from energy_mvp.toolbox import calculate_residuals
from energy_mvp.validation import validate_events


def _quantify(candidates: dict[str, Any], source: Path) -> list[dict[str, Any]]:
    loaded = load_data(source, interval_minutes=60, site_timezone="Europe/Paris")
    residuals = calculate_residuals(loaded.readings, candidates["baseline"])
    output = []
    for event in candidates["events"]:
        start = datetime.fromisoformat(event["start"])
        end = datetime.fromisoformat(event["end"])
        start_internal = (
            start.astimezone(timezone.utc).replace(tzinfo=None)
            if start.tzinfo is not None else start
        )
        end_internal = (
            end.astimezone(timezone.utc).replace(tzinfo=None)
            if end.tzinfo is not None else end
        )
        energy = sum(
            max(float(point["residual_kw"]), 0.0) * float(point["interval_hours"] or 0.0)
            for point in residuals
            if start_internal <= datetime.fromisoformat(point["timestamp"]) < end_internal
        )
        output.append({**event, "estimated_energy_impact": energy})
    return output


def main() -> int:
    public_results: list[dict[str, Any]] = []
    private_truths: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        public = root / "public"
        private = root / "private"
        public.mkdir()
        private.mkdir()
        for index, case_name in enumerate(CASE_NAMES):
            source = public / f"{case_name}.csv"
            intake = public / f"{case_name}.intake.json"
            truth = private / f"{case_name}.truth.json"
            generate_blind_case(case_name, source, intake, truth, seed=700 + index)

        # Phase aveugle : ce bloc n'ouvre jamais le dossier private.
        for case_name in CASE_NAMES:
            source = public / f"{case_name}.csv"
            loaded = load_data(
                source, interval_minutes=60, site_timezone="Europe/Paris"
            )
            try:
                candidates = detect_candidate_events(loaded)
                detections = _quantify(candidates, source)
                status = "completed"
                reason = None
            except ValueError as exc:
                detections = []
                status = "unavailable"
                reason = str(exc)
            public_results.append({
                "case_name": case_name,
                "status": status,
                "reason": reason,
                "detections": detections,
            })

        # Évaluation postérieure uniquement.
        for case_name in CASE_NAMES:
            private_truths[case_name] = json.loads(
                (private / f"{case_name}.truth.json").read_text(encoding="utf-8")
            )

    evaluated = []
    energy_errors = []
    for result in public_results:
        truth = private_truths[result["case_name"]]
        metrics = validate_events(truth["anomalies"], result["detections"], minimum_iou=0.25)
        truth_by_id = {item["anomaly_id"]: item for item in truth["anomalies"]}
        detected_by_id = {item["event_id"]: item for item in result["detections"]}
        for match in metrics["matches"]:
            expected = truth_by_id[match["injected_id"]]["expected_energy_impact"]
            estimated = detected_by_id[match["detected_id"]]["estimated_energy_impact"]
            if expected:
                energy_errors.append(abs(estimated - expected) / expected)
        evaluated.append({
            "case_name": result["case_name"],
            "legitimate_events": len(truth["legitimate_events"]),
            **{key: metrics[key] for key in (
                "injected_events", "detected_events", "true_positives", "false_positives",
                "false_negatives", "precision", "recall", "f1", "unmatched_injected",
                "unmatched_detected",
            )},
        })
    tp = sum(item["true_positives"] for item in evaluated)
    fp = sum(item["false_positives"] for item in evaluated)
    fn = sum(item["false_negatives"] for item in evaluated)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    comparison_path = Path("reports/blind_codex_comparison.json")
    if comparison_path.is_file():
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        codex_comparison = {
            "status": "measured_on_independent_six_case_subset",
            "artifact": str(comparison_path),
            "independent_sessions": comparison["design"]["independent_codex_sessions"],
            "public_cases": comparison["design"]["public_cases"],
            "python_only_same_subset": comparison["python_only_same_public_cases"],
            "codex_temporal_sessions": [
                {
                    "session_id": item["session_id"],
                    **item["temporal_detection"],
                }
                for item in comparison["python_plus_codex_sessions"]
            ],
            "caveat": (
                "Comparaison sur six cas et seeds figés distincts de la métrique globale "
                "quatorze cas; ne pas substituer un score à l'autre."
            ),
        }
    else:
        codex_comparison = {
            "status": "not_yet_measured_in_independent_sessions",
            "reason": "Aucune sortie Codex indépendante et aveugle n'a encore été fournie au harnais.",
        }
    payload = {
        "schema_version": 1,
        "validation_design": "generation_private_then_detection_public_then_evaluation",
        "generator_independent_from_demo_py": True,
        "python_only": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "mean_absolute_energy_error_ratio": (
                sum(energy_errors) / len(energy_errors) if energy_errors else None
            ),
        },
        "codex_comparison": codex_comparison,
        "cases": evaluated,
        "limitations": [
            "Les données restent synthétiques malgré un générateur indépendant.",
            "La pertinence métier des questions au-delà du contrat structuré n'est pas mesurée automatiquement.",
            "Les événements légitimes sont comptés comme faux positifs Python si un signal les couvre.",
        ],
    }
    Path("reports/validation_blind.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["python_only"], indent=2))
    print("Benchmark aveugle écrit: reports/validation_blind.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
