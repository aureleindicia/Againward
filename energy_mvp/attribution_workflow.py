"""Branchement production conditionnel de MinimalEvidenceAttribution."""
from __future__ import annotations
import json
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Sequence
from .client_lifecycle import lifecycle_directory,record_canonical_answers,assert_workflow_action_allowed
from .privacy import assert_case_privacy_cleared
from .artifact_store import case_mutation, read_json, write_json
from .minimal_attribution import AnonymousElectricalComponent,EquipmentRecord,EvidenceItem,EvidenceLedger,MicroQuestion,assess_attribution,rank_micro_questions
def _write(path,payload): write_json(path,payload)
def _read(path):
    value=read_json(path)
    if not isinstance(value,dict): raise ValueError(f"Objet JSON attendu: {path}.")
    return value
def _component(value):
    data=dict(value); data.pop("claim_boundary",None)
    for key in ("amplitude_range_kw","operating_days","source_refs"):
        if data.get(key) is not None: data[key]=tuple(data[key])
    return AnonymousElectricalComponent(**data)
def _asset(value):
    data=dict(value); data.pop("unknown_fields",None)
    for key in ("nominal_power_range_kw","operating_days","simultaneous_with","auxiliaries","maintenance_dates"):
        if data.get(key) is not None: data[key]=tuple(data[key])
    if data.get("known_shutdowns") is not None: data["known_shutdowns"]=tuple(tuple(x) for x in data["known_shutdowns"])
    return EquipmentRecord(**data)
def _requests(assessment,questions,related):
    ids=list(dict.fromkeys([x.asset_id for x in assessment.candidates if not x.eliminated and (x.asset_id in assessment.alternatives or x.asset_id==assessment.selected_asset_id)] or assessment.alternatives))
    ranked=rank_micro_questions(ids,questions) if len(ids)>=2 else []; lookup={x.question_id:x for x in questions}; result=[]
    for rank in ranked:
        q=lookup[rank["question_id"]]; groups={}
        for asset,answer in q.answer_by_candidate.items():
            if asset in ids: groups.setdefault(answer,[]).append(asset)
        result.append({"request_id":q.question_id,"request_type":"MICRO_QUESTION","client_question":q.prompt,
          "internal_reason":"Départager les actifs compatibles sans export lourd.","target_role":"personne connaissant le site",
          "related_hypothesis_ids":list(related),"related_component_ids":[assessment.component_id],"hypotheses_distinguished":ids,
          "answer_by_hypothesis":{k:v for k,v in q.answer_by_candidate.items() if k in ids},
          "plausible_answers":[{"answer_id":f"OPTION-{i:02d}","label":a,"decision_effects":["Actifs compatibles restants: "+", ".join(m)]} for i,(a,m) in enumerate(groups.items(),1)],
          "decision_impact_dimensions":["asset_attribution","false_conclusion_risk"],"effort":q.effort,"availability":q.availability,
          "reliability":q.reliability,"source_cost":0,"expected_source_type":"CLIENT_DECLARATION","expected_effort":"micro-réponse ponctuelle","importance":"BLOCKING","mea_voi":rank})
    return result
@case_mutation
def run_minimal_attribution(case_directory:str|Path,*,component:AnonymousElectricalComponent|None,inventory:Sequence[EquipmentRecord]|None,micro_questions:Sequence[MicroQuestion]=(),related_hypothesis_ids:Sequence[str]=(),applicability_reason:str|None=None):
    root=lifecycle_directory(case_directory); path=root/"minimal_attribution.json"
    assert_workflow_action_allowed(case_directory,"asset_attribution")
    if component is None or not inventory:
        payload={"schema_version":"indicia-minimal-attribution-workflow-v1","status":"not_applicable","reason":applicability_reason or "signature_anonyme_ou_inventaire_absent","separation_of_claims":["detection","reproducible_signature","anonymous_component","asset_compatibility","asset_attribution","physical_mechanism","prognosis"]}; _write(path,payload); return payload
    ledger_path=root/"evidence"/f"minimal_attribution_{component.component_id}_ledger.json"
    ledger=EvidenceLedger.from_dict(_read(ledger_path)) if ledger_path.exists() else EvidenceLedger(component.component_id)
    assessment=assess_attribution(component,inventory,evidence=ledger.active_items(),method="guarded_evidence"); ledger.record_assessment(assessment)
    payload={"schema_version":"indicia-minimal-attribution-workflow-v1","status":"assessed","assessed_at_utc":datetime.now(timezone.utc).isoformat(),"method":"guarded_evidence",
      "component":component.to_dict(),"inventory":[x.to_dict() for x in inventory],"micro_questions":[asdict(x) for x in micro_questions],"related_hypothesis_ids":list(related_hypothesis_ids),
      "ledger_ref":str(ledger_path.relative_to(root)),"assessment":assessment.to_dict(),"candidate_requests":_requests(assessment,micro_questions,related_hypothesis_ids),"claim_boundary":"attribution_only_no_physical_mechanism_no_prognosis"}
    _write(ledger_path,ledger.to_dict()); _write(path,payload); return payload
@case_mutation
def record_attribution_answer(case_directory:str|Path,*,answer:dict[str,Any],evidence:dict[str,Any]):
    root=lifecycle_directory(case_directory); workflow=_read(root/"minimal_attribution.json")
    assert_case_privacy_cleared(case_directory)
    if workflow.get("status")!="assessed": raise ValueError("MinimalEvidenceAttribution non applicable.")
    component=_component(workflow["component"]); inventory=[_asset(x) for x in workflow["inventory"]]
    item=EvidenceItem(
        evidence_id=str(evidence["evidence_id"]), kind=str(evidence.get("kind","client_answer")),
        direction=str(evidence["direction"]), candidate_ids=tuple(evidence["candidate_ids"]),
        reliability=float(answer.get("reliability",evidence.get("reliability",.6))),
        observed_at=str(answer["provided_at_utc"]), provenance=str(answer["source_or_evidence"]),
        statement=str(evidence.get("statement",answer["answer"])),
        observed_or_inferred=str(evidence.get("observed_or_inferred","observed")),
        source_class=str(answer["source_type"]), anchor_verified=bool(answer.get("verified_anchor",False)),
        supersedes_evidence_id=evidence.get("supersedes_evidence_id"), request_id=str(answer["request_id"]),
        finding_ids=tuple(evidence.get("finding_ids",())),
        hypothesis_ids=tuple(evidence.get("hypothesis_ids",workflow.get("related_hypothesis_ids",()))),
    )
    ledger_path=root/workflow["ledger_ref"]; ledger=EvidenceLedger.from_dict(_read(ledger_path)); ledger.append(item)
    answer_result=record_canonical_answers(case_directory,[answer]); assessment=assess_attribution(component,inventory,evidence=ledger.active_items(),method="guarded_evidence"); ledger.record_assessment(assessment); _write(ledger_path,ledger.to_dict())
    workflow.update({"previous_assessment":workflow["assessment"],"assessment":assessment.to_dict(),"last_answer_id":answer_result["recorded_answers"][0]["answer_id"],"reassessment_required":True}); _write(root/"minimal_attribution.json",workflow)
    return {"answer":answer_result,"assessment":assessment.to_dict(),"ledger":ledger.to_dict()}
