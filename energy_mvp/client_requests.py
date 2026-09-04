"""Contrat unique des demandes client et sélection par valeur décisionnelle."""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

from .minimal_attribution import MicroQuestion, rank_micro_questions

REQUEST_TYPES = {"INFER_AUTOMATICALLY", "MICRO_QUESTION", "REQUEST_EXISTING_DOCUMENT",
                 "FIELD_OBSERVATION", "FIELD_VERIFICATION", "REQUEST_DATA_EXPORT",
                 "TEMPORARY_INSTRUMENTATION"}
DECISION_DIMENSIONS = {"evidence_level", "asset_attribution", "economic_materiality",
                       "investigation_priority", "field_action", "false_conclusion_risk"}
SOURCE_TYPES = {"CLIENT_DECLARATION", "EXISTING_DOCUMENT", "FIELD_OBSERVATION",
                "PREREGISTERED_TEST", "INSTRUMENT_MEASUREMENT"}
SOURCE_PRIORITY = {name: index for index, name in enumerate(("INFER_AUTOMATICALLY",
    "MICRO_QUESTION", "REQUEST_EXISTING_DOCUMENT", "FIELD_OBSERVATION",
    "FIELD_VERIFICATION", "REQUEST_DATA_EXPORT", "TEMPORARY_INSTRUMENTATION"))}
LEGACY_TYPE_MAP = {"question_metier": "MICRO_QUESTION", "ASK_CLIENT": "MICRO_QUESTION",
    "donnee_complementaire": "REQUEST_DATA_EXPORT", "REQUEST_DATA": "REQUEST_DATA_EXPORT",
    "test_terrain_simple": "FIELD_VERIFICATION", "FIELD_TEST": "FIELD_VERIFICATION",
    "REQUEST_DOCUMENT": "REQUEST_EXISTING_DOCUMENT", "REQUEST_TECHNICAL_EVIDENCE": "FIELD_VERIFICATION",
    "OPTIONAL_FUTURE_INSTRUMENTATION": "TEMPORARY_INSTRUMENTATION",
    "REQUEST_QUOTE": "REQUEST_EXISTING_DOCUMENT"}

def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip(): raise ValueError(f"{field} est requis.")
    return value.strip()

def _normal(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", value))

def semantic_key(request: dict[str, Any]) -> str:
    subject = [*request.get("related_hypothesis_ids", []), *request.get("related_component_ids", []),
               *request.get("related_finding_ids", [])]
    if subject: return "|".join(sorted(_normal(str(x)) for x in subject))
    hypotheses = sorted(_normal(str(x)) for x in request.get("hypotheses_distinguished", []))
    return "|".join([*hypotheses, _normal(str(request.get("client_question", "")))])

def normalize_request(candidate: dict[str, Any]) -> dict[str, Any]:
    rid = _text(candidate.get("request_id"), "request_id")
    rtype = LEGACY_TYPE_MAP.get(str(candidate.get("request_type")), candidate.get("request_type"))
    if rtype not in REQUEST_TYPES or rtype == "INFER_AUTOMATICALLY":
        raise ValueError(f"{rid}: request_type externe inconnu.")
    question = _text(candidate.get("client_question", candidate.get("ask_client")), f"{rid}/client_question")
    if len(question) < 12 or _normal(question) in {"plus de donnees", "davantage de donnees"}:
        raise ValueError(f"{rid}: demande trop vague.")
    distinguished = list(dict.fromkeys(str(x).strip() for x in candidate.get("hypotheses_distinguished", []) if str(x).strip()))
    if len(distinguished) < 2: raise ValueError(f"{rid}: deux hypothèses explicites sont requises.")
    plausible = candidate.get("plausible_answers")
    if plausible is None:
        impact = _text(candidate.get("decision_impact", candidate.get("information_value")), f"{rid}/decision_impact")
        plausible = [{"answer_id":"YES_OR_CONFIRMED","label":candidate.get("expected_if_true","Oui / confirmé"),"decision_effects":[impact]},
                     {"answer_id":"NO_OR_REFUTED","label":"Non / infirmé","decision_effects":[f"Alternative maintenue: {distinguished[-1]}"]}]
    if not isinstance(plausible, list) or len(plausible) < 2: raise ValueError(f"{rid}: deux réponses plausibles sont requises.")
    answers, signatures = [], set()
    for raw in plausible:
        aid, label = _text(raw.get("answer_id"), f"{rid}/answer_id"), _text(raw.get("label"), f"{rid}/label")
        effects = raw.get("decision_effects")
        if not isinstance(effects, list) or not effects or any(not str(x).strip() for x in effects):
            raise ValueError(f"{rid}/{aid}: decision_effects requis.")
        effects = [str(x).strip() for x in effects]; signatures.add(tuple(sorted(_normal(x) for x in effects)))
        answers.append({"answer_id": aid, "label": label, "decision_effects": effects})
    if len(signatures) < 2: raise ValueError(f"{rid}: les réponses plausibles ne changent aucune décision.")
    dimensions = list(dict.fromkeys(candidate.get("decision_impact_dimensions", ["false_conclusion_risk"])))
    if not dimensions or set(dimensions) - DECISION_DIMENSIONS: raise ValueError(f"{rid}: dimensions invalides.")
    source = candidate.get("expected_source_type") or {"MICRO_QUESTION":"CLIENT_DECLARATION",
        "REQUEST_EXISTING_DOCUMENT":"EXISTING_DOCUMENT", "FIELD_OBSERVATION":"FIELD_OBSERVATION",
        "FIELD_VERIFICATION":"PREREGISTERED_TEST", "REQUEST_DATA_EXPORT":"EXISTING_DOCUMENT",
        "TEMPORARY_INSTRUMENTATION":"INSTRUMENT_MEASUREMENT"}[rtype]
    if source not in SOURCE_TYPES: raise ValueError(f"{rid}: type de source invalide.")
    effort, availability, reliability, cost = (float(candidate.get("effort", 1)), float(candidate.get("availability",1)),
        float(candidate.get("reliability",.65)), float(candidate.get("source_cost",0)))
    if effort <= 0 or cost < 0 or not 0 <= availability <= 1 or not 0 <= reliability <= 1:
        raise ValueError(f"{rid}: effort/disponibilité/fiabilité/coût invalides.")
    importance = candidate.get("importance", "NON_BLOCKING")
    if importance not in {"BLOCKING", "NON_BLOCKING"}: raise ValueError(f"{rid}: importance invalide.")
    field = candidate.get("field_verification")
    if rtype in {"FIELD_OBSERVATION","FIELD_VERIFICATION","TEMPORARY_INSTRUMENTATION"}:
        required = {"what_to_check","asset_or_group","period_or_regime","why_discriminating","competent_role",
                    "safety_constraints","stop_condition","confirming_result","refuting_result","before_after_comparison"}
        if not isinstance(field, dict) or any(not str(field.get(k,"")).strip() for k in required):
            raise ValueError(f"{rid}: protocole terrain minimal incomplet.")
    result = {"request_id":rid,"request_type":rtype,"client_question":question,
        "internal_reason":_text(candidate.get("internal_reason", candidate.get("why_useful")),f"{rid}/internal_reason"),
        "target_role":_text(candidate.get("target_role",candidate.get("responsible_role")),f"{rid}/target_role"),
        "related_hypothesis_ids":list(dict.fromkeys(candidate.get("related_hypothesis_ids",[]))),
        "related_finding_ids":list(dict.fromkeys(candidate.get("related_finding_ids",[]))),
        "related_component_ids":list(dict.fromkeys(candidate.get("related_component_ids",[]))),
        "hypotheses_distinguished":distinguished,"plausible_answers":answers,
        "answer_by_hypothesis":dict(candidate.get("answer_by_hypothesis",{})),
        "decision_impact_dimensions":dimensions,"expected_effort":str(candidate.get("expected_effort",candidate.get("client_effort","effort minimal"))),
        "effort":effort,"availability":availability,"reliability":reliability,"source_cost":cost,
        "expected_source_type":source,"importance":importance,"field_verification":field}
    result["semantic_key"] = semantic_key(result); return result

def _voi(item: dict[str, Any]) -> float:
    hypotheses, mapping = item["hypotheses_distinguished"], item["answer_by_hypothesis"]
    if set(mapping) >= set(hypotheses):
        ranked = rank_micro_questions(hypotheses,[MicroQuestion(item["request_id"],item["client_question"],
            {h:str(mapping[h]) for h in hypotheses},item["effort"]+item["source_cost"],item["availability"],item["reliability"],item["expected_source_type"])])
        return float(ranked[0]["utility"]) if ranked else 0
    return len(item["decision_impact_dimensions"])/len(DECISION_DIMENSIONS)*item["availability"]*item["reliability"]/(item["effort"]+item["source_cost"]+1e-9)

def select_minimum_requests(candidates: Iterable[dict[str, Any]], *, max_requests: int = 3) -> dict[str, Any]:
    if not 1 <= max_requests <= 3: raise ValueError("max_requests doit être entre 1 et 3.")
    accepted, rejected = [], []
    for raw in candidates:
        try: item = normalize_request(raw)
        except (TypeError,ValueError) as exc: rejected.append({"request_id":str(raw.get("request_id","?")),"reason":str(exc)}); continue
        item["voi_score"] = round(_voi(item),9)
        if item["voi_score"] <= 0: rejected.append({"request_id":item["request_id"],"reason":"aucune valeur décisionnelle positive"}); continue
        accepted.append(item)
    by_key = {}
    for item in accepted:
        old = by_key.get(item["semantic_key"])
        rank = (SOURCE_PRIORITY[item["request_type"]],item["effort"]+item["source_cost"],-item["voi_score"])
        if old is None: by_key[item["semantic_key"]] = item
        elif rank < (SOURCE_PRIORITY[old["request_type"]],old["effort"]+old["source_cost"],-old["voi_score"]):
            rejected.append({"request_id":old["request_id"],"reason":f"doublon remplacé par {item['request_id']}"}); by_key[item["semantic_key"]]=item
        else: rejected.append({"request_id":item["request_id"],"reason":f"doublon de {old['request_id']}"})
    ranked = sorted(by_key.values(),key=lambda x:(-x["voi_score"],SOURCE_PRIORITY[x["request_type"]],x["effort"],x["request_id"]))
    for item in ranked[max_requests:]: rejected.append({"request_id":item["request_id"],"reason":"hors ensemble minimal global"})
    return {"schema_version":"indicia-client-request-selection-v2","default_question_count":0,
            "selected":ranked[:max_requests],"rejected":rejected,
            "selection_basis":"global_counterfactual_decision_value_then_lowest_burden"}
