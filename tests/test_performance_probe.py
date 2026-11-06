"""The resource harness stays bounded and uses the real offline API paths."""
from __future__ import annotations

import importlib.util
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("performance_probe", ROOT / "scripts" / "performance_probe.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class PerformanceProbeTests(unittest.TestCase):
    def test_small_probe_records_valid_listing_pdf_and_concurrency_evidence(self):
        report = probe.execute([1, 2], samples=1, pdf_pages=1, text_characters=1000)
        self.assertTrue(report["engineering_only"])
        self.assertEqual(report["live_model_calls"], 0)
        self.assertEqual([item["campaigns"] for item in report["listing"]], [1, 2])
        self.assertEqual(report["pdf"]["pages"], 1)
        self.assertEqual(report["concurrent_start"]["second_start_status"], 409)
        self.assertGreater(report["long_evidence"]["response_bytes"], 1000)
        self.assertGreater(report["storage"]["file_count"], 20)
        self.assertGreater(report["wall_seconds"], 0)
        self.assertIn("no 512 MiB limit imposed", report["scope"])

    def test_cli_rejects_unbounded_parameters_before_creating_workspace(self):
        for arguments in (["--campaigns", "101"], ["--pdf-pages", "51"],
                          ["--text-characters", "200001"], ["--samples", "0"]):
            with self.subTest(arguments=arguments), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as raised:
                probe.main(arguments)
            self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
