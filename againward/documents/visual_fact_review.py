"""One short, source-bound human check for visual facts in an analyst review.

The operator's local identity is a claim, not cryptographic authentication.
Scripted tests exercise the protocol but never count as a real inspection.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any, Callable

from againward.evidence.hashing import stable_hash
from .codex_provider import _images
from .contracts import DocumentError, SourceBatch, closed, digest, text, timestamp
from .readers import read_document


_ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,63}")
_ATTESTATION_KEYS = {"source_sha256", "location", "unit_sha256", "preview_sha256",
                     "candidate_hashes", "reviewer_role", "reviewer_id", "reviewed_at_utc", "decision"}


def _accepted_visual_groups(extractions: tuple[Any, ...], review: dict) -> dict[tuple[str, str], list[Any]]:
    decisions = {row.get("candidate_id"): row.get("decision") for row in review.get("decisions", [])
                 if isinstance(row, dict)}
    grouped: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for extraction in extractions:
        for candidate in extraction.candidates:
            if decisions.get(candidate.candidate_id) == "ACCEPT" and "VISUAL_TRANSCRIPTION_UNVERIFIED" in candidate.ambiguity_flags:
                grouped[(extraction.source_sha256, candidate.location)].append(candidate)
    return dict(grouped)


def _render_hash(document: Any, root: Path, location: str, temp: Path) -> tuple[str, Path, str]:
    parsed = read_document(document, root)
    visual_units = [unit for unit in parsed.units if unit.route != "NATIVE"]
    if location not in {unit.location for unit in visual_units}:
        raise DocumentError("SOURCE_LOCATION_INVALID", "Visual review location changed")
    images = _images(document, parsed, root, temp)
    image_by_location = {unit.location: image for unit, image in zip(visual_units, images)}
    image = image_by_location[location]
    unit = next(unit for unit in visual_units if unit.location == location)
    return hashlib.sha256(image.read_bytes()).hexdigest(), image, unit.unit_sha256


def attest_visual_facts(batch: SourceBatch, extractions: tuple[Any, ...], review: dict,
                        root: Path, *, actor_id: str, ask: Callable[[str], str],
                        interactive: bool) -> dict:
    """Return a NEW review; only an actual TTY CLI may set interactive=True."""
    if not interactive:
        raise DocumentError("HUMAN_REVIEW_REQUIRED", "Interactive original-pixel inspection required")
    if not _ACTOR.fullmatch(actor_id):
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Bounded local operator ID required")
    if review.get("reviewer_role") != "ANALYST" or review.get("visual_attestations"):
        raise DocumentError("REVIEW_STALE", "Expected an unattested analyst review")
    expected_hashes = sorted(extraction.to_dict()["extraction_sha256"] for extraction in extractions)
    if review.get("extraction_hashes") != expected_hashes:
        raise DocumentError("REVIEW_STALE", "Fact review no longer matches source extractions")
    groups = _accepted_visual_groups(extractions, review)
    if not groups:
        raise DocumentError("HUMAN_REVIEW_REQUIRED", "No accepted visual fact requires attestation")
    by_hash = {document.sha256: document for document in batch.documents}
    attestations = []
    with tempfile.TemporaryDirectory(prefix="againward-visual-facts-") as directory:
        for source_sha, location in sorted(groups):
            document = by_hash.get(source_sha)
            if document is None:
                raise DocumentError("SOURCE_CHANGED", "Visual source absent from batch")
            preview_hash, preview, unit_sha = _render_hash(document, root, location, Path(directory))
            candidates = groups[(source_sha, location)]
            print(f"Inspect original source {source_sha}, {location}: {preview}")
            for candidate in candidates:
                print(f"  {candidate.semantic_type} = {candidate.value!r}; visual quote = {candidate.raw_observed_value!r}")
            if ask(f"Open the preview and inspect every listed fact. Type INSPECTED {source_sha[:12]}: ").strip() != f"INSPECTED {source_sha[:12]}":
                raise DocumentError("HUMAN_REVIEW_REQUIRED", "Original visual source not inspected")
            candidate_hashes = sorted(stable_hash(candidate.to_dict()) for candidate in candidates)
            challenge = stable_hash({"source": source_sha, "location": location,
                                     "preview": preview_hash, "candidates": candidate_hashes})[:12]
            if ask(f"Confirm ALL listed facts against pixels? Type CONFIRM {challenge}: ").strip() != f"CONFIRM {challenge}":
                raise DocumentError("HUMAN_REVIEW_REQUIRED", "Visual facts not confirmed")
            attestations.append({"source_sha256": source_sha, "location": location,
                                 "unit_sha256": unit_sha, "preview_sha256": preview_hash,
                                 "candidate_hashes": candidate_hashes, "reviewer_role": "HUMAN",
                                 "reviewer_id": actor_id,
                                 "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
                                 "decision": "CONFIRMED"})
    revised = json.loads(json.dumps(review))
    revised["visual_attestations"] = attestations
    return revised


def verify_visual_attestations(batch: SourceBatch, extractions: tuple[Any, ...],
                               review: dict, root: Path) -> None:
    """Require exact candidate and rendered-pixel binding, not a free HUMAN flag."""
    groups = _accepted_visual_groups(extractions, review)
    attestations = review.get("visual_attestations", [])
    if not isinstance(attestations, list) or len(attestations) != len(groups):
        raise DocumentError("HUMAN_REVIEW_REQUIRED", "Every accepted visual component needs one attestation")
    by_hash = {document.sha256: document for document in batch.documents}
    seen = set()
    with tempfile.TemporaryDirectory(prefix="againward-visual-verify-") as directory:
        for entry in attestations:
            row = closed(entry, _ATTESTATION_KEYS)
            key = (digest(row["source_sha256"]), text(row["location"], maximum=160))
            if key not in groups or key in seen or row["reviewer_role"] != "HUMAN" or row["decision"] != "CONFIRMED":
                raise DocumentError("HUMAN_REVIEW_REQUIRED", "Visual attestation does not match accepted component")
            seen.add(key)
            if not isinstance(row["reviewer_id"], str) or not _ACTOR.fullmatch(row["reviewer_id"]):
                raise DocumentError("HUMAN_REVIEW_REQUIRED", "Visual operator ID missing")
            timestamp(row["reviewed_at_utc"])
            expected_candidates = sorted(stable_hash(candidate.to_dict()) for candidate in groups[key])
            if row["candidate_hashes"] != expected_candidates:
                raise DocumentError("REVIEW_STALE", "Visual fact set changed after inspection")
            preview_hash, _, unit_sha = _render_hash(by_hash[key[0]], root, key[1], Path(directory))
            if row["unit_sha256"] != unit_sha or row["preview_sha256"] != preview_hash:
                raise DocumentError("REVIEW_STALE", "Visual preview changed after inspection")
