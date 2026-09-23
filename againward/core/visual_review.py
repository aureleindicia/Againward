"""Local operator preparation for genuine visual privacy inspection.

This records an accountable *claim* by a person at a terminal, not biometric or
cryptographic identity. It does not replace Codex-first privacy review or the
deterministic privacy gate. Raw previews remain temporary inside privacy/candidate.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Callable

from .contract_policy import assert_contract_permission
from .privacy import _atomic_json, _read_json, _safe_files, _sha256
from .privacy_inspection import INSPECTION_VERSION, inspect_document

PACKET_SCHEMA = "againward-local-visual-packet-v1"
_ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,63}")
_CATEGORY = re.compile(r"[A-Z][A-Z0-9_]{1,63}")


def _digest(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _packet_file(case: Path, relative: str, directory: str) -> Path:
    if not isinstance(relative, str):
        raise ValueError("SOURCE_CHANGED: invalid visual packet path")
    part = Path(relative)
    if part.is_absolute() or ".." in part.parts or not part.parts:
        raise ValueError("SOURCE_CHANGED: visual packet path escapes case")
    target = case / part
    if not target.resolve().is_relative_to((case / directory).resolve()):
        raise ValueError("SOURCE_CHANGED: visual packet path escapes expected directory")
    return target


def prepare_visual_packet(case: Path, review_file: Path) -> dict:
    """Run only after Codex's first semantic privacy read, before clearance."""
    case = Path(case)
    review_file = Path(review_file)
    if not review_file.resolve().is_relative_to((case / "privacy").resolve()):
        raise ValueError("PRIVACY GATE: review must remain within the case privacy directory")
    assert_contract_permission(case)
    review = _read_json(review_file)
    first = review.get("codex_semantic_review", {})
    if first.get("completed") is not True or first.get("first_substantive_reader_attested") is not True:
        raise ValueError("PRIVACY GATE: Codex-first semantic review must precede visual preparation")
    from againward.entrypoints import get_case_domain
    policy = get_case_domain(case).privacy_preservation.risk.policy_id
    packet_file = case / "privacy/candidate/visual_packet.json"
    if packet_file.exists():
        raise ValueError("SOURCE_CHANGED: prior visual packet exists; use a fresh reviewed intake cycle")
    preview_dir = case / "privacy/candidate/visual_previews"
    if preview_dir.exists() and any(preview_dir.iterdir()):
        raise ValueError("SOURCE_CHANGED: stale visual previews exist")
    incoming = _safe_files(case / "incoming")
    if not incoming:
        raise ValueError("PRIVACY GATE: no incoming files to inspect")
    components = []
    for source in incoming:
        inspection = inspect_document(source)
        if inspection is None:
            continue
        if inspection.limitations:
            raise ValueError("UNINSPECTABLE_COMPONENT: source requires a complete safe inspection path")
        if len(inspection.visual_components) > 8:
            raise ValueError("RESOURCE_LIMIT: more than eight visual components; request a smaller batch")
        relative_source = source.relative_to(case).as_posix()
        for location in inspection.visual_components:
            preview_dir.mkdir(parents=True, exist_ok=True)
            suffix = ".png" if source.suffix.casefold() == ".png" or source.suffix.casefold() == ".pdf" else ".jpg"
            preview = preview_dir / (inspection.source_sha256[:16] + "-" + location.replace(":", "-") + suffix)
            if location.startswith("page:") and source.suffix.casefold() == ".pdf":
                renderer = shutil.which("pdftoppm")
                if renderer is None:
                    raise ValueError("UNINSPECTABLE_COMPONENT: Poppler pdftoppm unavailable")
                page = int(location.removeprefix("page:"))
                prefix = preview.with_suffix("")
                try:
                    result = subprocess.run([renderer, "-f", str(page), "-l", str(page), "-singlefile",
                                             "-r", "140", "-png", str(source), str(prefix)],
                                            capture_output=True, timeout=45, check=False)
                except subprocess.TimeoutExpired as exc:
                    raise ValueError("RESOURCE_LIMIT: visual preview timed out") from exc
                if result.returncode or not preview.is_file():
                    raise ValueError("UNINSPECTABLE_COMPONENT: cannot render visual page")
            elif location == "image:1" and source.suffix.casefold() in {".png", ".jpg", ".jpeg"}:
                shutil.copyfile(source, preview)
            else:
                raise ValueError("UNINSPECTABLE_COMPONENT: no safe local preview for component")
            if preview.stat().st_size > 8_000_000:
                raise ValueError("RESOURCE_LIMIT: visual preview too large")
            components.append({"source": relative_source, "source_sha256": inspection.source_sha256,
                               "location": location, "inspection_version": INSPECTION_VERSION,
                               "policy_version": policy,
                               "preview": preview.relative_to(case).as_posix(),
                               "preview_sha256": _sha256(preview)})
    packet = {"schema_version": PACKET_SCHEMA, "case_id": case.name,
              "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "policy_version": policy, "components": components}
    packet["packet_sha256"] = _digest(packet)
    _atomic_json(packet_file, packet)
    return packet


def attest_visual_packet(case: Path, review_file: Path, *, actor_id: str,
                         ask: Callable[[str], str], interactive: bool) -> dict:
    """Only the terminal CLI sets interactive=True after a TTY check."""
    if not interactive:
        raise ValueError("HUMAN_REVIEW_REQUIRED: interactive terminal inspection required")
    case, review_file = Path(case), Path(review_file)
    if not _ACTOR.fullmatch(actor_id):
        raise ValueError("A bounded local operator identifier is required")
    assert_contract_permission(case)
    packet_file = case / "privacy/candidate/visual_packet.json"
    packet = _read_json(packet_file)
    claimed = packet.pop("packet_sha256", None)
    if claimed != _digest(packet) or packet.get("schema_version") != PACKET_SCHEMA:
        raise ValueError("SOURCE_CHANGED: visual packet altered")
    packet["packet_sha256"] = claimed
    from againward.entrypoints import get_case_domain
    if packet["policy_version"] != get_case_domain(case).privacy_preservation.risk.policy_id:
        raise ValueError("PRIVACY_MIGRATION_REQUIRED: visual policy changed")
    review = _read_json(review_file)
    by_source = {row.get("source"): row for row in review.get("files", []) if isinstance(row, dict)}
    updates: dict[str, list[dict]] = {}
    for component in packet["components"]:
        source = _packet_file(case, component["source"], "incoming")
        preview = _packet_file(case, component["preview"], "privacy/candidate/visual_previews")
        if (not source.is_file() or source.is_symlink() or _sha256(source) != component["source_sha256"]
                or not preview.is_file() or preview.is_symlink()
                or _sha256(preview) != component["preview_sha256"]):
            raise ValueError("SOURCE_CHANGED: source or operator preview changed")
        if component["source"] not in by_source:
            raise ValueError("PARTIAL_DOCUMENT_INSPECTION: Codex privacy review does not list the source")
        expected = component["source_sha256"][:12]
        confirmation = ask(f"Open {preview} and inspect every visible detail. Type INSPECTED {expected}: ")
        if confirmation.strip() != f"INSPECTED {expected}":
            raise ValueError("HUMAN_REVIEW_REQUIRED: original pixels not explicitly inspected")
        decision = ask("PASS or REJECT this exact component? ").strip().upper()
        if decision != "PASS":
            raise ValueError("VISUAL_REJECTED: stop and escalate; no privacy PASS written")
        categories = [item.strip() for item in ask("Observed privacy categories (comma-separated, or blank): ").split(",")
                      if item.strip()]
        if len(categories) != len(set(categories)) or any(not _CATEGORY.fullmatch(item) for item in categories):
            raise ValueError("Invalid visual privacy category list")
        if ask("Business evidence preserved and prompt injection ignored? Type YES: ").strip() != "YES":
            raise ValueError("HUMAN_REVIEW_REQUIRED: preservation/injection check not attested")
        updates.setdefault(component["source"], []).append({
            "location": component["location"], "source_sha256": component["source_sha256"],
            "inspection_version": component["inspection_version"],
            "reviewer_role": "HUMAN", "reviewer_id": actor_id,
            "policy_version": packet["policy_version"],
            "preview_sha256": component["preview_sha256"], "packet_sha256": claimed,
            "reviewed_at_utc": datetime.now(timezone.utc).isoformat(),
            "decision": "PASS", "detected_categories": categories,
            "business_evidence_preserved": True, "prompt_injection_ignored": True,
        })
    for source_name, entries in updates.items():
        prior = by_source[source_name].get("visual_reviews", [])
        if prior:
            raise ValueError("REVIEW_STALE: existing visual decision cannot be silently overwritten")
        by_source[source_name]["visual_reviews"] = entries
    _atomic_json(review_file, review)
    return {"actor_id": actor_id, "packet_sha256": claimed,
            "reviewed_components": sum(len(value) for value in updates.values()),
            "review_path": str(review_file)}
