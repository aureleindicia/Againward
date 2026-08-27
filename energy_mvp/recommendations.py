from __future__ import annotations

from typing import Any, Iterable

from .investigation import InformationRequest


CAUSE_STATUSES = {"confirmed", "plausible_not_proven", "not_identified"}
ACTION_STATUSES = {"verification_only", "ready_for_controlled_action"}


def validate_operational_recommendation(payload: dict[str, Any]) -> None:
    """Valide une recommandation sans transformer une anomalie en cause ou économie."""

    text_fields = (
        "recommendation_id", "finding_id", "measured_anomaly", "owner_role",
        "verification_effort", "expected_if_hypothesis_true",
    )
    if any(not str(payload.get(name, "")).strip() for name in text_fields):
        raise ValueError("Une recommandation opérationnelle doit renseigner anomalie, responsable et effort.")
    impact = payload.get("observed_impact") or {}
    if not str(impact.get("period", "")).strip() or not str(
        impact.get("quantitative_source", "")
    ).strip():
        raise ValueError("L'impact observé doit citer sa période et sa source quantitative.")
    energy = impact.get("excess_energy_kwh")
    if not isinstance(energy, (int, float)) or energy < 0:
        raise ValueError("L'impact énergétique observé doit être un nombre non négatif.")
    cost = impact.get("associated_cost")
    if cost is not None and (not isinstance(cost, (int, float)) or cost < 0):
        raise ValueError("Le coût associé doit être absent ou non négatif.")
    confidence = payload.get("confidence") or {}
    if confidence.get("level") not in {"low", "medium", "high"} or not confidence.get("basis"):
        raise ValueError("La confiance exige un niveau et une justification.")
    causes = payload.get("plausible_causes") or []
    if not causes or any(
        not item.get("cause") or not isinstance(item.get("rank"), int) for item in causes
    ):
        raise ValueError("Les causes plausibles doivent être classées explicitement.")
    ranks = [item["rank"] for item in causes]
    if sorted(ranks) != list(range(1, len(ranks) + 1)):
        raise ValueError("Le classement des causes doit être continu à partir de 1.")
    cause_status = payload.get("physical_cause_status")
    action_status = payload.get("action_status")
    if cause_status not in CAUSE_STATUSES or action_status not in ACTION_STATUSES:
        raise ValueError("Statut de cause ou d'action non reconnu.")
    if cause_status != "confirmed" and action_status != "verification_only":
        raise ValueError("Une cause non prouvée ne peut déclencher qu'une vérification.")
    request = payload.get("next_verification") or {}
    InformationRequest(
        request_id=request["request_id"],
        request_type=request["request_type"],
        ask_client=request["ask_client"],
        why_useful=request["why_useful"],
        information_value=request["information_value"],
        hypotheses_distinguished=tuple(request["hypotheses_distinguished"]),
        responsible_role=request["responsible_role"],
        client_effort=request["client_effort"],
        effort_level=request["effort_level"],
        expected_if_true=request["expected_if_true"],
        priority=request.get("priority", 1),
    )
    after = payload.get("post_action_measurement") or {}
    for name in ("metric", "baseline_definition", "evaluation_window", "success_rule"):
        if not str(after.get(name, "")).strip():
            raise ValueError(f"Mesure après intervention incomplète: {name} est requis.")
    if payload.get("recoverable_saving") is not None and cause_status != "confirmed":
        raise ValueError("Une économie récupérable ne peut être publiée avec une cause non prouvée.")


def validate_recommendations(recommendations: Iterable[dict[str, Any]]) -> None:
    identifiers: set[str] = set()
    for payload in recommendations:
        validate_operational_recommendation(payload)
        identifier = payload["recommendation_id"]
        if identifier in identifiers:
            raise ValueError(f"Identifiant de recommandation dupliqué: {identifier}.")
        identifiers.add(identifier)
