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
from .disposition import active_occurrences, excluded_ids
from .state import REQUIRED, fields

DESCRIPTIONS = {
    "SOURCE_NOT_READ": "This original source has no bound reading yet. Inspect or request a source-local reading; do not invent absent observations.",
    "SOURCE_OCCURRENCE_MISSING": "This source's observations do not yet form a scoped invoice line or tariff term. Declare a candidate only with complete unambiguous evidence; inspect/re-read missing original facts.",
    "OBSERVATION_CONFLICT": "Conflicting normalized scalar facts remain in this original source. Inspect them; only an independent evidenced disposition can reject an extraction error or establish explicit supersession. Two genuine PDLs/terms cannot be arbitrarily selected.",
    "MATERIAL_QUARANTINE": "This rejected row is potentially financial. Preserve the valid siblings. Inspect/re-read its original source, then request independent replacement/rejection with exact evidence. Do not discard the whole document.",
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
    excluded = excluded_ids(state)
    active = active_occurrences(state)
    for document in sorted(batch.documents, key=lambda d: d.source_id):
        if document.source_id in excluded:
            continue
        # Receipts retain their source even if the model extracted zero atoms.
        read = any(read_json(root / "energy_billing" / "readings" / (digest + ".json"))["source_id"] == document.source_id
                   for digest in state["readings"])
        if not read:
            return local_issue("SOURCE_NOT_READ", sources=[document.source_id])
        material = [key for key, row in state['quarantine'].items()
                    if row['source_id'] == document.source_id and row['potentially_material'] and key not in excluded]
        if material:
            return local_issue('MATERIAL_QUARANTINE', sources=[document.source_id], targets=[sorted(material)[0]])
        scalar_ids = [key for key, row in state['observations'].items()
                      if row['source_id'] == document.source_id and key not in excluded and
                      row['field'] in set(REQUIRED['INVOICE']) | set(REQUIRED['TARIFF'])]
        try:
            fields(state, scalar_ids)
        except BillingFailure as exc:
            if exc.code != 'OCCURRENCE_AMBIGUOUS':
                raise
            conflicts = [key for key in scalar_ids if state['observations'][key]['field'] in exc.diagnostic['conflicting_fields']]
            return local_issue('OBSERVATION_CONFLICT', sources=[document.source_id], targets=sorted(conflicts), diagnostic=exc.diagnostic)
        if not any(row["source_id"] == document.source_id for row in active.values()):
            return local_issue("SOURCE_OCCURRENCE_MISSING", sources=[document.source_id])
    for target in sorted(active):
        try:
            current_review(state, target, root)
        except BillingFailure as exc:
            if exc.code not in {"MATERIAL_EVIDENCE_MISSING", "REVIEW_STALE", "BUSINESS_AMBIGUITY"}:
                raise
            return local_issue(exc.code, targets=[target], diagnostic=exc.diagnostic)
    decision = readiness(state, root)
    if decision["support_state"] == "UNSUPPORTED":
        raise BillingFailure("UNSUPPORTED_DOMAIN_RULE", stage="ENVELOPE", root_issues=decision["root_issues"])
    relations = {key: row for key, row in state['relations'].items() if row['invoice_id'] in active and row['tariff_id'] in active}
    if not relations and len(active) == 2:
        kinds = {row["kind"] for row in active.values()}
        if kinds == {"INVOICE", "TARIFF"}:
            return local_issue("GOVERNS_MISSING", targets=sorted(active))
    for target in sorted(relations):
        try:
            current_review(state, target, root)
        except BillingFailure as exc:
            if exc.code not in {"MATERIAL_EVIDENCE_MISSING", "REVIEW_STALE", "BUSINESS_AMBIGUITY"}:
                raise
            return local_issue(exc.code, targets=[target], diagnostic=exc.diagnostic)
    if decision["ready"]:
        return local_issue("READY_PROPOSAL", targets=sorted(relations))
    diagnostic = decision["root_issues"][0]
    if diagnostic["code"] in {"SOURCE_CHANGED", "SOURCE_UNREADABLE"}:
        raise DocumentError(diagnostic["code"], "Current original source is not inspectable")
    sources = diagnostic.get("source_ids", [])
    related = sorted(active)
    if diagnostic.get('stage') == 'DISPOSITION':
        from .disposition import target as disposition_target
        key = diagnostic['target']
        sources = [disposition_target(state, key)[1]['source_id']]
        related = [key]
    for key in diagnostic.get('root_issue_ids', []):
        if key in state['quarantine']:
            related.append(key)
            sources = [state['quarantine'][key]['source_id']]
            break
    return local_issue(diagnostic["code"], sources=sources[:1], targets=related, diagnostic=diagnostic)
