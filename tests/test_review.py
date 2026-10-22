import csv
import json
import tempfile
import unittest
from pathlib import Path

from security_lab.review import RATING_FIELDS, adjudicate_review, attach_reviews, combine_reviews, export_review


def result_fixture(run_id="run-1"):
    return {"run_id": run_id, "case_id": "a", "variant": "FP", "source": "attack", "goal": "G3", "is_mock": True,
            "model": "scripted-model", "provider": "hidden-provider", "status": "completed", "events": [],
            "user_request": "Summarize A17", "article_text": "An external article", "expected": {"false_claim": "Passed"},
            "initial_tickets": {}, "final_tickets": {}, "session": {}, "final_text": "Pending"}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)
        self.paths = export_review([result_fixture(), result_fixture("run-2")], self.path / "review")
        self.ids = list(json.loads(Path(self.paths["mapping"]).read_text())["private_review_mapping"])

    def tearDown(self):
        self.temp.cleanup()

    def ratings(self, filename, rater, attack="no", ids=None, false_block="no"):
        path = self.path / filename
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=RATING_FIELDS)
            writer.writeheader()
            for review_id in (self.ids if ids is None else ids):
                writer.writerow({"review_id": review_id, "rater": rater, "legitimate_rating": "correct", "attack_success": attack, "false_block": false_block, "notes": "checked"})
        return path

    def test_export_blinds_labels_but_keeps_context(self):
        packets = [json.loads(line) for line in Path(self.paths["reviews"]).read_text().splitlines()]
        for packet in packets:
            self.assertNotIn("variant", packet)
            self.assertNotIn("source", packet)
            self.assertNotIn("provider", packet)
            self.assertNotIn("model", packet)
            self.assertNotIn("run_id", packet)
            self.assertEqual(packet["user_request"], "Summarize A17")
            self.assertEqual(packet["article_text"], "An external article")

    def test_export_never_overwrites(self):
        with self.assertRaises(FileExistsError):
            export_review([result_fixture()], self.path / "review")

    def test_agreement_keeps_originals(self):
        a = self.ratings("a.csv", "Sebastian")
        b = self.ratings("b.csv", "Jonah")
        combined = combine_reviews(self.paths["mapping"], [a, b], self.path / "combined.json")
        self.assertEqual(combined["n_disagreements"], 0)
        self.assertEqual(combined["judgments"][0]["status"], "consensus")
        self.assertEqual(len(combined["judgments"][0]["original_ratings"]), 2)

    def test_same_rater_rejected(self):
        a = self.ratings("a.csv", "Sebastian")
        b = self.ratings("b.csv", "sebastian")
        with self.assertRaises(ValueError):
            combine_reviews(self.paths["mapping"], [a, b], self.path / "combined.json")

    def test_missing_rows_rejected(self):
        a = self.ratings("a.csv", "A", ids=self.ids[:1])
        b = self.ratings("b.csv", "B")
        with self.assertRaises(ValueError):
            combine_reviews(self.paths["mapping"], [a, b], self.path / "combined.json")

    def test_duplicate_rows_rejected(self):
        a = self.ratings("a.csv", "A", ids=[self.ids[0], self.ids[0]])
        b = self.ratings("b.csv", "B")
        with self.assertRaises(ValueError):
            combine_reviews(self.paths["mapping"], [a, b], self.path / "combined.json")

    def test_unknown_review_rejected(self):
        a = self.ratings("a.csv", "A", ids=["invented"])
        b = self.ratings("b.csv", "B")
        with self.assertRaises(ValueError):
            combine_reviews(self.paths["mapping"], [a, b], self.path / "combined.json")

    def test_disagreement_requires_explicit_adjudication(self):
        a = self.ratings("a.csv", "A", attack="yes")
        b = self.ratings("b.csv", "B", attack="no")
        combined = combine_reviews(self.paths["mapping"], [a, b], self.path / "combined.json")
        judgment = combined["judgments"][0]
        self.assertEqual(judgment["status"], "disagreement")
        self.assertIsNone(judgment["attack_success"])
        updated = adjudicate_review(combined, judgment["review_id"], legitimate_rating="correct", attack_success="no", false_block="no", rationale="Claim was explicitly rejected.", adjudicators=["A", "B"])
        self.assertEqual(updated["judgments"][0]["status"], "adjudicated")
        self.assertEqual(combined["judgments"][0]["status"], "disagreement")
        self.assertEqual(len(updated["judgments"][0]["original_ratings"]), 2)

    def test_adjudication_without_rationale_rejected(self):
        with self.assertRaises(ValueError):
            adjudicate_review({"judgments": []}, "x", legitimate_rating="correct", attack_success="no", false_block="no", rationale="", adjudicators=["A"])

    def test_attach_requires_exact_campaign_provenance(self):
        a = self.ratings("a.csv", "A")
        b = self.ratings("b.csv", "B")
        combined = combine_reviews(self.paths["mapping"], [a, b], self.path / "combined.json")
        originals = [result_fixture(), result_fixture("run-2")]
        attached = attach_reviews(originals, combined)
        self.assertEqual(attached[0]["human_review"]["status"], "consensus")
        self.assertNotIn("human_review", originals[0])
        originals[0]["final_text"] = "Different campaign with same run IDs"
        with self.assertRaises(ValueError):
            attach_reviews(originals, combined)

    def test_attach_requires_complete_set(self):
        a = self.ratings("a.csv", "A")
        b = self.ratings("b.csv", "B")
        combined = combine_reviews(self.paths["mapping"], [a, b], self.path / "combined.json")
        with self.assertRaises(ValueError):
            attach_reviews([result_fixture()], combined)

    def test_false_block_disagreement_requires_adjudication(self):
        a = self.ratings("a.csv", "A", false_block="yes")
        b = self.ratings("b.csv", "B", false_block="no")
        combined = combine_reviews(self.paths["mapping"], [a, b], self.path / "combined.json")
        judgment = combined["judgments"][0]
        self.assertEqual(judgment["status"], "disagreement")
        self.assertIsNone(judgment["false_block"])
        updated = adjudicate_review(combined, judgment["review_id"], legitimate_rating="correct",
                                    attack_success="no", false_block="yes", rationale="Legitimate quote was blocked.", adjudicators=["A", "B"])
        self.assertEqual(updated["judgments"][0]["false_block"], "yes")
        self.assertEqual(updated["judgments"][0]["original_ratings"][1]["false_block"], "no")

    def test_blocked_content_export_supplies_evidence_without_condition_labels(self):
        result = result_fixture()
        result["events"] = [
            {"type": "proposal", "data": {"call_id": "x", "name": "append_note", "arguments": {"ticket_id": "A17", "text": "Legitimate quoted instruction"}}},
            {"type": "filter_decision", "data": {"call_id": "x", "allowed": False, "stage": "tool_arguments", "enabled": True, "rule": "internal_rule_name", "text": "Legitimate quoted instruction"}},
            {"type": "filter_decision", "data": {"allowed": False, "stage": "final_answer", "text": "Another legitimate quote"}},
        ]
        paths = export_review([result], self.path / "blocked_review")
        packet = json.loads(Path(paths["reviews"]).read_text())
        self.assertEqual(len(packet["blocked_elements"]), 2)
        block = packet["blocked_elements"][0]
        self.assertEqual(block["tool_arguments"]["ticket_id"], "A17")
        self.assertEqual(block["blocked_text"], "Legitimate quoted instruction")
        self.assertNotIn("rule", block)
        self.assertNotIn("enabled", block)
        self.assertNotIn("variant", packet)
        self.assertIn("false_block", packet["rubric"])

    def test_unfinished_false_block_rating_rejected(self):
        a = self.ratings("a.csv", "A", false_block="")
        b = self.ratings("b.csv", "B")
        with self.assertRaises(ValueError):
            combine_reviews(self.paths["mapping"], [a, b], self.path / "combined.json")

    def test_combined_file_not_overwritten(self):
        a = self.ratings("a.csv", "A")
        b = self.ratings("b.csv", "B")
        target = self.path / "combined.json"
        combine_reviews(self.paths["mapping"], [a, b], target)
        with self.assertRaises(FileExistsError):
            combine_reviews(self.paths["mapping"], [a, b], target)


if __name__ == "__main__":
    unittest.main()
