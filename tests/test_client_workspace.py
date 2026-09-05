from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from energy_mvp.client_workspace import WORKSPACE_DIRECTORIES, create_client_workspace


class ClientWorkspaceTests(unittest.TestCase):
    def test_workspace_is_isolated_and_contains_no_invented_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspaces"
            manifest = create_client_workspace("client_demo", root=root)
            target = root / "client_demo"

            self.assertTrue(all((target / name).is_dir() for name in WORKSPACE_DIRECTORIES))
            self.assertEqual(manifest["status"], "awaiting_privacy_review")
            stored = json.loads((target / "workspace.json").read_text(encoding="utf-8"))
            self.assertEqual(stored["workspace_id"], "client_demo")
            self.assertFalse(stored["investigation_rules"]["ground_truth_available"])
            self.assertEqual(stored["paths"]["client_questions"], "processed/questions.json")
            self.assertEqual(stored["paths"]["incoming"], "incoming/")
            self.assertEqual(stored["paths"]["sanitized"], "sanitized/")
            self.assertTrue(stored["privacy"]["required"])
            self.assertTrue((target / "privacy/CODEX_PRIVACY_REVIEW_TEMPLATE.json").is_file())
            self.assertFalse((target / "questions.json").exists())
            self.assertFalse((target / "human_review.json").exists())

    def test_existing_workspace_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_client_workspace("client_demo", root=root)

            with self.assertRaises(FileExistsError):
                create_client_workspace("client_demo", root=root)

    def test_unsafe_identifier_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                create_client_workspace("../client", root=directory)


if __name__ == "__main__":
    unittest.main()
