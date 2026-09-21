"""Deterministic source units, not semantic extraction or OCR."""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path
import posixpath
import subprocess
import sys
from typing import Any
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from againward.evidence.hashing import stable_hash
from .contracts import DocumentError, DocumentLimits, SourceBatch, SourceDocument, load_json
from .sources import assert_document_action, safe_file, verify_batch

READER_VERSION = "againward-native-reader-v1"
_SHEET = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass(frozen=True)
class SourceUnit:
    source_id: str
    location: str
    text: str
    route: str
    metadata: dict[str, Any]

    @property
    def unit_sha256(self) -> str:
        return stable_hash(asdict(self))

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "unit_sha256": self.unit_sha256}


@dataclass(frozen=True)
class ParsedDocument:
    source_id: str
    reader_version: str
    units: tuple[SourceUnit, ...]
    limitations: tuple[str, ...]

    @property
    def status(self) -> str:
        return "NEEDS_REVIEW" if self.limitations or any(u.route != "NATIVE" for u in self.units) else "SUCCESS"

    def to_dict(self) -> dict[str, Any]:
        return {"source_id": self.source_id, "reader_version": self.reader_version,
                "units": [u.to_dict() for u in self.units], "limitations": list(self.limitations),
                "status": self.status}


def _xml(archive: ZipFile, name: str) -> ET.Element:
    raw = archive.read(name)
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise DocumentError("SOURCE_UNREADABLE", "DTD/entity declarations refused")
    return ET.fromstring(raw)


def _archive(path: Path, limits: DocumentLimits) -> ZipFile:
    book = ZipFile(path)
    members = book.infolist()
    names = [m.filename for m in members]
    if (len(members) > limits.maximum_archive_members
            or sum(m.file_size for m in members) > limits.maximum_archive_bytes
            or len(set(names)) != len(names)):
        book.close()
        raise DocumentError("RESOURCE_LIMIT", "Archive members/expanded bytes exceeded or duplicated")
    if any(n.startswith("/") or ".." in Path(n).parts or "\\" in n for n in names):
        book.close()
        raise DocumentError("SOURCE_UNSAFE_PATH", "Unsafe archive member")
    if any("vbaproject" in n.lower() for n in names):
        book.close()
        raise DocumentError("SOURCE_UNSUPPORTED", "Spreadsheet macros refused")
    return book


def _xlsx(path: Path, sid: str, limits: DocumentLimits) -> tuple[list[SourceUnit], list[str]]:
    from openpyxl.utils.cell import coordinate_to_tuple, range_boundaries
    units: list[SourceUnit] = []
    limitations = []
    with _archive(path, limits) as book:
        strings = []
        if "xl/sharedStrings.xml" in book.namelist():
            strings = ["".join(si.itertext()) for si in _xml(book, "xl/sharedStrings.xml").findall(_SHEET + "si")]
        workbook = _xml(book, "xl/workbook.xml")
        props = workbook.find(_SHEET + "workbookPr")
        epoch = "1904" if props is not None and props.get("date1904") in {"1", "true"} else "1900"
        rels = {r.get("Id"): r for r in _xml(book, "xl/_rels/workbook.xml.rels")}
        styles = _xml(book, "xl/styles.xml") if "xl/styles.xml" in book.namelist() else None
        formats = {x.get("numFmtId"): x.get("formatCode") for x in
                   styles.findall(_SHEET + "numFmts/" + _SHEET + "numFmt")} if styles is not None else {}
        cell_styles = styles.findall(_SHEET + "cellXfs/" + _SHEET + "xf") if styles is not None else []
        for sheet in workbook.findall(_SHEET + "sheets/" + _SHEET + "sheet"):
            rid = sheet.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            rel = rels.get(rid)
            if rel is None or rel.get("TargetMode") == "External":
                raise DocumentError("SOURCE_UNSUPPORTED", "External or missing worksheet")
            target = rel.get("Target", "")
            member = target.lstrip("/") if target.startswith("/xl/") else posixpath.normpath("xl/" + target)
            if not member.startswith("xl/") or member not in book.namelist():
                raise DocumentError("SOURCE_UNSAFE_PATH", "Invalid worksheet relationship")
            tree = _xml(book, member)
            merged = [x.get("ref") for x in tree.findall(_SHEET + "mergeCells/" + _SHEET + "mergeCell")]
            if merged:
                limitations.append("MERGED_CELLS_REQUIRE_REVIEW:" + str(sheet.get("name")))
            if sheet.get("state", "visible") != "visible":
                limitations.append("HIDDEN_SHEET:" + str(sheet.get("name")))
            for row in tree.findall(_SHEET + "sheetData/" + _SHEET + "row"):
                for cell in row.findall(_SHEET + "c"):
                    formula = cell.find(_SHEET + "f")
                    raw = cell.findtext(_SHEET + "v", "")
                    kind = cell.get("t", "n")
                    if kind == "s":
                        value = strings[int(raw)]
                    elif kind == "inlineStr":
                        value = "".join(cell.itertext())
                    else:
                        value = raw
                    style = int(cell.get("s", "0"))
                    format_id = cell_styles[style].get("numFmtId") if style < len(cell_styles) else None
                    row_number, column_number = coordinate_to_tuple(cell.get("r", ""))
                    merged_cell = any(c1 <= column_number <= c2 and r1 <= row_number <= r2
                                      for c1, r1, c2, r2 in (range_boundaries(str(v)) for v in merged))
                    metadata = {"sheet": sheet.get("name"), "cell": cell.get("r"),
                                "raw_xml_value": raw, "cell_type": kind, "style_id": cell.get("s"),
                                "number_format_id": format_id, "number_format": formats.get(format_id),
                                "date_epoch": epoch,
                                "formula": formula.text if formula is not None else None,
                                "formula_present": formula is not None, "merged_ranges": merged,
                                "merged_cell": merged_cell,
                                "hidden_row": row.get("hidden") in {"1", "true"},
                                "date_interpretation": "RAW_SERIAL_OR_ISO_UNTIL_EXPLICIT_REVIEW"}
                    if formula is not None:
                        limitations.append("FORMULA_NOT_EVALUATED")
                    units.append(SourceUnit(sid, f"sheet:{sheet.get('name')}/cell:{cell.get('r')}",
                                            value, "NATIVE", metadata))
                    if len(units) > limits.maximum_cells:
                        raise DocumentError("RESOURCE_LIMIT", "Spreadsheet cells exceeded")
    return units, limitations


def _docx(path: Path, sid: str, limits: DocumentLimits) -> tuple[list[SourceUnit], list[str]]:
    with _archive(path, limits) as book:
        tree = _xml(book, "word/document.xml")
        units = [SourceUnit(sid, f"paragraph:{i}", "".join(
                    t.text or "" for t in p.iter(_WORD + "t")), "NATIVE", {})
                 for i, p in enumerate(tree.iter(_WORD + "p"), 1)]
        limitations = ["DOCX_NON_BODY_COMPONENTS_REQUIRE_REVIEW"] if any(
            n.startswith(("word/header", "word/footer", "word/comments", "word/media",
                          "word/footnotes", "word/endnotes")) for n in book.namelist()) else []
        if any(x.tag in {_WORD + "del", _WORD + "ins"} for x in tree.iter()):
            limitations.append("TRACKED_CHANGES_REQUIRE_REVIEW")
        return units, limitations


def _pdf(path: Path, sid: str, limits: DocumentLimits) -> tuple[list[SourceUnit], list[str], str]:
    # Parser memory/CPU isolation matters on Termux. No shell, network, OCR or
    # document-controlled command is invoked. The worker is our private parser.
    command = [sys.executable, "-m", "againward.documents.pdf_worker", str(path.resolve()),
               str(limits.maximum_pages), str(limits.maximum_text_characters)]
    try:
        result = subprocess.run(command, capture_output=True, timeout=30, check=False)
    except subprocess.TimeoutExpired as exc:
        raise DocumentError("RESOURCE_LIMIT", "PDF parser timed out") from exc
    if result.returncode:
        raise DocumentError("SOURCE_UNREADABLE", "PDF parser refused, failed or exceeded resources")
    payload = load_json(result.stdout, maximum=limits.maximum_output_bytes)
    units = [SourceUnit(sid, f"page:{p['page']}", p["text"], p["route"],
                        {"page": p["page"], "page_count": len(payload["pages"]),
                         "embedded_images": p["embedded_images"]}) for p in payload["pages"]]
    return units, payload["limitations"], READER_VERSION + "/pypdf-" + payload["pypdf_version"]


def read_document(document: SourceDocument, root: Path, *,
                  limits: DocumentLimits = DocumentLimits()) -> ParsedDocument:
    """Low-level parser of a verified blob; use read_batch at the workflow boundary."""
    path = safe_file(root, document.blob_path)
    from againward.core.workflow import fingerprint
    from againward.core.privacy import assert_source_approved_for_analysis
    assert_source_approved_for_analysis(path, output_directory=root)
    assert_document_action(root)
    if path.stat().st_size > limits.maximum_file_bytes:
        raise DocumentError("RESOURCE_LIMIT", "File bytes exceeded")
    if fingerprint(path) != document.sha256:
        raise DocumentError("SOURCE_CHANGED")
    sid, media = document.source_id, document.media_type
    version = READER_VERSION
    limitations: list[str] = []
    units: list[SourceUnit] = []
    try:
        if media == "application/pdf":
            units, limitations, version = _pdf(path, sid, limits)
        elif media.startswith("image/"):
            units = [SourceUnit(sid, "image:1", "", "MULTIMODAL_REQUIRED", {"media_type": media})]
        elif media.endswith("spreadsheetml.sheet"):
            units, limitations = _xlsx(path, sid, limits)
        elif media.endswith("wordprocessingml.document"):
            units, limitations = _docx(path, sid, limits)
        elif media == "text/csv":
            with path.open(encoding="utf-8-sig", newline="") as handle:
                for row_index, row in enumerate(csv.reader(handle), 1):
                    for column, value in enumerate(row, 1):
                        units.append(SourceUnit(sid, f"row:{row_index}/column:{column}", value,
                                                "NATIVE", {"row": row_index, "column": column}))
                        if len(units) > limits.maximum_cells:
                            raise DocumentError("RESOURCE_LIMIT", "CSV cells exceeded")
        elif media == "message/rfc822":
            message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
            for i, (name, value) in enumerate(message.items(), 1):
                units.append(SourceUnit(sid, f"header:{i}", str(value), "NATIVE", {"header": name}))
            for i, part in enumerate(message.walk(), 1):
                if part.is_multipart():
                    continue
                if part.get_content_type() == "text/plain" and part.get_content_disposition() != "attachment":
                    units.append(SourceUnit(sid, f"part:{i}", str(part.get_content()), "NATIVE", {}))
                else:
                    limitations.append("UNEXTRACTED_EMAIL_COMPONENT:" + str(i))
            if message.defects:
                limitations.append("MALFORMED_EMAIL")
        elif media == "text/plain":
            units = [SourceUnit(sid, f"line:{i}", line, "NATIVE", {})
                     for i, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1)]
        else:
            raise DocumentError("SOURCE_UNSUPPORTED")
    except DocumentError:
        raise
    except (OSError, ValueError, UnicodeError, BadZipFile, KeyError, IndexError, ET.ParseError, csv.Error) as exc:
        raise DocumentError("SOURCE_UNREADABLE", "Native parsing failed") from exc
    if not units:
        limitations.append("EMPTY_DOCUMENT")
    if len(units) > limits.maximum_cells or sum(len(u.text) for u in units) > limits.maximum_text_characters:
        raise DocumentError("RESOURCE_LIMIT", "Source units/text exceeded")
    locations = [u.location for u in units]
    if len(locations) != len(set(locations)):
        raise DocumentError("SOURCE_UNREADABLE", "Duplicate source location")
    if fingerprint(path) != document.sha256:
        raise DocumentError("SOURCE_CHANGED")
    return ParsedDocument(sid, version, tuple(units), tuple(sorted(set(limitations))))


def read_batch(batch: SourceBatch, root: Path, *,
               limits: DocumentLimits = DocumentLimits()) -> tuple[ParsedDocument, ...]:
    verify_batch(batch, root, limits=limits)
    parsed = tuple(read_document(d, root, limits=limits) for d in batch.documents)
    verify_batch(batch, root, limits=limits)
    return parsed
