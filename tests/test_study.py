import copy
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from security_lab.batch import run_batch, write_json
from security_lab.cases import load_cases
from security_lab.models import ScriptedModel
from security_lab.study import (export_part_cases, link_campaigns, main, make_plan,
                                preflight, validate_plan, verify_study)


ROOT = Path(__file__).parents[1]
FROZEN_CODE = {"git_commit": "c" * 40, "source_sha256": {"src/security_lab/core.py": "a" * 64,
    "uv.lock": "b" * 64, "pyproject.toml": "d" * 64, ".python-version": "e" * 64}}
TEST_CONFIG = {
    "enabled": True, "model": "synthetic-test-model", "max_completion_tokens": 100,
    "max_input_tokens": 20000, "max_requests": 24, "input_eur_per_million": "1",
    "output_eur_per_million": "2", "run_budget_eur": "1",
    "price_reference": "invented test prices, not provider pricing", "price_checked_on": "2026-11-06",
}


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cases = load_cases(ROOT / "cases/dev")[:2]
        for target in ("security_lab.study.provenance", "security_lab.batch.provenance"):
            mocked = patch(target, return_value=FROZEN_CODE)
            mocked.start()
            self.addCleanup(mocked.stop)

    def execute_parts(self, plan):
        paths = []
        for part in plan["parts"]:
            path = self.root / part["part_id"]
            subset = [case for case in plan["cases"] if case["case_id"] in part["case_ids"]]
            run_batch(subset, path, ScriptedModel, variants=plan["variants"], sources=plan["sources"],
                      repeats=plan["repeats"], seed=part["order_seed"], provider_config=plan["provider_config"])
            paths.append(path)
        return paths

    def test_720_run_plan_keeps_every_case_block_together(self):
        cases = []
        for index in range(30):
            case = copy.deepcopy(self.cases[0])
            case["case_id"] = f"DEV-G1-{index + 1:02d}"
            cases.append(case)
        plan = make_plan(cases, name="Preparation only", repeats=3)
        self.assertEqual(plan["planned_runs"], 720)
        self.assertEqual([part["planned_runs"] for part in plan["parts"]], [480, 240])
        self.assertFalse(plan["main_experiment_approved"])
        self.assertEqual(len({cid for p in plan["parts"] for cid in p["case_ids"]}), 30)
        self.assertEqual(plan["parts"], make_plan(list(reversed(cases)), name="Preparation only", repeats=3)["parts"])
        validate_plan(plan)

    def test_invalid_partition_and_duplicate_cases_rejected(self):
        for options in ({"max_part_runs": 481}, {"max_part_runs": 8, "repeats": 2}, {"repeats": 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                make_plan(self.cases, name="Test", **options)
        with self.assertRaises(ValueError):
            make_plan([self.cases[0], self.cases[0]], name="Test")

    def test_frozen_case_export_is_readable_and_never_overwrites(self):
        plan = make_plan(self.cases, name="Test", repeats=1, max_part_runs=8)
        target = self.root / "cases"
        export_part_cases(plan, "part-01", target)
        self.assertEqual(load_cases(target), plan["cases"][:1])
        with self.assertRaises(FileExistsError):
            export_part_cases(plan, "part-01", target)
        with self.assertRaisesRegex(ValueError, "Unknown study part"):
            export_part_cases(plan, "part-99", self.root / "unknown")

    def test_link_and_restore_verify_all_originals_without_recounting_copies(self):
        plan = make_plan(self.cases, name="Test", repeats=1, max_part_runs=8)
        paths = self.execute_parts(plan)
        linked = link_campaigns(plan, paths)
        self.assertEqual(linked["recorded_runs"], 16)
        self.assertTrue(linked["execution_complete"])
        self.assertTrue(linked["engineering_only"])
        copies = [self.root / (path.name + "-restored") for path in paths]
        for path, target in zip(paths, copies):
            shutil.copytree(path, target)
        self.assertTrue(verify_study(plan, linked, copies)["verified_integrity"])
        with self.assertRaises(ValueError):
            link_campaigns(plan, [paths[0], paths[0]])
        with self.assertRaises(ValueError):
            link_campaigns(plan, list(reversed(paths)))

    def test_modified_schedule_case_provider_and_code_rejected(self):
        plan = make_plan(self.cases[:1], name="Test", repeats=1)
        paths = self.execute_parts(plan)
        manifest_path = paths[0] / "manifest.json"
        original = json.loads(manifest_path.read_text())
        changes = {"order_seed": -1, "cases_sha256": "wrong", "provider_config": {}, "provenance": {},
                   "schedule": list(reversed(original["schedule"]))}
        for key, value in changes.items():
            with self.subTest(field=key):
                changed = {**original, key: value}
                write_json(manifest_path, changed)
                with self.assertRaises(ValueError):
                    link_campaigns(plan, paths)
        write_json(manifest_path, original)
        self.assertTrue(link_campaigns(plan, paths)["evidence_complete"])

    def test_study_detects_added_and_modified_evidence(self):
        plan = make_plan(self.cases[:1], name="Test", repeats=1)
        paths = self.execute_parts(plan)
        linked = link_campaigns(plan, paths)
        (paths[0] / "extra.txt").write_text("new note")
        with self.assertRaises(ValueError):
            verify_study(plan, linked, paths)
        (paths[0] / "extra.txt").unlink()
        record = next((paths[0] / "records").glob("*.json"))
        value = json.loads(record.read_text())
        value["final_text"] = "modified"
        write_json(record, value)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            verify_study(plan, linked, paths)

    def test_incomplete_campaign_stays_incomplete(self):
        plan = make_plan(self.cases[:1], name="Cancelled study", repeats=1)
        path = self.root / "cancelled"
        run_batch(plan["cases"], path, ScriptedModel, variants=plan["variants"], sources=plan["sources"],
                  seed=plan["parts"][0]["order_seed"], provider_config=plan["provider_config"], should_cancel=lambda: True)
        linked = link_campaigns(plan, [path])
        self.assertFalse(linked["execution_complete"])
        self.assertEqual(linked["recorded_runs"], 0)
        self.assertTrue(verify_study(plan, linked, [path])["verified_integrity"])

    def test_running_campaign_cannot_be_linked(self):
        plan = make_plan(self.cases[:1], name="Running", repeats=1)
        paths = self.execute_parts(plan)
        value = json.loads((paths[0] / "manifest.json").read_text())
        value["state"] = "running"
        write_json(paths[0] / "manifest.json", value)
        with self.assertRaisesRegex(ValueError, "Finish or cancel"):
            link_campaigns(plan, paths)

    def test_mock_records_cannot_be_relabelled_as_live_study(self):
        plan = make_plan(self.cases[:1], name="Pilot preparation", repeats=1, provider_config=TEST_CONFIG)
        paths = self.execute_parts(plan)  # Deliberately mock execution with an incorrect provider label.
        with self.assertRaisesRegex(ValueError, "no relabeling"):
            link_campaigns(plan, paths)

    def test_versions_and_approval_claims_fail_closed(self):
        plan = make_plan(self.cases, name="Test")
        for changes in ({"schema_version": 2}, {"main_experiment_approved": True}, {"planned_runs": 1},
                        {"variants": ["B"]}, {"provider_config": {"provider": "mock", "secret": "not-allowed"}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_plan({**plan, **changes})

    def test_invalid_frozen_fingerprints_and_provenance_types_fail_closed(self):
        plan = make_plan(self.cases[:1], name="Test", repeats=1)
        for invalid in ({"not-a-hash": True}, {**FROZEN_CODE["source_sha256"], "../outside": "a" * 64},
                        {**FROZEN_CODE["source_sha256"], "src/security_lab/core.py": True}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_plan({**plan, "provenance": {**FROZEN_CODE, "source_sha256": invalid}})
        with self.assertRaises(ValueError):
            validate_plan({**plan, "provenance": {**FROZEN_CODE, "git_commit": "not-a-commit"}})
        paths = self.execute_parts(plan)
        manifest_path = paths[0] / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["provenance"] = ["malformed"]
        write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "code/lockfiles differ"):
            link_campaigns(plan, paths)

    def test_preflight_is_read_only_and_never_constructs_provider(self):
        plan = make_plan(self.cases, name="Pilot", repeats=1, provider_config=TEST_CONFIG)
        record = self.root / "acceptance.md"
        record.write_text("Unverified external record")
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        with patch("security_lab.providers.OpenAIModel", side_effect=AssertionError("No provider construction")):
            result = preflight(plan, already_spent_eur="0", records={"author_acceptance": record})
        self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()})
        self.assertFalse(result["paid_run_authorized"])
        self.assertEqual(result["network_requests_made"], 0)
        self.assertEqual(next(x for x in result["gates"] if x["gate"] == "author_acceptance")["status"], "supplied_unverified")
        self.assertEqual(result["cost"]["max_requests"], 24)
        self.assertFalse(result["cost"]["price_verified"])

    def test_preflight_accounts_for_each_part_budget_and_unknown_spend(self):
        plan = make_plan(self.cases, name="Pilot", repeats=1, max_part_runs=8,
                         provider_config={**TEST_CONFIG, "run_budget_eur": "2"})
        unknown = preflight(plan)
        self.assertIn({"gate": "project_budget", "status": "unknown_spend"}, unknown["gates"])
        report = preflight(plan, already_spent_eur="247")
        self.assertEqual(report["cost"]["aggregate_configured_budget_eur"], "4")
        self.assertIn({"gate": "project_budget", "status": "exceeds_project_budget"}, report["gates"])
        for spent in ("NaN", "-1", "Infinity"):
            with self.subTest(spent=spent), self.assertRaises(ValueError):
                preflight(plan, already_spent_eur=spent)

    def test_cli_refuses_overwriting_plan_and_campaign(self):
        plan = make_plan(self.cases[:1], name="Test", repeats=1)
        plan_path = self.root / "plan.json"
        write_json(plan_path, plan)
        paths = self.execute_parts(plan)
        before = plan_path.read_bytes()
        with patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(main(["link", str(plan_path), "--campaigns", str(paths[0]), "--output", str(plan_path)]), 2)
            self.assertEqual(main(["link", str(plan_path), "--campaigns", str(paths[0]), "--output", str(paths[0] / "linked.json")]), 2)
        self.assertEqual(before, plan_path.read_bytes())

    def test_cli_mock_preflight_and_duplicate_json_failure(self):
        plan = make_plan(self.cases, name="Test", repeats=1)
        path = self.root / "plan.json"
        write_json(path, plan)
        output = io.StringIO()
        with patch("sys.stdout", new=output):
            self.assertEqual(main(["preflight", str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue())["cost"]["estimated_eur"], "0")
        path.write_text('{"schema_version":1,"schema_version":2}')
        with patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(main(["preflight", str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
