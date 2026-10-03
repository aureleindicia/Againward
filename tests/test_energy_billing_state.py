"""Generic source/state integration; scripted model is not provider proof."""
import json

import pytest

from againward.documents.sources import inventory_sources
from againward.domains.energy_billing.calculation import calculate, readiness
from againward.domains.energy_billing.investigator import semantic_hash
from againward.domains.energy_billing.protocol import BillingFailure
from againward.domains.energy_billing.provider import ModelBoundary
from againward.domains.energy_billing.reader import read_source
from againward.domains.energy_billing.reporting import render_report
from againward.domains.energy_billing.review import current_review, request_review
from againward.domains.energy_billing.state import commit_event, initialize, load_state


def action(state, root, kind, **payload):
    return commit_event(state, {"type": "ACTION", "focus": "local-issue",
                        "response": {"issue_id": "local-issue", "action": {"type": kind, **payload}}}, root)


def receipt(state, target, root, **changes):
    row = state["occurrences"].get(target) or state["relations"][target]
    ids = row["evidence_ids"]
    if row["kind"] == "GOVERNS":
        ids = sorted(set(ids + state["occurrences"][row["invoice_id"]]["evidence_ids"]
                         + state["occurrences"][row["tariff_id"]]["evidence_ids"]))
        response = {"verdict": "SUPPORTED", "evidence_ids": ids, "reason": "Accepted applicable original contractual terms.",
                    "authority_kind": "ACCEPTED_CONTRACT"}
        from againward.domains.energy_billing.review import current_sources
        sid = state["occurrences"][row["tariff_id"]]["source_id"]
        context = next(c for c in current_sources(state, target, root) if c["source_id"] == sid)
        clause = next(unit for unit in context["units"] if "Authority: Accepted commercial terms" in unit["text"])
        response.update(authority_source_id=sid, authority_location=clause["location"],
                        authority_quote="Authority: Accepted commercial terms for this contract.")
        if changes.get("authority_kind") == "INVOICE_PRICE":
            sid = state["occurrences"][row["invoice_id"]]["source_id"]
            atom = next(atom for atom in state["observations"].values() if atom["source_id"] == sid and atom["field"] == "billed_amount")
            response.update(authority_source_id=sid, authority_location=atom["location"], authority_quote=atom["quote"])
    else:
        response = {"verdict": "SUPPORTED", "evidence_ids": ids, "reason": "All exact scalar values independently source-checked.",
                    "coverage": "ALL_MATERIAL_FACTS_BOUND", "charge_kind": "CONSUMPTION_HT", "end_convention": "EXCLUSIVE",
                    "nonmaterial_quarantine_ids": [key for key, item in state["quarantine"].items()
                                                  if item["source_id"] == row["source_id"] and not item["potentially_material"]]}
        if row["kind"] == "TARIFF":
            response.update(tariff_type="FIXED", rounding_rule="HALF_UP_PER_LINE")
    response.update(changes)
    boundary = ModelBoundary(lambda *_: json.dumps(response).encode())
    digest = request_review(state, target, root, model="SCRIPTED", boundary=boundary)
    return commit_event(state, {"type": "REVIEW", "receipt_sha256": digest}, root)


def case(tmp_path, *, invoice_changes=None, tariff_changes=None, bad_atom=None, reviews=True, reader_changes=None, notes=(0, 0)):
    iv = {"invoice_id": "INV-Generic", "supplier_id": "SUPPLIER", "pdl": "12345678901234", "currency": "EUR",
          "period_start": "2026-02-01", "period_end": "2026-03-01", "quantity": "1501", "quantity_unit": "kWh",
          "billed_amount": "223.00"}
    tv = {"contract_id": "TERMS-Generic", "supplier_id": "SUPPLIER", "pdl": "12345678901234", "currency": "EUR",
          "effective_start": "2026-01-01", "effective_end": "2027-01-01", "tariff_price": "0.123",
          "price_unit": "EUR/kWh", "rounding_rule": "HALF_UP_PER_LINE", "tariff_type": "FIXED"}
    iv.update(invoice_changes or {})
    tv.update(tariff_changes or {})
    source = tmp_path / "input"
    source.mkdir()
    for name, values in (("invoice", iv), ("tariff", tv)):
        count = notes[0] if values is iv else notes[1]
        lines = [key + ": " + value for key, value in values.items()]
        lines.extend(f"Annotation {i}: informational text {i}" for i in range(count))
        if values is tv:
            lines[0] += " ; Authority: Accepted commercial terms for this contract."
        (source / (name + ".txt")).write_text("\n".join(lines))
    root = tmp_path / "state"
    batch = inventory_sources(source, root)
    state = initialize(batch, root)
    for doc in batch.documents:
        values = iv if "invoice.txt" in doc.original_names else tv
        rows = [{"field": key, "value": value, "group": "document", "location": f"line:{index+1}",
                 "quote": key + ": " + value} for index, (key, value) in enumerate(values.items())]
        count = notes[0] if values is iv else notes[1]
        rows.extend({"field": "note", "value": f"informational text {i}", "group": "annotation",
                     "location": f"line:{len(values)+i+1}", "quote": f"Annotation {i}: informational text {i}"}
                    for i in range(count))
        if values is iv and reader_changes:
            for row in rows:
                row.update(reader_changes.get(row["field"], {}))
        if bad_atom and values is iv:
            rows.append(bad_atom)
        boundary = ModelBoundary(lambda *_: json.dumps({"observations": rows, "limitations": []}).encode())
        digest = read_source(batch, doc.source_id, root, model="SCRIPTED", boundary=boundary, role="PRIMARY")
        state = commit_event(state, {"type": "READ", "receipt_sha256": digest}, root)
        ids = [eid for eid, row in state["observations"].items() if row["source_id"] == doc.source_id]
        state = action(state, root, "DECLARE_INVOICE" if values is iv else "DECLARE_TARIFF", evidence_ids=ids)
    iid = next(key for key, row in state["occurrences"].items() if row["kind"] == "INVOICE")
    tid = next(key for key, row in state["occurrences"].items() if row["kind"] == "TARIFF")
    ids = [state["occurrences"][iid]["evidence_ids"][0], state["occurrences"][tid]["evidence_ids"][0]]
    state = action(state, root, "LINK_TARIFF", invoice_id=iid, tariff_id=tid, evidence_ids=ids)
    rid = next(iter(state["relations"]))
    if reviews:
        for target in (iid, tid, rid):
            state = receipt(state, target, root)
    return state, root, iid, tid, rid


def test_supported_source_state_replay_calculation_and_real_pdf(tmp_path):
    state, root, *_ = case(tmp_path)
    assert load_state(root) == state
    result = calculate(state, root)
    # Independent exact oracle: 1501 * .123 = 184.623 → 184.62.
    assert result["billed_cents"] == 22300
    assert result["expected_cents"] == 18462
    assert result["discrepancy_cents"] == 3838
    report = render_report(root, result["calculation_sha256"])
    assert (root / report["files"]["report.pdf"]["path"]).read_bytes().startswith(b"%PDF-")
    text = (root / report["files"]["report.md"]["path"]).read_text()
    assert "184.62 EUR" in text and "38.38 EUR" in text
    assert report["qa_state"] == "NOT_PERFORMED" and report["delivery_state"] == "INTERNAL_REVIEW_REQUIRED"


@pytest.mark.parametrize("changes, expected", [
    ({"pdl": "98765432109876"}, "RELATION_AMBIGUOUS"),
    ({"supplier_id": "OTHER"}, "RELATION_AMBIGUOUS"),
    ({"effective_start": "2026-02-02"}, "AUTHORITY_UNRESOLVED"),
    ({"effective_end": "2026-02-28"}, "AUTHORITY_UNRESOLVED"),
    ({"currency": "USD"}, "UNSUPPORTED_DOMAIN_RULE"),
    ({"price_unit": "EUR/hour"}, "UNSUPPORTED_DOMAIN_RULE"),
])
def test_neighbor_authority_and_envelope_failures_have_one_root(tmp_path, changes, expected):
    state, root, *_ = case(tmp_path, tariff_changes=changes)
    decision = readiness(state, root)
    assert not decision["ready"] and decision["root_issues"][0]["code"] == expected
    assert len(decision["root_issues"]) == 1 and "expected_cents" not in decision
    with pytest.raises(BillingFailure) as failure:
        calculate(state, root)
    assert failure.value.code == "READINESS_BLOCKED"


def test_invoice_price_is_not_contractual_authority(tmp_path):
    state, root, _, _, rid = case(tmp_path)
    state = receipt(state, rid, root, authority_kind="INVOICE_PRICE")
    assert readiness(state, root)["root_issues"][0]["code"] == "AUTHORITY_UNRESOLVED"


def test_unsupported_tariff_convention_is_explicit_not_defaulted(tmp_path):
    state, root, _, tid, _ = case(tmp_path)
    state = receipt(state, tid, root, tariff_type="INDEXED")
    assert readiness(state, root)["support_state"] == "UNSUPPORTED"


@pytest.mark.parametrize("field, material", [("note", False), ("billed_amount", True)])
def test_local_invalid_atom_survives_to_readiness(tmp_path, field, material):
    atom = {"field": field, "group": "bad", "value": "junk", "location": "line:999", "quote": "not present"}
    state, root, *_ = case(tmp_path, bad_atom=atom)
    assert len(state["quarantine"]) == 1 and len(state["occurrences"]) == 2
    assert readiness(state, root)["ready"] is not material


def test_duplicate_actions_and_evidence_do_not_duplicate_money(tmp_path):
    state, root, iid, tid, rid = case(tmp_path)
    before = calculate(state, root)
    state = action(state, root, "DECLARE_INVOICE", evidence_ids=state["occurrences"][iid]["evidence_ids"])
    state = action(state, root, "LINK_TARIFF", invoice_id=iid, tariff_id=tid, evidence_ids=state["relations"][rid]["evidence_ids"])
    assert len(state["occurrences"]) == 2 and len(state["relations"]) == 1
    assert calculate(state, root) == before


def test_invalid_action_is_transactionally_nonmutating(tmp_path):
    state, root, *_ = case(tmp_path)
    before = (root / "energy_billing" / "state.json").read_bytes()
    with pytest.raises(BillingFailure):
        action(state, root, "DECLARE_TARIFF", evidence_ids=["unknown"])
    assert (root / "energy_billing" / "state.json").read_bytes() == before


def test_mutated_dependency_preserves_history_but_blocks_consumers(tmp_path):
    state, root, iid, tid, _ = case(tmp_path)
    doc = next(d for d in state["batch"]["documents"] if d["source_id"] == state["occurrences"][tid]["source_id"])
    (root / doc["blob_path"]).write_text("Changed tariff bytes")
    assert load_state(root) == state
    assert current_review(state, iid, root)["verdict"] == "SUPPORTED"
    assert readiness(state, root)["root_issues"][0]["code"] == "SOURCE_CHANGED"


def test_repeated_reread_receipt_is_not_semantic_progress(tmp_path):
    state, root, *_ = case(tmp_path)
    event = json.loads((root / "energy_billing" / "state.json").read_text())["events"][0]
    before = semantic_hash(state)
    assert semantic_hash(commit_event(state, event, root)) == before


def test_right_arithmetic_wrong_numeric_proof_cannot_pass(tmp_path):
    state, root, *_ = case(tmp_path)
    # Production cannot trust a mutable caller-state substitution.
    atom = next(row for row in state["observations"].values() if row["field"] == "quantity")
    atom["quote"] = "billed_amount: 223.00"
    with pytest.raises(BillingFailure) as failure:
        calculate(state, root)
    assert failure.value.code == "STATE_CHANGED"


def test_wrong_reader_value_with_valid_span_and_positive_model_review_still_fails(tmp_path):
    state, root, *_ = case(tmp_path, reader_changes={"quantity": {"value": "1502"}})
    decision = readiness(state, root)
    assert not decision["ready"]
    assert decision["root_issues"][0]["code"] == "EVIDENCE_BINDING_INVALID"


def test_new_invoice_fact_only_stales_invoice_and_link_reviews(tmp_path):
    from againward.documents.contracts import SourceBatch
    state, root, iid, tid, rid = case(tmp_path)
    source_id = state["occurrences"][iid]["source_id"]
    row = {"field": "note", "value": "new interpretation", "group": "additional", "location": "line:1",
           "quote": "invoice_id: INV-Generic"}
    boundary = ModelBoundary(lambda *_: json.dumps({"observations": [row], "limitations": []}).encode())
    digest = read_source(SourceBatch.from_dict(state["batch"]), source_id, root, model="SCRIPTED", boundary=boundary, role="RECOVERY")
    state = commit_event(state, {"type": "READ", "receipt_sha256": digest}, root)
    assert current_review(state, tid, root)["verdict"] == "SUPPORTED"
    for target in (iid, rid):
        with pytest.raises(BillingFailure) as failure:
            current_review(state, target, root)
        assert failure.value.code == "REVIEW_STALE"


def test_note_label_does_not_authorize_dismissing_quarantine(tmp_path):
    atom = {"field": "note", "group": "bad", "value": "unbound credit", "location": "line:999", "quote": "Credit 60 EUR"}
    state, root, iid, *_ = case(tmp_path, bad_atom=atom)
    state = receipt(state, iid, root, nonmaterial_quarantine_ids=[])
    assert readiness(state, root)["root_issues"][0]["code"] == "MATERIAL_EVIDENCE_MISSING"


def test_ambiguous_review_cannot_be_substituted_for_supported(tmp_path):
    state, root, _, _, rid = case(tmp_path)
    state = receipt(state, rid, root, verdict="AMBIGUOUS", authority_kind="UNRESOLVED")
    assert readiness(state, root)["root_issues"][0]["code"] == "BUSINESS_AMBIGUITY"


@pytest.mark.parametrize("notes, count", [((0, 14), 33), ((23, 22), 64)])
def test_authority_review_can_cite_entire_union_of_two_bounded_subjects(tmp_path, notes, count):
    state, root, _, _, rid = case(tmp_path, notes=notes)
    assert len(state["reviews"][rid]["response"]["evidence_ids"]) == count
    assert readiness(state, root)["ready"]
    assert calculate(state, root)["expected_cents"] == 18462


@pytest.mark.parametrize("gap", ["unread_locations", "parser_limitations"])
def test_uninspectable_source_scope_cannot_be_approved_by_model(tmp_path, monkeypatch, gap):
    from againward.domains.energy_billing import review
    state, root, iid, *_ = case(tmp_path)
    contexts = review.current_sources(state, iid, root)
    contexts[0][gap] = ["uninspected component"]
    monkeypatch.setattr(review, "current_sources", lambda *_: contexts)
    boundary = ModelBoundary(lambda *_: b'{}')
    with pytest.raises(BillingFailure) as failure:
        request_review(state, iid, root, model="SCRIPTED", boundary=boundary)
    assert failure.value.code == "MATERIAL_EVIDENCE_MISSING"
    assert boundary.calls == 0
    with pytest.raises(BillingFailure):
        current_review(state, iid, root)


def test_altered_calculation_cannot_be_silently_repaired_during_report(tmp_path):
    state, root, *_ = case(tmp_path)
    result = calculate(state, root)
    path = root / "energy_billing" / "calculations" / (result["calculation_sha256"] + ".json")
    value = json.loads(path.read_text())
    value["expected_cents"] += 1
    path.write_text(json.dumps(value))
    before = path.read_bytes()
    with pytest.raises(BillingFailure) as failure:
        render_report(root, result["calculation_sha256"])
    assert failure.value.code == "REPORT_PROVENANCE_FAILURE" and path.read_bytes() == before


def test_authority_reviews_relation_and_acceptance_clause_without_repeating_fact_review(tmp_path):
    state, root, _, _, rid = case(tmp_path, notes=(0, 14))
    # All arithmetic inputs remain independently positively reviewed. The
    # authority reviewer cites its own focused relation, plus exact acceptance.
    state = receipt(state, rid, root, evidence_ids=state["relations"][rid]["evidence_ids"])
    assert readiness(state, root)["ready"]
    result = calculate(state, root)
    assert result["authority"]["contract_acceptance_evidence"]["quote"] == "Authority: Accepted commercial terms for this contract."


@pytest.mark.parametrize("changes", [{"authority_source_id": "wrong-source"}, {"authority_location": "line:999"},
                                    {"authority_quote": "fabricated accepted contract"}])
def test_wrong_acceptance_proof_cannot_authorize_correct_amount(tmp_path, changes):
    state, root, _, _, rid = case(tmp_path)
    before = (root / "energy_billing" / "state.json").read_bytes()
    with pytest.raises(BillingFailure) as failure:
        receipt(state, rid, root, **changes)
    assert failure.value.code == "MODEL_PROTOCOL_FAILURE"
    assert (root / "energy_billing" / "state.json").read_bytes() == before


@pytest.mark.parametrize("field", ["credit_amount", "invoice_total"])
def test_positive_model_coverage_cannot_hide_known_other_financial_amount(tmp_path, field):
    state, root, *_ = case(tmp_path, invoice_changes={field: "40.00"})
    decision = readiness(state, root)
    assert not decision["ready"] and decision["root_issues"][0]["code"] == "MATERIAL_EVIDENCE_MISSING"
    assert decision["root_issues"][0]["unresolved_evidence_ids"]


def test_bad_domain_targets_are_repaired_before_reducer_mutation(tmp_path):
    from againward.domains.energy_billing.investigator import propose_action
    state, root, iid, tid, rid = case(tmp_path)
    replies = iter([
        {"issue_id": "issue", "action": {"type": "LINK_TARIFF", "invoice_id": tid, "tariff_id": iid,
         "evidence_ids": state["relations"][rid]["evidence_ids"]}},
        {"issue_id": "issue", "action": {"type": "LINK_TARIFF", "invoice_id": iid, "tariff_id": tid,
         "evidence_ids": state["relations"][rid]["evidence_ids"]}},
    ])
    boundary = ModelBoundary(lambda *_: json.dumps(next(replies)).encode())
    before = (root / "energy_billing" / "state.json").read_bytes()
    response = propose_action(state, {"issue_id": "issue", "targets": [iid, tid]}, boundary)
    assert response["action"]["invoice_id"] == iid and boundary.calls == 2
    assert (root / "energy_billing" / "state.json").read_bytes() == before
