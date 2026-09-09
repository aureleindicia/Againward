from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "prepare.py"
SPEC = importlib.util.spec_from_file_location("prospecting_prepare", MODULE_PATH)
assert SPEC and SPEC.loader
prepare_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare_module)


def prospect(identifier: str, entity_key: str) -> dict[str, object]:
    return {
        "prospect_id": identifier,
        "entity_key": entity_key,
        "name": identifier,
        "sector": "test",
        "discovered_at": "2026-08-28",
        "prequalification_status": "CANDIDATE",
        "facts": [{
            "field": "activity", "value": "atelier", "source_id": "S1",
            "observed_at": "2026-08-28", "confidence": "high",
        }],
        "inferences": [{
            "statement": "inférence explicitement séparée", "basis_source_ids": ["S1"], "confidence": "low",
        }],
        "sources": [{
            "source_id": "S1", "title": "source", "url": "https://example.test/source",
            "retrieved_at": "2026-08-28", "source_type": "company_website", "confidence": "high",
        }],
        "missing_information": [],
        "negative_signals": [],
        "related_entities": [],
    }


class ProspectPreparationTests(unittest.TestCase):
    def test_exact_entity_duplicates_merge_with_trace(self) -> None:
        first = prospect("P1", "ateliertest")
        second = prospect("P2", "ateliertest")
        merged, audit = prepare_module._merge_records([first, second])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["merged_from_prospect_ids"], ["P1", "P2"])
        self.assertEqual(audit[0]["action"], "merged_exact_entity_key")

    def test_scoring_field_is_refused_before_scoring_phase(self) -> None:
        payload = {"prospects": [prospect("P1", "ateliertest")]}
        payload["prospects"][0]["score"] = 90
        with self.assertRaisesRegex(ValueError, "Champ interdit avant scoring"):
            prepare_module._assert_no_scoring_fields(payload)

    def test_preparation_keeps_candidates_and_rejections_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.json"
            opposition = root / "opposition.json"
            candidate = prospect("P1", "ateliertest")
            rejected = prospect("P2", "microatelier")
            rejected["prequalification_status"] = "REJECTED"
            rejected["negative_signals"] = [{"kind": "too_small", "detail": "taille observée faible", "source_id": "S1"}]
            raw.write_text(json.dumps({"prospects": [candidate, rejected]}), encoding="utf-8")
            opposition.write_text(json.dumps({"oppositions": []}), encoding="utf-8")

            old_data = prepare_module.DATA
            try:
                prepare_module.DATA = root
                summary = prepare_module.prepare(raw, opposition)
            finally:
                prepare_module.DATA = old_data

            self.assertFalse(summary["scoring_performed"])
            self.assertEqual(summary["counts"], {"CANDIDATE": 1, "REJECTED": 1})
            self.assertEqual(len(json.loads((root / "candidates_pre_scoring.json").read_text())["prospects"]), 1)
            self.assertEqual(len(json.loads((root / "rejected_prequalification.json").read_text())["prospects"]), 1)



    def test_preparation_can_write_an_isolated_research_batch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.json"
            opposition = root / "opposition.json"
            output = root / "international_batch"
            raw.write_text(json.dumps({"prospects": [prospect("P1", "ateliertest")]}), encoding="utf-8")
            opposition.write_text(json.dumps({"oppositions": []}), encoding="utf-8")
            prepare_module.prepare(raw, opposition, output)
            self.assertTrue((output / "candidates_pre_scoring.json").is_file())
            self.assertFalse((root / "candidates_pre_scoring.json").exists())


if __name__ == "__main__":
    unittest.main()
