"""Contrat unique des demandes client et sélection par valeur décisionnelle."""
from __future__ import annotations

import re
import math
from collections import Counter
from itertools import combinations
import unicodedata
from typing import Any, Iterable

from .minimal_attribution import MicroQuestion, rank_micro_questions

REQUEST_TYPES = {"INFER_AUTOMATICALLY", "MICRO_QUESTION", "REQUEST_EXISTING_DOCUMENT",
                 "FIELD_OBSERVATION", "FIELD_VERIFICATION", "REQUEST_DATA_EXPORT",
                 "TEMPORARY_INSTRUMENTATION"}
DECISION_DIMENSIONS = {
    "evidence_level",
    "asset_attribution",
    "alternatives",
    "confidence",
    "economic_materiality",
    "investigation_priority",
    "field_action",
    "false_conclusion_risk",
}
MIN_VOI_SCORE = 0.05
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
    hypotheses = sorted(_normal(str(x)) for x in request.get("hypotheses_distinguished", []))
    mapping = request.get("answer_by_hypothesis", {})
    original = sorted(request.get("hypotheses_distinguished", []))
    # Equivalence is a partition of explanations, not just a shared hypothesis ID.
    if original and set(mapping) >= set(original):
        groups = {}
        for hypothesis in original:
            groups.setdefault(str(mapping[hypothesis]), []).append(_normal(hypothesis))
        discriminator = repr(sorted(sorted(group) for group in groups.values()))
    else:
        discriminator = _normal(str(request.get("client_question", "")))
    return repr((sorted(_normal(str(x)) for x in subject), hypotheses,
                 _normal(str(request.get("information_target", ""))), discriminator))

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
    if not all(math.isfinite(x) for x in (effort, cost, availability, reliability)) or effort <= 0 or cost < 0 or not 0 <= availability <= 1 or not 0 <= reliability <= 1:
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
        "information_target":str(candidate.get("information_target", "")),
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

def _marginal_voi(item: dict[str, Any], selected: list[dict[str, Any]]) -> float:
    """Conditional information under an explicit uniform hypothesis model, not EVSI.

    Availability/reliability are analyst estimates. Scores do not establish truth.
    Unmapped requests retain the documented decision-dimension heuristic.
    """
    hypotheses = item["hypotheses_distinguished"]
    mapping = item["answer_by_hypothesis"]
    if not set(mapping) >= set(hypotheses):
        return _voi(item)
    comparable = [other for other in selected
                  if set(other["hypotheses_distinguished"]) == set(hypotheses)
                  and other["information_target"] == item["information_target"]
                  and set(other["related_hypothesis_ids"]) == set(item["related_hypothesis_ids"])
                  and set(other["answer_by_hypothesis"]) >= set(hypotheses)]
    groups = {}
    for h in hypotheses:
        key = tuple(str(other["answer_by_hypothesis"][h]) for other in comparable)
        groups.setdefault(key, []).append(h)
    entropy = 0.0
    for group in groups.values():
        counts = Counter(str(mapping[h]) for h in group)
        entropy += len(group)/len(hypotheses) * sum(
            -(n/len(group))*math.log2(n/len(group)) for n in counts.values())
    return entropy*item["availability"]*item["reliability"]/(item["effort"]+item["source_cost"])


def select_minimum_requests(candidates: Iterable[dict[str, Any]], *, max_requests: int = 3) -> dict[str, Any]:
    if type(max_requests) is not int or not 1 <= max_requests <= 3: raise ValueError("max_requests doit être entre 1 et 3.")
    accepted, rejected = [], []
    ids = set()
    for raw in candidates:
        if not isinstance(raw, dict):
            rejected.append({"request_id":"?", "reason":"objet requis"}); continue
        if raw.get("request_id") in ids:
            raise ValueError("request_id dupliqué dans les candidats.")
        ids.add(raw.get("request_id"))
        try: item = normalize_request(raw)
        except (TypeError,ValueError) as exc: rejected.append({"request_id":str(raw.get("request_id","?")),"reason":str(exc)}); continue
        item["voi_score"] = round(_voi(item),9)
        if item["voi_score"] < MIN_VOI_SCORE:
            rejected.append({
                "request_id": item["request_id"],
                "reason": "valeur décisionnelle insuffisante après effort et fiabilité",
            })
            continue
        accepted.append(item)
    by_key = {}
    for item in accepted:
        old = by_key.get(item["semantic_key"])
        rank = (
            -item["voi_score"],
            SOURCE_PRIORITY[item["request_type"]],
            item["effort"] + item["source_cost"],
        )
        if old is None: by_key[item["semantic_key"]] = item
        elif rank < (
            -old["voi_score"],
            SOURCE_PRIORITY[old["request_type"]],
            old["effort"] + old["source_cost"],
        ):
            rejected.append({"request_id":old["request_id"],"reason":f"doublon remplacé par {item['request_id']}"}); by_key[item["semantic_key"]]=item
        else: rejected.append({"request_id":item["request_id"],"reason":f"doublon de {old['request_id']}"})
    remaining, selected = list(by_key.values()), []
    basis="conditional_information_greedy"
    def comparable_scope(item):
        return (tuple(sorted(item["hypotheses_distinguished"])),
                tuple(sorted(item["related_hypothesis_ids"])),item["information_target"],
                item["availability"]*item["reliability"]/(item["effort"]+item["source_cost"]))
    # Exhaustive choice is cheap for <=12 requests and <=3 slots. Restrict it to
    # the case with a well-defined additive joint-information objective.
    if (remaining and len(remaining)<=12 and len({comparable_scope(x) for x in remaining})==1
        and all(set(x["answer_by_hypothesis"])>=set(x["hypotheses_distinguished"]) for x in remaining)):
        best_score=0.0
        for size in range(1,min(max_requests,len(remaining))+1):
            for group in combinations(sorted(remaining,key=lambda x:x["request_id"]),size):
                gains=[_marginal_voi(item,list(group[:i])) for i,item in enumerate(group)]
                if min(gains)>=MIN_VOI_SCORE and sum(gains)>best_score+1e-9:
                    best_score=sum(gains); selected=list(group)
        for i,item in enumerate(selected):
            item["marginal_voi_score"]=round(_marginal_voi(item,selected[:i]),9)
        remaining=[x for x in remaining if x not in selected]
        basis="exact_small_equal_cost_information_set"
    while basis=="conditional_information_greedy" and remaining and len(selected) < max_requests:
        for item in remaining:
            item["marginal_voi_score"] = round(_marginal_voi(item, selected), 9)
        remaining.sort(key=lambda x:(-x["marginal_voi_score"],SOURCE_PRIORITY[x["request_type"]],x["effort"],x["request_id"]))
        if remaining[0]["marginal_voi_score"] < MIN_VOI_SCORE:
            break
        selected.append(remaining.pop(0))
    for item in remaining: rejected.append({"request_id":item["request_id"],"reason":"budget ou valeur marginale insuffisante"})
    return {"schema_version":"indicia-client-request-selection-v2","default_question_count":0,
            "minimum_voi_score":MIN_VOI_SCORE,
            "selected":selected,"rejected":rejected,
            "selection_basis":basis,
            "calibration":"uniform_hypothesis_heuristic_not_expected_monetary_value"}
