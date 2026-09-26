"""The model adapter may propose, but exact source and privacy remain authorities."""
import json
from pathlib import Path
import subprocess

import pytest

from againward.documents.codex_provider import (CodexCliProvider, VISUAL_RENDER_DPI,
    VISUAL_RENDER_VERSION, _model_invocation_failure, assemble_proposal, prompt_version_for_guidance)
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.documents.analyst_review import build_analyst_review, review_visual_with_codex
from againward.domains.rental.models import DOCUMENT_ROLES
from againward.domains.rental.semantic_guidance import guidance, visual_guidance
from benchmarking.document_renderers import pdf


def _source(tmp_path: Path, content="Invoice INV-9: net EUR 850.00."):
    incoming = tmp_path / "public"
    incoming.mkdir()
    (incoming / "invoice.txt").write_text(content)
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    return root, batch, document, parsed


def _raw(location: str, quote: str):
    return {"status": "SUCCESS", "limitations": [], "candidates": [{
        "entity_id": "invoice-line-1", "semantic_type": "net_amount",
        "value_type": "DECIMAL", "value": "850.00", "raw_observed_value": quote,
        "location": location, "normalization_notes": "Exact decimal on invoice line",
        "ambiguity_flags": [],
    }]}


def test_provider_assembles_exact_quote_and_validation_keeps_model_non_authoritative(tmp_path):
    root, batch, document, parsed = _source(tmp_path)
    proposal = assemble_proposal(_raw(parsed.units[0].location, "850.00"),
                                 document, parsed, batch.batch_id, "gpt-5.3-codex")
    result = validate_proposal(proposal, batch, root)
    assert result.candidates[0].source_span == (23, 29)
    assert result.candidates[0].semantic_type == "net_amount"
    assert result.model == "gpt-5.3-codex"
    assert result.candidates[0].confidence is None


@pytest.mark.parametrize("content,quote", [
    ("Invoice INV-9: net EUR 850.00.", "900.00"),
    ("Invoice 850.00, credit 850.00.", "850.00"),
])
def test_model_cannot_invent_or_ambiguously_locate_quote(tmp_path, content, quote):
    _, batch, document, parsed = _source(tmp_path, content)
    with pytest.raises(DocumentError, match="SOURCE_LOCATION_INVALID"):
        assemble_proposal(_raw(parsed.units[0].location, quote), document, parsed,
                          batch.batch_id, "gpt-5.3-codex")


def test_unexplained_model_normalization_is_not_silently_approved(tmp_path):
    root, batch, document, parsed = _source(tmp_path)
    raw = _raw(parsed.units[0].location, "net EUR 850.00")
    raw["candidates"][0]["normalization_notes"] = ""
    proposal = assemble_proposal(raw, document, parsed, batch.batch_id, "gpt-6-sol")
    result = validate_proposal(proposal, batch, root)
    assert result.status == "NEEDS_REVIEW"
    assert "UNEXPLAINED_NORMALIZATION" in result.candidates[0].ambiguity_flags


def test_cli_participant_receives_only_approved_units_and_never_promotes(tmp_path, monkeypatch):
    root, batch, document, parsed = _source(tmp_path)
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["prompt"] = kwargs["input"]
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(_raw(parsed.units[0].location, "850.00")))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run", fake_run)
    proposal = CodexCliProvider(root, model="gpt-5.3-codex").propose(
        document, parsed, {"batch": batch, "semantic_guidance": "Synthetic Rental extraction only."})
    assert "--sandbox" in captured["command"] and "read-only" in captured["command"]
    assert "--ephemeral" in captured["command"]
    assert document.source_id in captured["prompt"]
    assert "850.00" in captured["prompt"]
    assert "privacy_manifest" not in captured["prompt"]
    assert "approved_facts" not in proposal
    assert proposal["prompt_version"] == prompt_version_for_guidance("Synthetic Rental extraction only.")
    assert validate_proposal(proposal, batch, root).candidates[0].value == "850.00"


def test_model_budget_refuses_oversized_units_before_subprocess(tmp_path, monkeypatch):
    root, batch, document, parsed = _source(tmp_path, "x" * 30_001)
    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run",
                        lambda *args, **kwargs: pytest.fail("No model call allowed"))
    with pytest.raises(DocumentError, match="RESOURCE_LIMIT"):
        CodexCliProvider(root, model="gpt-5.3-codex").propose(
            document, parsed, {"batch": batch, "semantic_guidance": "Rental"})


def test_invalid_model_identifier_fails_with_candidate_index(tmp_path):
    _, batch, document, parsed = _source(tmp_path)
    raw = _raw(parsed.units[0].location, "850.00")
    raw["candidates"][0]["entity_id"] = "line with spaces"
    with pytest.raises(DocumentError, match="Candidate 1 entity_id"):
        assemble_proposal(raw, document, parsed, batch.batch_id, "gpt-6-sol")


def test_rental_guidance_names_every_canonical_document_role():
    instructions = guidance()
    assert all(role in instructions for role in DOCUMENT_ROLES)
    assert 'invoice_line_id "1"' in instructions


def test_visual_invoice_reader_keeps_structural_metadata_on_the_billed_line(tmp_path, monkeypatch):
    incoming = tmp_path / "visual-public"
    incoming.mkdir()
    pdf(incoming / "invoice.pdf", [
        "ACCEPTED INVOICE INV-7, Line 1, asset LIFT-5, net EUR 150.00."], scan=True)
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    observed = [
        ("entity_kind", "ENUM", "INVOICE_LINE", "ACCEPTED INVOICE"),
        ("document_role", "ENUM", "INVOICE", "ACCEPTED INVOICE"),
        ("document_status", "ENUM", "ACCEPTED", "ACCEPTED INVOICE"),
        ("invoice_id", "IDENTIFIER", "INV-7", "INV-7"),
        ("invoice_line_id", "IDENTIFIER", "1", "Line 1"),
        ("asset_id", "IDENTIFIER", "LIFT-5", "LIFT-5"),
        ("net_amount", "DECIMAL", "150.00", "EUR 150.00"),
    ]
    raw = {"status": "NEEDS_REVIEW", "limitations": [],
           "observations": [{"semantic_type": semantic, "value_type": kind, "value": value,
                             "visible_text": quote, "page": 1, "ambiguity": [],
                             "entity_hint": "invoice line 1"}
                            for semantic, kind, value, quote in observed]}
    captured = {}
    original_run = subprocess.run

    def fake_run(command, **kwargs):
        if "input" not in kwargs:
            return original_run(command, **kwargs)
        captured["prompt"] = kwargs["input"]
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(raw))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run", fake_run)
    proposal = CodexCliProvider(root, model="synthetic-model").propose(
        document, parsed, {"batch": batch, "semantic_guidance": visual_guidance()})
    extraction = validate_proposal(proposal, batch, root)
    line = [candidate for candidate in extraction.candidates if candidate.semantic_type != "page"]
    assert {candidate.semantic_type for candidate in line} >= {
        "entity_kind", "document_role", "document_status", "invoice_id", "invoice_line_id", "net_amount"}
    assert len({candidate.entity_id for candidate in line}) == 1
    assert "each material visual entity" in captured["prompt"]
    assert "Never split structural metadata across different entity_hint values" in captured["prompt"]
    assert "Limitations must be atomic, source-local claims" in captured["prompt"]
    assert "Do not say an amount/total is not visible" in captured["prompt"]

    incomplete = dict(raw, observations=[row for row in raw["observations"]
                                         if row["semantic_type"] != "entity_kind"])
    incomplete_extraction = validate_proposal(assemble_proposal(
        incomplete, document, parsed, batch.batch_id, "synthetic-model",
        prompt_version=proposal["prompt_version"], visual_bindings=proposal["visual_bindings"],
        invocation_id=proposal["invocation_id"]), batch, root)
    base = build_analyst_review(batch, (incomplete_extraction,), {}, root)
    accepted = {"decisions": [{"candidate_id": candidate.candidate_id, "decision": "ACCEPT",
        "reason": "The pixel fact is individually legible.", "resolved_flags": []}
        for candidate in incomplete_extraction.candidates]}
    monkeypatch.setattr("againward.documents.analyst_review._ask_codex",
                        lambda *args, **kwargs: (accepted, 0.1))
    blocked = review_visual_with_codex(batch, (incomplete_extraction,), base, root,
                                       model="synthetic-model")
    assert blocked["status"] == "REPAIR_REQUIRED"
    assert blocked["native_facts_accepted"] == 0
    assert blocked["visual_structural_gaps"][0]["missing"] == ["entity_kind"]


@pytest.mark.parametrize("family", ["correspondence", "accounting_export", "rate_sheet"])
def test_native_document_families_keep_structural_trio_on_each_entity(tmp_path, monkeypatch, family):
    from openpyxl import Workbook

    incoming = tmp_path / family
    incoming.mkdir()
    if family == "correspondence":
        (incoming / "source.eml").write_text(
            "Subject: Off-hire request AG-9\nMIME-Version: 1.0\n"
            "Content-Type: text/plain; charset=utf-8\n\nWe request off-hire for one LIFT-5 unit.\n")
        kind, role, status = "SUPPORTING_DOCUMENT", "EMAIL_EVIDENCE", "EXTRACTED"
        fact_type, fact_value, fact_quote = "item_id", "LIFT-5", "LIFT-5"
        structural_quote = "Off-hire request AG-9"
    elif family == "accounting_export":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Export"
        sheet.append(["Type", "Invoice", "Reference", "Net EUR"])
        sheet.append(["INVOICE", "INV-9", "Mirror only", "900.00"])
        sheet.append(["CREDIT", "CN-9", "INV-9/L1", "100.00"])
        workbook.save(incoming / "source.xlsx")
        kind, role, status = "SUPPORTING_DOCUMENT", "PAYMENT_EXPORT", "EXTRACTED"
        fact_type, fact_value, fact_quote = "invoice_id", "INV-9", "INV-9"
        structural_quote = "Mirror only"
    else:
        pdf(incoming / "source.pdf", ["ACCEPTED RATE SHEET.", "LIFT-5 net EUR 50.00 per day."])
        kind, role, status = "SUPPORTING_DOCUMENT", "RATE_CARD", "ACCEPTED"
        fact_type, fact_value, fact_quote = "rate", "50.00", "50.00"
        structural_quote = "ACCEPTED RATE SHEET"

    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    assert all(unit.route == "NATIVE" for unit in parsed.units)

    def location_for(quote):
        matches = [unit for unit in parsed.units if unit.text == quote]
        if not matches:
            matches = [unit for unit in parsed.units if quote in unit.text]
        assert len(matches) == 1
        return matches[0].location

    entity_id = "source-entity-1"
    values = [("entity_kind", "ENUM", kind, structural_quote),
              ("document_role", "ENUM", role, structural_quote),
              ("document_status", "ENUM", status, structural_quote),
              (fact_type, "DECIMAL" if fact_type == "rate" else "IDENTIFIER",
               fact_value, fact_quote)]
    raw = {"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": entity_id, "semantic_type": semantic, "value_type": value_type,
         "value": value, "raw_observed_value": quote, "location": location_for(quote),
         "normalization_notes": "Source-supported structural classification or exact value.",
         "ambiguity_flags": []}
        for semantic, value_type, value, quote in values]}
    if family == "accounting_export":
        for semantic, value_type, value, quote in (
                ("entity_kind", "ENUM", "SUPPORTING_DOCUMENT", "CREDIT"),
                ("document_role", "ENUM", "PAYMENT_EXPORT", "Type"),
                ("document_status", "ENUM", "EXTRACTED", "Type"),
                ("credit_id", "IDENTIFIER", "CN-9", "CN-9"),
                ("net_amount", "DECIMAL", "100.00", "100.00")):
            raw["candidates"].append({"entity_id": "export-credit-1", "semantic_type": semantic,
                "value_type": value_type, "value": value, "raw_observed_value": quote,
                "location": location_for(quote),
                "normalization_notes": "Source-local exported credit row; review remains required.",
                "ambiguity_flags": []})
    captured = {}

    original_run = subprocess.run

    def fake_run(command, **kwargs):
        if "input" not in kwargs:
            return original_run(command, **kwargs)
        captured["prompt"] = kwargs["input"]
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(raw))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run", fake_run)
    provider = CodexCliProvider(root, model="synthetic-model")
    payload = provider.propose(document, parsed, {"batch": batch, "semantic_guidance": guidance()})
    extraction = validate_proposal(payload, batch, root)
    assert {candidate.semantic_type for candidate in extraction.candidates} >= {
        "entity_kind", "document_role", "document_status", fact_type}
    expected_entities = {entity_id, "export-credit-1"} if family == "accounting_export" else {entity_id}
    assert {candidate.entity_id for candidate in extraction.candidates} == expected_entities
    assert "For every material Rental entity_id, emit entity_kind, document_role and document_status" in captured["prompt"]
    assert "same entity_id" in captured["prompt"]
    if family == "accounting_export":
        assert "PAYMENT_EXPORT and EXTRACTED describe the source document" in captured["prompt"]
        assert "a CREDIT row type does not by itself change the document role or status" in captured["prompt"]

    accepted = {"decisions": [{"candidate_id": candidate.candidate_id, "decision": "ACCEPT",
        "reason": "Exact source observation with complete source-supported structural metadata.",
        "resolved_flags": []} for candidate in extraction.candidates]}
    ready = build_analyst_review(batch, (extraction,), {document.source_id: accepted}, root)
    assert ready["status"] == "READY_FOR_PACKAGE"
    assert ready["native_facts_accepted"] == len(extraction.candidates)

    incomplete_raw = json.loads(json.dumps(raw))
    incomplete_raw["candidates"] = [row for row in incomplete_raw["candidates"]
                                    if row["semantic_type"] != "entity_kind"]
    incomplete = validate_proposal(assemble_proposal(incomplete_raw, document, parsed, batch.batch_id,
        "synthetic-model", prompt_version=payload["prompt_version"]), batch, root)
    incomplete_decisions = {"decisions": [{"candidate_id": candidate.candidate_id,
        "decision": "ACCEPT", "reason": "Exact source observation.", "resolved_flags": []}
        for candidate in incomplete.candidates]}
    blocked = build_analyst_review(batch, (incomplete,),
                                  {document.source_id: incomplete_decisions}, root)
    assert blocked["status"] == "REPAIR_REQUIRED"
    assert blocked["native_facts_accepted"] == 0
    assert blocked["structural_gaps"] == [{"source_id": document.source_id,
        "entity_id": expected_entity, "missing": ["entity_kind"]}
        for expected_entity in sorted(expected_entities)]


def test_invoice_line_label_requires_explicit_safe_identifier(tmp_path):
    root, batch, document, parsed = _source(tmp_path, "Line 1 - net EUR 850.00.")
    raw = _raw(parsed.units[0].location, "850.00")
    line = dict(raw["candidates"][0], semantic_type="invoice_line_id",
                value_type="IDENTIFIER", value="Line 1", raw_observed_value="Line 1",
                normalization_notes="")
    raw["candidates"] = [line]
    with pytest.raises(DocumentError, match="EXTRACTION_SCHEMA_INVALID"):
        validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
                                           "gpt-6-sol"), batch, root)
    line["value"] = "1"
    line["normalization_notes"] = "Printed line label normalized to its exact number."
    result = validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
                                                 "gpt-6-sol"), batch, root)
    assert result.candidates[0].value == "1"
    assert result.candidates[0].raw_observed_value == "Line 1"


@pytest.mark.parametrize("stderr,code", [
    ("Authentication required: PRIVATE_SOURCE_MARKER", "MODEL_AUTH_REQUIRED"),
    ("429 Too Many Requests: PRIVATE_SOURCE_MARKER", "MODEL_RATE_LIMITED"),
    ("stream disconnected before completion: PRIVATE_SOURCE_MARKER", "MODEL_TRANSPORT_FAILURE"),
    ("unrecognized failure: PRIVATE_SOURCE_MARKER", "MODEL_INVOCATION_FAILURE"),
    ("Invalid configuration: PRIVATE_SOURCE_MARKER", "MODEL_CONFIGURATION_ERROR"),
    ("model overloaded: PRIVATE_SOURCE_MARKER", "MODEL_UNAVAILABLE"),
])
def test_cli_failure_is_categorized_without_leaking_stderr(tmp_path, monkeypatch, stderr, code):
    root, batch, document, parsed = _source(tmp_path)

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", stderr)

    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run", fake_run)
    with pytest.raises(DocumentError) as caught:
        CodexCliProvider(root, model="gpt-6-sol").propose(
            document, parsed, {"batch": batch, "semantic_guidance": "Rental"})
    assert caught.value.code == code
    assert "PRIVATE_SOURCE_MARKER" not in str(caught.value)


def test_cli_missing_binary_and_empty_success_fail_closed(tmp_path, monkeypatch):
    root, batch, document, parsed = _source(tmp_path)

    def absent(*args, **kwargs):
        raise FileNotFoundError("PRIVATE_SOURCE_MARKER")

    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run", absent)
    with pytest.raises(DocumentError, match="MODEL_CLI_UNAVAILABLE") as caught:
        CodexCliProvider(root, model="gpt-6-sol").propose(
            document, parsed, {"batch": batch, "semantic_guidance": "Rental"})
    assert "PRIVATE_SOURCE_MARKER" not in str(caught.value)

    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run",
                        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", ""))
    with pytest.raises(DocumentError, match="MODEL_EMPTY_RESPONSE"):
        CodexCliProvider(root, model="gpt-6-sol").propose(
            document, parsed, {"batch": batch, "semantic_guidance": "Rental"})


def test_invocation_failure_classifier_uses_stdout_and_exit_code_without_echoing_output():
    failure = _model_invocation_failure("", stdout='{"type":"error","message":"unknown model gpt-private"}',
                                       returncode=2)
    assert failure.code == "MODEL_CONFIGURATION_ERROR"
    assert "gpt-private" not in str(failure)
    assert _model_invocation_failure("", stdout="process exited", returncode=7).code == "MODEL_INVOCATION_FAILURE"


def test_provider_drops_nonexact_native_quote_without_converting_it_to_evidence(tmp_path, monkeypatch):
    root, batch, document, parsed = _source(tmp_path,
        "Email says: Please return the lift. This is not proof of physical return.")
    exact = _raw(parsed.units[0].location, "Please return the lift.")["candidates"][0]
    paraphrase = dict(exact, entity_id="email-proof", semantic_type="verification",
                      value="NOT_PROOF", raw_observed_value="The email itself is not proof of an earlier physical return.")
    raw = {"status": "SUCCESS", "limitations": [], "candidates": [exact, paraphrase]}

    def fake_run(command, **kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(raw))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run", fake_run)
    proposal = CodexCliProvider(root, model="gpt-6-luna").propose(
        document, parsed, {"batch": batch, "semantic_guidance": "Rental"})
    accepted = validate_proposal(proposal, batch, root)
    assert accepted.status == "PARTIAL"
    assert len(accepted.candidates) == 1
    assert accepted.candidates[0].raw_observed_value == "Please return the lift."
    assert accepted.candidates[0].source_span == (12, 35)
    diagnostic_path = next((root.parent / "scratch/visual_model_diagnostics").glob("*.json"))
    diagnostic = json.loads(diagnostic_path.read_text())
    assert diagnostic["stage"] == "NATIVE_CITATION_FILTER"
    assert diagnostic["rejection_code"] == "SOURCE_LOCATION_INVALID"
    assert diagnostic["rejected_count"] == 1
    assert diagnostic["semantic_values_present_before_rejection"] is True
    assert "raw_response" not in diagnostic
    assert "The email itself" not in diagnostic_path.read_text()


def test_provider_fails_closed_when_all_native_quotes_are_nonexact(tmp_path, monkeypatch):
    root, batch, document, parsed = _source(tmp_path)
    raw = _raw(parsed.units[0].location, "A plausible paraphrase of the invoice.")

    def fake_run(command, **kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(raw))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run", fake_run)
    with pytest.raises(DocumentError, match="SOURCE_LOCATION_INVALID"):
        CodexCliProvider(root, model="gpt-6-luna").propose(
            document, parsed, {"batch": batch, "semantic_guidance": "Rental"})


def test_accounting_export_keeps_amounts_numeric_and_currency_separate(tmp_path):
    from openpyxl import Workbook

    incoming = tmp_path / "accounting-export"
    incoming.mkdir()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ledger"
    values = {"A1": "INV-900", "B1": "1", "C1": "LIFT-5", "D1": "900.00",
              "E1": "EUR", "F1": "90.00", "G1": "100.00", "H1": "125.00"}
    for cell, value in values.items():
        sheet[cell] = value
    workbook.save(incoming / "accounting_export.xlsx")
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    units_by_value = {unit.text: unit for unit in parsed.units}
    fields = [
        ("net_amount", "DECIMAL", "900.00"), ("currency", "CURRENCY", "EUR"),
        ("unit_rate", "DECIMAL", "90.00"), ("allocated_amount", "DECIMAL", "100.00"),
        ("rate", "DECIMAL", "125.00"),
    ]
    raw = {"status": "SUCCESS", "limitations": [], "candidates": []}
    for index, (semantic, kind, value) in enumerate(fields, 1):
        unit = units_by_value[value]
        raw["candidates"].append({"entity_id": "ledger-line-1", "semantic_type": semantic,
            "value_type": kind, "value": value, "raw_observed_value": value,
            "location": unit.location, "normalization_notes": "", "ambiguity_flags": []})
    extraction = validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
                                                      "scripted-model"), batch, root)
    assert {candidate.semantic_type: candidate.value_type for candidate in extraction.candidates} == {
        "net_amount": "DECIMAL", "currency": "CURRENCY", "unit_rate": "DECIMAL",
        "allocated_amount": "DECIMAL", "rate": "DECIMAL"}
    for semantic, _, _ in fields:
        if semantic == "currency":
            continue
        wrong = json.loads(json.dumps(raw))
        next(row for row in wrong["candidates"] if row["semantic_type"] == semantic)["value_type"] = "CURRENCY"
        with pytest.raises(DocumentError, match="EXTRACTION_SCHEMA_INVALID"):
            assemble_proposal(wrong, document, parsed, batch.batch_id, "scripted-model")
    wrong_currency = json.loads(json.dumps(raw))
    currency_row = next(row for row in wrong_currency["candidates"] if row["semantic_type"] == "currency")
    currency_row.update(value="900.00", raw_observed_value="900.00",
                        location=units_by_value["900.00"].location)
    with pytest.raises(DocumentError, match="CURRENCY_MISMATCH"):
        validate_proposal(assemble_proposal(wrong_currency, document, parsed, batch.batch_id,
                                            "scripted-model"), batch, root)


def _visual_source(tmp_path):
    public = tmp_path / "visual-public"
    public.mkdir()
    pdf(public / "scan.pdf", ["Invoice INV-7 amount EUR 150.00"], scan=True)
    root = tmp_path / "visual-documents"
    batch = inventory_sources(public, root)
    document = batch.documents[0]
    return root, batch, document, read_document(document, root)


def test_visual_observation_has_no_model_locator_and_python_binds_current_300dpi_page(tmp_path, monkeypatch):
    root, batch, document, parsed = _visual_source(tmp_path)
    captured = {}
    raw = {"status": "SUCCESS", "limitations": [], "observations": [{
        "semantic_type": "net_amount", "value_type": "DECIMAL", "value": "150.00",
        "visible_text": "EUR 150.00", "page": 1, "ambiguity": [], "entity_hint": "invoice total"}]}
    real_run = subprocess.run

    def fake_run(command, **kwargs):
        if Path(command[0]).name == "pdftoppm" or "againward.documents.pdf_worker" in command:
            return real_run(command, **kwargs)
        captured["command"] = command
        captured["prompt"] = kwargs["input"]
        captured["image"] = Path(command[command.index("--image") + 1]).read_bytes()
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(raw), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run", fake_run)
    provider = CodexCliProvider(root, model="gpt-6-luna", evaluation_only=True)
    proposal = provider.propose(document, parsed, {"batch": batch, "semantic_guidance": "Rental billing"})
    extraction = validate_proposal(proposal, batch, root)
    candidate = extraction.candidates[0]
    binding = extraction.visual_bindings[0]
    assert "source_sha256" not in captured["prompt"]
    assert "unit_sha256" not in captured["prompt"]
    assert "candidate_id" not in captured["prompt"]
    assert captured["command"].count("--image") == 1
    assert binding["source_id"] == document.source_id
    assert binding["source_sha256"] == document.sha256
    assert binding["location"] == "page:1"
    assert binding["render_dpi"] == VISUAL_RENDER_DPI == 300
    assert binding["render_version"] == VISUAL_RENDER_VERSION
    assert binding["render_sha256"] == __import__("hashlib").sha256(captured["image"]).hexdigest()
    assert candidate.source_span is None
    assert candidate.value == "150.00"
    assert "VISUAL_TRANSCRIPTION_UNVERIFIED" in candidate.ambiguity_flags
    assert "COMPONENT_REVIEW_REQUIRED" in candidate.ambiguity_flags
    raw["observations"].append({"semantic_type": "currency", "value_type": "CURRENCY",
        "value": "EUR", "visible_text": "EUR", "page": 1, "ambiguity": [], "entity_hint": "invoice total"})
    separated = validate_proposal(provider.propose(document, parsed,
        {"batch": batch, "semantic_guidance": "Rental billing"}), batch, root)
    assert {item.semantic_type: (item.value_type, item.value) for item in separated.candidates} == {
        "net_amount": ("DECIMAL", "150.00"), "currency": ("CURRENCY", "EUR")}
    diagnostics = list((root.parent / "scratch/visual_model_diagnostics").glob("*.json"))
    assert len(diagnostics) == 2
    assert all("raw_response" in json.loads(item.read_text()) for item in diagnostics)
    raw["observations"][0].update(value_type="CURRENCY", value="150.00 EUR")
    with pytest.raises(DocumentError, match="EXTRACTION_SCHEMA_INVALID"):
        provider.propose(document, parsed, {"batch": batch, "semantic_guidance": "Rental billing"})


def test_visual_reader_rejects_impossible_page_and_stale_source_bytes(tmp_path, monkeypatch):
    root, batch, document, parsed = _visual_source(tmp_path)
    raw = {"status": "SUCCESS", "limitations": [], "observations": [{
        "semantic_type": "invoice_id", "value_type": "IDENTIFIER", "value": "INV-7",
        "visible_text": "INV-7", "page": 2, "ambiguity": [], "entity_hint": "invoice"}]}
    real_run = subprocess.run

    def fake_run(command, **kwargs):
        if Path(command[0]).name == "pdftoppm" or "againward.documents.pdf_worker" in command:
            return real_run(command, **kwargs)
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(raw))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run", fake_run)
    provider = CodexCliProvider(root, model="gpt-6-luna")
    with pytest.raises(DocumentError, match="SOURCE_LOCATION_INVALID"):
        provider.propose(document, parsed, {"batch": batch, "semantic_guidance": "Rental"})
    diagnostic = json.loads(next((root.parent / "scratch/visual_model_diagnostics").glob("*.json")).read_text())
    assert diagnostic["stage"] == "VISUAL_ASSEMBLY"
    assert diagnostic["emitted_locations"] == [2]
    assert diagnostic["valid_locations"] == ["page:1"]
    assert diagnostic["rejection_code"] == "SOURCE_LOCATION_INVALID"
    assert diagnostic["semantic_values_present"] is True
    assert "raw_response" not in diagnostic

    raw["observations"][0]["page"] = 1
    proposal = provider.propose(document, parsed, {"batch": batch, "semantic_guidance": "Rental"})
    stale_render = json.loads(json.dumps(proposal))
    stale_render["visual_bindings"][0]["render_sha256"] = "0" * 64
    with pytest.raises(DocumentError, match="SOURCE_LOCATION_INVALID"):
        validate_proposal(stale_render, batch, root)
    (root / document.blob_path).write_bytes(b"mutated original")
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        validate_proposal(proposal, batch, root)
