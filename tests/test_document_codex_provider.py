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
from againward.domains.rental.models import DOCUMENT_ROLES
from againward.domains.rental.semantic_guidance import guidance
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
    diagnostics = list((root.parent / "scratch/visual_model_diagnostics").glob("*.json"))
    assert len(diagnostics) == 1
    assert "raw_response" in json.loads(diagnostics[0].read_text())
    raw["observations"][0].update(value_type="CURRENCY", value="150.00 EUR")
    combined = validate_proposal(provider.propose(document, parsed,
        {"batch": batch, "semantic_guidance": "Rental billing"}), batch, root).candidates[0]
    assert combined.value_type == "DECIMAL" and combined.value == "150.00"
    assert "NUMERIC_NORMALIZATION_REQUIRES_REVIEW" in combined.ambiguity_flags


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
