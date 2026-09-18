"""Reusable methodological review; domain validators supply evidence policy."""
from __future__ import annotations
from typing import Any
from .investigation import validate_follow_up_logic

DECISIONS = {
    "CONFIRME",
    "A_CONSERVER_AVEC_RESERVES",
    "INSUFFISAMMENT_ETAYE",
    "REJETE",
}
REVIEW_CHECK_STATUSES = {"passed", "failed", "not_applicable"}


def validate_investigation_document(payload: dict[str, Any], *, hypothesis_validator=None, recommendation_validator=None) -> None:
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
        if hypothesis_validator is not None:
            hypothesis_validator(hypothesis)
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
    if recommendation_validator is not None:
        recommendation_validator(recommendations)


def validate_adversarial_review(
    payload: dict[str, Any], investigation: dict[str, Any], *, required_checks: set[str]
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
        if not isinstance(checks, dict) or set(checks) != required_checks:
            raise ValueError(f"{identifier}: les contrôles adversariaux du domaine sont requis.")
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
