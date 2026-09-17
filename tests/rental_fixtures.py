"""Synthetic generic rental evidence, deliberately independent of Construction."""
from copy import deepcopy


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
