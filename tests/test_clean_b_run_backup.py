import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from security_lab import backup, clean_b_evidence as evidence, clean_b_run as runner
from security_lab.batch import digest, write_json
from security_lab.budget import BudgetLedger
from security_lab.clean_b import prepare
from test_luna_pilot import reply


class CleanBRunBackupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.workspace = self.root / "workspace"
        self.source = self.root / "source"
        self.source.mkdir()
        for name in backup.SOURCE_LOCKFILES:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"controlled test fixture")
        self.git("init", "-q")
        self.git("add", ".")
        self.commit("source for experiment")
        self.prior_commit = self.git("rev-parse", "HEAD")
        self.commit("later deployment")
        provenance = {"git_commit": self.prior_commit, "source_sha256": {
            "uv.lock": hashlib.sha256((self.source / "uv.lock").read_bytes()).hexdigest()}}
        self.enterContext(patch.object(runner, "provenance", return_value=provenance))
        self.enterContext(patch("security_lab.batch.provenance", return_value=provenance))
        self.transport = self.enterContext(patch("security_lab.providers._http_transport",
                                                return_value={**reply(), "service_tier": "default"}))
        self.ledger = BudgetLedger(self.workspace / runner.LEDGER)
        original = self.ledger.reserve("0.01")
        self.ledger.settle(original, "0.001")
        self.plan, self.cases = prepare()
        self.job = runner.prepare_start(self.workspace, self.plan["plan_sha256"], "offline-test")
        self.campaign = self.workspace / runner.CAMPAIGN

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.source, text=True).strip()

    def commit(self, message):
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-q", "--allow-empty", "-m", message)

    def round_trip(self, name):
        archive = self.root / (name + ".zip")
        backup.export_workspace(self.workspace, self.source, archive)
        report = backup.restore_workspace_backup(archive, self.root / name)
        saved = Path(report["workspace"])
        self.assertTrue(report["source_evidence_complete"])
        self.assertIn(self.prior_commit, report["source_snapshots"]["included_commits"])
        self.assertEqual((saved / runner.ATTEMPT).read_bytes(), (self.workspace / runner.ATTEMPT).read_bytes())
        self.assertEqual((saved / runner.LEDGER).read_bytes(), self.ledger.path.read_bytes())
        with self.assertRaises(FileExistsError):
            runner.prepare_start(saved, self.plan["plan_sha256"], "offline-test")
        return report

    def test_marker_only_and_interrupted_initial_publication_restore_without_replay(self):
        marker_only = self.round_trip("marker")
        self.assertFalse(marker_only["evidence_complete"])
        self.assertFalse(marker_only["campaigns_complete"])
        self.assertFalse(marker_only["clean_b_paid_attempt"]["campaign_present"])
        self.campaign.mkdir()
        fragment = self.campaign / "cases.snapshot.json.0123456789abcdef.tmp"
        fragment.write_bytes(b"[")
        initial = self.round_trip("initial")
        self.assertEqual(initial["clean_b_paid_attempt"]["unpublished_writes"], [fragment.relative_to(self.workspace).as_posix()])
        self.assertEqual((Path(initial["workspace"]) / fragment.relative_to(self.workspace)).read_bytes(), b"[")
        fragment.unlink()
        write_json(self.campaign / "cases.snapshot.json", self.cases)
        self.assertEqual(self.round_trip("cases")["clean_b_paid_attempt"]["state"], "interrupted")
        write_json(self.campaign / "cases.snapshot.json", [])
        with self.assertRaisesRegex(ValueError, "case snapshot"):
            evidence.verify_paid_attempt(self.workspace)
        self.transport.assert_not_called()

    def test_stale_running_state_and_unconfirmed_transport_preserve_budget_and_lease(self):
        self.transport.side_effect = TimeoutError
        runner.execute(self.job)
        stopped = self.round_trip("unknown")
        self.assertEqual(stopped["clean_b_paid_attempt"]["state"], "stopped")
        self.assertEqual(stopped["clean_b_paid_attempt"]["pending_reservations"], 1)
        path = self.campaign / "manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["state"] = "running"
        write_json(path, manifest)
        with runner._writer_lease(self.workspace), self.assertRaisesRegex(ValueError, "active worker"):
            backup.export_workspace(self.workspace, self.source, self.root / "busy.zip")
        report = self.round_trip("interrupted")
        self.assertFalse(report["campaigns_complete"])
        self.assertEqual(report["clean_b_paid_attempt"]["state"], "interrupted")
        self.assertEqual((Path(report["workspace"]) / runner.CAMPAIGN / path.name).read_bytes(), path.read_bytes())
        self.assertEqual(self.transport.call_count, 1)

    def test_closed_run_and_tampered_shared_reservation(self):
        runner.execute(self.job)
        report = self.round_trip("closed")
        self.assertEqual(report["clean_b_paid_attempt"]["recorded_runs"], 12)
        self.assertTrue(report["campaigns_complete"])
        self.assertFalse(report["engineering_only"])
        ledger = json.loads(self.ledger.path.read_bytes())
        entries = [e for e in ledger["reservations"].values() if "study_attempt_id" in e["metadata"]]
        first, second = sorted(entries, key=lambda e:e["metadata"]["study_request_index"])[:2]
        first["metadata"]["study_request_index"], second["metadata"]["study_request_index"] = 2, 1
        write_json(self.ledger.path, ledger)
        with self.assertRaisesRegex(ValueError, "request index"):
            evidence.verify_paid_attempt(self.workspace)
        self.ledger.path.unlink()
        with self.assertRaisesRegex(ValueError, "Missing.*ledger"):
            evidence.verify_paid_attempt(self.workspace)

    def test_same_price_receipts_cannot_swap_ledger_ids_or_request_order(self):
        meta = {"study_attempt_id": "a"*32,"study_plan_sha256": runner.PLAN_V1}
        usage = {"reserved_eur":"0.01","estimated_cost_eur":"0.001","accounting":"reported_usage"}
        entries = {k: {"reserved_eur":"0.01","amount_eur":"0.001","state":"settled",
                       "metadata":{**meta,"study_request_index":i}} for i,k in enumerate(("a","b"),1)}
        def event(key,index):
            return {"type":"model_response","data":{"usage":{**usage,**meta,"reservation_id":key,"study_request_index":index}}}
        for events in [[event("b",1),event("a",2)],[event("b",2),event("a",1)]]:
            with self.subTest(events=events), self.assertRaisesRegex(ValueError, "request index"):
                evidence._receipt_ids([{"events":events}],entries,paid_series=True)

    def test_pinned_plan_and_manifest_schedule_cannot_be_replaced(self):
        runner.execute(self.job)
        manifest_path = self.campaign / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["order_seed"] += 1
        write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "differs from the original attempt"):
            evidence.verify_paid_attempt(self.workspace)
        marker_path = self.workspace / runner.ATTEMPT
        marker = json.loads(marker_path.read_bytes())
        marker["plan"]["schedule"].reverse()
        marker["plan"]["plan_sha256"] = digest({k:v for k,v in marker["plan"].items() if k!="plan_sha256"})
        marker["approved_plan_sha256"] = marker["plan"]["plan_sha256"]
        write_json(marker_path, marker)
        with self.assertRaisesRegex(ValueError, "fixed plan"):
            evidence.verify_paid_attempt(self.workspace)

    def test_missing_response_rejected_with_recomputed_record_manifest_and_event_hashes(self):
        runner.execute(self.job)
        mpath = self.campaign / "manifest.json"
        manifest = json.loads(mpath.read_bytes())
        item = manifest["runs"][0]
        path = self.campaign / item["path"]
        record = json.loads(path.read_bytes())
        record["events"] = [e for e in record["events"] if e["type"] != "model_response"]
        events = "".join(json.dumps(e, ensure_ascii=True) + "\n" for e in record["events"]).encode()
        item.update(sha256=digest(record), events_sha256=hashlib.sha256(events).hexdigest())
        write_json(path, record)
        (self.campaign / item["events_path"]).write_bytes(events)
        write_json(mpath, manifest)
        with self.assertRaisesRegex(ValueError, "receipts do not cover"):
            evidence.verify_paid_attempt(self.workspace)
        manifest.update(runs=[], completed_runs=0)
        write_json(mpath, manifest)
        with self.assertRaisesRegex(ValueError, "missing runs"):
            evidence.verify_paid_attempt(self.workspace)

    def test_other_temporary_files_remain_ineligible_for_full_backup(self):
        self.campaign.mkdir()
        unrelated = self.campaign / "notes.json.0123456789abcdef.tmp"
        unrelated.write_bytes(b"unpublished test bytes")
        with self.assertRaisesRegex(ValueError, "unfinished temporary write"):
            backup.export_workspace(self.workspace, self.source, self.root / "wrong.zip")
