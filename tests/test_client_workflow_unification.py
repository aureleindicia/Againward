import json
from pathlib import Path
import pytest
from energy_mvp.attribution_workflow import record_attribution_answer,run_minimal_attribution
from energy_mvp.case_lifecycle import evaluate_delivery_gate
from energy_mvp.evidence_cli import execute_case_query
from energy_mvp.client_lifecycle import (assert_workflow_action_allowed,close_clarification_budget,complete_resume,initialize_client_lifecycle,mark_finalizable,publish_client_requests,record_canonical_answers,record_existing_data_exhaustion)
from energy_mvp.client_requests import normalize_request,select_minimum_requests
from energy_mvp.minimal_attribution import AnonymousElectricalComponent,EquipmentRecord,EvidenceItem,EvidenceLedger,MicroQuestion,assess_attribution
from energy_mvp.workflow import prepare_investigation
from operational_economics import publish_economic_request_batch

def candidate(rid="Q1",*,request_type="MICRO_QUESTION",importance="BLOCKING",related="H1",effort=1.,availability=1.):
    value={"request_id":rid,"request_type":request_type,"client_question":"Le site était-il fermé pendant le palier observé ?","internal_reason":"Départage une activité utile d'une charge inexpliquée.","target_role":"responsable du site","related_hypothesis_ids":[related],"related_finding_ids":["F1"],"hypotheses_distinguished":["activité utile","charge inexpliquée"],"answer_by_hypothesis":{"activité utile":"ouvert","charge inexpliquée":"fermé"},"plausible_answers":[{"answer_id":"OPEN","label":"Site ouvert","decision_effects":["Conserver l'activité utile."]},{"answer_id":"CLOSED","label":"Site fermé","decision_effects":["Écarter l'activité utile."]}],"decision_impact_dimensions":["evidence_level","false_conclusion_risk"],"expected_effort":"réponse oui/non","effort":effort,"availability":availability,"reliability":.7,"source_cost":0,"expected_source_type":"CLIENT_DECLARATION","importance":importance}
    if request_type in {"FIELD_OBSERVATION","FIELD_VERIFICATION","TEMPORARY_INSTRUMENTATION"}: value["field_verification"]={"what_to_check":"Observer marche/arrêt.","asset_or_group":"pompes P1/P2","period_or_regime":"05:45–06:15","why_discriminating":"une seule pompe active","competent_role":"technicien habilité","safety_constraints":"ne pas ouvrir sous tension","stop_condition":"arrêter si dangereux","confirming_result":"P1 active","refuting_result":"P1 arrêtée","before_after_comparison":"horodatage terrain/compteur"}
    return value
def ready(path): initialize_client_lifecycle(path); record_existing_data_exhaustion(path,analysis_inventory_ref="inventory.json",reviewed_sources=["input.csv"]); return path
def answer(rid="Q1",**kw):
    value={"answer_id":f"A-{rid}","request_id":rid,"answer":"Le site était fermé.","provided_by_role":"responsable","source_or_evidence":"échange daté","source_type":"CLIENT_DECLARATION","provided_at_utc":"2026-09-03T10:00:00+02:00","reliability":.65}; value.update(kw); return value
def resume(path,hid="H1"): complete_resume(path,recalculation_refs=["recalc.json"],adversarial_review_ref="review.json",before_after=[{"hypothesis_id":hid,"before":"unknown","after":"revised","decision_dimensions":{key:"reassessed" for key in ("evidence_level","asset_attribution","alternatives","confidence","economic_materiality","investigation_priority","field_action","false_conclusion_risk")}}])
def component(): return AnonymousElectricalComponent("C1",10,(9,11),6,18,None,None,None,(0,1,2,3,4),None,None,None,.9,.9,8,"dependent",{},("signal.json",))
def assets(): return [EquipmentRecord("P1",family="pump",nominal_power_kw=10,usual_start_hour=6,usual_stop_hour=18,operating_days=(0,1,2,3,4),production_dependency="dependent"),EquipmentRecord("P2",family="pump",nominal_power_kw=10,usual_start_hour=6,usual_stop_hour=18,operating_days=(0,1,2,3,4),production_dependency="dependent")]
def micro(): return MicroQuestion("Q-ASSET","Pendant le palier, laquelle des deux pompes était en marche ?",{"P1":"P1","P2":"P2","unknown":"autre"},1,.9,.7)

def test_zero_question_and_normal_finalization(tmp_path):
    ready(tmp_path); assert publish_client_requests(tmp_path,[])["selected"]==[]; assert mark_finalizable(tmp_path,conclusion_ref="investigation.json")["client_lifecycle"]["state"]=="FINALIZABLE"
def test_must_exhaust_existing_data(tmp_path):
    initialize_client_lifecycle(tmp_path)
    with pytest.raises(ValueError,match="exhaustivement"): publish_client_requests(tmp_path,[candidate()])
def test_low_value_rejected(tmp_path):
    ready(tmp_path); assert not publish_client_requests(tmp_path,[candidate(availability=.05)])["selected"]
def test_micro_beats_export_and_instrumentation():
    result=select_minimum_requests([candidate("M",request_type="TEMPORARY_INSTRUMENTATION",effort=20),candidate("E",request_type="REQUEST_DATA_EXPORT",effort=5),candidate("Q")]); assert [x["request_id"] for x in result["selected"]]==["Q"]
def test_micro_question_is_not_overvalued_when_unreliable_or_unavailable():
    result=select_minimum_requests([candidate("Q",availability=.4),candidate("I",request_type="TEMPORARY_INSTRUMENTATION",effort=2)]); assert [x["request_id"] for x in result["selected"]]==["I"]
def test_global_rank_max_three():
    result=select_minimum_requests([candidate(f"Q{i}",related=f"H{i}",effort=i) for i in range(1,6)]); assert len(result["selected"])==3 and len(result["rejected"])==2
def test_counterfactual_must_differ():
    value=candidate(); value["plausible_answers"][1]["decision_effects"]=value["plausible_answers"][0]["decision_effects"]
    with pytest.raises(ValueError,match="aucune décision"): normalize_request(value)
def test_field_plan_required():
    value=candidate(request_type="FIELD_VERIFICATION"); del value["field_verification"]["stop_condition"]
    with pytest.raises(ValueError,match="terrain"): normalize_request(value)
def test_blocking_stops_and_suspends(tmp_path):
    ready(tmp_path); result=publish_client_requests(tmp_path,[candidate()]); assert result["must_stop"] and result["state"]=="WAITING_FOR_REQUIRED_INFORMATION"
    with pytest.raises(ValueError,match="STOP"): assert_workflow_action_allowed(tmp_path,"report_generation")
def test_mixed_batch_still_stops(tmp_path):
    ready(tmp_path); publish_client_requests(tmp_path,[candidate("QB"),candidate("QN",importance="NON_BLOCKING",related="H2")]); assert not record_canonical_answers(tmp_path,[answer("QN")])["analysis_may_continue"]
def test_answer_append_only_and_resume_required(tmp_path):
    ready(tmp_path); publish_client_requests(tmp_path,[candidate()]); assert record_canonical_answers(tmp_path,[answer()])["state"]=="RESUMING"
    with pytest.raises(ValueError,match="déjà"): record_canonical_answers(tmp_path,[answer()])
    with pytest.raises(ValueError,match="Recalcul"): complete_resume(tmp_path,recalculation_refs=[],adversarial_review_ref="",before_after=[])
    resume(tmp_path)
def test_contradictions_preserved(tmp_path):
    ready(tmp_path); publish_client_requests(tmp_path,[candidate("Q1"),candidate("Q2",related="H2")]); record_canonical_answers(tmp_path,[answer("Q1")]); record_canonical_answers(tmp_path,[answer("Q2",source_type="EXISTING_DOCUMENT",contradicts_answer_ids=["A-Q1"])]); assert len(json.loads((tmp_path/"questions.json").read_text())["responses"])==2
def test_correction_is_append_only_and_linked(tmp_path):
    ready(tmp_path); publish_client_requests(tmp_path,[candidate()]); record_canonical_answers(tmp_path,[answer()]); corrected=record_canonical_answers(tmp_path,[answer(answer_id="A-Q1-CORR",answer="Correction: le site était ouvert.",supersedes_answer_id="A-Q1")]); responses=json.loads((tmp_path/"questions.json").read_text())["responses"]; assert len(responses)==2 and corrected["recorded_answers"][0]["supersedes_answer_id"]=="A-Q1"
def test_operator_never_verified_anchor():
    with pytest.raises(ValueError,match="ancre vérifiée"): EvidenceItem("E","answer","supports",("P1",),1,"2026","call","P1",source_class="CLIENT_DECLARATION",anchor_verified=True)
def test_ledger_roundtrip_correction():
    ledger=EvidenceLedger("C"); ledger.append(EvidenceItem("E1","a","supports",("P1",),.6,"2026","call","P1",source_class="CLIENT_DECLARATION")); ledger.append(EvidenceItem("E2","f","contradicts",("P1",),.9,"2026","visit","off",source_class="FIELD_OBSERVATION",anchor_verified=True,supersedes_evidence_id="E1")); assert [x.evidence_id for x in EvidenceLedger.from_dict(ledger.to_dict()).active_items()]==["E2"]
def test_two_cycles_max(tmp_path):
    ready(tmp_path); publish_client_requests(tmp_path,[candidate("Q1")]); record_canonical_answers(tmp_path,[answer("Q1")]); resume(tmp_path)
    with pytest.raises(ValueError,match="nouvelle branche"): publish_client_requests(tmp_path,[candidate("Q2",related="H2")])
    publish_client_requests(tmp_path,[candidate("Q2",related="H2")],new_material_branch={"trigger_response_ids":["Q1"],"decision_change":"nouvelle branche"}); record_canonical_answers(tmp_path,[answer("Q2")]); resume(tmp_path,"H2")
    with pytest.raises(ValueError,match="Budget"): publish_client_requests(tmp_path,[candidate("Q3",related="H3")],new_material_branch={"trigger_response_ids":["Q2"],"decision_change":"autre"})
def test_budget_exhaustion_unknown(tmp_path):
    ready(tmp_path); publish_client_requests(tmp_path,[candidate()])
    with pytest.raises(ValueError, match="STOP"):
        close_clarification_budget(tmp_path,terminal_limitations=["Actif unknown et cause non démontrée: information insuffisante."])
def test_missing_answer_not_confirmation(tmp_path):
    ready(tmp_path); publish_client_requests(tmp_path,[candidate()]); q=json.loads((tmp_path/"questions.json").read_text()); assert q["questions"][0]["status"]=="open" and not q["responses"]
def test_mea_not_applicable(tmp_path): assert run_minimal_attribution(tmp_path,component=None,inventory=None)["status"]=="not_applicable"
def test_e2e_mea_stop_answer_ledger_resume(tmp_path):
    source=tmp_path/"client.csv"; source.write_text("timestamp,energy_kwh,machine_mode\n2026-01-01T00:00:00,2.5,idle\n2026-01-01T00:15:00,2.6,idle\n",encoding="utf-8"); case=tmp_path/"case"; prepared=prepare_investigation(source,case); request=tmp_path/"query.json"; request.write_text(json.dumps({"schema_version":"indicia-evidence-query-v1","query_id":"q-e2e","dataset_id":prepared["evidence_plane"]["dataset_id"],"operation":"describe_schema","arguments":{},"purpose":"Tracer la structure de la mesure client avant le finding."}),encoding="utf-8"); query=execute_case_query(case,request); handle=query["retrieval_handles"][0]["handle"]; record_existing_data_exhaustion(case,analysis_inventory_ref="prepared_analysis.json",reviewed_sources=["client.csv","prepared_analysis.json","evidence_card.json"])
    first=run_minimal_attribution(case,component=component(),inventory=assets(),micro_questions=[micro()],related_hypothesis_ids=["H-ASSET"]); assert first["assessment"]["selected_asset_id"] is None
    assert publish_client_requests(case,first["candidate_requests"])["must_stop"]
    result=record_attribution_answer(case,answer=answer("Q-ASSET",answer_id="A-ASSET"),evidence={"evidence_id":"E-ASSET","direction":"supports","candidate_ids":["P1"]}); assert result["answer"]["state"]=="RESUMING" and result["assessment"]["evidence_level"]["ordinal"]<=6
    (case/"recalc.json").write_text(json.dumps({"p1_compatibility":next(x["compatibility_score"] for x in result["assessment"]["candidates"] if x["asset_id"]=="P1")}),encoding="utf-8"); resume(case,"H-ASSET")
    investigation={"ground_truth_used":False,"evidence_plane_session":json.loads((case/"evidence_query_session.json").read_text())["session_id"],"hypotheses":[{"hypothesis_id":"H-ASSET","observation":"Palier électrique reproductible de 10 kW.","hypothesis":"La réponse rend P1 plus compatible, sans attribution robuste.","tests_requested":["Recalculer la compatibilité avec la preuve déclarative."],"results":{"quantitative_source":"recalc.json","selected_asset_id":None},"alternative_explanations":["P2 ou un actif absent de l'inventaire reste possible."],"best_reason_false":"La déclaration peut être erronée et n'est pas une ancre terrain.","decision":"A_CONSERVER_AVEC_RESERVES","confidence":{"asset_attribution":"faible"},"physical_cause_status":"non_etablie_avec_les_donnees_disponibles","evidence_query_ids":["q-e2e"],"evidence_handles":[handle],"terminal_status":"non_identifiable","why_no_further_request":"La micro-question a été utilisée; une déclaration seule ne justifie pas une nouvelle charge client."}],"recommendations":[]}; (case/"investigation.json").write_text(json.dumps(investigation),encoding="utf-8")
    checks={name:{"status":"passed","evidence":f"Contrôle {name} tracé."} for name in ("calculations","data_quality","baseline_robustness","alternative_explanations","causality","annualization","recoverable_saving","double_counting")}; (case/"review.json").write_text(json.dumps({"ground_truth_used":False,"reviewed_hypotheses":[{"hypothesis_id":"H-ASSET","best_reason_false":"La réponse déclarative n'identifie pas robustement l'actif.","checks":checks,"final_decision":"A_CONSERVER_AVEC_RESERVES"}]}),encoding="utf-8"); (case/"agent_findings.json").write_text(json.dumps({"schema_version":"indicia-agent-findings-v1","ground_truth_used":False,"findings":[{"finding_id":"F-ASSET","status":"A_CONSERVER_AVEC_RESERVES","claim_or_abstention":"P1 est plus compatible, sans attribution robuste.","evidence_query_ids":["q-e2e"],"evidence_handles":[handle],"alternative_explanations_tested":["P2 ou actif absent de l'inventaire"]}]}),encoding="utf-8"); (case/"report.md").write_text("# Rapport final\n\nP1 est plus compatible; l'actif reste non identifiable sans ancre terrain.\n",encoding="utf-8"); (case/"human_review.json").write_text(json.dumps({"status":"approved","approved_for_delivery":True,"reviewer_role":"ingénieur énergie","reviewed_at_utc":"2026-09-04T09:00:00+00:00","reservations":["Attribution non démontrée."]}),encoding="utf-8")
    mark_finalizable(case,conclusion_ref="investigation.json"); delivered=evaluate_delivery_gate(case); assert delivered["ready_for_delivery"], delivered["blocking_reasons"]; assert initialize_client_lifecycle(case)["client_lifecycle"]["state"]=="DELIVERABLE"
def test_e2e_two_insufficient_answers_finalize(tmp_path):
    ready(tmp_path); publish_client_requests(tmp_path,[candidate("Q1")]); record_canonical_answers(tmp_path,[answer("Q1",answer="inconnu")]); resume(tmp_path); publish_client_requests(tmp_path,[candidate("Q2",related="H2")],new_material_branch={"trigger_response_ids":["Q1"],"decision_change":"planning"}); record_canonical_answers(tmp_path,[answer("Q2",answer="indisponible")]); resume(tmp_path,"H2"); close_clarification_budget(tmp_path,terminal_limitations=["Information insuffisante; non identifiable."]); assert mark_finalizable(tmp_path,conclusion_ref="i.json")["client_lifecycle"]["state"]=="FINALIZABLE"
def test_resume_from_files(tmp_path):
    ready(tmp_path); publish_client_requests(tmp_path,[candidate()]); record_canonical_answers(tmp_path,[answer()]); assert initialize_client_lifecycle(Path(str(tmp_path)))["client_lifecycle"]["state"]=="RESUMING"
def test_no_semantic_reask(tmp_path):
    ready(tmp_path); publish_client_requests(tmp_path,[candidate()]); record_canonical_answers(tmp_path,[answer()]); resume(tmp_path)
    with pytest.raises(ValueError,match="sémantiquement"): publish_client_requests(tmp_path,[candidate("BIS")],new_material_branch={"trigger_response_ids":["Q1"],"decision_change":"redondant"})
def test_document_changes_score_not_anchor():
    before=assess_attribution(component(),assets(),method="guarded_evidence"); evidence=EvidenceItem("D","doc","supports",("P1",),.9,"2026","doc","registre",source_class="EXISTING_DOCUMENT"); after=assess_attribution(component(),assets(),evidence=[evidence],method="guarded_evidence"); assert after.selected_asset_id is None and next(x.compatibility_score for x in after.candidates if x.asset_id=="P1")>=next(x.compatibility_score for x in before.candidates if x.asset_id=="P1")
def test_field_observation_can_anchor_not_mechanism():
    evidence=EvidenceItem("F","field","supports",("P1",),.95,"2026","visit","P1 seule",source_class="FIELD_OBSERVATION",anchor_verified=True); result=assess_attribution(component(),assets(),evidence=[evidence],method="guarded_evidence"); assert result.selected_asset_id=="P1" and result.evidence_level.value<=6
def test_document_answer_not_verified(tmp_path):
    ready(tmp_path); publish_client_requests(tmp_path,[candidate()]); assert not record_canonical_answers(tmp_path,[answer(source_type="EXISTING_DOCUMENT",verified_anchor=True)])["recorded_answers"][0]["verified_anchor"]
def test_goal_b_uses_canonical_questions(tmp_path):
    ready(tmp_path); publish_economic_request_batch(tmp_path,[candidate("ECO")]); assert json.loads((tmp_path/"questions.json").read_text())["questions"][0]["request_id"]=="ECO"
def test_incoherent_state_fails_safely(tmp_path):
    (tmp_path/"investigation_state.json").write_text(json.dumps({"client_lifecycle":{"state":"MAGIC"}}))
    with pytest.raises(ValueError,match="invalide"): initialize_client_lifecycle(tmp_path)
def test_valid_state_name_with_incoherent_waiting_fails_safely(tmp_path):
    state=initialize_client_lifecycle(tmp_path); state["client_lifecycle"].update({"state":"WAITING_FOR_REQUIRED_INFORMATION","resume_required":True,"blocking_request_ids":[]}); (tmp_path/"investigation_state.json").write_text(json.dumps(state))
    with pytest.raises(ValueError,match="WAITING incohérent"): initialize_client_lifecycle(tmp_path)
def test_tampered_clarification_budget_fails_safely(tmp_path):
    state=initialize_client_lifecycle(tmp_path); state["client_lifecycle"]["max_cycles"]=99; (tmp_path/"investigation_state.json").write_text(json.dumps(state))
    with pytest.raises(ValueError,match="max_cycles invalide"): initialize_client_lifecycle(tmp_path)
def test_lifecycle_and_question_artifacts_must_agree(tmp_path):
    ready(tmp_path); publish_client_requests(tmp_path,[candidate()]); state=json.loads((tmp_path/"investigation_state.json").read_text()); state["client_lifecycle"]["open_request_ids"]=[]; (tmp_path/"investigation_state.json").write_text(json.dumps(state))
    with pytest.raises(ValueError,match="incohérents"): assert_workflow_action_allowed(tmp_path,"report_generation")
def test_skill_and_prompt_paths():
    root=Path(__file__).resolve().parents[1]; skill=root/".codex/skills/againward-client-workflow/SKILL.md"; texts=[skill.read_text(),(root/"docs/CLIENT_INVESTIGATION_PROMPT.md").read_text()]
    assert all("/storage/emulated/0/Download" in x and "questions.json" in x and "RESUMING" in x for x in texts)
    for relative in ("docs/CLIENT_WORKFLOW.md","docs/CLIENT_INFORMATION_REQUEST_POLICY.md","docs/VALUE_OF_INFORMATION_POLICY.md","docs/MINIMAL_EVIDENCE_ATTRIBUTION.md","docs/REPOSITORY_LAYOUT.md","energy_mvp/client_lifecycle.py","energy_mvp/client_requests.py","energy_mvp/attribution_workflow.py","energy_mvp/case_lifecycle.py"):
        assert (root/relative).is_file(), relative
