"""Fixtures compactes et exécutables de Goal C.1.

Elles décrivent des contrats Goal A/B distincts.  Elles ne sont ni des règles
de production ni un moteur de décision : Codex fournit explicitement chaque
décision et Python valide seulement ses références/calculs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from client_delivery import generate_client_report
from energy_mvp.client_lifecycle import mark_finalizable,record_existing_data_exhaustion

def _allow_report(case):
    record_existing_data_exhaustion(case,analysis_inventory_ref="derived/canonical_case.json",reviewed_sources=["evidence/intake_inventory.json","investigation/structured_findings.json"])
    mark_finalizable(case,conclusion_ref="investigation/economic_decision_state.json")
from client_intake_pipeline import create_client_case, ingest_client_drop, record_structured_findings
from operational_economics import calculate_economic_scenarios, initialize_economic_state, persist_economic_packet


SCENARIOS = ("LOW", "BASE", "HIGH")


def _action(action_id: str, finding_id: str, effect_id: str, title: str, *, burden: str = "Intervention ponctuelle planifiée.") -> dict:
    return {
        "action_id": action_id, "finding_ids": [finding_id], "title": title,
        "description": "Action candidate formulée par Codex dans une fixture de livraison.", "action_type": "maintenance",
        "technical_rationale": "Le finding technique est maintenu dans Goal A.", "operational_rationale": burden,
        "implementation_scope": "Équipement concerné.", "requires_professional_validation": True,
        "reversibility": "PARTIALLY_REVERSIBLE", "energy_effect_ref": effect_id,
        "validation_plan": {"metric": "Consommation comparable", "expected_direction": "baisse", "comparison_window": "deux semaines comparables", "confounders": "activité et ouverture", "minimum_evidence": "baisse persistante à activité comparable"},
        "downtime": "À planifier hors production", "major_uncertainty": "La cause physique exacte est confirmée par le professionnel.",
    }


def _effect(effect_id: str, finding_id: str, dataset_id: str, values: tuple[float, float, float]) -> dict:
    return {"effect_id": effect_id, "basis": "DIRECTLY_MEASURED_HISTORICAL_EXCESS", "baseline": "régimes comparables", "unit": "kWh/year", "period": "annual", "scenarios": dict(zip(SCENARIOS, values)), "finding_refs": [finding_id], "source_refs": [dataset_id]}


def _input(input_id: str, kind: str, value: float, unit: str, period: str, source_ref: str) -> dict:
    return {"input_id": input_id, "kind": kind, "value": value, "unit": unit, "currency": "EUR", "period": period, "provenance": "DOCUMENT_EXTRACTED", "status": "KNOWN", "source": {"source_refs": [source_ref]}, "confidence": "HIGH"}


def _calculation(effect: dict, action_id: str, capex: float, capex_id: str) -> dict:
    refs = {"energy_effect": {name: [effect["finding_refs"][0]] for name in SCENARIOS}, "tariff_per_kwh": {name: ["TAR-01"] for name in SCENARIOS}, "intervention_cost": {name: [capex_id] for name in SCENARIOS}}
    return calculate_economic_scenarios(effect, tariff_per_kwh={name: 0.20 for name in SCENARIOS}, intervention_cost={name: capex for name in SCENARIOS}, input_references=refs)


def _claim(action_id: str, decision_id: str, finding_id: str, _legacy_claim_type: str, *, constraint_refs: list[str] | None = None, why_this_matters: str | None = None) -> dict:
    refs = {"decision_ref": decision_id, "action_ref": action_id, "finding_refs": [finding_id], "constraint_refs": constraint_refs or [], "economic_refs": [action_id], "evidence_refs": []}
    return {
        "what_we_found": {**refs, "claim_type": "OBSERVATION", "text": "Le comportement étudié persiste dans les régimes comparables."},
        "why_this_matters": {**refs, "claim_type": "WHY_THIS_MATTERS", "text": why_this_matters or "Cette situation mérite une décision proportionnée à son coût et à l activité du site."},
        "contextual_rationale": {**refs, "claim_type": "CONTEXTUAL_RATIONALE", "text": "Le contexte opérationnel est pris en compte sans modifier la directive de décision."},
        "uncertainty": {**refs, "claim_type": "UNCERTAINTY", "text": "Les conditions de mise en œuvre doivent être confirmées avant engagement."},
    }


def _narrative(site: str, cards: dict[str, tuple[str, str, str, str, list[str]]], dataset_id: str, *, no_action: list[dict] | None = None, checked_finding: str | None = None, why_by_action: dict[str, str] | None = None) -> dict:
    card_payload = {action_id: {"headline": headline, "claims": _claim(action_id, decision_id, finding_id, claim_type, constraint_refs=constraint_refs, why_this_matters=(why_by_action or {}).get(action_id))} for action_id, (headline, decision_id, finding_id, claim_type, constraint_refs) in cards.items()}
    checked = []
    if checked_finding:
        checked = [{"claim_type": "WHAT_WAS_CHECKED", "decision_ref": next(iter(cards.values()))[1] if cards else None, "action_ref": next(iter(cards)) if cards else None, "finding_refs": [checked_finding], "constraint_refs": [], "economic_refs": [], "evidence_refs": [dataset_id], "text": "Les régimes disponibles et leur cohérence avec l activité du site."}]
    return {"site_name": site, "report_title": "Analyse de performance énergétique", "analysis_period": "Période de données fournie", "executive_message": "Les décisions proposées distinguent clairement ce qui mérite une action, une vérification ou aucune modification.", "cards": card_payload, "no_action_items": no_action or [], "what_we_checked": checked, "chart_requests": [{"type": "ENERGY_WITH_OPERATION_STATUS", "dataset_id": dataset_id, "title": "Consommation et activité", "purpose": "Le graphique répond à la question de la consommation pendant les régimes observés."}], "limitations": ["La validation après action reste nécessaire lorsque l intervention est engagée."], "method": "Les montants proviennent uniquement des calculs économiques déterministes validés."}


def _raw(root: Path) -> Path:
    raw = root / "raw_input"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "energy.csv").write_text("timestamp,energy_kwh,production\n2026-07-01 00:00,6,0\n2026-07-01 06:00,5,0\n2026-07-01 08:00,3,10\n2026-07-01 12:00,3,12\n2026-07-01 18:00,5,0\n", encoding="utf-8")
    (raw / "tariff.txt").write_text("Tarif : 0,20 EUR/kWh.", encoding="utf-8")
    (raw / "quote.txt").write_text("Devis de maintenance et de remplacement disponible.", encoding="utf-8")
    (raw / "schedule.txt").write_text("Production ouverte entre huit heures et dix-huit heures.", encoding="utf-8")
    return raw


def _case(root: Path, case_id: str, *, findings: list[dict], no_finding: dict | None = None) -> tuple[Path, dict[str, str], str]:
    case_root = root / case_id
    create_client_case(case_id.lower().replace("-", "_"), root=case_root)
    case = case_root / case_id.lower().replace("-", "_")
    ingest_client_drop(_raw(root), case)
    inventory = json.loads((case / "evidence" / "intake_inventory.json").read_text(encoding="utf-8"))
    refs = {item["raw_relative_path"]: item["artifact_id"] for item in inventory["artifacts"]}
    dataset_id = json.loads((case / "derived" / "canonical_case.json").read_text(encoding="utf-8"))["available_datasets"][0]["dataset_id"]
    record_structured_findings(case, findings, no_finding=no_finding)
    initialize_economic_state(case)
    return case, refs, dataset_id


def _finding(identifier: str) -> dict:
    return {"finding_id": identifier, "observation": "Écart récurrent dans les périodes comparables.", "status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "confidence": "MEDIUM", "possible_explanations": ["charge évitable", "service utile non documenté"], "provenance": ["evidence/dataset_provenance.json"], "recommended_next_analytical_step": "Contrôle proportionné au risque."}


def _decision(identifier: str, kind: str, action_ids: list[str], *, blocking: list[str] | None = None) -> dict:
    selected = action_ids if kind in {"ACT_NOW", "INVESTIGATE_FIRST", "MONITOR", "DEFER"} else []
    payload = {"decision_id": identifier, "decision": kind, "selected_action_ids": selected, "considered_action_ids": action_ids, "reason": "Décision explicitement formulée par Codex pour le contexte disponible.", "priority_reasoning": "Priorisation propre au cas client.", "technical_confidence": "MEDIUM", "economic_importance": "MEDIUM"}
    if kind == "INVESTIGATE_FIRST":
        payload["evidence_acquisition"] = {"what_it_resolves": "La cause et le coût réel de l intervention", "decision_that_can_change": "Investir ou ne pas investir", "cost_or_burden": "Contrôle ciblé peu coûteux", "why_worth_it": "Évite une dépense importante non justifiée"}
    if blocking:
        payload["blocking_constraint_ids"] = blocking
        payload["constraint_assessments"] = [{"constraint_id": item, "disposition": "BLOCKS", "rationale": "La contrainte doit être respectée."} for item in blocking]
    return payload


def generate(root: str | Path) -> dict[str, Path]:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    definitions = {
        "C-A": ("ACT_NOW", (24000, 24000, 24000), 450, "Action ciblée immédiatement rentable"),
        "C-B": ("INVESTIGATE_FIRST", (18000, 24000, 30000), 12000, "Vérifier avant investissement majeur"),
        "C-C": ("NO_ECONOMIC_CASE", (600, 600, 600), 900, "Problème réel mais gain insuffisant"),
        "C-D": ("OPERATIONALLY_NOT_JUSTIFIED", (9000, 9000, 9000), 500, "Optimisation non compatible avec la production"),
        "C-G": ("ACT_NOW", (24000, 24000, 24000), 450, "Montant précis préservé"),
        "C-H": ("ACT_NOW", (6000, 18000, 36000), 900, "Fourchette large préservée"),
        "C-I": ("OPERATIONALLY_NOT_JUSTIFIED", (8000, 8000, 8000), 400, "Charge opérationnelle disproportionnée"),
    }
    for fixture_id, (kind, values, capex, title) in definitions.items():
        finding_id, action_id, effect_id, decision_id = f"F-{fixture_id}", f"A-{fixture_id}", f"E-{fixture_id}", f"D-{fixture_id}"
        case, refs, dataset_id = _case(root, fixture_id, findings=[_finding(finding_id)])
        action = _action(action_id, finding_id, effect_id, title, burden="Modification quotidienne incompatible avec le rythme client." if fixture_id in {"C-D", "C-I"} else "Intervention ponctuelle planifiée.")
        effect = _effect(effect_id, finding_id, dataset_id, values)
        constraint_ids: list[str] = []
        constraints: list[dict] = []
        if kind == "OPERATIONALLY_NOT_JUSTIFIED":
            constraint_ids = [f"K-{fixture_id}"]
            constraints = [{"constraint_id": constraint_ids[0], "category": "PRODUCTION", "description": "La production et la fraîcheur ne permettent pas ce changement quotidien.", "source_status": "EXPLICIT", "source_refs": [refs["schedule.txt"]], "hard": True, "material": True, "affected_action_ids": [action_id]}]
        inputs = [_input("TAR-01", "electricity_tariff", .20, "EUR/kWh", "per_kwh", refs["tariff.txt"]), _input(f"CAP-{fixture_id}", "quote", capex, "EUR", "one_off", refs["quote.txt"])]
        decision = _decision(decision_id, kind, [action_id], blocking=constraint_ids)
        packet = {"technical_finding_refs": [{"finding_id": finding_id}], "economic_inputs": inputs, "scenario_assumptions": [], "candidate_actions": [action], "operational_constraints": constraints, "relationships": [], "combined_effects": {}, "scenario_calculations": {action_id: _calculation(effect, action_id, capex, f"CAP-{fixture_id}")}, "economic_requests": [], "decision": decision}
        persist_economic_packet(case, packet)
        claim_type = {"ACT_NOW": "ACTION_RECOMMENDED", "INVESTIGATE_FIRST": "VERIFY_BEFORE_INVESTING", "NO_ECONOMIC_CASE": "NO_ACTION_ECONOMIC", "OPERATIONALLY_NOT_JUSTIFIED": "NO_ACTION_OPERATIONAL"}[kind]
        no_action = [] if kind not in {"NO_ECONOMIC_CASE", "OPERATIONALLY_NOT_JUSTIFIED"} else [{"title": "Action non retenue", "claim": {"claim_type": claim_type, "decision_ref": decision_id, "action_ref": action_id, "finding_refs": [finding_id], "constraint_refs": constraint_ids, "economic_refs": [action_id], "evidence_refs": [], "text": "La décision conserve l économie théorique sans imposer une contrainte disproportionnée."}}]
        context = {
            "C-B": "Le remplacement envisagé engage un budget important alors qu un contrôle ciblé peut encore lever l incertitude avant cet engagement.",
            "C-D": "L économie théorique existe, mais avancer la production compromettrait la fraîcheur attendue des produits ; cette contrainte quotidienne est disproportionnée.",
            "C-I": "Le petit gain potentiel ne compense pas une consigne quotidienne supplémentaire ni la coordination durable demandée au personnel.",
        }
        narrative = _narrative(f"Fixture {fixture_id}", {action_id: (title, decision_id, finding_id, claim_type, constraint_ids)}, dataset_id, no_action=no_action, checked_finding=finding_id, why_by_action={action_id: context[fixture_id]} if fixture_id in context else None)
        _allow_report(case); generate_client_report(case, narrative)
        outputs[fixture_id] = case

    # C-E : no-finding Goal A réel et décision Goal B explicitement vide.
    case, _, dataset_id = _case(root, "C-E", findings=[], no_finding={"what_was_analyzed": "Données disponibles", "usable_period": "Période fournie", "operating_regimes": "Régime stable", "limitations": "Période courte", "monitoring_baseline_meaningful": True})
    persist_economic_packet(case, {"technical_finding_refs": [], "economic_inputs": [], "scenario_assumptions": [], "candidate_actions": [], "operational_constraints": [], "relationships": [], "combined_effects": {}, "scenario_calculations": {}, "economic_requests": [], "decision": _decision("D-C-E", "DO_NOTHING", [])})
    narrative = {"site_name": "Fixture C-E", "report_title": "Analyse de performance énergétique", "analysis_period": "Période de données fournie", "executive_message": "Aucune anomalie significative ne justifie une dépense corrective.", "cards": {}, "no_action_items": [{"title": "Aucune action corrective", "claim": {"claim_type": "NO_ACTION_REQUIRED", "decision_ref": "D-C-E", "action_ref": None, "finding_refs": [], "constraint_refs": [], "economic_refs": [], "evidence_refs": [], "no_finding_ref": "GOAL_A_NO_FINDING", "text": "Le fonctionnement observé ne justifie pas une intervention supplémentaire."}}], "what_we_checked": [{"claim_type": "WHAT_WAS_CHECKED", "decision_ref": "D-C-E", "action_ref": None, "finding_refs": [], "constraint_refs": [], "economic_refs": [], "evidence_refs": [dataset_id], "no_finding_ref": "GOAL_A_NO_FINDING", "text": "Les régimes disponibles et leur stabilité."}], "chart_requests": [], "limitations": ["La période servira de référence si l activité change."], "method": "La conclusion préserve le résultat no finding de Goal A."}
    _allow_report(case); generate_client_report(case, narrative)
    outputs["C-E"] = case

    # C-F : alternatives mutuellement exclusives, comparées sans somme.
    finding_id = "F-C-F"
    case, refs, dataset_id = _case(root, "C-F", findings=[_finding(finding_id)])
    repair, replacement = _action("A-C-F-REPAIR", finding_id, "E-C-F-REPAIR", "Réparation ciblée"), _action("A-C-F-REPLACE", finding_id, "E-C-F-REPLACE", "Remplacement complet")
    effects = [_effect("E-C-F-REPAIR", finding_id, dataset_id, (18000, 18000, 18000)), _effect("E-C-F-REPLACE", finding_id, dataset_id, (22000, 22000, 22000))]
    inputs = [_input("TAR-01", "electricity_tariff", .20, "EUR/kWh", "per_kwh", refs["tariff.txt"]), _input("CAP-REPAIR", "quote", 450, "EUR", "one_off", refs["quote.txt"]), _input("CAP-REPLACE", "quote", 3200, "EUR", "one_off", refs["quote.txt"])]
    packet = {"technical_finding_refs": [{"finding_id": finding_id}], "economic_inputs": inputs, "scenario_assumptions": [], "candidate_actions": [repair, replacement], "operational_constraints": [], "relationships": [{"relationship_id": "R-C-F", "type": "MUTUALLY_EXCLUSIVE", "action_a": repair["action_id"], "action_b": replacement["action_id"], "rationale": "Deux réponses au même équipement."}], "combined_effects": {}, "scenario_calculations": {repair["action_id"]: _calculation(effects[0], repair["action_id"], 450, "CAP-REPAIR"), replacement["action_id"]: _calculation(effects[1], replacement["action_id"], 3200, "CAP-REPLACE")}, "economic_requests": [], "decision": _decision("D-C-F", "ACT_NOW", [repair["action_id"], replacement["action_id"]])}
    # An alternative cannot be selected twice; select repair and keep replacement considered.
    packet["decision"]["selected_action_ids"] = [repair["action_id"]]
    persist_economic_packet(case, packet)
    narrative = _narrative("Fixture C-F", {repair["action_id"]: ("Réparer avant de remplacer", "D-C-F", finding_id, "ACTION_RECOMMENDED", [])}, dataset_id, checked_finding=finding_id)
    _allow_report(case); generate_client_report(case, narrative)
    outputs["C-F"] = case

    # C-J : une réponse client Goal B.4 est persistée, puis la livraison est
    # régénérée depuis l'état repris (request → GBE → économie → rapport).
    from workspace.generate_goal_b_4_e2e import generate as generate_b4
    case = generate_b4(root / "C-J")
    dataset_id = json.loads((case / "derived" / "canonical_case.json").read_text(encoding="utf-8"))["available_datasets"][0]["dataset_id"]
    narrative = _narrative("Fixture C-J", {"ACT-INSPECT-01": ("Inspection avant intervention", "DEC-B4-01", "FIND-EXCESS-01", "VERIFY_BEFORE_INVESTING", ["CONS-PROD-01"])}, dataset_id, checked_finding="FIND-EXCESS-01")
    _allow_report(case); generate_client_report(case, narrative)
    outputs["C-J"] = case

    # E2E C.1 : un même site porte quatre décisions distinctes et non sommées.
    finding_ids = ["F-MULTI-NOW", "F-MULTI-CHECK", "F-MULTI-MONITOR", "F-MULTI-OPS"]
    case, refs, dataset_id = _case(root, "C-MULTI", findings=[_finding(item) for item in finding_ids])
    action_ids = ["A-MULTI-NOW", "A-MULTI-CHECK", "A-MULTI-MONITOR", "A-MULTI-OPS"]
    effect_ids = ["E-MULTI-NOW", "E-MULTI-CHECK", "E-MULTI-MONITOR", "E-MULTI-OPS"]
    actions = [_action(action_id, finding_id, effect_id, title, burden="Modification quotidienne incompatible avec la production." if action_id.endswith("OPS") else "Intervention ponctuelle planifiée.") for action_id, finding_id, effect_id, title in zip(action_ids, finding_ids, effect_ids, ["Réparer maintenant", "Vérifier avant investissement", "Surveiller le régime", "Ne pas modifier les horaires"]) ]
    effects = [_effect(effect_id, finding_id, dataset_id, values) for effect_id, finding_id, values in zip(effect_ids, finding_ids, [(24000, 24000, 24000), (18000, 24000, 30000), (3000, 4000, 5000), (9000, 9000, 9000)])]
    inputs = [_input("TAR-01", "electricity_tariff", .20, "EUR/kWh", "per_kwh", refs["tariff.txt"])] + [_input(f"CAP-{index}", "quote", value, "EUR", "one_off", refs["quote.txt"]) for index, value in enumerate((450, 12000, 0, 500), start=1)]
    ops_constraint = {"constraint_id": "K-MULTI-OPS", "category": "PRODUCTION", "description": "Les horaires de production ne peuvent pas être déplacés sans perte de fraîcheur.", "source_status": "EXPLICIT", "source_refs": [refs["schedule.txt"]], "hard": True, "material": True, "affected_action_ids": ["A-MULTI-OPS"]}
    decisions = [_decision("D-MULTI-NOW", "ACT_NOW", ["A-MULTI-NOW"]), _decision("D-MULTI-CHECK", "INVESTIGATE_FIRST", ["A-MULTI-CHECK"]), _decision("D-MULTI-MONITOR", "MONITOR", ["A-MULTI-MONITOR"]), _decision("D-MULTI-OPS", "OPERATIONALLY_NOT_JUSTIFIED", ["A-MULTI-OPS"], blocking=["K-MULTI-OPS"])]
    packet = {"technical_finding_refs": [{"finding_id": item} for item in finding_ids], "economic_inputs": inputs, "scenario_assumptions": [], "candidate_actions": actions, "operational_constraints": [ops_constraint], "relationships": [], "combined_effects": {}, "scenario_calculations": {action_id: _calculation(effect, action_id, capex, f"CAP-{index}") for index, (action_id, effect, capex) in enumerate(zip(action_ids, effects, (450, 12000, 0, 500)), start=1)}, "economic_requests": [], "decisions": decisions}
    persist_economic_packet(case, packet)
    narrative = _narrative("Fixture multi-décision", {"A-MULTI-NOW": ("Réparer maintenant", "D-MULTI-NOW", "F-MULTI-NOW", "ACTION_RECOMMENDED", []), "A-MULTI-CHECK": ("Vérifier avant investissement", "D-MULTI-CHECK", "F-MULTI-CHECK", "VERIFY_BEFORE_INVESTING", []), "A-MULTI-MONITOR": ("Surveiller ce régime", "D-MULTI-MONITOR", "F-MULTI-MONITOR", "MONITOR", []), "A-MULTI-OPS": ("Ne pas modifier les horaires", "D-MULTI-OPS", "F-MULTI-OPS", "NO_ACTION_OPERATIONAL", ["K-MULTI-OPS"])}, dataset_id, no_action=[{"title": "Optimisation des horaires non retenue", "claim": {"claim_type": "NO_ACTION_OPERATIONAL", "decision_ref": "D-MULTI-OPS", "action_ref": "A-MULTI-OPS", "finding_refs": ["F-MULTI-OPS"], "constraint_refs": ["K-MULTI-OPS"], "economic_refs": ["A-MULTI-OPS"], "evidence_refs": [], "text": "Le gain potentiel ne justifie pas de perturber la production quotidienne."}}], checked_finding="F-MULTI-NOW")
    _allow_report(case); generate_client_report(case, narrative)
    outputs["C-MULTI"] = case
    return outputs


if __name__ == "__main__":
    generated = generate("examples/goal_c_1_fixtures")
    print(json.dumps({key: str(value) for key, value in generated.items()}, ensure_ascii=False, indent=2))
