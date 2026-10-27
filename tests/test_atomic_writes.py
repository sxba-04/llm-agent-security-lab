"""Atomic campaign evidence survives transient Windows reader conflicts."""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import threading

from security_lab import batch
from security_lab.cases import load_cases
from security_lab.models import ScriptedModel


def windows_error(code: int) -> OSError:
    error = PermissionError(errno.EACCES, "Synthetic Windows replacement conflict")
    # Keep fault injection portable so Linux CI also checks the retry boundary.
    error.winerror = code
    return error


class AtomicWriteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.target = self.root / "manifest.json"
        self.original = b'{"state": "running", "completed_runs": 1}\n'
        self.updated = b'{"state": "completed", "completed_runs": 2}\n'
        self.target.write_bytes(self.original)

    def test_transient_windows_conflicts_preserve_complete_target_until_publication(self):
        real_replace = Path.replace
        for code in (5, 32, 33):
            with self.subTest(winerror=code):
                self.target.write_bytes(self.original)
                attempts = []

                def replace(source, destination):
                    attempts.append(source)
                    self.assertEqual(destination.read_bytes(), self.original)
                    self.assertEqual(source.read_bytes(), self.updated)
                    if len(attempts) < 3:
                        raise windows_error(code)
                    return real_replace(source, destination)

                with patch.object(Path, "replace", new=replace), \
                        patch("security_lab.batch.os.fsync", wraps=os.fsync) as fsync:
                    batch._atomic_bytes(self.target, self.updated)
                self.assertEqual(self.target.read_bytes(), self.updated)
                self.assertEqual(len(set(attempts)), 1, "Retries must reuse the durable temporary file")
                self.assertEqual(fsync.call_count, 1)
                self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_persistent_windows_conflict_is_bounded_and_preserves_original(self):
        error = windows_error(5)
        elapsed = 0.0

        def sleep(seconds):
            nonlocal elapsed
            self.assertGreater(seconds, 0)
            elapsed += seconds
            self.assertLessEqual(elapsed, 2, "Replacement retries must have a short deadline")
            self.assertEqual(self.target.read_bytes(), self.original)

        with patch.object(Path, "replace", side_effect=error) as replace, \
                patch("security_lab.batch.time.monotonic", side_effect=lambda: elapsed), \
                patch("security_lab.batch.time.sleep", side_effect=sleep):
            with self.assertRaises(PermissionError) as caught:
                batch._atomic_bytes(self.target, self.updated)
        self.assertIs(caught.exception, error)
        self.assertGreater(replace.call_count, 1)
        self.assertGreater(elapsed, 0)
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_other_errors_including_plain_permission_denial_are_not_retried(self):
        failures = (PermissionError(errno.EACCES, "No Windows sharing code"),
                    OSError(errno.EIO, "Storage failure"), windows_error(112))
        for error in failures:
            with self.subTest(error=repr(error)), \
                    patch.object(Path, "replace", side_effect=error) as replace, \
                    patch("security_lab.batch.time.sleep") as sleep:
                with self.assertRaises(OSError) as caught:
                    batch._atomic_bytes(self.target, self.updated)
                self.assertIs(caught.exception, error)
                self.assertEqual(replace.call_count, 1)
                sleep.assert_not_called()
                self.assertEqual(self.target.read_bytes(), self.original)
                self.assertEqual(list(self.root.glob("*.tmp")), [])

    @unittest.skipUnless(os.name == "nt", "Windows file sharing semantics required")
    def test_real_windows_reader_is_released_before_replacement_retry(self):
        real_replace = Path.replace
        conflicts = []
        with self.target.open("rb") as reader:
            def replace(source, destination):
                try:
                    return real_replace(source, destination)
                except OSError as error:
                    conflicts.append(error.winerror)
                    self.assertEqual(reader.read(), self.original)
                    reader.close()
                    raise

            with patch.object(Path, "replace", new=replace):
                batch._atomic_bytes(self.target, self.updated)
        self.assertEqual(len(conflicts), 1)
        self.assertIn(conflicts[0], (5, 32, 33))
        self.assertEqual(self.target.read_bytes(), self.updated)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_campaign_replacement_retry_does_not_repeat_model_work(self):
        case = load_cases(Path(__file__).resolve().parents[1] / "cases/dev")[0]
        campaign = self.root / "campaign"
        real_replace = Path.replace
        injected = False
        models = []

        class CountingModel(ScriptedModel):
            calls = 0

            def respond(self, messages, tools):
                self.calls += 1
                return super().respond(messages, tools)

        def factory(case, source):
            model = CountingModel(case, source)
            models.append(model)
            return model

        def replace(source, destination):
            nonlocal injected
            if destination == campaign / "manifest.json" and not injected:
                content = json.loads(source.read_bytes())
                if content["completed_runs"] == 1:
                    injected = True
                    raise windows_error(32)
            return real_replace(source, destination)

        with patch.object(Path, "replace", new=replace):
            manifest = batch.run_batch([case], campaign, factory,
                                       variants=["B", "F", "P", "FP"], sources=["clean", "attack"])
        records = batch.load_results(campaign)
        self.assertTrue(injected)
        self.assertEqual(manifest["state"], "completed")
        self.assertEqual(manifest["completed_runs"], 8)
        self.assertEqual(len(records), 8)
        self.assertEqual(len(models), 8)
        self.assertEqual(sum(model.calls for model in models), sum(row["model_calls"] for row in records))
        self.assertEqual(list(campaign.rglob("*.tmp")), [])

    def test_new_json_is_fully_synced_before_exclusive_publication(self):
        output = self.root / "decision.json"
        value = {"rater": "Prüfer", "notes": "Immutable original"}
        real_link = os.link
        with patch("security_lab.batch.os.fsync", wraps=os.fsync) as synced:
            def publish(source, target):
                self.assertFalse(output.exists())
                self.assertEqual(synced.call_count, 1)
                self.assertEqual(json.loads(Path(source).read_bytes()), value)
                return real_link(source, target)
            with patch("security_lab.batch.os.link", side_effect=publish):
                batch.write_json_new(output, value)
        self.assertEqual(json.loads(output.read_bytes()), value)
        with self.assertRaises(FileExistsError):
            batch.write_json_new(output, {"replacement": True})
        self.assertEqual(json.loads(output.read_bytes()), value)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_new_json_failed_sync_or_publication_leaves_no_partial_final_version(self):
        for operation in ("fsync", "link"):
            with self.subTest(operation=operation):
                output = self.root / "new-decision.json"
                with patch("security_lab.batch.os." + operation, side_effect=OSError(errno.ENOSPC, "Synthetic storage failure")):
                    with self.assertRaises(OSError):
                        batch.write_json_new(output, {"notes": "Complete decision"})
                self.assertFalse(output.exists())
                self.assertEqual(list(self.root.glob("*.tmp")), [])
                self.assertEqual(self.target.read_bytes(), self.original)

    def test_new_json_invalid_value_creates_no_directory(self):
        output = self.root / "never-created" / "decision.json"
        with self.assertRaises(ValueError):
            batch.write_json_new(output, {"invalid": float("nan")})
        self.assertFalse(output.parent.exists())

    def test_concurrent_new_json_writers_cannot_replace_the_winner(self):
        output = self.root / "race.json"
        real_link = os.link
        barrier = threading.Barrier(2)
        def publish(source, target):
            barrier.wait(timeout=5)
            return real_link(source, target)
        def write(value):
            try:
                batch.write_json_new(output, {"writer": value})
                return value
            except FileExistsError:
                return None
        with patch("security_lab.batch.os.link", side_effect=publish), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, ["first", "second"]))
        winners = [value for value in results if value is not None]
        self.assertEqual(len(winners), 1)
        self.assertEqual(json.loads(output.read_bytes()), {"writer": winners[0]})
        self.assertEqual(list(self.root.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
