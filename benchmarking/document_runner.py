"""Participant-side runner: documents plus supplied proposals, never scorer truth.

No semantic extraction is faked. Without a supplied extraction this deliberately
records NO_SUBMISSION and abstains. It is a routing baseline, not model accuracy.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from againward.documents.contracts import DocumentError, load_json
from againward.documents.sources import inventory_sources
from againward.documents.readers import read_batch
from againward.domains.rental.document_adapter import load_document_case
from againward.domains.rental.reconciliation import reconcile


def engine_identity(repository: Path, *, holdout: bool) -> dict:
    def git(*args):
        return subprocess.run(["git", "-C", str(repository), *args], check=True, capture_output=True).stdout
    status = git("status", "--porcelain", "--untracked-files=all")
    if holdout and status:
        raise ValueError("HOLDOUT requires a clean committed engine; freeze before running")
    return {"head": git("rev-parse", "HEAD").decode().strip(), "clean": not bool(status),
            "diff_sha256": hashlib.sha256(git("diff", "HEAD")).hexdigest(),
            "status_sha256": hashlib.sha256(status).hexdigest()}


def run_documents(public: Path, output: Path, *, submissions: Path | None = None, split="DEV") -> dict:
    if split not in {"DEV", "ADVERSARIAL", "HOLDOUT"}:
        raise ValueError("Unknown evaluation split")
    public, output = Path(public), Path(output)
    repository = Path(__file__).resolve().parents[1]
    identity = engine_identity(repository, holdout=split == "HOLDOUT")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use an empty run directory; previous observations are immutable")
    output.mkdir(parents=True, exist_ok=True)
    observations = {}
    for folder in sorted(public.iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError("Participant root must contain only ordinary case directories")
        started = time.perf_counter()
        root = output / folder.name
        record = {"status": "NO_SUBMISSION", "supported_discrepancy": None, "facts": [], "relationships": [],
                  "manual_decisions": 0, "unresolved_facts": None, "automatic_recovery_claims": 0,
                  "source_chain_validated": False, "failure_code": None}
        batch = inventory_sources(folder, root)
        parsed = read_batch(batch, root)
        record["source_hashes"] = sorted(d.sha256 for d in batch.documents)
        record["routes"] = [u.route for p in parsed for u in p.units]
        record["reader_limitations"] = sorted({limit for p in parsed for limit in p.limitations})
        proposal = submissions / (folder.name + ".json") if submissions else None
        if proposal and proposal.is_file():
            try:
                raw = proposal.read_bytes()
                record["submission_sha256"] = hashlib.sha256(raw).hexdigest()
                package = load_json(raw)
                if package.get("batch", {}).get("batch_id") != batch.batch_id:
                    raise DocumentError("SOURCE_CHANGED", "Submission does not cover the exact participant document batch")
                case, lineage = load_document_case(package, root)
                result = reconcile(case)
                record.update(status="VALIDATED", supported_discrepancy={
                    c: totals["supported_positive_discrepancy"] for c, totals in result["totals_by_currency"].items()},
                    facts=lineage["facts"], source_chain_validated=True)
                record["unresolved_groups"] = sum(g["difference"] is None for g in result["groups"])
                if record["unresolved_groups"]:
                    record["supported_discrepancy"] = None
                entities = {e["entity_id"]: e for e in lineage["entities"]}
                for key in ("rental_resolution", "credit_resolution"):
                    for link in lineage[key]["relationships"]:
                        record["relationships"].append({**link,
                            "left_source": entities[link["left"]]["source_id"].removeprefix("src-"),
                            "right_source": entities[link["right"]]["source_id"].removeprefix("src-")})
                record["manual_decisions"] = len(package["fact_review"]["decisions"]) + sum(
                    len(package[key]["decisions"]) if package[key] else 0
                    for key in ("rental_relationship_review", "credit_relationship_review"))
                record["unresolved_facts"] = sum(d["decision"] in {"DEFER", "DISPUTED"}
                                                for d in package["fact_review"]["decisions"])
            except (DocumentError, ValueError) as exc:
                record.update(status="ABSTAIN", failure_code=getattr(exc, "code", "CANONICALIZATION_REFUSED"),
                              failure_reason=str(exc))
        record["seconds"] = round(time.perf_counter() - started, 6)
        observations[folder.name] = record
    if engine_identity(repository, holdout=split == "HOLDOUT") != identity:
        raise ValueError("Engine changed during the run; do not score these observations")
    result = {"schema_version": "againward-document-observations-v1", "split": split, "engine": identity,
              "participant": "SUPPLIED_EXTRACTION_REPLAY" if submissions else "NO_EXTRACTION_ROUTING_BASELINE",
              "model_accuracy_measured": False, "cases": observations,
              "limits": ["Replay quality is not live model accuracy or autonomous reviewer performance.",
                         "No findings review or client lifecycle is fabricated by this runner."]}
    data = (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode()
    (output / "observations.json").write_bytes(data)
    (output / "observations.sha256").write_text(hashlib.sha256(data).hexdigest() + "\n")
    return result
