"""Generic Rental integration into the shared investigation kernel."""
from __future__ import annotations

from againward.core.domain import DomainPreparation
from againward.evidence.plane import relationship_loss_certificate
from againward.evidence.protocol import query_contract
from .ingestion import load_rental_case, build_evidence_dataset
from .profiles import get_profile
from .reconciliation import reconcile, FINDING_FAMILIES


class RentalDomainPack:
    name = "rental"
    review_checks = ("calculations", "data_quality", "contract_authority", "timeline",
                     "alternative_explanations", "recoverability", "double_counting", "currency")

    def __init__(self, *, profile=None):
        self.profile = get_profile(profile)

    @property
    def privacy_preservation(self):
        from .privacy_policy import RENTAL_PRESERVATION
        return RENTAL_PRESERVATION

    def intake_template(self):
        return {"schema_version": "againward-rental-intake-v1", "domain": self.name,
                "profile": self.profile.name, "scope": None, "supplier_ids": [],
                "source_conventions_reviewed": False, "contract_completeness": "UNKNOWN"}

    def delivery_policy(self):
        from .review_policy import RentalDeliveryPolicy
        return RentalDeliveryPolicy()

    def prepare(self, source, *, source_sha256, intake, options, evidence_plane_mode):
        if evidence_plane_mode != "preferred":
            raise ValueError("Rental has no legacy or shadow numerical engine; use preferred mode.")
        if options.get("default_tariff") is not None:
            raise ValueError("Energy tariffs do not apply to Rental.")
        if intake.get("profile", self.profile.name) != self.profile.name:
            raise ValueError("Rental intake profile differs from explicitly selected profile.")
        case, inventory = load_rental_case(source)
        result = reconcile(case)
        dataset = build_evidence_dataset(case)
        gaps = sorted({gap for group in result["groups"] for gap in group["limitations"]})
        assessment = {"missing_critical": gaps, "automatic_questions": False,
                      "limits": ["Semantic document extraction requires analyst review.",
                                 "No discrepancy is automatically a recoverable claim."]}
        candidates = {"status": "candidate_signals_only", "events": result["candidates"],
                      "zero_candidates_means": "No candidate emitted; completeness still requires analyst review."}
        context = {"schema_version": "againward-rental-context-v1", "domain": "rental", "profile": self.profile.name,
                   "finding_families": sorted(FINDING_FAMILIES),
                   "profile_hints": [{"item_id": item.item_id, **self.profile.suggest_category(item.description)} for item in case.items],
                   "likely_charge_types": list(self.profile.likely_charge_types),
                   "operational_checks": list(self.profile.operational_checks),
                   "tools": ["build_expected_ledger", "build_actual_ledger", "reconcile", "resolve_timeline",
                             "query_evidence.py", "manage_investigation.py"],
                   "evidence_levels": {"L1": "signal", "L2": "supported discrepancy", "L3": "recovery-grade after explicit review"}}
        artifacts = {"rental_case.json": case.to_dict(), "artifact_inventory.json": inventory,
                     "prepared_analysis.json": result, "expected_charge_ledger.json": result["expected_ledger"],
                     "actual_charge_ledger.json": result["actual_ledger"], "candidate_signals.json": candidates,
                     "intake_assessment.json": assessment, "domain_context.json": context}
        return DomainPreparation({"dataset": {"rows": len(dataset.rows), "documents": len(case.documents)},
            "candidate_detection": candidates, "intake_assessment": assessment,
            "profile": self.profile.name,
            "prohibited_shortcuts": ["numeric_gap_as_recoverable_claim", "collection_request_as_signed_return",
                                     "unknown_terms_as_zero", "sum_overlapping_finding_families"]},
            artifacts, dataset, trace_details={"canonical_schema": case.to_dict()["schema_version"],
                                             "source_extraction_sha256": source_sha256})

    def evidence_card(self, preparation, session):
        dataset = preparation.evidence_dataset
        candidates = preparation.state["candidate_detection"]["events"]
        return {"schema_version": "againward-rental-evidence-card-v1", "status": "initial_evidence_not_a_conclusion",
            "dataset": {"dataset_id": dataset.dataset_id, "dataset_sha256": dataset.dataset_sha256,
                        "rows": len(dataset.rows)}, "field_inventory": dataset.fields,
            "candidate_overview": [{k: c[k] for k in ("finding_id", "family", "group_id", "evidence_level")} for c in candidates[:25]],
            "candidate_count": len(candidates), "candidate_overview_truncated": len(candidates) > 25,
            "relationship_loss": relationship_loss_certificate(sorted(dataset.field_keys), omitted_examples_limit=10),
            "query_capabilities": query_contract()["operations"],
            "retrieval": {"session_id": session.session_id, "dataset_snapshot": "evidence_dataset.json",
                          "request_command": "python query_evidence.py CASE_DIRECTORY REQUEST.json"},
            "decision": None}

    def analyst_brief(self, state):
        return """# Rental investigation — analyst brief

Read artifact_inventory.json, rental_case.json and both charge ledgers before
selecting hypotheses. Python has calculated discrepancies only, not claims.
Inspect evidence_card.json, then request bounded source/contrast queries through
query_evidence.py. Verify quantities, dates, accepted rates, amendments, credit
allocation and the strongest alternative explanation for each material candidate.

Missing contractual conventions remain unknown. L1 signals and L2 discrepancies
are not recovery-grade. Different finding families can reference the same charge
group; use its amount once. Never combine currencies or treat a requested
collection as signed possession without contractual and operational evidence.

Exhaust existing sources before a bounded question. Publish a BLOCKING request
only when its answer can change a material decision; STOP in WAITING, then record
the answer, recalculate, review and complete RESUME. Explicit abstention is valid.
The final deliverable requires adversarial and human review. Construction profile
hints enrich vocabulary only; they do not change arithmetic or lifecycle.
"""
