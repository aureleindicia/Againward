import json

import pytest

from energy_mvp import artifact_store as store
from energy_mvp.client_lifecycle import initialize_client_lifecycle
from energy_mvp.evidence_cli import execute_case_query, validate_case_findings
from energy_mvp.evidence_protocol import EvidenceQuerySession, QueryBudget
from energy_mvp.evidence_plane import EvidenceDataset
from energy_mvp.workflow import prepare_investigation
from energy_mvp.workflow_paths import inspect_case_status


def prepared(root):
    source=root/"source.csv"
    source.write_text("timestamp,power_kw,production_active\n"+"\n".join(
        f"2026-01-01T{i:02d}:00:00,{10+i},{str(i>=6).lower()}" for i in range(12)))
    case=root/"case"
    state=prepare_investigation(source,case)
    request={"query_id":"overview","dataset_id":state["evidence_plane"]["dataset_id"],
             "operation":"describe_schema","arguments":{},"purpose":"inspect source structure"}
    path=root/"query.json"
    path.write_text(json.dumps(request))
    return case,path


@pytest.mark.parametrize("interruption",[1,2,3,4])
def test_evidence_commit_recovery_keeps_response_session_trace_together(tmp_path, monkeypatch, interruption):
    case,request=prepared(tmp_path)
    original=store.atomic_write_json
    calls=0
    def fail(path,value):
        nonlocal calls
        calls+=1
        original(path,value)
        if calls==interruption:raise OSError("interrupted")
    with monkeypatch.context() as patch:
        patch.setattr(store,"atomic_write_json",fail)
        with pytest.raises(OSError):execute_case_query(case,request)
    store.recover_artifacts(case)
    session=EvidenceQuerySession.from_dict(json.loads((case/"evidence_query_session.json").read_text()))
    assert session.successful_query_ids=={"overview"}
    response=json.loads((case/"evidence_queries/overview.json").read_text())
    trace=json.loads((case/"trace.json").read_text())
    assert trace["entries"][-1]["response_sha256"]==response["response_sha256"]
    # A lost CLI acknowledgement can be retried without spending or duplicating evidence.
    assert execute_case_query(case,request)==response
    persisted=json.loads((case/"evidence_query_session.json").read_text())
    assert persisted["usage"]["calls"]==1


def test_altered_materialized_response_cannot_validate_findings(tmp_path):
    case,request=prepared(tmp_path)
    response=execute_case_query(case,request)
    finding={"schema_version":"indicia-agent-findings-v1","ground_truth_used":False,
             "findings":[{"finding_id":"F1","status":"A_CONSERVER_AVEC_RESERVES",
               "claim_or_abstention":"Structure needs review.","evidence_query_ids":["overview"],
               "evidence_handles":[response["retrieval_handles"][0]["handle"]],
               "alternative_explanations_tested":["incomplete export"]}]}
    file=tmp_path/"findings.json";file.write_text(json.dumps(finding))
    response["result"]["forged"]=999
    (case/"evidence_queries/overview.json").write_text(json.dumps(response))
    with pytest.raises(ValueError,match="hash mismatch"):validate_case_findings(case,file)


def test_expensive_rejected_response_still_consumes_compute_budget(tmp_path):
    case,_=prepared(tmp_path)
    dataset=EvidenceDataset.from_dict(json.loads((case/"evidence_dataset.json").read_text()))
    session=EvidenceQuerySession.create(dataset,budget=QueryBudget(maximum_context_bytes=1000))
    query={"query_id":"support","dataset_id":dataset.dataset_id,"operation":"support_atlas",
           "arguments":{"split_field":"production_active","reference_value":False,"target_value":True,
                        "dimensions":[{"field":"power_kw","kind":"numeric","tolerance":20}]},
           "purpose":"test support"}
    with pytest.raises(ValueError,match="octets"):session.execute(dataset,query)
    assert session.pair_comparisons_used==36
    EvidenceQuerySession.from_dict(session.to_dict())


def test_default_arguments_cannot_launder_repeated_queries(tmp_path):
    case,_=prepared(tmp_path)
    dataset=EvidenceDataset.from_dict(json.loads((case/"evidence_dataset.json").read_text()))
    session=EvidenceQuerySession.create(dataset)
    query={"query_id":"rows","dataset_id":dataset.dataset_id,"operation":"raw_slice",
           "arguments":{"fields":["power_kw","timestamp"]},"purpose":"inspect rows"}
    session.execute(dataset,query)
    query["query_id"]="rows-again"
    query["arguments"]={"fields":["timestamp","power_kw"],"limit":50,"start":0,"representation":"typed"}
    with pytest.raises(ValueError,match="répétée"):session.execute(dataset,query)


def test_status_does_not_offer_delivery_for_inconsistent_state(tmp_path):
    state=initialize_client_lifecycle(tmp_path)
    state["client_lifecycle"]["state"]="DELIVERABLE"
    (tmp_path/"investigation_state.json").write_text(json.dumps(state))
    status=inspect_case_status(tmp_path)
    assert status["lifecycle_error"]
    assert status["next_action"]=="REPAIR_INVALID_LIFECYCLE_STATE"


def test_idempotent_transport_retries_cannot_create_an_unbounded_loop(tmp_path):
    case,request=prepared(tmp_path)
    execute_case_query(case,request)
    for _ in range(8):execute_case_query(case,request)
    with pytest.raises(ValueError,match="replay"):
        execute_case_query(case,request)
