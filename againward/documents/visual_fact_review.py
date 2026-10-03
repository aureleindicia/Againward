"""Source-bound visual receipts for model review and exceptional human fallback.

The operator's local identity is a claim, not cryptographic authentication.
Scripted tests exercise the protocol but never count as a real inspection.
MODEL receipts bind independent source QA, visual review and rendered pixels;
they are probabilistic evidence, not HUMAN attestations or accuracy proof.
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

from againward.core.artifact_store import read_json
from againward.evidence.hashing import stable_hash
from .codex_provider import _images
from .contracts import DocumentError, SourceBatch, closed, digest, text, timestamp
from .readers import read_document


_ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,63}")
_ATTESTATION_KEYS = {"source_sha256", "location", "unit_sha256", "preview_sha256",
                     "candidate_hashes", "reviewer_role", "reviewer_id", "reviewed_at_utc", "decision"}
MODEL_VISUAL_VERSION = "againward-visual-model-evidence-v2-300dpi"


def _selection_is_qa_bound(source_id: str, selected_sha: str, qa_row: dict,
                           adjudication: dict, extractions: tuple[Any, ...]) -> bool:
    if selected_sha in {qa_row["primary_extraction_sha256"], qa_row["challenger_extraction_sha256"]}:
        return True
    extension = adjudication.get("adjudicator_extractions", {}).get(source_id)
    extraction = next((item for item in extractions if item.source_id == source_id
                       and item.to_dict()["extraction_sha256"] == selected_sha), None)
    if not isinstance(extension, dict) or extraction is None:
        return False
    candidate_hashes = sorted(stable_hash(candidate.to_dict()) for candidate in extraction.candidates
                              if {"ADJUDICATOR_PIXEL_OBSERVATION", "ADJUDICATOR_NATIVE_OBSERVATION"}
                              & set(candidate.ambiguity_flags))
    native_observed = [observation for decision in adjudication.get("decisions", [])
                       if decision.get("source_id") == source_id
                       for observation in decision.get("native_observations", [])]
    native_candidates = [candidate for candidate in extraction.candidates
                         if "ADJUDICATOR_NATIVE_OBSERVATION" in candidate.ambiguity_flags]
    native_bound = len(native_observed) == len(native_candidates) and all(any(
        candidate.source_id == observation.get("source_id") == source_id
        and candidate.location == observation.get("location")
        and candidate.unit_sha256 == observation.get("unit_sha256")
        and candidate.semantic_type == observation.get("semantic_type")
        and candidate.value_type == observation.get("value_type")
        and candidate.value == observation.get("value")
        and candidate.raw_observed_value == observation.get("raw_observed_value")
        and candidate.source_span is not None
        and list(candidate.source_span) == observation.get("source_span")
        for observation in native_observed) for candidate in native_candidates)
    base_hashes = {qa_row["primary_extraction_sha256"], qa_row["challenger_extraction_sha256"]}
    observed = [observation for decision in adjudication.get("decisions", [])
                if decision.get("source_id") == source_id
                for observation in decision.get("pixel_observations", [])]
    candidates = [candidate for candidate in extraction.candidates
                  if "ADJUDICATOR_PIXEL_OBSERVATION" in candidate.ambiguity_flags]
    bound_match = all(any(
        candidate.location == observation.get("location")
        and candidate.semantic_type == observation.get("semantic_type")
        and candidate.value_type == observation.get("value_type")
        and candidate.value == observation.get("value")
        and candidate.raw_observed_value == observation.get("visible_text")
        and observation.get("source_id") == source_id
        and observation.get("source_sha256") == extraction.source_sha256
        and observation.get("adjudicator_model") == adjudication.get("model")
        and observation.get("adjudication_version") == adjudication.get("schema_version")
        and observation.get("origin") == "ADJUDICATOR_PIXEL_OBSERVATION"
        for observation in observed) for candidate in candidates)
    return (extension.get("extraction_sha256") == selected_sha
            and extension.get("base_extraction_sha256") in base_hashes
            and extension.get("candidate_hashes") == candidate_hashes and bool(candidate_hashes)
            and len(observed) + len(native_observed) == len(candidate_hashes) and bound_match and native_bound
            and all(candidate.source_span is None
                    and "ADJUDICATOR_PIXEL_OBSERVATION" in candidate.ambiguity_flags
                    and "VISUAL_TRANSCRIPTION_UNVERIFIED" in candidate.ambiguity_flags
                    for candidate in extraction.candidates
                    if "ADJUDICATOR_PIXEL_OBSERVATION" in candidate.ambiguity_flags))


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
    if review.get("reviewer_role") not in {"ANALYST", "HUMAN"} or review.get("visual_attestations"):
        raise DocumentError("REVIEW_STALE", "Expected an unattested source-fact review")
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
    confirmed = {candidate.candidate_id: candidate
                 for candidates in groups.values() for candidate in candidates}
    for decision in revised["decisions"]:
        candidate = confirmed.get(decision.get("candidate_id"))
        if candidate is not None:
            decision["resolved_flags"] = sorted(set(decision["resolved_flags"]) |
                                                set(candidate.ambiguity_flags))
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


def record_model_visual_review(batch: SourceBatch, extractions: tuple[Any, ...],
                               visual: dict, qa: dict, adjudication: dict,
                               root: Path, *, model: str) -> dict:
    """Issue a MODEL (never HUMAN) receipt after source QA and pixel review."""
    if (visual.get("status") != "WAITING_FOR_VISUAL_ATTESTATION"
            or visual.get("receipt_sha256") != stable_hash({k: v for k, v in visual.items()
                                                            if k != "receipt_sha256"})
            or visual.get("batch_id") != batch.batch_id):
        raise DocumentError("REVIEW_STALE", "Current pixel analyst review required")
    review = json.loads(json.dumps(visual["review"]))
    decisions = {row["candidate_id"]: row for row in review["decisions"]}
    groups = _accepted_visual_groups(extractions, review)
    if not groups or any(decisions[c.candidate_id]["decision"] != "ACCEPT"
                         for extraction in extractions for c in extraction.candidates
                         if "VISUAL_TRANSCRIPTION_UNVERIFIED" in c.ambiguity_flags):
        raise DocumentError("HUMAN_REVIEW_REQUIRED", "Unresolved pixel facts cannot receive model approval")
    if (qa.get("qa_sha256") != stable_hash({k: v for k, v in qa.items() if k != "qa_sha256"})
            or adjudication.get("adjudication_sha256") != stable_hash(
                {k: v for k, v in adjudication.items() if k != "adjudication_sha256"})
            or qa.get("batch_id") != batch.batch_id or adjudication.get("batch_id") != batch.batch_id
            or adjudication.get("qa_sha256") != qa["qa_sha256"]
            or adjudication.get("material_unresolved_source_ids")):
        raise DocumentError("REVIEW_STALE", "Source QA/adjudication does not support model visual review")
    selected = {item.source_id: item.to_dict()["extraction_sha256"] for item in extractions}
    if adjudication.get("selected_extractions") != selected:
        raise DocumentError("REVIEW_STALE", "Selected visual proposal changed")
    by_hash = {document.sha256: document for document in batch.documents}
    source_by_sha = {document.sha256: document.source_id for document in batch.documents}
    qa_by_source = {row["source_id"]: row for row in qa["source_results"]}
    decisions_by_source = {row["source_id"]: row for row in adjudication["decisions"]}
    rows = []
    with tempfile.TemporaryDirectory(prefix="againward-model-visual-") as directory:
        for source_sha, location in sorted(groups):
            document = by_hash[source_sha]
            source_id = source_by_sha[source_sha]
            qa_row = qa_by_source[source_id]
            if not _selection_is_qa_bound(source_id, selected[source_id], qa_row,
                                          adjudication, extractions):
                raise DocumentError("REVIEW_STALE", "Visual selection is not an independently read proposal")
            if qa_row["material_needs_reconciliation"] and not any(
                    cite.get("source_id") == source_id and cite.get("location") == location
                    and "preview_sha256" in cite
                    for cite in decisions_by_source.get(source_id, {}).get("citations", [])):
                raise DocumentError("HUMAN_REVIEW_REQUIRED", "Disputed pixels were not reopened in adjudication")
            preview, _, unit = _render_hash(document, root, location, Path(directory))
            rows.append({"schema_version": MODEL_VISUAL_VERSION,
                         "source_id": source_id, "source_sha256": source_sha,
                         "location": location, "unit_sha256": unit, "preview_sha256": preview,
                         "render_version": "againward-poppler-png-300dpi-v1" if document.media_type == "application/pdf" else "original-image-v1",
                         "render_dpi": 300 if document.media_type == "application/pdf" else None,
                         "candidate_hashes": sorted(stable_hash(c.to_dict()) for c in groups[(source_sha, location)]),
                         "reviewer_role": "MODEL", "model": model,
                         "visual_receipt_sha256": visual["receipt_sha256"],
                         "qa_sha256": qa["qa_sha256"],
                         "adjudication_sha256": adjudication["adjudication_sha256"],
                         "decision": "SUPPORTED_FOR_FACT_REVIEW"})
    for extraction in extractions:
        for candidate in extraction.candidates:
            if candidate.source_span is None and decisions[candidate.candidate_id]["decision"] == "ACCEPT":
                decisions[candidate.candidate_id]["resolved_flags"] = list(candidate.ambiguity_flags)
    review["visual_model_reviews"] = rows
    verify_model_visual_reviews(batch, extractions, review, root)
    return review


def verify_model_visual_reviews(batch: SourceBatch, extractions: tuple[Any, ...],
                                review: dict, root: Path) -> None:
    """Replay persisted model/QA receipts and exact pixels; a role flag alone proves nothing."""
    groups = _accepted_visual_groups(extractions, review)
    rows = review.get("visual_model_reviews", [])
    if not isinstance(rows, list) or len(rows) != len(groups):
        raise DocumentError("HUMAN_REVIEW_REQUIRED", "Every accepted pixel group needs a model receipt")
    by_source = {document.source_id: document for document in batch.documents}
    selected = {item.source_id: item.to_dict()["extraction_sha256"] for item in extractions}
    seen = set()
    with tempfile.TemporaryDirectory(prefix="againward-model-visual-verify-") as directory:
        for row in rows:
            if not isinstance(row, dict) or set(row) != {
                    "schema_version", "source_id", "source_sha256", "location", "unit_sha256",
                    "preview_sha256", "render_version", "render_dpi", "candidate_hashes", "reviewer_role", "model",
                    "visual_receipt_sha256", "qa_sha256", "adjudication_sha256", "decision"}:
                raise DocumentError("REVIEW_STALE", "Model visual receipt fields invalid")
            document = by_source.get(row["source_id"])
            key = (row["source_sha256"], row["location"])
            if (document is None or document.sha256 != row["source_sha256"] or key not in groups or key in seen
                    or row["schema_version"] != MODEL_VISUAL_VERSION or row["reviewer_role"] != "MODEL"
                    or row["decision"] != "SUPPORTED_FOR_FACT_REVIEW"
                    or row["render_version"] != ("againward-poppler-png-300dpi-v1" if document.media_type == "application/pdf" else "original-image-v1")
                    or row["render_dpi"] != (300 if document.media_type == "application/pdf" else None)):
                raise DocumentError("REVIEW_STALE", "Model visual receipt does not match current component")
            seen.add(key)
            if row["candidate_hashes"] != sorted(stable_hash(c.to_dict()) for c in groups[key]):
                raise DocumentError("REVIEW_STALE", "Visual candidates changed")
            preview, _, unit = _render_hash(document, root, row["location"], Path(directory))
            if preview != row["preview_sha256"] or unit != row["unit_sha256"]:
                raise DocumentError("REVIEW_STALE", "Visual pixels changed")
            receipts = []
            for folder, digest_key, field in (("analyst_reviews", "receipt_sha256", "visual_receipt_sha256"),
                                              ("independent_qa", "qa_sha256", "qa_sha256"),
                                              ("adjudications", "adjudication_sha256", "adjudication_sha256")):
                path = root / folder / (digest(row[field]) + ".json")
                if path.is_symlink() or not path.is_file():
                    raise DocumentError("REVIEW_STALE", "Model visual dependency receipt missing")
                receipt = read_json(path)
                if receipt.get(digest_key) != row[field] or stable_hash(
                        {k: v for k, v in receipt.items() if k != digest_key}) != row[field]:
                    raise DocumentError("REVIEW_STALE", "Model visual dependency receipt changed")
                receipts.append(receipt)
            visual, qa, adjudication = receipts
            if (visual.get("batch_id") != batch.batch_id or visual.get("model", row["model"]) != row["model"]
                    or visual.get("status") != "WAITING_FOR_VISUAL_ATTESTATION"
                    or qa.get("batch_id") != batch.batch_id or adjudication.get("batch_id") != batch.batch_id
                    or adjudication.get("qa_sha256") != qa["qa_sha256"]
                    or adjudication.get("selected_extractions") != selected
                    or adjudication.get("material_unresolved_source_ids")):
                raise DocumentError("REVIEW_STALE", "Model visual dependencies changed")
            reviewed = {item["candidate_id"]: item for item in visual["review"]["decisions"]}
            for candidate in groups[key]:
                current = next(item for item in review["decisions"] if item["candidate_id"] == candidate.candidate_id)
                prior = reviewed.get(candidate.candidate_id)
                if (prior is None or prior["decision"] != "ACCEPT"
                        or {k: v for k, v in current.items() if k != "resolved_flags"} !=
                           {k: v for k, v in prior.items() if k != "resolved_flags"}):
                    raise DocumentError("REVIEW_STALE", "Visual model decision changed after pixel review")
            qa_row = next(item for item in qa["source_results"] if item["source_id"] == row["source_id"])
            if not _selection_is_qa_bound(row["source_id"], selected[row["source_id"]], qa_row,
                                          adjudication, extractions):
                raise DocumentError("REVIEW_STALE", "Visual proposal is outside independent source QA")
            if qa_row["material_needs_reconciliation"] and not any(
                    cite.get("source_id") == row["source_id"] and cite.get("location") == row["location"]
                    and cite.get("preview_sha256") == preview
                    for decision in adjudication["decisions"] for cite in decision["citations"]):
                raise DocumentError("REVIEW_STALE", "Material visual dispute lacks pixel adjudication")
            if qa_row["material_needs_reconciliation"]:
                from .adjudication import verify_adjudication_pixels
                verify_adjudication_pixels(batch, adjudication, root)
