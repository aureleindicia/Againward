"""Architecture invariants on generic sources; no known dossier or oracle inputs."""
from dataclasses import replace
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from againward.documents.adjudication import adjudicate_with_codex, validate_adjudication
from againward.documents.analyst_review import build_analyst_review, review_visual_with_codex
from againward.documents.codex_provider import assemble_proposal, bind_visual_pages, prompt_version_for_guidance
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal, promote_facts, replay_extraction, CanonicalFact
from againward.documents.independent_qa import compare_extractions
from againward.documents.readers import read_document
from againward.documents.reconciliation import assemble_observations
from againward.documents.resolution import Entity
from againward.documents.sources import inventory_sources
from againward.domains.rental.document_adapter import _line_identifier
from againward.domains.rental.extraction_validation import validate_rental_extraction, package_source_gaps
from againward.domains.rental.entity_contract import normalize_document_envelopes, structural_gaps
from tests.test_document_analyst_review import _native_decisions

CONTENT = "Issued Invoice ZX-42 rental net 730.00 EUR."
FIELDS = [("entity_kind", "ENUM", "INVOICE_LINE", "rental"),
          ("document_role", "ENUM", "INVOICE", "Invoice"),
          ("document_status", "ENUM", "ISSUED", "Issued"),
          ("invoice_id", "IDENTIFIER", "ZX-42", "ZX-42"),
          ("net_amount", "DECIMAL", "730.00", "730.00"),
          ("charge_type", "ENUM", "RENTAL", "rental"),
          ("currency", "CURRENCY", "EUR", "EUR")]


def _fixture(tmp_path, *, visual=False):
    incoming = tmp_path / "incoming"
    incoming.mkdir(parents=True)
    if visual:
        from benchmarking.document_renderers import pdf
        pdf(incoming / "record.pdf", [CONTENT], scan=True)
    else:
        (incoming / "record.txt").write_text(CONTENT)
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    doc = batch.documents[0]
    parsed = read_document(doc, root)

    def read(indices, label="line"):
        raw = {"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": label, "semantic_type": field, "value_type": kind, "value": value,
             "raw_observed_value": quote, "location": parsed.units[0].location,
             "normalization_notes": "Source classification", "ambiguity_flags": []}
            for index, (field, kind, value, quote) in enumerate(FIELDS) if index in indices]}
        kwargs = {}
        if visual:
            version = prompt_version_for_guidance("")
            kwargs = {"prompt_version": version, "invocation_id": "test-visual",
                      "visual_bindings": bind_visual_pages(doc, parsed, root, model="synthetic-model",
                          prompt_version=version, invocation_id="test-visual")}
        return validate_proposal(assemble_proposal(raw, doc, parsed, batch.batch_id,
                                                  "synthetic-model", **kwargs), batch, root)
    return root, batch, read


def _dispositions(p, q):
    covered = set()
    rows = []
    for parent in (p, q):
        for c in parent.candidates:
            include = c.semantic_type not in covered
            covered.add(c.semantic_type)
            rows.append({"extraction_sha256": parent.to_dict()["extraction_sha256"],
                         "candidate_id": c.candidate_id, "decision": "INCLUDE" if include else "REJECT",
                         "entity_id": "reconciled-line" if include else ""})
    return rows


def test_complementary_partials_require_explicit_assembly_new_qa_and_new_review(tmp_path):
    root, batch, read = _fixture(tmp_path)
    p, q = read(range(5)), read([0, 1, 2, 5, 6], "other-label")
    assert package_source_gaps(p) and package_source_gaps(q)
    qa = compare_extractions(batch, (p,), (q,), root)
    raw = {"decisions": [{"source_id": p.source_id, "selection": "ASSEMBLE", "rationale": "Complementary original facts",
        "citations": [{"source_id": p.source_id, "location": "line:1", "quote": CONTENT, "preview_sha256": ""}],
        "observations": [], "candidate_selections": _dispositions(p, q)}]}
    result = validate_adjudication(batch, (p,), (q,), qa, raw, root, required_source_facts=package_source_gaps)
    assert result["facts_approved"] == 0 and p.source_id not in result["selected_extractions"]
    assembled = replay_extraction(result["assembly_proposals"][p.source_id], batch, root)
    validate_rental_extraction(assembled, require_package_facts=True)
    assert assembled.to_dict()["extraction_sha256"] not in {p.to_dict()["extraction_sha256"], q.to_dict()["extraction_sha256"]}
    fresh_qa = compare_extractions(batch, (assembled,), (q,), root)
    assert fresh_qa["qa_sha256"] != qa["qa_sha256"]
    assert fresh_qa["source_results"][0]["material_needs_reconciliation"]
    old_review = build_analyst_review(batch, (p,), _native_decisions((p,)), root)["review"]
    with pytest.raises(DocumentError):
        promote_facts((assembled,), old_review, batch, root)
    selected = deepcopy(raw)
    selected["decisions"][0].update(selection="PRIMARY", candidate_selections=[])
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        validate_adjudication(batch, (assembled,), (q,), qa, selected, root)
    final = validate_adjudication(batch, (assembled,), (q,), fresh_qa, selected, root,
                                 required_source_facts=package_source_gaps)
    assert final["selected_extractions"][p.source_id] == assembled.to_dict()["extraction_sha256"]
    fresh_review = build_analyst_review(batch, (assembled,), _native_decisions((assembled,)), root)
    facts = promote_facts((assembled,), fresh_review["review"], batch, root)
    assert [f.candidate.value for f in facts if f.candidate.semantic_type == "net_amount"] == ["730.00"]


def test_assembly_cannot_silently_omit_inputs_or_change_source_evidence(tmp_path):
    root, batch, read = _fixture(tmp_path)
    p, q = read(range(5)), read([0, 1, 2, 5, 6], "peer")
    rows = _dispositions(p, q)
    with pytest.raises(DocumentError, match="EXTRACTION_INCOMPLETE"):
        assemble_observations(p, q, rows[:-1], batch, root)
    rows[0]["value"] = "fabricated"
    with pytest.raises(DocumentError, match="EXTRACTION_SCHEMA_INVALID"):
        assemble_observations(p, q, rows, batch, root)
    (root / batch.documents[0].blob_path).write_text("Mutated")
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        assemble_observations(p, q, _dispositions(p, q), batch, root)


def test_assembled_invoice_keeps_same_source_document_identity_and_lineage(tmp_path):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "record.txt").write_text(
        "support file. invoice document is issued. INV-8 line item totals EUR 20.00.")
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    def make_read(*, include_invoice_id: bool, label: str):
        rows = [
            {"entity_id": "support", "semantic_type": "entity_kind", "value_type": "ENUM",
             "value": "SUPPORTING_DOCUMENT", "raw_observed_value": "support file"},
            {"entity_id": "support", "semantic_type": "document_role", "value_type": "ENUM",
             "value": "INVOICE", "raw_observed_value": "invoice document"},
            {"entity_id": "support", "semantic_type": "document_status", "value_type": "ENUM",
             "value": "ISSUED", "raw_observed_value": "is issued"},
            {"entity_id": label, "semantic_type": "entity_kind", "value_type": "ENUM",
             "value": "INVOICE_LINE", "raw_observed_value": "line item"},
            {"entity_id": label, "semantic_type": "currency", "value_type": "CURRENCY",
             "value": "EUR", "raw_observed_value": "EUR"},
            {"entity_id": label, "semantic_type": "net_amount", "value_type": "DECIMAL",
             "value": "20.00", "raw_observed_value": "20.00"},
        ]
        if include_invoice_id:
            rows.append({"entity_id": "support", "semantic_type": "invoice_id", "value_type": "IDENTIFIER",
                         "value": "INV-8", "raw_observed_value": "INV-8"})
        for row in rows:
            row.update(location=parsed.units[0].location, normalization_notes="Exact source observation",
                       ambiguity_flags=[])
        raw = normalize_document_envelopes({"status": "SUCCESS", "limitations": [],
                                             "candidates": rows}, visual=False)
        return validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
            "synthetic-model"), batch, root)

    primary, challenger = make_read(include_invoice_id=False, label="primary-line"), \
        make_read(include_invoice_id=True, label="challenger-line")
    source_id = primary.source_id
    seen: set[tuple[str, str]] = set()
    dispositions = []
    for proposal in (primary, challenger):
        extraction_hash = proposal.to_dict()["extraction_sha256"]
        for candidate in proposal.candidates:
            scope = "support" if candidate.entity_id == "support" else "line"
            identity = candidate.semantic_type, scope
            include = identity not in seen
            if include:
                seen.add(identity)
            dispositions.append({"extraction_sha256": extraction_hash, "candidate_id": candidate.candidate_id,
                "decision": "INCLUDE" if include else "DEFER",
                "entity_id": ("support" if candidate.entity_id == "support" else "reconciled-line")
                if include else ""})
    assembled = assemble_observations(primary, challenger, dispositions, batch, root)
    validate_rental_extraction(assembled, require_package_facts=True)
    invoice_id = next(c for c in assembled.candidates if c.entity_id == "reconciled-line"
                      and c.semantic_type == "invoice_id")
    assert invoice_id.value == "INV-8"
    assert invoice_id.source_id == source_id
    assert invoice_id.raw_observed_value == "INV-8"
    assert invoice_id.source_span is not None


def test_partial_and_contradictory_reads_are_provisional_never_calculation_ready(tmp_path):
    root, batch, read = _fixture(tmp_path)
    p = read(range(7))
    conflict = replace(p, limitations=("No net amount is visible.",), status="NEEDS_REVIEW")
    validate_rental_extraction(conflict, provisional=True)
    with pytest.raises(DocumentError, match="EXTRACTION_CONTRADICTION"):
        validate_rental_extraction(conflict, require_package_facts=True)
    qa = compare_extractions(batch, (conflict,), (conflict,), root)
    assert qa["source_results"][0]["material_needs_reconciliation"]
    assert qa["source_results"][0]["primary_contract_issues"]["validation_code"] == "OBSERVATION_LIMITATION_CONFLICT"
    incomplete = read(range(5))
    validate_rental_extraction(incomplete, allow_incomplete=True, provisional=True)
    with pytest.raises(DocumentError, match="STRUCTURAL_INCOMPLETE"):
        validate_rental_extraction(incomplete, require_package_facts=True)


def test_native_and_visual_converge_without_promoting_visual_evidence(tmp_path):
    root, batch, read = _fixture(tmp_path / "native")
    native = read(range(7))
    vroot, vbatch, vread = _fixture(tmp_path / "visual", visual=True)
    visual = vread(range(7))
    assert {(c.semantic_type, c.value) for c in native.candidates} == {(c.semantic_type, c.value) for c in visual.candidates}
    for item in (native, visual):
        validate_rental_extraction(item, require_package_facts=True)
    assert all(c.source_span is not None for c in native.candidates)
    assert all(c.source_span is None and "VISUAL_TRANSCRIPTION_UNVERIFIED" in c.ambiguity_flags for c in visual.candidates)
    forged = visual.to_dict()
    forged["visual_bindings"][0]["render_sha256"] = "0" * 64
    from againward.evidence.hashing import stable_hash
    forged["extraction_sha256"] = stable_hash({k: v for k, v in forged.items() if k != "extraction_sha256"})
    with pytest.raises(DocumentError, match="SOURCE_LOCATION_INVALID"):
        replay_extraction(forged, vbatch, vroot)
    base = build_analyst_review(vbatch, (visual,), {}, vroot)
    assert promote_facts((visual,), base["review"], vbatch, vroot) == ()


def test_technical_line_identity_does_not_depend_on_model_group_label(tmp_path):
    _root, _batch, read = _fixture(tmp_path)
    p, q = read(range(7), "one"), read(range(7), "another")
    entities = [Entity("model-" + str(i), str(i), item.source_id, "INVOICE_LINE",
        tuple(CanonicalFact("f"+str(n), c, "e", "r", "reviewed") for n, c in enumerate(item.candidates)))
        for i, item in enumerate((p, q))]
    assert _line_identifier(entities[0])[0] == _line_identifier(entities[1])[0]
    assert entities[0].values["net_amount"] == entities[1].values["net_amount"] == "730.00"


def test_rejected_entity_metadata_cannot_inherit_accepted_authority():
    accepted = [("source", "a", f) for f in ("entity_kind", "document_role", "document_status")]
    accepted += [("source", "b", "entity_kind"), ("source", "b", "net_amount")]
    offered = accepted + [("source", "b", "document_status")]
    gaps = structural_gaps(accepted, offered=offered)
    assert gaps == [{"source_id": "source", "entity_id": "b", "missing": ["document_status"]}]


def test_focused_adjudication_schema_binds_one_source_and_disallows_native_pixels(tmp_path, monkeypatch):
    root, batch, read = _fixture(tmp_path)
    p, q = read(range(7)), read(range(5))
    qa = compare_extractions(batch, (p,), (q,), root)
    calls = []
    def respond(command, **kwargs):
        schema = json.loads(Path(command[command.index("--output-schema") + 1]).read_text())
        assert schema["type"] == "object" and "source_id" not in schema["properties"]
        context = json.JSONDecoder().raw_decode(kwargs["input"].split("\n", 1)[1])[0]
        assert [d["source_id"] for d in context["material_disagreements"]] == [p.source_id]
        assert schema["properties"]["observations"]["maxItems"] == 0
        body = {"decisions": [{"source_id": p.source_id, "selection": "PRIMARY", "rationale": "Read source",
                "candidate_selections": [], "observations": [], "citations": [{"source_id": p.source_id,
                "location": "line:1", "quote": CONTENT, "preview_sha256": ""}]}]}
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(body))
        calls.append(1)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr("againward.documents.adjudication.subprocess.run", respond)
    result = adjudicate_with_codex(batch, (p,), (q,), qa, root, model="synthetic-model")
    assert len(calls) == 1 and result["facts_approved"] == 0
    # Cardinality remains fail-closed even if the provider disregards its schema.
    with pytest.raises(DocumentError, match="EXTRACTION_INCOMPLETE"):
        validate_adjudication(batch, (p,), (q,), qa, {"decisions": []}, root)


def test_mixed_native_visual_review_does_not_index_empty_candidate_set(tmp_path, monkeypatch):
    # A fully native source is valid in a visual-review batch and has no pixel candidates.
    root, batch, read = _fixture(tmp_path)
    p = read(range(7))
    base = build_analyst_review(batch, (p,), _native_decisions((p,)), root)
    monkeypatch.setattr("againward.documents.analyst_review._ask_codex", lambda *a, **kw: pytest.fail("No visual invocation needed"))
    result = review_visual_with_codex(batch, (p,), base, root, model="synthetic-model")
    assert result["visual_analyst_model_calls"] == 0
    assert result["visual_structural_gaps"] == []
    assert result["human_approval"] is False


def test_job_reconciles_then_replays_reviews_and_stops_cleanly_on_missing_business_evidence(tmp_path, monkeypatch):
    from againward.core.workspace import create_client_workspace
    from againward.domains.rental.source_job import run_approved_sources_job
    create_client_workspace("generic", root=tmp_path, synthetic=True, domain_name="rental", intake_payload={})
    workspace = tmp_path / "generic"
    (workspace / "incoming" / "record.txt").write_text(CONTENT)
    reads, adjudications, reviews = [], [], []

    def propose(self, document, parsed, context):
        indices = range(5) if context["invocation_phase"] == "PRIMARY_EXTRACTION" else [0, 1, 2, 5, 6]
        reads.append(context["invocation_phase"])
        raw = {"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": "line", "semantic_type": field, "value_type": kind, "value": value,
             "raw_observed_value": quote, "location": parsed.units[0].location,
             "normalization_notes": "Source observation", "ambiguity_flags": []}
            for i, (field, kind, value, quote) in enumerate(FIELDS) if i in indices]}
        return assemble_proposal(raw, document, parsed, context["batch"].batch_id, "synthetic-model")

    def decide(batch, primary, challenger, qa, root, **kwargs):
        adjudications.append(qa["qa_sha256"])
        p, q = primary[0], challenger[0]
        assemble = len(adjudications) == 1
        assert kwargs["allow_assembly"] == assemble
        if not assemble:
            assert kwargs["assembly_context"]["original_primary"]
            assert not reviews
        raw = {"decisions": [{"source_id": p.source_id,
            "selection": "ASSEMBLE" if assemble else "PRIMARY", "rationale": "Read exact original",
            "candidate_selections": _dispositions(p, q) if assemble else [], "observations": [],
            "citations": [{"source_id": p.source_id, "location": "line:1", "quote": CONTENT, "preview_sha256": ""}]}]}
        return validate_adjudication(batch, primary, challenger, qa, raw, root,
                                     required_source_facts=package_source_gaps)

    def review(batch, selected, root, **kwargs):
        reviews.append(selected[0].to_dict()["extraction_sha256"])
        result = build_analyst_review(batch, selected, _native_decisions(selected), root)
        result.update(model_calls=1)
        from againward.evidence.hashing import stable_hash
        result["receipt_sha256"] = stable_hash({k: v for k, v in result.items() if k != "receipt_sha256"})
        return result

    def missing_relation(*args, **kwargs):
        raise DocumentError("ENTITY_AMBIGUOUS", "No supported contractual link",
            diagnostic={"schema_path": "$.relationships", "validation_code": "MISSING_REVIEWED_LINK",
                        "error_category": "SOURCE_EVIDENCE_MISSING"})

    monkeypatch.setattr("againward.documents.codex_provider.CodexCliProvider.propose", propose)
    monkeypatch.setattr("againward.domains.rental.source_job.adjudicate_with_codex", decide)
    monkeypatch.setattr("againward.domains.rental.source_job.review_with_codex", review)
    monkeypatch.setattr("againward.domains.rental.source_job.load_document_case", missing_relation)
    result = run_approved_sources_job(workspace, model="synthetic-model", evaluation_only=True)
    assert result["status"] == "WAITING_FOR_REQUIRED_INFORMATION"
    assert result["stage"] == "DOCUMENT_PACKAGE_VALIDATION"
    assert result["diagnostic"]["validation_code"] == "MISSING_REVIEWED_LINK"
    assert len(reads) == 2 and len(set(adjudications)) == 2 and len(reviews) == 1
    state = json.loads((workspace / "processed/source_job_state.json").read_text())
    assert state["qa_receipt"] != state["preassembly_qa_receipt"]
    assert not any(e["phase"] == "CALCULATING" for e in state["events"])
    # Resume revalidates lineage and uses only reviews bound to the new hash.
    again = run_approved_sources_job(workspace, model="synthetic-model", evaluation_only=True)
    assert again["status"] == "WAITING_FOR_REQUIRED_INFORMATION"
    assert len(reads) == 2 and len(adjudications) == 2 and len(reviews) == 1


def test_global_adjudication_collects_exactly_one_validated_decision_per_disputed_source(tmp_path, monkeypatch):
    from tests.test_document_adjudication import _case
    root, batch, primary, challenger, _, _, _ = _case(tmp_path)
    changed = replace(challenger[0], candidates=tuple(replace(c, value="PROPOSED")
        if c.semantic_type == "document_status" else c for c in challenger[0].candidates))
    challenger = (changed, challenger[1])
    qa = compare_extractions(batch, primary, challenger, root)
    expected = {row["source_id"] for row in qa["source_results"] if row["material_needs_reconciliation"]}
    assert len(expected) == 2
    calls = []
    def respond(command, **kwargs):
        schema = json.loads(Path(command[command.index("--output-schema") + 1]).read_text())
        assert "source_id" not in schema["properties"]
        context = json.JSONDecoder().raw_decode(kwargs["input"].split("\n", 1)[1])[0]
        source_ids = [d["source_id"] for d in context["material_disagreements"]]
        assert len(source_ids) == 1
        calls.append(source_ids[0])
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps({"decisions": [{
            "source_id": source_ids[0], "selection": "UNRESOLVED", "rationale": "Ambiguous source",
            "citations": [], "observations": [], "candidate_selections": []}]}))
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr("againward.documents.adjudication.subprocess.run", respond)
    result = adjudicate_with_codex(batch, primary, challenger, qa, root, model="synthetic-model")
    assert len(calls) == len(set(calls)) == 2
    assert set(result["material_unresolved_source_ids"]) == expected
    assert result["selected_extractions"] == {} and result["facts_approved"] == 0


def test_visual_review_mixed_batch_inspects_pixels_and_skips_native_empty_visual_group(tmp_path, monkeypatch):
    from benchmarking.document_renderers import pdf
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "native.txt").write_text(CONTENT)
    pdf(incoming / "scan.pdf", [CONTENT], scan=True)
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    extractions = []
    for doc in batch.documents:
        parsed = read_document(doc, root)
        visual = any(u.route != "NATIVE" for u in parsed.units)
        raw = {"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": "line", "semantic_type": field, "value_type": kind, "value": value,
             "raw_observed_value": quote, "location": parsed.units[0].location,
             "normalization_notes": "Original-source classification", "ambiguity_flags": []}
            for field, kind, value, quote in FIELDS]}
        kwargs = {}
        if visual:
            version = prompt_version_for_guidance("")
            kwargs = {"prompt_version": version, "invocation_id": "mixed-test",
                "visual_bindings": bind_visual_pages(doc, parsed, root, model="synthetic-model",
                    prompt_version=version, invocation_id="mixed-test")}
        extractions.append(validate_proposal(assemble_proposal(raw, doc, parsed, batch.batch_id,
                                                               "synthetic-model", **kwargs), batch, root))
    selected = tuple(extractions)
    native = tuple(e for e in selected if all(c.source_span is not None for c in e.candidates))
    base = build_analyst_review(batch, selected, _native_decisions(native), root)
    pixels = [c for e in selected for c in e.candidates if c.source_span is None]
    def read_pixels(prompt, **kwargs):
        assert len(kwargs["images"]) == 1
        return {"decisions": [{"candidate_id": c.candidate_id, "decision": "ACCEPT",
                "reason": "Visible original pixels", "resolved_flags": []} for c in pixels]}, 0.1
    monkeypatch.setattr("againward.documents.analyst_review._ask_codex", read_pixels)
    reviewed = review_visual_with_codex(batch, selected, base, root, model="synthetic-model")
    assert reviewed["status"] == "WAITING_FOR_VISUAL_ATTESTATION"
    assert reviewed["visual_candidates_pending_attestation"] == len(pixels)
    assert reviewed["human_approval"] is False
    assert reviewed["visual_structural_gaps"] == []
    with pytest.raises(DocumentError):
        promote_facts(selected, reviewed["review"], batch, root)


def test_assembly_package_cannot_lose_parent_lineage_or_smuggle_changed_values(tmp_path):
    root, batch, read = _fixture(tmp_path)
    p, q = read(range(5)), read([0, 1, 2, 5, 6], "peer")
    assembled = assemble_observations(p, q, _dispositions(p, q), batch, root)
    changed = replace(assembled, candidates=tuple(replace(c, value="CREDIT") if c.semantic_type == "entity_kind" else c
                                                  for c in assembled.candidates))
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        replay_extraction(changed.to_dict(), batch, root)
    receipt = root / "assemblies" / (assembled.assembly_receipt_sha256 + ".json")
    receipt.unlink()
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        replay_extraction(assembled.to_dict(), batch, root)


def test_visual_partial_assembly_keeps_unapproved_pixel_flags_and_parent_bindings(tmp_path):
    root, batch, read = _fixture(tmp_path, visual=True)
    p, q = read(range(5)), read([0, 1, 2, 5, 6], "peer")
    assembled = assemble_observations(p, q, _dispositions(p, q), batch, root)
    validate_rental_extraction(assembled, require_package_facts=True)
    assert assembled.assembly_receipt_sha256
    assert assembled.visual_bindings == p.visual_bindings
    assert all("VISUAL_TRANSCRIPTION_UNVERIFIED" in c.ambiguity_flags for c in assembled.candidates)
    base = build_analyst_review(batch, (assembled,), {}, root)
    assert promote_facts((assembled,), base["review"], batch, root) == ()


def test_every_reader_retry_contract_fits_provider_budget_and_current_registry():
    from againward.documents.independent_qa import QA_INSTRUCTIONS, RETRY_INSTRUCTIONS, VISUAL_RETRY_INSTRUCTIONS
    from againward.domains.rental.semantic_guidance import guidance, visual_guidance, STRUCTURE_RETRY_INSTRUCTIONS
    from againward.domains.rental.document_adapter import _current_extraction_prompt_versions
    from againward.domains.rental.entity_contract import observation_instructions
    for base, retry in ((guidance(), RETRY_INSTRUCTIONS), (visual_guidance(), VISUAL_RETRY_INSTRUCTIONS)):
        assert base.count(observation_instructions()) == 1
        for peer in ("", QA_INSTRUCTIONS):
            for suffix in ("", retry, retry + STRUCTURE_RETRY_INSTRUCTIONS):
                composed = base + peer + suffix
                assert len(composed) + 100 < 12_000  # room for bounded diagnostic hints
                assert prompt_version_for_guidance(composed) in _current_extraction_prompt_versions()
    assert guidance() in visual_guidance()


def test_assembly_references_bound_by_runtime_preserve_explicit_dispositions(tmp_path):
    from againward.documents.adjudication import bind_model_citations
    root, batch, read = _fixture(tmp_path)
    p, q = read(range(5)), read([0, 1, 2, 5, 6], "peer")
    old = _dispositions(p, q)
    by_hash = {item.to_dict()["extraction_sha256"]: (name, item)
               for name, item in (("PRIMARY", p), ("CHALLENGER", q))}
    refs = []
    for row in old:
        name, parent = by_hash[row["extraction_sha256"]]
        refs.append({"reader": name, "candidate_index": next(i for i, c in enumerate(parent.candidates, 1)
                    if c.candidate_id == row["candidate_id"]),
                    "decision": row["decision"], "entity_id": row["entity_id"]})
    raw = {"decisions": [{"source_id": p.source_id, "selection": "ASSEMBLE", "rationale": "Complementary evidence",
        "candidate_selections": refs, "observations": [],
        "citations": [{"source_id": p.source_id, "location": "line:1", "quote": CONTENT}]}]}
    bound = bind_model_citations(raw, [], primary=(p,), challenger=(q,))
    assert bound["decisions"][0]["candidate_selections"] == old
    assert "extraction_sha256" not in raw["decisions"][0]["candidate_selections"][0]
    qa = compare_extractions(batch, (p,), (q,), root)
    result = validate_adjudication(batch, (p,), (q,), qa, bound, root, required_source_facts=package_source_gaps)
    assert result["facts_approved"] == 0
    assert result["assembly_proposals"]
    for bad_index in (0, -1, 1000, True, "1"):
        invalid = deepcopy(raw)
        invalid["decisions"][0]["candidate_selections"][0]["candidate_index"] = bad_index
        with pytest.raises(DocumentError) as exc:
            bind_model_citations(invalid, [], primary=(p,), challenger=(q,))
        assert exc.value.diagnostic["validation_code"] == "ASSEMBLY_REFERENCE_INVALID"


def test_fresh_pixel_citation_not_candidate_locked_but_does_not_approve_facts(tmp_path):
    from againward.documents.adjudication import bind_model_citations, verify_adjudication_pixels
    from againward.documents.visual_fact_review import _render_hash
    import tempfile
    root, batch, read = _fixture(tmp_path, visual=True)
    p, q = read(range(7)), read(range(5), "peer")
    qa = compare_extractions(batch, (p,), (q,), root)
    with tempfile.TemporaryDirectory() as directory:
        render, _, _ = _render_hash(batch.documents[0], root, "page:1", Path(directory))
    raw = {"decisions": [{"source_id": p.source_id, "selection": "PRIMARY", "rationale": "Read original pixels",
        "candidate_selections": [], "observations": [],
        "citations": [{"source_id": p.source_id, "location": "page:1", "quote": CONTENT}]}]}
    assert CONTENT not in {c.raw_observed_value for c in (*p.candidates, *q.candidates)}
    bound = bind_model_citations(raw, [{"source_id": p.source_id, "location": "page:1", "preview_sha256": render}])
    result = validate_adjudication(batch, (p,), (q,), qa, bound, root)
    assert result["facts_approved"] == 0 and result["delivery_approved"] is False
    assert result["decisions"][0]["pixel_observations"] == []
    verify_adjudication_pixels(batch, result, root)
    native_review = build_analyst_review(batch, (p,), {}, root)
    assert native_review["native_facts_accepted"] == 0
    assert not promote_facts((p,), native_review["review"], batch, root)
    wrong_page = deepcopy(raw)
    wrong_page["decisions"][0]["citations"][0]["location"] = "page:99"
    with pytest.raises(DocumentError, match="SOURCE_LOCATION_INVALID"):
        validate_adjudication(batch, (p,), (q,), qa, bind_model_citations(wrong_page, []), root)
    stale = deepcopy(bound)
    stale["decisions"][0]["citations"][0]["preview_sha256"] = "0" * 64
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        validate_adjudication(batch, (p,), (q,), qa, bind_model_citations(stale, []), root)


def test_runtime_binding_never_converts_native_paraphrase_to_evidence(tmp_path):
    from againward.documents.adjudication import bind_model_citations
    root, batch, read = _fixture(tmp_path)
    p, q = read(range(7)), read(range(5))
    qa = compare_extractions(batch, (p,), (q,), root)
    raw = {"decisions": [{"source_id": p.source_id, "selection": "PRIMARY", "rationale": "Wrong quote",
        "candidate_selections": [], "observations": [],
        "citations": [{"source_id": p.source_id, "location": "line:1", "quote": "rental totals 730 euros"}]}]}
    with pytest.raises(DocumentError, match="SOURCE_LOCATION_INVALID"):
        validate_adjudication(batch, (p,), (q,), qa, bind_model_citations(raw, []), root)
