"""Scorer-only private truth access, after participant observations are frozen."""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def score_documents(corpus: Path, run: Path) -> dict:
    corpus, run = Path(corpus), Path(run)
    data = (run / "observations.json").read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != (run / "observations.sha256").read_text().strip():
        raise ValueError("Frozen observations changed before scoring")
    observed = json.loads(data)
    manifest = json.loads((corpus / "manifest.json").read_text())
    truth_bytes = (corpus / "private/truth.json").read_bytes()
    if hashlib.sha256(truth_bytes).hexdigest() != manifest["truth_sha256"]:
        raise ValueError("Generator truth changed after corpus freeze")
    truth = json.loads(truth_bytes)
    if observed["split"] != truth["split"] or set(observed["cases"]) != set(truth["cases"]):
        raise ValueError("Split or complete case coverage mismatch")
    if truth["split"] == "HOLDOUT" and not observed["engine"]["clean"]:
        raise ValueError("Cannot score a dirty-engine HOLDOUT")
    tp = fp = fn = tn = exact = abstain_correct = abstain_total = 0
    field_found = field_correct = field_total = numeric_found = numeric_correct = 0
    facts_count = provenance_count = 0
    cases = {}
    for cid, expected in truth["cases"].items():
        actual = observed["cases"][cid]
        if set(actual["source_hashes"]) != set(expected["source_hashes"].values()):
            raise ValueError("Participant did not observe the full source set")
        amounts = actual["supported_discrepancy"]
        reference = expected["expected_supported_discrepancy"]
        positive = amounts is not None and any(Decimal(v) > 0 for v in amounts.values())
        should_positive = reference is not None and any(Decimal(v) > 0 for v in reference.values())
        tp += positive and should_positive
        fp += positive and not should_positive
        fn += not positive and should_positive
        tn += not positive and not should_positive
        exact += amounts == reference
        if expected["must_abstain"]:
            abstain_total += 1
            # Returning a numeric zero for unknown is not a correct abstention.
            abstain_correct += amounts is None
        by_key = {}
        for f in actual["facts"]:
            c = f["candidate"]
            by_key.setdefault((c["source_id"].removeprefix("src-"), c["semantic_type"]), set()).add(c["value"])
        for annotation in expected["decisive_fields"]:
            field_total += 1
            values = by_key.get((annotation["source_sha256"], annotation["field"]), set())
            field_found += bool(values)
            if annotation["field"] == "rate":
                numeric_found += bool(values)
                correct = len(values) == 1 and Decimal(next(iter(values))) == Decimal(annotation["value"])
                numeric_correct += correct
            else:
                correct = values == {annotation["value"]}
            field_correct += correct
        facts_count += len(actual["facts"])
        provenance_count += len(actual["facts"]) if actual["source_chain_validated"] else 0
        cases[cid] = {"family": expected["family"], "status": actual["status"],
                      "exact_financial_match": amounts == reference,
                      "expected": reference, "observed": amounts}
    report = {"schema_version": "againward-document-score-v1", "split": truth["split"],
              "observations_sha256": digest, "participant": observed["participant"], "cases": cases,
              "metrics": {"true_positives": tp, "false_positives": fp, "false_negatives": fn, "true_negatives": tn,
                          "supported_discrepancy_precision": _ratio(tp, tp + fp),
                          "supported_discrepancy_recall": _ratio(tp, tp + fn),
                          "financial_exact_cases": exact, "total_cases": len(cases),
                          "abstention_correct": abstain_correct, "abstention_required": abstain_total,
                          "annotated_field_precision": _ratio(field_correct, field_found),
                          "annotated_field_recall": _ratio(field_correct, field_total),
                          "numeric_exact_match": _ratio(numeric_correct, numeric_found),
                          "canonical_fact_retrievable_support": _ratio(provenance_count, facts_count),
                          "date_exact_match": None, "entity_pair_precision": None, "entity_pair_recall": None,
                          "false_financial_claim_rate": None, "double_count_rate": None,
                          "retained_finding_chain_completeness": None, "lifecycle_correctness": None,
                          "manual_decisions": sum(r["manual_decisions"] for r in observed["cases"].values())},
              "limits": ["Only the declared decisive-field subset is annotated; other extracted fields are not scored.",
                         "Null means unmeasured or no denominator, never perfect accuracy.",
                         "Routing baseline abstention is not a successful document-intelligence benchmark.",
                         "Case-level discrepancies are not recovery-grade claims or retained findings.",
                         "Holdout separation is procedural, not a filesystem sandbox or independent blind evaluation."]}
    destination = run / "score.json"
    if destination.exists():
        raise ValueError("Score already exists; do not overwrite a prior evaluation")
    destination.write_text(json.dumps(report, indent=2) + "\n")
    return report
