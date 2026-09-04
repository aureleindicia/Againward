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
)


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
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Fichier requis absent: {path}.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide dans {path}: {exc}.") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} doit contenir un objet JSON.")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def validate_investigation_document(payload: dict[str, Any]) -> None:
    """Vérifie la complétude méthodologique sans décider à la place de Codex."""

    if payload.get("ground_truth_used") is not False:
        raise ValueError("investigation.json doit déclarer ground_truth_used=false.")
    hypotheses = payload.get("hypotheses")
    if not isinstance(hypotheses, list):
        raise ValueError("investigation.json: hypotheses doit être une liste.")
    identifiers: set[str] = set()
    evidence_plane_enabled = bool(payload.get("evidence_plane_session"))
    for hypothesis in hypotheses:
        identifier = hypothesis.get("hypothesis_id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in identifiers:
            raise ValueError("Identifiant d'hypothèse absent ou dupliqué.")
        identifiers.add(identifier)
        for field in ("observation", "hypothesis", "best_reason_false"):
            if not str(hypothesis.get(field, "")).strip():
                raise ValueError(f"{identifier}: {field} est requis.")
        tests = hypothesis.get("tests_requested")
        if not isinstance(tests, list) or not tests or any(
            not str(item).strip() for item in tests
        ):
            raise ValueError(f"{identifier}: au moins un test explicite est requis.")
        results = hypothesis.get("results")
        if not isinstance(results, dict) or not results:
            raise ValueError(f"{identifier}: un résultat quantifié ou une limite testée est requis.")
        if not payload.get("quantitative_source") and not results.get("quantitative_source"):
            raise ValueError(
                f"{identifier}: la source Python des résultats doit être référencée."
            )
        alternatives = hypothesis.get("alternative_explanations")
        if not isinstance(alternatives, list) or not alternatives:
            raise ValueError(f"{identifier}: une contre-explication au minimum est requise.")
        if hypothesis.get("decision") not in DECISIONS:
            raise ValueError(f"{identifier}: décision finale absente ou inconnue.")
        confidence = hypothesis.get("confidence")
        if not isinstance(confidence, dict) or not confidence:
            raise ValueError(f"{identifier}: confiance non justifiée.")
        if not str(hypothesis.get("physical_cause_status", "")).strip():
            raise ValueError(f"{identifier}: statut de cause physique absent.")
        if evidence_plane_enabled:
            query_ids = hypothesis.get("evidence_query_ids", [])
            handles = hypothesis.get("evidence_handles", [])
            if not isinstance(query_ids, list) or any(
                not isinstance(item, str) or not item.strip() for item in query_ids
            ):
                raise ValueError(f"{identifier}: evidence_query_ids est invalide.")
            if not isinstance(handles, list) or any(
                not isinstance(item, str) or not item.strip() for item in handles
            ):
                raise ValueError(f"{identifier}: evidence_handles est invalide.")
            if hypothesis.get("decision") in {"CONFIRME", "A_CONSERVER_AVEC_RESERVES"}:
                if not query_ids or not handles:
                    raise ValueError(
                        f"{identifier}: une conclusion conservée exige des preuves Evidence Plane."
                    )
    validate_follow_up_logic(hypotheses)
    recommendations = payload.get("recommendations", [])
    if not isinstance(recommendations, list):
        raise ValueError("investigation.json: recommendations doit être une liste.")
    validate_recommendations(recommendations)


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


def validate_adversarial_review(
    payload: dict[str, Any], investigation: dict[str, Any]
) -> None:
    if payload.get("ground_truth_used") is not False:
        raise ValueError("review.json doit déclarer ground_truth_used=false.")
    reviews = payload.get("reviewed_hypotheses")
    if not isinstance(reviews, list):
        raise ValueError("review.json: reviewed_hypotheses doit être une liste.")
    required_ids = {
        item["hypothesis_id"] for item in investigation["hypotheses"]
        if item["decision"] != "REJETE"
    }
    investigation_decisions = {
        item["hypothesis_id"]: item["decision"] for item in investigation["hypotheses"]
    }
    reviewed_ids: set[str] = set()
    for review in reviews:
        identifier = review.get("hypothesis_id")
        if identifier in reviewed_ids or identifier not in required_ids:
            raise ValueError(f"Review absente, dupliquée ou inconnue: {identifier}.")
        reviewed_ids.add(identifier)
        if not str(review.get("best_reason_false", "")).strip():
            raise ValueError(f"{identifier}: meilleure raison d'être faux absente.")
        if review.get("final_decision") not in DECISIONS:
            raise ValueError(f"{identifier}: décision après review absente.")
        if review["final_decision"] != investigation_decisions[identifier]:
            raise ValueError(
                f"{identifier}: investigation.json doit être révisé pour refléter la décision "
                "de la review avant livraison."
            )
        checks = review.get("checks")
        if not isinstance(checks, dict) or set(checks) != REVIEW_CHECKS:
            raise ValueError(f"{identifier}: les huit contrôles adversariaux sont requis.")
        failed = False
        for name, check in checks.items():
            if not isinstance(check, dict) or check.get("status") not in REVIEW_CHECK_STATUSES:
                raise ValueError(f"{identifier}/{name}: statut de contrôle invalide.")
            if not str(check.get("evidence", "")).strip():
                raise ValueError(f"{identifier}/{name}: preuve ou justification absente.")
            failed = failed or check["status"] == "failed"
        if failed and review["final_decision"] == "CONFIRME":
            raise ValueError(f"{identifier}: une review échouée ne peut rester CONFIRME.")
    if reviewed_ids != required_ids:
        missing = sorted(required_ids - reviewed_ids)
        raise ValueError(f"Review adversariale manquante pour: {', '.join(missing)}.")


def evaluate_delivery_gate(case_directory: str | Path) -> dict[str, Any]:
    """Évalue la livrabilité; ne crée jamais une approbation humaine."""

    root = lifecycle_directory(case_directory)
    reasons: list[str] = []
    lifecycle_path = root / "investigation_state.json"
    lifecycle_state = None
    if lifecycle_path.exists():
        lifecycle_payload = _read_json(lifecycle_path)
        lifecycle_state = lifecycle_payload.get("client_lifecycle")
        if lifecycle_state is not None:
            if not isinstance(lifecycle_state, dict): reasons.append("Cycle client canonique invalide.")
            elif lifecycle_state.get("state") not in {"FINALIZABLE", "DELIVERABLE"}: reasons.append(f"Cycle client non finalisable: état {lifecycle_state.get('state','inconnu')}.")
            if isinstance(lifecycle_state,dict) and lifecycle_state.get("blocking_request_ids"): reasons.append("Des demandes BLOCKING restent ouvertes.")
    required = ("investigation.json", "review.json", "report.md", "human_review.json")
    for name in required:
        if not (root / name).is_file():
            reasons.append(f"Fichier requis absent: {name}.")
    investigation: dict[str, Any] | None = None
    if (root / "investigation.json").is_file():
        try:
            investigation = _read_json(root / "investigation.json")
            validate_investigation_document(investigation)
        except ValueError as exc:
            reasons.append(str(exc))
    if investigation is not None and (root / "review.json").is_file():
        try:
            validate_adversarial_review(_read_json(root / "review.json"), investigation)
        except ValueError as exc:
            reasons.append(str(exc))
    if (root / "report.md").is_file() and not (root / "report.md").read_text(
        encoding="utf-8"
    ).strip():
        reasons.append("report.md est vide.")
    if (root / "human_review.json").is_file():
        try:
            human = _read_json(root / "human_review.json")
            if human.get("status") != "approved" or human.get("approved_for_delivery") is not True:
                reasons.append("La revue humaine n'approuve pas encore la livraison.")
            for field in ("reviewer_role", "reviewed_at_utc"):
                if not str(human.get(field, "")).strip():
                    reasons.append(f"Revue humaine incomplète: {field} absent.")
        except ValueError as exc:
            reasons.append(str(exc))
    evidence_artifacts: tuple[str, ...] = ()
    if (root / "evidence_query_session.json").is_file():
        evidence_artifacts = ("evidence_query_session.json", "agent_findings.json")
        if not (root / "agent_findings.json").is_file():
            reasons.append(
                "Fichier requis absent pour le chemin Evidence Plane: agent_findings.json."
            )
        else:
            try:
                session = EvidenceQuerySession.from_dict(
                    _read_json(root / "evidence_query_session.json")
                )
                validate_finding_provenance(
                    _read_json(root / "agent_findings.json"), session
                )
            except ValueError as exc:
                reasons.append(str(exc))
    payload = {
        "schema_version": 1,
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "ready_for_delivery" if not reasons else "blocked",
        "ready_for_delivery": not reasons,
        "blocking_reasons": reasons,
        "artifact_hashes": {
            name: _sha256(root / name)
            for name in required + evidence_artifacts if (root / name).is_file()
        },
    }
    _write_json(root / "delivery_gate.json", payload)
    if not reasons and lifecycle_state is not None:
        lifecycle_payload=_read_json(lifecycle_path); lifecycle_payload["client_lifecycle"]["state"]="DELIVERABLE"
        lifecycle_payload["client_lifecycle"]["history"].append({"at_utc":payload["evaluated_at_utc"],"action":"marked_deliverable"}); _write_json(lifecycle_path,lifecycle_payload)
    _append_trace(root, "evaluate_delivery_gate", {
        "status": payload["status"],
        "blocking_reasons": reasons,
    })
    return payload
