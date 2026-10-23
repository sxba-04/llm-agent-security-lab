"""Worker death and damaged evidence are isolated without changing originals."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from security_lab.batch import load_results, run_batch, write_json
from security_lab.cases import load_cases
from security_lab.jobs import CampaignJobs
from security_lab.models import ScriptedModel


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "cases" / "dev"


class CampaignJobsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name) / "workspace"
        self.cases = load_cases(CASES)[:1]

    def cli_campaign(self, name):
        path = self.workspace / name
        run_batch(self.cases, path, ScriptedModel, variants=["B"], sources=["clean"])
        return path

    def managed_campaign(self):
        jobs = CampaignJobs(self.workspace)
        self.addCleanup(jobs.shutdown)
        result = jobs.start(self.cases, variants=["B"], sources=["clean"], repeats=1, seed=42, document_ids=[])
        jobs._jobs[result["campaign_id"]]["thread"].join(timeout=10)
        self.assertFalse(jobs.running)
        return jobs, result["campaign_id"], jobs.directory(result["campaign_id"])

    def test_live_other_process_is_not_recovered_but_its_crash_is(self):
        ready = self.workspace.parent / "ready.json"
        script = r'''
import json, sys, threading
from pathlib import Path
from security_lab import jobs as module
from security_lab.cases import load_cases
real_run = module.batch.run_batch
def paused_run(*args, **kwargs):
    original = kwargs['on_progress']
    def progress(manifest):
        original(manifest)
        if manifest['completed_runs'] == 1:
            Path(sys.argv[3]).write_text(json.dumps({'campaign_id': Path(args[1]).name}))
            threading.Event().wait(30)
    kwargs['on_progress'] = progress
    return real_run(*args, **kwargs)
module.batch.run_batch = paused_run
manager = module.CampaignJobs(Path(sys.argv[1]))
started = manager.start(load_cases(Path(sys.argv[2]))[:1], variants=['B','P'], sources=['clean'], repeats=1, seed=42, document_ids=[])
manager._jobs[started['campaign_id']]['thread'].join()
'''
        environment = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        process = subprocess.Popen([sys.executable, "-c", script, str(self.workspace), str(CASES), str(ready)],
                                   env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not ready.exists():
                if process.poll() is not None:
                    self.fail(f"Child worker ended before test checkpoint: {process.communicate()!r}")
                self.assertLess(time.monotonic(), deadline, "Child worker did not reach checkpoint")
                time.sleep(.01)
            campaign_id = json.loads(ready.read_text())["campaign_id"]
            path = self.workspace / "campaigns" / campaign_id
            manifest_before = (path / "manifest.json").read_bytes()
            records_before = {record.name: record.read_bytes() for record in (path / "records").glob("*.json")}
            observer = CampaignJobs(self.workspace)
            live = observer.list()[0]
            self.assertEqual(live["state"], "running")
            self.assertTrue(live["worker_active"])
            self.assertFalse(live["can_cancel"])
            self.assertEqual((path / "manifest.json").read_bytes(), manifest_before)
            self.assertFalse((path / "provenance").exists())
            process.kill()
            process.communicate(timeout=10)
            restarted = CampaignJobs(self.workspace)
            self.addCleanup(restarted.shutdown)
            recovered = restarted.list()[0]
            self.assertEqual(recovered["state"], "interrupted")
            self.assertTrue(recovered["valid_evidence"])
            self.assertFalse(recovered["worker_active"])
            self.assertEqual(recovered["completed_runs"], 1)
            manifest = json.loads((path / "manifest.json").read_bytes())
            receipt = path / manifest["recovery"]["receipt"]
            self.assertEqual((receipt / "manifest.original.json").read_bytes(), manifest_before)
            self.assertEqual({record.name: record.read_bytes() for record in (path / "records").glob("*.json")}, records_before)
            self.assertEqual(len(load_results(path)), 1)
            self.assertEqual(json.loads((path / "summary.json").read_text())["campaign_state"], "interrupted")
            restarted.list()
            self.assertEqual(len(list((path / "provenance").glob("recovery-*"))), 1)
            # Restart permits a new mock run; it does not silently resume or
            # duplicate the interrupted campaign's remaining planned executions.
            started = restarted.start(self.cases, variants=["P"], sources=["clean"], repeats=1, seed=42, document_ids=[])
            restarted._jobs[started["campaign_id"]]["thread"].join(timeout=10)
            self.assertFalse(restarted.running)
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)

    def test_unowned_running_cli_and_legacy_ui_records_are_not_rewritten(self):
        for name in ("cli-running", "campaigns/campaign-" + "a" * 32):
            path = self.cli_campaign(name)
            manifest = json.loads((path / "manifest.json").read_text())
            manifest["state"] = "running"
            write_json(path / "manifest.json", manifest)
        originals = {path: path.read_bytes() for path in self.workspace.rglob("manifest.json")}
        rows = CampaignJobs(self.workspace).list()
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["state"], "running")
            self.assertIsNone(row["worker_active"])
            self.assertFalse(row["managed_worker"])
            self.assertFalse(row["can_cancel"])
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)

    def test_one_damaged_campaign_does_not_hide_healthy_campaigns(self):
        healthy = self.cli_campaign("healthy")
        broken_manifest = self.cli_campaign("bad-manifest")
        broken_hash = self.cli_campaign("bad-hash")
        broken_metadata = self.cli_campaign("bad-metadata")
        (broken_manifest / "manifest.json").write_text('{"state":')
        metadata = json.loads((broken_metadata / "manifest.json").read_text())
        metadata["created_at"] = {"invalid": "timestamp"}
        write_json(broken_metadata / "manifest.json", metadata)
        record = next((broken_hash / "records").glob("*.json"))
        value = json.loads(record.read_text())
        value["final_text"] = "changed after run"
        write_json(record, value)
        originals = {path: path.read_bytes() for directory in (broken_manifest, broken_hash, broken_metadata)
                     for path in directory.rglob("*") if path.is_file()}
        jobs = CampaignJobs(self.workspace)
        rows = jobs.list()
        self.assertEqual(len(rows), 4)
        self.assertEqual(len([row for row in rows if row["state"] == "completed"]), 1)
        damaged = [row for row in rows if row["state"] == "damaged"]
        self.assertEqual(len(damaged), 3)
        self.assertTrue(all(row["valid_evidence"] is False and row["error"] for row in damaged))
        self.assertEqual(len(load_results(healthy)), 1)
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)

    def test_owned_crash_with_invalid_or_unindexed_evidence_is_not_repaired(self):
        for corruption in ("hash", "unindexed"):
            with self.subTest(corruption=corruption):
                jobs, campaign_id, path = self.managed_campaign()
                manifest = json.loads((path / "manifest.json").read_text())
                manifest["state"] = "running"
                write_json(path / "manifest.json", manifest)
                record = next((path / "records").glob("*.json"))
                if corruption == "hash":
                    record.write_text('{}')
                else:
                    (record.parent / "run-unindexed.json").write_bytes(record.read_bytes())
                original_manifest = (path / "manifest.json").read_bytes()
                observer = CampaignJobs(self.workspace)
                row = next(row for row in observer.list() if row["campaign_id"] == campaign_id)
                self.assertEqual(row["state"], "damaged")
                self.assertFalse(row["valid_evidence"])
                self.assertFalse(row["worker_active"])
                self.assertEqual((path / "manifest.json").read_bytes(), original_manifest)
                self.assertFalse((path / "provenance").exists())

    def test_missing_owned_manifest_and_modified_finished_record_are_reported(self):
        jobs, campaign_id, path = self.managed_campaign()
        record = next((path / "records").glob("*.json"))
        record.write_text('{}')
        # Even this process's finished jobs must re-check their record hashes.
        self.assertEqual(jobs.brief(campaign_id)["state"], "damaged")
        (path / "manifest.json").unlink()
        restarted = CampaignJobs(self.workspace)
        row = next(row for row in restarted.list() if row["campaign_id"] == campaign_id)
        self.assertEqual(row["state"], "damaged")
        self.assertFalse(row["valid_evidence"])


if __name__ == "__main__":
    unittest.main()
