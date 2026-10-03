"""Derive one local prerequisite issue; no model decision or financial fallback."""
from __future__ import annotations

from typing import Any
from pathlib import Path

from againward.core.artifact_store import read_json
from againward.documents.contracts import DocumentError, SourceBatch
from againward.evidence.hashing import stable_hash

from .calculation import readiness
from .protocol import BillingFailure
from .review import current_review

DESCRIPTIONS = {
    "SOURCE_NOT_READ": "This original source has no bound reading yet. Inspect or request a source-local reading; do not invent absent observations.",
    "SOURCE_OCCURRENCE_MISSING": "This source's observations do not yet form a scoped invoice line or tariff term. Declare a candidate only with complete unambiguous evidence; inspect/re-read missing original facts.",
    "GOVERNS_MISSING": "No candidate relation establishes which accepted tariff governs this invoice line. Compare supplier, PDL and effective dates; ambiguity must remain unresolved.",
    "READY_PROPOSAL": "Python currently finds no remaining scoped prerequisite gap. You may request readiness; only Python can create the final calculation.",
}


def local_issue(code: str, *, sources: list[str] | None = None, targets: list[str] | None = None,
                diagnostic: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "targets": targets or [], "diagnostic": diagnostic or {}}
    if sources:
        if len(sources) != 1:
            raise ValueError("A source issue must be local to one document")
        body["source_id"] = sources[0]
    return {"issue_id": "eb-focus-" + stable_hash(body), **body,
            "description": DESCRIPTIONS.get(code, "Resolve only this root prerequisite. Independent review, source inspection or re-reading may help; do not bypass the diagnostic.")}


def next_issue(state: dict[str, Any], root: Path) -> dict[str, Any]:
    """Missing sources/objects, then local reviews, then readiness root only.

    Documents and targets are ordered by immutable identity, never filename.
    Unknown or competing material documents are not automatically irrelevant.
    """
    batch = SourceBatch.from_dict(state["batch"])
    for document in sorted(batch.documents, key=lambda d: d.source_id):
        # Receipts retain their source even if the model extracted zero atoms.
        read = any(read_json(root / "energy_billing" / "readings" / (digest + ".json"))["source_id"] == document.source_id
                   for digest in state["readings"])
        if not read:
            return local_issue("SOURCE_NOT_READ", sources=[document.source_id])
        if not any(row["source_id"] == document.source_id for row in state["occurrences"].values()):
            return local_issue("SOURCE_OCCURRENCE_MISSING", sources=[document.source_id])
    for target in sorted(state["occurrences"]):
        try:
            current_review(state, target, root)
        except BillingFailure as exc:
            if exc.code not in {"MATERIAL_EVIDENCE_MISSING", "REVIEW_STALE", "BUSINESS_AMBIGUITY"}:
                raise
            return local_issue(exc.code, targets=[target], diagnostic=exc.diagnostic)
    decision = readiness(state, root)
    if decision["support_state"] == "UNSUPPORTED":
        raise BillingFailure("UNSUPPORTED_DOMAIN_RULE", stage="ENVELOPE", root_issues=decision["root_issues"])
    if not state["relations"] and len(state["occurrences"]) == 2:
        kinds = {row["kind"] for row in state["occurrences"].values()}
        if kinds == {"INVOICE", "TARIFF"}:
            return local_issue("GOVERNS_MISSING", targets=sorted(state["occurrences"]))
    for target in sorted(state["relations"]):
        try:
            current_review(state, target, root)
        except BillingFailure as exc:
            if exc.code not in {"MATERIAL_EVIDENCE_MISSING", "REVIEW_STALE", "BUSINESS_AMBIGUITY"}:
                raise
            return local_issue(exc.code, targets=[target], diagnostic=exc.diagnostic)
    if decision["ready"]:
        return local_issue("READY_PROPOSAL", targets=sorted(state["relations"]))
    diagnostic = decision["root_issues"][0]
    if diagnostic["code"] in {"SOURCE_CHANGED", "SOURCE_UNREADABLE"}:
        raise DocumentError(diagnostic["code"], "Current original source is not inspectable")
    sources = diagnostic.get("source_ids", [])
    return local_issue(diagnostic["code"], sources=sources[:1], targets=sorted(state["occurrences"]), diagnostic=diagnostic)
