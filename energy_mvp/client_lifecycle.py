"""Machine d'état canonique du cycle d'information client."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .client_requests import select_minimum_requests

STATES={"ANALYZING","WAITING_FOR_REQUIRED_INFORMATION","RESUMING","FINALIZABLE","DELIVERABLE"}
MAX_CYCLES=2; MAX_REQUESTS=3
def _now(): return datetime.now(timezone.utc).isoformat()
def _read(path:Path):
    try: value=json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc: raise ValueError(f"Fichier requis absent: {path}.") from exc
    if not isinstance(value,dict): raise ValueError(f"Objet JSON attendu: {path}.")
    return value
def _write(path:Path,value:dict):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def lifecycle_directory(case_directory:str|Path)->Path:
    root=Path(case_directory)
    return root/"investigation" if (root/"investigation").is_dir() and ((root/"case_manifest.json").exists() or (root/"derived").is_dir() or (root/"investigation/case_state.json").exists()) else root
def _fresh(action="client_lifecycle_initialized"):
    return {"state":"ANALYZING","cycle_count":0,"max_cycles":MAX_CYCLES,"max_requests_per_cycle":MAX_REQUESTS,
      "existing_data_exhausted":False,"analysis_inventory_ref":None,"open_request_ids":[],"blocking_request_ids":[],
      "suspended_hypothesis_ids":[],"answered_request_ids":[],"exhausted":False,"terminal_limitations":[],
      "resume_required":False,"history":[{"at_utc":_now(),"action":action}]}
def initialize_client_lifecycle(case_directory:str|Path)->dict[str,Any]:
    root=lifecycle_directory(case_directory); root.mkdir(parents=True,exist_ok=True); path=root/"investigation_state.json"
    if path.exists():
        state=_read(path)
        if state.get("client_lifecycle") is None: state["client_lifecycle"]=_fresh("legacy_investigation_state_migrated"); _write(path,state)
        if not isinstance(state.get("client_lifecycle"),dict) or state["client_lifecycle"].get("state") not in STATES: raise ValueError("client_lifecycle invalide.")
    else: state={"schema_version":"indicia-investigation-state-v2","client_lifecycle":_fresh()}; _write(path,state)
    q=root/"questions.json"
    if not q.exists(): _write(q,{"schema_version":"indicia-client-questions-v2","questions":[],"responses":[],"cycle_history":[]})
    return state
def _load(case):
    root=lifecycle_directory(case); state=initialize_client_lifecycle(case); questions=_read(root/"questions.json")
    if not isinstance(questions.get("questions",[]),list) or not isinstance(questions.get("responses",[]),list): raise ValueError("questions.json invalide.")
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
    duplicates=[str(x.get("request_id")) for x in answers if x.get("request_id") in by_id and by_id[x.get("request_id")].get("status")=="answered"]
    if duplicates: raise ValueError("La réponse "+", ".join(duplicates)+" est déjà enregistrée.")
    if life["state"] not in {"WAITING_FOR_REQUIRED_INFORMATION","ANALYZING"}: raise ValueError("Réponses recevables seulement pour un cycle ouvert.")
    recorded=[]
    for raw in answers:
        rid=raw.get("request_id")
        if rid not in by_id: raise ValueError(f"Demande inconnue: {rid}.")
        for field in ("answer","provided_by_role","source_or_evidence","source_type","provided_at_utc"):
            if not str(raw.get(field,"")).strip(): raise ValueError(f"{rid}: {field} requis.")
        if raw["source_type"] not in {"CLIENT_DECLARATION","EXISTING_DOCUMENT","FIELD_OBSERVATION","PREREGISTERED_TEST","INSTRUMENT_MEASUREMENT"}: raise ValueError(f"{rid}: source_type invalide.")
        aid=str(raw.get("answer_id") or f"ANS-{len(questions['responses'])+len(recorded)+1:03d}")
        if any(x.get("answer_id")==aid for x in questions["responses"]): raise ValueError(f"answer_id déjà enregistré: {aid}.")
        request=by_id[rid]; reliability=float(raw.get("reliability",.6))
        if not 0<=reliability<=1: raise ValueError("reliability invalide.")
        entry={"answer_id":aid,"request_id":rid,"answer":str(raw["answer"]).strip(),"provided_by_role":str(raw["provided_by_role"]).strip(),
          "source_or_evidence":str(raw["source_or_evidence"]).strip(),"source_type":raw["source_type"],"provided_at_utc":raw["provided_at_utc"],
          "recorded_at_utc":_now(),"reliability":reliability,"contradicts_answer_ids":list(raw.get("contradicts_answer_ids",[])),
          "supersedes_answer_id":raw.get("supersedes_answer_id"),"related_hypothesis_ids":request["related_hypothesis_ids"],
          "related_finding_ids":request["related_finding_ids"],"related_component_ids":request["related_component_ids"],
          "verified_anchor":raw["source_type"] in {"FIELD_OBSERVATION","PREREGISTERED_TEST","INSTRUMENT_MEASUREMENT"} and bool(raw.get("verified_anchor",False))}
        request.update({"status":"answered","answer_id":aid}); questions["responses"].append(entry); recorded.append(entry)
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
    if any(not isinstance(x,dict) or not x.get("hypothesis_id") or "before" not in x or "after" not in x for x in before_after): raise ValueError("before_after invalide.")
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
def assert_workflow_action_allowed(case_directory:str|Path,action:str):
    path=lifecycle_directory(case_directory)/"investigation_state.json"
    if not path.exists(): return
    life=_read(path).get("client_lifecycle")
    if life is None: return
    if life.get("state")=="WAITING_FOR_REQUIRED_INFORMATION": raise ValueError(f"STOP: {action} interdit pendant une demande BLOCKING.")
    if action in {"report_generation","delivery"} and life.get("state") not in {"FINALIZABLE","DELIVERABLE"}: raise ValueError(f"{action} exige FINALIZABLE ou DELIVERABLE.")
