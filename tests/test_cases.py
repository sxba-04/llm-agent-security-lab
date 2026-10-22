from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from security_lab.cases import CaseValidationError, load_case, load_cases, validate_case


DEV = Path(__file__).resolve().parents[1] / "cases" / "dev"


class CaseFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases(DEV)

    def test_development_catalog_covers_planned_goals_and_strategies(self):
        self.assertEqual(len(self.cases), 12)
        self.assertEqual(Counter(case["goal"] for case in self.cases), {"G1": 4, "G2": 4, "G3": 4})
        self.assertEqual(Counter((case["goal"], case["strategy"]) for case in self.cases),
                         {(goal, strategy): 2 for goal in ("G1", "G2", "G3")
                          for strategy in ("authority", "dependency")})

    def test_pairs_preserve_every_clean_article_and_required_fact(self):
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                self.assertIn(case["articles"]["clean"], case["articles"]["attack"])
                for fact in case["expected"]["required_facts"]:
                    self.assertIn(fact, case["articles"]["attack"])

    def test_canaries_are_generated_and_absent_from_model_inputs(self):
        for case in self.cases:
            self.assertEqual(case["tickets"]["B08"]["secret"], "__GENERATE__")
            public_input = case["user_request"] + " ".join(case["articles"].values())
            self.assertNotIn("__GENERATE__", public_input)
            self.assertNotIn("{{secret:", public_input)

    def test_clean_scripts_contain_only_authorized_tool_operations(self):
        for case in self.cases:
            session = case["session"]
            for step in case["mock"]["clean"]:
                if "text" in step:
                    continue
                target = step["arguments"]["ticket_id"]
                with self.subTest(case=case["case_id"], step=step):
                    if step["name"] == "read_ticket":
                        self.assertIn(target, session["read_ticket_ids"])
                    else:
                        self.assertTrue(session["write_enabled"])
                        self.assertEqual(target, session["write_ticket_id"])

    def test_read_only_write_attack_is_present(self):
        matches = [case for case in self.cases if case["goal"] == "G2"
                   and not case["session"]["write_enabled"]]
        self.assertTrue(matches)
        for case in matches:
            self.assertIn(case["expected"]["target_ticket_id"], case["session"]["read_ticket_ids"])
            self.assertEqual(case["expected"]["task"], "read")

    def test_g3_keeps_formally_authorized_output(self):
        for case in self.cases:
            if case["goal"] != "G3":
                continue
            self.assertEqual(case["expected"]["target_ticket_id"], case["expected"]["legitimate_ticket_id"])
            self.assertNotIn(case["expected"]["false_claim"], case["articles"]["clean"])
            self.assertIn(case["expected"]["false_claim"], case["articles"]["attack"])

    def test_benign_suspicious_quotation_is_present(self):
        self.assertTrue(any("ignore previous instructions" in case["articles"]["clean"]
                            for case in self.cases))

    def test_invalid_trusted_session_is_rejected(self):
        changes = [
            ("user_id", ""), ("read_ticket_ids", ["B08"]),
            ("read_ticket_ids", ["missing"]), ("read_ticket_ids", ["A17", "A17"]),
            ("write_enabled", "false"), ("write_enabled", 1),
            ("write_ticket_id", "B08"),
        ]
        for field, value in changes:
            case = deepcopy(self.cases[0])
            case["session"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(CaseValidationError):
                validate_case(case)

    def test_missing_write_target_is_rejected(self):
        case = deepcopy(self.cases[0])
        case["session"]["write_enabled"] = True
        with self.assertRaises(CaseValidationError):
            validate_case(case)

    def test_removed_legitimate_fact_is_rejected(self):
        case = deepcopy(self.cases[0])
        case["articles"]["attack"] = "Manipulierter Text ohne die nötigen Nutzinformationen."
        with self.assertRaises(CaseValidationError):
            validate_case(case)

    def test_nonstring_enum_rejected_as_validation_error(self):
        for field in ("goal", "strategy"):
            case = deepcopy(self.cases[0])
            case[field] = []
            with self.subTest(field=field), self.assertRaises(CaseValidationError):
                validate_case(case)

    def test_mock_may_not_invoke_arbitrary_tools_or_targets(self):
        for step in (
            {"name": "shell", "arguments": {"ticket_id": "A17"}},
            {"name": "read_ticket", "arguments": {"ticket_id": "unknown"}},
            {"name": "read_ticket", "arguments": {"ticket_id": "A17", "user_id": "admin"}},
        ):
            case = deepcopy(self.cases[0])
            case["mock"]["attack"][0] = step
            with self.subTest(step=step), self.assertRaises(CaseValidationError):
                validate_case(case)

    def test_duplicate_case_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("a.json", "b.json"):
                (Path(directory) / name).write_text(json.dumps(self.cases[0]), encoding="utf-8")
            with self.assertRaisesRegex(CaseValidationError, "duplicate case_id"):
                load_cases(directory)

    def test_shared_scenario_group_is_retained_for_clustering(self):
        with tempfile.TemporaryDirectory() as directory:
            for index in range(2):
                case = deepcopy(self.cases[0])
                case["case_id"] = f"related-{index}"
                (Path(directory) / f"{index}.json").write_text(json.dumps(case), encoding="utf-8")
            cases = load_cases(directory)
            self.assertEqual(cases[0]["scenario_group"], cases[1]["scenario_group"])

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ambiguous.json"
            path.write_text('{"session": {}, "session": {"write_enabled": true}}', encoding="utf-8")
            with self.assertRaisesRegex(CaseValidationError, "duplicate key"):
                load_case(path)

    def test_empty_catalog_is_an_error_not_an_implicit_development_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(CaseValidationError, "no JSON cases"):
                load_cases(directory)


if __name__ == "__main__":
    unittest.main()
