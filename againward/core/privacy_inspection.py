"""Pre-clearance document inspection. This extracts only privacy-relevant text/routes.

It deliberately calls the same bounded PDF/DOCX primitives as the source reader,
without invoking its post-clearance business entrypoint. No extracted text is
serialized in a privacy receipt. Visual content requires a source-bound review.
"""
from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
import hashlib
from pathlib import Path

from againward.documents.contracts import DocumentError, DocumentLimits

INSPECTION_VERSION = "againward-privacy-inspection-v1"


def _digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass(frozen=True)
class PrivacyInspection:
    source_sha256: str
    native_text: str
    native_units: int
    visual_components: tuple[str, ...]
    limitations: tuple[str, ...]
    inspection_mode: str
    reader_version: str

    def audit(self) -> dict:
        return {"source_sha256": self.source_sha256,
                "inspection_version": INSPECTION_VERSION,
                "reader_version": self.reader_version,
                "inspection_mode": self.inspection_mode,
                "native_units": self.native_units,
                "visual_components": list(self.visual_components),
                "limitations": list(self.limitations)}


def inspect_document(path: Path, *, limits: DocumentLimits = DocumentLimits()) -> PrivacyInspection | None:
    """Inspect supported non-tabular files only after the Codex-first review.

    None means the legacy tabular/text scanner owns the format. Any parser failure
    is fatal to clearance, never interpreted as absence of sensitive content.
    """
    suffix = path.suffix.casefold()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".eml", ".docx"}:
        return None
    if path.stat().st_size > limits.maximum_file_bytes:
        raise DocumentError("RESOURCE_LIMIT", "Privacy source exceeds bounded parser budget")
    before = _digest(path)
    text = ""
    components: list[str] = []
    limitations: list[str] = []
    native_units = 0
    reader_version = INSPECTION_VERSION
    if suffix == ".pdf":
        from againward.documents.readers import READER_VERSION, _pdf_payload
        payload = _pdf_payload(path, limits)
        pages = payload["pages"]
        limitations = payload["limitations"]
        reader_version = READER_VERSION + "/pypdf-" + payload["pypdf_version"]
        text = "\n".join([*(page["text"] for page in pages), payload.get("metadata_text", "")])
        native_units = sum(bool(page["text"].strip()) for page in pages)
        components = [f"page:{page['page']}" for page in pages if page["route"] != "NATIVE"]
        for limitation, location in (("PDF_FORM_FIELDS_REQUIRE_REVIEW", "pdf:forms"),
                                     ("PDF_ANNOTATIONS_REQUIRE_REVIEW", "pdf:annotations")):
            if limitation in limitations:
                components.append(location)
    elif suffix in {".png", ".jpg", ".jpeg"}:
        with path.open("rb") as handle:
            signature = handle.read(8)
        if not (suffix == ".png" and signature == b"\x89PNG\r\n\x1a\n"
                or suffix in {".jpg", ".jpeg"} and signature.startswith(b"\xff\xd8\xff")):
            raise DocumentError("SOURCE_UNREADABLE", "Image signature invalid")
        components = ["image:1"]
    elif suffix == ".docx":
        from againward.documents.readers import _docx
        units, limitations = _docx(path, "privacy-source", limits)
        text = "\n".join(unit.text for unit in units)
        native_units = len(units)
    else:
        message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
        if message.defects:
            raise DocumentError("SOURCE_UNREADABLE", "Malformed business email")
        values = [str(value) for _, value in message.items()]
        for part in message.walk():
            if part.is_multipart():
                continue
            if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
                values.append(str(part.get_content()))
            else:
                limitations.append("UNEXTRACTED_EMAIL_COMPONENT")
        text = "\n".join(values)
        native_units = len(values)
    if len(text) > limits.maximum_text_characters:
        raise DocumentError("RESOURCE_LIMIT", "Privacy text exceeds bounded parser budget")
    if not text.strip() and not components:
        limitations.append("EMPTY_OR_UNINSPECTABLE_DOCUMENT")
    after = _digest(path)
    if before != after:
        raise DocumentError("SOURCE_CHANGED", "Privacy source changed during inspection")
    return PrivacyInspection(before, text, native_units, tuple(sorted(set(components))),
                             tuple(sorted(set(limitations))),
                             "NATIVE_AND_VISUAL" if components and text.strip() else
                             "VISUAL" if components else "NATIVE", reader_version)
