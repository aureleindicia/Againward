import json
from dataclasses import replace

import pytest

from benchmarking.architecture_probe import request, answer, ready
from energy_mvp.client_requests import select_minimum_requests, normalize_request
from energy_mvp.client_lifecycle import (
    publish_client_requests, record_canonical_answers, complete_resume,
    continue_clarification, RESUME_DIMENSIONS,
)
from energy_mvp.evidence_protocol import EvidenceQuerySession, QueryBudget, stable_json_bytes
from energy_mvp.evidence_plane import EvidenceDataset, stable_hash
from energy_mvp.io import load_data


@pytest.fixture
def dataset(tmp_path):
    path=tmp_path/"s.csv"
    path.write_text("timestamp,power_kw\n"+"\n".join(f"2026-01-01T{h:02d}:00:00,100" for h in range(24))+"\n")
    return EvidenceDataset.from_loaded_data(load_data(path),source_sha256="synthetic")


def query(dataset, index):
    return {"query_id":f"q{index}","dataset_id":dataset.dataset_id,"operation":"raw_slice",
            "arguments":{"fields":["power_kw"],"start":index,"limit":1},"purpose":"Test a distinct observed interval."}


def test_continuation_preserves_usage_and_requires_new_progress(dataset):
    session=EvidenceQuerySession.create(dataset,budget=QueryBudget(maximum_calls=2))
    for i in range(2): session.execute(dataset,query(dataset,i))
    before=session.returned_rows_used
    assessment={"budget":{"maximum_calls":4},"progress_query_ids":["q0","q1"],
                "unresolved_hypotheses":["H1"],"next_tests":["inspect next interval"],
                "decision_impact":"Resolve remaining change in operation."}
    session.continue_investigation(**assessment)
    session.execute(dataset,query(dataset,2))
    assert session.returned_rows_used==before+1
    with pytest.raises(ValueError,match="nouvelles preuves"):
        session.continue_investigation(**{**assessment,"budget":{"maximum_calls":6}})
    assert EvidenceQuerySession.from_dict(session.to_dict()).continuations==session.continuations


def test_failures_do_not_consume_useful_call_allowance_but_are_bounded(dataset):
    session=EvidenceQuerySession.create(dataset,budget=QueryBudget(maximum_calls=1,maximum_rejected_calls=2))
    with pytest.raises(ValueError):session.execute(dataset,{**query(dataset,0),"arguments":{"invalid":1}})
    assert session.status=="open"
    response=session.execute(dataset,query(dataset,0))
    assert response["result"]["returned"]==1
    session._audit_failure(query(dataset,2),"closed")
    assert session.status=="failure_budget_exhausted"
    for _ in range(100):session._audit_failure({},"closed")
    assert len(session.calls)==3
    EvidenceQuerySession.from_dict(session.to_dict())


def test_response_byte_accounting_includes_hash(dataset):
    session=EvidenceQuerySession.create(dataset)
    response=session.execute(dataset,query(dataset,0))
    assert response["resource_usage"]["response_bytes"]==len(stable_json_bytes(response))
    assert session.context_bytes_used==len(stable_json_bytes(response))


def test_semantic_failure_does_not_poison_retry(dataset):
    session=EvidenceQuerySession.create(dataset,budget=QueryBudget(maximum_returned_rows=1))
    session.execute(dataset,query(dataset,0))
    with pytest.raises(ValueError):session.execute(dataset,query(dataset,1))
    session.continue_investigation(budget={"maximum_returned_rows":2},progress_query_ids=["q0"],
        unresolved_hypotheses=["H1"],next_tests=["retrieve next row"],decision_impact="comparison needed")
    assert session.execute(dataset,query(dataset,1))["result"]["returned"]==1


def test_session_rejects_rehashed_counter_corruption(dataset):
    session=EvidenceQuerySession.create(dataset)
    session.execute(dataset,query(dataset,0))
    payload=session.to_dict()
    payload["usage"]["returned_rows"]=0
    payload["session_sha256"]=stable_hash({k:v for k,v in payload.items() if k!="session_sha256"})
    with pytest.raises(ValueError,match="Compteurs"):
        EvidenceQuerySession.from_dict(payload)


def test_batch_selects_complementary_partitions_not_redundant_sources():
    first=request("first")
    same=request("same",partition={"A":"1","B":"1","C":"0","D":"0"})
    complementary=request("other",partition={"A":"yes","B":"no","C":"yes","D":"no"})
    selected=select_minimum_requests([first,same,complementary])["selected"]
    assert {q["request_id"] for q in selected}=={"first","other"}
    assert all(q["marginal_voi_score"]==1 for q in selected)


@pytest.mark.parametrize("field",["effort","source_cost","availability","reliability"])
def test_nonfinite_selection_inputs_rejected(field):
    with pytest.raises(ValueError):normalize_request({**request(),field:float("nan")})


def test_one_extra_question_cycle_requires_completed_progress(tmp_path):
    ready(tmp_path)
    for i in range(2):
        q={**request(f"Q{i}"),"related_hypothesis_ids":[f"H{i}"]}
        branch=None if i==0 else {"trigger_response_ids":["Q0"],"decision_change":"new branch"}
        publish_client_requests(tmp_path,[q],new_material_branch=branch)
        record_canonical_answers(tmp_path,[{**answer(),"request_id":f"Q{i}","answer_id":f"A{i}"}])
        complete_resume(tmp_path,recalculation_refs=["calc.json"],adversarial_review_ref="review.json",
            before_after=[{"hypothesis_id":f"H{i}","before":"unknown","after":"revised",
                           "decision_dimensions":{k:"reassessed" for k in RESUME_DIMENSIONS}}])
    third={**request("Q2"),"related_hypothesis_ids":["H2"]}
    with pytest.raises(ValueError,match="Budget"):
        publish_client_requests(tmp_path,[third],new_material_branch={"trigger_response_ids":["Q1"],"decision_change":"remaining branch"})
    continue_clarification(tmp_path,progress_answer_ids=["A1"],candidates=[third],decision_impact="New material branch after response.")
    assert publish_client_requests(tmp_path,[third],new_material_branch={"trigger_response_ids":["Q1"],"decision_change":"remaining branch"})["must_stop"]
