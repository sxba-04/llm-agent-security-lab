"""CI summary output retains actual checkout provenance and failure outcomes."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci_job_summary.py"
SPEC = importlib.util.spec_from_file_location("ci_job_summary", SCRIPT)
summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(summary)


class JobSummaryTests(unittest.TestCase):
    def test_python_summary_appends_real_checkout_and_failure_without_changing_markdown(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "summary.md"
            destination.write_text("Previous step\n", encoding="utf-8")
            environment = {"GITHUB_STEP_SUMMARY": str(destination), "GITHUB_SHA": "not-the-checkout",
                           "RUNNER_OS": "Windows", "LAB_TEST_OUTCOME": "failure",
                           "LAB_CAMPAIGN_OUTCOME": "cancelled"}
            with patch.dict(os.environ, environment), \
                    patch.object(summary.subprocess, "check_output", return_value="actual-checkout\n") as git:
                summary.main(["python-checks"])
            git.assert_called_once_with(["git", "rev-parse", "HEAD"], text=True)
            self.assertEqual(destination.read_text(encoding="utf-8"), (
                "Previous step\n## Python checks on Windows\n\n"
                "- Behavioral tests: **failure**.\n"
                "- Synthetic campaign and archive roundtrip: **cancelled**.\n"
                "- Checked-out commit (PR merge when applicable): `actual-checkout`.\n"
                "- Artifacts expire after 14 days; download evidence you want to keep.\n"))

    def test_mock_summary_entrypoint_keeps_exact_output_and_uses_git_checkout(self):
        checkout = SCRIPT.parents[1]
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=checkout, text=True).strip()
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "summary.md"
            environment = {**os.environ, "GITHUB_STEP_SUMMARY": str(destination),
                           "GITHUB_SHA": "not-the-checkout", "LAB_CAMPAIGN_OUTCOME": "success"}
            process = subprocess.run([sys.executable, str(SCRIPT), "mock-campaign"],
                                     cwd=checkout, env=environment, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(destination.read_text(encoding="utf-8"), (
                "## Job outcome\n\n"
                "- Campaign step: **success**.\n"
                "- Checked-out commit: `" + commit + "`.\n"
                "- This workflow is mock-only and creates no public application endpoint.\n"
                "- Download artifacts within 14 days; they are not a permanent backup.\n"))

    def test_failed_git_does_not_create_or_modify_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "summary.md"
            destination.write_text("Preserve existing evidence\n", encoding="utf-8")
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(destination)}), \
                    patch.object(summary.subprocess, "check_output",
                                 side_effect=subprocess.CalledProcessError(128, ["git"])):
                with self.assertRaises(subprocess.CalledProcessError):
                    summary.main(["mock-campaign"])
            self.assertEqual(destination.read_text(encoding="utf-8"), "Preserve existing evidence\n")

    def test_missing_outcome_keeps_partial_summary_and_does_not_claim_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "summary.md"
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(destination)}, clear=True), \
                    patch.object(summary.subprocess, "check_output", return_value="actual-checkout"):
                with self.assertRaises(KeyError):
                    summary.main(["mock-campaign"])
            self.assertEqual(destination.read_text(encoding="utf-8"), "## Job outcome\n\n")


if __name__ == "__main__":
    unittest.main()
