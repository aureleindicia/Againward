"""Exercise the real transport/parser/intent gates, without rerunning dossiers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from againward.documents.contracts import DocumentError
from againward.domains.rental.autonomous_review import _ask
from againward.domains.rental.case_graph import state_hash
from againward.domains.rental.case_graph_claims import CLAIM_VALUES, _shape
from againward.domains.rental.case_investigator import Budget, investigate, model_provider
from againward.domains.rental.case_investigator_contract import (
    ACTION_FIELDS, RESPONSE_SCHEMA, VERSION, validate_response,
)
from tests.test_rental_case_graph_relations import occurrences, PAIR
from tests.test_rental_case_graph_adapter import complete_graph

FOCUS = "gap-synthetic"


def intent(action, issue_id=FOCUS):
    return {"issue_id": issue_id, "action": action}


def claim(kind="OBSERVATION_DISPOSITION", value="IRRELEVANT", ids=None):
    return {"type": "PROPOSE_CLAIM", "proposal": {"kind": kind, "target": "obs-synthetic",
        "value": value, "evidence_ids": ["obs-synthetic"] if ids is None else ids,
        "reason": "Inspected source supports this proposed decision; independent review remains required"}}


def cli_reply(monkeypatch, raw, inspect=None):
    """Only substitute the CLI process; execute actual _ask and Python gates."""
    calls = []
    def reply(command, **kwargs):
        schema = json.loads(Path(command[command.index("--output-schema") + 1]).read_text())
        calls.append((command, kwargs, schema))
        if inspect:
            inspect(schema, kwargs)
        body = raw(kwargs["input"]) if callable(raw) else raw
        Path(command[command.index("--output-last-message") + 1]).write_bytes(body)
        return SimpleNamespace(returncode=0, stdout="synthetic stdout", stderr="")
    monkeypatch.setattr("againward.domains.rental.autonomous_review.subprocess.run", reply)
    return calls


@pytest.mark.parametrize("action", [
    {"type": "DECLARE_OCCURRENCE", "kind": "INVOICE_LINE", "evidence_ids": ["obs-synthetic"], "anchor_ids": ["obs-synthetic"]},
    *[{"type": kind, "target": "occ-synthetic", "evidence_ids": ["obs-synthetic"]}
      for kind in ["ATTACH_OBSERVATIONS", "REPLACE_OBSERVATIONS"]],
    claim(),
    *[{"type": kind, "target": "target-synthetic"}
      for kind in ["REQUEST_REVIEW", "INSPECT_OCCURRENCE", "INSPECT_ISSUE"]],
    {"type": "REQUEST_REREAD", "source_id": "src-synthetic", "locations": []},
    {"type": "REQUEST_REREAD", "source_id": "src-synthetic", "locations": ["page:1"]},
    {"type": "INSPECT_SOURCE", "source_id": "src-synthetic", "location": "page:1", "start": 0, "end": 10},
    {"type": "REFRESH_RELATIONS"},
    {"type": "MARK_UNRESOLVED", "reason": "Missing original evidence"},
    {"type": "PROPOSE_READY"},
])
def test_each_action_has_exact_native_schema_and_validates(action):
    validate_response(intent(action), FOCUS)
    assert {branch["properties"]["type"]["enum"][0]
            for branch in RESPONSE_SCHEMA["properties"]["action"]["anyOf"]} == set(ACTION_FIELDS)


@pytest.mark.parametrize("kind,value", [(k, v) for k, values in CLAIM_VALUES.items() for v in sorted(values)])
def test_every_claim_enum_shared_by_transport_and_durable_validator(kind, value):
    action = claim(kind, value)
    validate_response(intent(action), FOCUS)
    _shape(action["proposal"])
    branches = ACTION_FIELDS["PROPOSE_CLAIM"]["proposal"]["anyOf"]
    branch = next(b for b in branches if b["properties"]["kind"]["enum"] == [kind])
    assert branch["properties"]["value"]["enum"] == sorted(CLAIM_VALUES[kind])


@pytest.mark.parametrize("response,path,rule", [
    (intent(claim(value="EXCLUDE", ids=[])), "$.action.proposal.value", "enum"),
    (intent(claim(ids=[])), "$.action.proposal.evidence_ids", "array_length"),
    (intent(claim(value="irrelevant")), "$.action.proposal.value", "enum"),
    (intent(claim(kind="READING_ISSUE_RESOLUTION", value="IRRELEVANT")), "$.action.proposal.value", "enum"),
    (intent({"type": "READY"}), "$.action.type", "enum"),
    (intent({"type": "MARK_UNRESOLVED", "reason": "   "}), "$.action.reason", "length"),
    (intent({"type": "REQUEST_REVIEW", "target": "occ-synthetic", "reviewer_role": "HUMAN"}), "$.action", "additionalProperties"),
    (intent({"type": "REQUEST_REVIEW"}), "$.action.target", "required"),
    (intent({"type": "REQUEST_REREAD", "source_id": "src-synthetic", "locations": ["page:1", "page:1"]}), "$.action.locations", "unique_items"),
    (intent(claim(ids=["obs-synthetic", "obs-synthetic"])), "$.action.proposal.evidence_ids", "unique_items"),
    (intent({"type": "INSPECT_SOURCE", "source_id": "src-synthetic", "location": "page:1", "start": True, "end": 10}), "$.action.start", "integer_range"),
    (intent({"type": "INSPECT_SOURCE", "source_id": "src-synthetic", "location": "page:1", "start": "0", "end": 10}), "$.action.start", "integer_range"),
    (intent({"type": "INSPECT_SOURCE", "source_id": "src-synthetic", "location": "page:1", "start": -1, "end": 10}), "$.action.start", "integer_range"),
    (intent({"type": "PROPOSE_READY"}, "other-gap"), "$.issue_id", "focused_issue"),
    ({"payload": json.dumps(intent({"type": "PROPOSE_READY"}))}, "$", "additionalProperties"),
    (intent([{"type": "PROPOSE_READY"}, {"type": "MARK_UNRESOLVED", "reason": "Unknown"}]), "$.action", "object"),
    ({"issue_id": FOCUS}, "$.action", "required"),
    ({**intent({"type": "PROPOSE_READY"}), "calculation": "fabricated"}, "$", "additionalProperties"),
])
def test_invalid_or_ambiguous_intents_have_precise_safe_diagnostics(response, path, rule):
    before = deepcopy(response)
    with pytest.raises(DocumentError) as error:
        validate_response(response, FOCUS)
    assert error.value.code == "EXTRACTION_SCHEMA_INVALID"
    assert error.value.diagnostic["schema_path"] == path
    assert error.value.diagnostic["rule"] == rule
    assert response == before
    assert "EXCLUDE" not in json.dumps(error.value.diagnostic)


def test_null_issue_only_when_no_open_focus():
    validate_response(intent({"type": "PROPOSE_READY"}, None), None)
    with pytest.raises(DocumentError):
        validate_response(intent({"type": "PROPOSE_READY"}, None), FOCUS)


def test_native_transport_passes_real_action_schema_without_string_envelope(monkeypatch):
    raw = json.dumps(intent(claim())).encode()
    def inspect(schema, kwargs):
        assert schema == RESPONSE_SCHEMA
        assert "payload" not in schema["properties"]
        assert "payload STRING" not in kwargs["input"]
    calls = cli_reply(monkeypatch, raw, inspect)
    response = model_provider("synthetic-model", Budget())({"issue_id": FOCUS})
    validate_response(response, FOCUS)
    assert response == intent(claim()) and len(calls) == 1
    assert "synthetic-model" in calls[0][0]


@pytest.mark.parametrize("raw,rule", [
    (b'{"issue_id":"gap-synthetic","action":{"type":"PROPOSE_READY","type":"MARK_UNRESOLVED"}}', "duplicate_member"),
    (b'{"issue_id":"gap-synthetic","action":', "json_syntax"),
    (b'{}{}', "json_syntax"),
    (b'{"action":NaN}', "nonfinite_number"),
    (b'[]', "object_required"),
    (b'\xff', "invalid_utf8"),
])
def test_native_json_rejects_ambiguity_before_intent_with_exact_hash(monkeypatch, raw, rule):
    cli_reply(monkeypatch, raw)
    with pytest.raises(DocumentError) as error:
        model_provider("synthetic-model", Budget())({"issue_id": FOCUS})
    diagnostic = error.value.diagnostic
    assert diagnostic["rule"] == rule
    assert diagnostic["response_sha256"] == hashlib.sha256(raw).hexdigest()
    assert diagnostic["schema_path"] == "$" and diagnostic["raw_retained"] is False


@pytest.mark.parametrize("raw", [
    b'```json\n{"issue_id":"gap-synthetic","action":{"type":"PROPOSE_READY"}}\n```',
    b'{"issue_id":"gap-synthetic","action":{"type":"PROPOSE_READY",},}',
])
def test_only_unambiguous_notation_recovery_preserves_intent(monkeypatch, raw):
    cli_reply(monkeypatch, raw)
    response = model_provider("synthetic-model", Budget())({"issue_id": FOCUS})
    validate_response(response, FOCUS)
    assert response == intent({"type": "PROPOSE_READY"})


@pytest.mark.parametrize("raw", [b'{"action":', json.dumps(intent(claim())).encode()])
def test_evaluation_retains_exact_bytes_and_schema_before_parser_failure(tmp_path, monkeypatch, raw):
    cli_reply(monkeypatch, raw)
    root = tmp_path / "source-snapshot" / "case_graph_v2"
    root.mkdir(parents=True)
    provider = model_provider("synthetic-model", Budget(), evaluation_root=root)
    if raw == b'{"action":':
        with pytest.raises(DocumentError):
            provider({"issue_id": FOCUS})
    else:
        provider({"issue_id": FOCUS})
    files = list((root.parent / "scratch/evaluation_provider_invocations").glob("*/attempt-0/model_response.json"))
    assert len(files) == 1 and files[0].read_bytes() == raw
    assert files[0].stat().st_mode & 0o777 == 0o600
    assert json.loads((files[0].parent / "response_schema.json").read_text()) == RESPONSE_SCHEMA


def test_non_evaluation_never_retains_raw_workspace_artifacts(tmp_path, monkeypatch):
    cli_reply(monkeypatch, json.dumps(intent(claim())).encode())
    model_provider("synthetic-model", Budget())({"issue_id": FOCUS})
    assert list(tmp_path.iterdir()) == []


def test_schema_rejection_is_feedback_with_no_silent_claim_and_bounded_correction(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]], review=False)
    before = state_hash(graph)
    def provider(context):
        if context["feedback"] is None:
            return intent(claim(value="EXCLUDE", ids=[]), context["issue_id"])
        assert context["feedback"]["diagnostic"]["schema_path"] == "$.action.proposal.value"
        return intent({"type": "MARK_UNRESOLVED", "reason": "Cannot establish supported exclusion"}, context["issue_id"])
    result = investigate(graph, root, model="synthetic", provider=provider, budget=Budget(max_turns=2))
    assert result["stop_reason"] == "MATERIAL_AMBIGUITY"
    assert result["metrics"]["rejected_actions"] == 1
    assert state_hash(result["graph"]) == before
    assert not any(row["kind"] == "SEMANTIC_CLAIM" for row in result["graph"]["issues"].values())
    assert result["calculation"] is None and result["response_contract_version"] == VERSION


def test_terminal_json_failure_diagnostic_survives_in_investigation_receipt(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]], review=False)
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", _ask)
    raw = b'{"action":{"type":"PROPOSE_READY","type":"MARK_UNRESOLVED"}}'
    cli_reply(monkeypatch, raw)
    result = investigate(graph, root, model="synthetic-model", evaluation_only=True)
    assert result["stop_reason"] == "PROVIDER_FAILURE"
    assert result["feedback"]["diagnostic"]["rule"] == "duplicate_member"
    receipts = list((root / "case_graph_v2/investigations").glob("*.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text())
    assert receipt["turns"][0]["feedback"]["diagnostic"] == result["feedback"]["diagnostic"]
    assert result["graph"] == graph and result["calculation"] is None
    assert result["metrics"]["model_calls"] == 1


def test_limits_nonfinite_and_oversized_intent_still_fail_closed():
    with pytest.raises(DocumentError, match="EXTRACTION_SCHEMA_INVALID"):
        validate_response(intent({"type": "INSPECT_SOURCE", "start": float("nan")}), FOCUS)
    with pytest.raises(DocumentError, match="RESOURCE_LIMIT"):
        validate_response(intent({"type": "MARK_UNRESOLVED", "reason": "x" * 32_001}), FOCUS)


@pytest.mark.parametrize("complete", [False, True])
def test_native_transport_propose_ready_executes_actual_python_gate_and_engine(tmp_path, monkeypatch, complete):
    if complete:
        root, graph, _ = complete_graph(tmp_path, monkeypatch)
    else:
        root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]], review=False)
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", _ask)
    def reply(prompt):
        context = json.loads(prompt.rsplit("\n", 1)[1])
        return json.dumps(intent({"type": "PROPOSE_READY"}, context["issue_id"])).encode()
    calls = cli_reply(monkeypatch, reply)
    result = investigate(graph, root, model="synthetic", budget=Budget(max_turns=1))
    assert len(calls) == 1 and result["graph"] == graph
    if complete:
        assert result["stop_reason"] == "CALCULATED"
        assert result["calculation"]["groups"][0]["difference"] == "5.00"
    else:
        assert result["feedback"]["rejection_code"] == "CASE_NOT_READY"
        assert result["calculation"] is None and result["remaining_issues"]


def test_evaluation_refuses_linked_scratch_before_raw_write(tmp_path, monkeypatch):
    destination = tmp_path / "outside"
    destination.mkdir()
    (tmp_path / "scratch").symlink_to(destination, target_is_directory=True)
    cli_reply(monkeypatch, json.dumps(intent(claim())).encode())
    with pytest.raises(DocumentError, match="SOURCE_UNSAFE_PATH"):
        model_provider("synthetic", Budget(), evaluation_root=tmp_path / "case_graph_v2")({"issue_id": FOCUS})
    assert list(destination.iterdir()) == []


def test_timeout_keeps_one_call_and_no_retry(tmp_path, monkeypatch):
    calls = []
    def timeout(command, **kwargs):
        calls.append(command)
        raise subprocess.TimeoutExpired(command, 1, output=b"partial", stderr=b"timeout")
    monkeypatch.setattr("againward.domains.rental.autonomous_review.subprocess.run", timeout)
    with pytest.raises(DocumentError, match="MODEL_TIMEOUT"):
        _ask("synthetic", (), model="synthetic", timeout_seconds=1, response_schema=RESPONSE_SCHEMA,
             evaluation_root=tmp_path / "case_graph_v2")
    assert len(calls) == 1
    command_files = list((tmp_path / "scratch/evaluation_provider_invocations").glob("*/attempt-0/command.json"))
    assert len(command_files) == 1 and json.loads(command_files[0].read_text())["timeout"] is True
