"""Material QA selection reopens exact source evidence and grants no approval."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace

import pytest

from againward.documents.adjudication import (_SCHEMA, adjudicate_with_codex,
    validate_adjudication, verify_adjudication_pixels)
from againward.documents.codex_provider import assemble_proposal, bind_visual_pages, prompt_version_for_guidance
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal
from againward.documents.independent_qa import compare_extractions
from againward.domains.rental.extraction_validation import package_source_gaps, validate_rental_extraction
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.documents.visual_fact_review import _render_hash
from benchmarking.document_renderers import pdf


def _case(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    (public / "agreement.txt").write_text(
        "ACCEPTED agreement: an off-hire request alone does not stop billing.")
    (public / "email.txt").write_text(
        "We request off-hire. This email is not proof of physical return.")
    root = tmp_path / "documents"
    batch = inventory_sources(public, root)
    by_name = {document.original_names[0]: document for document in batch.documents}

    def extract(name, kind):
        document = by_name[name]
        parsed = read_document(document, root)
        quote = "ACCEPTED" if name == "agreement.txt" else "We request off-hire."
        fields = [("entity_kind", kind, quote),
                  ("document_role", "RENTAL_AGREEMENT" if name == "agreement.txt" else "EMAIL_EVIDENCE",
                   "ACCEPTED agreement" if name == "agreement.txt" else "This email"),
                  ("document_status", "ACCEPTED" if name == "agreement.txt" else "EXTRACTED", quote)]
        raw = {"status": "SUCCESS", "limitations": [], "candidates": [{
            "entity_id": "scope" if name == "agreement.txt" else "email",
            "semantic_type": field, "value_type": "ENUM", "value": value,
            "raw_observed_value": observed, "location": parsed.units[0].location,
            "normalization_notes": "Classified source role", "ambiguity_flags": [],
        } for field, value, observed in fields]}
        return validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
                                                    "synthetic-model"), batch, root)

    agreement = extract("agreement.txt", "RENTAL_SCOPE")
    primary_email = extract("email.txt", "SUPPORTING_DOCUMENT")
    challenger_email = extract("email.txt", "RETURN")
    primary = (agreement, primary_email)
    challenger = (agreement, challenger_email)
    qa = compare_extractions(batch, primary, challenger, root)
    email = by_name["email.txt"]
    contract = by_name["agreement.txt"]
    raw = {"decisions": [{"source_id": email.source_id, "selection": "PRIMARY",
                          "rationale": "The accepted rule and email both distinguish request from return.",
                          "observations": [],
                          "citations": [
                              {"source_id": email.source_id, "location": "line:1",
                               "quote": "This email is not proof of physical return.", "preview_sha256": ""},
                              {"source_id": contract.source_id, "location": "line:1",
                               "quote": "an off-hire request alone does not stop billing.", "preview_sha256": ""},
                          ]}]}
    return root, batch, primary, challenger, qa, raw, email


def test_adjudication_selects_source_bound_proposal_without_approving_facts(tmp_path):
    root, batch, primary, challenger, qa, raw, email = _case(tmp_path)
    result = validate_adjudication(batch, primary, challenger, qa, raw, root)
    assert result["status"] == "RESOLVED_FOR_FACT_REVIEW"
    assert result["facts_approved"] == 0 and result["delivery_approved"] is False
    assert result["selected_extractions"][email.source_id] == primary[1].to_dict()["extraction_sha256"]
    assert len(result["decisions"][0]["citations"]) == 2
    assert all(row["source_span"][1] > row["source_span"][0]
               for row in result["decisions"][0]["citations"])


def test_adjudication_rejects_unsupported_or_stale_evidence(tmp_path):
    root, batch, primary, challenger, qa, raw, email = _case(tmp_path)
    invalid = deepcopy(raw)
    invalid["decisions"][0]["citations"][0]["quote"] = "not in the original"
    with pytest.raises(DocumentError, match="SOURCE_LOCATION_INVALID"):
        validate_adjudication(batch, primary, challenger, qa, invalid, root)
    without_disputed_source = deepcopy(raw)
    without_disputed_source["decisions"][0]["citations"] = [raw["decisions"][0]["citations"][1]]
    with pytest.raises(DocumentError, match="EXTRACTION_INCOMPLETE"):
        validate_adjudication(batch, primary, challenger, qa, without_disputed_source, root)
    stale = deepcopy(qa)
    stale["source_results"][0]["primary_status"] = "FAILED"
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        validate_adjudication(batch, primary, challenger, stale, raw, root)
    (root / email.blob_path).write_text("changed")
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        validate_adjudication(batch, primary, challenger, qa, raw, root)


def test_unresolved_adjudication_cannot_select_material_source(tmp_path):
    root, batch, primary, challenger, qa, raw, email = _case(tmp_path)
    raw["decisions"][0].update(selection="UNRESOLVED", rationale="Source is contradictory.", citations=[])
    result = validate_adjudication(batch, primary, challenger, qa, raw, root)
    assert result["status"] == "RECONCILIATION_REQUIRED"
    assert email.source_id in result["material_unresolved_source_ids"]
    assert email.source_id not in result["selected_extractions"]


def test_matching_missing_commercial_field_cannot_be_selected_as_complete(tmp_path):
    incoming = tmp_path / "public"
    incoming.mkdir()
    (incoming / "invoice.txt").write_text("Issued Invoice INV-8 rental line net 850.00 EUR.")
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    rows = [("entity_kind", "ENUM", "INVOICE_LINE", "rental line"),
            ("document_role", "ENUM", "INVOICE", "Invoice"),
            ("document_status", "ENUM", "ISSUED", "Issued"),
            ("invoice_id", "IDENTIFIER", "INV-8", "INV-8"),
            ("net_amount", "DECIMAL", "850.00", "850.00"),
            ("currency", "CURRENCY", "EUR", "EUR")]
    raw = {"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": "line", "semantic_type": field, "value_type": value_type,
         "value": value, "raw_observed_value": quote, "location": parsed.units[0].location,
         "normalization_notes": "Exact source observation", "ambiguity_flags": []}
        for field, value_type, value, quote in rows]}
    extraction = validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
        "synthetic-model"), batch, root)
    qa = compare_extractions(batch, (extraction,), (extraction,), root)
    assert qa["source_results"][0]["primary_source_fact_gaps"]["line"] == ["charge_type"]
    decision = {"decisions": [{"source_id": document.source_id, "selection": "PRIMARY",
        "rationale": "The amount is visible, but the type was omitted.", "observations": [],
        "citations": [{"source_id": document.source_id, "location": parsed.units[0].location,
                       "quote": "rental line", "preview_sha256": ""}]}]}
    with pytest.raises(DocumentError) as caught:
        validate_adjudication(batch, (extraction,), (extraction,), qa, decision, root,
                              required_source_facts=package_source_gaps)
    assert caught.value.diagnostic["validation_code"] == "SELECTED_SOURCE_FACT_GAP"
    assert caught.value.diagnostic["missing_semantic_fields"] == ["charge_type"]
    decision["decisions"][0].update(selection="UNRESOLVED", citations=[])
    unresolved = validate_adjudication(batch, (extraction,), (extraction,), qa, decision, root)
    assert unresolved["status"] == "RECONCILIATION_REQUIRED"


def test_adjudicator_reopens_original_sources_without_private_truth(tmp_path, monkeypatch):
    root, batch, primary, challenger, qa, raw, _email = _case(tmp_path)
    calls = []
    prompts = []

    def fake_codex(command, *, input, **_kwargs):
        prompts.append(input)
        prompt = json.loads(input.split("\n", 1)[1])
        calls.append(prompt)
        assert len(prompt["original_sources"]) == 2
        assert "off-hire request alone" in json.dumps(prompt["original_sources"])
        assert "not proof of physical return" in json.dumps(prompt["original_sources"])
        assert "private_truth" not in input
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(raw))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("againward.documents.adjudication.subprocess.run", fake_codex)
    result = adjudicate_with_codex(batch, primary, challenger, qa, root, model="synthetic-model")
    assert result["status"] == "RESOLVED_FOR_FACT_REVIEW"
    assert len(calls) == 1
    stale = deepcopy(qa)
    stale["source_results"][0]["primary_status"] = "FAILED"
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        adjudicate_with_codex(batch, primary, challenger, stale, root, model="synthetic-model")
    assert len(calls) == 1


def test_adjudicator_retries_one_invalid_closed_schema_response(tmp_path, monkeypatch):
    root, batch, primary, challenger, qa, raw, _email = _case(tmp_path)
    invalid = deepcopy(raw)
    invalid["decisions"][0]["selection"] = "CHOOSE_WHATEVER"
    responses = [invalid, raw]
    prompts = []
    original_run = subprocess.run

    def fake_codex(command, **kwargs):
        if "input" not in kwargs:
            return original_run(command, **kwargs)
        prompts.append(kwargs["input"])
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(responses.pop(0)))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("againward.documents.adjudication.subprocess.run", fake_codex)
    result = adjudicate_with_codex(batch, primary, challenger, qa, root, model="synthetic-model")
    assert result["status"] == "RESOLVED_FOR_FACT_REVIEW"
    assert len(prompts) == 2
    assert "did not satisfy the closed adjudication schema" in prompts[1]
    assert "Do not omit required members" in prompts[1]
    assert "selection chooses a source-local observation set" in prompts[0]
    assert "does NOT establish contractual authority" in prompts[0]
    assert "different phrasing or grouping alone is not a material" in prompts[0]
    assert "Treat limitations as independent source-local claims" in prompts[0]
    assert "choose UNRESOLVED" in prompts[0]


def test_adjudication_runtime_failure_is_classified_and_sanitized(tmp_path, monkeypatch):
    root, batch, primary, challenger, qa, _raw, _email = _case(tmp_path)

    def failed_call(command, **_kwargs):
        return SimpleNamespace(returncode=2, stdout='{"type":"error","code":"invalid_json_schema"}',
                               stderr="PRIVATE_SOURCE_MARKER")

    monkeypatch.setattr("againward.documents.adjudication.subprocess.run", failed_call)
    with pytest.raises(DocumentError) as caught:
        adjudicate_with_codex(batch, primary, challenger, qa, root, model="synthetic-model",
                              evaluation_only=False)
    assert caught.value.code == "MODEL_CONFIGURATION_ERROR"
    assert "PRIVATE_SOURCE_MARKER" not in str(caught.value)
    diagnostic_path = next((root.parent / "scratch/visual_model_diagnostics").glob("*.json"))
    diagnostic = json.loads(diagnostic_path.read_text())
    assert diagnostic["stage"] == "SOURCE_ADJUDICATION_MODEL_INVOCATION"
    assert diagnostic["failure_category"] == "MODEL_CONFIGURATION_ERROR"
    assert diagnostic["returncode"] == 2
    assert diagnostic["stdout_bytes"] > 0 and diagnostic["stderr_bytes"] > 0
    assert diagnostic["retention_scope"] == "SANITIZED_FAILURE_METADATA"
    assert "PRIVATE_SOURCE_MARKER" not in diagnostic_path.read_text()


def test_adjudication_response_schema_requires_every_declared_decision_field():
    decision = _SCHEMA["properties"]["decisions"]["items"]
    assert set(decision["required"]) == set(decision["properties"])
    assert "observations" in decision["required"]


def test_adjudication_schema_failure_has_safe_exact_path_diagnostic(tmp_path, monkeypatch):
    root, batch, primary, challenger, qa, raw, _email = _case(tmp_path)
    raw["decisions"][0]["observations"] = "PRIVATE_RESPONSE_MARKER"

    def fake_codex(command, **_kwargs):
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(raw))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("againward.documents.adjudication.subprocess.run", fake_codex)
    monkeypatch.setattr("againward.documents.codex_provider._codex_cli_version",
                        lambda: "codex-test-version")
    with pytest.raises(DocumentError) as caught:
        adjudicate_with_codex(batch, primary, challenger, qa, root, model="synthetic-model",
                              evaluation_only=False)
    assert caught.value.code == "EXTRACTION_SCHEMA_INVALID"
    assert caught.value.diagnostic["schema_path"] == "$.decisions[0].observations"
    assert caught.value.diagnostic["validation_code"] == "TYPE_MISMATCH"
    assert caught.value.diagnostic["expected_type"] == "array"
    assert caught.value.diagnostic["received_shape"].startswith("string(length=")
    diagnostics = list((root.parent / "scratch/visual_model_diagnostics").glob("*.json"))
    assert len(diagnostics) == 2  # bounded schema retry, then fail closed
    for diagnostic in diagnostics:
        serialized = diagnostic.read_text()
        assert "PRIVATE_RESPONSE_MARKER" not in serialized
        assert "raw_response" not in serialized
        payload = json.loads(serialized)
        assert payload["stage"] == "SOURCE_ADJUDICATION_VALIDATION"
        assert payload["retention_scope"] == "SANITIZED_FAILURE_METADATA"
        assert payload["response_sha256"]


def test_evaluation_only_adjudication_diagnostic_may_keep_raw_in_private_scratch(tmp_path, monkeypatch):
    root, batch, primary, challenger, qa, raw, _email = _case(tmp_path)
    raw["decisions"][0]["observations"] = "PRIVATE_EVAL_DETAIL"

    def fake_codex(command, **_kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(raw))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("againward.documents.adjudication.subprocess.run", fake_codex)
    monkeypatch.setattr("againward.documents.codex_provider._codex_cli_version",
                        lambda: "codex-test-version")
    with pytest.raises(DocumentError):
        adjudicate_with_codex(batch, primary, challenger, qa, root, model="synthetic-model",
                              evaluation_only=True)
    diagnostic_path = next((root.parent / "scratch/visual_model_diagnostics").glob("*.json"))
    payload = json.loads(diagnostic_path.read_text())
    assert payload["retention_scope"] == "DEV_EVALUATION_ONLY_PRIVATE_SCRATCH"
    assert "PRIVATE_EVAL_DETAIL" in json.dumps(payload["raw_response"])
    assert diagnostic_path.stat().st_mode & 0o077 == 0


def test_adjudication_incomplete_resolution_names_missing_source_evidence(tmp_path):
    root, batch, primary, challenger, qa, raw, email = _case(tmp_path)
    raw["decisions"][0]["citations"] = []
    with pytest.raises(DocumentError) as caught:
        validate_adjudication(batch, primary, challenger, qa, raw, root)
    assert caught.value.code == "EXTRACTION_INCOMPLETE"
    assert caught.value.diagnostic["schema_path"] == "$.decisions[0].citations"
    assert caught.value.diagnostic["source_id"] == email.source_id
    assert caught.value.diagnostic["validation_code"] == "RESOLUTION_WITHOUT_CITATION"


def test_visual_dispute_requires_current_disputed_pixels_not_other_document(tmp_path, monkeypatch):
    public = tmp_path / "public"
    public.mkdir()
    pdf(public / "return.pdf", ["Signed return: LIFT-5 serial 204 returned September 5."], scan=True)
    (public / "agreement.txt").write_text("Contract says an email request alone is not a return.")
    root = tmp_path / "documents"
    batch = inventory_sources(public, root)
    visual = next(doc for doc in batch.documents if "return.pdf" in doc.original_names)
    native = next(doc for doc in batch.documents if "agreement.txt" in doc.original_names)

    def proposal(document, kind):
        parsed = read_document(document, root)
        observed = "Signed return: LIFT-5 serial 204 returned September 5." if document == visual else "Contract says"
        raw = {"status": "SUCCESS", "limitations": [], "candidates": [{
            "entity_id": "return", "semantic_type": "entity_kind", "value_type": "ENUM",
            "value": kind, "raw_observed_value": observed, "location": parsed.units[0].location,
            "normalization_notes": "Source classification", "ambiguity_flags": [],
        }]}
        prompt_version = prompt_version_for_guidance("")
        kwargs = {}
        if any(unit.route != "NATIVE" for unit in parsed.units):
            kwargs = {"prompt_version": prompt_version,
                      "visual_bindings": bind_visual_pages(document, parsed, root,
                          model="scripted-model", prompt_version=prompt_version,
                          invocation_id="fixture-visual"),
                      "invocation_id": "fixture-visual"}
        return validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
                                                   "scripted-model", **kwargs), batch, root)

    native_pass = proposal(native, "RENTAL_SCOPE")
    primary_visual = proposal(visual, "RETURN")
    challenger_visual = proposal(visual, "SUPPORTING_DOCUMENT")
    primary = (native_pass, primary_visual)
    challenger = (native_pass, challenger_visual)
    qa = compare_extractions(batch, primary, challenger, root)
    with tempfile.TemporaryDirectory() as directory:
        preview, _, _ = _render_hash(visual, root, "page:1", Path(directory))
    raw = {"decisions": [{"source_id": visual.source_id, "selection": "PRIMARY",
                          "rationale": "Pixel reading supports a signed return; model judgment, not deterministic proof.",
                          "observations": [],
                          "citations": [{"source_id": visual.source_id, "location": "page:1",
                                         "quote": "Signed return: LIFT-5 serial 204 returned September 5.",
                                         "preview_sha256": preview}]}]}
    resolved = validate_adjudication(batch, primary, challenger, qa, raw, root)
    assert resolved["status"] == "RESOLVED_FOR_FACT_REVIEW"
    assert resolved["decisions"][0]["citations"][0]["deterministic_semantic_verification"] is False
    verify_adjudication_pixels(batch, resolved, root)
    original_render = _render_hash
    monkeypatch.setattr("againward.documents.visual_fact_review._render_hash",
                        lambda *args: ("0" * 64, None, "0" * 64))
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        verify_adjudication_pixels(batch, resolved, root)
    monkeypatch.setattr("againward.documents.visual_fact_review._render_hash", original_render)
    stale = deepcopy(raw)
    stale["decisions"][0]["citations"][0]["preview_sha256"] = "0" * 64
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        validate_adjudication(batch, primary, challenger, qa, stale, root)
    wrong_source = deepcopy(raw)
    wrong_source["decisions"][0]["citations"][0]["source_id"] = native.source_id
    with pytest.raises(DocumentError):
        validate_adjudication(batch, primary, challenger, qa, wrong_source, root)
    unresolved = deepcopy(raw)
    unresolved["decisions"][0].update(selection="UNRESOLVED", citations=[])
    assert validate_adjudication(batch, primary, challenger, qa, unresolved, root)["status"] == "RECONCILIATION_REQUIRED"
    (root / visual.blob_path).write_bytes(b"mutated source")
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        validate_adjudication(batch, primary, challenger, qa, raw, root)


def test_visual_absence_limitation_cannot_be_selected_against_pixel_supported_fact(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    pdf(public / "invoice.pdf", ["ACCEPTED INVOICE INV-7.", "Net total EUR 150.00."], scan=True)
    root = tmp_path / "documents"
    batch = inventory_sources(public, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    prompt_version = prompt_version_for_guidance("limitation conflict regression")
    binding = bind_visual_pages(document, parsed, root, model="synthetic-model",
        prompt_version=prompt_version, invocation_id="limitation-conflict")
    observations = [
        ("entity_kind", "ENUM", "INVOICE_LINE", "ACCEPTED INVOICE"),
        ("document_role", "ENUM", "INVOICE", "ACCEPTED INVOICE"),
        ("document_status", "ENUM", "ISSUED", "ACCEPTED INVOICE"),
        ("invoice_id", "IDENTIFIER", "INV-7", "INV-7"),
        ("net_amount", "DECIMAL", "150.00", "Net total EUR 150.00"),
    ]

    def extract(limitations):
        raw = {"status": "NEEDS_REVIEW", "limitations": limitations,
               "observations": [{"semantic_type": semantic, "value_type": kind, "value": value,
                   "visible_text": quote, "page": 1, "ambiguity": [], "entity_hint": "invoice line 1"}
                   for semantic, kind, value, quote in observations]}
        payload = assemble_proposal(raw, document, parsed, batch.batch_id, "synthetic-model",
            prompt_version=prompt_version, visual_bindings=binding, invocation_id="limitation-conflict")
        return validate_proposal(payload, batch, root)

    primary = (extract(["No invoice total is visible."]),)
    challenger = (extract([]),)
    qa = compare_extractions(batch, primary, challenger, root)
    assert qa["source_results"][0]["material_needs_reconciliation"] is True
    with tempfile.TemporaryDirectory() as directory:
        preview, _, _ = _render_hash(document, root, "page:1", Path(directory))
    decision = {"source_id": document.source_id, "selection": "CHALLENGER",
        "rationale": "Pixels show the net total; the challenger has no contradictory absence limitation.",
        "observations": [],
        "citations": [{"source_id": document.source_id, "location": "page:1",
                       "quote": "Net total EUR 150.00", "preview_sha256": preview}]}
    resolved = validate_adjudication(batch, primary, challenger, qa,
                                     {"decisions": [decision]}, root)
    assert resolved["selected_extractions"][document.source_id] == challenger[0].to_dict()["extraction_sha256"]
    assert resolved["facts_approved"] == 0 and resolved["delivery_approved"] is False

    contradictory_selection = deepcopy(decision)
    contradictory_selection["selection"] = "PRIMARY"
    with pytest.raises(DocumentError, match="EXTRACTION_CONTRADICTION"):
        validate_adjudication(batch, primary, challenger, qa,
                              {"decisions": [contradictory_selection]}, root)


def test_explicit_duplicate_rate_sheet_primary_is_selected_as_unapproved_supporting_evidence(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    (public / "agreement.txt").write_text("ACCEPTED agreement AG-7 governs rental terms.")
    (public / "rate_sheet.txt").write_text(
        "ACCEPTED NEGOTIATED RATE SHEET for agreement AG-7.\n"
        "This duplicates daily prices in the signed agreement; no amendment.\n"
        "LIFT-5 / SN-L5-204: net EUR 50.00 per asset per calendar day.\n"
        "LIFT-50 / SN-L50-830: net EUR 30.00 per asset per calendar day.\n"
        "The agreement governs start, stop, weekend and minimum conventions.")
    root = tmp_path / "documents"
    batch = inventory_sources(public, root)
    docs = {doc.original_names[0]: doc for doc in batch.documents}
    rate_doc = docs["rate_sheet.txt"]
    parsed = read_document(rate_doc, root)
    rows = []
    for entity_id, row_index, asset, serial, rate in (
            ("support-lift5", 2, "LIFT-5", "SN-L5-204", "50.00"),
            ("support-lift50", 3, "LIFT-50", "SN-L50-830", "30.00")):
        for semantic, kind, value, quote, line in (
                ("entity_kind", "ENUM", "SUPPORTING_DOCUMENT", "ACCEPTED NEGOTIATED RATE SHEET", 0),
                ("document_role", "ENUM", "RATE_CARD", "RATE SHEET", 0),
                ("document_status", "ENUM", "ACCEPTED", "ACCEPTED", 0),
                ("agreement_id", "IDENTIFIER", "AG-7", "agreement AG-7", 0),
                ("asset_id", "IDENTIFIER", asset, asset, row_index),
                ("serial_number", "IDENTIFIER", serial, serial, row_index),
                ("currency", "CURRENCY", "EUR", "EUR", row_index),
                ("rate", "DECIMAL", rate, rate, row_index),
                ("billing_unit", "ENUM", "DAY", "per calendar day", row_index)):
            rows.append({"entity_id": entity_id, "semantic_type": semantic, "value_type": kind,
                "value": value, "raw_observed_value": quote,
                "location": parsed.units[line].location,
                "normalization_notes": "Exact source-local transcription", "ambiguity_flags": []})
    primary_rate = validate_proposal(assemble_proposal({"status": "NEEDS_REVIEW", "limitations": [],
        "candidates": rows}, rate_doc, parsed, batch.batch_id, "synthetic-model"), batch, root)
    challenger_rate = validate_proposal(assemble_proposal({"status": "SUCCESS", "limitations": [],
        "candidates": []}, rate_doc, parsed, batch.batch_id, "synthetic-model"), batch, root)
    contract_doc = docs["agreement.txt"]
    contract_units = read_document(contract_doc, root)
    contract = validate_proposal(assemble_proposal({"status": "SUCCESS", "limitations": [],
        "candidates": []}, contract_doc, contract_units, batch.batch_id, "synthetic-model"), batch, root)
    primary, challenger = (contract, primary_rate), (contract, challenger_rate)
    qa = compare_extractions(batch, primary, challenger, root)
    row = next(item for item in qa["source_results"] if item["source_id"] == rate_doc.source_id)
    assert row["material_needs_reconciliation"]
    raw = {"decisions": [{"source_id": rate_doc.source_id, "selection": "PRIMARY",
        "rationale": "The sheet explicitly says its two rates duplicate the signed agreement and makes no amendment; these are source observations, not independent tariff authority.",
        "observations": [],
        "citations": [
            {"source_id": rate_doc.source_id, "location": "line:2",
             "quote": "This duplicates daily prices in the signed agreement; no amendment.", "preview_sha256": ""},
            {"source_id": rate_doc.source_id, "location": "line:3",
             "quote": "LIFT-5 / SN-L5-204: net EUR 50.00 per asset per calendar day.", "preview_sha256": ""},
            {"source_id": rate_doc.source_id, "location": "line:4",
             "quote": "LIFT-50 / SN-L50-830: net EUR 30.00 per asset per calendar day.", "preview_sha256": ""}]}]}
    adjudication = validate_adjudication(batch, primary, challenger, qa, raw, root)
    assert adjudication["status"] == "RESOLVED_FOR_FACT_REVIEW"
    assert adjudication["facts_approved"] == 0 and adjudication["delivery_approved"] is False
    rates = {candidate.entity_id: candidate.value for candidate in primary_rate.candidates
             if candidate.semantic_type == "rate"}
    assert rates == {"support-lift5": "50.00", "support-lift50": "30.00"}


def test_clear_signed_return_scan_resolves_grouping_only_difference_through_pixels(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    pdf(public / "signed_return.pdf", [
        "SIGNED RETURN / OFF-HIRE RECORD, agreement AG-7.",
        "One of two LIFT-5 units, serial SN-L5-204, returned 2026-09-05.",
        "One LIFT-5 unit remains on hire through contract end 2026-09-10.",
        "The LIFT-50 asset is not returned by this record."], scan=True)
    root = tmp_path / "documents"
    batch = inventory_sources(public, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    version = prompt_version_for_guidance("visual return regression")
    binding = bind_visual_pages(document, parsed, root, model="synthetic-model",
        prompt_version=version, invocation_id="return-regression")

    def proposal(hints):
        fields = [
            ("entity_kind", "ENUM", "RETURN", "SIGNED RETURN / OFF-HIRE RECORD", 0),
            ("document_role", "ENUM", "RETURN_NOTE", "SIGNED RETURN / OFF-HIRE RECORD", 0),
            ("document_status", "ENUM", "ACCEPTED", "SIGNED RETURN / OFF-HIRE RECORD", 0),
            ("agreement_id", "IDENTIFIER", "AG-7", "agreement AG-7", 0),
            ("item_id", "IDENTIFIER", "LIFT-5", "LIFT-5 units", 1),
            ("serial_number", "IDENTIFIER", "SN-L5-204", "SN-L5-204", 1),
            ("quantity", "INTEGER", 1, "One of two LIFT-5 units", 1),
            ("event_type", "TEXT", "returned", "returned 2026-09-05", 1),
            ("date", "DATE", "2026-09-05", "2026-09-05", 1),
            ("verification", "ENUM", "DOCUMENTED", "SIGNED RETURN", 0),
            ("item_id", "IDENTIFIER", "LIFT-50", "LIFT-50 asset", 3),
            ("event_type", "TEXT", "not returned", "not returned by this record", 3),
        ]
        observations = [{"semantic_type": semantic, "value_type": kind, "value": value,
            "visible_text": quote, "page": 1, "ambiguity": [], "entity_hint": hints[group]}
            for semantic, kind, value, quote, group in fields]
        return validate_proposal(assemble_proposal({"status": "NEEDS_REVIEW",
            "observations": observations, "limitations": []}, document, parsed, batch.batch_id,
            "synthetic-model", prompt_version=version, visual_bindings=binding,
            invocation_id="return-regression"), batch, root)

    primary_return = proposal({0: "return-header", 1: "returned-unit", 3: "not-returned-asset"})
    challenger_return = proposal({0: "return-record", 1: "return-record", 3: "return-record"})
    primary, challenger = (primary_return,), (challenger_return,)
    qa = compare_extractions(batch, primary, challenger, root)
    assert qa["source_results"][0]["material_needs_reconciliation"]
    with tempfile.TemporaryDirectory() as directory:
        preview, _, _ = _render_hash(document, root, "page:1", Path(directory))
    result = validate_adjudication(batch, primary, challenger, qa, {"decisions": [{
        "source_id": document.source_id, "selection": "PRIMARY",
        "rationale": "The current original scan clearly supports the return date and separate remaining asset; grouping differences do not change those printed facts.",
        "observations": [],
        "citations": [{"source_id": document.source_id, "location": "page:1",
                       "quote": "returned 2026-09-05", "preview_sha256": preview}]}]}, root)
    assert result["status"] == "RESOLVED_FOR_FACT_REVIEW"
    assert result["facts_approved"] == 0 and result["delivery_approved"] is False
    assert result["decisions"][0]["citations"][0]["verification_method"] == "MULTIMODAL_ORIGINAL_PIXELS"
    assert result["decisions"][0]["citations"][0]["deterministic_semantic_verification"] is False


def test_adjudicator_structural_pixel_observation_gets_one_bounded_repair(tmp_path, monkeypatch):
    public = tmp_path / "public"
    public.mkdir()
    pdf(public / "invoice.pdf", ["ISSUED INVOICE INV-7.", "Net total EUR 150.00."], scan=True)
    root = tmp_path / "documents"
    batch = inventory_sources(public, root)
    document = batch.documents[0]
    parsed = read_document(document, root)

    def extraction(amount: str, invocation: str):
        prompt_version = prompt_version_for_guidance("adjudicator structure retry")
        binding = bind_visual_pages(document, parsed, root, model="synthetic-model",
            prompt_version=prompt_version, invocation_id=invocation)
        observations = [
            ("entity_kind", "ENUM", "INVOICE_LINE", "ISSUED INVOICE"),
            ("document_role", "ENUM", "INVOICE", "ISSUED INVOICE"),
            ("document_status", "ENUM", "ISSUED", "ISSUED"),
            ("invoice_id", "IDENTIFIER", "INV-7", "INV-7"),
            ("net_amount", "DECIMAL", amount, "Net total EUR " + amount),
        ]
        raw = {"status": "NEEDS_REVIEW", "limitations": [], "observations": [
            {"semantic_type": semantic, "value_type": kind, "value": value,
             "visible_text": quote, "page": 1, "ambiguity": [], "entity_hint": "invoice-line"}
            for semantic, kind, value, quote in observations]}
        return validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
            "synthetic-model", prompt_version=prompt_version, visual_bindings=binding,
            invocation_id=invocation), batch, root)

    primary = (extraction("150.00", "primary"),)
    challenger = (extraction("100.00", "challenger"),)
    qa = compare_extractions(batch, primary, challenger, root)
    with tempfile.TemporaryDirectory() as directory:
        preview, _, _ = _render_hash(document, root, "page:1", Path(directory))
    source_id = document.source_id

    def response(*, extra_observation: bool):
        observations = ([{"semantic_type": "date", "value_type": "DATE", "value": "2026-09-03",
            "visible_text": "2026-09-03", "page": 1, "ambiguity": [], "entity_hint": "date-only-group"}]
            if extra_observation else [])
        return {"decisions": [{"source_id": source_id, "selection": "PRIMARY",
            "rationale": "Pixel binding resolves the amount candidate for later review.",
            "citations": [{"source_id": source_id, "location": "page:1",
                "quote": "Net total EUR 150.00", "preview_sha256": preview}],
            "observations": observations}]}

    responses = [response(extra_observation=True), response(extra_observation=False)]
    prompts = []
    original_run = subprocess.run

    def fake_codex(command, **kwargs):
        if "input" not in kwargs:
            return original_run(command, **kwargs)
        input = kwargs["input"]
        prompts.append(input)
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps(responses.pop(0)))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("againward.documents.adjudication.subprocess.run", fake_codex)
    result = adjudicate_with_codex(batch, primary, challenger, qa, root, model="synthetic-model",
                                   validate_pixel_observations=validate_rental_extraction)
    assert result["status"] == "RESOLVED_FOR_FACT_REVIEW"
    assert len(prompts) == 2
    assert "required source-supported entity metadata" in prompts[1]
    assert "choose UNRESOLVED where necessary" in prompts[1]
