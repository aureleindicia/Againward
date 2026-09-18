import json
from pathlib import Path

import pytest

from againward.core.domain import DomainPreparation
from againward.core.workflow import prepare_investigation
from againward.core.workspace import create_client_workspace
from againward.entrypoints import get_domain
from againward.evidence.dataset import EvidenceDataset


def test_energy_pack_produces_existing_analysis_through_shared_workflow(tmp_path):
    from energy_mvp.workflow import prepare_investigation as legacy
    source = Path("examples/sample_energy.csv")
    routed = prepare_investigation(source, tmp_path / "routed", domain=get_domain("energy"))
    old = legacy(source, tmp_path / "legacy")
    assert routed["domain"] == "energy"
    assert routed["client_lifecycle"]["state"] == "ANALYZING"
    for name in ["prepared_analysis.json", "candidate_signals.json", "evidence_dataset.json",
                 "evidence_card.json", "review_template.json", "intake_assessment.json"]:
        assert json.loads((tmp_path / "routed" / name).read_text()) == json.loads((tmp_path / "legacy" / name).read_text())
    assert routed["dataset"] == old["dataset"]


def test_unknown_domain_is_never_silently_assumed():
    with pytest.raises(ValueError, match="Unknown domain"):
        get_domain("maybe_energy")


def test_workspace_domain_mismatch_is_refused_before_parsing(tmp_path):
    create_client_workspace("case", root=tmp_path, synthetic=True,
                            domain_name="rental", intake_payload={})
    source = tmp_path / "case/sanitized/source.csv"
    source.write_text("not parseable")
    with pytest.raises(ValueError, match="domain differs"):
        prepare_investigation(source, tmp_path / "case/processed", domain=get_domain("energy"))


class OtherDomain:
    name = "documents"
    review_checks = ("calculations", "source_authority")

    def intake_template(self): return {}

    def prepare(self, source, *, source_sha256, intake, options, evidence_plane_mode):
        dataset = EvidenceDataset.from_records(dataset_id="docs",
            records=[{"source_row": 1, "title": source.read_text()}],
            fields=[{"key": "source_row", "data_type": "integer"}, {"key": "title", "data_type": "string"}],
            provenance={"sources": [{"source_id": "D1", "sha256": source_sha256}],
                        "rows": {"1": [{"source_id": "D1", "location": "line:1"}]}})
        return DomainPreparation({"dataset": {"rows": 1}}, {}, dataset)

    def evidence_card(self, preparation, session):
        return {"dataset_id": preparation.evidence_dataset.dataset_id, "decision": None}

    def analyst_brief(self, state): return "Choose and test documentary hypotheses."


def test_new_domain_runs_without_physical_fields_or_core_modification(tmp_path):
    source = tmp_path / "document.txt"
    source.write_text("Documentary evidence")
    output = tmp_path / "case"
    state = prepare_investigation(source, output, domain=OtherDomain())
    assert state["domain"] == "documents"
    assert state["client_lifecycle"]["state"] == "ANALYZING"
    assert not (output / "physical_differential_template.json").exists()
    assert json.loads((output / "review_template.json").read_text())["required_checks"] == list(OtherDomain.review_checks)
    assert json.loads((output / "questions.json").read_text())["questions"] == []
