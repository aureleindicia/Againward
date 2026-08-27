from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def temporal_iou(first: dict[str, Any], second: dict[str, Any]) -> float:
    first_start, first_end = _timestamp(first["start"]), _timestamp(first["end"])
    second_start, second_end = _timestamp(second["start"]), _timestamp(second["end"])
    if first_end <= first_start or second_end <= second_start:
        raise ValueError("Un evenement doit avoir une duree strictement positive.")
    overlap = max(
        0.0,
        (min(first_end, second_end) - max(first_start, second_start)).total_seconds(),
    )
    union = (
        max(first_end, second_end) - min(first_start, second_start)
    ).total_seconds()
    return overlap / union if union > 0 else 0.0


def validate_events(
    injected_events: Sequence[dict[str, Any]],
    detected_events: Sequence[dict[str, Any]],
    *,
    minimum_iou: float = 0.3,
    require_same_type: bool = True,
) -> dict[str, Any]:
    """Apparie des evenements temporels une seule fois, jamais des lignes individuelles."""

    if not 0 < minimum_iou <= 1:
        raise ValueError("minimum_iou doit etre compris dans ]0, 1].")
    candidates = []
    for injected_index, injected in enumerate(injected_events):
        for detected_index, detected in enumerate(detected_events):
            if require_same_type and injected.get("type") != detected.get("type"):
                continue
            score = temporal_iou(injected, detected)
            if score >= minimum_iou:
                candidates.append((score, injected_index, detected_index))
    candidates.sort(reverse=True)
    used_injected: set[int] = set()
    used_detected: set[int] = set()
    matches = []
    for score, injected_index, detected_index in candidates:
        if injected_index in used_injected or detected_index in used_detected:
            continue
        used_injected.add(injected_index)
        used_detected.add(detected_index)
        injected = injected_events[injected_index]
        detected = detected_events[detected_index]
        matches.append(
            {
                "injected_id": injected.get("anomaly_id"),
                "detected_id": detected.get("event_id"),
                "type": injected.get("type"),
                "temporal_iou": score,
            }
        )
    true_positives = len(matches)
    false_positives = len(detected_events) - true_positives
    false_negatives = len(injected_events) - true_positives
    precision = (
        true_positives / len(detected_events) if detected_events else float(not injected_events)
    )
    recall = true_positives / len(injected_events) if injected_events else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "injected_events": len(injected_events),
        "detected_events": len(detected_events),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "minimum_temporal_iou": minimum_iou,
        "matches": matches,
        "unmatched_injected": [
            event.get("anomaly_id")
            for index, event in enumerate(injected_events)
            if index not in used_injected
        ],
        "unmatched_detected": [
            event.get("event_id")
            for index, event in enumerate(detected_events)
            if index not in used_detected
        ],
    }
