"""Generic V2 evidence invariants; no commercial outcome fixtures."""
from copy import deepcopy

import pytest

from againward.documents.codex_provider import assemble_proposal
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.domains.rental.case_graph import (
    empty_graph, graph_hash, import_reading, replay_evidence, save_evidence, state_hash,
)


def evidence(tmp_path):
    incoming = tmp_path / "sources"
    incoming.mkdir()
    (incoming / "record.txt").write_text("Invoice ZX-4. Net amount 72.00 EUR.")
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    doc = batch.documents[0]
    parsed = read_document(doc, root)
    raw = {"status": "SUCCESS", "limitations": [], "candidates": [{
        "entity_id": "model-group", "semantic_type": "net_amount", "value_type": "DECIMAL",
        "value": "72.00", "raw_observed_value": "72.00", "location": parsed.units[0].location,
        "normalization_notes": "", "ambiguity_flags": []}]}
    extraction = validate_proposal(assemble_proposal(raw, doc, parsed, batch.batch_id,
                                                    "synthetic-reader"), batch, root)
    return root, batch, extraction.to_dict()


def test_graph_import_is_idempotent_and_not_promotion(tmp_path):
    root, batch, payload = evidence(tmp_path)
    graph = import_reading(empty_graph(batch), payload, root, role="PRIMARY")
    assert import_reading(graph, payload, root, role="PRIMARY") == graph
    assert graph["occurrences"] == graph["reviews"] == {}
    assert next(iter(graph["observations"].values()))["disposition"] == "UNRESOLVED"
    assert replay_evidence(graph, root) == graph
    assert save_evidence(graph, root).is_file()


def test_graph_equivalence_retains_independent_lineage_without_labels_as_identity(tmp_path):
    root, batch, payload = evidence(tmp_path)
    graph = import_reading(empty_graph(batch), payload, root, role="PRIMARY")
    second = deepcopy(payload)
    second["candidates"][0]["entity_id"] = "other-label"
    from againward.evidence.hashing import stable_hash
    second["extraction_sha256"] = stable_hash({k: v for k, v in second.items() if k != "extraction_sha256"})
    graph = import_reading(graph, second, root, role="INDEPENDENT")
    assert len(graph["observations"]) == 1
    assert len(next(iter(graph["observations"].values()))["origins"]) == 2
    reverse = import_reading(empty_graph(batch), second, root, role="INDEPENDENT")
    reverse = import_reading(reverse, payload, root, role="PRIMARY")
    assert state_hash(reverse) == state_hash(graph)
    assert graph_hash(reverse) != graph_hash(graph)  # Causal import order remains auditable.
    assert replay_evidence(graph, root) == graph


def test_graph_snapshot_cannot_promote_or_rewrite_observation(tmp_path):
    root, batch, payload = evidence(tmp_path)
    graph = import_reading(empty_graph(batch), payload, root, role="PRIMARY")
    next(iter(graph["observations"].values()))["disposition"] = "USED"
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        replay_evidence(graph, root)


def test_graph_replay_detects_source_mutation(tmp_path):
    root, batch, payload = evidence(tmp_path)
    graph = import_reading(empty_graph(batch), payload, root, role="PRIMARY")
    (root / batch.documents[0].blob_path).write_text("changed")
    with pytest.raises(DocumentError):
        replay_evidence(graph, root)


def test_graph_rejects_forged_native_span_even_with_rehashed_payload(tmp_path):
    root, batch, payload = evidence(tmp_path)
    payload["candidates"][0]["source_span"] = [0, 5]
    from againward.evidence.hashing import stable_hash
    payload["extraction_sha256"] = stable_hash({k: v for k, v in payload.items() if k != "extraction_sha256"})
    with pytest.raises(DocumentError, match="SOURCE_LOCATION_INVALID"):
        import_reading(empty_graph(batch), payload, root, role="PRIMARY")


def test_visual_graph_keeps_current_pixels_unreviewed_and_rejects_stale_render(tmp_path):
    from againward.documents.codex_provider import bind_visual_pages, prompt_version_for_guidance
    from againward.evidence.hashing import stable_hash
    from benchmarking.document_renderers import pdf
    incoming = tmp_path / "sources"
    incoming.mkdir()
    pdf(incoming / "record.pdf", ["Returned on 2027-02-03."], scan=True)
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    doc = batch.documents[0]
    parsed = read_document(doc, root)
    version = prompt_version_for_guidance("")
    raw = {"status": "NEEDS_REVIEW", "limitations": [], "candidates": [{
        "entity_id": "any-label", "semantic_type": "date", "value_type": "DATE",
        "value": "2027-02-03", "raw_observed_value": "2027-02-03",
        "location": parsed.units[0].location, "normalization_notes": "Printed date",
        "ambiguity_flags": []}]}
    proposal = assemble_proposal(raw, doc, parsed, batch.batch_id, "synthetic-reader",
        prompt_version=version, invocation_id="visual-test",
        visual_bindings=bind_visual_pages(doc, parsed, root, model="synthetic-reader",
                                         prompt_version=version, invocation_id="visual-test"))
    payload = validate_proposal(proposal, batch, root).to_dict()
    graph = import_reading(empty_graph(batch), payload, root, role="PRIMARY")
    obs = next(iter(graph["observations"].values()))
    assert obs["visual_binding"]["render_sha256"]
    assert obs["source_span"] is None
    assert graph["reviews"] == {}
    assert obs["disposition"] == "UNRESOLVED"
    assert replay_evidence(graph, root) == graph
    payload["visual_bindings"][0]["render_sha256"] = "0" * 64
    payload["extraction_sha256"] = stable_hash({k: v for k, v in payload.items() if k != "extraction_sha256"})
    with pytest.raises(DocumentError, match="SOURCE_LOCATION_INVALID"):
        import_reading(empty_graph(batch), payload, root, role="INDEPENDENT")


def test_equal_values_at_distinct_spans_are_not_collapsed(tmp_path):
    from againward.evidence.hashing import stable_hash
    incoming = tmp_path / "sources"
    incoming.mkdir()
    (incoming / "record.txt").write_text("Row alpha 42.00; row beta 42.00.")
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    doc = batch.documents[0]
    parsed = read_document(doc, root)
    unit = parsed.units[0]
    raw = {"status": "SUCCESS", "limitations": [], "candidates": [{
        "entity_id": "reused-label", "semantic_type": "net_amount", "value_type": "DECIMAL",
        "value": "42.00", "raw_observed_value": "Row alpha 42.00", "location": unit.location,
        "normalization_notes": "Exact row amount", "ambiguity_flags": []}]}
    proposal = assemble_proposal(raw, doc, parsed, batch.batch_id, "synthetic-reader")
    first = proposal["candidates"][0]
    first["raw_observed_value"] = "42.00"
    # Explicit exact coordinates distinguish two identical amounts, not a label.
    start = unit.text.index("42.00")
    first["source_span"] = [start, start + 5]
    second = deepcopy(first)
    second["candidate_id"] = "second-observation"
    start = unit.text.rindex("42.00")
    second["source_span"] = [start, start + 5]
    proposal["candidates"].append(second)
    payload = validate_proposal(proposal, batch, root).to_dict()
    graph = import_reading(empty_graph(batch), payload, root, role="PRIMARY")
    assert len(graph["observations"]) == 2
    assert not graph["occurrences"]
    assert stable_hash(graph) == graph_hash(replay_evidence(graph, root))


def test_same_text_in_different_sources_keeps_distinct_provenance(tmp_path):
    incoming = tmp_path / "sources"
    incoming.mkdir()
    (incoming / "first.txt").write_text("First record: amount 16.00.")
    (incoming / "second.txt").write_text("Second record: amount 16.00.")
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    graph = empty_graph(batch)
    for doc in batch.documents:
        parsed = read_document(doc, root)
        raw = {"status": "SUCCESS", "limitations": [], "candidates": [{
            "entity_id": "same-label", "semantic_type": "net_amount", "value_type": "DECIMAL",
            "value": "16.00", "raw_observed_value": "16.00", "location": parsed.units[0].location,
            "normalization_notes": "", "ambiguity_flags": []}]}
        payload = validate_proposal(assemble_proposal(raw, doc, parsed, batch.batch_id,
                                                      "synthetic-reader"), batch, root).to_dict()
        graph = import_reading(graph, payload, root, role="PRIMARY")
    assert len(graph["observations"]) == 2
    assert len({o["source_id"] for o in graph["observations"].values()}) == 2
    assert graph["relations"] == {}


@pytest.mark.parametrize("change", [{"readings": []}, {"readings": {"x": None}}, {"actions": {}},
                                    {"extra": "unrecognized"}])
def test_malformed_graph_returns_controlled_error(tmp_path, change):
    root, batch, _ = evidence(tmp_path)
    with pytest.raises(DocumentError, match="EXTRACTION_SCHEMA_INVALID"):
        replay_evidence({**empty_graph(batch), **change}, root)
