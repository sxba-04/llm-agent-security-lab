"""Workflow entry-point boundaries; no real model transport is involved."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "ci_mock_campaign", Path(__file__).resolve().parents[1] / "scripts" / "ci_mock_campaign.py")
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)


class MockWorkflowTests(unittest.TestCase):
    def test_untrusted_dispatch_values_are_rejected_before_any_effect(self):
        for preset, repeats in [("openai", "1"), ("demo24", "0"), ("catalog96", "4"),
                                ("demo24; echo injected", "1"), ("catalog96", "1; echo injected")]:
            with self.subTest(preset=preset, repeats=repeats), tempfile.TemporaryDirectory() as temporary:
                destination = Path(temporary) / "output"
                with patch.dict(os.environ, {"LAB_MOCK_PRESET": preset, "LAB_MOCK_REPEATS": repeats}), \
                        patch.object(ci, "_cli") as run:
                    with self.assertRaises(SystemExit) as error:
                        ci.main(["--output", str(destination)])
                    self.assertEqual(error.exception.code, 2)
                    run.assert_not_called()
                self.assertFalse(destination.exists())

    def test_existing_evidence_is_never_cleared_or_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "existing"
            destination.mkdir()
            original = destination / "original.bin"
            original.write_bytes(b"preserve the prior experiment")
            with patch.object(ci, "_cli") as run:
                self.assertEqual(ci.main(["--preset", "demo24", "--repeats", "1", "--output", str(destination)]), 1)
                run.assert_not_called()
            self.assertEqual(original.read_bytes(), b"preserve the prior experiment")
            self.assertEqual(list(destination.iterdir()), [original])

    def test_failed_cli_keeps_non_success_report_and_propagates_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "output"
            summary = Path(temporary) / "job.md"
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}), \
                    patch.object(ci, "_cli", side_effect=subprocess.CalledProcessError(2, ["mock"])):
                self.assertEqual(ci.main(["--preset", "catalog96", "--repeats", "3", "--output", str(destination)]), 1)
            result = json.loads((destination / "result.json").read_text(encoding="utf-8"))
            self.assertFalse(result["completed"])
            self.assertEqual(result["planned_runs"], 288)
            self.assertNotIn("archive_sha256", result)
            self.assertFalse((destination / "campaign.zip").exists())
            self.assertIn("Incomplete or failed", summary.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
