from __future__ import annotations

from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
DEV_CASE_IDS = (
    "case_a17", "case_b42", "case_c08", "case_d31", "case_e55", "case_f63",
    "case_g14", "case_h27", "case_j90", "case_k22", "case_l48", "case_m76",
    "case_n05", "case_p39", "case_q81", "case_r24", "case_s67", "case_t12",
)


def test_candidate_analytical_and_knowledge_files_contain_no_dev_case_ids() -> None:
    files = [
        REPOSITORY / "energy_mvp" / "physical_diagnostics.py",
        REPOSITORY / "energy_mvp" / "physical_tools.py",
        REPOSITORY / "docs" / "PHYSICAL_DIAGNOSTICS.md",
        *(REPOSITORY / "knowledge" / "physical_diagnostics").glob("*"),
    ]
    for path in files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").casefold()
        for case_id in DEV_CASE_IDS:
            assert case_id not in text, f"Hardcoding DEV détecté dans {path}: {case_id}"
