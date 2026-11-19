"""Offline-only integration checks for the once-per-workspace clean rehearsal."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch

from security_lab import clean_b_rehearsal as rehearsal
from security_lab.batch import load_results


class CleanBRehearsalTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        self.campaign = self.workspace / rehearsal.REHEARSAL
        self.attempt = self.workspace / rehearsal.ATTEMPT

    def test_concurrent_starts_persist_one_mock_campaign_with_the_fixed_plan(self):
        barrier = threading.Barrier(2)
        prepare = rehearsal.prepare

        def simultaneous_plans():
            plan_and_cases = prepare()
            barrier.wait(timeout=15)
            return plan_and_cases

        with (patch.object(rehearsal, "prepare", simultaneous_plans),
              patch("security_lab.providers._http_transport", side_effect=AssertionError("network")) as transport,
              ThreadPoolExecutor(max_workers=2) as pool):
            futures = [pool.submit(rehearsal.rehearse, self.workspace) for _ in range(2)]
            successes = [future.result() for future in futures if future.exception() is None]
            rejected = [future.exception() for future in futures if future.exception() is not None]
        transport.assert_not_called()
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(rejected), 1)
        self.assertIsInstance(rejected[0], FileExistsError)
        outcome = successes[0]
        self.assertEqual(outcome["state"], "completed")
        self.assertTrue(outcome["engineering_only"])
        self.assertEqual((outcome["planned_runs"], outcome["recorded_runs"], outcome["provider_cost_eur"]),
                         (12, 12, "0"))
        self.assertFalse((self.workspace / "studies/budget.json").exists())
        self.assertFalse((self.workspace / "studies/luna-clean-first").exists())

        original = (self.workspace / outcome["attempt"]).read_bytes()
        plan = json.loads(original)["plan"]
        manifest = json.loads((self.workspace / outcome["manifest"]).read_bytes())
        self.assertEqual(manifest["schedule"], plan["schedule"])
        self.assertEqual(manifest["provider_config"]["rehearsal_attempt_sha256"],
                         hashlib.sha256(original).hexdigest())
        snapshot = json.loads((self.campaign / "cases.snapshot.json").read_bytes())
        self.assertTrue(all(set(case["articles"]) == set(case["mock"]) == {"clean"} for case in snapshot))
        records = load_results(self.campaign)
        self.assertEqual(len({record["case_id"] for record in records}), 12)
        for record in records:
            self.assertTrue(record["is_mock"])
            self.assertEqual((record["variant"], record["source"], record["repetition"], record["status"]),
                             ("B", "clean", 1, "completed"))
        # All twelve fixtures read once; six also append a note before answering.
        self.assertEqual((outcome["mock_model_calls"], outcome["tool_calls"]), (30, 18))
        with self.assertRaises(FileExistsError):
            rehearsal.rehearse(self.workspace)
        self.assertEqual(self.attempt.read_bytes(), original)

    def test_initial_storage_failure_preserves_attempt_and_prevents_replay(self):
        with patch.object(rehearsal, "run_batch", side_effect=OSError("simulated disk failure")) as batch:
            with self.assertRaises(OSError):
                rehearsal.rehearse(self.workspace)
            original = self.attempt.read_bytes()
            self.assertFalse(self.campaign.exists())
            with self.assertRaises(FileExistsError):
                rehearsal.rehearse(self.workspace)
            batch.assert_called_once()
        self.assertEqual(self.attempt.read_bytes(), original)

    def test_orphaned_partial_campaign_is_preserved_without_publishing_another_attempt(self):
        self.campaign.mkdir(parents=True)
        partial = self.campaign / "partial.json"
        partial.write_bytes(b"original")
        with patch.object(rehearsal, "run_batch") as batch, self.assertRaises(FileExistsError):
            rehearsal.rehearse(self.workspace)
        batch.assert_not_called()
        self.assertEqual(partial.read_bytes(), b"original")
        self.assertFalse(self.attempt.exists())

    def test_managed_workspace_cannot_redirect_the_rehearsal(self):
        with TemporaryDirectory() as target:
            try:
                (self.workspace / "studies").symlink_to(target, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"Directory symlinks are unavailable: {error}")
            with self.assertRaises(ValueError):
                rehearsal.rehearse(self.workspace)
            self.assertFalse(list(Path(target).iterdir()))
