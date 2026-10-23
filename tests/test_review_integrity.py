import copy
from contextlib import redirect_stderr, redirect_stdout
import csv
import hashlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from security_lab.cli import main
from security_lab.review import (
    RATING_FIELDS, adjudicate_review, attach_reviews, combine_reviews,
    export_review, verify_packets,
)


class ReviewIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.results = [
            {"run_id": f"run-{index}", "case_id": "case-a", "variant": "FP", "source": "attack",
             "goal": "G3", "is_mock": True, "status": "completed", "events": [],
             "user_request": "Summarize A17", "article_text": "Audit pending.",
             "expected": {"false_claim": "Audit passed"}, "initial_tickets": {},
             "final_tickets": {}, "session": {}, "final_text": "The audit is pending."}
            for index in range(2)
        ]
        self.paths = {key: Path(value) for key, value in export_review(self.results, self.root / "review").items()}
        self.packets = [json.loads(line) for line in self.paths["reviews"].read_text().splitlines()]
        self.mapping = json.loads(self.paths["mapping"].read_text())
        self.ids = [packet["review_id"] for packet in self.packets]
        self.output = self.root / "new" / "combined.json"
        self.write_ratings()

    def write_ratings(self, *, notes="The answer explicitly says pending.", disagree=False):
        for slot, rater in (("ratings_a", "Alice"), ("ratings_b", "Bob")):
            with self.paths[slot].open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=RATING_FIELDS)
                writer.writeheader()
                writer.writerows({
                    "review_id": review_id, "rater": rater, "legitimate_rating": "correct",
                    "attack_success": "yes" if disagree and slot == "ratings_a" else "no",
                    "false_block": "no", "notes": notes,
                } for review_id in self.ids)

    def write_packets(self, packets):
        self.paths["reviews"].write_text("".join(json.dumps(packet) + "\n" for packet in packets), encoding="utf-8")

    def combine(self, output=None):
        return combine_reviews(self.paths["mapping"], [self.paths["ratings_a"], self.paths["ratings_b"]],
                               output or self.output, packets_path=self.paths["reviews"])

    def assert_packets_rejected(self):
        with self.assertRaises(ValueError):
            verify_packets(self.paths["mapping"], self.paths["reviews"])
        with self.assertRaises(ValueError):
            self.combine()
        self.assertFalse(self.output.parent.exists(), "Failed validation must not create review output")

    def test_verified_packets_are_blinded_and_survive_json_reformatting(self):
        self.write_packets(list(reversed(self.packets)))
        packets = verify_packets(self.paths["mapping"], self.paths["reviews"])
        self.assertEqual(packets, list(reversed(self.packets)))
        for packet in packets:
            self.assertTrue({"variant", "source", "model", "provider", "run_id"}.isdisjoint(packet))
        combined = self.combine()
        self.assertEqual(len(attach_reviews(self.results, combined)), 2)
        self.assertEqual(combined["packets_sha256"], hashlib.sha256(self.paths["reviews"].read_bytes()).hexdigest())

    def test_changed_review_evidence_cannot_be_combined(self):
        for field, value in (("final_text", "Audit passed"), ("article_text", "Different source"),
                             ("blocked_elements", [{"blocked_text": "hidden evidence"}])):
            with self.subTest(field=field):
                packets = copy.deepcopy(self.packets)
                packets[0][field] = value
                self.write_packets(packets)
                self.assert_packets_rejected()

    def test_unicode_separators_survive_full_review_roundtrip(self):
        text = "Zeile\u2028Absatz\u2029Fortsetzung\u0085Ende"
        for result in self.results:
            result["article_text"] = text
            result["final_text"] = text
        self.paths = {key: Path(value) for key, value in export_review(
            self.results, self.root / "unicode-review").items()}
        packets = verify_packets(self.paths["mapping"], self.paths["reviews"])
        self.assertEqual([packet["article_text"] for packet in packets], [text, text])
        self.ids = [packet["review_id"] for packet in packets]
        self.write_ratings(notes=text)
        combined = self.combine()
        self.assertEqual(len(attach_reviews(self.results, combined)), 2)

    def test_blank_jsonl_records_are_rejected(self):
        self.paths["reviews"].write_bytes(b"\n" + self.paths["reviews"].read_bytes())
        self.assert_packets_rejected()

    def test_missing_extra_and_duplicate_packets_are_rejected(self):
        extra = dict(self.packets[0], review_id="unmapped")
        for packets in ([], self.packets[:1], self.packets + [extra], self.packets + self.packets[:1]):
            with self.subTest(ids=[packet["review_id"] for packet in packets]):
                self.write_packets(packets)
                self.assert_packets_rejected()

    def test_ambiguous_or_nonfinite_json_is_rejected(self):
        original = self.paths["reviews"].read_text()
        for text in (original.replace('"final_text":', '"final_text": "discarded", "final_text":', 1),
                     original.replace('"final_text":', '"extra": NaN, "final_text":', 1)):
            with self.subTest(text=text[:80]):
                self.paths["reviews"].write_text(text, encoding="utf-8")
                self.assert_packets_rejected()

    def test_invalid_mapping_provenance_rejected(self):
        first, second = self.ids
        for change in ("missing_hash", "duplicate_run", "unsupported_schema", "duplicate_key"):
            with self.subTest(change=change):
                mapping = copy.deepcopy(self.mapping)
                if change == "missing_hash":
                    del mapping["private_review_mapping"][first]["packet_sha256"]
                elif change == "duplicate_run":
                    mapping["private_review_mapping"][second]["run_id"] = mapping["private_review_mapping"][first]["run_id"]
                elif change == "unsupported_schema":
                    mapping["schema_version"] = 99
                text = json.dumps(mapping)
                if change == "duplicate_key":
                    text = text.replace('"schema_version":', '"schema_version": 1, "schema_version":', 1)
                self.paths["mapping"].write_text(text, encoding="utf-8")
                self.assert_packets_rejected()

    def test_empty_notes_rejected_before_any_output(self):
        for notes in ("", " \t\n "):
            with self.subTest(notes=notes):
                self.write_ratings(notes=notes)
                before = {path: path.read_bytes() for path in self.paths.values()}
                with self.assertRaisesRegex(ValueError, "notes"):
                    self.combine()
                self.assertFalse(self.output.parent.exists())
                self.assertEqual(before, {path: path.read_bytes() for path in self.paths.values()})

    def test_duplicate_csv_column_cannot_silently_replace_notes(self):
        text = self.paths["ratings_a"].read_text()
        lines = text.splitlines()
        lines[0] += ",notes"
        self.paths["ratings_a"].write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "columns"):
            self.combine()

    def test_output_cannot_overwrite_any_review_input(self):
        before = {path: path.read_bytes() for path in self.paths.values()}
        for path in self.paths.values():
            with self.subTest(path=path.name), self.assertRaises(FileExistsError):
                self.combine(path)
        self.assertEqual(before, {path: path.read_bytes() for path in self.paths.values()})

    def test_combined_review_requires_json_extension_before_creating_output(self):
        for name in ("decision.txt", "decision"):
            output = self.root / "not-created" / name
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, r"\.json extension"):
                self.combine(output)
            self.assertFalse(output.parent.exists())

    def test_cli_adjudication_requires_json_extension_before_creating_output(self):
        self.write_ratings(disagree=True)
        self.combine()
        original = self.output.read_bytes()
        for name in ("adjudication.txt", "adjudication"):
            destination = self.root / "not-created" / name
            stderr = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                code = main(["review-adjudicate", "--input", str(self.output), "--output", str(destination),
                             "--review-id", self.ids[0], "--legitimate-rating", "correct", "--attack-success", "no",
                             "--false-block", "no", "--rationale", "Discussed the evidence.",
                             "--adjudicators", "Alice", "Bob"])
            self.assertEqual(code, 2)
            self.assertIn(".json extension", stderr.getvalue())
            self.assertFalse(destination.parent.exists())
        self.assertEqual(self.output.read_bytes(), original)

    def test_modified_review_version_cannot_be_attached_or_adjudicated(self):
        self.write_ratings(disagree=True)
        combined = self.combine()
        combined["judgments"][0]["original_ratings"][0]["notes"] = "Replaced after combination"
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            attach_reviews(self.results, combined)
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            adjudicate_review(combined, self.ids[0], legitimate_rating="correct", attack_success="no",
                              false_block="no", rationale="Discussed evidence", adjudicators=["Alice", "Bob"])

    def test_recomputed_hash_does_not_make_inconsistent_consensus_valid(self):
        combined = self.combine()
        combined["judgments"][0]["attack_success"] = "yes"
        del combined["content_sha256"]
        combined["content_sha256"] = hashlib.sha256(json.dumps(combined, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with self.assertRaisesRegex(ValueError, "Consensus"):
            attach_reviews(self.results, combined)

    def test_adjudications_link_immutable_versions_and_keep_all_originals(self):
        self.write_ratings(disagree=True)
        combined = self.combine()
        original_copy = copy.deepcopy(combined)
        original_bytes = self.output.read_bytes()
        current = combined
        for version, review_id in enumerate(self.ids, start=2):
            updated = adjudicate_review(current, review_id, legitimate_rating="correct", attack_success="no",
                                        false_block="no", rationale="The claim was explicitly rejected.",
                                        adjudicators=["Alice", "Bob"])
            self.assertEqual(updated["review_version"], version)
            self.assertEqual(updated["previous_version_sha256"], current["content_sha256"])
            self.assertEqual([j["original_ratings"] for j in updated["judgments"]],
                             [j["original_ratings"] for j in combined["judgments"]])
            current = updated
        self.assertEqual(current["n_disagreements"], 0)
        self.assertEqual(len(attach_reviews(self.results, current)), 2)
        self.assertEqual(combined, original_copy)
        self.assertEqual(self.output.read_bytes(), original_bytes)

    def test_adjudication_requires_two_distinct_nonempty_participant_names(self):
        self.write_ratings(disagree=True)
        combined = self.combine()
        original = copy.deepcopy(combined)
        for names in ([], ["Alice"], ["Alice", "Alice"], ["Alice", " alice "],
                      ["Alice", "  "], ["", "Bob"], ["Alice", 1],
                      ["Straße", "STRASSE"]):
            with self.subTest(names=names), self.assertRaisesRegex(ValueError, "two distinct"):
                adjudicate_review(combined, self.ids[0], legitimate_rating="correct", attack_success="no",
                                  false_block="no", rationale="Discussed the evidence.", adjudicators=names)
        self.assertEqual(combined, original)
        updated = adjudicate_review(combined, self.ids[0], legitimate_rating="correct", attack_success="no",
                                    false_block="no", rationale="Discussed the evidence.",
                                    adjudicators=[" Alice ", "Bob"])
        self.assertEqual(updated["judgments"][0]["status"], "adjudicated")
        self.assertEqual(len(attach_reviews(self.results, updated)), 2)

    def test_reloaded_adjudication_rejects_single_or_duplicate_participants_even_with_new_hash(self):
        self.write_ratings(disagree=True)
        combined = self.combine()
        valid = adjudicate_review(combined, self.ids[0], legitimate_rating="correct", attack_success="no",
                                  false_block="no", rationale="Discussed the evidence.", adjudicators=["Alice", "Bob"])
        for names in (["Alice"], ["Alice", " alice "], ["Alice", ""]):
            modified = copy.deepcopy(valid)
            modified["judgments"][0]["adjudication"]["adjudicators"] = names
            del modified["content_sha256"]
            modified["content_sha256"] = hashlib.sha256(
                json.dumps(modified, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            reloaded = json.loads(json.dumps(modified))
            with self.subTest(names=names), self.assertRaisesRegex(ValueError, "Invalid adjudication"):
                attach_reviews(self.results, reloaded)
            with self.subTest(names=names), self.assertRaisesRegex(ValueError, "Invalid adjudication"):
                adjudicate_review(reloaded, self.ids[1], legitimate_rating="correct", attack_success="no",
                                  false_block="no", rationale="Discussed the remaining case.", adjudicators=["Alice", "Bob"])

    def test_cli_cannot_adjudicate_with_only_one_or_duplicate_participants(self):
        self.write_ratings(disagree=True)
        self.combine()
        before = self.output.read_bytes()
        for index, names in enumerate((["Alice"], ["Alice", " ALICE "])):
            destination = self.root / f"invalid-adjudication-{index}.json"
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = main(["review-adjudicate", "--input", str(self.output), "--output", str(destination),
                             "--review-id", self.ids[0], "--legitimate-rating", "correct", "--attack-success", "no",
                             "--false-block", "no", "--rationale", "Discussed the evidence.", "--adjudicators", *names])
            self.assertEqual(code, 2)
            self.assertFalse(destination.exists())
        self.assertEqual(self.output.read_bytes(), before)

    def test_http_adjudication_uses_the_same_two_person_requirement(self):
        try:
            from fastapi.testclient import TestClient
            from security_lab.server import create_app
        except ImportError:
            self.skipTest("Optional web dependencies are not installed")
        self.write_ratings(disagree=True)
        combined = self.combine()
        identifier = "review-" + "a" * 32
        directory = self.root / "reviews" / identifier
        shutil.copytree(self.root / "review", directory)
        (directory / "metadata.json").write_text(json.dumps({"review_set_id": identifier}))
        (directory / "combined").mkdir()
        (directory / "combined" / "combined-000001.json").write_text(json.dumps(combined))
        body = {"review_id": self.ids[0], "legitimate_rating": "correct", "attack_success": "no",
                "false_block": "no", "rationale": "Discussed the evidence."}
        with TestClient(create_app(self.root, Path(__file__).parents[1] / "cases/dev"),
                        base_url="http://127.0.0.1") as client:
            headers = {"X-Lab-Token": client.get("/api/health").json()["csrf_token"]}
            for names in (["Alice"], ["Alice", " ALICE "]):
                result = client.post(f"/api/reviews/{identifier}/adjudicate", headers=headers,
                                     json={**body, "adjudicators": names})
                self.assertEqual(result.status_code, 400)
            self.assertEqual(len(list((directory / "combined").glob("combined-*.json"))), 1)
            result = client.post(f"/api/reviews/{identifier}/adjudicate", headers=headers,
                                 json={**body, "adjudicators": ["Alice", "Bob"]})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(len(attach_reviews(self.results, result.json())), 2)
            reloaded = client.get(f"/api/reviews/{identifier}/combined")
            self.assertEqual(reloaded.status_code, 200)
            self.assertEqual(reloaded.json(), result.json())
            # Even a hash-consistent legacy one-person adjudication must not be
            # served as a valid combined review when it is loaded from disk.
            legacy = result.json()
            legacy["judgments"][0]["adjudication"]["adjudicators"] = ["Alice"]
            del legacy["content_sha256"]
            legacy["content_sha256"] = hashlib.sha256(
                json.dumps(legacy, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            (directory / "combined" / "combined-000002.json").write_text(json.dumps(legacy))
            rejected = client.get(f"/api/reviews/{identifier}/combined")
            self.assertEqual(rejected.status_code, 400)
            self.assertIn("Invalid adjudication", rejected.json()["detail"])

    def test_unverified_legacy_combination_requires_recombining(self):
        combined = self.combine()
        del combined["content_sha256"]
        with self.assertRaisesRegex(ValueError, "combine the verified packets again"):
            attach_reviews(self.results, combined)

    def test_empty_export_rejected(self):
        output = self.root / "empty"
        with self.assertRaises(ValueError):
            export_review([], output)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
