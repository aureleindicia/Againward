from __future__ import annotations

import inspect

import pytest

import energy_mvp.physical_diagnostics as diagnostics
from energy_mvp.physical_diagnostics import (
    DiscriminatingMeasurement,
    describe_evidence_boundaries,
    load_all_physical_knowledge,
    physical_differential_template,
    rank_discriminating_measurements,
    validate_physical_differential,
    validate_epistemic_decision_semantics,
)


def _measurement(identifier: str, category: str, *, effort: str = "LOW") -> dict[str, object]:
    return DiscriminatingMeasurement(
        measurement_id=identifier,
        variable="variable physique mesurée",
        measurement_class=category,
        location="au niveau du service physique",
        timing="pendant deux régimes comparables",
        client_effort="relevé court",
        effort_level=effort,
        technician_required=False,
        risk_level="LOW",
        hypotheses_distinguished=("H_A", "H_B"),
        predictions_by_hypothesis={
            "H_A": "la variable augmente avec le signal énergétique",
            "H_B": "la variable reste stable malgré le signal énergétique",
        },
        limitations=("La synchronisation doit être vérifiée.",),
    ).to_dict()


def _differential() -> dict[str, object]:
    hypotheses = []
    for rank, cause in enumerate(
        (
            "mécanisme physique non répertorié dans les fiches",
            "demande de service légitime accrue",
            "artefact ou variable de procédé manquante",
        ),
        start=1,
    ):
        hypotheses.append({
            "rank": rank,
            "cause": cause,
            "mechanism": "Le mécanisme produit une prédiction observable distincte.",
            "supporting_evidence": ["Une mesure quantitative est compatible."],
            "contrary_evidence": ["Une contre-explication reste compatible."],
            "expected_observables": ["Un feedback physique doit évoluer si la piste est vraie."],
            "best_discriminating_measurement": _measurement(
                f"M_{rank}", "DIRECT_PHYSICAL_DISCRIMINATOR"
            ),
            "falsifier": "La prédiction ne se reproduit pas à service comparable.",
            "safety_constraints": ["Mesure non intrusive ou personne compétente."],
            "confidence": 0.3,
        })
    return {
        "schema_version": 1,
        "family": "motors_pumps_fans",
        "observation": "Une énergie spécifique a changé sur des régimes appariés.",
        "energy_chain": {
            "energy_input": "électricité",
            "equipment": "moteur et entraînement",
            "physical_service": "mouvement ou débit",
            "process_output": "sortie procédé",
            "unobserved_links": ["couple mécanique"],
        },
        "service_demand_assessment": {
            "status": "UNKNOWN",
            "evidence": [],
            "missing_variables": ["service utile réellement produit"],
        },
        "system_efficiency_assessment": {
            "status": "NOT_IDENTIFIABLE",
            "evidence": [],
            "evaluated_after_service_demand": True,
        },
        "command_feedback_assessment": {
            "command_variable": "ordre moteur",
            "feedback_variable": "courant et vitesse réels",
            "status": "UNKNOWN",
            "evidence": [],
        },
        "hypotheses": hypotheses,
    }


def test_all_family_knowledge_is_structured_but_non_decisional() -> None:
    knowledge = load_all_physical_knowledge()
    assert set(knowledge) == diagnostics.SYSTEM_FAMILIES
    serialized = repr(knowledge).casefold()
    assert "automatic_causal_conclusion" not in serialized
    assert "probability" not in serialized


def test_unlisted_cause_and_protocol_remain_valid() -> None:
    payload = _differential()
    validate_physical_differential(payload)
    known = repr(load_all_physical_knowledge()).casefold()
    assert payload["hypotheses"][0]["cause"].casefold() not in known


def test_unknown_service_demand_prevents_efficiency_claim_in_contract() -> None:
    payload = _differential()
    payload["system_efficiency_assessment"]["status"] = "CHANGED"
    with pytest.raises(ValueError, match="demande essentielle"):
        validate_physical_differential(payload)


def test_template_contains_no_preselected_hypothesis() -> None:
    template = physical_differential_template()
    assert template["hypotheses"] == []
    assert template["instructions"][-1].endswith("sequence.")


def test_information_value_is_consultative_and_overridable() -> None:
    direct = _measurement("direct", "DIRECT_PHYSICAL_DISCRIMINATOR")
    submeter = _measurement("submeter", "SUBMETERING", effort="HIGH")
    ranked = rank_discriminating_measurements([submeter, direct])
    assert ranked[0]["measurement_id"] == "direct"
    assert all(item["selected_for_next_action"] is None for item in ranked)
    assert all(item["automatic_causal_conclusion"] is None for item in ranked)

    overridden = rank_discriminating_measurements(
        [direct, submeter],
        analyst_override=["submeter", "direct"],
        override_reason="Le sous-compteur existe déjà et le test direct exige un arrêt impossible.",
    )
    assert overridden[0]["measurement_id"] == "submeter"
    assert overridden[0]["ranking_basis"] == "analyst_override"


def test_indistinguishable_causes_expose_boundaries_without_deciding_abstention() -> None:
    result = describe_evidence_boundaries(
        anomaly_status="UNKNOWN",
        essential_demand_available=False,
        essential_process_variable_available=False,
        hypotheses_distinguishable_with_current_evidence=False,
    )
    assert result["analyst_decision"] is None
    assert result["next_measurement_selected"] is None
    assert "essential_process_variable_missing" in result["unresolved_evidence_boundaries"]


def test_module_contains_no_automatic_diagnostic_or_recommendation_entrypoint() -> None:
    source = inspect.getsource(diagnostics)
    for forbidden in (
        "def diagnose_fault",
        "def choose_cause",
        "def recommend_action",
        "def select_best_hypothesis",
        "def automatic_physical_diagnosis",
    ):
        assert forbidden not in source




def test_measurement_rejects_non_boolean_technician_flag() -> None:
    payload = _measurement("strict_bool", "CONTROL_STATE")
    payload["technician_required"] = "false"
    with pytest.raises(ValueError, match="booléen"):
        diagnostics.measurement_from_dict(payload)


def _epistemic(decision: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "decision": decision,
        "abnormal_phenomenon_status": "CONFIRMED",
        "legitimate_operation_explains_observation": False,
        "physical_cause_distinguished": True,
        "decision_required_blocked": False,
        "data_quality_blocks_qualification": False,
        "evidence_summary": ["Une observation directement discriminante élimine les alternatives plausibles."],
        "remaining_competing_explanations": [],
    }
    payload.update(overrides)
    return payload


def test_sparse_but_discriminating_evidence_can_support_strong_claim() -> None:
    validate_epistemic_decision_semantics(_epistemic("CAUSE_CONFIRMED"))


def test_rich_evidence_with_competing_causes_requires_cause_uncertain_not_overclaim() -> None:
    validate_epistemic_decision_semantics(_epistemic(
        "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN",
        physical_cause_distinguished=False,
        remaining_competing_explanations=["Deux mécanismes restent compatibles avec les observations riches."],
    ))


def test_legitimate_operation_remains_normal_operation() -> None:
    validate_epistemic_decision_semantics(_epistemic(
        "NORMAL_OPERATION",
        abnormal_phenomenon_status="NOT_CONFIRMED",
        legitimate_operation_explains_observation=True,
        physical_cause_distinguished=False,
    ))


def test_insufficient_information_requires_a_decision_blocker() -> None:
    with pytest.raises(ValueError, match="bloque la décision"):
        validate_epistemic_decision_semantics(_epistemic("INSUFFICIENT_INFORMATION"))
