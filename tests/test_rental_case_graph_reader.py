"""V2 model reads atoms; runtime binds or quarantines them independently."""
import json
from types import SimpleNamespace

import pytest

from againward.documents.contracts import DocumentError
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.domains.rental.case_graph import empty_graph, replay_evidence
from againward.domains.rental.case_graph_reader import invoke_read, reduce_read


def source(tmp_path, content="Invoice NX-8 net 46.00 EUR.", *, visual=False):
    incoming = tmp_path / "input"
    incoming.mkdir()
    if visual:
        from benchmarking.document_renderers import pdf
        pdf(incoming / "scan.pdf", [content], scan=True)
    else:
        (incoming / "record.txt").write_text(content)
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    return root, empty_graph(batch), batch.documents[0]


def scripted(monkeypatch, rows, *, limitations=(), expect_images=False):
    def ask(prompt, images, **kwargs):
        assert "No entity labels" in prompt and "independently" in prompt
        assert bool(images) == expect_images
        assert kwargs["normalize_json"] is True
        return {"observations": rows, "limitations": list(limitations)}, 0.1
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", ask)


def test_atomic_reader_needs_no_model_ids_types_hashes_or_grouping(tmp_path, monkeypatch):
    root, graph, doc = source(tmp_path)
    scripted(monkeypatch, [{"semantic_type": "net_amount", "value": "46.00", "quote": "46.00"},
                           {"semantic_type": "invoice_id", "value": "NX-8", "quote": "NX-8"}])
    receipt = invoke_read(graph, doc.source_id, root, model="scripted-reader", role="PRIMARY")
    result = reduce_read(graph, receipt, root)
    assert len(result["observations"]) == 2
    assert result["occurrences"] == result["reviews"] == {}
    assert all(row["source_sha256"] == doc.sha256 and row["source_span"] for row in result["observations"].values())
    assert {row["value_type"] for row in result["observations"].values()} == {"DECIMAL", "IDENTIFIER"}
    assert [event["type"] for event in result["actions"]] == ["SOURCE_READ"]
    assert replay_evidence(result, root) == result
    assert reduce_read(result, receipt, root) == result


def test_nonexact_observation_is_quarantined_without_losing_valid_atoms(tmp_path, monkeypatch):
    root, graph, doc = source(tmp_path)
    scripted(monkeypatch, [{"semantic_type": "net_amount", "value": "46.00", "quote": "46.00"},
                           {"semantic_type": "invoice_id", "value": "NX-8", "quote": "Paraphrased invoice NX-8"}])
    receipt = invoke_read(graph, doc.source_id, root, model="scripted-reader", role="PRIMARY")
    result = reduce_read(graph, receipt, root)
    assert len(result["observations"]) == 1
    rejection, = [q for q in result["issues"].values() if q["kind"] == "READING_REJECTION"]
    assert rejection["details"]["index"] == 1
    assert rejection["details"]["code"] == "SOURCE_LOCATION_INVALID"
    assert rejection["state"] == "OPEN" and rejection["materiality"] == "POTENTIALLY_MATERIAL"
    assert replay_evidence(result, root) == result


def test_material_null_stays_an_issue_and_never_becomes_zero(tmp_path, monkeypatch):
    root, graph, doc = source(tmp_path)
    scripted(monkeypatch, [{"semantic_type": "net_amount", "value": None, "quote": "46.00"}])
    receipt = invoke_read(graph, doc.source_id, root, model="scripted-reader", role="PRIMARY")
    result = reduce_read(graph, receipt, root)
    assert result["observations"] == {}
    assert any(q["kind"] == "READING_REJECTION" for q in result["issues"].values())
    assert replay_evidence(result, root) == result


def test_repeated_quote_without_a_unique_location_is_not_assigned_arbitrarily(tmp_path, monkeypatch):
    root, graph, doc = source(tmp_path, "First record 46.00.\nSecond record 46.00.")
    scripted(monkeypatch, [{"semantic_type": "net_amount", "value": "46.00", "quote": "46.00"}])
    receipt = invoke_read(graph, doc.source_id, root, model="scripted-reader", role="PRIMARY")
    result = reduce_read(graph, receipt, root)
    assert not result["observations"]
    assert next(iter(result["issues"].values()))["details"]["code"] == "SOURCE_LOCATION_INVALID"


def test_visual_reading_has_runtime_bound_actual_page_and_pixels(tmp_path, monkeypatch):
    root, graph, doc = source(tmp_path, visual=True)
    location = read_document(doc, root).units[0].location
    scripted(monkeypatch, [{"semantic_type": "net_amount", "value": "46.00", "quote": "46.00",
                            "location": location}], expect_images=True)
    receipt = invoke_read(graph, doc.source_id, root, model="scripted-reader", role="PRIMARY")
    result = reduce_read(graph, receipt, root)
    observation, = result["observations"].values()
    assert observation["visual_binding"]["render_sha256"]
    assert observation["location"] == location and observation["disposition"] == "UNRESOLVED"
    assert replay_evidence(result, root) == result


def test_empty_source_read_and_limitations_are_not_silent_success(tmp_path, monkeypatch):
    root, graph, doc = source(tmp_path)
    scripted(monkeypatch, [], limitations=["Meaning uncertain"])
    receipt = invoke_read(graph, doc.source_id, root, model="scripted-reader", role="PRIMARY")
    result = reduce_read(graph, receipt, root)
    assert len(result["issues"]) == 2 and not result["observations"]
    assert all(q["state"] == "OPEN" for q in result["issues"].values())
    assert replay_evidence(result, root) == result


def test_reader_source_mutation_is_rejected_before_replay(tmp_path, monkeypatch):
    root, graph, doc = source(tmp_path)
    scripted(monkeypatch, [{"semantic_type": "net_amount", "value": "46.00", "quote": "46.00"}])
    receipt = invoke_read(graph, doc.source_id, root, model="scripted-reader", role="PRIMARY")
    (root / doc.blob_path).write_text("Different document")
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        reduce_read(graph, receipt, root)


def test_reader_replay_refuses_a_different_normalization_contract(tmp_path, monkeypatch):
    from againward.core.artifact_store import read_json, write_json
    from againward.evidence.hashing import stable_hash
    root, graph, doc = source(tmp_path)
    scripted(monkeypatch, [{"semantic_type": "net_amount", "value": "46.00", "quote": "46.00"}])
    receipt = invoke_read(graph, doc.source_id, root, model="scripted-reader", role="PRIMARY")
    directory = root / "case_graph_v2" / "reader_invocations"
    body = read_json(directory / (receipt + ".json"))
    body.pop("receipt_sha256")
    body["normalization_version"] = "unavailable-historical-contract"
    replacement = stable_hash(body)
    write_json(directory / (replacement + ".json"), {**body, "receipt_sha256": replacement})
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        reduce_read(graph, replacement, root)
    assert not graph["observations"] and not graph["actions"]


def test_wrong_rate_observation_is_quarantined_and_exact_denominator_recovered(tmp_path, monkeypatch):
    quote = "Rental rate EUR 21 per item per calendar day"
    root, graph, doc = source(tmp_path, quote)
    scripted(monkeypatch, [{"semantic_type": "quantity_basis", "value": "PER_SCOPE", "quote": quote}])
    receipt = invoke_read(graph, doc.source_id, root, model="scripted-reader", role="PRIMARY")
    result = reduce_read(graph, receipt, root)
    fields = {row["semantic_type"]: row["value"] for row in result["observations"].values()}
    assert fields["quantity_basis"] == "PER_ITEM" and fields["billing_unit"] == "DAY"
    assert any(q["kind"] == "READING_REJECTION" and q["state"] == "OPEN" for q in result["issues"].values())
    assert all(row["disposition"] == "UNRESOLVED" for row in result["observations"].values())
    assert replay_evidence(result, root) == result


def test_visual_reader_cannot_invent_an_unavailable_page(tmp_path, monkeypatch):
    root, graph, doc = source(tmp_path, visual=True)
    scripted(monkeypatch, [{"semantic_type": "net_amount", "value": "46.00", "quote": "46.00",
                            "location": "page:99"}], expect_images=True)
    receipt = invoke_read(graph, doc.source_id, root, model="scripted-reader", role="PRIMARY")
    result = reduce_read(graph, receipt, root)
    assert not result["observations"]
    assert any(q["details"]["code"] == "SOURCE_LOCATION_INVALID" for q in result["issues"].values())


def test_stale_visual_binding_is_not_admitted_as_an_observation(tmp_path, monkeypatch):
    from againward.core.artifact_store import read_json, write_json
    from againward.evidence.hashing import stable_hash
    root, graph, doc = source(tmp_path, visual=True)
    scripted(monkeypatch, [{"semantic_type": "net_amount", "value": "46.00", "quote": "46.00"}], expect_images=True)
    receipt = invoke_read(graph, doc.source_id, root, model="scripted-reader", role="PRIMARY")
    path = root / "case_graph_v2" / "reader_invocations"
    body = read_json(path / (receipt + ".json"))
    body.pop("receipt_sha256")
    body["visual_bindings"][0]["render_sha256"] = "0" * 64
    forged = stable_hash(body)
    write_json(path / (forged + ".json"), {**body, "receipt_sha256": forged})
    result = reduce_read(graph, forged, root)
    assert not result["observations"]
    assert any(q["details"]["code"] == "SOURCE_LOCATION_INVALID" for q in result["issues"].values())


def test_v2_runtime_recovers_json_notation_but_rejects_duplicate_decisions(monkeypatch):
    from pathlib import Path
    from againward.domains.rental.autonomous_review import _ask

    def subprocess_reply(command, **kwargs):
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps({"payload": '```json\n{"verdict":"SUPPORTED",}\n```'}))
        return SimpleNamespace(returncode=0, stderr="")
    monkeypatch.setattr("againward.domains.rental.autonomous_review.subprocess.run", subprocess_reply)
    result, _ = _ask("synthetic", (), model="scripted", timeout_seconds=2, normalize_json=True)
    assert result == {"verdict": "SUPPORTED"}

    def contradictory_reply(command, **kwargs):
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps({"payload": '{"verdict":"SUPPORTED","verdict":"UNSUPPORTED"}'}))
        return SimpleNamespace(returncode=0, stderr="")
    monkeypatch.setattr("againward.domains.rental.autonomous_review.subprocess.run", contradictory_reply)
    with pytest.raises(DocumentError, match="EXTRACTION_SCHEMA_INVALID"):
        _ask("synthetic", (), model="scripted", timeout_seconds=2, normalize_json=True)
