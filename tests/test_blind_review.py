from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from energy_mvp.blind_review import validate_blind_session_review


class BlindReviewTests(unittest.TestCase):
    def test_review_requires_no_truth_declaration_and_known_public_case(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = root / "normal"
            case.mkdir()
            (case / "investigation_state.json").write_text("{}", encoding="utf-8")
            payload = {
                "session_id": "S1", "ground_truth_accessed": False,
                "cases": [{"case_name": "normal", "hypotheses": [], "questions_to_client": []}],
            }
            validate_blind_session_review(payload, root)
            payload["ground_truth_accessed"] = True
            with self.assertRaisesRegex(ValueError, "ground_truth_accessed"):
                validate_blind_session_review(payload, root)


if __name__ == "__main__":
    unittest.main()
