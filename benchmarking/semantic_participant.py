"""Run a real Codex semantic participant on public synthetic files only.

No generator, private truth, scripted fact review or financial authority is
imported here. This output is candidate quality, not an approved Rental case.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

from againward.documents.codex_provider import CodexCliProvider, PROMPT_VERSION, EXTRACTOR_VERSION
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal
from againward.documents.readers import read_batch
from againward.documents.sources import inventory_sources
from againward.domains.rental.semantic_guidance import GUIDANCE_VERSION, guidance
from benchmarking.document_runner import engine_identity


def run_semantic_participant(public: Path, output: Path, *, split: str, model: str,
                             timeout_seconds: int = 180) -> dict:
    if split not in {"DEV", "ADVERSARIAL", "HOLDOUT"}:
        raise ValueError("Unknown evaluation split")
    public, output = Path(public), Path(output)
    if public.name != "public" or not public.is_dir() or public.is_symlink():
        raise ValueError("Participant input must be the isolated public case directory")
    repository = Path(__file__).resolve().parents[1]
    identity = engine_identity(repository, holdout=split == "HOLDOUT")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use an empty participant output directory")
    output.mkdir(parents=True, exist_ok=True)
    observations = {}
    for folder in sorted(public.iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError("Public root must contain only case directories")
        case_started = time.perf_counter()
        root = output / "cases" / folder.name
        batch = inventory_sources(folder, root)
        parsed = {item.source_id: item for item in read_batch(batch, root)}
        provider = CodexCliProvider(root, model=model, timeout_seconds=timeout_seconds)
        documents = []
        for document in batch.documents:
            started = time.perf_counter()
            entry = {"source_sha256": document.sha256, "media_type": document.media_type,
                     "status": "ABSTAIN", "failure_code": None, "candidates": [],
                     "limitations": [], "seconds": None}
            try:
                proposal = provider.propose(document, parsed[document.source_id],
                                            {"batch": batch, "semantic_guidance": guidance()})
                extraction = validate_proposal(proposal, batch, root)
                entry.update(status=extraction.status,
                             candidates=[candidate.to_dict() for candidate in extraction.candidates],
                             limitations=list(extraction.limitations),
                             extraction_sha256=extraction.to_dict()["extraction_sha256"])
            except (DocumentError, OSError, ValueError) as exc:
                entry["failure_code"] = getattr(exc, "code", "PARTICIPANT_REFUSED")
            entry["seconds"] = round(time.perf_counter() - started, 6)
            documents.append(entry)
        observations[folder.name] = {"source_hashes": sorted(d.sha256 for d in batch.documents),
                                     "documents": documents, "seconds": round(time.perf_counter() - case_started, 6),
                                     "human_decisions": 0, "approved_facts": 0,
                                     "client_facing_financial_claims": 0}
    if engine_identity(repository, holdout=split == "HOLDOUT") != identity:
        raise ValueError("Engine changed during participant run")
    result = {"schema_version": "againward-semantic-participant-v1", "split": split,
              "participant": "CODEX_CLI_REAL_SOURCE_UNITS", "model": model,
              "prompt_version": PROMPT_VERSION, "extractor_version": EXTRACTOR_VERSION,
              "rental_guidance_version": GUIDANCE_VERSION,
              "engine": identity, "cases": observations,
              "limits": ["Model candidates are not reviewed facts or supported financial findings.",
                         "Source-quote validity does not prove semantic correctness.",
                         "Human visual/fact/relation/financial review is not performed by this runner."]}
    encoded = (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode()
    (output / "semantic_observations.json").write_bytes(encoded)
    (output / "semantic_observations.sha256").write_text(hashlib.sha256(encoded).hexdigest() + "\n")
    return result
