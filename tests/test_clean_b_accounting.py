"""Offline checks for B-study claims and reservation provenance in the shared ledger."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from security_lab.batch import load_results, run_batch
from security_lab.budget import BudgetLedger
from security_lab.clean_b import prepare
from security_lab.contracts import BudgetExceeded
from security_lab.providers import OpenAIModel


class CleanBAccountingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.ledger = BudgetLedger(self.root / "budget.json", 1, 1)
        self.plan, self.cases = prepare()
        self.plan_hash = self.plan["plan_sha256"]
        self.attempt_id = "abcd" * 8

    def model(self, transport, **context):
        return OpenAIModel({**self.plan["model_profile"], "enabled": True},
                           "offline-test-key", self.ledger, transport, **context)

    def historical_entry(self, amount="0.01"):
        reservation = self.ledger.reserve(amount, {"model": "historical-pilot"})
        self.assertTrue(self.ledger.settle(reservation, amount))
        return reservation

    def test_incomplete_or_noncanonical_identifiers_are_rejected_before_use(self):
        transport = Mock()
        for attempt, plan in ((None, self.plan_hash), (self.attempt_id, None),
                              ("NOT-A-UUID", self.plan_hash), (self.attempt_id, "INVALID")):
            with self.subTest(attempt=attempt, plan=plan), self.assertRaises(ValueError):
                self.model(transport, study_attempt_id=attempt, study_plan_sha256=plan)
        transport.assert_not_called()
        self.assertFalse(self.ledger.path.exists())

    def test_settled_and_uncertain_requests_remain_bound_to_the_original_attempt(self):
        old_id = self.historical_entry()
        previous = self.ledger.snapshot()["reservations"][old_id]
        actual_requests = []
        def transport(payload, _key, _timeout):
            actual_requests.append(payload)
            reservations = self.ledger.snapshot()["reservations"]
            self.assertEqual(len(reservations), 1 + len(actual_requests))
            if len(actual_requests) == 2:
                raise TimeoutError("simulated unknown transport outcome")
            return {"model": self.plan["model_profile"]["model"], "service_tier": "default",
                    "usage": {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40,
                              "reservation_id": "external-label", "study_attempt_id": "external-label"},
                    "choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": None,
                                 "tool_calls": [{"id": "read", "type": "function", "function": {
                                     "name": "read_ticket", "arguments": '{"ticket_id":"A17"}'}}]}}]}

        model = self.model(transport, study_attempt_id=self.attempt_id, study_plan_sha256=self.plan_hash)
        with self.ledger.preflight_study("0.50", study_plan_sha256=self.plan_hash):
            pass
        output = self.root / "campaign"
        manifest = run_batch(self.cases[:2], output, lambda *_: model, variants=["B"], sources=["clean"])

        self.assertEqual((manifest["state"], manifest["planned_runs"]), ("stopped", 2))
        record, = load_results(output)
        self.assertEqual((record["status"], record["tool_calls"], len(actual_requests)), ("technical_error", 1, 2))
        with self.assertRaises(BudgetExceeded):
            model.respond([], [])
        self.assertEqual(len(actual_requests), 2)
        receipts = [event["data"]["usage"] for event in record["events"] if event["type"] == "model_response"]
        receipt, = receipts
        self.assertEqual(receipt["study_attempt_id"], self.attempt_id)
        self.assertEqual(receipt["study_plan_sha256"], self.plan_hash)
        self.assertEqual(receipt["study_request_index"], 1)
        entries = self.ledger.snapshot()["reservations"]
        self.assertEqual(entries.pop(old_id), previous)
        self.assertEqual(entries[receipt["reservation_id"]]["state"], "settled")
        for index, entry in enumerate(entries.values(), start=1):
            self.assertEqual(entry["state"], "settled" if index == 1 else "reserved")
            self.assertEqual(entry["metadata"]["study_attempt_id"], self.attempt_id)
            self.assertEqual(entry["metadata"]["study_plan_sha256"], self.plan_hash)
            self.assertEqual(entry["metadata"]["study_request_index"], index)
        for payload in actual_requests:
            self.assertEqual((payload["reasoning_effort"], payload["service_tier"]), ("none", "default"))
            self.assertNotIn(self.attempt_id, json.dumps(payload))
            self.assertNotIn(self.plan_hash, json.dumps(payload))
        self.assertNotIn("offline-test-key", self.ledger.path.read_text(encoding="utf-8"))

    def test_preflight_holds_ledger_lock_during_claim_without_charging(self):
        old = self.historical_entry("0.50")
        original = self.ledger.path.read_bytes()
        with self.ledger.preflight_study("0.50", study_plan_sha256=self.plan_hash) as reservations:
            self.assertEqual(reservations, json.loads(original)["reservations"])
            self.assertEqual(reservations[old]["state"], "settled")
            with self.assertRaises(BudgetExceeded):
                BudgetLedger(self.ledger.path).reserve("0.01")
            self.assertTrue(self.ledger.lock_path.exists())
        self.assertEqual(self.ledger.path.read_bytes(), original)
        self.assertFalse(self.ledger.lock_path.exists())

    def test_read_only_budget_review_neither_creates_a_workspace_nor_arms_the_provider(self):
        missing = BudgetLedger(self.root / "missing" / "budget.json", 1, 1)
        with self.assertRaises(BudgetExceeded):
            missing.review_study("0.50", study_plan_sha256=self.plan_hash)
        self.assertFalse(missing.path.parent.exists())
        self.historical_entry()
        original = self.ledger.path.read_bytes()
        self.assertEqual(self.ledger.review_study("0.50", study_plan_sha256=self.plan_hash),
                         json.loads(original)["reservations"])
        model = self.model(Mock(), study_attempt_id=self.attempt_id, study_plan_sha256=self.plan_hash)
        with self.assertRaises(BudgetExceeded):
            model.respond([], [])
        self.assertEqual(self.ledger.path.read_bytes(), original)

    def test_preflight_refuses_unreconciled_or_previously_used_budget_before_claim(self):
        def rejected():
            with self.assertRaises(BudgetExceeded), self.ledger.preflight_study("0.50", study_plan_sha256=self.plan_hash):
                self.fail("invalid ledger admitted the claim")

        rejected()  # missing historical ledger
        self.ledger.path.write_text("broken", encoding="utf-8")
        rejected()
        self.ledger.path.unlink()
        previous = self.ledger.reserve("0.10", {"study_plan_sha256": self.plan_hash})
        rejected()  # open reservation
        self.ledger.settle(previous, "0.10")
        rejected()  # earlier settled request for the same plan
        self.ledger.path.unlink()
        self.historical_entry("0.51")
        rejected()  # less than the requested study cap available
        self.ledger.path.unlink()
        self.ledger.settle(self.ledger.reserve("0.10"), "0.15")
        rejected()  # ledger halted by a prior overrun

    def test_bound_request_never_recreates_a_missing_project_ledger(self):
        self.historical_entry()
        transport = Mock()
        model = self.model(transport, study_attempt_id=self.attempt_id, study_plan_sha256=self.plan_hash)
        with self.ledger.preflight_study("0.50", study_plan_sha256=self.plan_hash):
            pass
        self.ledger.path.unlink()
        with self.assertRaises(BudgetExceeded):
            model.respond([], [])
        transport.assert_not_called()
        self.assertFalse(self.ledger.path.exists())

    def test_loss_of_a_preflight_or_new_settlement_stops_before_the_next_request(self):
        for lost in ("historical", "current-study"):
            with self.subTest(lost=lost):
                self.ledger = BudgetLedger(self.root / (lost + ".json"), 1, 1)
                old = self.historical_entry()
                reply = {"model": self.plan["model_profile"]["model"], "service_tier": "default",
                         "usage": {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
                         "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "OK"}}]}
                transport = Mock(return_value=reply)
                model = self.model(transport, study_attempt_id=self.attempt_id, study_plan_sha256=self.plan_hash)
                with self.ledger.preflight_study("0.50", study_plan_sha256=self.plan_hash):
                    pass
                first = model.respond([], [])
                self.assertEqual(first.usage["accounting"], "reported_usage")
                damaged = json.loads(self.ledger.path.read_bytes())
                del damaged["reservations"][old if lost == "historical" else first.usage["reservation_id"]]
                self.ledger.path.write_text(json.dumps(damaged), encoding="utf-8")
                with self.assertRaises(BudgetExceeded):
                    model.respond([], [])
                transport.assert_called_once()
                self.assertEqual(json.loads(self.ledger.path.read_bytes()), damaged)

    def test_loss_during_transport_preserves_response_and_stops_before_tool_effect(self):
        old = self.historical_entry()
        def transport(*_):
            damaged = json.loads(self.ledger.path.read_bytes())
            del damaged["reservations"][old]
            self.ledger.path.write_text(json.dumps(damaged), encoding="utf-8")
            return {"model": self.plan["model_profile"]["model"], "service_tier": "default",
                    "usage": {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
                    "choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": None,
                                 "tool_calls": [{"id": "read", "type": "function", "function": {
                                     "name": "read_ticket", "arguments": '{"ticket_id":"A17"}'}}]}}]}

        injected = Mock(side_effect=transport)
        model = self.model(injected, study_attempt_id=self.attempt_id, study_plan_sha256=self.plan_hash)
        with self.ledger.preflight_study("0.50", study_plan_sha256=self.plan_hash):
            pass
        output = self.root / "interrupted-study"
        manifest = run_batch(self.cases[:2], output, lambda *_: model, variants=["B"], sources=["clean"])
        self.assertEqual(manifest["state"], "stopped")
        record, = load_results(output)
        self.assertEqual((record["status"], record["tool_calls"]), ("technical_error", 0))
        injected.assert_called_once()
        receipt, = [e["data"]["usage"] for e in record["events"] if e["type"] == "model_response"]
        self.assertEqual((receipt["accounting"], receipt["total_tokens"]), ("settlement_failed", 40))
        persisted = json.loads(self.ledger.path.read_bytes())["reservations"]
        self.assertEqual(persisted[receipt["reservation_id"]]["state"], "reserved")
