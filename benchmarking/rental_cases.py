"""Synthetic generic rental evidence, deliberately independent of Construction."""
from copy import deepcopy
import csv
import json
from pathlib import Path

from againward.core.workflow import fingerprint


def rental_packet():
    ref = [{"document_id": "AGREEMENT", "location": "page:1"}]
    invoice_ref = [{"document_id": "INVOICE", "location": "line:1"}]
    return deepcopy({
        "schema_version": "againward-rental-case-v1",
        "documents": [
            {"document_id": "AGREEMENT", "role": "RENTAL_AGREEMENT", "path": "agreement.txt", "sha256": "a" * 64, "status": "ACCEPTED"},
            {"document_id": "INVOICE", "role": "INVOICE", "path": "invoice.csv", "sha256": "b" * 64, "status": "ACCEPTED"}],
        "parties": [{"party_id": "CLIENT", "role": "CLIENT", "evidence_refs": ref},
                    {"party_id": "VENDOR", "role": "RENTAL_VENDOR", "evidence_refs": ref}],
        "items": [{"item_id": "ITEM", "description": "Portable operational asset", "evidence_refs": ref}],
        "periods": [{"period_id": "PERIOD", "agreement_id": "A1", "item_id": "ITEM", "supplier_id": "VENDOR",
                     "client_id": "CLIENT", "start": "2026-09-01", "end": "2026-09-08", "quantity": "1", "evidence_refs": ref}],
        "terms": [{"term_id": "RATE", "period_id": "PERIOD", "charge_key": "hire", "charge_type": "RENTAL", "currency": "EUR",
                   "billing_unit": "WEEK", "rate": "700", "quantity": "1", "weekends_billable": True,
                   "minimum_days": 0, "partial_period_policy": "PRORATA", "stop_event": "RETURNED",
                   "stop_day_billable": False, "discount_fraction": "0", "evidence_refs": ref}],
        "events": [],
        "actual_charges": [{"invoice_id": "I1", "invoice_line_id": "L1", "period_id": "PERIOD", "charge_key": "hire",
                            "charge_type": "RENTAL", "currency": "EUR", "net_amount": "850.00", "unit_rate": "850",
                            "quantity": "1", "billed_units": "1", "start": "2026-09-01", "end": "2026-09-08", "evidence_refs": invoice_ref}],
        "credits": [],
    })


def return_evidence(packet, *, documented=True):
    packet["documents"].append({"document_id": "RETURN", "role": "RETURN_NOTE" if documented else "TEXT_NOTE",
        "path": "return.txt", "sha256": "c" * 64, "status": "ACCEPTED"})
    packet["events"].append({"event_id": "RETURN1", "period_id": "PERIOD", "event_type": "RETURNED",
        "date": "2026-09-05", "quantity": "1", "verification": "DOCUMENTED" if documented else "DECLARED",
        "evidence_refs": [{"document_id": "RETURN", "location": "event:RETURN1"}]})


def cases():
    """Generator/scorer truth stays outside every participant case directory."""
    base = rental_packet()
    base["actual_charges"][0].update(net_amount="700.00", unit_rate="700")
    packets, truth = {}, {}

    def add(name, packet, amount, families=(), *, positive=False, credit_accounting=None):
        packets[name] = packet
        truth[name] = {"supported_discrepancy": amount, "required_families": list(families),
                       "positive_supported_case": positive}
        if credit_accounting is not None:
            truth[name]["credit_accounting"] = credit_accounting

    add("R01_correct", deepcopy(base), "0.00")
    add("R02_wrong_rate", rental_packet(), "150.00", ["WRONG_RATE"], positive=True)
    packet = deepcopy(base); return_evidence(packet)
    add("R03_post_return", packet, "300.00", ["POST_RETURN_BILLING"], positive=True)
    packet = deepcopy(base)
    packet["actual_charges"].append({**packet["actual_charges"][0], "invoice_line_id": "L2"})
    add("R04_duplicate", packet, "700.00", ["DUPLICATE_BILLING"], positive=True)
    packet = deepcopy(base)
    packet["actual_charges"].append({**packet["actual_charges"][0], "invoice_line_id": "L2", "charge_key": "cleaning",
        "charge_type": "CLEANING", "net_amount": "80.00", "unit_rate": "80"})
    add("R05_unsupported_fee", packet, "0.00", ["UNAUTHORIZED_FEE", "UNKNOWN_CONTRACTUAL_BASIS"])
    packet = deepcopy(base); return_evidence(packet, documented=False)
    add("R06_ambiguous_return", packet, "0.00", ["UNKNOWN_CONTRACTUAL_BASIS"])
    packet = deepcopy(base)
    packet["items"].append({**packet["items"][0], "item_id": "ITEM2", "asset_id": "ASSET2"})
    packet["periods"].append({**packet["periods"][0], "period_id": "PERIOD2", "item_id": "ITEM2", "site_id": "SITE2"})
    packet["terms"].append({**packet["terms"][0], "term_id": "RATE2", "period_id": "PERIOD2"})
    packet["actual_charges"].append({**packet["actual_charges"][0], "invoice_line_id": "L2", "period_id": "PERIOD2"})
    add("A01_same_description_distinct_assets_sites", packet, "0.00")
    packet = deepcopy(base); return_evidence(packet)
    packet["events"].append({"event_id": "EXT1", "period_id": "PERIOD", "event_type": "EXTENDED",
        "date": "2026-09-06", "extended_end": "2026-09-15", "verification": "DOCUMENTED",
        "evidence_refs": packet["terms"][0]["evidence_refs"]})
    add("A02_later_extension", packet, "0.00", ["UNKNOWN_CONTRACTUAL_BASIS"])
    packet = deepcopy(base)
    packet["terms"].append({**packet["terms"][0], "term_id": "WEEKEND", "charge_key": "weekend",
        "charge_type": "SURCHARGE", "billing_unit": "FIXED", "rate": "80"})
    packet["actual_charges"].append({**packet["actual_charges"][0], "invoice_line_id": "L2", "charge_key": "weekend",
        "charge_type": "SURCHARGE", "net_amount": "80.00", "unit_rate": "80"})
    add("A03_authorized_weekend_surcharge", packet, "0.00")
    packet = rental_packet()
    packet["documents"].append({"document_id": "CREDIT", "role": "CREDIT_NOTE", "status": "ACCEPTED", "path": "credit.txt", "sha256": "c" * 64})
    packet["credits"].append({"credit_id": "C1", "charge_id": "I1/L1", "currency": "EUR", "net_amount": "150.00",
        "status": "ISSUED", "evidence_refs": [{"document_id": "CREDIT", "location": "credit:C1"}]})
    add("A04_correct_credit", packet, "0.00", credit_accounting={
        "issued_credit": "150.00", "unallocated_credit": "0.00", "group_difference": "0.00"})
    packet = rental_packet()
    packet["documents"].append({"document_id": "AMEND", "role": "AMENDMENT", "status": "ACCEPTED", "path": "amend.txt", "sha256": "d" * 64})
    packet["terms"].append({**packet["terms"][0], "term_id": "RATE2", "rate": "850", "supersedes_term_id": "RATE",
        "evidence_refs": [{"document_id": "AMEND", "location": "term:RATE2"}]})
    add("A05_accepted_changed_rate", packet, "0.00")
    packet = rental_packet(); packet["terms"] = []
    add("A06_missing_contract", packet, "0.00", ["UNKNOWN_CONTRACTUAL_BASIS"])
    packet = deepcopy(base)
    packet["periods"][0]["quantity"] = "2"; packet["terms"][0]["quantity"] = "2"
    packet["actual_charges"].append({**packet["actual_charges"][0], "invoice_line_id": "L2"})
    add("A07_authorized_split_quantity", packet, "0.00")
    packet = rental_packet()
    packet["documents"].append({"document_id": "CREDIT", "role": "CREDIT_NOTE", "status": "ACCEPTED",
                                "path": "credit.txt", "sha256": "c" * 64})
    packet["credits"].append({"credit_id": "C1", "charge_id": None, "invoice_id": "I1",
                              "allocation_state": "UNALLOCATED_CREDIT", "currency": "EUR", "net_amount": "150.00",
                              "status": "ISSUED", "evidence_refs": [{"document_id": "CREDIT", "location": "credit:C1"}]})
    add("A08_unallocated_issued_credit", packet, "0.00", ["UNALLOCATED_CREDIT"], credit_accounting={
        "issued_credit": "0.00", "unallocated_credit": "150.00", "group_difference": None})
    packet = deepcopy(packet)
    packet["credits"][0].update(charge_id="I1/L1", allocation_state="PARTIALLY_ALLOCATED_CREDIT",
                                 allocated_amount="80.00")
    add("A09_partially_allocated_credit", packet, "0.00", ["UNALLOCATED_CREDIT"], credit_accounting={
        "issued_credit": "80.00", "unallocated_credit": "70.00", "group_difference": None})
    return packets, truth


def write_sources(root, packet):
    """Readable synthetic source exports plus explicit semantic extraction, no truth."""
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    packet = deepcopy(packet)
    for doc in packet["documents"]:
        records = []
        for kind in ("parties", "items", "periods", "terms", "events", "actual_charges", "credits"):
            records += [{"record_type": kind, **record} for record in packet[kind]
                        if any(ref["document_id"] == doc["document_id"] for ref in record["evidence_refs"])]
        path = root / doc["path"]
        if path.suffix == ".csv":
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle); writer.writerow(["invoice_id", "invoice_line_id", "period_id", "net_amount", "currency"])
                for record in records:
                    writer.writerow([record.get(key, "") for key in ("invoice_id", "invoice_line_id", "period_id", "net_amount", "currency")])
        else:
            path.write_text("SYNTHETIC EVIDENCE — " + doc["role"] + "\n" + json.dumps(records, indent=2), encoding="utf-8")
        doc["sha256"] = fingerprint(path)
    source = root / "extraction.json"
    source.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return source
