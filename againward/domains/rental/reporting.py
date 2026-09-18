"""Minimal evidence export; analyst-authored synthesis remains mandatory."""
from pathlib import Path
from againward.core.artifact_store import read_json, write_json, transaction
from againward.core.client_lifecycle import assert_workflow_action_allowed
from againward.core.workflow_paths import resolve_analysis_directory
from againward.evidence.hashing import stable_hash


def evidence_pack(root, findings):
    return {"schema_version": "againward-rental-evidence-pack-v1", "ground_truth_used": False,
            "findings": findings, "documents": read_json(root / "artifact_inventory.json")["documents"],
            "charge_groups": read_json(root / "prepared_analysis.json")["groups"],
            "dataset_sha256": read_json(root / "evidence_dataset.json")["dataset_sha256"],
            "review_sha256": stable_hash(read_json(root / "review.json")),
            "investigation_sha256": stable_hash(read_json(root / "investigation.json")),
            "policy": "Claim basis only; human approval and shared delivery gate remain required."}


def render_report(case_directory, synthesis):
    """Compose supplied analyst prose with immutable calculated evidence tables.

    Natural-language claims still require human review. No automatic executive
    narrative, legal entitlement or recovery forecast is generated here.
    """
    from .review_policy import validate_current_review, review_hashes
    root = resolve_analysis_directory(case_directory)
    assert_workflow_action_allowed(root, "report_generation")
    if not isinstance(synthesis, str) or not synthesis.strip():
        raise ValueError("Provide the analyst's executive synthesis and recommended next actions.")
    with transaction(root):
        findings = validate_current_review(root)
        write_json(root / "rental_evidence_pack.json", evidence_pack(root, findings))
    lines = ["# Rental investigation", "", synthesis.strip(), "", "## Calculated discrepancies", "",
             "Amounts are net of tax. Repeated group IDs share one discrepancy; do not add finding rows.", "",
             "| Finding | Family | Decision | Grade | Currency | Discrepancy | Claim basis |",
             "|---|---|---|---|---|---:|---:|"]
    for f in findings["findings"]:
        lines.append("| " + " | ".join(str(f[k]) if f[k] is not None else "Unknown" for k in
            ("finding_id", "family", "status", "evidence_level", "currency", "difference", "recovery_grade_amount")) + " |")
    lines += ["", "## Claim basis without overlap", "", str(findings["recovery_grade_totals_by_currency"]),
              "", "This evidence-grade amount is not a guarantee of recovery.", "", "## Evidence and limitations", ""]
    for f in findings["findings"]:
        lines += [f"### {f['finding_id']} ({f['group_id']})", f["claim_or_abstention"],
                  "Best alternative: " + f["best_reason_false"], "Limits: " + "; ".join(f["limitations"]),
                  "Open questions: " + "; ".join(f["unresolved_questions"]),
                  "Evidence: " + ", ".join(f["evidence_handles"]), ""]
    target = root / "report.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"report": str(target), "evidence_pack": str(root / "rental_evidence_pack.json"),
            "reviewed_artifact_hashes": review_hashes(root), "approved_for_delivery": False}
