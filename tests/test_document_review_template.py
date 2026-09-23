"""A worksheet never impersonates an analyst or approves a model candidate."""
import pytest

from againward.documents.contracts import DocumentError
from againward.documents.extraction import promote_facts, validate_proposal
from againward.documents.readers import read_document
from againward.documents.review_template import fact_review_template
from againward.documents.sources import inventory_sources
from tests.test_document_codex_provider import _raw
from againward.documents.codex_provider import assemble_proposal


def test_review_template_requires_operator_and_covers_every_candidate(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    (public / "invoice.txt").write_text("Invoice INV-9: net EUR 850.00.")
    root = tmp_path / "documents"
    batch = inventory_sources(public, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    extraction = validate_proposal(assemble_proposal(_raw(parsed.units[0].location, "850.00"),
                                                    document, parsed, batch.batch_id, "TEST"), batch, root)
    template, sheet = fact_review_template(batch, (extraction,))
    assert template["reviewer_role"] is None
    assert template["limitations_acknowledged"] is False
    assert template["decisions"][0]["decision"] == "DEFER"
    assert "850.00" in sheet and document.sha256 in sheet
    with pytest.raises(DocumentError, match="Invalid fact review"):
        promote_facts((extraction,), template, batch, root)


def test_review_template_refuses_missing_source_extraction(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    (public / "invoice.txt").write_text("Invoice INV-9.")
    batch = inventory_sources(public, tmp_path / "documents")
    with pytest.raises(DocumentError, match="EXTRACTION_INCOMPLETE"):
        fact_review_template(batch, ())
