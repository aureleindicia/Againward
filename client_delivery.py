"""Livraison client Goal C : modèle fidèle, graphiques explicitement choisis et PDF léger.

Codex fournit le récit client (priorités, explications, langage métier). Python
résout les références Goal A/B, produit les nombres et le PDF, et refuse toute
altération structurelle de la décision ou des claims quantitatifs.
"""
from __future__ import annotations

import binascii
import csv
import json
import math
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from operational_economics import SCENARIOS, aggregate_declared_portfolio


DECISION_LABELS = {
    "ACT_NOW": "Action recommandée",
    "INVESTIGATE_FIRST": "Vérifier avant d'investir",
    "MONITOR": "À surveiller",
    "DEFER": "À planifier",
    "DO_NOTHING": "Aucune action nécessaire",
    "NO_ECONOMIC_CASE": "Action non justifiée économiquement",
    "OPERATIONALLY_NOT_JUSTIFIED": "Action non recommandée dans les conditions actuelles",
    "INSUFFICIENT_FOR_ECONOMIC_DECISION": "Informations insuffisantes pour décider",
}
EVIDENCE_LABELS = {"HIGH": "Fort", "MEDIUM": "Modéré", "LOW": "Limité", "NOT_CALIBRATED": "Non calibré"}
SAVING_STATUS = {"POTENTIAL", "EXPECTED", "VERIFIED"}
_OPERATION_CONTEXT_MIN_COVERAGE = 0.80
_FORBIDDEN_NARRATIVE = re.compile(r"(?:\b(?:verified savings|économie vérifiée|act_now|investigate_first)\b|\b(?:find|art|ds|gbe|dec|act|eff|rel|cons)-[a-z0-9-]+\b|/(?:data|home|storage)/|\b[a-f0-9]{32,}\b)", re.IGNORECASE)
_CARD_CLAIM_TYPES = {
    "what_we_found": "OBSERVATION",
    "why_this_matters": "WHY_THIS_MATTERS",
    "contextual_rationale": "CONTEXTUAL_RATIONALE",
    "uncertainty": "UNCERTAINTY",
}


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Objet JSON attendu : {path}")
    return payload


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require_text(value: Any, label: str, *, max_length: int = 700, allow_numbers: bool = False) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
        raise ValueError(f"{label} doit être un texte client non vide et concis.")
    if _FORBIDDEN_NARRATIVE.search(value):
        raise ValueError(f"{label} expose un identifiant interne ou une formulation interdite.")
    if not allow_numbers and re.search(r"\d", value):
        raise ValueError(f"{label} ne peut pas contenir de nombre libre : utilisez un claim quantitatif validé.")
    return value.strip()


def _money(value: float | None, currency: str = "EUR") -> str | None:
    if value is None:
        return None
    symbol = "€" if currency == "EUR" else currency + " "
    return f"{symbol}{value:,.0f}".replace(",", " ")


def _range_or_exact(values: dict[str, Any], *, field: str, currency: str, period: str) -> dict[str, Any] | None:
    low, base, high = (values[name].get(field) for name in SCENARIOS)
    if any(item is None for item in (low, base, high)):
        return None
    low, base, high = float(low), float(base), float(high)
    if low == base == high:
        display = f"{_money(base, currency)}/{period}"
        precision = "EXACT"
    else:
        display = f"{_money(low, currency)}–{_money(high, currency)}/{period}"
        precision = "RANGE"
    return {"kind": precision, "low": low, "base": base, "high": high, "currency": currency, "period": period, "display": display, "scenario_used_as_expected": "BASE" if precision == "EXACT" else None}


def _economic_claim(calculation: dict[str, Any]) -> dict[str, Any]:
    scenarios = calculation["scenarios"]
    annual = _range_or_exact(scenarios, field="net_annual_benefit", currency=calculation["currency"], period="an")
    capex = _range_or_exact(scenarios, field="intervention_cost", currency=calculation["currency"], period="ponctuel")
    energy = {name: float(scenarios[name]["annual_energy_saving_kwh"]) for name in SCENARIOS}
    return {
        "saving_status": "POTENTIAL",
        "annual_net_benefit": annual,
        "intervention_cost": capex,
        "annual_energy_saving_kwh": energy,
        "calculation_ref": calculation["effect_id"],
        "baseline": calculation["baseline"],
        "claim_refs": calculation["reproducibility"]["input_references"],
    }


def _decision_next_step(decision: dict[str, Any], action: dict[str, Any]) -> dict[str, Any] | None:
    """Expose une prochaine étape déterminée par la décision, jamais par un récit libre."""
    kind = decision["decision"]
    if kind == "ACT_NOW":
        plan = action.get("validation_plan")
        if not isinstance(plan, dict):
            return None
        return {"kind": "POST_ACTION_VALIDATION", "title": "Comment vérifier après action", "details": {
            field: plan[field] for field in ("metric", "expected_direction", "comparison_window", "confounders", "minimum_evidence") if field in plan
        }}
    if kind == "INVESTIGATE_FIRST":
        evidence = decision.get("evidence_acquisition")
        if not isinstance(evidence, dict):
            return None
        return {"kind": "PRE_INVESTMENT_VERIFICATION", "title": "Ce qu'il faut vérifier avant d'investir", "details": {
            field: evidence[field] for field in ("what_it_resolves", "decision_that_can_change", "cost_or_burden", "why_worth_it") if field in evidence
        }}
    if kind == "MONITOR":
        plan = action.get("validation_plan")
        if not isinstance(plan, dict):
            return None
        return {"kind": "MONITORING", "title": "Ce qu'il faut surveiller", "details": {
            field: plan[field] for field in ("metric", "comparison_window", "expected_direction", "confounders", "minimum_evidence") if field in plan
        }}
    if kind == "DEFER":
        evidence = decision.get("evidence_acquisition")
        if not isinstance(evidence, dict):
            return None
        return {"kind": "REASSESSMENT", "title": "Quand réévaluer cette option", "details": {
            field: evidence[field] for field in ("what_it_resolves", "decision_that_can_change", "why_worth_it") if field in evidence
        }}
    # Une action non recommandée, non rentable ou un no-finding ne reçoit pas
    # artificiellement un protocole de validation post-intervention.
    return None


def _human_sources(case: Path) -> list[dict[str, str]]:
    inventory = _read(case / "evidence" / "intake_inventory.json").get("artifacts", [])
    return [
        {"source_ref": item["artifact_id"], "label": Path(str(item.get("raw_relative_path") or item["original_filename"])).name, "role": item.get("probable_role", "UNKNOWN")}
        for item in inventory if item.get("probable_role") != "IRRELEVANT"
    ]


def _goal_a_findings(case: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    payload = _read(case / "investigation" / "structured_findings.json")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise ValueError("Findings Goal A invalides.")
    mapping = {item.get("finding_id"): item for item in findings if isinstance(item, dict) and item.get("finding_id")}
    return mapping, payload.get("no_finding")


def _validate_claim(
    claim: Any,
    *,
    label: str,
    decisions: dict[str, dict[str, Any]],
    actions: dict[str, dict[str, Any]],
    findings: dict[str, dict[str, Any]],
    constraints: dict[str, dict[str, Any]],
    calculations: dict[str, dict[str, Any]],
    dataset_ids: set[str],
    no_finding: dict[str, Any] | None,
    expected_action_id: str | None = None,
    expected_decision_id: str | None = None,
    expected_kind: str | None = None,
) -> dict[str, Any]:
    """Valide le rattachement, pas le sens libre du français écrit par Codex.

    Les types de claim rendent impossible qu'un bloc de recommandation soit
    structurellement un claim de non-action pour une décision ACT_NOW.  Le
    texte reste du ressort de Codex : Python vérifie les objets auxquels il se
    rapporte, sans tenter d'interpréter le langage naturel.
    """
    if not isinstance(claim, dict):
        raise ValueError(f"{label} doit être un claim client structuré.")
    _require_text(claim.get("text"), f"{label}/text")
    claim_type = claim.get("claim_type")
    if not isinstance(claim_type, str) or not claim_type:
        raise ValueError(f"{label} exige claim_type.")
    if expected_kind and claim_type != expected_kind:
        raise ValueError(f"{label} exige un claim_type {expected_kind}.")
    decision_ref = claim.get("decision_ref")
    if decision_ref is not None and decision_ref not in decisions:
        raise ValueError(f"{label} référence une décision Goal B inexistante.")
    if expected_decision_id is not None and decision_ref != expected_decision_id:
        raise ValueError(f"{label} doit rester rattaché à la décision de sa carte.")
    action_ref = claim.get("action_ref")
    if action_ref is not None and action_ref not in actions:
        raise ValueError(f"{label} référence une action Goal B inexistante.")
    if expected_action_id is not None and action_ref != expected_action_id:
        raise ValueError(f"{label} doit rester rattaché à l'action de sa carte.")
    finding_refs = claim.get("finding_refs", [])
    if not isinstance(finding_refs, list) or set(finding_refs) - set(findings):
        raise ValueError(f"{label} référence un finding Goal A inexistant.")
    if expected_action_id is not None and set(finding_refs) != set(actions[expected_action_id]["finding_ids"]):
        raise ValueError(f"{label} doit conserver les findings de l'action concernée.")
    constraint_refs = claim.get("constraint_refs", [])
    if not isinstance(constraint_refs, list) or set(constraint_refs) - set(constraints):
        raise ValueError(f"{label} référence une contrainte inexistante.")
    if expected_action_id is not None:
        related_constraints = {
            item["constraint_id"] for item in constraints.values()
            if expected_action_id in item.get("affected_action_ids", [])
        }
        if set(constraint_refs) - related_constraints:
            raise ValueError(f"{label} référence une contrainte d'une autre action.")
    economic_refs = claim.get("economic_refs", [])
    if not isinstance(economic_refs, list) or set(economic_refs) - set(calculations):
        raise ValueError(f"{label} référence un calcul économique inexistant.")
    if expected_action_id is not None and set(economic_refs) - {expected_action_id}:
        raise ValueError(f"{label} référence un calcul économique d'une autre action.")
    evidence_refs = claim.get("evidence_refs", [])
    if not isinstance(evidence_refs, list) or set(evidence_refs) - dataset_ids:
        raise ValueError(f"{label} référence une preuve ou dataset inexistant.")
    if claim.get("no_finding_ref") not in {None, "GOAL_A_NO_FINDING"}:
        raise ValueError(f"{label} possède un no_finding_ref invalide.")
    if claim.get("no_finding_ref") == "GOAL_A_NO_FINDING" and not no_finding:
        raise ValueError(f"{label} référence un no-finding Goal A absent.")
    if not (finding_refs or constraint_refs or economic_refs or evidence_refs or claim.get("no_finding_ref") == "GOAL_A_NO_FINDING" or decision_ref or action_ref):
        raise ValueError(f"{label} ne peut pas créer un fait client sans référence auditable.")
    return claim


def _validate_narrative(
    narrative: dict[str, Any], *, decisions: dict[str, dict[str, Any]], actions: dict[str, dict[str, Any]],
    findings: dict[str, dict[str, Any]], constraints: dict[str, dict[str, Any]], calculations: dict[str, dict[str, Any]],
    dataset_ids: set[str], no_finding: dict[str, Any] | None,
) -> None:
    if not isinstance(narrative, dict):
        raise ValueError("Le contenu narratif Codex doit être un objet.")
    _require_text(narrative.get("site_name"), "site_name", max_length=100, allow_numbers=True)
    _require_text(narrative.get("report_title", "Analyse de performance énergétique"), "report_title", max_length=140, allow_numbers=True)
    _require_text(narrative.get("analysis_period", "Période disponible dans les données"), "analysis_period", max_length=160, allow_numbers=True)
    _require_text(narrative.get("executive_message"), "executive_message", max_length=500)
    cards = narrative.get("cards", {})
    if not isinstance(cards, dict) or set(cards) - set(actions):
        raise ValueError("Les récits de cartes doivent référencer des actions Goal B réelles.")
    for action_id, card in cards.items():
        if not isinstance(card, dict):
            raise ValueError(f"Carte narrative {action_id} invalide.")
        _require_text(card.get("headline"), f"Carte {action_id}/headline", max_length=150)
        decision = next((item for item in decisions.values() if action_id in item.get("considered_action_ids", item.get("selected_action_ids", item.get("action_ids", [])))), None)
        if decision is None:
            raise ValueError("Une carte ne peut pas mettre en avant une action absente des décisions Goal B.")
        claims = card.get("claims")
        if not isinstance(claims, dict) or set(claims) != set(_CARD_CLAIM_TYPES):
            raise ValueError("Chaque carte exige ses quatre claims client structurés.")
        for field, kind in _CARD_CLAIM_TYPES.items():
            _validate_claim(claims[field], label=f"Carte {action_id}/{field}", decisions=decisions, actions=actions, findings=findings, constraints=constraints, calculations=calculations, dataset_ids=dataset_ids, no_finding=no_finding, expected_action_id=action_id, expected_decision_id=decision["decision_id"], expected_kind=kind)
    for item in narrative.get("no_action_items", []):
        if not isinstance(item, dict):
            raise ValueError("Élément no-action invalide.")
        _require_text(item.get("title"), "no-action/title", max_length=150)
        claim = _validate_claim(item.get("claim"), label="no-action/claim", decisions=decisions, actions=actions, findings=findings, constraints=constraints, calculations=calculations, dataset_ids=dataset_ids, no_finding=no_finding)
        if claim["claim_type"] not in {"NO_ACTION_REQUIRED", "NO_ACTION_ECONOMIC", "NO_ACTION_OPERATIONAL", "INSUFFICIENT_TO_DECIDE"}:
            raise ValueError("Un no-action item ne peut pas porter une recommandation positive.")
    for item in narrative.get("what_we_checked", []):
        _validate_claim(item, label="what_we_checked", decisions=decisions, actions=actions, findings=findings, constraints=constraints, calculations=calculations, dataset_ids=dataset_ids, no_finding=no_finding, expected_kind="WHAT_WAS_CHECKED")
    for item in narrative.get("limitations", []):
        _require_text(item, "limitation", max_length=320)
    if "method" in narrative:
        _require_text(narrative["method"], "method", max_length=500)


class _ClientChartCanvas:
    """Petit raster local Goal C : il dessine, sans interpréter les données."""

    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width, height
        self.pixels = bytearray((255, 255, 255) * (width * height))

    def point(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self.pixels[offset:offset + 3] = bytes(color)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        for y in range(max(0, y0), min(self.height, y1)):
            start, end = (y * self.width + max(0, x0)) * 3, (y * self.width + min(self.width, x1)) * 3
            self.pixels[start:end] = bytes(color) * max(0, min(self.width, x1) - max(0, x0))

    def line(self, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        dx, sx, dy, sy = abs(x1 - x0), (1 if x0 < x1 else -1), -abs(y1 - y0), (1 if y0 < y1 else -1)
        error = dx + dy
        while True:
            self.point(x0, y0, color)
            if x0 == x1 and y0 == y1:
                return
            twice = 2 * error
            if twice >= dy:
                error += dy
                x0 += sx
            if twice <= dx:
                error += dx
                y0 += sy

    def save(self, path: Path, title: str) -> None:
        raw = b"".join(b"\x00" + bytes(self.pixels[row * self.width * 3:(row + 1) * self.width * 3]) for row in range(self.height))
        def chunk(kind: bytes, payload: bytes) -> bytes:
            body = kind + payload
            return struct.pack(">I", len(payload)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)) + chunk(b"tEXt", b"Title\x00" + title.encode("latin-1", errors="replace")) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(png)


def _downsample_operation(values: list[bool | None], target: int) -> list[bool | None]:
    """Conserve `UNKNOWN` : aucune valeur manquante ne devient inactive."""
    groups = [[item] for item in values] if len(values) <= target else [values[index * len(values) // target:(index + 1) * len(values) // target] for index in range(target)]
    result: list[bool | None] = []
    for group in groups:
        known = [item for item in group if item is not None]
        if any(item is True for item in known):
            result.append(True)
        elif len(known) == len(group):
            result.append(False)
        else:
            result.append(None)
    return result


def _write_operation_context_chart(values: list[float], operation: list[bool | None] | None, path: Path, *, title: str) -> None:
    """Affiche l'état opérationnel prouvé; `None` reste inconnu, jamais inactif."""
    width, height, left, right, top, bottom = 900, 360, 52, 18, 20, 36
    plot_width, plot_height = width - left - right, height - top - bottom
    if not values or not all(math.isfinite(item) for item in values):
        raise ValueError("Le graphique opérationnel exige une énergie finie.")
    bins = min(plot_width, len(values))
    energy = [sum(values[index * len(values) // bins:(index + 1) * len(values) // bins]) / max(1, len(values[index * len(values) // bins:(index + 1) * len(values) // bins])) for index in range(bins)]
    activity = None if operation is None else _downsample_operation(operation, bins)
    minimum, maximum = min(0.0, min(energy)), max(energy)
    if math.isclose(minimum, maximum):
        maximum += 1.0
    maximum += (maximum - minimum) * .05
    canvas = _ClientChartCanvas(width, height)
    if activity is not None:
        for index, active in enumerate(activity):
            x0 = left + round(plot_width * index / bins)
            x1 = left + round(plot_width * (index + 1) / bins)
            color = (255, 244, 218) if active is True else (244, 247, 250) if active is False else (237, 237, 245)
            canvas.rect(x0, top, x1, top + plot_height, color)
    for step in range(6):
        y = top + round(plot_height * step / 5)
        canvas.line(left, y, width - right, y, (220, 225, 230))
    canvas.line(left, top, left, top + plot_height, (95, 105, 115))
    canvas.line(left, top + plot_height, width - right, top + plot_height, (95, 105, 115))
    previous: tuple[int, int] | None = None
    for index, value in enumerate(energy):
        x = left + round(plot_width * index / max(1, len(energy) - 1))
        y = top + plot_height - round((value - minimum) / (maximum - minimum) * plot_height)
        if previous is not None:
            canvas.line(previous[0], previous[1], x, y, (31, 119, 180))
        previous = (x, y)
    canvas.save(path, title)


def _operation_context_source(dataset: dict[str, Any]) -> tuple[str, float]:
    """Résout uniquement une source Goal A explicitement identifiée, jamais une colonne vide par défaut."""
    lineage = dataset.get("field_lineage")
    coverage = dataset.get("data_quality", {}).get("production_coverage_ratio")
    if not isinstance(lineage, dict) or "production" not in lineage:
        raise ValueError("ENERGY_WITH_OPERATION_STATUS exige une source Goal A explicite de production ou d'activité.")
    if not isinstance(coverage, (int, float)) or not math.isfinite(float(coverage)) or float(coverage) < _OPERATION_CONTEXT_MIN_COVERAGE:
        raise ValueError("ENERGY_WITH_OPERATION_STATUS exige une couverture de production suffisante; utilisez ENERGY_SERIES sans contexte opérationnel.")
    return "production", float(coverage)


def _production_status(value: Any) -> bool | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric > 0 if math.isfinite(numeric) else None


def _resolve_chart_requests(case: Path, narrative: dict[str, Any], output_dir: Path) -> list[dict[str, Any]]:
    canonical = _read(case / "derived" / "canonical_case.json")
    datasets = {item["dataset_id"]: item for item in canonical.get("available_datasets", [])}
    charts: list[dict[str, Any]] = []
    for index, request in enumerate(narrative.get("chart_requests", []), start=1):
        if not isinstance(request, dict) or request.get("type") not in {"ENERGY_SERIES", "ENERGY_WITH_OPERATION_STATUS"}:
            raise ValueError("Le type de graphique client doit être ENERGY_SERIES ou ENERGY_WITH_OPERATION_STATUS.")
        dataset = datasets.get(request.get("dataset_id"))
        if not dataset or not dataset.get("analytically_usable") or dataset.get("role") not in {"ENERGY_INTERVAL_SERIES", "POWER_SERIES"}:
            raise ValueError("Le graphique doit référencer une série Goal A réellement exploitable.")
        title = _require_text(request.get("title"), "chart/title", max_length=140)
        purpose = _require_text(request.get("purpose"), "chart/purpose", max_length=260)
        source = case / str(dataset["normalized_file"])
        context_field, context_coverage = (None, None)
        if request["type"] == "ENERGY_WITH_OPERATION_STATUS":
            context_field, context_coverage = _operation_context_source(dataset)
        values: list[float] = []
        operation: list[bool | None] = []
        timestamps: list[str] = []
        with source.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                raw = row.get("energy_kwh") or row.get("power_kw") or row.get("measurement")
                try:
                    values.append(float(raw))
                    timestamps.append(str(row.get("timestamp", "")))
                    if context_field is not None:
                        operation.append(_production_status(row.get(context_field)))
                except (TypeError, ValueError):
                    continue
        if len(values) < 2:
            raise ValueError("Un graphique client exige au moins deux observations numériques.")
        filename = f"chart_{index:02d}.png"
        path = output_dir / "charts" / filename
        has_binary_context = context_field is not None and len(operation) == len(values)
        if has_binary_context:
            _write_operation_context_chart(values, operation, path, title=title)
        else:
            _write_operation_context_chart(values, None, path, title=title)
        unknown_count = sum(item is None for item in operation) if has_binary_context else 0
        charts.append({"chart_id": f"CHART-{index:02d}", "type": request["type"], "title": title, "purpose": purpose, "caption": purpose, "dataset_ref": dataset["dataset_id"], "relative_path": f"charts/{filename}", "claim_refs": [dataset["dataset_id"]], "axis_x": "Chronologie des relevés" if not timestamps else f"Chronologie des relevés ({timestamps[0]} à {timestamps[-1]})", "axis_y": "Énergie par intervalle (kWh)" if dataset.get("measurement_type") != "POWER" else "Puissance (kW)", "legend": "Courbe bleue : consommation" + (" ; bandes orange pâle : activité/production active ; bandes grises : inactive" + (" ; bandes violettes pâles : statut inconnu" if unknown_count else "") if has_binary_context else ""), "operation_encoding": "BACKGROUND_BANDS" if has_binary_context else "NONE", "operation_context": None if not has_binary_context else {"source_field": context_field, "coverage_ratio": context_coverage, "unknown_interval_count": unknown_count}, "explains": purpose})
    return charts


def _decision_cards(
    findings: dict[str, dict[str, Any]], state: dict[str, Any], narrative: dict[str, Any],
) -> list[dict[str, Any]]:
    actions = {item["action_id"]: item for item in state.get("candidate_actions", [])}
    constraints = state.get("operational_constraints", [])
    calculations = state.get("scenario_calculations", {})
    cards: list[dict[str, Any]] = []
    for decision in state.get("decisions", []):
        selected = decision.get("selected_action_ids", decision.get("action_ids", []))
        considered = decision.get("considered_action_ids", selected)
        displayed = selected if decision["decision"] not in {"NO_ECONOMIC_CASE", "OPERATIONALLY_NOT_JUSTIFIED"} else considered
        for action_id in displayed:
            action = actions[action_id]
            if action_id not in narrative.get("cards", {}):
                raise ValueError(f"Codex doit fournir un récit client pour l'action sélectionnée {action_id}.")
            linked_findings = [findings[item] for item in action["finding_ids"]]
            hard_constraints = [item for item in constraints if item.get("hard") and item.get("material") and action_id in item.get("affected_action_ids", [])]
            assessment_ids = {item.get("constraint_id") for item in decision.get("constraint_assessments", [])}
            if any(item["constraint_id"] not in assessment_ids for item in hard_constraints):
                raise ValueError("Une contrainte dure pertinente ne peut pas disparaître du rapport client.")
            calc = calculations.get(action_id)
            claim_text = narrative["cards"][action_id]["claims"]
            card = {
                "card_id": f"CARD-{decision['decision_id']}-{action_id}", "decision_ref": decision["decision_id"], "action_ref": action_id,
                "considered_action_ref": action_id if action_id in considered else None,
                "decision": decision["decision"], "client_directive": DECISION_LABELS[decision["decision"]],
                "headline": narrative["cards"][action_id]["headline"],
                "what_we_found": claim_text["what_we_found"]["text"],
                "why_this_matters": claim_text["why_this_matters"]["text"],
                "contextual_rationale": claim_text["contextual_rationale"]["text"],
                "uncertainty": claim_text["uncertainty"]["text"],
                "claims": claim_text,
                "observed": [item["observation"] for item in linked_findings],
                "inferred": [explanation for item in linked_findings for explanation in item.get("possible_explanations", [])],
                "evidence_level": EVIDENCE_LABELS.get(decision.get("technical_confidence"), "Non calibré"),
                "operational_constraints": [{"constraint_ref": item["constraint_id"], "description": item["description"], "hard": item["hard"], "material": item["material"]} for item in hard_constraints],
                "next_step": _decision_next_step(decision, action),
                "economic_impact": None if calc is None else _economic_claim(calc),
                "claim_refs": {"finding_ids": action["finding_ids"], "decision_id": decision["decision_id"], "action_id": action_id, "economic_calculation_refs": [action_id] if action_id in calculations else [], "constraint_refs": [item["constraint_id"] for item in hard_constraints]},
                "considered_action_ids": considered,
            }
            cards.append(card)
    return cards


def _alternative_groups(state: dict[str, Any]) -> list[dict[str, Any]]:
    actions = {item["action_id"]: item for item in state.get("candidate_actions", [])}
    calculations = state.get("scenario_calculations", {})
    groups = []
    for relation in state.get("relationships", []):
        if relation.get("type") not in {"MUTUALLY_EXCLUSIVE", "ALTERNATIVE"}:
            continue
        members = [relation["action_a"], relation["action_b"]]
        selected = {action_id for decision in state.get("decisions", []) for action_id in decision.get("selected_action_ids", decision.get("action_ids", []))}
        def option(action_id: str) -> dict[str, Any]:
            calculation = calculations.get(action_id)
            scenario = None if calculation is None else calculation.get("scenarios", {}).get("BASE", {})
            affected = [item["description"] for item in state.get("operational_constraints", []) if action_id in item.get("affected_action_ids", [])]
            return {
                "action_ref": action_id, "title": actions[action_id]["title"],
                "economic_impact": None if calculation is None else _economic_claim(calculation),
                "payback_years": None if scenario is None else scenario.get("simple_payback_years"),
                "downtime": actions[action_id].get("downtime", "À confirmer avec le prestataire"),
                "operational_burden": actions[action_id].get("operational_rationale"),
                "major_uncertainty": actions[action_id].get("major_uncertainty", "À confirmer avant engagement."),
                "constraint_refs": [item["constraint_id"] for item in state.get("operational_constraints", []) if action_id in item.get("affected_action_ids", [])],
                "current_preference": action_id in selected,
            }
        groups.append({
            "relationship_ref": relation["relationship_id"], "type": relation["type"], "rationale": relation["rationale"],
            "options": [option(action_id) for action_id in members],
            "not_additive": True,
        })
    return groups


def _portfolio_total(state: dict[str, Any]) -> dict[str, Any] | None:
    selected = [action_id for decision in state.get("decisions", []) for action_id in decision.get("selected_action_ids", decision.get("action_ids", []))]
    calculations = state.get("scenario_calculations", {})
    if not selected or any(action_id not in calculations for action_id in selected):
        return None
    if len(selected) == 1:
        return _economic_claim(calculations[selected[0]])["annual_net_benefit"]
    try:
        aggregate = aggregate_declared_portfolio(selected, calculations, state.get("relationships", []), combined_effects=state.get("combined_effects", {}), economic_value_sources=state.get("economic_inputs", []) + state.get("scenario_assumptions", []))
    except ValueError:
        return None
    values = {name: {"net_annual_benefit": aggregate["net_annual_benefit"][name]} for name in SCENARIOS}
    return _range_or_exact(values, field="net_annual_benefit", currency="EUR", period="an")


def build_client_report_model(case_directory: str | Path, narrative: dict[str, Any], *, output_directory: str | Path | None = None) -> dict[str, Any]:
    """Construit le modèle C sans créer de diagnostic ou de décision.

    `narrative` est un contrat d'explication fourni par Codex. Toute valeur,
    décision, référence et relation vient exclusivement des états Goal A/B.
    """
    from energy_mvp.client_lifecycle import assert_workflow_action_allowed
    assert_workflow_action_allowed(case_directory,"report_generation")
    case = Path(case_directory)
    findings, no_finding = _goal_a_findings(case)
    state_path = case / "investigation" / "economic_decision_state.json"
    if not state_path.exists():
        raise ValueError("Goal C exige un état économique Goal B persistant.")
    state = _read(state_path)
    decisions = state.get("decisions", [])
    decisions_by_id = {item["decision_id"]: item for item in decisions}
    actions = {item["action_id"]: item for item in state.get("candidate_actions", [])}
    constraints = {item["constraint_id"]: item for item in state.get("operational_constraints", [])}
    canonical = _read(case / "derived" / "canonical_case.json")
    lifecycle_path = case / "investigation" / "investigation_state.json"
    lifecycle_state = _read(lifecycle_path).get("client_lifecycle", {}).get("state") if lifecycle_path.exists() else None
    dataset_ids = {item["dataset_id"] for item in canonical.get("available_datasets", [])}
    _validate_narrative(narrative, decisions=decisions_by_id, actions=actions, findings=findings, constraints=constraints, calculations=state.get("scenario_calculations", {}), dataset_ids=dataset_ids, no_finding=no_finding)
    decision = decisions[0] if decisions else None
    if not findings:
        if not isinstance(no_finding, dict) or not decision or decision.get("decision") != "DO_NOTHING":
            raise ValueError("Un rapport sans finding exige un no_finding Goal A canonique et DO_NOTHING Goal B.")
    cards = _decision_cards(findings, state, narrative)
    if not findings and cards:
        raise ValueError("Un no-finding ne peut pas produire de carte d'action.")
    target = Path(output_directory) if output_directory else case / "outputs" / "client_report"
    charts = _resolve_chart_requests(case, narrative, target)
    priority_cards = cards[:3]
    no_action_items = [{"title": item["title"], "explanation": item["claim"]["text"], "claim": item["claim"]} for item in narrative.get("no_action_items", [])]
    if not findings and not no_action_items:
        raise ValueError("Un rapport no-finding exige une explication client utile.")
    canonical_questions = case / "investigation" / "questions.json"
    if canonical_questions.exists():
        pending_questions = [{"request_ref": item["request_id"], "question": item["client_question"],
            "decision_impact": ", ".join(item.get("decision_impact_dimensions", []))}
            for item in _read(canonical_questions).get("questions", []) if item.get("status") == "open"]
    else:
        evidence_by_request = {item.get("request_id") for item in state.get("goal_b_evidence", []) if item.get("request_id")}
        pending_questions = [{"request_ref": item["request_id"], "question": item["client_question"], "decision_impact": item["decision_impact"]}
            for item in state.get("economic_requests", []) if item.get("request_id") not in evidence_by_request]
    model = {
        "schema_version": 3,
        "kind": "CLIENT_REPORT_MODEL",
        "metadata": {"case_id": _read(case / "case_manifest.json")["case_id"], "site_name": narrative["site_name"], "report_title": narrative.get("report_title", "Analyse de performance énergétique"), "analysis_period": narrative.get("analysis_period", "Période disponible dans les données"), "regulatory_notice": "Cette prestation ne constitue pas un audit énergétique réglementaire.", "client_lifecycle_state": lifecycle_state},
        "executive_summary": {"message": narrative["executive_message"], "important_subjects": len(cards), "recommended_actions": sum(card["decision"] == "ACT_NOW" for card in cards), "verify_first": sum(card["decision"] == "INVESTIGATE_FIRST" for card in cards), "monitor": sum(card["decision"] == "MONITOR" for card in cards), "no_action_items": len(no_action_items), "economic_total": _portfolio_total(state), "priority_card_refs": [card["card_id"] for card in priority_cards]},
        "decision_cards": cards,
        "alternative_groups": _alternative_groups(state),
        "no_action_items": no_action_items,
        "client_dialogue": {"pending_questions": pending_questions, "resolved_goal_b_evidence_refs": sorted(item.get("evidence_id") for item in state.get("goal_b_evidence", []) if item.get("evidence_id"))},
        "what_we_checked": list(narrative.get("what_we_checked", [])),
        "charts": charts,
        "technical_appendix": {"sources": _human_sources(case), "limitations": narrative.get("limitations", []), "method": narrative.get("method", "Les chiffres affichés reprennent les calculs validés et les décisions enregistrées."), "claim_reference_policy": "Chaque carte relie décision, action, finding et calcul Goal A/B; les identifiants restent internes."},
        "claim_fidelity": {"goal_a_findings_ref": "investigation/structured_findings.json", "goal_b_state_ref": "investigation/economic_decision_state.json", "decision_strengthened": False, "savings_status": "POTENTIAL", "internal_claim_refs_present": True, "non_additive_actions_not_summed": True},
    }
    validate_client_report_model(model, case)
    _write(target / "CLIENT_REPORT_MODEL.json", model)
    return model


def validate_client_report_model(model: dict[str, Any], case_directory: str | Path) -> None:
    """Contrat anti-renforcement : le modèle doit refléter exactement Goal A/B."""
    case = Path(case_directory)
    if model.get("kind") != "CLIENT_REPORT_MODEL" or model.get("schema_version") != 3:
        raise ValueError("Schéma de modèle client invalide.")
    findings, no_finding = _goal_a_findings(case)
    state = _read(case / "investigation" / "economic_decision_state.json")
    decisions = {item["decision_id"]: item for item in state.get("decisions", [])}
    actions = {item["action_id"]: item for item in state.get("candidate_actions", [])}
    calculations = state.get("scenario_calculations", {})
    constraints = {item["constraint_id"]: item for item in state.get("operational_constraints", [])}
    canonical = _read(case / "derived" / "canonical_case.json")
    dataset_ids = {item["dataset_id"] for item in canonical.get("available_datasets", [])}
    metadata = model.get("metadata", {})
    for field in ("site_name", "report_title", "analysis_period", "regulatory_notice"):
        _require_text(metadata.get(field), f"metadata/{field}", max_length=220, allow_numbers=True)
    lifecycle_path = case / "investigation" / "investigation_state.json"
    expected_lifecycle = _read(lifecycle_path).get("client_lifecycle", {}).get("state") if lifecycle_path.exists() else None
    if metadata.get("client_lifecycle_state") != expected_lifecycle and not (
        expected_lifecycle == "DELIVERABLE" and metadata.get("client_lifecycle_state") == "FINALIZABLE"
    ):
        raise ValueError("Le rapport doit conserver l'état du lifecycle client canonique.")
    _require_text(model.get("executive_summary", {}).get("message"), "executive_summary/message", max_length=500)
    expected_cards = {
        (decision["decision_id"], action_id)
        for decision in decisions.values()
        for action_id in (decision.get("considered_action_ids", decision.get("selected_action_ids", decision.get("action_ids", []))) if decision["decision"] in {"NO_ECONOMIC_CASE", "OPERATIONALLY_NOT_JUSTIFIED"} else decision.get("selected_action_ids", decision.get("action_ids", [])))
    }
    actual_cards = {(item.get("decision_ref"), item.get("action_ref")) for item in model.get("decision_cards", [])}
    if actual_cards != expected_cards:
        raise ValueError("Le rapport doit représenter chaque action correspondant à une décision Goal B client-facing.")
    seen_actions: set[str] = set()
    for card in model.get("decision_cards", []):
        action_id = card.get("action_ref")
        decision = decisions.get(card.get("decision_ref"))
        if action_id not in actions or not decision or card.get("decision") != decision.get("decision"):
            raise ValueError("Une carte client ne peut pas modifier une décision ou une action Goal B.")
        selected = set(decision.get("selected_action_ids", decision.get("action_ids", [])))
        considered = set(decision.get("considered_action_ids", selected))
        allowed = considered if decision["decision"] in {"NO_ECONOMIC_CASE", "OPERATIONALLY_NOT_JUSTIFIED"} else selected
        if action_id not in allowed:
            raise ValueError("Une carte client ne peut pas promouvoir une action hors de sa décision Goal B.")
        if card.get("considered_action_ref") != (action_id if action_id in considered else None):
            raise ValueError("La carte doit distinguer une action considérée d'une action sélectionnée.")
        if card.get("client_directive") != DECISION_LABELS[decision["decision"]]:
            raise ValueError("La directive client doit être dérivée de la décision Goal B exacte.")
        claim_refs = card.get("claim_refs", {})
        if set(claim_refs.get("finding_ids", [])) != set(actions[action_id]["finding_ids"]) or set(actions[action_id]["finding_ids"]) - set(findings):
            raise ValueError("Une carte doit référencer les findings Goal A réels de son action.")
        if claim_refs.get("decision_id") != decision["decision_id"] or claim_refs.get("action_id") != action_id:
            raise ValueError("La chaîne carte → décision → action doit rester locale et explicite.")
        expected_economic_refs = [action_id] if action_id in calculations else []
        if claim_refs.get("economic_calculation_refs") != expected_economic_refs:
            raise ValueError("Une carte ne peut référencer que le calcul économique de sa propre action.")
        if card.get("evidence_level") != EVIDENCE_LABELS.get(decision.get("technical_confidence"), "Non calibré"):
            raise ValueError("Le niveau de preuve client ne peut pas augmenter la confiance Goal B.")
        claims = card.get("claims")
        if not isinstance(claims, dict) or set(claims) != set(_CARD_CLAIM_TYPES):
            raise ValueError("Toute carte doit conserver ses claims structurés.")
        for field, kind in _CARD_CLAIM_TYPES.items():
            _validate_claim(claims[field], label=f"model/{card.get('card_id')}/{field}", decisions=decisions, actions=actions, findings=findings, constraints=constraints, calculations=calculations, dataset_ids=dataset_ids, no_finding=no_finding, expected_action_id=action_id, expected_decision_id=decision["decision_id"], expected_kind=kind)
            if card.get(field) != claims[field].get("text"):
                raise ValueError("Le texte affiché d'une carte doit provenir de son claim validé.")
        if action_id in calculations:
            economic = card.get("economic_impact")
            if not isinstance(economic, dict) or economic.get("saving_status") == "VERIFIED":
                raise ValueError("Une économie client doit être un claim potentiel/attendu, jamais vérifié sans post-action.")
            expected = _economic_claim(calculations[action_id])
            if economic != expected:
                raise ValueError("Le claim économique client diffère du calcul déterministe Goal B.")
        relevant_hard = [item for item in state.get("operational_constraints", []) if item.get("hard") and item.get("material") and action_id in item.get("affected_action_ids", [])]
        expected_constraint_refs = [item["constraint_id"] for item in relevant_hard]
        if claim_refs.get("constraint_refs") != expected_constraint_refs:
            raise ValueError("Une carte ne peut afficher que les contraintes matérielles de sa propre action.")
        expected_constraints = [{"constraint_ref": item["constraint_id"], "description": item["description"], "hard": item["hard"], "material": item["material"]} for item in relevant_hard]
        if card.get("operational_constraints") != expected_constraints:
            raise ValueError("Les contraintes affichées doivent être celles de l'action concernée, sans ajout ni omission.")
        if card.get("next_step") != _decision_next_step(decision, actions[action_id]):
            raise ValueError("La prochaine étape client doit être adaptée à la décision Goal B exacte.")
        seen_actions.add(action_id)
    if not findings:
        if not isinstance(no_finding, dict) or model.get("decision_cards"):
            raise ValueError("Le rapport no-finding ne peut pas inventer une action.")
    if model.get("claim_fidelity", {}).get("decision_strengthened") is not False:
        raise ValueError("Goal C ne peut jamais renforcer une décision Goal B.")
    for group in model.get("alternative_groups", []):
        if not group.get("not_additive"):
            raise ValueError("Les alternatives doivent rester explicitement non additives.")
    evidence_ids = {item.get("evidence_id") for item in state.get("goal_b_evidence", [])}
    if set(model.get("client_dialogue", {}).get("resolved_goal_b_evidence_refs", [])) - evidence_ids:
        raise ValueError("Le rapport client référence une preuve Goal B inexistante.")
    total = model.get("executive_summary", {}).get("economic_total")
    if total is not None and total.get("scenario_used_as_expected") == "HIGH":
        raise ValueError("Le scénario HIGH ne peut pas devenir une valeur attendue client.")
    for item in model.get("no_action_items", []):
        _require_text(item.get("title"), "model/no-action/title", max_length=150)
        claim = _validate_claim(item.get("claim"), label="model/no-action", decisions=decisions, actions=actions, findings=findings, constraints=constraints, calculations=calculations, dataset_ids=dataset_ids, no_finding=no_finding)
        if claim["claim_type"] not in {"NO_ACTION_REQUIRED", "NO_ACTION_ECONOMIC", "NO_ACTION_OPERATIONAL", "INSUFFICIENT_TO_DECIDE"}:
            raise ValueError("Un no-action client ne peut pas contenir une recommandation positive.")
        if item.get("explanation") != claim.get("text"):
            raise ValueError("Un no-action client doit afficher le texte de son claim sourcé.")
    for item in model.get("what_we_checked", []):
        _validate_claim(item, label="model/what-we-checked", decisions=decisions, actions=actions, findings=findings, constraints=constraints, calculations=calculations, dataset_ids=dataset_ids, no_finding=no_finding, expected_kind="WHAT_WAS_CHECKED")
    for chart in model.get("charts", []):
        for field in ("title", "purpose", "caption", "axis_x", "axis_y", "legend", "explains"):
            _require_text(chart.get(field), f"chart/{field}", max_length=350, allow_numbers=True)
        if chart.get("dataset_ref") not in dataset_ids or set(chart.get("claim_refs", [])) - dataset_ids:
            raise ValueError("Un graphique client doit rester attaché à un dataset Goal A réel.")
    appendix = model.get("technical_appendix", {})
    _require_text(appendix.get("method"), "appendix/method", max_length=500)
    for value in appendix.get("limitations", []):
        _require_text(value, "appendix/limitation", max_length=320)
    for source in appendix.get("sources", []):
        _require_text(source.get("label"), "appendix/source", max_length=200, allow_numbers=True)
    # Toute chaîne réellement rendue passe la même barrière de confidentialité,
    # y compris les valeurs remontées de Goal B (contraintes, alternatives,
    # validation) qui ne sont pas du texte narratif Codex.
    visible: list[tuple[str, Any]] = []
    for card in model.get("decision_cards", []):
        visible.extend([(f"card/{card.get('card_id')}/headline", card.get("headline")), ("card/directive", card.get("client_directive")), ("card/evidence", card.get("evidence_level"))])
        for constraint in card.get("operational_constraints", []):
            visible.append(("card/constraint", constraint.get("description")))
        if isinstance(card.get("next_step"), dict):
            visible.append(("card/next-step/title", card["next_step"].get("title")))
            visible.extend(("card/next-step", value) for value in card["next_step"].get("details", {}).values())
    for group in model.get("alternative_groups", []):
        for option in group.get("options", []):
            visible.extend(("alternative", option.get(field)) for field in ("title", "downtime", "operational_burden", "major_uncertainty"))
    for request in model.get("client_dialogue", {}).get("pending_questions", []):
        visible.append(("client-question", request.get("question")))
    for label, value in visible:
        _require_text(value, label, max_length=700, allow_numbers=True)


def _pdf_text(value: str) -> bytes:
    return value.encode("cp1252", errors="replace").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _wrap(text: str, width: int = 82) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        proposal = (current + " " + word).strip()
        if len(proposal) > width and current:
            lines.append(current)
            current = word
        else:
            current = proposal
    return lines + ([current] if current else [])


@dataclass
class _PdfPage:
    commands: list[str]
    y: float = 790.0

    def text(self, value: str, *, size: int = 10, bold: bool = False, gap: float = 4.0) -> None:
        for line in _wrap(value, 70 if size >= 14 else 88):
            if self.y < 60:
                raise OverflowError("page overflow")
            encoded = _pdf_text(line).decode("latin-1")
            font = "F2" if bold else "F1"
            self.commands.append(f"BT /{font} {size} Tf 48 {self.y:.1f} Td ({encoded}) Tj ET")
            self.y -= size + gap
        self.y -= gap

    def line(self) -> None:
        self.commands.append(f"0.75 w 48 {self.y:.1f} m 547 {self.y:.1f} l S")
        self.y -= 12


def _png_rgb(path: Path) -> tuple[int, int, bytes]:
    raw = path.read_bytes()
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Chart PNG invalide.")
    cursor, width, height, parts = 8, None, None, []
    while cursor < len(raw):
        size = int.from_bytes(raw[cursor:cursor + 4], "big")
        kind, payload = raw[cursor + 4:cursor + 8], raw[cursor + 8:cursor + 8 + size]
        cursor += 12 + size
        if kind == b"IHDR":
            width, height, depth, color = int.from_bytes(payload[:4], "big"), int.from_bytes(payload[4:8], "big"), payload[8], payload[9]
            if depth != 8 or color != 2:
                raise ValueError("Chart PNG RGB 8-bit requis.")
        elif kind == b"IDAT":
            parts.append(payload)
        elif kind == b"IEND":
            break
    decoded = zlib.decompress(b"".join(parts))
    stride = (width or 0) * 3
    rows = []
    for row in range(height or 0):
        start = row * (stride + 1)
        if decoded[start] != 0:
            raise ValueError("Filtre PNG non supporté.")
        rows.append(decoded[start + 1:start + 1 + stride])
    if width is None or height is None:
        raise ValueError("Dimensions PNG absentes.")
    return width, height, zlib.compress(b"".join(rows), 6)


def _render_pages(model: dict[str, Any], model_path: Path) -> tuple[list[_PdfPage], list[tuple[str, int, int, bytes]]]:
    pages: list[_PdfPage] = []
    images: list[tuple[str, int, int, bytes]] = []

    def page() -> _PdfPage:
        result = _PdfPage([])
        pages.append(result)
        return result

    def needed(value: str, size: int = 10) -> float:
        return len(_wrap(value, 70 if size >= 14 else 88)) * (size + 4.0) + 8.0

    def add(current: _PdfPage, value: str, *, size: int = 10, bold: bool = False, reserve: float = 0.0) -> _PdfPage:
        if current.y - needed(value, size) - reserve < 58:
            current = page()
        current.text(value, size=size, bold=bold)
        return current

    def section(current: _PdfPage, heading: str, value: str) -> _PdfPage:
        current = add(current, heading, size=10, bold=True, reserve=needed(value, 10))
        return add(current, value, size=10)

    metadata, summary = model["metadata"], model["executive_summary"]
    current = page()
    current = add(current, metadata["report_title"].upper(), size=19, bold=True)
    current = add(current, metadata["site_name"], size=13, bold=True)
    current = add(current, "Période analysée : " + metadata["analysis_period"])
    current.line()
    current = add(current, "Décision en bref", size=14, bold=True)
    current = add(current, summary["message"], size=11)
    counters = f"{summary['recommended_actions']} action(s) recommandée(s) · {summary['verify_first']} point(s) à vérifier · {summary['monitor']} élément(s) à surveiller · {summary['no_action_items']} conclusion(s) sans action"
    current = add(current, counters, bold=True)
    total = summary.get("economic_total")
    if total:
        current = add(current, "Potentiel économique validement agrégable : " + total["display"], size=12, bold=True)
    for card in model["decision_cards"][:3]:
        current = add(current, card["client_directive"] + " — " + card["headline"], size=11, bold=True, reserve=needed(card["why_this_matters"]))
        current = add(current, card["why_this_matters"])
        if card.get("economic_impact", {}).get("annual_net_benefit"):
            current = add(current, "Impact potentiel : " + card["economic_impact"]["annual_net_benefit"]["display"], bold=True)
    for request in model.get("client_dialogue", {}).get("pending_questions", []):
        current = add(current, "Information utile pour confirmer la suite", size=11, bold=True, reserve=needed(request["question"]))
        current = add(current, request["question"])
    for card in model["decision_cards"]:
        current = add(current, card["client_directive"].upper(), size=13, bold=True, reserve=needed(card["headline"], 16) + 80)
        current = add(current, card["headline"], size=16, bold=True)
        current.line()
        for heading, key in (("Ce que nous avons constaté", "what_we_found"), ("Pourquoi cela compte", "why_this_matters"), ("Contexte de décision", "contextual_rationale"), ("Ce qui reste à clarifier", "uncertainty")):
            current = section(current, heading, card[key])
        if card.get("economic_impact", {}).get("annual_net_benefit"):
            impact = card["economic_impact"]
            current = add(current, "Impact économique potentiel", size=10, bold=True)
            current = add(current, "Bénéfice annuel net : " + impact["annual_net_benefit"]["display"])
            if impact.get("intervention_cost"):
                current = add(current, "Coût d'intervention : " + impact["intervention_cost"]["display"])
        current = add(current, "Niveau de preuve : " + card["evidence_level"], bold=True)
        for constraint in card.get("operational_constraints", []):
            current = add(current, "Contrainte opérationnelle : " + constraint["description"])
        if card.get("next_step"):
            step = card["next_step"]
            current = add(current, step["title"], size=10, bold=True)
            labels = {
                "metric": "Mesure", "expected_direction": "Attendu", "comparison_window": "Période", "confounders": "À tenir compte",
                "minimum_evidence": "Critère", "what_it_resolves": "Information", "decision_that_can_change": "Décision concernée",
                "cost_or_burden": "Effort", "why_worth_it": "Pourquoi",
            }
            for field, value in step.get("details", {}).items():
                current = add(current, f"{labels.get(field, 'Détail')} : {value}.")
    if model["no_action_items"] or model["what_we_checked"] or model["alternative_groups"]:
        current = add(current, "Ce que nous avons vérifié", size=14, bold=True)
        for item in model["what_we_checked"]:
            current = add(current, "• " + item["text"])
        for item in model["no_action_items"]:
            current = add(current, item["title"], size=11, bold=True, reserve=needed(item["explanation"]))
            current = add(current, item["explanation"])
        for group in model["alternative_groups"]:
            # Deux alternatives doivent rester lisibles comme une comparaison,
            # pas être séparées par un saut de page après leur seul titre.
            current = add(current, "Options à comparer — non cumulables", size=11, bold=True, reserve=230)
            for option in group["options"]:
                line = option["title"]
                if option["economic_impact"] and option["economic_impact"]["annual_net_benefit"]:
                    line += " : " + option["economic_impact"]["annual_net_benefit"]["display"]
                cost_line = None
                if option.get("economic_impact", {}).get("intervention_cost"):
                    cost_line = "Coût : " + option["economic_impact"]["intervention_cost"]["display"] + "; retour : " + ("non calculable" if option.get("payback_years") is None else f"{option['payback_years']:.1f} an(s)")
                detail_line = "Arrêt : " + option["downtime"] + "; charge opérationnelle : " + option["operational_burden"] + "; incertitude : " + option["major_uncertainty"]
                reserve = needed(cost_line or "", 9) + needed(detail_line, 9) + 10
                current = add(current, line, bold=option.get("current_preference", False), reserve=reserve)
                if cost_line:
                    current = add(current, cost_line, size=9)
                current = add(current, detail_line, size=9)
    if model["charts"] or model["technical_appendix"]:
        current = add(current, "Sources, méthode et limites", size=14, bold=True)
        current = add(current, model["technical_appendix"]["method"])
        for limitation in model["technical_appendix"].get("limitations", []):
            current = add(current, "Limite : " + limitation)
        current = add(current, "Sources principales", size=10, bold=True)
        for source in model["technical_appendix"]["sources"][:6]:
            current = add(current, "• " + source["label"])
        for index, chart in enumerate(model["charts"], start=1):
            path = model_path.parent / chart["relative_path"]
            width, height, compressed = _png_rgb(path)
            draw_w, draw_h = 430, min(190, 430 * height / width)
            if current.y - draw_h - 86 < 58:
                current = page()
            current = add(current, "Graphique — " + chart["title"], size=11, bold=True)
            current = add(current, "Axe X : " + chart["axis_x"] + ". Axe Y : " + chart["axis_y"] + ".", size=9)
            current = add(current, "Légende : " + chart["legend"], size=9)
            image_name = f"Im{index}"
            images.append((image_name, width, height, compressed))
            y = current.y - draw_h
            current.commands.append(f"q {draw_w:.1f} 0 0 {draw_h:.1f} 80 {y:.1f} cm /{image_name} Do Q")
            current.y = y - 12
            current = add(current, chart["caption"], size=9)
    current = add(current, metadata["regulatory_notice"], size=8)
    return pages, images


def render_client_report_pdf(model: dict[str, Any], model_path: str | Path, pdf_path: str | Path, *, case_directory: str | Path) -> dict[str, Any]:
    """Rendu PDF seulement après revalidation complète du modèle à l'instant T."""
    validate_client_report_model(model, case_directory)
    model_file = Path(model_path)
    pages, images = _render_pages(model, model_file)
    if not 1 <= len(pages) <= 8:
        raise ValueError("Le rapport client doit rester compact et contenir entre une et huit pages.")
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_object_ids = [3 + index for index in range(len(pages))]
    objects.append(("<< /Type /Pages /Kids [" + " ".join(f"{identifier} 0 R" for identifier in page_object_ids) + f"] /Count {len(pages)} >>").encode())
    font1 = 3 + len(pages)
    font2 = font1 + 1
    image_ids = {name: font2 + 1 + index for index, (name, _, _, _) in enumerate(images)}
    content_ids = {index: font2 + 1 + len(images) + index for index in range(len(pages))}
    for index, page in enumerate(pages):
        image_refs = " ".join(f"/{name} {image_ids[name]} 0 R" for name, *_ in images)
        resources = f"<< /Font << /F1 {font1} 0 R /F2 {font2} 0 R >> /XObject << {image_refs} >> >>"
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources {resources} /Contents {content_ids[index]} 0 R >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    for _, width, height, compressed in images:
        objects.append(f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(compressed)} >>\nstream\n".encode() + compressed + b"\nendstream")
    for page in pages:
        stream = ("\n".join(page.commands) + "\n").encode("latin-1", errors="replace")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"endstream")
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode())
        output.extend(obj)
        output.extend(b"\nendobj\n")
    startxref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f\n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n\n".encode())
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode())
    target = Path(pdf_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(bytes(output))
    return {"pdf_path": str(target), "page_count": len(pages), "renderer": "stdlib_minimal_pdf_v2", "contains_client_internal_ids": False, "validated_immediately_before_render": True}


def generate_client_report(case_directory: str | Path, narrative: dict[str, Any], *, output_directory: str | Path | None = None) -> dict[str, Any]:
    case = Path(case_directory)
    target = Path(output_directory) if output_directory else case / "outputs" / "client_report"
    model = build_client_report_model(case, narrative, output_directory=target)
    model_path = target / "CLIENT_REPORT_MODEL.json"
    rendered = render_client_report_pdf(model, model_path, target / "ENERGY_ANALYSIS_REPORT.pdf", case_directory=case)
    _write(target / "CLIENT_REPORT_DELIVERY.json", {"schema_version": 1, "model": "CLIENT_REPORT_MODEL.json", "pdf": "ENERGY_ANALYSIS_REPORT.pdf", "rendered": rendered, "claim_validation": "passed"})
    return {"model": model, "model_path": model_path, **rendered}
