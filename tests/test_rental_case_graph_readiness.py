"""Financial prerequisites expose missing evidence, never fill numeric gaps."""
from copy import deepcopy

from againward.domains.rental.case_graph_readiness import prerequisites
from tests.test_rental_case_graph_relations import occurrences, PAIR


def test_reviewed_identity_is_not_financial_readiness(tmp_path, monkeypatch):
    _, graph, targets = occurrences(tmp_path, monkeypatch, PAIR)
    result = prerequisites(graph)
    assert not result["prerequisites_satisfied"]
    assert any(gap["target"] == targets[0] and gap.get("field") == "net_amount" for gap in result["gaps"])
    assert any(gap.get("field") == "CHARGE_MEANING" for gap in result["gaps"])
    assert not any(gap["kind"] == "UNIQUE_RELATION_REQUIRED" for gap in result["gaps"])


def test_numeric_zero_is_present_but_missing_rate_is_not_zero(tmp_path, monkeypatch):
    records = deepcopy(PAIR)
    records[0][1].update(net_amount="0.00", currency="EUR")
    _, graph, targets = occurrences(tmp_path, monkeypatch, records)
    result = prerequisites(graph)
    assert not any(gap.get("field") == "net_amount" for gap in result["gaps"])
    assert any(gap["target"] == targets[1] and gap["kind"] == "APPLICABLE_TERM_REQUIRED" for gap in result["gaps"])


def test_temporal_rate_requires_conventions_without_fabricated_defaults(tmp_path, monkeypatch):
    records = deepcopy(PAIR)
    records[1][1].update(rate="17.00", currency="EUR", billing_unit="MONTH")
    _, graph, targets = occurrences(tmp_path, monkeypatch, records)
    before = deepcopy(graph)
    result = prerequisites(graph)
    missing = {gap.get("field") for gap in result["gaps"] if gap["target"] == targets[1]}
    assert {"partial_period_policy", "weekends_billable", "minimum_days", "discount_fraction",
            "quantity_basis", "stop_event", "GOVERNING_TERM"} <= missing
    assert graph == before


def test_unique_relation_does_not_grant_credit_allocation(tmp_path, monkeypatch):
    records = [("INVOICE_LINE", {"invoice_id": "DOC-K", "invoice_line_id": "ROW-M", "currency": "EUR"}),
               ("CREDIT", {"credit_id": "CR-Q", "invoice_id": "DOC-K", "invoice_line_id": "ROW-M",
                           "currency": "EUR", "net_amount": "13.00", "status": "ISSUED"})]
    _, graph, targets = occurrences(tmp_path, monkeypatch, records)
    result = prerequisites(graph)
    assert any(gap["target"] == targets[1] and gap.get("field") == "allocation_state" for gap in result["gaps"])
    assert not result["prerequisites_satisfied"]


def test_missing_line_id_is_not_a_missing_commercial_fact(tmp_path, monkeypatch):
    _, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]])
    result = prerequisites(graph)
    assert not any(gap.get("field") in {"invoice_line_id", "charge_key", "entity_kind"} for gap in result["gaps"])


def test_supporting_container_cannot_hide_financial_evidence(tmp_path, monkeypatch):
    _, graph, _ = occurrences(tmp_path, monkeypatch, [("SUPPORTING_RECORD", {"net_amount": "23.00"})])
    assert any(gap["kind"] == "SUPPORTING_MATERIALITY_REVIEW_REQUIRED" for gap in prerequisites(graph)["gaps"])


def test_two_containers_cannot_count_one_amount_observation_twice(tmp_path, monkeypatch):
    from againward.domains.rental.case_graph_actions import apply_action, bind_action
    root, graph, targets = occurrences(tmp_path, monkeypatch, [
        ("INVOICE_LINE", {"invoice_id": "DOC-S", "net_amount": "23.00", "currency": "EUR"})])
    ids = [oid for group in graph["occurrences"][targets[0]]["fields"].values() for oid in group]
    graph = apply_action(graph, bind_action(graph, {"type": "DECLARE_OCCURRENCE", "kind": "INVOICE_LINE",
        "evidence_ids": ids, "anchor_ids": ids[:1]}), root)
    assert len(graph["occurrences"]) == 2
    assert any(gap["kind"] == "MATERIAL_OBSERVATION_REUSED" for gap in prerequisites(graph)["gaps"])
