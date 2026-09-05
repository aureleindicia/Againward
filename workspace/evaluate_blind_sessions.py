#!/usr/bin/env python3
"""Compare Python seul et plusieurs reviews Codex, après gel de la phase aveugle."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

from energy_mvp.blind_review import validate_blind_session_review
from energy_mvp.validation import temporal_iou, validate_events


RETAINED = {"CONFIRME", "A_CONSERVER_AVEC_RESERVES"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _aggregate(items: list[dict[str, Any]]) -> dict[str, Any]:
    tp = sum(item["true_positives"] for item in items)
    fp = sum(item["false_positives"] for item in items)
    fn = sum(item["false_negatives"] for item in items)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
    }


def freeze_public_phase(
    public_root: Path, session_review_paths: list[Path]
) -> dict[str, Any]:
    """Ne reçoit aucun chemin privé : valide et fige uniquement les sorties publiques."""

    case_names = sorted(path.name for path in public_root.iterdir() if path.is_dir())
    python_events: dict[str, list[dict[str, Any]]] = {}
    public_case_hashes: dict[str, dict[str, str]] = {}
    for name in case_names:
        payload = json.loads(
            (public_root / name / "candidate_signals.json").read_text(encoding="utf-8")
        )
        python_events[name] = payload.get("events", [])
        public_case_hashes[name] = {
            filename: _sha256(public_root / name / filename)
            for filename in (
                "input.csv", "intake.json", "candidate_signals.json",
                "investigation_state.json",
            )
        }
    sessions = []
    for path in session_review_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_blind_session_review(payload, public_root)
        sessions.append({
            "sha256": _sha256(path),
            "payload": payload,
        })
    return {
        "case_names": case_names,
        "python_events": python_events,
        "public_case_hashes": public_case_hashes,
        "sessions": sessions,
    }


def _session_events(session: dict[str, Any], case_name: str) -> list[dict[str, Any]]:
    case = next(item for item in session["cases"] if item["case_name"] == case_name)
    return [
        {
            "event_id": hypothesis["hypothesis_id"],
            "type": hypothesis["type"],
            "start": hypothesis["start"],
            "end": hypothesis["end"],
        }
        for hypothesis in case["hypotheses"]
        if hypothesis["decision"] in RETAINED
    ]


def _status(session: dict[str, Any], case_name: str) -> str:
    case = next(item for item in session["cases"] if item["case_name"] == case_name)
    decisions = {item["decision"] for item in case["hypotheses"]}
    if "CONFIRME" in decisions:
        return "confirmed"
    if "A_CONSERVER_AVEC_RESERVES" in decisions:
        return "reserved"
    return "not_retained"


def _pairwise_stability(
    sessions: list[dict[str, Any]], case_names: list[str]
) -> dict[str, Any]:
    event_f1: list[float] = []
    case_agreement: list[float] = []
    pairs = []
    for first, second in combinations(sessions, 2):
        metrics = []
        equal = 0
        for case_name in case_names:
            first_events = _session_events(first, case_name)
            second_events = _session_events(second, case_name)
            injected = [
                {**item, "anomaly_id": item["event_id"]} for item in first_events
            ]
            metrics.append(validate_events(
                injected, second_events, minimum_iou=0.25, require_same_type=False
            ))
            equal += _status(first, case_name) == _status(second, case_name)
        aggregate = _aggregate(metrics)
        agreement = equal / len(case_names) if case_names else 1.0
        event_f1.append(aggregate["f1"])
        case_agreement.append(agreement)
        pairs.append({
            "sessions": [first["session_id"], second["session_id"]],
            "retained_event_temporal_f1": aggregate["f1"],
            "exact_case_disposition_agreement": agreement,
        })
    return {
        "pairs": pairs,
        "mean_retained_event_temporal_f1": (
            sum(event_f1) / len(event_f1) if event_f1 else None
        ),
        "mean_exact_case_disposition_agreement": (
            sum(case_agreement) / len(case_agreement) if case_agreement else None
        ),
    }


def evaluate_after_blind_phase(
    frozen: dict[str, Any], private_truth_root: Path
) -> dict[str, Any]:
    """Cette fonction est la première à ouvrir les vérités, après validation des reviews."""

    truths = {
        name: json.loads((private_truth_root / f"{name}.json").read_text(encoding="utf-8"))
        for name in frozen["case_names"]
    }
    python_case_metrics = []
    for name in frozen["case_names"]:
        python_case_metrics.append(validate_events(
            truths[name]["anomalies"], frozen["python_events"][name],
            minimum_iou=0.25, require_same_type=True,
        ))
    session_results = []
    for frozen_session in frozen["sessions"]:
        session = frozen_session["payload"]
        temporal_metrics = []
        exact_type_metrics = []
        legitimate_total = 0
        legitimate_overlaps = 0
        duplicate_pairs = 0
        requests = []
        retained_cases = 0
        retained_cases_with_verification = 0
        case_metrics = []
        for name in frozen["case_names"]:
            truth = truths[name]
            retained = _session_events(session, name)
            temporal = validate_events(
                truth["anomalies"], retained, minimum_iou=0.25, require_same_type=False
            )
            exact = validate_events(
                truth["anomalies"], retained, minimum_iou=0.25, require_same_type=True
            )
            temporal_metrics.append(temporal)
            exact_type_metrics.append(exact)
            legitimate_total += len(truth["legitimate_events"])
            legitimate_overlaps += sum(
                temporal_iou(legitimate, event) >= 0.25
                for legitimate in truth["legitimate_events"] for event in retained
            )
            duplicate_pairs += sum(
                temporal_iou(first, second) >= 0.25
                for first, second in combinations(retained, 2)
            )
            case = next(item for item in session["cases"] if item["case_name"] == name)
            case_requests = [
                request
                for hypothesis in case["hypotheses"]
                for request in hypothesis.get("follow_up_requests", [])
            ]
            requests.extend(case_requests)
            if retained:
                retained_cases += 1
                retained_cases_with_verification += bool(case_requests)
            case_metrics.append({
                "case_name": name,
                "retained_events": len(retained),
                "temporal_true_positives": temporal["true_positives"],
                "temporal_false_positives": temporal["false_positives"],
                "temporal_false_negatives": temporal["false_negatives"],
                "disposition": _status(session, name),
            })
        session_results.append({
            "session_id": session["session_id"],
            "review_sha256": frozen_session["sha256"],
            "ground_truth_accessed_declared": session["ground_truth_accessed"],
            "temporal_detection": _aggregate(temporal_metrics),
            "exact_free_text_type_detection": _aggregate(exact_type_metrics),
            "legitimate_events": legitimate_total,
            "legitimate_events_retained_as_anomaly": legitimate_overlaps,
            "overlapping_retained_pairs": duplicate_pairs,
            "follow_up_requests": len(requests),
            "effort_levels": dict(Counter(item["effort_level"] for item in requests)),
            "request_contract_validated": True,
            "retained_cases_with_next_verification": retained_cases_with_verification,
            "retained_cases": retained_cases,
            "next_verification_coverage": (
                retained_cases_with_verification / retained_cases if retained_cases else None
            ),
            "cases": case_metrics,
        })
    public_sessions = [
        {"session_id": item["payload"]["session_id"], **item["payload"]}
        for item in frozen["sessions"]
    ]
    stability = _pairwise_stability(public_sessions, frozen["case_names"])
    python_metrics = _aggregate(python_case_metrics)
    codex_temporal = [item["temporal_detection"] for item in session_results]
    return {
        "schema_version": 1,
        "design": {
            "order": "public_outputs_validated_and_hashed_before_private_truth_opened",
            "public_cases": len(frozen["case_names"]),
            "independent_codex_sessions": len(session_results),
            "ground_truth_forbidden_during_sessions": True,
            "public_case_hashes": frozen["public_case_hashes"],
        },
        "python_only_same_public_cases": python_metrics,
        "python_plus_codex_sessions": session_results,
        "stability": stability,
        "comparison": {
            "mean_codex_temporal_precision": sum(
                item["precision"] for item in codex_temporal
            ) / len(codex_temporal),
            "mean_codex_temporal_recall": sum(
                item["recall"] for item in codex_temporal
            ) / len(codex_temporal),
            "python_false_positives": python_metrics["false_positives"],
            "mean_codex_false_positives": sum(
                item["false_positives"] for item in codex_temporal
            ) / len(codex_temporal),
            "interpretation": (
                "Mesure limitée à six cas synthétiques indépendants de la démo. "
                "Le score temporel accepte les taxonomies ad hoc de Codex; le score de type exact "
                "est publié séparément et ne doit pas être masqué."
            ),
        },
        "unmeasured": [
            "pertinence métier des questions au-delà de la conformité de leur contrat",
            "qualité des recommandations opérationnelles, non demandées dans ce protocole",
            "quantification Codex standardisée des kWh, absente du schéma de session",
            "performance sur données réelles client",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", help="Racine contenant public/, private_truth/ et session_N/")
    parser.add_argument("--output", default="reports/blind_codex_comparison.json")
    parser.add_argument(
        "--reviews-dir",
        help="Dossier des reviews figées; par défaut utilise root/session_*/review.json",
    )
    args = parser.parse_args(argv)
    root = Path(args.root)
    reviews = (
        sorted(Path(args.reviews_dir).glob("*.json"))
        if args.reviews_dir else sorted(root.glob("session_*/review.json"))
    )
    if len(reviews) < 2:
        raise ValueError("Au moins deux sessions Codex indépendantes sont requises.")
    frozen = freeze_public_phase(root / "public", reviews)
    result = evaluate_after_blind_phase(frozen, root / "private_truth")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "python_only": result["python_only_same_public_cases"],
        "codex_sessions": [
            {"session_id": item["session_id"], **item["temporal_detection"]}
            for item in result["python_plus_codex_sessions"]
        ],
        "stability": result["stability"],
    }, ensure_ascii=False, indent=2))
    print(f"Comparaison écrite: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
