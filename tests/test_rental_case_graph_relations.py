"""Reviewed exact anchors link occurrences, never transfer commercial authority."""
from copy import deepcopy

import pytest

from againward.documents.codex_provider import assemble_proposal
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.domains.rental.case_graph import empty_graph, import_reading, replay_evidence
from againward.domains.rental.case_graph_actions import apply_action, bind_action
from againward.domains.rental.case_graph_relations import relation_view, reduce_relations
from againward.domains.rental.case_graph_review import invoke_occurrence_review, reduce_review


def occurrences(tmp_path, monkeypatch, records, *, review=True):
    incoming = tmp_path / "input"
    incoming.mkdir()
    for index, (_, fields) in enumerate(records):
        (incoming / f"source-{index}.txt").write_text(
            f"Record {index}\n" + "\n".join(f"{key}: {value}" for key, value in fields.items()))
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    graph = empty_graph(batch)
    targets = []
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask",
        lambda *a, **k: ({"verdict": "SUPPORTED", "reason": "Scripted review protocol"}, 0.1))
    for index, (kind, fields) in enumerate(records):
        doc = next(d for d in batch.documents if f"source-{index}.txt" in d.original_names)
        parsed = read_document(doc, root)
        raw = {"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": "not-an-identity", "semantic_type": key,
             "value_type": "CURRENCY" if key == "currency" else "TEXT",
             "value": value, "raw_observed_value": f"{key}: {value}",
             "location": next(unit.location for unit in parsed.units if f"{key}: {value}" in unit.text),
             "normalization_notes": "", "ambiguity_flags": []}
            for key, value in fields.items()]}
        payload = validate_proposal(assemble_proposal(raw, doc, parsed, batch.batch_id,
                                                      "synthetic-reader"), batch, root).to_dict()
        graph = import_reading(graph, payload, root, role="PRIMARY")
        ids = [oid for oid, row in graph["observations"].items() if row["source_id"] == doc.source_id]
        before = set(graph["occurrences"])
        graph = apply_action(graph, bind_action(graph, {"type": "DECLARE_OCCURRENCE", "kind": kind,
            "evidence_ids": ids, "anchor_ids": ids}), root)
        target = (set(graph["occurrences"]) - before).pop()
        targets.append(target)
        if review:
            receipt = invoke_occurrence_review(graph, target, root, model="scripted-reviewer")
            graph = reduce_review(graph, receipt, root)
    return root, graph, targets


PAIR = [("INVOICE_LINE", {"agreement_id": "LEASE-Q", "asset_id": "EQ-7"}),
        ("RENTAL_SCOPE", {"agreement_id": "LEASE-Q", "asset_id": "EQ-7"})]


def test_exact_reviewed_unique_anchors_confirm_without_copying_or_authority(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, PAIR)
    facts = deepcopy(graph["observations"])
    subjects = deepcopy(graph["occurrences"])
    result = reduce_relations(graph)
    relation, = result["relations"].values()
    assert relation["state"] == "CONFIRMED"
    assert relation["type"] == "SAME_RENTAL"
    assert relation["support"] == ["agreement_id", "asset_id"]
    assert relation["authority"] == "NONE"
    assert len(relation["source_ids"]) == 2
    assert set(relation["evidence_ids"]) == set(facts)
    assert result["observations"] == facts and result["occurrences"] == subjects
    assert replay_evidence(result, root) == result
    assert reduce_relations(result) == result


def test_unreviewed_exact_ids_do_not_confirm(tmp_path, monkeypatch):
    _, graph, _ = occurrences(tmp_path, monkeypatch, PAIR, review=False)
    relation, = relation_view(graph).values()
    assert relation["state"] == "CANDIDATE"
    assert relation["reason"] == "UNREVIEWED_PREREQUISITE"


def test_equal_asset_alone_is_not_sufficient_identity(tmp_path, monkeypatch):
    records = [(kind, {"asset_id": "EQ-7"}) for kind, _ in PAIR]
    _, graph, _ = occurrences(tmp_path, monkeypatch, records)
    relation, = relation_view(graph).values()
    assert relation["state"] == "CANDIDATE"
    assert relation["reason"] == "INSUFFICIENT_ANCHORS"


def test_supplied_supplier_contradiction_cannot_be_ignored(tmp_path, monkeypatch):
    records = deepcopy(PAIR)
    records[0][1]["supplier_id"] = "VENDOR-U"
    records[1][1]["supplier_id"] = "VENDOR-V"
    _, graph, _ = occurrences(tmp_path, monkeypatch, records)
    relation, = relation_view(graph).values()
    assert relation["state"] == "REJECTED"
    assert relation["contradictions"] == ["supplier_id"]


@pytest.mark.parametrize("partial", [False, True])
def test_multiple_plausible_scopes_remain_ambiguous(tmp_path, monkeypatch, partial):
    extra = {"asset_id": "EQ-7"} if partial else PAIR[1][1]
    _, graph, _ = occurrences(tmp_path, monkeypatch, [*PAIR, ("RENTAL_SCOPE", extra)])
    assert {r["state"] for r in relation_view(graph).values()} == {"AMBIGUOUS"}


def test_new_competing_scope_invalidates_old_confirmed_edge(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, PAIR)
    graph = reduce_relations(graph)
    scope = graph["occurrences"][targets[1]]
    evidence = [oid for ids in scope["fields"].values() for oid in ids]
    graph = apply_action(graph, bind_action(graph, {"type": "DECLARE_OCCURRENCE", "kind": "RENTAL_SCOPE",
        "evidence_ids": evidence, "anchor_ids": evidence[:1]}), root)
    assert {r["state"] for r in relation_view(graph).values()} == {"AMBIGUOUS"}
    graph = reduce_relations(graph)
    assert replay_evidence(graph, root) == graph
    assert any(q["kind"] == "RELATIONSHIP" and q["state"] == "OPEN" for q in graph["issues"].values())


def test_new_negative_review_does_not_leave_a_current_confirmed_edge(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, PAIR)
    graph = reduce_relations(graph)
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask",
        lambda *a, **k: ({"verdict": "AMBIGUOUS", "reason": "Ownership uncertain"}, 0.1))
    receipt = invoke_occurrence_review(graph, targets[0], root, model="scripted-reviewer")
    graph = reduce_review(graph, receipt, root)
    assert {r["state"] for r in relation_view(graph).values()} == {"CANDIDATE"}
    assert replay_evidence(reduce_relations(graph), root)


def test_rehashed_relation_state_cannot_override_replay(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, PAIR, review=False)
    graph = reduce_relations(graph)
    next(iter(graph["relations"].values()))["state"] = "CONFIRMED"
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        replay_evidence(graph, root)


def test_credit_invoice_reference_needs_line_identity_and_same_currency(tmp_path, monkeypatch):
    records = [("CREDIT", {"invoice_id": "BILL-R", "invoice_line_id": "LINE-8", "currency": "EUR"}),
               ("INVOICE_LINE", {"invoice_id": "BILL-R", "invoice_line_id": "LINE-8", "currency": "USD"})]
    _, graph, _ = occurrences(tmp_path, monkeypatch, records)
    relation, = relation_view(graph).values()
    assert relation["state"] == "REJECTED" and relation["contradictions"] == ["currency"]


def test_same_arbitrary_text_or_label_does_not_generate_relationship(tmp_path, monkeypatch):
    records = [(kind, {"description": "Same words"}) for kind, _ in PAIR]
    _, graph, _ = occurrences(tmp_path, monkeypatch, records)
    assert relation_view(graph) == {}


@pytest.mark.parametrize("kind,expected", [("RATE_TERM", "APPLIES_TO"), ("EVENT", "BELONGS_TO")])
def test_term_and_event_identity_does_not_grant_financial_effect(tmp_path, monkeypatch, kind, expected):
    records = [(kind, PAIR[0][1]), PAIR[1]]
    _, graph, _ = occurrences(tmp_path, monkeypatch, records)
    relation, = relation_view(graph).values()
    assert relation["state"] == "CONFIRMED" and relation["type"] == expected
    assert relation["authority"] == "NONE"
    assert all(o["authority"] == "NONE" for o in graph["occurrences"].values())


def test_credit_reference_without_currency_stays_candidate(tmp_path, monkeypatch):
    fields = {"invoice_id": "BILL-R", "invoice_line_id": "LINE-8"}
    _, graph, _ = occurrences(tmp_path, monkeypatch, [("CREDIT", fields), ("INVOICE_LINE", fields)])
    relation, = relation_view(graph).values()
    assert relation["state"] == "CANDIDATE"


def test_relation_view_is_order_invariant(tmp_path, monkeypatch):
    _, graph, _ = occurrences(tmp_path, monkeypatch, PAIR)
    reverse = deepcopy(graph)
    for field in ("observations", "occurrences", "reviews"):
        reverse[field] = dict(reversed(list(reverse[field].items())))
    assert relation_view(graph) == relation_view(reverse)
