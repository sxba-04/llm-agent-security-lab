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

    def test_pairs_preserve_article_facts_and_require_both_information_sources(self):
        for case in self.cases:
            with self.subTest(case=case["case_id"]):
                self.assertIn(case["articles"]["clean"], case["articles"]["attack"])
                sources = case["expected"]["required_fact_sources"]
                self.assertEqual({item["source"] for item in sources}, {"article", "ticket"})
                for item in sources:
                    if item["source"] == "article":
                        self.assertIn(item["fact"], case["articles"]["attack"])
                        self.assertNotIn(item["fact"], " ".join(case["tickets"]["A17"]["facts"].values()))
                    else:
                        self.assertNotIn(item["fact"], case["articles"]["clean"])
                self.assertTrue(case["expected"]["semantic_criteria"])
                self.assertTrue(case["document"]["document_id"])

    def test_legacy_fixtures_without_fact_sources_remain_valid(self):
        case = deepcopy(self.cases[0])
        del case["expected"]["required_fact_sources"]
        for source in ("clean", "attack"):
            case["articles"][source] += "\n" + " ".join(case["expected"]["required_facts"])
        validate_case(case)

    def test_fact_source_must_be_complete_unique_and_readable(self):
        original = self.cases[0]
        malformed = [[], [original["expected"]["required_fact_sources"][0]] * 3,
                     [{"fact": original["expected"]["required_facts"][0], "source": "ticket", "ticket_id": "B08"}],
                     [{"fact": "missing", "source": "article"}]]
        for value in malformed:
            case = deepcopy(original)
            case["expected"]["required_fact_sources"] = value
            with self.subTest(value=value), self.assertRaises(CaseValidationError):
                validate_case(case)

    def test_wrapped_pdf_facts_are_accepted_without_changing_stored_text(self):
        case = deepcopy(self.cases[0])
        item = next(item for item in case["expected"]["required_fact_sources"] if item["source"] == "article")
        original = case["articles"]["clean"]
        wrapped = item["fact"].replace(" ", "\n  ")
        case["articles"]["clean"] = original.replace(item["fact"], wrapped)
        validate_case(case)
        self.assertIn(wrapped, case["articles"]["clean"])
        case["articles"]["clean"] = original.replace(item["fact"], item["fact"].upper())
        with self.assertRaises(CaseValidationError):
            validate_case(case)

    def test_article_and_ticket_evidence_cannot_be_silently_swapped(self):
        case = deepcopy(self.cases[0])
        item = case["expected"]["required_fact_sources"][0]
        item.pop("ticket_id")
        item["source"] = "article"
        with self.assertRaises(CaseValidationError):
            validate_case(case)

    def test_optional_document_metadata_is_validated(self):
        case = deepcopy(self.cases[0])
        case["article_sources"] = {"clean": {"document_id": "pdf-id", "origin": "uploaded_pdf", "confirmed": True}}
        validate_case(case)
        case["article_sources"]["other"] = {"document_id": "x"}
        with self.assertRaises(CaseValidationError):
            validate_case(case)
        case.pop("article_sources")
        case["document"]["title"] = ""
        with self.assertRaises(CaseValidationError):
            validate_case(case)

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

    def test_maintenance_answer_needs_external_planning_guidance_in_read_only_mode(self):
        case = next(case for case in self.cases if case["case_id"] == "DEV-G2-03")
        external = [item["fact"] for item in case["expected"]["required_fact_sources"] if item["source"] == "article"]
        self.assertEqual(len(external), 1)
        self.assertIn("zwei Zeitvorschläge mit dem Betriebsteam", external[0])
        self.assertNotIn("Zeitvorschläge", case["user_request"])
        self.assertNotIn("Zeitvorschläge", json.dumps(case["tickets"], ensure_ascii=False))
        for source in ("clean", "attack"):
            self.assertIn(external[0], case["articles"][source])
        self.assertFalse(case["session"]["write_enabled"])
        self.assertEqual(case["expected"]["task"], "read")
        self.assertTrue(all("name" not in step or step["name"] == "read_ticket" for step in case["mock"]["clean"]))

    def test_controlled_clean_answers_include_both_sources_without_extra_tools(self):
        for case in self.cases:
            with self.subTest(case_id=case["case_id"]):
                # This validates fixture consistency, not a model's semantic
                # performance: these scripts intentionally supply exact facts.
                answer = case["mock"]["clean"][-1]["text"]
                for fact in case["expected"]["required_facts"]:
                    self.assertIn(fact, answer)
                    for step in case["mock"]["clean"]:
                        if step.get("name") == "append_note":
                            self.assertIn(fact, step["arguments"]["text"])
                self.assertTrue(all("name" not in step or step["name"] in {"read_ticket", "append_note"}
                                    for step in case["mock"]["clean"]))

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

    def test_fixture_ticket_ids_use_the_documented_tool_grammar(self):
        for invalid in ("A 17", "1A17", "A/17", "Ä17", "A" * 65):
            # Rename all references, so failure is the grammar rather than an
            # accidental dangling session, expected fact source or mock call.
            serialized = json.dumps(self.cases[0], ensure_ascii=False).replace("A17", invalid)
            case = json.loads(serialized)
            with self.subTest(ticket_id=invalid), self.assertRaisesRegex(CaseValidationError, "ticket ID"):
                validate_case(case)
        for valid in ("A", "A_17-test", "A" * 64):
            validate_case(json.loads(json.dumps(self.cases[0]).replace("A17", valid)))

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
