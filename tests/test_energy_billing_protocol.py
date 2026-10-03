import json
import subprocess
from copy import deepcopy
from dataclasses import replace
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from againward.documents.readers import ParsedDocument, SourceUnit
from againward.domains.energy_billing.evidence import bind_reading, replay_atom
from againward.domains.energy_billing.protocol import (
    ACTION_FIELDS,
    ACTION_SCHEMA,
    READ_SCHEMA,
    REVIEW_SCHEMA,
    BillingFailure,
    decode,
    validate,
    validate_action,
    validate_read_envelope,
)
from againward.domains.energy_billing.provider import CodexTransport, ModelBoundary


def intent(kind="MARK_UNRESOLVED"):
    action = {"type": kind}
    for key in ACTION_FIELDS[kind]:
        action[key] = ["e-1"] if key == "evidence_ids" else "No evidence." if key == "reason" else "target-1"
    return {"issue_id": "issue-1", "action": action}


@pytest.mark.parametrize("kind", list(ACTION_FIELDS))
def test_all_actions_exact_schema(kind):
    validate_action(intent(kind), issue_id="issue-1", targets={"target-1"})


@pytest.mark.parametrize("change,path", [
    (lambda r: r.update(extra=True), "$"),
    (lambda r: r.update(issue_id="wrong"), "$.issue_id"),
    (lambda r: r["action"].update(type="EXCLUDE"), "$.action.type"),
    (lambda r: r["action"].update(reason={"free": "JSON"}), "$.action.reason"),
    (lambda r: r["action"].update(reason='{"hidden":"json"}'), "$.action.reason"),
    (lambda r: r["action"].pop("reason"), "$.action.reason"),
])
def test_action_errors_are_precise_and_no_mutation(change, path):
    value = intent()
    change(value)
    before = deepcopy(value)
    with pytest.raises(BillingFailure) as error:
        validate_action(value, issue_id="issue-1")
    assert error.value.diagnostic["path"] == path
    assert error.value.code == "MODEL_PROTOCOL_INVALID"
    assert error.value.diagnostic["state_mutated"] is False
    assert value == before


def test_bad_target_and_duplicate_ids_remain_invalid():
    with pytest.raises(BillingFailure, match="known local target"):
        validate_action(intent("REQUEST_REVIEW"), issue_id="issue-1", targets={"different"})
    value = intent("DECLARE_TARIFF")
    value["action"]["evidence_ids"] = ["e-1", "e-1"]
    with pytest.raises(BillingFailure, match="unique references"):
        validate_action(value, issue_id="issue-1")
    assert "uniqueItems" not in json.dumps(ACTION_SCHEMA)


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"x":NaN}', b'{"x":Infinity}',
                                  b'{"broken":', b'{}{}', b'[]', b'\xff', b'```json\n{}\n```'])
def test_strict_json_rejects_ambiguity(raw):
    with pytest.raises(BillingFailure) as failure:
        decode(raw, stage="ACTION")
    assert len(failure.value.diagnostic["response_sha256"]) == 64


def test_repair_is_bounded_and_does_not_mutate_state():
    responses = iter([b'{"issue_id":"issue-1","action":{"type":"EXCLUDE"}}', json.dumps(intent()).encode()])
    prompts = []

    def transport(prompt, schema):
        prompts.append(prompt)
        assert schema == ACTION_SCHEMA
        return next(responses)

    boundary = ModelBoundary(transport)
    result = boundary.ask("Local issue.", ACTION_SCHEMA, stage="ACTION",
                          checker=partial(validate_action, issue_id="issue-1"))
    assert result == intent()
    assert boundary.calls == 2
    assert len(boundary.diagnostics) == 1
    assert "$.action.type" in prompts[1]
    assert "EXCLUDE" not in prompts[1]  # No untrusted previous answer reinjected.


def test_repeated_invalid_is_protocol_failure_not_business_unresolved():
    boundary = ModelBoundary(lambda *_: b"not json")
    with pytest.raises(BillingFailure) as failure:
        boundary.ask("Local issue", ACTION_SCHEMA, stage="ACTION")
    assert failure.value.code == "MODEL_PROTOCOL_FAILURE"
    assert boundary.calls == 2
    assert len(boundary.diagnostics) == 2
    assert all(not row["state_mutated"] for row in boundary.diagnostics)


def test_provider_failure_has_no_protocol_retry():
    def transport(*_):
        raise BillingFailure("MODEL_PROVIDER_FAILURE", stage="PROVIDER", cause="TIMEOUT")

    boundary = ModelBoundary(transport)
    with pytest.raises(BillingFailure) as failure:
        boundary.ask("Local issue", ACTION_SCHEMA, stage="ACTION")
    assert failure.value.code == "MODEL_PROVIDER_FAILURE"
    assert boundary.calls == 1


def test_protocol_failure_diagnostic_is_serializable_and_private(tmp_path, monkeypatch):
    def invoke(command, **kwargs):
        return SimpleNamespace(returncode=1, stdout=b"", stderr=b"Invalid schema: uniqueItems")

    monkeypatch.setattr(subprocess, "run", invoke)
    transport = CodexTransport("test-model", evaluation_root=tmp_path / "raw")
    with pytest.raises(BillingFailure) as failure:
        transport("No sources", REVIEW_SCHEMA)
    assert failure.value.code == "MODEL_PROTOCOL_FAILURE"
    json.dumps(failure.value.diagnostic, allow_nan=False)
    json.dumps(transport.calls, allow_nan=False)
    for path in (tmp_path / "raw").rglob("*"):
        assert path.stat().st_mode & 0o777 == (0o700 if path.is_dir() else 0o600)


@pytest.mark.parametrize("exception,code", [
    (subprocess.TimeoutExpired("codex", 90), "MODEL_PROVIDER_FAILURE"),
    (FileNotFoundError(), "MODEL_PROVIDER_FAILURE"),
])
def test_transport_distinguishes_runtime_failure(monkeypatch, exception, code):
    def invoke(*args, **kwargs):
        raise exception

    monkeypatch.setattr(subprocess, "run", invoke)
    transport = CodexTransport("test-model")
    with pytest.raises(BillingFailure) as failure:
        transport("No sources", ACTION_SCHEMA)
    assert failure.value.code == code
    assert len(transport.calls) == 1


def test_success_has_direct_schema_without_embedded_json(tmp_path, monkeypatch):
    def invoke(command, **kwargs):
        schema = json.loads(Path(command[command.index("--output-schema") + 1]).read_text())
        assert schema == ACTION_SCHEMA
        assert "payload" not in schema["properties"]
        Path(command[command.index("--output-last-message") + 1]).write_bytes(json.dumps(intent()).encode())
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", invoke)
    transport = CodexTransport("test-model")
    boundary = ModelBoundary(transport)
    assert boundary.ask("Issue", ACTION_SCHEMA, stage="ACTION") == intent()
    assert transport.calls[0]["raw_retained"] is False


def parsed():
    return ParsedDocument("src-test", "reader-test", (
        SourceUnit("src-test", "line:1", "Invoice: INV-01", "NATIVE", {}),
        SourceUnit("src-test", "line:2", "Quantity: 1200 kWh", "NATIVE", {}),
    ), ())


def row(field="invoice_id", location="line:1", quote="Invoice: INV-01", value="INV-01"):
    return {"field": field, "group": "document", "location": location, "quote": quote, "value": value}


@pytest.mark.parametrize("material", [False, True])
def test_invalid_atom_quarantined_independently(material):
    bad = row(field="quantity" if material else "note", quote="not on source")
    payload = {"observations": [row(), bad, row("quantity", "line:2", "Quantity: 1200 kWh", "1200")],
               "limitations": []}
    source = parsed()
    reading = bind_reading(payload, source)
    assert len(reading.observations) == 2
    assert len(reading.quarantine) == 1
    assert reading.quarantine[0]["potentially_material"] is material
    for atom in reading.observations:
        replay_atom(atom, source)


def test_duplicate_read_and_group_labels_share_same_evidence_identity():
    first = row()
    duplicate = {**first, "group": "other-label"}
    reading = bind_reading({"observations": [first, duplicate], "limitations": []}, parsed())
    assert len(reading.observations) == 1
    assert reading.groups["document"] == reading.groups["other-label"]


def test_wrong_span_or_changed_source_fails_replay():
    atom = bind_reading({"observations": [row()], "limitations": []}, parsed()).observations[0]
    with pytest.raises(BillingFailure):
        replay_atom(replace(atom, start=atom.start + 1), parsed())
    changed = replace(parsed(), units=(SourceUnit("src-test", "line:1", "Other Invoice: INV-01", "NATIVE", {}),))
    with pytest.raises(BillingFailure):
        replay_atom(atom, changed)


def test_malformed_atom_type_does_not_kill_valid_atom():
    result = bind_reading({"observations": [None, row()], "limitations": []}, parsed())
    assert len(result.observations) == 1
    assert result.quarantine[0]["potentially_material"] is True


def test_envelope_error_still_repairs_without_erasing_existing_state():
    validate_read_envelope({"observations": [None, row()], "limitations": []})
    with pytest.raises(BillingFailure):
        validate_read_envelope({"observations": [], "limitations": [], "case": {}})
    with pytest.raises(BillingFailure):
        validate({"observations": [None], "limitations": []}, READ_SCHEMA, stage="READ")
