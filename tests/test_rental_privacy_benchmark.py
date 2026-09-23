"""Policy counts include both false blocks and unsafe passes on synthetic files."""
import json

import pytest

from benchmarking.rental_privacy import run_privacy_benchmark


def test_rental_privacy_cases_and_multidocument_source_chain(tmp_path):
    result = run_privacy_benchmark(tmp_path / "run")
    assert result["total"] == result["passed"] == 19, result
    assert result["metrics"] == {"ordinary_expected": 11, "unsafe_expected": 8,
                                 "false_blocks": 0, "unsafe_passes": 0,
                                 "false_block_rate": 0.0, "unsafe_pass_rate": 0.0}
    folder = result["cases"]["ordinary_rental_folder"]["document_chain"]
    assert folder == {"approved_files": 8, "source_documents": 8, "parsed_documents": 8,
                      "privacy_bound": True, "scan_routed": True}
    assert result["cases"]["high_risk_rental_folder"]["failure_code"] == "AUTHENTICATION_SECRET"
    persisted = (tmp_path / "run/validation.json").read_text()
    assert "sk-live" not in persisted and "jean.dupont@" not in persisted
    assert json.loads(persisted)["metrics"] == result["metrics"]
    with pytest.raises(ValueError, match="empty"):
        run_privacy_benchmark(tmp_path / "run")
