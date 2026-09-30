"""Reconcile source-local observations without granting them fact authority.

Proposal-level assembly uses explicit dispositions. Complementary reads may be
united deterministically only when exact source bindings and canonical anchors
prove scope and identity. Either result stays unapproved and requires ordinary
QA, adjudication where needed, and fact review.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from againward.evidence.hashing import stable_hash
from .contracts import DocumentError, SourceBatch, identifier, digest, load_json
from againward.core.artifact_store import write_json, transaction
from .extraction import (DocumentExtraction, replay_extraction, append_adjudicator_native_observations,
                         append_adjudicator_visual_observations)

ASSEMBLY_VERSION = "againward-explicit-assembly-v3-source-recovery"
FACT_RECONCILIATION_VERSION = "againward-deterministic-fact-reconciliation-v1"


def complete_fact_superset(primary: DocumentExtraction, challenger: DocumentExtraction,
                           batch: SourceBatch, root: Path) -> tuple[DocumentExtraction, str] | None:
    """Select a complete read only when it contains the other's full canonical evidence set.

    This is narrower than fact union: it applies when one current, source-bound
    proposal is a strict semantic superset of the other, has no contradiction
    or unresolved scope, and independently passes selected-proposal
    completeness. The smaller read contributes no unique fact that would be
    lost. Selection remains unapproved and normal fact review still follows.
    """
    if (primary.source_id != challenger.source_id or primary.source_sha256 != challenger.source_sha256
            or primary.status == "FAILED" or challenger.status == "FAILED"
            or primary.limitations or challenger.limitations):
        return None
    primary = replay_extraction(primary.to_dict(), batch, root)
    challenger = replay_extraction(challenger.to_dict(), batch, root)
    from .independent_qa import _canonical_observations, _observation_comparison, _observation_key
    from againward.domains.rental.extraction_validation import (occurrence_kind_overrides,
        validate_rental_extraction)

    first = _canonical_observations(primary,
        entity_kind_overrides=occurrence_kind_overrides(primary, (challenger,)))
    second = _canonical_observations(challenger,
        entity_kind_overrides=occurrence_kind_overrides(challenger, (primary,)))
    if (any(row["scope"] == "UNKNOWN" and row["material"] for row in (*first, *second))
            or any(row["anchor"] is None and row["material"]
                   and row["scope"] != "SOURCE_METADATA" for row in (*first, *second))):
        return None
    comparison = _observation_comparison(first, second)
    if comparison["conflicting_fields"] or comparison["unknown_fields"]:
        return None
    first_keys = {_observation_key(row) for row in first}
    second_keys = {_observation_key(row) for row in second}
    if first_keys > second_keys:
        options = ((primary, "PRIMARY"),)
    elif second_keys > first_keys:
        options = ((challenger, "CHALLENGER"),)
    else:
        return None
    for candidate, selection in options:
        try:
            validate_rental_extraction(candidate, require_package_facts=True)
        except DocumentError:
            return None
        # A selection receipt must cite the same current original source. All
        # candidates were already replay-validated, so the caller can bind one
        # exact citation when producing the deterministic decision record.
        return candidate, selection
    return None


def _build_assembly(primary: DocumentExtraction, challenger: DocumentExtraction,
                          dispositions: list[dict[str, Any]], batch: SourceBatch,
                          root: Path, *, native_observations: list[dict[str, Any]] | None = None,
                          pixel_observations: list[dict[str, Any]] | None = None,
                          output_version: str = ASSEMBLY_VERSION) -> DocumentExtraction:
    if output_version not in {ASSEMBLY_VERSION, FACT_RECONCILIATION_VERSION}:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown reconciliation output version")
    if any(item.extractor_version in {ASSEMBLY_VERSION, FACT_RECONCILIATION_VERSION}
           or item.assembly_receipt_sha256 is not None
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
        if row["decision"] in {"REJECT", "DEFER"}:
            if row["entity_id"]:
                raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Rejected observation cannot target an entity")
            continue
        if row["decision"] != "INCLUDE":
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Explicit INCLUDE, REJECT or DEFER required")
        group = identifier(row["entity_id"])
        candidate = expected[key]
        identity = {"source": primary.source_id, "parents": sorted(h for h, _ in expected),
                    "dispositions": sorted(dispositions, key=lambda row: (row["extraction_sha256"], row["candidate_id"])),
                    "input": key, "group": group}
        selected.append(replace(candidate, entity_id=group, candidate_id="assembled-" + stable_hash(identity)))
    if seen != set(expected) or not (selected or native_observations or pixel_observations):
        raise DocumentError("EXTRACTION_INCOMPLETE", "Every parent observation needs an explicit disposition",
                            diagnostic={"validation_code": "ASSEMBLY_COVERAGE_INCOMPLETE",
                                        "schema_path": "$.candidate_selections",
                                        "error_category": "DECISION_COVERAGE", "source_id": primary.source_id})
    receipt_body = {"schema_version": ASSEMBLY_VERSION,
        "primary": primary.to_dict(), "challenger": challenger.to_dict(), "dispositions": dispositions,
        "native_observations": native_observations or [], "pixel_observations": pixel_observations or []}
    if output_version != ASSEMBLY_VERSION:
        receipt_body["output_version"] = output_version
    receipt_hash = stable_hash(receipt_body)
    result = replace(primary, extractor_version=output_version, status="NEEDS_REVIEW",
                     assembly_receipt_sha256=receipt_hash,
                     candidates=tuple(sorted(selected, key=lambda c: c.candidate_id)),
                     limitations=tuple(sorted(set(primary.limitations) | set(challenger.limitations))))
    if pixel_observations:
        result = append_adjudicator_visual_observations(result, pixel_observations, batch, root, receipt_hash)
    if native_observations:
        result = append_adjudicator_native_observations(result, native_observations, batch, root, receipt_hash)
    # A fact union can place facts for one proven occurrence in separate
    # runtime groups when one reader omitted its entity_kind. Rebuild those
    # groups from explicit same-source anchors before the fresh QA/replay.
    from againward.domains.rental.extraction_validation import reconstruct_runtime_structure
    return reconstruct_runtime_structure(result)


def assemble_observations(primary: DocumentExtraction, challenger: DocumentExtraction,
                          dispositions: list[dict[str, Any]], batch: SourceBatch,
                          root: Path, *, native_observations: list[dict[str, Any]] | None = None,
                          pixel_observations: list[dict[str, Any]] | None = None,
                          output_version: str = ASSEMBLY_VERSION) -> DocumentExtraction:
    result = _build_assembly(primary, challenger, dispositions, batch, root,
                             native_observations=native_observations, pixel_observations=pixel_observations,
                             output_version=output_version)
    receipt = {"schema_version": ASSEMBLY_VERSION, "primary": primary.to_dict(),
               "challenger": challenger.to_dict(), "dispositions": dispositions,
               "native_observations": native_observations or [], "pixel_observations": pixel_observations or []}
    if output_version != ASSEMBLY_VERSION:
        receipt["output_version"] = output_version
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
    if extraction.extractor_version not in {ASSEMBLY_VERSION, FACT_RECONCILIATION_VERSION}:
        raise DocumentError("REVIEW_STALE", "Assembly binding on a non-assembly extraction")
    receipt_hash = digest(extraction.assembly_receipt_sha256)
    path = root / "assemblies" / (receipt_hash + ".json")
    if (not path.is_file() or path.is_symlink()
            or not path.resolve().is_relative_to(root.resolve())):
        raise DocumentError("REVIEW_STALE", "Assembly lineage receipt unavailable")
    receipt = load_json(path.read_bytes())
    allowed = {"schema_version", "primary", "challenger", "dispositions", "native_observations", "pixel_observations"}
    if "output_version" in receipt:
        allowed.add("output_version")
    output_version = receipt.get("output_version", ASSEMBLY_VERSION)
    if (stable_hash(receipt) != receipt_hash or set(receipt) != allowed
            or receipt["schema_version"] != ASSEMBLY_VERSION
            or output_version != extraction.extractor_version):
        raise DocumentError("REVIEW_STALE", "Assembly lineage hash mismatch")
    parents = []
    for key in ("primary", "challenger"):
        payload = receipt[key]
        if (not isinstance(payload, dict) or payload.get("extractor_version") == ASSEMBLY_VERSION
                or payload.get("assembly_receipt_sha256") is not None):
            raise DocumentError("REVIEW_STALE", "Recursive assembly lineage refused")
        parents.append(replay_extraction(payload, batch, root))
    expected = _build_assembly(parents[0], parents[1], receipt["dispositions"], batch, root,
        native_observations=receipt["native_observations"], pixel_observations=receipt["pixel_observations"],
        output_version=output_version)
    if expected.to_dict() != extraction.to_dict():
        raise DocumentError("REVIEW_STALE", "Assembled candidates differ from explicit parent dispositions")


def reconcile_complementary_facts(primary: DocumentExtraction, challenger: DocumentExtraction,
                                 batch: SourceBatch, root: Path) -> DocumentExtraction | None:
    """Union only unambiguous source-local facts with a deterministic identity anchor.

    Model-local entity labels are never used as identity. Complementary facts
    without a source-bound canonical scope/anchor remain unresolved for the
    ordinary adjudication path. Equivalent observations retain one selected
    citation while both immutable parent extractions remain in the lineage.
    """
    if (primary.source_id != challenger.source_id or primary.source_sha256 != challenger.source_sha256
            or primary.status == "FAILED" or challenger.status == "FAILED"
            or primary.limitations or challenger.limitations):
        return None
    from .independent_qa import _canonical_observations
    from againward.domains.rental.extraction_validation import occurrence_kind_overrides

    primary_hash = primary.to_dict()["extraction_sha256"]
    challenger_hash = challenger.to_dict()["extraction_sha256"]
    if primary_hash == challenger_hash:
        return None
    extraction_hashes = {primary_hash: primary, challenger_hash: challenger}
    observations = {
        primary_hash: _canonical_observations(primary,
            entity_kind_overrides=occurrence_kind_overrides(primary, (challenger,))),
        challenger_hash: _canonical_observations(challenger,
            entity_kind_overrides=occurrence_kind_overrides(challenger, (primary,))),
    }
    value_sets: dict[tuple[str, str, str], set[str]] = {}
    for extraction_hash, extraction in extraction_hashes.items():
        rows = observations[extraction_hash]
        if len(rows) != len(extraction.candidates):
            return None
        for candidate, observation in zip(extraction.candidates, rows, strict=True):
            scope, anchor, semantic = (observation["scope"], observation["anchor"],
                                       observation["semantic_type"])
            if scope != "SOURCE_METADATA" and anchor is None and observation["material"]:
                return None
            if not observation["material"] and anchor is None:
                # A structural/document fragment is already retained in each
                # immutable parent receipt. It is not a financial fact and
                # must not create an unanchored entity in the reconciled view.
                continue
            fact_key = (scope, anchor or "", semantic)
            value_hash = stable_hash(observation["value"])
            value_sets.setdefault(fact_key, set()).add(value_hash)
    if any(len(values) > 1 for values in value_sets.values()):
        return None

    parents = ((primary.to_dict()["extraction_sha256"], primary),
               (challenger.to_dict()["extraction_sha256"], challenger))
    dispositions: list[dict[str, Any]] = []
    emitted: set[str] = set()
    for parent_hash, extraction in parents:
        rows = observations[parent_hash]
        for candidate, observation in zip(extraction.candidates, rows, strict=True):
            scope, anchor, semantic = (observation["scope"], observation["anchor"],
                                       observation["semantic_type"])
            if not observation["material"] and anchor is None:
                dispositions.append({"extraction_sha256": parent_hash,
                    "candidate_id": candidate.candidate_id, "decision": "DEFER", "entity_id": ""})
                continue
            value_hash = stable_hash(observation["value"])
            key = scope + "\0" + (anchor or "") + "\0" + semantic
            identity = stable_hash({"fact_key": key, "value": value_hash})
            if identity in emitted:
                decision, entity_id = "DEFER", ""
            else:
                emitted.add(identity)
                group_seed = ("source-metadata" if scope == "SOURCE_METADATA"
                              else scope + "\0" + str(anchor))
                entity_id = "fact-" + stable_hash({"source_id": primary.source_id,
                                                    "scope_anchor": group_seed})[:24]
                decision = "INCLUDE"
            dispositions.append({"extraction_sha256": parent_hash,
                "candidate_id": candidate.candidate_id, "decision": decision,
                "entity_id": entity_id})
    try:
        return assemble_observations(primary, challenger, dispositions, batch, root,
                                     output_version=FACT_RECONCILIATION_VERSION)
    except DocumentError:
        # A safe union is an optimization, never a reason to weaken ordinary
        # validation. Fall back to the explicit source adjudication route.
        return None


def complete_dispositions(primary: DocumentExtraction, challenger: DocumentExtraction,
                          selections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Account for every omitted observation as deferred, never approved/rejected.

    The model requests assembly explicitly. Python records the entire parent
    set; omitted candidates stay visible in lineage and the next independent QA.
    Conflicting selections and unknown references still fail closed.
    """
    expected = {(p.to_dict()["extraction_sha256"], c.candidate_id)
                for p in (primary, challenger) for c in p.candidates}
    seen = set()
    result = []
    for row in selections:
        if not isinstance(row, dict) or set(row) != {"extraction_sha256", "candidate_id", "decision", "entity_id"}:
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Invalid assembly selection")
        if not all(isinstance(value, str) for value in row.values()):
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Assembly references must be strings")
        key = (row["extraction_sha256"], row["candidate_id"])
        if key not in expected or key in seen:
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown or duplicate assembly selection")
        seen.add(key)
        result.append(dict(row))
    result.extend({"extraction_sha256": h, "candidate_id": c, "decision": "DEFER", "entity_id": ""}
                  for h, c in sorted(expected - seen))
    return result
