"""Regression checks for preserving original evidence at CLI output boundaries."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from security_lab.batch import run_batch, load_results, write_json
from security_lab.cases import load_cases
from security_lab.cli import main
from security_lab.models import ScriptedModel


class EvidenceOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / "campaign"
        run_batch(load_cases(Path("cases/dev"))[:1], self.directory, ScriptedModel,
                  variants=["B"], sources=["clean"])

    def test_events_are_not_overwritten(self):
        path = next((self.directory / "events").glob("*.jsonl"))
        before = path.read_bytes()
        with redirect_stderr(StringIO()), redirect_stdout(StringIO()):
            code = main(["summarize", str(self.directory), "--output", str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(load_results(self.directory)), 1)

    def test_review_input_cannot_be_summary_output(self):
        # Use real export/import to ensure the guard runs after successful attach.
        from security_lab.review import export_review, combine_reviews
        import csv
        review_dir = Path(self.tmp.name) / "review"
        export_review(load_results(self.directory), review_dir)
        for slot, rater in (("a", "Sebastian"), ("b", "Jonah")):
            path = review_dir / f"ratings_{slot}.csv"
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                fields, rows = reader.fieldnames, list(reader)
            for row in rows:
                row.update(rater=rater, legitimate_rating="correct", attack_success="no",
                           false_block="no", notes="Synthetischer Test der Dateierhaltung.")
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        combined = review_dir / "combined.json"
        combine_reviews(review_dir / "mapping.json", [review_dir / "ratings_a.csv", review_dir / "ratings_b.csv"],
                        combined, packets_path=review_dir / "reviews.jsonl")
        before = combined.read_bytes()
        with redirect_stderr(StringIO()), redirect_stdout(StringIO()):
            code = main(["summarize", str(self.directory), "--reviews", str(combined), "--output", str(combined)])
        self.assertEqual(code, 2)
        self.assertEqual(combined.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
