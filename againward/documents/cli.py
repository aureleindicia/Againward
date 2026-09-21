"""Local document proposal workflow. No provider call or approval is fabricated."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from againward.core.artifact_store import transaction, write_json
from againward.core.privacy import assert_source_approved_for_analysis
from againward.evidence.hashing import stable_hash
from .contracts import SourceBatch, load_json
from .extraction import (
    persist_extraction, promote_facts, replay_extraction, validate_proposal,
)
from .readers import read_batch
from .sources import assert_document_action, inventory_sources


def _load(path: Path, root: Path) -> dict:
    assert_source_approved_for_analysis(path, output_directory=root)
    return load_json(path.read_bytes())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    intake = commands.add_parser("inventory", help="Snapshot approved sources; does not clear privacy")
    intake.add_argument("source", type=Path)
    intake.add_argument("root", type=Path)
    intake.add_argument("--previous", type=Path)
    intake.add_argument("--purpose", choices=("INITIAL", "SUPPLEMENTAL", "CORRECTION", "CLIENT_RESPONSE"), default="INITIAL")
    inspect = commands.add_parser("inspect", help="Native source units and multimodal needs")
    inspect.add_argument("root", type=Path)
    inspect.add_argument("batch", type=Path)
    validate = commands.add_parser("validate", help="Validate and store a supplied model/analyst proposal")
    validate.add_argument("root", type=Path)
    validate.add_argument("batch", type=Path)
    validate.add_argument("proposal", type=Path)
    promote = commands.add_parser("promote", help="Apply an explicit source-bound fact review")
    promote.add_argument("root", type=Path)
    promote.add_argument("batch", type=Path)
    promote.add_argument("review", type=Path)
    promote.add_argument("extractions", nargs="+", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            previous = SourceBatch.from_dict(_load(args.previous, args.root)) if args.previous else None
            result = inventory_sources(args.source, args.root, purpose=args.purpose, previous=previous).to_dict()
        else:
            batch = SourceBatch.from_dict(_load(args.batch, args.root))
            if args.command == "inspect":
                result = {"batch_id": batch.batch_id,
                          "documents": [d.to_dict() for d in read_batch(batch, args.root)]}
            elif args.command == "validate":
                extraction = validate_proposal(_load(args.proposal, args.root), batch, args.root)
                path = persist_extraction(extraction, args.root)
                result = {"status": extraction.status, "extraction_path": str(path),
                          "candidate_count": len(extraction.candidates), "canonical_facts": 0}
            else:
                assert_document_action(args.root, mutation=True)
                extractions = tuple(replay_extraction(_load(path, args.root), batch, args.root)
                                    for path in args.extractions)
                review = _load(args.review, args.root)
                facts = promote_facts(extractions, review, batch, args.root)
                body = {"schema_version": "againward-canonical-facts-v1", "batch_id": batch.batch_id,
                        "extraction_paths": [str(p) for p in args.extractions],
                        "review": review, "facts": [f.to_dict() for f in facts]}
                destination = args.root / "promotions" / (stable_hash(body) + ".json")
                with transaction(args.root):
                    if destination.exists() and _load(destination, args.root) != body:
                        raise ValueError("SOURCE_CHANGED: prior canonical promotion altered")
                    write_json(destination, body)
                result = {"status": "REVIEWED_FACTS", "canonical_facts": len(facts),
                          "artifact": str(destination), "approved_for_delivery": False}
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
