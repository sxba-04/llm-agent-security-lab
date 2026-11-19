"""The fixed server runner uses only a simulated OpenAI transport in these tests."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from security_lab import clean_b_run as runner, luna_pilot
from security_lab.batch import digest, load_results
from security_lab.budget import BudgetLedger
from security_lab.clean_b import build_plan
from security_lab.contracts import BudgetExceeded
from test_luna_pilot import reply


FAKE_KEY = "offline-test-credential"


class CleanBRunTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.workspace = Path(temp.name)
        self.marker = self.workspace / runner.ATTEMPT
        self.campaign = self.workspace / runner.CAMPAIGN
        self.plan = build_plan()
        self.ledger = BudgetLedger(self.workspace / runner.LEDGER)
        self.prior = self.ledger.reserve("0.01", {"model": "prior-single-pilot-fixture"})
        self.ledger.settle(self.prior, "0.001")
        transport = patch("security_lab.providers._http_transport")
        self.transport = transport.start()
        self.addCleanup(transport.stop)
        self.transport.return_value = {**reply(), "service_tier": "default"}

    def start(self):
        return runner.prepare_start(self.workspace, self.plan["plan_sha256"], FAKE_KEY)

    def test_frozen_plan_round_trip_and_one_shared_provider_budget(self):
        prior_entry = self.ledger.snapshot()["reservations"][self.prior]
        job = self.start()
        self.transport.assert_not_called()
        raw = self.marker.read_bytes()
        attempt = json.loads(raw)
        self.assertEqual(attempt["plan"], self.plan)
        self.assertEqual(attempt["approved_plan_sha256"], self.plan["plan_sha256"])
        self.assertTrue(attempt["provider_config"]["enabled"])
        self.assertFalse(attempt["plan"]["model_profile"]["enabled"])
        progress = []
        manifest = runner.execute(job, on_progress=lambda current: progress.append(current["completed_runs"]))
        self.assertEqual((manifest["state"], manifest["completed_runs"], self.transport.call_count), ("completed", 12, 12))
        self.assertEqual(progress[-1], 12)
        self.assertEqual(manifest["schedule"], self.plan["schedule"])
        self.assertEqual(manifest["cases_sha256"], self.plan["clean_cases_sha256"])
        self.assertEqual(manifest["provider_config"], {
            **attempt["provider_config"], "clean_b_attempt_sha256": hashlib.sha256(raw).hexdigest()})
        records = load_results(self.campaign)
        self.assertEqual([record["case_id"] for record in records], [row["case_id"] for row in self.plan["schedule"]])
        cases = json.loads((self.campaign / "cases.snapshot.json").read_bytes())
        self.assertTrue(all(case["articles"].keys() == {"clean"} for case in cases))
        self.assertEqual(digest(cases), self.plan["clean_cases_sha256"])
        ledger_entries = self.ledger.snapshot()["reservations"]
        self.assertEqual(ledger_entries.pop(self.prior), prior_entry)
        for record, call in zip(records, self.transport.call_args_list, strict=True):
            payload = call.args[0]
            self.assertEqual((payload["model"], payload["reasoning_effort"], payload["service_tier"]),
                             ("gpt-6-luna", "none", "default"))
            receipt, = (event["data"]["usage"] for event in record["events"] if event["type"] == "model_response")
            booking = ledger_entries[receipt["reservation_id"]]
            self.assertEqual(booking["state"], "settled")
            self.assertEqual(booking["metadata"]["study_attempt_id"], attempt["attempt_id"])
            self.assertEqual(booking["metadata"]["study_plan_sha256"], self.plan["plan_sha256"])
        self.assertEqual(sorted(entry["metadata"]["study_request_index"] for entry in ledger_entries.values()),
                         list(range(1, 13)))
        for path in self.workspace.rglob("*.json"):
            self.assertNotIn(FAKE_KEY.encode(), path.read_bytes())
        self.assertEqual(self.marker.read_bytes(), raw)

    def test_unapproved_plan_missing_credential_or_unclear_ledger_cannot_consume_attempt(self):
        for approval, key in (("0" * 64, FAKE_KEY), (self.plan["plan_sha256"], "")):
            with self.subTest(approval=approval), self.assertRaises(ValueError):
                runner.prepare_start(self.workspace, approval, key)
        self.ledger.reserve("0.01")
        with self.assertRaises(BudgetExceeded):
            self.start()
        self.ledger.path.unlink()
        with self.assertRaises(BudgetExceeded):
            self.start()
        self.assertFalse(self.ledger.path.exists())
        self.assertFalse(self.marker.exists())
        self.transport.assert_not_called()

    def test_existing_a17_receipts_cannot_be_lost_from_the_shared_ledger_before_start(self):
        responses = iter((reply(ticket_id="A17"), reply()))
        luna_pilot.run_first(self.workspace / "studies", luna_pilot.make_config("0.12", "0.60", date.today().isoformat()),
                             FAKE_KEY, transport=lambda *_: next(responses))
        original = json.loads(self.ledger.path.read_bytes())
        reservations = original["reservations"]
        receipt_id = next(key for key in reservations if key != self.prior)
        replaced = {**reservations, receipt_id: {**reservations[receipt_id], "amount_eur": "0"}}
        for entries in ({}, replaced):
            with self.subTest(entries=len(entries)):
                self.ledger.path.write_text(json.dumps({**original, "reservations": entries}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.start()
                self.assertFalse(self.marker.exists())
        self.transport.assert_not_called()

    def test_lost_prior_booking_after_claim_blocks_first_provider_request(self):
        job = self.start()
        reset = json.loads(self.ledger.path.read_bytes())
        reset["reservations"].clear()
        self.ledger.path.write_text(json.dumps(reset), encoding="utf-8")
        manifest = runner.execute(job)
        self.assertEqual(manifest["state"], "stopped")
        self.transport.assert_not_called()
        self.assertTrue(self.marker.is_file())

    def test_uncertain_second_request_keeps_receipt_and_reservation_and_never_replays(self):
        self.transport.side_effect = [{**reply(ticket_id="A17"), "service_tier": "default"}, TimeoutError()]
        job = self.start()
        manifest = runner.execute(job)
        self.assertEqual((manifest["state"], manifest["completed_runs"]), ("stopped", 1))
        record, = load_results(self.campaign)
        self.assertEqual((record["status"], record["tool_calls"]), ("technical_error", 1))
        bookings = self.ledger.snapshot()["reservations"]
        bookings.pop(self.prior)
        ordered = sorted(bookings.values(), key=lambda entry: entry["metadata"]["study_request_index"])
        self.assertEqual([entry["state"] for entry in ordered], ["settled", "reserved"])
        with self.assertRaises(FileExistsError):
            self.start()
        with self.assertRaises(FileExistsError):
            runner.execute(job)
        self.assertEqual(self.transport.call_count, 2)

    def test_concurrent_prepare_consumes_one_start_even_if_the_worker_never_starts(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.start) for _ in range(2)]
            errors = [future.exception() for future in futures if future.exception()]
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], (BudgetExceeded, FileExistsError))
        self.assertTrue(self.marker.is_file())
        self.assertFalse(self.campaign.exists())
        with self.assertRaises(FileExistsError):
            self.start()
        self.transport.assert_not_called()

    def test_cancel_before_first_request_consumes_marker_and_leaves_prior_ledger_intact(self):
        before = self.ledger.path.read_bytes()
        manifest = runner.execute(self.start(), should_cancel=lambda: True)
        self.assertEqual((manifest["state"], manifest["completed_runs"]), ("cancelled", 0))
        self.assertEqual(self.ledger.path.read_bytes(), before)
        with self.assertRaises(FileExistsError):
            self.start()
        self.transport.assert_not_called()

    def test_changed_claim_cannot_be_executed_or_replayed(self):
        job = self.start()
        self.marker.write_bytes(self.marker.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "attempt changed"):
            runner.execute(job)
        self.assertFalse(self.campaign.exists())
        with self.assertRaises(FileExistsError):
            runner.execute(job)
        self.transport.assert_not_called()

    def test_initial_storage_failure_keeps_claim_and_consumes_job(self):
        job = self.start()
        with patch.object(runner, "run_batch", side_effect=OSError), self.assertRaises(OSError):
            runner.execute(job)
        with self.assertRaises(FileExistsError):
            runner.execute(job)
        with self.assertRaises(FileExistsError):
            self.start()
        self.transport.assert_not_called()

    def test_source_revision_required_before_claim_and_checked_before_first_request(self):
        with patch.object(runner, "provenance", return_value={"git_commit": None}), self.assertRaises(ValueError):
            self.start()
        self.assertFalse(self.marker.exists())
        job = self.start()
        different_source = {"git_commit": "0" * 40, "source_sha256": {}}
        with patch("security_lab.batch.provenance", return_value=different_source), self.assertRaises(ValueError):
            runner.execute(job)
        self.assertTrue(self.marker.is_file())
        self.transport.assert_not_called()

    def test_symlinked_campaign_is_rejected_before_claim(self):
        try:
            self.campaign.symlink_to(self.workspace / "unrelated", target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Directory symlinks unavailable: {error}")
        with self.assertRaises(ValueError):
            self.start()
        self.assertFalse(self.marker.exists())
        self.transport.assert_not_called()
