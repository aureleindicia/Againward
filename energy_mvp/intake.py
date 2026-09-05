from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


OPERATING_MODES = {"scheduled", "24_7", "variable", "seasonal", "unknown"}


def intake_template() -> dict[str, Any]:
    """Questionnaire minimal lisible par une petite entreprise, sans jargon analytique."""

    return {
        "schema_version": 1,
        "site": {
            "name": None,
            "activity": None,
            "timezone": None,
            "meter_scope": None,
            "operations_contact_role": None,
        },
        "metering": {
            "measurement_kind": None,
            "unit": None,
            "timestamp_position": None,
            "nominal_interval_minutes": None,
        },
        "operations": {
            "operating_mode": "unknown",
            "weekly_schedule": {},
            "known_closures": [],
            "known_maintenance_periods": [],
            "legitimate_night_activity": None,
            "legitimate_weekend_activity": None,
        },
        "production": {
            "available": None,
            "unit": None,
            "product_families_available": None,
        },
        "weather": {"material_for_site": None},
        "cost": {
            "currency": "EUR",
            "flat_price_per_kwh": None,
            "has_time_of_use_or_demand_charges": None,
            "time_of_use_periods": [],
            "demand_charge_per_kw_month": None,
        },
        "known_changes": [],
        "client_questions_or_constraints": [],
        "human_review": {
            "required_before_delivery": True,
            "reviewer_role": None,
        },
    }


@dataclass(slots=True)
class IntakeAssessment:
    valid: bool
    missing_critical: list[dict[str, str]] = field(default_factory=list)
    missing_context: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    declared_capabilities: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "missing_critical": self.missing_critical,
            "missing_context": self.missing_context,
            "warnings": self.warnings,
            "declared_capabilities": self.declared_capabilities,
        }


def _need(path: str, question: str, reason: str) -> dict[str, str]:
    return {"field": path, "ask_client": question, "why_useful": reason}


def assess_intake(
    payload: dict[str, Any], *, evidence: dict[str, Any] | None = None
) -> IntakeAssessment:
    """Evalue ce que le contexte declare permet, sans inventer une reponse manquante."""

    site = payload.get("site") or {}
    metering = payload.get("metering") or {}
    operations = payload.get("operations") or {}
    production = payload.get("production") or {}
    weather = payload.get("weather") or {}
    cost = payload.get("cost") or {}
    evidence = evidence or {}
    critical: list[dict[str, str]] = []
    context: list[dict[str, str]] = []
    warnings: list[str] = []

    if not site.get("timezone"):
        critical.append(_need(
            "site.timezone",
            "Dans quel fuseau horaire se trouve le site (par exemple Europe/Paris) ?",
            "Il faut distinguer les heures locales de production et les changements d'heure.",
        ))
    if not site.get("meter_scope"):
        critical.append(_need(
            "site.meter_scope",
            "Que mesure exactement le compteur : site entier, bâtiment, atelier ou équipement ?",
            "Le périmètre conditionne toute interprétation et évite d'attribuer une charge au mauvais procédé.",
        ))
    resolved_measurement_kind = metering.get("measurement_kind") or evidence.get(
        "measurement_kind"
    )
    if resolved_measurement_kind not in {
        "power", "energy_per_interval", "cumulative_energy"
    }:
        critical.append(_need(
            "metering.measurement_kind",
            "La colonne principale est-elle une puissance, une énergie par intervalle ou un index cumulatif ?",
            "Ces trois mesures ne se convertissent pas de la même manière en kWh.",
        ))
    resolved_unit = metering.get("unit") or evidence.get("unit")
    if not resolved_unit:
        critical.append(_need(
            "metering.unit",
            "Quelle est l'unité exacte de la mesure principale (kW, kWh, W, Wh, etc.) ?",
            "Une unité ambiguë peut rendre tous les totaux faux.",
        ))
    resolved_timestamp_position = metering.get("timestamp_position")
    if resolved_timestamp_position not in {"start", "end"} and evidence.get(
        "timestamp_position_is_authoritative"
    ):
        resolved_timestamp_position = evidence.get("timestamp_position")
    if resolved_timestamp_position not in {"start", "end"}:
        critical.append(_need(
            "metering.timestamp_position",
            "L'horodatage désigne-t-il le début ou la fin de l'intervalle mesuré ?",
            "Cette convention fixe les périodes réellement couvertes par chaque valeur.",
        ))

    mode = operations.get("operating_mode", "unknown")
    if mode not in OPERATING_MODES:
        warnings.append(f"Mode d'exploitation non reconnu: {mode}.")
        mode = "unknown"
    if mode == "unknown":
        context.append(_need(
            "operations.operating_mode",
            "Le site fonctionne-t-il selon des horaires, en continu 24/7, de façon variable ou saisonnière ?",
            "Cela évite de traiter une activité nocturne ou de week-end légitime comme une anomalie.",
        ))
    if mode == "scheduled" and not operations.get("weekly_schedule"):
        context.append(_need(
            "operations.weekly_schedule",
            "Quels sont les horaires habituels d'ouverture ou de production pour chaque jour de la semaine ?",
            "Ils permettent de comparer les consommations en fonctionnement et hors horaires.",
        ))
    production_available = production.get("available")
    if production_available is None and evidence.get("production_available_in_dataset") is True:
        production_available = True
    if production_available is None:
        context.append(_need(
            "production.available",
            "Disposez-vous d'une quantité produite ou au moins d'un indicateur marche/arrêt aligné avec l'énergie ?",
            "Sans cette information, le système ne peut pas conclure sur l'efficacité à production comparable.",
        ))
    if weather.get("material_for_site") is None:
        context.append(_need(
            "weather.material_for_site",
            "Le chauffage, le froid, le séchage ou la météo influencent-ils fortement la consommation ?",
            "La réponse détermine si la température doit être contrôlée comme explication alternative.",
        ))
    if cost.get("flat_price_per_kwh") is None:
        context.append(_need(
            "cost.flat_price_per_kwh",
            "Quel prix moyen par kWh faut-il utiliser, hors TVA si possible ?",
            "Le tarif permet de convertir un impact énergétique observé en coût associé.",
        ))
    if cost.get("has_time_of_use_or_demand_charges") is None:
        context.append(_need(
            "cost.has_time_of_use_or_demand_charges",
            "Le contrat comporte-t-il des heures pleines/creuses ou une facturation de puissance ?",
            "Un prix moyen peut sinon sous-estimer ou surestimer l'importance économique d'un événement.",
        ))
    elif cost.get("has_time_of_use_or_demand_charges") is True and not (
        cost.get("time_of_use_periods") or cost.get("demand_charge_per_kw_month") is not None
    ):
        context.append(_need(
            "cost.time_of_use_periods",
            "Pouvez-vous copier les plages heures pleines/creuses et le prix de puissance mensuel indiqués sur le contrat ?",
            "Sans ces valeurs, un prix moyen ne permet pas de calculer fidèlement le coût réel par période.",
        ))

    if not metering.get("measurement_kind") and evidence.get("measurement_kind"):
        warnings.append(
            "Nature de mesure déduite de la colonne source: "
            f"{evidence['measurement_kind']}."
        )
    if not metering.get("unit") and evidence.get("unit"):
        warnings.append(f"Unité déduite de l'en-tête source: {evidence['unit']}.")

    return IntakeAssessment(
        valid=not critical,
        missing_critical=critical,
        missing_context=context,
        warnings=warnings,
        declared_capabilities={
            "off_schedule_analysis": mode == "scheduled" and bool(operations.get("weekly_schedule")),
            "continuous_operation_context": mode == "24_7",
            "production_efficiency_analysis": production_available is True,
            "weather_normalization_expected": (
                weather.get("material_for_site") is True
                and evidence.get("temperature_available_in_dataset", True)
            ),
            "flat_costing": cost.get("flat_price_per_kwh") is not None,
        },
    )
