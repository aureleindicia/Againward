"""Small synthetic document renderers; never imported by the analysis engine."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from io import BytesIO
import subprocess
import tempfile
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import xml.etree.ElementTree as ET

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject, NumberObject


def pdf(path: Path, lines: list[str], *, title="SYNTHETIC - NOT A REAL CLIENT", scan=False, hybrid=False):
    """Readable one-page PDF. Optional genuine rasterization requires Poppler.

    Scan text is rendered into pixels, not hidden in a text layer. Temporary
    native originals stay outside the participant's document directory.
    """
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    text_lines = [title, "", *lines]
    if len(text_lines) > 43 or any(len(line) > 95 for line in text_lines):
        raise ValueError("Synthetic renderer refuses clipped text")
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in text_lines]
    content = ("BT /F1 10 Tf 38 800 Td 17 TL " + " ".join(f"({line}) Tj T*" for line in escaped) + " ET").encode("latin-1")
    stream = DecodedStreamObject()
    stream.set_data(content)
    page[NameObject("/Resources")] = resources
    page[NameObject("/Contents")] = writer._add_object(stream)
    if scan or hybrid:
        with tempfile.TemporaryDirectory(prefix="againward-synthetic-raster-") as temp:
            native = Path(temp) / "native.pdf"
            writer.write(native)
            process = subprocess.run(["pdftoppm", "-singlefile", "-gray", "-r", "96", str(native)],
                                     capture_output=True, timeout=30, check=True)
            # Poppler emits binary PGM (P5), without comments; explicitly check.
            magic, shape, maximum, pixels = process.stdout.split(b"\n", 3)
            if magic != b"P5" or maximum != b"255":
                raise ValueError("Unexpected Poppler raster format")
            width, height = map(int, shape.split())
            if len(pixels) != width * height:
                raise ValueError("Incomplete synthetic raster")
        image = DecodedStreamObject()
        image.set_data(pixels)
        image.update({NameObject("/Type"): NameObject("/XObject"), NameObject("/Subtype"): NameObject("/Image"),
                      NameObject("/Width"): NumberObject(width), NameObject("/Height"): NumberObject(height),
                      NameObject("/ColorSpace"): NameObject("/DeviceGray"), NameObject("/BitsPerComponent"): NumberObject(8)})
        resources[NameObject("/XObject")] = DictionaryObject({NameObject("/Im1"): writer._add_object(image.flate_encode())})
        stream.set_data((b"BT /F1 9 Tf 38 825 Td (Invoice attachment follows) Tj ET " if hybrid else b"")
                        + b"q 595 0 0 810 0 0 cm /Im1 Do Q")
    writer.write(path)


def xlsx(path, book):
    """Freeze core and ZIP timestamps so a seed reproduces identical source bytes."""
    fixed = datetime(2026, 9, 1)
    book.properties.created = fixed
    book.properties.modified = fixed
    raw = BytesIO()
    book.save(raw)
    with ZipFile(raw) as source, ZipFile(path, "w", compression=ZIP_DEFLATED) as output:
        for name in sorted(source.namelist()):
            data = source.read(name)
            if name == "docProps/core.xml":
                tree = ET.fromstring(data)
                for key in ("created", "modified"):
                    node = tree.find("{http://purl.org/dc/terms/}" + key)
                    if node is not None:
                        node.text = "2026-09-01T00:00:00Z"
                data = ET.tostring(tree, encoding="utf-8")
            info = ZipInfo(name, date_time=(2026, 9, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            output.writestr(info, data)
