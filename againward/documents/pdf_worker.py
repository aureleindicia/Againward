"""Private memory/CPU-bounded native PDF worker; no model and no OCR."""
from __future__ import annotations

import json
from pathlib import Path
import resource
import re
import sys
from typing import cast


def main() -> None:
    import pypdf
    from pypdf import PdfReader
    from pypdf.generic import DictionaryObject

    # Android's allocator reserves a large virtual arena even for a tiny Python
    # process. A fixed AS ceiling below that reservation aborts before parsing.
    # Bound additional address space after trusted imports; CPU is independently
    # capped. This is a parser resource guard, not a universal hostile-PDF sandbox.
    current_virtual = int(Path("/proc/self/statm").read_text().split()[0])
    import os
    ceiling = current_virtual * os.sysconf("SC_PAGE_SIZE") + 384 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (ceiling, ceiling))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))

    path, maximum_pages, maximum_text = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    reader = PdfReader(path, strict=True)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF unsupported")
    if len(reader.pages) > maximum_pages:
        raise ValueError("Page budget exceeded")
    pages = []
    limitations = []
    root = cast(DictionaryObject, reader.trailer["/Root"])
    if "/AcroForm" in root:
        limitations.append("PDF_FORM_FIELDS_REQUIRE_REVIEW")
    if "/Names" in root:
        limitations.append("PDF_NAMED_COMPONENTS_REQUIRE_REVIEW")
    consumed = 0
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text()
        consumed += len(text)
        if consumed > maximum_text:
            raise ValueError("Text budget exceeded")
        resources = page.get("/Resources", {})
        objects = resources.get("/XObject", {}) if resources else {}
        image_count = sum(obj.get_object().get("/Subtype") == "/Image" for obj in objects.values())
        # Images alongside native text may contain a signature, clause or table.
        # Native text is available, but completeness requires component review.
        route = "NATIVE" if text.strip() and not image_count else (
            "HYBRID_REVIEW_REQUIRED" if text.strip() else "MULTIMODAL_REQUIRED")
        if "/Annots" in page:
            limitations.append("PDF_ANNOTATIONS_REQUIRE_REVIEW")
        pages.append({"page": number, "text": text, "route": route, "embedded_images": image_count})
    declared = [int(match.group(2)) for page in pages for match in re.finditer(
        r"(?i)\bpage\s+(\d+)\s*(?:of|sur|/)\s*(\d+)\b", page["text"])]
    if declared and max(declared) > len(pages):
        limitations.append("MISSING_PAGES_DECLARED_IN_SOURCE")
    print(json.dumps({"pages": pages, "limitations": sorted(set(limitations)),
                      "pypdf_version": pypdf.__version__}, ensure_ascii=False))


if __name__ == "__main__":
    main()
