"""Energy review and delivery extensions; no Energy assumptions in shared gates."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from againward.core import review
from againward.core.delivery import _read_json, _write_json
from energy_mvp.recommendations import validate_recommendations

DECISIONS = {
    "CONFIRME",
    "A_CONSERVER_AVEC_RESERVES",
    "INSUFFISAMMENT_ETAYE",
    "REJETE",
}
REVIEW_CHECKS = {
    "calculations",
    "data_quality",
    "baseline_robustness",
    "alternative_explanations",
    "causality",
    "annualization",
    "recoverable_saving",
    "double_counting",
}
REVIEW_CHECK_STATUSES = {"passed", "failed", "not_applicable"}


def _physical_status(hypothesis):
    if not str(hypothesis.get("physical_cause_status", "")).strip():
        raise ValueError(f"{hypothesis.get('hypothesis_id')}: statut de cause physique absent.")


class EnergyDeliveryPolicy:
    def validate_investigation(self, payload):
        review.validate_investigation_document(payload, hypothesis_validator=_physical_status,
                                               recommendation_validator=validate_recommendations)

    def validate_review(self, payload, investigation):
        review.validate_adversarial_review(payload, investigation, required_checks=REVIEW_CHECKS)

    def additional_checks(self, case_directory, root):
        reasons = []
        evidence_artifacts = ()
        economic_path = root / "economic_decision_state.json"
        if economic_path.is_file() and _read_json(economic_path).get("value_assessment"):
            from value_map import validate_value_map_human_review
            from againward.core.workflow_paths import resolve_case_layout
            try:
                human = _read_json(root / "human_review.json") if (root / "human_review.json").exists() else {}
                validate_value_map_human_review(Path(resolve_case_layout(case_directory)["case_root"]), human)
            except (OSError, ValueError) as exc:
                reasons.append(str(exc))
            evidence_artifacts += ("economic_decision_state.json", "value_map.json")
        from againward.core.workflow_paths import resolve_case_layout
        from againward.core.privacy import privacy_requirement
        case_root = Path(resolve_case_layout(case_directory)["case_root"])
        design_path = case_root / "outputs/client_report/REPORT_DESIGN_MODEL.json"
        report_validation = None
        if privacy_requirement(case_directory)["required"] or design_path.exists():
            from report_design import validate_report_delivery_artifacts
            try:
                human = _read_json(root / "human_review.json") if (root / "human_review.json").exists() else {}
                report_validation = validate_report_delivery_artifacts(case_root, human)
            except (OSError, ValueError) as exc:
                reasons.append(str(exc))
        return {"blocking_reasons": reasons, "artifact_names": evidence_artifacts,
                "report_validation": report_validation}

    def update_receipt(self, case_root, *, ready, report_validation):
        receipt_path = case_root / "outputs/client_report/CLIENT_REPORT_DELIVERY.json"
        if receipt_path.is_file():
            try:
                receipt = _read_json(receipt_path)
            except (OSError, ValueError):
                receipt = None  # Preserve malformed evidence; the gate remains blocked.
            if isinstance(receipt, dict) and receipt.get("renderer") == "againward_agent_composition_v1":
                # A failed semantic/reproducibility check must revoke a previous receipt too.
                approved = ready and report_validation is not None
                receipt["approved_for_delivery"] = approved
                receipt["status"] = "DELIVERABLE" if approved else "BLOCKED_BY_DELIVERY_GATE"
                _write_json(receipt_path, receipt)
