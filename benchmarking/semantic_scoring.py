"""Private scorer for model candidates; never imported by the participant."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _equal(left: object, right: object, field: str) -> bool:
    if field in {"rate", "net_amount", "allocated_amount"}:
        try:
            return Decimal(str(left)) == Decimal(str(right))
        except InvalidOperation:
            return False
    return left == right


def score_semantic_candidates(corpus: Path, run: Path) -> dict:
    corpus, run = Path(corpus), Path(run)
    raw = (run / "semantic_observations.json").read_bytes()
    observed_sha = hashlib.sha256(raw).hexdigest()
    if observed_sha != (run / "semantic_observations.sha256").read_text().strip():
        raise ValueError("Participant observations changed before scoring")
    observed = json.loads(raw)
    manifest = json.loads((corpus / "manifest.json").read_text())
    truth_bytes = (corpus / "private/truth.json").read_bytes()
    if hashlib.sha256(truth_bytes).hexdigest() != manifest["truth_sha256"]:
        raise ValueError("Private truth changed after generation")
    truth = json.loads(truth_bytes)
    if observed["split"] != truth["split"] or set(observed["cases"]) != set(truth["cases"]):
        raise ValueError("Split or complete case coverage mismatch")
    if truth["split"] == "HOLDOUT" and not observed["engine"]["clean"]:
        raise ValueError("HOLDOUT participant engine was not frozen")
    total = exact = found = predicted = correct_predictions = failed_documents = 0
    case_scores = {}
    for cid, expected in truth["cases"].items():
        actual = observed["cases"][cid]
        if set(actual["source_hashes"]) != set(expected["source_hashes"].values()):
            raise ValueError("Participant did not inventory all public files")
        by_key: dict[tuple[str, str], list[object]] = {}
        for document in actual["documents"]:
            failed_documents += document["status"] == "ABSTAIN"
            for candidate in document["candidates"]:
                if candidate["source_id"].removeprefix("src-") != document["source_sha256"]:
                    raise ValueError("Candidate source provenance differs from participant receipt")
                by_key.setdefault((document["source_sha256"], candidate["semantic_type"]), []).append(
                    candidate["value"])
        case_total = case_exact = 0
        for annotation in expected["decisive_fields"]:
            case_total += 1
            values = by_key.get((annotation["source_sha256"], annotation["field"]), [])
            case_exact += len(values) == 1 and _equal(values[0], annotation["value"], annotation["field"])
            found += bool(values)
            predicted += len(values)
            correct_predictions += sum(_equal(value, annotation["value"], annotation["field"])
                                       for value in values)
        total += case_total
        exact += case_exact
        case_scores[cid] = {"annotated_fields": case_total, "exact_fields": case_exact,
                            "documents": len(actual["documents"]),
                            "failures": [row["failure_code"] for row in actual["documents"]
                                         if row["failure_code"]]}
    result = {"schema_version": "againward-semantic-score-v1", "split": truth["split"],
              "participant": observed["participant"], "observations_sha256": observed_sha,
              "metrics": {"cases": len(case_scores), "annotated_fields": total,
                          "annotated_fields_found": found, "annotated_fields_exact": exact,
                          "annotated_field_exact_recall": _ratio(exact, total),
                          "annotated_value_precision": _ratio(correct_predictions, predicted),
                          "document_failures": failed_documents,
                          "financial_finding_precision": None,
                          "supported_discrepancy_recall": None,
                          "human_review_decisions": 0},
              "cases": case_scores,
              "limits": ["Only private decisive-field annotations are scored; other candidate fields are unscored.",
                         "A semantically correct quoted field is not a reviewed relationship or financial finding.",
                         "No human review or client-facing positive claim is made in this participant run."]}
    destination = run / "semantic_score.json"
    if destination.exists():
        raise ValueError("Prior semantic score cannot be overwritten")
    destination.write_text(json.dumps(result, indent=2) + "\n")
    return result
