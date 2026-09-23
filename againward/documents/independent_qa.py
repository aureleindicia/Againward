"""Blind source reread and conservative, entity-level extraction comparison.

The challenger receives original source units and independent instructions, never
the primary proposal. Agreement is a diagnostic, not proof of correctness or
authority to deliver. Disagreement must be reconciled before fact promotion.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from againward.evidence.hashing import stable_hash
from .codex_provider import CodexCliProvider
from .contracts import DocumentError, SourceBatch
from .extraction import DocumentExtraction, persist_extraction, replay_extraction, validate_proposal
from .readers import read_document
from .sources import verify_batch


QA_GUIDANCE_VERSION = "rental-independent-source-reread-v1"
QA_INSTRUCTIONS = """
INDEPENDENT ADVERSARIAL SOURCE REREAD. You have not seen the first extraction.
Read every original unit/page before answering. Search for material facts the
first pass might omit: all distinct invoice lines, issued credits and their
allocations, accepted terms versus mere proposals, exact quantities, dates,
rates, units, currencies, physical returns versus off-hire requests, and
duplicate exports that must not become new charges. Inspect internal conflicts.
Output source-local observations only, using the same closed Rental vocabulary.
Do not guess missing fields, compute money, or invent cross-document links.
Do not treat a document's existence as proof of contractual acceptance.
"""


def _entity_bundles(extraction: DocumentExtraction) -> Counter[str]:
    """Compare complete entities, not loose field multisets that hide swaps."""
    by_entity: dict[str, list[tuple[str, str, str]]] = {}
    for candidate in extraction.candidates:
        value = json.dumps(candidate.value, sort_keys=True, ensure_ascii=False)
        by_entity.setdefault(candidate.entity_id, []).append(
            (candidate.semantic_type, candidate.value_type, value))
    return Counter(stable_hash(sorted(fields)) for fields in by_entity.values())


def compare_extractions(batch: SourceBatch, primary: tuple[DocumentExtraction, ...],
                        challenger: tuple[DocumentExtraction, ...], root: Path) -> dict[str, Any]:
    """Fail closed on omissions, entity-field swaps, unreadable sources or stale bytes."""
    verify_batch(batch, root)
    expected = {document.source_id for document in batch.documents}
    if (len(primary) != len(expected) or len(challenger) != len(expected)
            or {extraction.source_id for extraction in primary} != expected
            or {extraction.source_id for extraction in challenger} != expected):
        raise DocumentError("EXTRACTION_INCOMPLETE", "Both passes must cover every source exactly once")
    first = {extraction.source_id: replay_extraction(extraction.to_dict(), batch, root) for extraction in primary}
    second = {extraction.source_id: replay_extraction(extraction.to_dict(), batch, root) for extraction in challenger}
    rows = []
    for document in batch.documents:
        p, q = first[document.source_id], second[document.source_id]
        a, b = _entity_bundles(p), _entity_bundles(q)
        difference = bool(a != b or p.status == "FAILED" or q.status == "FAILED"
                          or p.limitations or q.limitations)
        rows.append({"source_id": document.source_id, "source_sha256": document.sha256,
                     "primary_extraction_sha256": p.to_dict()["extraction_sha256"],
                     "challenger_extraction_sha256": q.to_dict()["extraction_sha256"],
                     "primary_status": p.status, "challenger_status": q.status,
                     "primary_only_entity_bundles": sum((a - b).values()),
                     "challenger_only_entity_bundles": sum((b - a).values()),
                     "primary_limitations": list(p.limitations),
                     "challenger_limitations": list(q.limitations),
                     "needs_reconciliation": difference})
    body = {"schema_version": "againward-independent-source-qa-v1",
            "qa_guidance_version": QA_GUIDANCE_VERSION,
            "batch_id": batch.batch_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "RECONCILIATION_REQUIRED" if any(row["needs_reconciliation"] for row in rows) else "AGREEMENT",
            "source_results": rows,
            "delivery_approved": False,
            "limitations": ["Same model family may share errors; agreement is not a blind accuracy estimate.",
                            "This check compares proposed source-local facts, not entity links, financial calculations or report completeness."]}
    body["qa_sha256"] = stable_hash(body)
    return body


def reread_sources(batch: SourceBatch, primary: tuple[DocumentExtraction, ...],
                   root: Path, *, model: str, timeout_seconds: int = 180) -> tuple[dict[str, Any], tuple[Path, ...]]:
    """Independently request all source units; stop if any challenge fails."""
    provider = CodexCliProvider(root, model=model, timeout_seconds=timeout_seconds)
    challenger = []
    paths = []
    # No primary facts, review decisions, oracle or financial result enter this call.
    from againward.domains.rental.semantic_guidance import guidance
    for document in batch.documents:
        parsed = read_document(document, root)
        proposal = provider.propose(document, parsed,
                                    {"batch": batch, "semantic_guidance": guidance() + QA_INSTRUCTIONS})
        extraction = validate_proposal(proposal, batch, root)
        challenger.append(extraction)
        paths.append(persist_extraction(extraction, root))
    return compare_extractions(batch, primary, tuple(challenger), root), tuple(paths)
