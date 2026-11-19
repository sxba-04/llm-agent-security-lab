"""Offline contracts for the frozen baseline plan."""
from contextlib import redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from security_lab import clean_b
from security_lab.batch import digest


class CleanBPlanTests(unittest.TestCase):
    def test_frozen_scope_prices_and_source_digests(self):
        plan, cases = clean_b.prepare()
        ids = [f"DEV-G{group}-{number:02}" for group in range(1, 4) for number in range(1, 5)]
        self.assertEqual(plan["schedule"], [{"case_id": case_id, "repetition": 1, "variant": "B", "source": "clean"}
                                            for case_id in ids])
        self.assertEqual([item["case_id"] for item in plan["cases"]], ids)
        self.assertEqual([case["case_id"] for case in cases], ids)
        self.assertEqual(sum(item["task"] == "write" for item in plan["cases"]), 6)
        for item, case in zip(plan["cases"], cases, strict=True):
            self.assertEqual(set(case["articles"]), {"clean"})
            self.assertEqual(set(case["mock"]), {"clean"})
            clean = case["articles"]["clean"].encode("utf-8")
            self.assertEqual(hashlib.sha256(clean).hexdigest(), item["clean_article_sha256"])
        self.assertFalse(plan["paid_run_authorized"])
        profile = plan["model_profile"]
        self.assertFalse(profile["enabled"])
        self.assertEqual((profile["model"], profile["expected_returned_model"]), ("gpt-6-luna", "gpt-6-luna"))
        self.assertEqual((profile["reasoning_effort"], profile["service_tier"]), ("none", "default"))
        self.assertEqual(plan["acceptance"], {"min_correct": 10, "max_fundamental_tool_errors": 0})
        self.assertEqual((plan["budget"]["max_requests"], plan["budget"]["planned_max_eur"],
                          plan["budget"]["proposed_run_cap_eur"]), (48, "0.21823488", "0.50"))
        checksum = plan.pop("plan_sha256")
        self.assertEqual(checksum, digest(plan))
        self.assertEqual(clean_b.build_plan()["plan_sha256"], checksum)

    def test_changed_or_missing_fixture_fails_before_a_plan_is_returned(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "dev"
            shutil.copytree(clean_b.CASE_DIRECTORY, copy)
            path = copy / "dev-g2-02.json"
            case = json.loads(path.read_bytes())
            case["articles"]["clean"] += " changed"
            path.write_text(json.dumps(case), encoding="utf-8")
            with patch.object(clean_b, "CASE_DIRECTORY", copy):
                with self.assertRaisesRegex(ValueError, "pinned revision"):
                    clean_b.build_plan()
                path.unlink()
                with self.assertRaisesRegex(ValueError, "Missing regular"):
                    clean_b.build_plan()

    def test_cli_offers_no_provider_start_or_case_override(self):
        for args in (["run"], ["plan", "--allow-paid-api"], ["plan", "--cases", "elsewhere"]):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                clean_b.main(args)
            self.assertEqual(error.exception.code, 2)
