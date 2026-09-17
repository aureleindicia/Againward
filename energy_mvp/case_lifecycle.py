from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .evidence_protocol import EvidenceQuerySession, validate_finding_provenance
from .investigation import next_information_request, validate_follow_up_logic
from .recommendations import validate_recommendations
from .client_lifecycle import (
    assert_workflow_action_allowed, close_clarification_budget, complete_resume,
    initialize_client_lifecycle, lifecycle_directory, mark_finalizable,
    publish_client_requests, record_canonical_answers, record_existing_data_exhaustion,
    validate_client_lifecycle_artifacts,
)
from .privacy import assert_case_privacy_cleared
from .artifact_store import case_mutation, read_json, write_json, artifact_sha256


DECISIONS = {
    "CONFIRME",
    "A_CONSERVER_AVEC_RESERVES",
    "INSUFFISAMMENT_ETAYE",
    "REJETE",
}
REVIEW_CHECKS = {
    "calculations",
    "data_quality",
    "baseline_robustness",
    "alternative_explanations",
    "causality",
    "annualization",
    "recoverable_saving",
    "double_counting",
}
REVIEW_CHECK_STATUSES = {"passed", "failed", "not_applicable"}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except FileNotFoundError as exc:
        raise ValueError(f"Fichier requis absent: {path}.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide dans {path}: {exc}.") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} doit contenir un objet JSON.")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def _sha256(path: Path) -> str:
    return artifact_sha256(path)


def _append_trace(case_directory: Path, action: str, details: dict[str, Any]) -> None:
    path = case_directory / "trace.json"
    payload = _read_json(path)
    entries = payload.setdefault("entries", [])
    if not isinstance(entries, list):
        raise ValueError("trace.json: entries doit être une liste.")
    entries.append({
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "action": action,
        **details,
    })
    _write_json(path, payload)


def validate_investigation_document(payload):
    from againward.domains.energy.review_policy import EnergyDeliveryPolicy
    return EnergyDeliveryPolicy().validate_investigation(payload)


def _question_candidates(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    seen: set[str] = set()
    for hypothesis in payload["hypotheses"]:
        request = next_information_request(hypothesis)
        if request is not None and request["request_id"] not in seen:
            seen.add(request["request_id"])
            yield {
                **request,
                "finding_id": hypothesis["hypothesis_id"],
                "origin": "uncertain_hypothesis",
            }
    for recommendation in payload.get("recommendations", []):
        if recommendation.get("action_status") != "verification_only":
            continue
        request = recommendation["next_verification"]
        if request["request_id"] in seen:
            continue
        seen.add(request["request_id"])
        yield {
            **request,
            "finding_id": recommendation["finding_id"],
            "origin": "unproven_physical_cause",
        }


@case_mutation
def publish_minimum_questions(
    case_directory: str | Path,
    *,
    investigation_name: str = "investigation.json",
) -> dict[str, Any]:
    """Adaptateur v1 vers la sélection globale canonique."""

    root = lifecycle_directory(case_directory)
    investigation_path = root / investigation_name
    investigation = _read_json(investigation_path)
    validate_investigation_document(investigation)
    candidates=[{**q,"related_hypothesis_ids":[q["finding_id"]],"related_finding_ids":[q["finding_id"]],
        "importance":"BLOCKING","effort":{"tres_faible":1,"faible":2,"modere":3}.get(q.get("effort_level"),2),
        "availability":.8,"reliability":.65} for q in _question_candidates(investigation)]
    publish_client_requests(root,candidates)
    payload=_read_json(root/"questions.json"); payload["investigation_sha256"]=_sha256(investigation_path); _write_json(root/"questions.json",payload)
    _append_trace(root, "publish_minimum_questions", {
        "investigation_sha256": payload["investigation_sha256"],
        "question_ids": [item["request_id"] for item in payload["questions"]],
    })
    return payload


@case_mutation
def record_client_answers(
    case_directory: str | Path,
    answers_path: str | Path,
) -> dict[str, Any]:
    """Adaptateur fichier v1 vers les réponses canoniques."""

    root = lifecycle_directory(case_directory)
    supplied = _read_json(Path(answers_path))
    answers = supplied.get("answers")
    if not isinstance(answers, list) or not answers:
        raise ValueError("Le fichier de réponses doit contenir une liste answers non vide.")
    now = datetime.now(timezone.utc).isoformat()
    result=record_canonical_answers(root,[{**x,"source_type":x.get("source_type","CLIENT_DECLARATION"),"provided_at_utc":x.get("provided_at_utc",now)} for x in answers])
    questions_payload=_read_json(root/"questions.json")
    _append_trace(root, "record_client_answers", {
        "answers_sha256": _sha256(Path(answers_path)),
        "request_ids": [x["request_id"] for x in result["recorded_answers"]],
    })
    return questions_payload


@case_mutation
def archive_answered_question_cycle(case_directory: str | Path) -> Path:
    """Archive un cycle entièrement répondu avant une nouvelle série de questions."""

    root = lifecycle_directory(case_directory)
    path = root / "questions.json"
    payload = _read_json(path)
    questions = payload.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("Aucun cycle de questions à archiver.")
    open_ids = [
        item.get("request_id") for item in questions if item.get("status") != "answered"
    ]
    if open_ids:
        raise ValueError(
            "Le cycle contient encore des questions ouvertes: " + ", ".join(open_ids) + "."
        )
    archive_directory = root / "question_cycles"
    archive_directory.mkdir(exist_ok=True)
    index = 1
    while (archive_directory / f"questions_cycle_{index:03d}.json").exists():
        index += 1
    target = archive_directory / f"questions_cycle_{index:03d}.json"
    _write_json(target, payload)
    payload.setdefault("cycle_history", []).append({"cycle": payload["questions"][0].get("cycle"), "questions": payload["questions"]})
    payload["questions"] = []
    payload["previous_cycle"] = str(target.relative_to(root))
    _write_json(path, payload)
    _append_trace(root, "archive_answered_question_cycle", {
        "archive": str(target.relative_to(root)),
        "archive_sha256": _sha256(target),
    })
    return target


def validate_adversarial_review(payload, investigation):
    from againward.domains.energy.review_policy import EnergyDeliveryPolicy
    return EnergyDeliveryPolicy().validate_review(payload, investigation)


def evaluate_delivery_gate(case_directory):
    from againward.core.delivery import evaluate_delivery_gate as evaluate
    from againward.domains.energy.review_policy import EnergyDeliveryPolicy
    return evaluate(case_directory, policy=EnergyDeliveryPolicy())
