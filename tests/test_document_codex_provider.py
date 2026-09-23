"""The model adapter may propose, but exact source and privacy remain authorities."""
import json
from pathlib import Path
import subprocess

import pytest

from againward.documents.codex_provider import CodexCliProvider, assemble_proposal
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources


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
    assert validate_proposal(proposal, batch, root).candidates[0].value == "850.00"


def test_model_budget_refuses_oversized_units_before_subprocess(tmp_path, monkeypatch):
    root, batch, document, parsed = _source(tmp_path, "x" * 30_001)
    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run",
                        lambda *args, **kwargs: pytest.fail("No model call allowed"))
    with pytest.raises(DocumentError, match="RESOURCE_LIMIT"):
        CodexCliProvider(root, model="gpt-5.3-codex").propose(
            document, parsed, {"batch": batch, "semantic_guidance": "Rental"})
