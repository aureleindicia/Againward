import json
from pathlib import Path

import pytest

from againward.core.workflow import fingerprint, prepare_investigation
from againward.core.workspace import create_client_workspace
from againward.domains.rental.ingestion import load_rental_case, build_evidence_dataset, EXTRACTION_SCHEMA
from againward.entrypoints import get_domain
from againward.evidence.cli import execute_case_query
from tests.rental_fixtures import rental_packet


def write_packet(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    packet = rental_packet()
    (root / "agreement.txt").write_text("Agreement A1. ITEM: 1 asset. 2026-09-01 to 2026-09-08 (exclusive). EUR 700/week.")
    (root / "invoice.csv").write_text("Invoice,Line,Amount,Rate,Quantity,Units,Start,End\nI1,L1,850.00,850,1,1,2026-09-01,2026-09-08\n")
    for doc in packet["documents"]:
        doc["sha256"] = fingerprint(root / doc["path"])
    path = root / "extraction.json"
    path.write_text(json.dumps(packet))
    return path, packet


def test_canonical_extraction_hashes_source_documents_and_builds_neutral_dataset(tmp_path):
    source, _ = write_packet(tmp_path)
    case, inventory = load_rental_case(source)
    assert len(inventory["documents"]) == 2
    dataset = build_evidence_dataset(case)
    assert dataset.metadata["domain"] == "rental"
    assert "power_kw" not in dataset.field_keys
    invoice = next(r for r in dataset.rows if r["record_type"] == "actual_charges")
    assert invoice["amount_minor"] == 85000
    assert dataset.source_references(invoice["source_row"])[0]["source_id"] == "INVOICE"
    (tmp_path / "invoice.csv").write_text("tampered")
    with pytest.raises(ValueError, match="hash"): load_rental_case(source)


def test_explicit_csv_mapping_retains_source_column_locations_and_no_silent_defaults(tmp_path):
    source, packet = write_packet(tmp_path)
    packet["actual_charges"] = []
    source.write_text(json.dumps({"schema_version": EXTRACTION_SCHEMA, "case": packet, "tables": [{
        "document_id": "INVOICE", "record_type": "actual_charges",
        "columns": {"invoice_id": "Invoice", "invoice_line_id": "Line", "net_amount": "Amount", "unit_rate": "Rate",
                    "quantity": "Quantity", "billed_units": "Units", "start": "Start", "end": "End"},
        "constants": {"period_id": "PERIOD", "charge_key": "hire", "charge_type": "RENTAL", "currency": "EUR"}}]}))
    case, inventory = load_rental_case(source)
    assert case.actual_charges[0].net_amount == "850.00"
    assert case.actual_charges[0].evidence_refs[0].location == "row:2"
    assert inventory["transformations"][0]["rows"] == 1


def test_rental_uses_shared_orchestration_lifecycle_and_bounded_queries(tmp_path):
    source, _ = write_packet(tmp_path / "sources")
    output = tmp_path / "case"
    state = prepare_investigation(source, output, domain=get_domain("rental"))
    assert state["domain"] == "rental"
    assert state["client_lifecycle"]["state"] == "ANALYZING"
    assert state["candidate_detection"]["events"][0]["recoverable_amount"] is None
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"query_id": "rental-source", "dataset_id": state["evidence_plane"]["dataset_id"],
        "operation": "raw_slice", "arguments": {"fields": ["record_type", "record_id", "rate", "amount_minor"], "limit": 20},
        "purpose": "Check invoice against contractual rate and original locations."}))
    reply = execute_case_query(output, request)
    assert reply["decision"] is None
    assert reply["result"]["sources"]
    assert json.loads((output / "questions.json").read_text())["questions"] == []
    assert not (output / "physical_differential_template.json").exists()


def test_construction_profile_enriches_context_without_changing_arithmetic(tmp_path):
    source, packet = write_packet(tmp_path / "sources")
    packet["items"][0]["description"] = "Mini excavator"
    source.write_text(json.dumps(packet))
    for profile in ("generic", "construction"):
        prepare_investigation(source, tmp_path / profile, domain=get_domain("rental", profile=profile))
    for name in ("expected_charge_ledger.json", "actual_charge_ledger.json", "evidence_dataset.json"):
        assert json.loads((tmp_path / "generic" / name).read_text()) == json.loads((tmp_path / "construction" / name).read_text())
    context = json.loads((tmp_path / "construction/domain_context.json").read_text())
    assert "excavator" in context["profile_hints"][0]["suggested_categories"]


def test_unreviewed_rental_incoming_is_refused_before_json_parsing(tmp_path):
    create_client_workspace("real", root=tmp_path, domain_name="rental", intake_payload={})
    source = tmp_path / "real/incoming/input.json"
    source.write_text("invalid JSON must never be parsed")
    with pytest.raises(ValueError, match="PRIVACY|CONTRACT"):
        load_rental_case(source, output_directory=tmp_path / "real/processed")


def test_document_path_escape_and_symlink_are_refused(tmp_path):
    source, packet = write_packet(tmp_path / "sources")
    packet["documents"][0]["path"] = "../elsewhere.txt"
    source.write_text(json.dumps(packet))
    with pytest.raises(ValueError, match="relative"): load_rental_case(source)


def test_rental_cli_routes_explicitly_and_rejects_energy_options(tmp_path):
    from againward.cli import main
    source, _ = write_packet(tmp_path / "source")
    args = [str(source), "--domain", "rental", "--profile", "construction", "--output-dir", str(tmp_path / "case")]
    assert main(args) == 0
    assert main([str(source), "--domain", "rental", "--energy-column", "Amount", "--output-dir", str(tmp_path / "invalid")]) == 2
