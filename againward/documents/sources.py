"""Hash-bound approved source snapshots; never stages or clears real raw input."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import stat

from againward.core.artifact_store import read_json, transaction, write_json
from againward.core.privacy import (
    assert_source_approved_for_analysis, case_root_for_path, privacy_manifest_path,
)
from againward.core.workflow import fingerprint
from .contracts import DocumentError, DocumentLimits, SourceBatch, SourceDocument, relative_path

MEDIA_TYPES = {
    ".pdf": "application/pdf", ".csv": "text/csv", ".txt": "text/plain",
    ".md": "text/plain", ".eml": "message/rfc822",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
}


def assert_document_action(root: Path, *, mutation: bool = False) -> None:
    """Upstream tools obey the existing STOP, including standalone test cases."""
    from againward.core.client_lifecycle import validate_client_lifecycle_artifacts
    from againward.core.workflow_paths import resolve_analysis_directory
    owner = case_root_for_path(root)
    if owner is not None:
        candidates = [resolve_analysis_directory(owner)]
    else:
        candidates = [p for p in (root, *root.parents) if (p / "investigation_state.json").is_file()]
    if not candidates:
        return
    life = validate_client_lifecycle_artifacts(candidates[0])
    if life and life["state"] == "WAITING_FOR_REQUIRED_INFORMATION":
        raise DocumentError("WAIT_BLOCKED", "STOP: document analysis forbidden during BLOCKING wait")
    if life and mutation and life["state"] in {"FINALIZABLE", "DELIVERABLE"}:
        raise DocumentError("REVIEW_STALE", "New evidence requires the existing resume/privacy workflow")


def safe_file(root: Path, relative: str) -> Path:
    path = root / relative_path(relative)
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise DocumentError("SOURCE_UNSAFE_PATH", "Symlink refused")
    if not path.resolve().is_relative_to(root.resolve()):
        raise DocumentError("SOURCE_UNSAFE_PATH")
    if not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise DocumentError("SOURCE_UNREADABLE", "Regular local file required")
    return path


def privacy_binding(path: Path) -> str | None:
    owner = case_root_for_path(path)
    manifest = privacy_manifest_path(owner) if owner else None
    return fingerprint(manifest) if manifest and manifest.is_file() else None


def approved_source_hashes(path: Path) -> set[str] | None:
    owner = case_root_for_path(path)
    manifest = privacy_manifest_path(owner) if owner else None
    if manifest is None or not manifest.is_file():
        return None
    payload = read_json(manifest)
    return {row["sanitized_sha256"] for row in payload.get("files", [])
            if row.get("sanitized_sha256") is not None}


def inventory_sources(source_root: Path, output: Path, *, purpose: str = "INITIAL",
                      previous: SourceBatch | None = None,
                      limits: DocumentLimits = DocumentLimits()) -> SourceBatch:
    """Snapshot a complete folder after clearance. Exact duplicate bytes share one ID.

    Files are never silently skipped. Existing blobs are verified, never replaced.
    A new batch does not reset lifecycle or query budgets and grants no clearance.
    """
    source_root, output = Path(source_root), Path(output)
    if any(p.is_symlink() for p in (output, *output.parents)):
        raise DocumentError("SOURCE_UNSAFE_PATH", "Output symlink refused")
    assert_source_approved_for_analysis(source_root, output_directory=output)
    assert_document_action(output, mutation=True)
    if not source_root.is_dir() or any(p.is_symlink() for p in (source_root, *source_root.parents)):
        raise DocumentError("SOURCE_UNSAFE_PATH")
    if output.resolve().is_relative_to(source_root.resolve()):
        raise DocumentError("SOURCE_UNSAFE_PATH", "Snapshot output cannot be inside input")
    paths = []
    for path in source_root.rglob("*"):
        if path.is_symlink():
            raise DocumentError("SOURCE_UNSAFE_PATH", "Symlink refused")
        if path.is_dir():
            continue
        paths.append(safe_file(source_root, path.relative_to(source_root).as_posix()))
        if len(paths) > limits.maximum_files:
            raise DocumentError("RESOURCE_LIMIT", "File count exceeded")
    if not paths:
        raise DocumentError("SOURCE_UNREADABLE", "Empty source folder")
    if sum(p.stat().st_size for p in paths) > limits.maximum_batch_bytes:
        raise DocumentError("RESOURCE_LIMIT", "Batch bytes exceeded")
    approved_binding = privacy_binding(source_root)
    approved_hashes = approved_source_hashes(source_root)
    bodies: dict[str, bytes] = {}
    aliases: dict[str, list[str]] = {}
    media: dict[str, str] = {}
    # Validate the whole batch before creating any analytical output.
    for path in sorted(paths):
        assert_source_approved_for_analysis(path, output_directory=output)
        if path.stat().st_size > limits.maximum_file_bytes:
            raise DocumentError("RESOURCE_LIMIT", "File bytes exceeded")
        kind = MEDIA_TYPES.get(path.suffix.lower())
        if kind is None:
            raise DocumentError("SOURCE_UNSUPPORTED", path.suffix)
        raw = path.read_bytes()
        if len(raw) > limits.maximum_file_bytes:
            raise DocumentError("RESOURCE_LIMIT", "File grew during ingestion")
        sha = hashlib.sha256(raw).hexdigest()
        if approved_hashes is not None and sha not in approved_hashes:
            raise DocumentError("PRIVACY_NOT_CLEARED", "Source bytes not approved by current manifest")
        if sha in media and media[sha] != kind:
            raise DocumentError("SOURCE_UNSUPPORTED", "Identical bytes declared with conflicting media types")
        bodies[sha], media[sha] = raw, kind
        aliases.setdefault(sha, []).append(path.relative_to(source_root).as_posix())
        if sum(len(v) for v in bodies.values()) > limits.maximum_batch_bytes:
            raise DocumentError("RESOURCE_LIMIT", "Batch grew during ingestion")
    if privacy_binding(source_root) != approved_binding:
        raise DocumentError("PRIVACY_NOT_CLEARED", "Privacy changed during ingestion")
    # Ensure approved bytes, not a later replacement, were read.
    for path in paths:
        assert_source_approved_for_analysis(path, output_directory=output)
        sha = fingerprint(path)
        if path.relative_to(source_root).as_posix() not in aliases.get(sha, []):
            raise DocumentError("SOURCE_CHANGED", "Source changed during ingestion")
    with transaction(output):
        blobs = output / "sources"
        if blobs.is_symlink():
            raise DocumentError("SOURCE_UNSAFE_PATH")
        blobs.mkdir(exist_ok=True)
        documents_by_id = {}
        if previous is not None:
            for doc in previous.documents:
                # Current clearance must include previous bytes too. The old
                # receipt stays immutable; the new receipt binds the union.
                if approved_hashes is not None and doc.sha256 not in approved_hashes:
                    raise DocumentError("PRIVACY_NOT_CLEARED", "Prior source absent from current clearance")
                if fingerprint(safe_file(output, doc.blob_path)) != doc.sha256:
                    raise DocumentError("SOURCE_CHANGED", "Prior source blob changed")
                documents_by_id[doc.source_id] = doc
        for sha, raw in sorted(bodies.items()):
            relative = "sources/" + sha + ".bin"
            path = output / relative
            if path.exists() or path.is_symlink():
                existing = safe_file(output, relative)
                if fingerprint(existing) != sha:
                    raise DocumentError("SOURCE_CHANGED", "Existing immutable blob altered")
            else:
                # Exclusive creation is intentional. An interrupted orphan can be
                # reverified; it never becomes an approved source without a receipt.
                with path.open("xb") as handle:
                    handle.write(raw)
                    handle.flush()
                    import os
                    os.fsync(handle.fileno())
            prior = documents_by_id.get("src-" + sha)
            if prior and prior.media_type != media[sha]:
                raise DocumentError("SOURCE_UNSUPPORTED", "Prior source media type conflict")
            names = tuple(sorted(set(aliases[sha]) | set(prior.original_names if prior else ())))
            documents_by_id["src-" + sha] = SourceDocument("src-" + sha, sha, len(raw), media[sha], relative, names)
        documents = tuple(sorted(documents_by_id.values(), key=lambda d: d.source_id))
        if len(documents) > limits.maximum_files or sum(d.byte_size for d in documents) > limits.maximum_batch_bytes:
            raise DocumentError("RESOURCE_LIMIT", "Cumulative source batch limits exceeded")
        batch = SourceBatch(documents, datetime.now(timezone.utc).isoformat(),
                            approved_binding, purpose, previous.batch_id if previous else None)
        from againward.evidence.hashing import stable_hash
        receipt = output / "batches" / batch.batch_id / (stable_hash(batch.to_dict()) + ".json")
        if not receipt.exists():
            write_json(receipt, batch.to_dict())
    return batch


def verify_batch(batch: SourceBatch, root: Path, *, limits: DocumentLimits = DocumentLimits()) -> None:
    assert_source_approved_for_analysis(root, output_directory=root)
    assert_document_action(root)
    if privacy_binding(root) != batch.privacy_manifest_sha256:
        raise DocumentError("PRIVACY_NOT_CLEARED", "Batch privacy binding is stale")
    approved_hashes = approved_source_hashes(root)
    if len(batch.documents) > limits.maximum_files or sum(d.byte_size for d in batch.documents) > limits.maximum_batch_bytes:
        raise DocumentError("RESOURCE_LIMIT", "Batch limits exceeded")
    for document in batch.documents:
        if approved_hashes is not None and document.sha256 not in approved_hashes:
            raise DocumentError("PRIVACY_NOT_CLEARED", "Snapshot source was never approved")
        path = safe_file(root, document.blob_path)
        if path.stat().st_size > limits.maximum_file_bytes:
            raise DocumentError("RESOURCE_LIMIT", "File bytes exceeded")
        if path.stat().st_size != document.byte_size or fingerprint(path) != document.sha256:
            raise DocumentError("SOURCE_CHANGED", document.source_id)
