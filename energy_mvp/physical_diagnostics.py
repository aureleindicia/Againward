from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


SYSTEM_FAMILIES = frozenset({
    "refrigeration",
    "thermal_ovens",
    "compressed_air",
    "motors_pumps_fans",
    "laundry_hot_water_steam",
    "hvac",
})

INFORMATION_VALUE_CLASSES = (
    "DIRECT_PHYSICAL_DISCRIMINATOR",
    "PROCESS_DISCRIMINATOR",
    "CONTROL_STATE",
    "MAINTENANCE_EVIDENCE",
    "SUBMETERING",
    "GENERIC_CONTEXT",
)

EFFORT_LEVELS = frozenset({"VERY_LOW", "LOW", "MODERATE", "HIGH"})
RISK_LEVELS = frozenset({"NEGLIGIBLE", "LOW", "MODERATE", "HIGH"})
SERVICE_DEMAND_STATUSES = frozenset({"CHANGED", "UNCHANGED", "UNKNOWN", "NOT_APPLICABLE"})
EFFICIENCY_STATUSES = frozenset({"CHANGED", "UNCHANGED", "UNKNOWN", "NOT_IDENTIFIABLE"})
COMMAND_FEEDBACK_STATUSES = frozenset({"CONSISTENT", "MISMATCHED", "UNKNOWN", "NOT_APPLICABLE"})
BENCHMARK_DECISIONS = frozenset({
    "NORMAL_OPERATION", "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "CAUSE_PROBABLE",
    "CAUSE_CONFIRMED", "INSUFFICIENT_INFORMATION", "DATA_QUALITY_BLOCKER",
})

_INFORMATION_VALUE_SCORES = {
    "DIRECT_PHYSICAL_DISCRIMINATOR": 60,
    "PROCESS_DISCRIMINATOR": 52,
    "CONTROL_STATE": 44,
    "MAINTENANCE_EVIDENCE": 32,
    "SUBMETERING": 24,
    "GENERIC_CONTEXT": 12,
}
_EFFORT_SCORES = {"VERY_LOW": 12, "LOW": 8, "MODERATE": 2, "HIGH": -8}
_RISK_PENALTIES = {"NEGLIGIBLE": 0, "LOW": 2, "MODERATE": 10, "HIGH": 25}


def _required_text(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} doit être une chaîne non vide.")
    return value.strip()


def _text_list(value: Any, *, field: str, minimum: int = 0) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{field} doit être une liste de chaînes valide.")
    return [item.strip() for item in value]


@dataclass(frozen=True, slots=True)
class DiscriminatingMeasurement:
    """Mesure candidate qui sépare des hypothèses sans décider laquelle est vraie."""

    measurement_id: str
    variable: str
    measurement_class: str
    location: str
    timing: str
    client_effort: str
    effort_level: str
    technician_required: bool
    risk_level: str
    hypotheses_distinguished: tuple[str, ...]
    predictions_by_hypothesis: Mapping[str, str]
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in ("measurement_id", "variable", "location", "timing", "client_effort"):
            _required_text(getattr(self, field), field=field)
        if self.measurement_class not in INFORMATION_VALUE_CLASSES:
            raise ValueError(f"Classe de mesure inconnue: {self.measurement_class}.")
        if self.effort_level not in EFFORT_LEVELS:
            raise ValueError(f"Effort inconnu: {self.effort_level}.")
        if self.risk_level not in RISK_LEVELS:
            raise ValueError(f"Risque inconnu: {self.risk_level}.")
        if len(self.hypotheses_distinguished) < 2:
            raise ValueError("Une mesure discriminante doit séparer au moins deux hypothèses.")
        if set(self.hypotheses_distinguished) - set(self.predictions_by_hypothesis):
            raise ValueError("Chaque hypothèse départagée exige une prédiction observable.")
        if any(not str(value).strip() for value in self.predictions_by_hypothesis.values()):
            raise ValueError("Les prédictions observables doivent être explicites.")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["hypotheses_distinguished"] = list(self.hypotheses_distinguished)
        payload["predictions_by_hypothesis"] = dict(self.predictions_by_hypothesis)
        payload["limitations"] = list(self.limitations)
        return payload


def measurement_from_dict(payload: Mapping[str, Any]) -> DiscriminatingMeasurement:
    technician_required = payload.get("technician_required")
    if not isinstance(technician_required, bool):
        raise ValueError("technician_required doit être booléen.")
    return DiscriminatingMeasurement(
        measurement_id=str(payload.get("measurement_id", "")),
        variable=str(payload.get("variable", "")),
        measurement_class=str(payload.get("measurement_class", "")),
        location=str(payload.get("location", "")),
        timing=str(payload.get("timing", "")),
        client_effort=str(payload.get("client_effort", "")),
        effort_level=str(payload.get("effort_level", "")),
        technician_required=technician_required,
        risk_level=str(payload.get("risk_level", "")),
        hypotheses_distinguished=tuple(payload.get("hypotheses_distinguished", ())),
        predictions_by_hypothesis=dict(payload.get("predictions_by_hypothesis", {})),
        limitations=tuple(payload.get("limitations", ())),
    )


def rank_discriminating_measurements(
    measurements: Sequence[DiscriminatingMeasurement | Mapping[str, Any]],
    *,
    analyst_override: Sequence[str] | None = None,
    override_reason: str | None = None,
) -> list[dict[str, Any]]:
    """Décrit un ordre consultatif de valeur d information, sans choisir la suite.

    Le classement par défaut favorise une grandeur physique ou procédé directe, puis
    pénalise effort, technicien et risque. Codex peut imposer un autre ordre lorsqu'un
    contexte de site le justifie, ignorer entièrement cet ordre ou proposer une mesure
    absente de la liste. La sortie ne sélectionne aucune question ni action.
    """

    parsed = [
        item if isinstance(item, DiscriminatingMeasurement) else measurement_from_dict(item)
        for item in measurements
    ]
    identifiers = [item.measurement_id for item in parsed]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Les identifiants de mesure doivent être uniques.")
    if analyst_override is not None:
        if set(analyst_override) != set(identifiers) or len(analyst_override) != len(identifiers):
            raise ValueError("La dérogation doit ordonner exactement toutes les mesures.")
        _required_text(override_reason, field="override_reason")
        order = {identifier: rank for rank, identifier in enumerate(analyst_override, start=1)}
    else:
        order = {}

    ranked = []
    for item in parsed:
        score = (
            _INFORMATION_VALUE_SCORES[item.measurement_class]
            + _EFFORT_SCORES[item.effort_level]
            - _RISK_PENALTIES[item.risk_level]
            - (4 if item.technician_required else 0)
        )
        ranked.append({
            **item.to_dict(),
            "qualitative_information_value_score": score,
            "ranking_basis": (
                "analyst_override" if analyst_override is not None
                else "generic_information_value_effort_risk"
            ),
            "selected_for_next_action": None,
            "override_reason": override_reason if analyst_override is not None else None,
            "automatic_causal_conclusion": None,
        })
    if analyst_override is not None:
        ranked.sort(key=lambda item: order[item["measurement_id"]])
    else:
        ranked.sort(key=lambda item: (-item["qualitative_information_value_score"], item["measurement_id"]))
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    return ranked


_DIFFERENTIAL_KEYS = {
    "rank",
    "cause",
    "mechanism",
    "supporting_evidence",
    "contrary_evidence",
    "expected_observables",
    "best_discriminating_measurement",
    "falsifier",
    "safety_constraints",
    "confidence",
}


def validate_physical_differential(payload: Mapping[str, Any], *, minimum_causes: int = 3) -> None:
    """Valide un raisonnement interne; ne valide jamais la vérité d'une cause."""

    if payload.get("schema_version") != 1:
        raise ValueError("Version de différentiel physique inconnue.")
    if payload.get("family") not in SYSTEM_FAMILIES:
        raise ValueError("Famille physique inconnue.")
    _required_text(payload.get("observation"), field="observation")

    chain = payload.get("energy_chain")
    if not isinstance(chain, Mapping):
        raise ValueError("La chaîne énergétique est requise.")
    expected_chain = {"energy_input", "equipment", "physical_service", "process_output", "unobserved_links"}
    if set(chain) != expected_chain:
        raise ValueError("La chaîne énergétique doit expliciter entrée, équipement, service, sortie et liens non observés.")
    for field in ("energy_input", "equipment", "physical_service", "process_output"):
        _required_text(chain.get(field), field=f"energy_chain.{field}")
    _text_list(chain.get("unobserved_links"), field="energy_chain.unobserved_links")

    demand = payload.get("service_demand_assessment")
    if not isinstance(demand, Mapping) or demand.get("status") not in SERVICE_DEMAND_STATUSES:
        raise ValueError("SERVICE_DEMAND_CHANGED? doit être évalué explicitement.")
    _text_list(demand.get("evidence"), field="service_demand_assessment.evidence")
    missing_demand = _text_list(
        demand.get("missing_variables"), field="service_demand_assessment.missing_variables"
    )
    if demand["status"] == "UNKNOWN" and not missing_demand:
        raise ValueError("Une demande de service inconnue doit nommer la variable manquante.")

    efficiency = payload.get("system_efficiency_assessment")
    if not isinstance(efficiency, Mapping) or efficiency.get("status") not in EFFICIENCY_STATUSES:
        raise ValueError("SYSTEM_EFFICIENCY_CHANGED? doit être évalué explicitement.")
    if efficiency.get("evaluated_after_service_demand") is not True:
        raise ValueError("L'efficacité doit être examinée après la demande de service.")
    _text_list(efficiency.get("evidence"), field="system_efficiency_assessment.evidence")
    if demand["status"] == "UNKNOWN" and efficiency["status"] in {"CHANGED", "UNCHANGED"}:
        raise ValueError("L'efficacité ne peut être tranchée si la demande essentielle reste inconnue.")

    control = payload.get("command_feedback_assessment")
    if not isinstance(control, Mapping) or control.get("status") not in COMMAND_FEEDBACK_STATUSES:
        raise ValueError("La distinction commande/état réel doit être évaluée.")
    for field in ("command_variable", "feedback_variable"):
        value = control.get(field)
        if not isinstance(value, str):
            raise ValueError(f"command_feedback_assessment.{field} doit être une chaîne.")
    _text_list(control.get("evidence"), field="command_feedback_assessment.evidence")
    if control["status"] in {"CONSISTENT", "MISMATCHED"} and (
        not control["command_variable"].strip() or not control["feedback_variable"].strip()
    ):
        raise ValueError("Une conclusion commande/feedback exige les deux variables réellement observées.")

    hypotheses = payload.get("hypotheses")
    if not isinstance(hypotheses, list) or len(hypotheses) < minimum_causes or len(hypotheses) > 5:
        raise ValueError(f"Le différentiel doit contenir entre {minimum_causes} et cinq causes.")
    ranks = []
    for item in hypotheses:
        if not isinstance(item, Mapping) or set(item) != _DIFFERENTIAL_KEYS:
            raise ValueError("Chaque cause doit respecter le contrat Physical Differential complet.")
        rank = item.get("rank")
        if not isinstance(rank, int):
            raise ValueError("Chaque cause exige un rang entier.")
        ranks.append(rank)
        for field in ("cause", "mechanism", "falsifier"):
            _required_text(item.get(field), field=field)
        for field in (
            "supporting_evidence",
            "contrary_evidence",
            "expected_observables",
            "safety_constraints",
        ):
            _text_list(item.get(field), field=field)
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= float(confidence) <= 1:
            raise ValueError("La confiance causale doit être comprise entre 0 et 1.")
        measurement = item.get("best_discriminating_measurement")
        if not isinstance(measurement, Mapping):
            raise ValueError("Chaque cause exige sa meilleure mesure discriminante.")
        measurement_from_dict(measurement)
    if sorted(ranks) != list(range(1, len(hypotheses) + 1)):
        raise ValueError("Les rangs du différentiel doivent être continus à partir de 1.")


def describe_evidence_boundaries(
    *,
    anomaly_status: str,
    essential_demand_available: bool,
    essential_process_variable_available: bool,
    hypotheses_distinguishable_with_current_evidence: bool,
    data_quality_blocker: bool = False,
) -> dict[str, Any]:
    """Expose les limites factuelles; Codex reste seul responsable de la decision.

    Cette fonction ne renvoie volontairement aucune classe du benchmark. Elle rend
    visibles les distinctions utiles a une abstention, sans choisir la suite.
    """

    allowed = {"CONFIRMED", "NOT_CONFIRMED", "UNKNOWN", "NORMAL_EXPLAINED"}
    if anomaly_status not in allowed:
        raise ValueError("Statut d anomalie inconnu.")
    unresolved = []
    if data_quality_blocker:
        unresolved.append("data_quality_prevents_phenomenon_qualification")
    if not essential_demand_available:
        unresolved.append("essential_service_demand_missing")
    if not essential_process_variable_available:
        unresolved.append("essential_process_variable_missing")
    if not hypotheses_distinguishable_with_current_evidence:
        unresolved.append("remaining_hypotheses_not_distinguishable")
    return {
        "anomaly_status_as_assessed_by_codex": anomaly_status,
        "data_quality_blocker_as_assessed_by_codex": data_quality_blocker,
        "essential_demand_available": essential_demand_available,
        "essential_process_variable_available": essential_process_variable_available,
        "hypotheses_distinguishable_with_current_evidence": hypotheses_distinguishable_with_current_evidence,
        "unresolved_evidence_boundaries": unresolved,
        "analyst_decision": None,
        "next_measurement_selected": None,
        "automatic_causal_conclusion": None,
    }


def validate_epistemic_decision_semantics(payload: Mapping[str, Any]) -> None:
    """Checks consistency of an analyst-declared decision without choosing it."""
    expected = {
        "decision", "abnormal_phenomenon_status", "legitimate_operation_explains_observation",
        "physical_cause_distinguished", "decision_required_blocked",
        "data_quality_blocks_qualification", "evidence_summary",
        "remaining_competing_explanations",
    }
    if set(payload) != expected:
        raise ValueError("Le contrat épistémique de décision est incomplet.")
    decision = payload.get("decision")
    if decision not in BENCHMARK_DECISIONS:
        raise ValueError("Décision benchmark inconnue.")
    abnormal = payload.get("abnormal_phenomenon_status")
    if abnormal not in {"CONFIRMED", "NOT_CONFIRMED", "UNKNOWN"}:
        raise ValueError("Le statut du phénomène anormal est invalide.")
    for field in ("legitimate_operation_explains_observation", "physical_cause_distinguished", "decision_required_blocked", "data_quality_blocks_qualification"):
        if not isinstance(payload.get(field), bool):
            raise ValueError(f"{field} doit être booléen.")
    _text_list(payload.get("evidence_summary"), field="evidence_summary", minimum=1)
    remaining = _text_list(payload.get("remaining_competing_explanations"), field="remaining_competing_explanations")
    if decision in {"CAUSE_PROBABLE", "CAUSE_CONFIRMED"} and abnormal != "CONFIRMED":
        raise ValueError("Une cause probable ou confirmée exige un phénomène anormal confirmé.")
    if decision == "NORMAL_OPERATION" and (abnormal == "CONFIRMED" or not payload["legitimate_operation_explains_observation"]):
        raise ValueError("NORMAL_OPERATION exige une explication opérationnelle légitime sans anomalie confirmée.")
    if decision == "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN":
        if abnormal != "CONFIRMED" or payload["physical_cause_distinguished"] or not remaining:
            raise ValueError("Cette décision exige une anomalie confirmée et des causes concurrentes non départagées.")
    if decision == "INSUFFICIENT_INFORMATION" and not payload["decision_required_blocked"]:
        raise ValueError("INSUFFICIENT_INFORMATION exige que l'information manquante bloque la décision requise.")
    if decision == "DATA_QUALITY_BLOCKER" and not payload["data_quality_blocks_qualification"]:
        raise ValueError("DATA_QUALITY_BLOCKER exige un blocage de qualification déclaré.")


def _knowledge_root() -> Path:
    return Path(__file__).resolve().parents[1] / "knowledge" / "physical_diagnostics"


def validate_knowledge_document(payload: Mapping[str, Any]) -> None:
    expected = {
        "schema_version",
        "family",
        "label",
        "energy_chain",
        "variables",
        "degradation_mechanisms",
        "legitimate_service_changes",
        "diagnostic_paths",
        "field_tests",
        "safety",
    }
    if set(payload) != expected or payload.get("schema_version") != 1:
        raise ValueError("Document de connaissance physique incomplet ou de version inconnue.")
    if payload.get("family") not in SYSTEM_FAMILIES:
        raise ValueError("Famille de connaissance inconnue.")
    _required_text(payload.get("label"), field="label")
    chain = payload.get("energy_chain")
    if not isinstance(chain, list) or len(chain) != 4:
        raise ValueError("Une fiche doit décrire les quatre maillons de la chaîne énergétique.")
    for index, link in enumerate(chain):
        _required_text(link, field=f"energy_chain[{index}]")
    variables = payload.get("variables")
    variable_keys = {"energy_input", "demand", "command", "feedback", "environment", "process_output"}
    if not isinstance(variables, Mapping) or set(variables) != variable_keys:
        raise ValueError("Les six catégories de variables physiques sont requises.")
    for name in variable_keys:
        _text_list(variables[name], field=f"variables.{name}", minimum=1)
    for name in ("degradation_mechanisms", "legitimate_service_changes", "diagnostic_paths", "field_tests", "safety"):
        value = payload.get(name)
        if not isinstance(value, list) or not value:
            raise ValueError(f"{name} doit être une liste non vide.")
    for path in payload["diagnostic_paths"]:
        if not isinstance(path, Mapping) or set(path) != {
            "observation_class", "mechanisms", "predictions", "discriminating_measurements", "interpretation_limits"
        }:
            raise ValueError("Un chemin diagnostique doit relier observation, mécanismes, prédictions et mesures.")
        _required_text(path.get("observation_class"), field="observation_class")
        for name in ("mechanisms", "predictions", "discriminating_measurements", "interpretation_limits"):
            _text_list(path.get(name), field=name, minimum=1)


def load_physical_knowledge(family: str, *, root: str | Path | None = None) -> dict[str, Any]:
    if family not in SYSTEM_FAMILIES:
        raise ValueError(f"Famille physique inconnue: {family}.")
    base = Path(root) if root is not None else _knowledge_root()
    target = base / f"{family}.json"
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Fiche physique absente: {target}.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Une fiche physique doit être un objet JSON.")
    validate_knowledge_document(payload)
    if payload["family"] != family:
        raise ValueError("Le nom de fichier et la famille physique ne correspondent pas.")
    return payload


def load_all_physical_knowledge(*, root: str | Path | None = None) -> dict[str, dict[str, Any]]:
    return {family: load_physical_knowledge(family, root=root) for family in sorted(SYSTEM_FAMILIES)}


def physical_reasoning_contract() -> dict[str, Any]:
    return {
        "guide": "docs/PHYSICAL_DIAGNOSTICS.md",
        "knowledge_directory": "knowledge/physical_diagnostics/",
        "energy_chain_required_for_major_findings": True,
        "service_demand_before_efficiency_claim": True,
        "command_vs_actual_feedback_considered": True,
        "maximum_justified_claim_required": True,
        "data_quantity_is_not_evidence_strength": True,
        "decision_semantics_validated_as_analyst_declarations": True,
        "physical_differential_fields": [
            "cause", "mechanism", "supporting_evidence", "contrary_evidence",
            "expected_observables", "best_discriminating_measurement",
            "falsifier", "safety_constraints",
        ],
        "fixed_investigation_sequence": False,
        "unlisted_hypotheses_and_tests_allowed": True,
        "python_selects_cause_question_action_or_decision": False,
    }


def physical_differential_template() -> dict[str, Any]:
    """Retourne un canevas vide; il ne propose aucune cause."""

    return {
        "schema_version": 1,
        "family": "REPLACE_WITH_FAMILY",
        "observation": "REPLACE_WITH_QUANTIFIED_OBSERVATION",
        "energy_chain": {
            "energy_input": "REPLACE",
            "equipment": "REPLACE",
            "physical_service": "REPLACE",
            "process_output": "REPLACE",
            "unobserved_links": [],
        },
        "service_demand_assessment": {
            "status": "UNKNOWN",
            "evidence": [],
            "missing_variables": ["REPLACE_WITH_MINIMUM_DEMAND_VARIABLE"],
        },
        "system_efficiency_assessment": {
            "status": "NOT_IDENTIFIABLE",
            "evidence": [],
            "evaluated_after_service_demand": True,
        },
        "command_feedback_assessment": {
            "command_variable": "",
            "feedback_variable": "",
            "status": "UNKNOWN",
            "evidence": [],
        },
        "hypotheses": [],
        "instructions": [
            "Codex creates at least three competing hypotheses for an open major finding.",
            "The knowledge layer is non-exhaustive and never selects a cause.",
            "This review contract does not impose an investigation sequence.",
        ],
    }
