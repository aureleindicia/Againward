"""V2 projects reviewed evidence into the existing financial engine."""
from copy import deepcopy

import pytest

from againward.documents.contracts import DocumentError
from againward.domains.rental.case_graph_adapter import load_graph_case
from againward.domains.rental.case_graph_claims import bind_claim, reduce_claim
from againward.domains.rental.case_graph_review import invoke_occurrence_review, reduce_review
from againward.domains.rental.reconciliation import reconcile
from tests.test_rental_case_graph_relations import occurrences


def complete_graph(tmp_path, monkeypatch, *, invoice_amount="39.00", scope_changes=None):
    records = [
        ("INVOICE_LINE", {"document_role": "INVOICE", "document_status": "ISSUED",
            "invoice_id": "BILL-T", "agreement_id": "LEASE-R", "asset_id": "EQ-X",
            "currency": "EUR", "net_amount": invoice_amount}),
        ("RENTAL_SCOPE", {"document_role": "RENTAL_AGREEMENT", "document_status": "ACCEPTED",
            "agreement_id": "LEASE-R", "asset_id": "EQ-X", "supplier_id": "VENDOR-R", "client_id": "CUSTOMER-T",
            "start": "2027-03-02", "end": "2027-03-04", "quantity": "1", "description": "Portable pump",
            "rate": "17.00", "currency": "EUR", "billing_unit": "DAY", "quantity_basis": "PER_ITEM",
            "weekends_billable": True, "minimum_days": 0, "stop_event": "CONTRACT_END", "discount_fraction": "0"})]
    records[1][1].update(scope_changes or {})
    root, graph, targets = occurrences(tmp_path, monkeypatch, records)
    for target, kind, value in ((targets[0], "CHARGE_MEANING", "RENTAL"),
                                (targets[1], "CHARGE_MEANING", "RENTAL"),
                                (targets[1], "GOVERNING_TERM", "GOVERNING")):
        evidence = [oid for ids in graph["occurrences"][target]["fields"].values() for oid in ids]
        graph = reduce_claim(graph, bind_claim(graph, {"kind": kind, "target": target,
            "value": value, "evidence_ids": evidence, "reason": "Generic source-supported commercial review"}))
        claim = next(key for key, issue in graph["issues"].items() if issue["kind"] == "SEMANTIC_CLAIM"
                     and issue["details"]["proposal"]["kind"] == kind and issue["details"]["proposal"]["target"] == target)
        receipt = invoke_occurrence_review(graph, claim, root, model="scripted-reviewer")
        graph = reduce_review(graph, receipt, root)
    return root, graph, targets


def test_graph_projects_to_existing_case_and_deterministic_calculation(tmp_path, monkeypatch):
    root, graph, _ = complete_graph(tmp_path, monkeypatch)
    before = deepcopy(graph)
    case, lineage = load_graph_case(graph, root)
    result = reconcile(case)
    assert case.actual_charges[0].net_amount == "39.00"
    assert case.terms[0].rate == "17.00"
    assert case.actual_charges[0].invoice_line_id.startswith("line-")
    assert lineage["technical_derivations"]
    assert graph == before
    assert result["groups"][0]["expected_amount"] == "34.00"
    assert result["groups"][0]["difference"] == "5.00"
    assert result["groups"][0]["limitations"] == []
    assert load_graph_case(graph, root)[0].to_dict() == case.to_dict()


def test_per_scope_rate_does_not_reuse_rented_asset_count_as_rate_quantity(tmp_path, monkeypatch):
    root, graph, _ = complete_graph(tmp_path, monkeypatch,
                                  scope_changes={"quantity": "3", "quantity_basis": "PER_SCOPE"})
    case, _ = load_graph_case(graph, root)
    assert case.periods[0].quantity == "3"
    assert case.terms[0].quantity is None
    assert reconcile(case)["groups"][0]["expected_amount"] == "34.00"


def test_lineage_return_value_cannot_mutate_canonical_graph(tmp_path, monkeypatch):
    root, graph, _ = complete_graph(tmp_path, monkeypatch)
    before = deepcopy(graph)
    _, lineage = load_graph_case(graph, root)
    lineage["observations"].clear()
    assert graph == before


def test_new_observation_cannot_be_ignored_to_project_the_old_reviewed_case(tmp_path, monkeypatch):
    root, graph, _ = complete_graph(tmp_path, monkeypatch)
    graph["issues"]["unreviewed"] = {"kind": "READING_REJECTION", "source_id": None,
        "observation_ids": [], "details": {}, "state": "OPEN", "materiality": "POTENTIALLY_MATERIAL"}
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        load_graph_case(graph, root)  # An unjournaled edit is rejected even before readiness.


def test_stale_source_prevents_projection_even_with_old_positive_reviews(tmp_path, monkeypatch):
    root, graph, _ = complete_graph(tmp_path, monkeypatch)
    (root / graph["batch"]["documents"][0]["blob_path"]).write_text("Changed evidence")
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        load_graph_case(graph, root)
