"""Machine d'état canonique du cycle d'information client."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .client_requests import select_minimum_requests
from .workflow_paths import resolve_analysis_directory
from .privacy import PRIVACY_STATES, inspect_privacy_status, assert_case_privacy_cleared

STATES={"ANALYZING","WAITING_FOR_REQUIRED_INFORMATION","RESUMING","FINALIZABLE","DELIVERABLE",*PRIVACY_STATES}
MAX_CYCLES=2; MAX_REQUESTS=3
RESUME_DIMENSIONS={"evidence_level","asset_attribution","alternatives","confidence","economic_materiality","investigation_priority","field_action","false_conclusion_risk"}
LIFECYCLE_LIST_FIELDS={"open_request_ids","blocking_request_ids","suspended_hypothesis_ids","answered_request_ids","terminal_limitations","history"}
def _now(): return datetime.now(timezone.utc).isoformat()
def _read(path:Path):
    try: value=json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc: raise ValueError(f"Fichier requis absent: {path}.") from exc
    if not isinstance(value,dict): raise ValueError(f"Objet JSON attendu: {path}.")
    return value
def _write(path:Path,value:dict):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def lifecycle_directory(case_directory:str|Path)->Path:
    return resolve_analysis_directory(case_directory)
def _fresh(action="client_lifecycle_initialized", state="ANALYZING"):
    return {"state":state,"cycle_count":0,"max_cycles":MAX_CYCLES,"max_requests_per_cycle":MAX_REQUESTS,
      "existing_data_exhausted":False,"analysis_inventory_ref":None,"open_request_ids":[],"blocking_request_ids":[],
      "suspended_hypothesis_ids":[],"answered_request_ids":[],"exhausted":False,"terminal_limitations":[],
      "resume_required":False,"history":[{"at_utc":_now(),"action":action}]}
def _validate_lifecycle(life:Any,questions:dict[str,Any]|None=None)->None:
    if not isinstance(life,dict) or life.get("state") not in STATES:
        raise ValueError("client_lifecycle invalide.")
    missing=LIFECYCLE_LIST_FIELDS-set(life)
    if missing or any(not isinstance(life.get(key),list) for key in LIFECYCLE_LIST_FIELDS):
        raise ValueError("client_lifecycle incomplet ou types invalides.")
    for key,maximum in (("max_cycles",MAX_CYCLES),("max_requests_per_cycle",MAX_REQUESTS)):
        value=life.get(key)
        if not isinstance(value,int) or isinstance(value,bool) or not 1<=value<=maximum:
            raise ValueError(f"client_lifecycle: {key} invalide.")
    cycle=life.get("cycle_count")
    if not isinstance(cycle,int) or isinstance(cycle,bool) or not 0<=cycle<=life["max_cycles"]:
        raise ValueError("client_lifecycle: cycle_count invalide.")
    if not isinstance(life.get("existing_data_exhausted"),bool) or not isinstance(life.get("resume_required"),bool) or not isinstance(life.get("exhausted"),bool):
        raise ValueError("client_lifecycle: drapeaux invalides.")
    state=life["state"]
    if state in PRIVACY_STATES and (life["existing_data_exhausted"] or life["open_request_ids"] or life["resume_required"]):
        raise ValueError(f"État {state} incohérent avec une investigation déjà commencée.")
    if state=="WAITING_FOR_REQUIRED_INFORMATION" and (not life["blocking_request_ids"] or not life["resume_required"]):
        raise ValueError("État WAITING incohérent sans demande BLOCKING et reprise requise.")
    if state=="RESUMING" and (life["blocking_request_ids"] or not life["resume_required"]):
        raise ValueError("État RESUMING incohérent.")
    if state in {"FINALIZABLE","DELIVERABLE"}:
        if life["blocking_request_ids"] or life["resume_required"] or not life["existing_data_exhausted"] or not str(life.get("conclusion_ref","")).strip():
            raise ValueError(f"État {state} incohérent avec les préconditions de finalisation.")
    if questions is None or questions.get("schema_version")!="indicia-client-questions-v2":
        return
    current=questions.get("questions")
    responses=questions.get("responses")
    history=questions.get("cycle_history",[])
    if not isinstance(current,list) or not isinstance(responses,list) or not isinstance(history,list):
        raise ValueError("questions.json canonique invalide.")
    open_ids={x.get("request_id") for x in current if isinstance(x,dict) and x.get("status")=="open"}
    blocking_ids={x.get("request_id") for x in current if isinstance(x,dict) and x.get("status")=="open" and x.get("importance")=="BLOCKING"}
    if set(life["open_request_ids"])!=open_ids or set(life["blocking_request_ids"])!=blocking_ids:
        raise ValueError("Lifecycle et questions.json sont incohérents.")
    all_questions=[x for x in current if isinstance(x,dict)]
    for cycle_payload in history:
        if isinstance(cycle_payload,dict) and isinstance(cycle_payload.get("questions"),list):
            all_questions.extend(x for x in cycle_payload["questions"] if isinstance(x,dict))
    known_request_ids={x.get("request_id") for x in all_questions}
    response_request_ids={x.get("request_id") for x in responses if isinstance(x,dict)}
    if not set(life["answered_request_ids"])<=response_request_ids or not response_request_ids<=known_request_ids:
        raise ValueError("Historique des réponses incohérent avec les demandes.")
def initialize_client_lifecycle(case_directory:str|Path)->dict[str,Any]:
    privacy=inspect_privacy_status(case_directory)
    if privacy["state"]=="PRIVACY_MIGRATION_REQUIRED":
        raise ValueError("Workspace historique: migration privacy explicite requise avant initialisation du lifecycle.")
    root=lifecycle_directory(case_directory); root.mkdir(parents=True,exist_ok=True); path=root/"investigation_state.json"
    initial_state=privacy["state"] if privacy["state"] in PRIVACY_STATES else "ANALYZING"
    if path.exists():
        state=_read(path)
        if state.get("client_lifecycle") is None: state["client_lifecycle"]=_fresh("legacy_investigation_state_migrated",initial_state); _write(path,state)
        _validate_lifecycle(state.get("client_lifecycle"))
    else: state={"schema_version":"indicia-investigation-state-v2","client_lifecycle":_fresh(state=initial_state)}; _write(path,state)
    q=root/"questions.json"
    if not q.exists(): _write(q,{"schema_version":"indicia-client-questions-v2","questions":[],"responses":[],"cycle_history":[]})
    return state

def synchronize_privacy_state(case_directory:str|Path,state_name:str,*,reason:str):
    if state_name not in PRIVACY_STATES: raise ValueError("État privacy invalide.")
    root=lifecycle_directory(case_directory); root.mkdir(parents=True,exist_ok=True); path=root/"investigation_state.json"
    payload=_read(path) if path.exists() else {"schema_version":"indicia-investigation-state-v2"}
    life=payload.get("client_lifecycle") or _fresh(state=state_name)
    if life.get("state")=="PURGED" and state_name!="PURGED": raise ValueError("Un dossier PURGED ne peut pas être rouvert.")
    if life.get("state") not in PRIVACY_STATES and life.get("state") != state_name:
        raise ValueError("Le privacy gate ne peut pas réécrire une investigation déjà commencée.")
    life["state"]=state_name; life["privacy_manifest_ref"]="privacy/privacy_manifest.json"
    life["privacy_approved_for_analysis"]=state_name=="PRIVACY_CLEARED"
    life["history"].append({"at_utc":_now(),"action":"privacy_state_synchronized","state":state_name,"reason":reason})
    payload["client_lifecycle"]=life; _validate_lifecycle(life); _write(path,payload)
    q=root/"questions.json"
    if not q.exists(): _write(q,{"schema_version":"indicia-client-questions-v2","questions":[],"responses":[],"cycle_history":[]})
    return payload

def _load_allow_privacy(case):
    root=lifecycle_directory(case); state=initialize_client_lifecycle(case); questions=_read(root/"questions.json")
    if not isinstance(questions.get("questions",[]),list) or not isinstance(questions.get("responses",[]),list): raise ValueError("questions.json invalide.")
    _validate_lifecycle(state["client_lifecycle"],questions); return root,state,questions

def begin_privacy_cleared_analysis(case_directory:str|Path):
    assert_case_privacy_cleared(case_directory)
    root,state,_=_load_allow_privacy(case_directory); life=state["client_lifecycle"]
    if life["state"]=="ANALYZING": return state
    if life["state"]!="PRIVACY_CLEARED": raise ValueError(f"PRIVACY GATE: analyse interdite en état {life['state']}.")
    life["state"]="ANALYZING"; life["history"].append({"at_utc":_now(),"action":"analysis_started_after_privacy_clearance"})
    _write(root/"investigation_state.json",state); return state
def _load(case):
    root,state,questions=_load_allow_privacy(case)
    if state["client_lifecycle"]["state"] in PRIVACY_STATES:
        raise ValueError(f"PRIVACY GATE: investigation interdite en état {state['client_lifecycle']['state']}.")
    assert_case_privacy_cleared(case)
    return root,state,questions
def record_existing_data_exhaustion(case_directory:str|Path,*,analysis_inventory_ref:str,reviewed_sources:list[str]):
    if not str(analysis_inventory_ref).strip() or not reviewed_sources or any(not str(x).strip() for x in reviewed_sources): raise ValueError("Inventaire et sources examinées requis.")
    root,state,_=_load(case_directory); life=state["client_lifecycle"]
    if life["state"]=="WAITING_FOR_REQUIRED_INFORMATION": raise ValueError("STOP: analyse dépendante interdite pendant l'attente.")
    life.update({"existing_data_exhausted":True,"analysis_inventory_ref":analysis_inventory_ref,"reviewed_sources":list(dict.fromkeys(reviewed_sources))})
    life["history"].append({"at_utc":_now(),"action":"existing_data_exhausted","analysis_inventory_ref":analysis_inventory_ref}); _write(root/"investigation_state.json",state); return state
def publish_client_requests(case_directory:str|Path,candidates:list[dict[str,Any]],*,new_material_branch:dict[str,Any]|None=None):
    root,state,questions=_load(case_directory); life=state["client_lifecycle"]
    if life["state"] in {"WAITING_FOR_REQUIRED_INFORMATION","RESUMING"}: raise ValueError("Le cycle précédent doit être répondu et réanalysé.")
    if life["state"] in {"FINALIZABLE","DELIVERABLE"}: raise ValueError("Investigation déjà finalisée.")
    if not life["existing_data_exhausted"]: raise ValueError("Analyser exhaustivement les données existantes avant toute demande externe.")
    cycle=life["cycle_count"]+1
    if cycle>life["max_cycles"]: raise ValueError("Budget de clarification épuisé.")
    if cycle==2:
        ids=(new_material_branch or {}).get("trigger_response_ids",[])
        if not ids or set(ids)-set(life["answered_request_ids"]) or not str((new_material_branch or {}).get("decision_change","")).strip(): raise ValueError("Le second cycle exige une nouvelle branche matérielle référant les réponses.")
    selection=select_minimum_requests(candidates,max_requests=life["max_requests_per_cycle"]); selected=selection["selected"]
    old=[*questions.get("questions",[])]
    for history in questions.get("cycle_history",[]): old.extend(history.get("questions",[]))
    keys={x.get("semantic_key") for x in old}
    repeated=[x["request_id"] for x in selected if x["semantic_key"] in keys]
    if repeated: raise ValueError("Demande sémantiquement déjà posée: "+", ".join(repeated))
    if not selected: return {**selection,"cycle":None,"must_stop":False,"state":life["state"]}
    if questions.get("questions"): questions.setdefault("cycle_history",[]).append({"cycle":life["cycle_count"],"questions":questions["questions"]})
    published=[{**x,"status":"open","cycle":cycle,"published_at_utc":_now()} for x in selected]
    questions.update({"schema_version":"indicia-client-questions-v2","questions":published,"selection":selection,"new_material_branch":new_material_branch})
    life["cycle_count"]=cycle; life["open_request_ids"]=[x["request_id"] for x in published]
    life["blocking_request_ids"]=[x["request_id"] for x in published if x["importance"]=="BLOCKING"]
    life["suspended_hypothesis_ids"]=sorted({h for x in published if x["importance"]=="BLOCKING" for h in x["related_hypothesis_ids"]})
    stop=bool(life["blocking_request_ids"])
    if stop: life["state"]="WAITING_FOR_REQUIRED_INFORMATION"; life["resume_required"]=True
    life["history"].append({"at_utc":_now(),"action":"client_requests_published","cycle":cycle,"request_ids":life["open_request_ids"],"must_stop":stop})
    _write(root/"questions.json",questions); _write(root/"investigation_state.json",state); return {**selection,"cycle":cycle,"must_stop":stop,"state":life["state"]}
def record_canonical_answers(case_directory:str|Path,answers:list[dict[str,Any]]):
    root,state,questions=_load(case_directory); life=state["client_lifecycle"]; by_id={x.get("request_id"):x for x in questions["questions"]}
    existing_answers={x.get("answer_id"):x for x in questions["responses"]}
    duplicates=[str(x.get("request_id")) for x in answers if x.get("request_id") in by_id and by_id[x.get("request_id")].get("status")=="answered" and not x.get("supersedes_answer_id")]
    if duplicates: raise ValueError("La réponse "+", ".join(duplicates)+" est déjà enregistrée.")
    if life["state"] not in {"WAITING_FOR_REQUIRED_INFORMATION","ANALYZING","RESUMING"}: raise ValueError("Réponses recevables seulement pour un cycle ouvert ou une correction de reprise.")
    recorded=[]
    for raw in answers:
        rid=raw.get("request_id")
        if rid not in by_id: raise ValueError(f"Demande inconnue: {rid}.")
        for field in ("answer","provided_by_role","source_or_evidence","source_type","provided_at_utc"):
            if not str(raw.get(field,"")).strip(): raise ValueError(f"{rid}: {field} requis.")
        if raw["source_type"] not in {"CLIENT_DECLARATION","EXISTING_DOCUMENT","FIELD_OBSERVATION","PREREGISTERED_TEST","INSTRUMENT_MEASUREMENT"}: raise ValueError(f"{rid}: source_type invalide.")
        aid=str(raw.get("answer_id") or f"ANS-{len(questions['responses'])+len(recorded)+1:03d}")
        if any(x.get("answer_id")==aid for x in questions["responses"]): raise ValueError(f"answer_id déjà enregistré: {aid}.")
        reference_ids=set(raw.get("contradicts_answer_ids",[]))
        supersedes=raw.get("supersedes_answer_id")
        if reference_ids-set(existing_answers) or (supersedes is not None and supersedes not in existing_answers): raise ValueError("Contradiction/correction référence une réponse inconnue.")
        if supersedes is not None and existing_answers[supersedes].get("request_id")!=rid: raise ValueError("Une correction doit viser une réponse de la même demande.")
        request=by_id[rid]; reliability=float(raw.get("reliability",.6))
        if not 0<=reliability<=1: raise ValueError("reliability invalide.")
        entry={"answer_id":aid,"request_id":rid,"answer":str(raw["answer"]).strip(),"provided_by_role":str(raw["provided_by_role"]).strip(),
          "source_or_evidence":str(raw["source_or_evidence"]).strip(),"source_type":raw["source_type"],"provided_at_utc":raw["provided_at_utc"],
          "recorded_at_utc":_now(),"reliability":reliability,"contradicts_answer_ids":list(raw.get("contradicts_answer_ids",[])),
          "supersedes_answer_id":raw.get("supersedes_answer_id"),"related_hypothesis_ids":request["related_hypothesis_ids"],
          "related_finding_ids":request["related_finding_ids"],"related_component_ids":request["related_component_ids"],
          "verified_anchor":raw["source_type"] in {"FIELD_OBSERVATION","PREREGISTERED_TEST","INSTRUMENT_MEASUREMENT"} and bool(raw.get("verified_anchor",False))}
        request.update({"status":"answered","answer_id":aid}); questions["responses"].append(entry); recorded.append(entry); existing_answers[aid]=entry
    life["open_request_ids"]=[x["request_id"] for x in questions["questions"] if x.get("status")!="answered"]
    life["blocking_request_ids"]=[x["request_id"] for x in questions["questions"] if x.get("status")!="answered" and x["importance"]=="BLOCKING"]
    life["answered_request_ids"]=list(dict.fromkeys([*life["answered_request_ids"],*(x["request_id"] for x in recorded)]))
    if not life["blocking_request_ids"] and life["resume_required"]: life["state"]="RESUMING"
    life["history"].append({"at_utc":_now(),"action":"client_answers_recorded","answer_ids":[x["answer_id"] for x in recorded]})
    _write(root/"questions.json",questions); _write(root/"investigation_state.json",state)
    return {"recorded_answers":recorded,"state":life["state"],"analysis_may_continue":life["state"]!="WAITING_FOR_REQUIRED_INFORMATION"}
def complete_resume(case_directory:str|Path,*,recalculation_refs:list[str],adversarial_review_ref:str,before_after:list[dict[str,Any]],terminal_limitations:list[str]|None=None):
    root,state,_=_load(case_directory); life=state["client_lifecycle"]
    if life["state"]!="RESUMING": raise ValueError("Aucune reprise requise.")
    if not recalculation_refs or not str(adversarial_review_ref).strip() or not before_after: raise ValueError("Recalculs, review et avant/après requis.")
    if any(not isinstance(x,dict) or not x.get("hypothesis_id") or "before" not in x or "after" not in x or not isinstance(x.get("decision_dimensions"),dict) or set(x["decision_dimensions"])!=RESUME_DIMENSIONS for x in before_after): raise ValueError("before_after doit réévaluer toutes les dimensions décisionnelles.")
    if set(life["suspended_hypothesis_ids"])-{x["hypothesis_id"] for x in before_after}: raise ValueError("Chaque hypothèse suspendue doit être réévaluée avant/après.")
    life.update({"state":"ANALYZING","resume_required":False,"suspended_hypothesis_ids":[],"last_resume":{"recalculation_refs":recalculation_refs,"adversarial_review_ref":adversarial_review_ref,"before_after":before_after}})
    if terminal_limitations: life["terminal_limitations"].extend(terminal_limitations)
    life["history"].append({"at_utc":_now(),"action":"resume_completed"}); _write(root/"investigation_state.json",state); return state
def close_clarification_budget(case_directory:str|Path,*,terminal_limitations:list[str]):
    root,state,questions=_load(case_directory); life=state["client_lifecycle"]
    if not terminal_limitations or not any(any(t in str(x).casefold() for t in ("unknown","inconnu","non identifiable","insuffis","cause non","non démontr")) for x in terminal_limitations): raise ValueError("Limite terminale honnête requise.")
    for x in questions["questions"]:
        if x.get("status")=="open": x["status"]="closed_budget_exhausted"
    life.update({"open_request_ids":[],"blocking_request_ids":[],"suspended_hypothesis_ids":[],"resume_required":False,"exhausted":True,"terminal_limitations":list(terminal_limitations),"state":"ANALYZING"})
    life["history"].append({"at_utc":_now(),"action":"clarification_budget_closed"}); _write(root/"questions.json",questions); _write(root/"investigation_state.json",state); return state
def mark_finalizable(case_directory:str|Path,*,conclusion_ref:str):
    root,state,_=_load(case_directory); life=state["client_lifecycle"]
    if life["state"] in {"WAITING_FOR_REQUIRED_INFORMATION","RESUMING"} or life["blocking_request_ids"]: raise ValueError("Information requise ou reprise en cours.")
    if not life["existing_data_exhausted"] or not str(conclusion_ref).strip(): raise ValueError("Analyse existante et conclusion traçable requises.")
    if life["exhausted"] and not life["terminal_limitations"]: raise ValueError("Budget épuisé sans limites.")
    life.update({"state":"FINALIZABLE","conclusion_ref":conclusion_ref}); life["history"].append({"at_utc":_now(),"action":"marked_finalizable"}); _write(root/"investigation_state.json",state); return state
def validate_client_lifecycle_artifacts(case_directory:str|Path)->dict[str,Any]|None:
    root=lifecycle_directory(case_directory); path=root/"investigation_state.json"
    if not path.exists(): return None
    state=_read(path); life=state.get("client_lifecycle")
    if life is None: return None
    questions=_read(root/"questions.json")
    _validate_lifecycle(life,questions)
    return life
def assert_workflow_action_allowed(case_directory:str|Path,action:str):
    path=lifecycle_directory(case_directory)/"investigation_state.json"
    assert_case_privacy_cleared(case_directory)
    if not path.exists():
        if inspect_privacy_status(case_directory)["state"]=="NOT_REQUIRED": return
        raise ValueError("Lifecycle absent: initialiser le dossier après clearance privacy.")
    life=validate_client_lifecycle_artifacts(case_directory)
    if life is None: return
    if life.get("state") in PRIVACY_STATES: raise ValueError(f"PRIVACY GATE: {action} interdit en état {life.get('state')}.")
    if life.get("state")=="WAITING_FOR_REQUIRED_INFORMATION": raise ValueError(f"STOP: {action} interdit pendant une demande BLOCKING.")
    if action in {"report_generation","delivery"} and life.get("state") not in {"FINALIZABLE","DELIVERABLE"}: raise ValueError(f"{action} exige FINALIZABLE ou DELIVERABLE.")
