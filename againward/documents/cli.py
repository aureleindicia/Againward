"""Local document workflow; extract is opt-in, and no approval is fabricated."""
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
    extract = commands.add_parser("extract", help="Opt-in Codex source-grounded proposals; no approval")
    extract.add_argument("root", type=Path)
    extract.add_argument("batch", type=Path)
    extract.add_argument("--model", required=True)
    extract.add_argument("--source-id")
    extract.add_argument("--timeout-seconds", type=int, default=180)
    validate = commands.add_parser("validate", help="Validate and store a supplied model/analyst proposal")
    validate.add_argument("root", type=Path)
    validate.add_argument("batch", type=Path)
    validate.add_argument("proposal", type=Path)
    promote = commands.add_parser("promote", help="Apply an explicit source-bound fact review")
    promote.add_argument("root", type=Path)
    promote.add_argument("batch", type=Path)
    promote.add_argument("review", type=Path)
    promote.add_argument("extractions", nargs="+", type=Path)
    template = commands.add_parser("review-template", help="Unreviewed fact worksheet from validated extractions")
    template.add_argument("root", type=Path)
    template.add_argument("batch", type=Path)
    template.add_argument("extractions", nargs="+", type=Path)
    visual_facts = commands.add_parser("visual-fact-attest", help="Interactive human check of accepted visual facts only")
    visual_facts.add_argument("root", type=Path)
    visual_facts.add_argument("batch", type=Path)
    visual_facts.add_argument("review", type=Path)
    visual_facts.add_argument("extractions", nargs="+", type=Path)
    visual_facts.add_argument("--actor-id", required=True)
    independent = commands.add_parser("independent-qa", help="Blind second source reread; no approval")
    independent.add_argument("root", type=Path)
    independent.add_argument("batch", type=Path)
    independent.add_argument("primary_extractions", nargs="+", type=Path)
    independent.add_argument("--model", required=True)
    independent.add_argument("--timeout-seconds", type=int, default=180)
    package = commands.add_parser("package-rental", help="Assemble reviewed document inputs; stop on unresolved links")
    package.add_argument("root", type=Path)
    package.add_argument("batch", type=Path)
    package.add_argument("fact_review", type=Path)
    package.add_argument("extractions", nargs="+", type=Path)
    package.add_argument("--rental-links", type=Path)
    package.add_argument("--credit-links", type=Path)
    links = commands.add_parser("link-review-template", help="Unreviewed Rental/credit relationship worksheets")
    links.add_argument("root", type=Path)
    links.add_argument("batch", type=Path)
    links.add_argument("fact_review", type=Path)
    links.add_argument("extractions", nargs="+", type=Path)
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
            elif args.command == "extract":
                from againward.documents.codex_provider import CodexCliProvider
                from againward.domains.rental.semantic_guidance import guidance
                from .readers import read_document
                provider = CodexCliProvider(args.root, model=args.model,
                                            timeout_seconds=args.timeout_seconds)
                selected = [d for d in batch.documents
                            if args.source_id is None or d.source_id == args.source_id]
                if not selected:
                    raise ValueError("Source ID absent from current batch")
                entries = []
                for document in selected:
                    parsed = read_document(document, args.root)
                    proposal = provider.propose(document, parsed,
                                                {"batch": batch, "semantic_guidance": guidance()})
                    extraction = validate_proposal(proposal, batch, args.root)
                    path = persist_extraction(extraction, args.root)
                    entries.append({"source_id": document.source_id, "status": extraction.status,
                                    "candidate_count": len(extraction.candidates),
                                    "extraction_path": str(path),
                                    "limitations": list(extraction.limitations)})
                result = {"batch_id": batch.batch_id, "model": args.model,
                          "approved_facts": 0, "extractions": entries}
            elif args.command == "validate":
                extraction = validate_proposal(_load(args.proposal, args.root), batch, args.root)
                path = persist_extraction(extraction, args.root)
                result = {"status": extraction.status, "extraction_path": str(path),
                          "candidate_count": len(extraction.candidates), "canonical_facts": 0}
            elif args.command == "review-template":
                from .review_template import fact_review_template
                assert_document_action(args.root, mutation=True)
                extractions = tuple(replay_extraction(_load(path, args.root), batch, args.root)
                                    for path in args.extractions)
                body, worksheet = fact_review_template(batch, extractions)
                prefix = args.root / "review_templates" / stable_hash(body)
                json_path = prefix.with_suffix(".json")
                sheet_path = prefix.with_suffix(".md")
                if json_path.exists() or sheet_path.exists():
                    raise ValueError("REVIEW_STALE: worksheet already exists; do not overwrite operator edits")
                json_path.parent.mkdir(parents=True, exist_ok=True)
                write_json(json_path, body)
                sheet_path.write_text(worksheet, encoding="utf-8")
                result = {"status": "UNREVIEWED_TEMPLATE", "candidate_count": len(body["decisions"]),
                          "review_template": str(json_path), "worksheet": str(sheet_path),
                          "approved_facts": 0}
            elif args.command == "visual-fact-attest":
                from .visual_fact_review import attest_visual_facts
                assert_document_action(args.root, mutation=True)
                extractions = tuple(replay_extraction(_load(path, args.root), batch, args.root)
                                    for path in args.extractions)
                reviewed = attest_visual_facts(batch, extractions, _load(args.review, args.root), args.root,
                                               actor_id=args.actor_id, ask=input,
                                               interactive=sys.stdin.isatty() and sys.stdout.isatty())
                destination = args.root / "review_templates" / ("attested-" + stable_hash(reviewed) + ".json")
                with transaction(args.root):
                    if destination.exists():
                        raise ValueError("REVIEW_STALE: visual fact attestation already exists")
                    write_json(destination, reviewed)
                result = {"status": "VISUAL_FACTS_ATTESTED", "review": str(destination),
                          "attested_components": len(reviewed["visual_attestations"]),
                          "approved_for_delivery": False}
            elif args.command == "independent-qa":
                from .independent_qa import reread_sources
                assert_document_action(args.root, mutation=True)
                primary = tuple(replay_extraction(_load(path, args.root), batch, args.root)
                                for path in args.primary_extractions)
                body, challenger_paths = reread_sources(batch, primary, args.root,
                                                        model=args.model,
                                                        timeout_seconds=args.timeout_seconds)
                destination = args.root / "independent_qa" / (body["qa_sha256"] + ".json")
                with transaction(args.root):
                    if destination.exists() and _load(destination, args.root) != body:
                        raise ValueError("SOURCE_CHANGED: prior independent QA artifact altered")
                    write_json(destination, body)
                result = {"status": body["status"], "qa_artifact": str(destination),
                          "challenger_extractions": [str(path) for path in challenger_paths],
                          "sources_needing_reconciliation": sum(row["needs_reconciliation"]
                                                                for row in body["source_results"]),
                          "approved_for_delivery": False}
            elif args.command == "package-rental":
                from againward.domains.rental.document_adapter import DOCUMENT_CASE_SCHEMA, load_document_case
                assert_document_action(args.root, mutation=True)
                package_body = {"schema_version": DOCUMENT_CASE_SCHEMA, "batch": batch.to_dict(),
                                "extractions": [_load(path, args.root) for path in args.extractions],
                                "fact_review": _load(args.fact_review, args.root),
                                "rental_relationship_review": _load(args.rental_links, args.root)
                                if args.rental_links else None,
                                "credit_relationship_review": _load(args.credit_links, args.root)
                                if args.credit_links else None}
                canonical, lineage = load_document_case(package_body, args.root)
                destination = args.root / "packages" / (stable_hash(package_body) + ".json")
                with transaction(args.root):
                    if destination.exists() and _load(destination, args.root) != package_body:
                        raise ValueError("SOURCE_CHANGED: prior Rental package altered")
                    write_json(destination, package_body)
                result = {"status": "REVIEWED_DOCUMENT_PACKAGE", "package": str(destination),
                          "canonical_case_sha256": lineage["canonical_case_sha256"],
                          "source_documents": len(batch.documents), "reviewed_facts": len(lineage["facts"]),
                          "invoice_lines": len(canonical.actual_charges),
                          "approved_for_delivery": False}
            elif args.command == "link-review-template":
                from .resolution import entities_from_facts, resolve_entities, RelationshipState
                from .review_template import relationship_review_template
                from againward.domains.rental.document_adapter import RENTAL_MATCH, CREDIT_MATCH
                assert_document_action(args.root, mutation=True)
                extractions = tuple(replay_extraction(_load(path, args.root), batch, args.root)
                                    for path in args.extractions)
                facts = promote_facts(extractions, _load(args.fact_review, args.root), batch, args.root)
                entities = entities_from_facts(facts)
                views = []
                planned = []
                for policy in (RENTAL_MATCH, CREDIT_MATCH):
                    resolved = resolve_entities(entities, policy)
                    draft, worksheet = relationship_review_template(resolved)
                    prefix = args.root / "review_templates" / (policy.relationship_type.lower() + "-" + stable_hash(draft))
                    json_path, sheet_path = prefix.with_suffix(".json"), prefix.with_suffix(".md")
                    if json_path.exists() or sheet_path.exists():
                        raise ValueError("REVIEW_STALE: relationship worksheet already exists")
                    planned.append((policy, resolved, draft, worksheet, json_path, sheet_path))
                for policy, resolved, draft, worksheet, json_path, sheet_path in planned:
                    json_path.parent.mkdir(parents=True, exist_ok=True)
                    write_json(json_path, draft)
                    sheet_path.write_text(worksheet, encoding="utf-8")
                    views.append({"relationship_type": policy.relationship_type,
                                  "unresolved": sum(r.state in {RelationshipState.CANDIDATE,
                                                                    RelationshipState.AMBIGUOUS}
                                                    for r in resolved.relationships),
                                  "review_template": str(json_path), "worksheet": str(sheet_path)})
                result = {"status": "UNREVIEWED_RELATIONSHIP_TEMPLATES", "relationships": views,
                          "human_approved_links": 0}
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
