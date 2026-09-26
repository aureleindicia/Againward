"""Explicit source-local assembly of unapproved observations.

No union, field value, provenance or authority is inferred. Every input candidate
needs a model disposition; a new proposal requires fresh QA/adjudication/review.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from againward.evidence.hashing import stable_hash
from .contracts import DocumentError, SourceBatch, identifier, digest, load_json
from againward.core.artifact_store import write_json, transaction
from .extraction import DocumentExtraction, replay_extraction

ASSEMBLY_VERSION = "againward-explicit-assembly-v1"


def _build_assembly(primary: DocumentExtraction, challenger: DocumentExtraction,
                          dispositions: list[dict[str, Any]], batch: SourceBatch,
                          root: Path) -> DocumentExtraction:
    if any(item.extractor_version == ASSEMBLY_VERSION or item.assembly_receipt_sha256 is not None
           for item in (primary, challenger)):
        raise DocumentError("EXTRACTION_INCOMPLETE", "Only one assembly round is permitted")
    parents = tuple(replay_extraction(item.to_dict(), batch, root) for item in (primary, challenger))
    if parents[0].source_id != parents[1].source_id:
        raise DocumentError("SOURCE_CHANGED", "Assembly parents must share the same current source")
    expected = {(item.to_dict()["extraction_sha256"], c.candidate_id): c
                for item in parents for c in item.candidates}
    if not isinstance(dispositions, list) or len(dispositions) != len(expected):
        raise DocumentError("EXTRACTION_INCOMPLETE", "Every parent observation needs one disposition",
                            diagnostic={"validation_code": "ASSEMBLY_COVERAGE_INCOMPLETE",
                                        "schema_path": "$.candidate_selections",
                                        "error_category": "DECISION_COVERAGE", "source_id": primary.source_id})
    seen: set[tuple[str, str]] = set()
    selected = []
    for row in dispositions:
        if not isinstance(row, dict) or set(row) != {"extraction_sha256", "candidate_id", "decision", "entity_id"}:
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Closed assembly disposition required")
        key = (row["extraction_sha256"], row["candidate_id"])
        if not all(isinstance(value, str) for value in row.values()) or key not in expected or key in seen:
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown or repeated assembly input")
        seen.add(key)
        if row["decision"] == "REJECT":
            if row["entity_id"]:
                raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Rejected observation cannot target an entity")
            continue
        if row["decision"] != "INCLUDE":
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Explicit INCLUDE or REJECT required")
        group = identifier(row["entity_id"])
        candidate = expected[key]
        identity = {"source": primary.source_id, "parents": sorted(h for h, _ in expected),
                    "dispositions": sorted(dispositions, key=lambda row: (row["extraction_sha256"], row["candidate_id"])),
                    "input": key, "group": group}
        selected.append(replace(candidate, entity_id=group, candidate_id="assembled-" + stable_hash(identity)))
    if seen != set(expected) or not selected:
        raise DocumentError("EXTRACTION_INCOMPLETE", "Every parent observation needs an explicit disposition",
                            diagnostic={"validation_code": "ASSEMBLY_COVERAGE_INCOMPLETE",
                                        "schema_path": "$.candidate_selections",
                                        "error_category": "DECISION_COVERAGE", "source_id": primary.source_id})
    receipt_hash = stable_hash({"schema_version": ASSEMBLY_VERSION,
        "primary": primary.to_dict(), "challenger": challenger.to_dict(), "dispositions": dispositions})
    result = replace(primary, extractor_version=ASSEMBLY_VERSION, status="NEEDS_REVIEW",
                     assembly_receipt_sha256=receipt_hash,
                     candidates=tuple(sorted(selected, key=lambda c: c.candidate_id)),
                     limitations=tuple(sorted(set(primary.limitations) | set(challenger.limitations))))
    return result


def assemble_observations(primary: DocumentExtraction, challenger: DocumentExtraction,
                          dispositions: list[dict[str, Any]], batch: SourceBatch,
                          root: Path) -> DocumentExtraction:
    result = _build_assembly(primary, challenger, dispositions, batch, root)
    receipt = {"schema_version": ASSEMBLY_VERSION, "primary": primary.to_dict(),
               "challenger": challenger.to_dict(), "dispositions": dispositions}
    path = root / "assemblies" / (str(result.assembly_receipt_sha256) + ".json")
    with transaction(root):
        if path.exists():
            if load_json(path.read_bytes()) != receipt:
                raise DocumentError("REVIEW_STALE", "Assembly receipt changed")
        else:
            write_json(path, receipt)
    return replay_extraction(result.to_dict(), batch, root)


def verify_assembly_extraction(extraction: DocumentExtraction, batch: SourceBatch, root: Path) -> None:
    """Package replay must verify parent lineage, not just the assembled values."""
    if extraction.extractor_version != ASSEMBLY_VERSION:
        raise DocumentError("REVIEW_STALE", "Assembly binding on a non-assembly extraction")
    receipt_hash = digest(extraction.assembly_receipt_sha256)
    path = root / "assemblies" / (receipt_hash + ".json")
    if (not path.is_file() or path.is_symlink()
            or not path.resolve().is_relative_to(root.resolve())):
        raise DocumentError("REVIEW_STALE", "Assembly lineage receipt unavailable")
    receipt = load_json(path.read_bytes())
    if (stable_hash(receipt) != receipt_hash or set(receipt) != {
            "schema_version", "primary", "challenger", "dispositions"}
            or receipt["schema_version"] != ASSEMBLY_VERSION):
        raise DocumentError("REVIEW_STALE", "Assembly lineage hash mismatch")
    parents = []
    for key in ("primary", "challenger"):
        payload = receipt[key]
        if (not isinstance(payload, dict) or payload.get("extractor_version") == ASSEMBLY_VERSION
                or payload.get("assembly_receipt_sha256") is not None):
            raise DocumentError("REVIEW_STALE", "Recursive assembly lineage refused")
        parents.append(replay_extraction(payload, batch, root))
    expected = _build_assembly(parents[0], parents[1], receipt["dispositions"], batch, root)
    if expected.to_dict() != extraction.to_dict():
        raise DocumentError("REVIEW_STALE", "Assembled candidates differ from explicit parent dispositions")
