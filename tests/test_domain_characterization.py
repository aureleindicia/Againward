"""Frozen pre-migration Energy semantics, independent of the future adapter."""
import hashlib
import json
from pathlib import Path

import pytest

from energy_mvp.analysis import analyze
from energy_mvp.evidence_plane import EvidenceDataset
from energy_mvp.io import load_data
from energy_mvp.report import render_markdown, write_json


FIXTURES = Path(__file__).parent / "fixtures/domain_kernel"


@pytest.mark.parametrize("name,source,tariff", [
    ("monthly", "examples/sample_energy.csv", None),
    ("demo", "examples/demo_15min.csv", 0.175),
])
def test_energy_reports_match_pre_migration_bytes(tmp_path, name, source, tariff):
    result = analyze(load_data(source), source=source, default_tariff=tariff)
    target = tmp_path / "report.json"
    write_json(result, target)
    for extension, content in [("json", target.read_bytes()),
                               ("md", render_markdown(result).encode())]:
        expected = (FIXTURES / f"energy_{name}.{extension}.sha256").read_text().strip()
        assert hashlib.sha256(content).hexdigest() == expected


def test_energy_snapshot_and_quarter_hour_units_match_frozen_contract(tmp_path):
    source = tmp_path / "records.csv"
    source.write_text("timestamp,power_kw,production_active,machine_mode\n"
                      "2026-01-01T00:00:00,100,false,idle\n"
                      "2026-01-01T00:15:00,100,false,idle\n")
    loaded = load_data(source)
    assert [r.energy_kwh for r in loaded.readings] == [25, 25]
    dataset = EvidenceDataset.from_loaded_data(
        loaded, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    expected = json.loads((FIXTURES / "energy_snapshot_v1.json").read_text())
    assert dataset.to_dict() == expected
    assert EvidenceDataset.from_dict(expected).to_dict() == expected
