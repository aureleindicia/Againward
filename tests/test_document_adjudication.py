"""Material QA selection reopens exact source evidence and grants no approval."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

import pytest

from againward.documents.adjudication import adjudicate_with_codex, validate_adjudication, verify_adjudication_pixels
from againward.documents.codex_provider import assemble_proposal
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

    def fake_codex(command, *, input, **_kwargs):
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
        return validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
                                                   "scripted-model"), batch, root)

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
