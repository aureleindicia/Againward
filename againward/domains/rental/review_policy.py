"""Rental review and delivery: revalidate sources, amounts and explicit decisions."""
from againward.core import review
from againward.core.artifact_store import read_json, artifact_sha256
from againward.core.workflow_paths import resolve_analysis_directory
from againward.evidence.cli import validate_session_artifacts
from againward.evidence.protocol import EvidenceQuerySession, validate_finding_provenance
from .domain_pack import RentalDomainPack
from .findings import review_findings
from .ingestion import build_evidence_dataset


BOUND_ARTIFACTS = ("rental_findings.json", "rental_assessments.json", "prepared_analysis.json",
                   "evidence_dataset.json", "agent_findings.json", "investigation.json", "review.json",
                   "report.md", "rental_evidence_pack.json", "rental_client_report.pdf")


def review_hashes(root):
    return {name: artifact_sha256(root / name) for name in BOUND_ARTIFACTS}


def validate_current_review(case_directory):
    """A changed document, source, amount, decision or evidence snapshot invalidates review."""
    from .workflow import current_calculations
    root = resolve_analysis_directory(case_directory)
    case, calculations = current_calculations(root)
    assessments = read_json(root / "rental_assessments.json")
    if assessments.get("schema_version") != "againward-rental-assessments-v1":
        raise ValueError("Unknown Rental assessment schema.")
    findings = review_findings(case, calculations, assessments["assessments"])
    if findings != read_json(root / "rental_findings.json"):
        raise ValueError("Rental findings are stale or altered.")
    if findings["unreviewed_candidate_ids"]:
        raise ValueError("Every Rental candidate needs an explicit decision, including rejection or abstention.")
    inventory = read_json(root / "artifact_inventory.json")
    dataset = build_evidence_dataset(case, document_lineage=inventory.get("document_lineage"))
    if dataset.to_dict() != read_json(root / "evidence_dataset.json"):
        raise ValueError("Evidence snapshot differs from current Rental sources.")
    session = EvidenceQuerySession.from_dict(read_json(root / "evidence_query_session.json"))
    validate_session_artifacts(root, session, dataset=dataset)
    agent = read_json(root / "agent_findings.json")
    validate_finding_provenance(agent, session)
    by_id = {f["finding_id"]: f for f in findings["findings"]}
    if {f["finding_id"] for f in agent["findings"]} != set(by_id):
        raise ValueError("Agent and Rental finding registers disagree.")
    for f in agent["findings"]:
        if any(f[key] != by_id[f["finding_id"]][key] for key in
               ("status", "claim_or_abstention", "evidence_query_ids", "evidence_handles")):
            raise ValueError("Agent and Rental decisions disagree.")
    investigation = read_json(root / "investigation.json")
    policy = RentalDeliveryPolicy()
    policy.validate_investigation(investigation)
    policy.validate_review(read_json(root / "review.json"), investigation)
    hypotheses = {h["hypothesis_id"]: h for h in investigation["hypotheses"]}
    if set(hypotheses) != set(by_id):
        raise ValueError("Investigation must cover exactly the reviewed Rental candidates.")
    for fid, f in by_id.items():
        h = hypotheses[fid]
        decision = "INSUFFISAMMENT_ETAYE" if f["status"] == "ABSTAIN" else f["status"]
        if h["decision"] != decision or h["results"] != {
                "group_id": f["group_id"], "difference": f["difference"], "currency": f["currency"],
                "recovery_grade_amount": f["recovery_grade_amount"]}:
            raise ValueError("Investigation must use the validated Rental decision and exact calculated amounts.")
        if h.get("evidence_query_ids") != f["evidence_query_ids"] or h.get("evidence_handles") != f["evidence_handles"]:
            raise ValueError("Investigation evidence differs from the finding review.")
    return findings


class RentalDeliveryPolicy:
    def validate_investigation(self, payload):
        review.validate_investigation_document(payload)

    def validate_review(self, payload, investigation):
        review.validate_adversarial_review(payload, investigation, required_checks=set(RentalDomainPack.review_checks))

    def additional_checks(self, case_directory, root):
        reasons = []
        try:
            findings = validate_current_review(root)
            from .reporting import evidence_pack
            if read_json(root / "rental_evidence_pack.json") != evidence_pack(root, findings):
                raise ValueError("Rental evidence pack is stale or altered.")
            human = read_json(root / "human_review.json")
            if human.get("reviewed_artifact_hashes") != review_hashes(root):
                raise ValueError("Human review must bind all current Rental report, review and evidence artifacts.")
        except (OSError, ValueError, KeyError) as exc:
            reasons.append(str(exc))
        return {"blocking_reasons": reasons, "artifact_names": BOUND_ARTIFACTS,
                "report_validation": {"domain": "rental", "valid": not reasons}}

    def update_receipt(self, case_root, *, ready, report_validation):
        # The shared delivery_gate.json is the authoritative receipt.
        pass
