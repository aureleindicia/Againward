"""Material QA selection reopens exact source evidence and grants no approval."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

import pytest

from againward.documents.adjudication import (_SCHEMA, adjudicate_with_codex,
    validate_adjudication, verify_adjudication_pixels)
from againward.documents.codex_provider import assemble_proposal, bind_visual_pages, prompt_version_for_guidance
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal
from againward.documents.independent_qa import compare_extractions
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
                          "citations": [
                              {"source_id": email.source_id, "location": "line:1",
                               "quote": "This email is not proof of physical return."},
                              {"source_id": contract.source_id, "location": "line:1",
                               "quote": "an off-hire request alone does not stop billing."},
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
    assert "selection chooses a source-local observation set" in prompts[0]
    assert "does NOT establish contractual authority" in prompts[0]
    assert "different phrasing or grouping alone is not a material" in prompts[0]
    stale = deepcopy(qa)
    stale["source_results"][0]["primary_status"] = "FAILED"
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        adjudicate_with_codex(batch, primary, challenger, stale, root, model="synthetic-model")
    assert len(calls) == 1


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
        "citations": [
            {"source_id": rate_doc.source_id, "location": "line:2",
             "quote": "This duplicates daily prices in the signed agreement; no amendment."},
            {"source_id": rate_doc.source_id, "location": "line:3",
             "quote": "LIFT-5 / SN-L5-204: net EUR 50.00 per asset per calendar day."},
            {"source_id": rate_doc.source_id, "location": "line:4",
             "quote": "LIFT-50 / SN-L50-830: net EUR 30.00 per asset per calendar day."}]}]}
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
        "citations": [{"source_id": document.source_id, "location": "page:1",
                       "quote": "returned 2026-09-05", "preview_sha256": preview}]}]}, root)
    assert result["status"] == "RESOLVED_FOR_FACT_REVIEW"
    assert result["facts_approved"] == 0 and result["delivery_approved"] is False
    assert result["decisions"][0]["citations"][0]["verification_method"] == "MULTIMODAL_ORIGINAL_PIXELS"
    assert result["decisions"][0]["citations"][0]["deterministic_semantic_verification"] is False
