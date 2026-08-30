"""Livraison client Goal C : modèle fidèle, graphiques explicitement choisis et PDF léger.

Codex fournit le récit client (priorités, explications, langage métier). Python
résout les références Goal A/B, produit les nombres et le PDF, et refuse toute
altération structurelle de la décision ou des claims quantitatifs.
"""
from __future__ import annotations

import csv
import json
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from energy_mvp.charts import write_line_chart
from operational_economics import SCENARIOS, aggregate_declared_portfolio


DECISION_LABELS = {
    "ACT_NOW": "Action recommandée",
    "INVESTIGATE_FIRST": "À vérifier avant d'investir",
    "MONITOR": "À surveiller",
    "DEFER": "À planifier",
    "DO_NOTHING": "Aucune action nécessaire",
    "NO_ECONOMIC_CASE": "Pas suffisamment rentable actuellement",
    "OPERATIONALLY_NOT_JUSTIFIED": "Économie possible, mais action non recommandée",
    "INSUFFICIENT_FOR_ECONOMIC_DECISION": "Informations insuffisantes pour décider",
}
EVIDENCE_LABELS = {"HIGH": "Fort", "MEDIUM": "Modéré", "LOW": "Limité", "NOT_CALIBRATED": "Non calibré"}
SAVING_STATUS = {"POTENTIAL", "EXPECTED", "VERIFIED"}
_FORBIDDEN_NARRATIVE = re.compile(r"\b(verified savings|économie vérifiée|act_now|investigate_first|find-[a-z0-9-]+|art-[a-z0-9-]+|ds-[a-z0-9-]+)\b", re.IGNORECASE)


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Objet JSON attendu : {path}")
    return payload


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require_text(value: Any, label: str, *, max_length: int = 700) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
        raise ValueError(f"{label} doit être un texte client non vide et concis.")
    if _FORBIDDEN_NARRATIVE.search(value):
        raise ValueError(f"{label} expose un identifiant interne ou une formulation interdite.")
    if re.search(r"\d", value):
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


def _validate_narrative(narrative: dict[str, Any], action_ids: set[str]) -> None:
    if not isinstance(narrative, dict):
        raise ValueError("Le contenu narratif Codex doit être un objet.")
    _require_text(narrative.get("site_name"), "site_name", max_length=100)
    _require_text(narrative.get("executive_message"), "executive_message", max_length=500)
    cards = narrative.get("cards", {})
    if not isinstance(cards, dict) or set(cards) - action_ids:
        raise ValueError("Les récits de cartes doivent référencer des actions Goal B réelles.")
    for action_id, card in cards.items():
        if not isinstance(card, dict):
            raise ValueError(f"Carte narrative {action_id} invalide.")
        for field in ("headline", "what_we_found", "why_this_matters", "recommendation", "uncertainty"):
            _require_text(card.get(field), f"Carte {action_id}/{field}")
    for item in narrative.get("no_action_items", []):
        if not isinstance(item, dict):
            raise ValueError("Élément no-action invalide.")
        _require_text(item.get("title"), "no-action/title", max_length=150)
        _require_text(item.get("explanation"), "no-action/explanation")
    for item in narrative.get("what_we_checked", []):
        _require_text(item, "what_we_checked", max_length=260)
    for item in narrative.get("limitations", []):
        _require_text(item, "limitation", max_length=320)
    if "method" in narrative:
        _require_text(narrative["method"], "method", max_length=500)


def _resolve_chart_requests(case: Path, narrative: dict[str, Any], output_dir: Path) -> list[dict[str, Any]]:
    canonical = _read(case / "derived" / "canonical_case.json")
    datasets = {item["dataset_id"]: item for item in canonical.get("available_datasets", [])}
    charts: list[dict[str, Any]] = []
    for index, request in enumerate(narrative.get("chart_requests", []), start=1):
        if not isinstance(request, dict) or request.get("type") != "ENERGY_SERIES":
            raise ValueError("Seul un graphique ENERGY_SERIES explicitement demandé est supporté.")
        dataset = datasets.get(request.get("dataset_id"))
        if not dataset or not dataset.get("analytically_usable") or dataset.get("role") not in {"ENERGY_INTERVAL_SERIES", "POWER_SERIES"}:
            raise ValueError("Le graphique doit référencer une série Goal A réellement exploitable.")
        title = _require_text(request.get("title"), "chart/title", max_length=140)
        purpose = _require_text(request.get("purpose"), "chart/purpose", max_length=260)
        source = case / str(dataset["normalized_file"])
        values: list[float] = []
        with source.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                raw = row.get("energy_kwh") or row.get("power_kw") or row.get("measurement")
                try:
                    values.append(float(raw))
                except (TypeError, ValueError):
                    continue
        if len(values) < 2:
            raise ValueError("Un graphique client exige au moins deux observations numériques.")
        filename = f"chart_{index:02d}.png"
        path = output_dir / "charts" / filename
        write_line_chart({"energy": values}, path, title=title, zero_floor=True)
        charts.append({"chart_id": f"CHART-{index:02d}", "type": "ENERGY_SERIES", "title": title, "purpose": purpose, "dataset_ref": dataset["dataset_id"], "relative_path": f"charts/{filename}", "claim_refs": [dataset["dataset_id"]]})
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
        for action_id in selected:
            action = actions[action_id]
            if action_id not in narrative.get("cards", {}):
                raise ValueError(f"Codex doit fournir un récit client pour l'action sélectionnée {action_id}.")
            linked_findings = [findings[item] for item in action["finding_ids"]]
            hard_constraints = [item for item in constraints if item.get("hard") and item.get("material") and action_id in item.get("affected_action_ids", [])]
            assessment_ids = {item.get("constraint_id") for item in decision.get("constraint_assessments", [])}
            if any(item["constraint_id"] not in assessment_ids for item in hard_constraints):
                raise ValueError("Une contrainte dure pertinente ne peut pas disparaître du rapport client.")
            calc = calculations.get(action_id)
            card = {
                "card_id": f"CARD-{action_id}", "action_ref": action_id,
                "decision": decision["decision"], "client_decision": DECISION_LABELS[decision["decision"]],
                "headline": narrative["cards"][action_id]["headline"],
                "what_we_found": narrative["cards"][action_id]["what_we_found"],
                "why_this_matters": narrative["cards"][action_id]["why_this_matters"],
                "recommendation": narrative["cards"][action_id]["recommendation"],
                "uncertainty": narrative["cards"][action_id]["uncertainty"],
                "observed": [item["observation"] for item in linked_findings],
                "inferred": [explanation for item in linked_findings for explanation in item.get("possible_explanations", [])],
                "evidence_level": EVIDENCE_LABELS.get(decision.get("technical_confidence"), "Non calibré"),
                "operational_constraints": [{"description": item["description"], "hard": item["hard"], "material": item["material"]} for item in hard_constraints],
                "next_step": decision.get("evidence_acquisition"),
                "validation_plan": action.get("validation_plan"),
                "economic_impact": None if calc is None else _economic_claim(calc),
                "claim_refs": {"finding_ids": action["finding_ids"], "decision_id": decision["decision_id"], "action_id": action_id},
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
        groups.append({
            "relationship_ref": relation["relationship_id"], "type": relation["type"], "rationale": relation["rationale"],
            "options": [{"action_ref": action_id, "title": actions[action_id]["title"], "economic_impact": None if action_id not in calculations else _economic_claim(calculations[action_id])} for action_id in members],
            "not_additive": True,
        })
    return groups


def _portfolio_total(state: dict[str, Any]) -> dict[str, Any] | None:
    decision = state.get("decisions", [None])[0]
    if not decision:
        return None
    selected = decision.get("selected_action_ids", decision.get("action_ids", []))
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
    case = Path(case_directory)
    findings, no_finding = _goal_a_findings(case)
    state_path = case / "investigation" / "economic_decision_state.json"
    if not state_path.exists():
        raise ValueError("Goal C exige un état économique Goal B persistant.")
    state = _read(state_path)
    actions = {item["action_id"] for item in state.get("candidate_actions", [])}
    _validate_narrative(narrative, actions)
    decisions = state.get("decisions", [])
    if len(decisions) > 1:
        raise ValueError("Goal C attend une décision Goal B courante unique.")
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
    no_action_items = list(narrative.get("no_action_items", []))
    if not findings and not no_action_items:
        raise ValueError("Un rapport no-finding exige une explication client utile.")
    evidence_by_request = {item.get("request_id") for item in state.get("goal_b_evidence", []) if item.get("request_id")}
    pending_questions = [
        {"request_ref": item["request_id"], "question": item["client_question"], "decision_impact": item["decision_impact"]}
        for item in state.get("economic_requests", []) if item.get("request_id") not in evidence_by_request
    ]
    model = {
        "schema_version": 1,
        "kind": "CLIENT_REPORT_MODEL",
        "metadata": {"case_id": _read(case / "case_manifest.json")["case_id"], "site_name": narrative["site_name"], "report_title": narrative.get("report_title", "Analyse de performance énergétique"), "analysis_period": narrative.get("analysis_period", "Période disponible dans les données"), "regulatory_notice": "Cette prestation ne constitue pas un audit énergétique réglementaire."},
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
    if model.get("kind") != "CLIENT_REPORT_MODEL" or model.get("schema_version") != 1:
        raise ValueError("Schéma de modèle client invalide.")
    findings, no_finding = _goal_a_findings(case)
    state = _read(case / "investigation" / "economic_decision_state.json")
    decisions = {item["decision_id"]: item for item in state.get("decisions", [])}
    actions = {item["action_id"]: item for item in state.get("candidate_actions", [])}
    calculations = state.get("scenario_calculations", {})
    seen_actions: set[str] = set()
    for card in model.get("decision_cards", []):
        action_id = card.get("action_ref")
        decision = decisions.get(card.get("claim_refs", {}).get("decision_id"))
        if action_id not in actions or not decision or card.get("decision") != decision.get("decision"):
            raise ValueError("Une carte client ne peut pas modifier une décision ou une action Goal B.")
        if action_id not in decision.get("selected_action_ids", decision.get("action_ids", [])):
            raise ValueError("Une carte client ne peut pas promouvoir une action non sélectionnée.")
        if card.get("client_decision") != DECISION_LABELS[decision["decision"]]:
            raise ValueError("Le libellé client doit refléter la décision Goal B exacte.")
        if set(card.get("claim_refs", {}).get("finding_ids", [])) != set(actions[action_id]["finding_ids"]) or set(actions[action_id]["finding_ids"]) - set(findings):
            raise ValueError("Une carte doit référencer les findings Goal A réels de son action.")
        if card.get("evidence_level") != EVIDENCE_LABELS.get(decision.get("technical_confidence"), "Non calibré"):
            raise ValueError("Le niveau de preuve client ne peut pas augmenter la confiance Goal B.")
        if action_id in calculations:
            economic = card.get("economic_impact")
            if not isinstance(economic, dict) or economic.get("saving_status") == "VERIFIED":
                raise ValueError("Une économie client doit être un claim potentiel/attendu, jamais vérifié sans post-action.")
            expected = _economic_claim(calculations[action_id])
            if economic != expected:
                raise ValueError("Le claim économique client diffère du calcul déterministe Goal B.")
        relevant_hard = [item for item in state.get("operational_constraints", []) if item.get("hard") and item.get("material") and action_id in item.get("affected_action_ids", [])]
        shown = {item["description"] for item in card.get("operational_constraints", [])}
        if {item["description"] for item in relevant_hard} - shown:
            raise ValueError("Une contrainte dure pertinente a été omise du rapport client.")
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
    metadata, summary = model["metadata"], model["executive_summary"]
    current = page()
    current.text(metadata["report_title"].upper(), size=19, bold=True)
    current.text(metadata["site_name"], size=13, bold=True)
    current.text("Période analysée : " + metadata["analysis_period"])
    current.line()
    current.text("Décision en bref", size=14, bold=True)
    current.text(summary["message"], size=11)
    counters = f"{summary['recommended_actions']} action(s) recommandée(s) · {summary['verify_first']} point(s) à vérifier · {summary['no_action_items']} conclusion(s) sans action"
    current.text(counters, bold=True)
    total = summary.get("economic_total")
    if total:
        current.text("Potentiel économique validement agrégable : " + total["display"], size=12, bold=True)
    for card in model["decision_cards"][:3]:
        current.text(card["client_decision"] + " — " + card["headline"], size=12, bold=True)
        current.text(card["why_this_matters"])
        if card.get("economic_impact", {}).get("annual_net_benefit"):
            current.text("Impact potentiel : " + card["economic_impact"]["annual_net_benefit"]["display"], bold=True)
    for request in model.get("client_dialogue", {}).get("pending_questions", []):
        current.text("Information utile pour confirmer la suite", size=11, bold=True)
        current.text(request["question"])
    for card in model["decision_cards"]:
        current = page()
        current.text(card["client_decision"].upper(), size=14, bold=True)
        current.text(card["headline"], size=18, bold=True)
        current.line()
        for heading, key in (("Ce que nous avons constaté", "what_we_found"), ("Pourquoi cela compte", "why_this_matters"), ("Ce que nous recommandons", "recommendation"), ("Ce qui reste à clarifier", "uncertainty")):
            current.text(heading, size=11, bold=True)
            current.text(card[key])
        if card.get("economic_impact", {}).get("annual_net_benefit"):
            impact = card["economic_impact"]
            current.text("Impact économique potentiel", size=11, bold=True)
            current.text("Bénéfice annuel net : " + impact["annual_net_benefit"]["display"])
            if impact.get("intervention_cost"):
                current.text("Coût d'intervention : " + impact["intervention_cost"]["display"])
        current.text("Niveau de preuve : " + card["evidence_level"], bold=True)
        for constraint in card.get("operational_constraints", []):
            current.text("Contrainte opérationnelle : " + constraint["description"])
        if card.get("next_step"):
            current.text("À vérifier avant d'investir", size=11, bold=True)
            current.text(card["next_step"]["what_it_resolves"] + ". " + card["next_step"]["why_worth_it"])
        if card.get("validation_plan"):
            validation = card["validation_plan"]
            current.text("Comment vérifier après action", size=11, bold=True)
            current.text(f"Mesure : {validation['metric']}. Attendu : {validation['expected_direction']}. Fenêtre : {validation['comparison_window']}. À tenir compte : {validation['confounders']}.")
    if model["no_action_items"] or model["what_we_checked"] or model["alternative_groups"]:
        current = page()
        current.text("Ce que nous avons vérifié", size=17, bold=True)
        for item in model["what_we_checked"]:
            current.text("• " + item)
        for item in model["no_action_items"]:
            current.text(item["title"], size=12, bold=True)
            current.text(item["explanation"])
        for group in model["alternative_groups"]:
            current.text("Options à comparer — non cumulables", size=12, bold=True)
            for option in group["options"]:
                line = option["title"]
                if option["economic_impact"] and option["economic_impact"]["annual_net_benefit"]:
                    line += " : " + option["economic_impact"]["annual_net_benefit"]["display"]
                current.text(line)
    if model["charts"] or model["technical_appendix"]:
        current = page()
        current.text("Sources, méthode et limites", size=17, bold=True)
        current.text(model["technical_appendix"]["method"])
        for limitation in model["technical_appendix"].get("limitations", []):
            current.text("Limite : " + limitation)
        current.text("Sources principales", size=11, bold=True)
        for source in model["technical_appendix"]["sources"][:6]:
            current.text("• " + source["label"])
        for index, chart in enumerate(model["charts"], start=1):
            path = model_path.parent / chart["relative_path"]
            width, height, compressed = _png_rgb(path)
            image_name = f"Im{index}"
            images.append((image_name, width, height, compressed))
            draw_w, draw_h = 430, min(190, 430 * height / width)
            y = max(80, current.y - draw_h)
            current.commands.append(f"q {draw_w:.1f} 0 0 {draw_h:.1f} 80 {y:.1f} cm /{image_name} Do Q")
            current.y = y - 12
            current.text(chart["purpose"], size=9)
    current = page()
    current.text("À retenir", size=17, bold=True)
    current.text(summary["message"], size=12)
    current.text(metadata["regulatory_notice"], size=9)
    return pages, images


def render_client_report_pdf(model: dict[str, Any], model_path: str | Path, pdf_path: str | Path) -> dict[str, Any]:
    """Rendu PDF A4 sans dépendance externe; les données viennent du modèle validé."""
    model_file = Path(model_path)
    pages, images = _render_pages(model, model_file)
    if not 3 <= len(pages) <= 8:
        raise ValueError("Le rapport client normal doit contenir entre 3 et 8 pages.")
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
    return {"pdf_path": str(target), "page_count": len(pages), "renderer": "stdlib_minimal_pdf_v1", "contains_client_internal_ids": False}


def generate_client_report(case_directory: str | Path, narrative: dict[str, Any], *, output_directory: str | Path | None = None) -> dict[str, Any]:
    case = Path(case_directory)
    target = Path(output_directory) if output_directory else case / "outputs" / "client_report"
    model = build_client_report_model(case, narrative, output_directory=target)
    model_path = target / "CLIENT_REPORT_MODEL.json"
    rendered = render_client_report_pdf(model, model_path, target / "ENERGY_ANALYSIS_REPORT.pdf")
    _write(target / "CLIENT_REPORT_DELIVERY.json", {"schema_version": 1, "model": "CLIENT_REPORT_MODEL.json", "pdf": "ENERGY_ANALYSIS_REPORT.pdf", "rendered": rendered, "claim_validation": "passed"})
    return {"model": model, "model_path": model_path, **rendered}
