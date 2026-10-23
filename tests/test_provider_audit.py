"""Offline regressions: malformed provider output must never erase audit runs."""
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
import base64
import http.client
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from security_lab.batch import load_results, run_batch
from security_lab.budget import BudgetLedger
from security_lab.cases import load_cases
from security_lab.cli import main
from security_lab.providers import OpenAIModel


CONFIG = {
    "enabled": True, "model": "offline-fixture-model", "max_completion_tokens": 100,
    "max_input_tokens": 100000, "max_requests": 4, "run_budget_eur": 1,
    "input_eur_per_million": 1, "output_eur_per_million": 2,
    "price_reference": "Invented offline test rates only", "price_checked_on": "2026-10-23",
}


def response(*, tool=None, arguments=None, text=None):
    message = {"role": "assistant", "content": text}
    if tool:
        message["tool_calls"] = [{"id": "call-fixture", "type": "function",
                                  "function": {"name": tool, "arguments": arguments}}]
    return {"id": "offline-response", "model": "offline-fixture-snapshot",
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            "choices": [{"message": message, "finish_reason": "tool_calls" if tool else "stop"}]}


def events(record, kind):
    return [event["data"] for event in record["events"] if event["type"] == kind]


class ProviderAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.case = load_cases(Path(__file__).parents[1] / "cases/dev")[0]

    def campaign(self, replies, name):
        pending = deepcopy(replies)
        calls = []
        ledger = BudgetLedger(self.root / (name + ".budget.json"), 5, 1)

        def transport(payload, key, timeout):
            calls.append(deepcopy(payload))
            return pending.pop(0)

        model = OpenAIModel(CONFIG, "FAKE-OFFLINE-KEY-NOT-A-CREDENTIAL", ledger, transport)
        output = self.root / name
        manifest = run_batch([self.case], output, lambda *_: model,
                             variants=["B"], sources=["attack"])
        records = load_results(output)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["provider"], "openai")
        # Require strict serializability even if storage also escapes Unicode.
        json.dumps(record, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.assertNotIn("FAKE-OFFLINE-KEY-NOT-A-CREDENTIAL", json.dumps(record))
        event_file = output / "events" / (record["run_id"] + ".jsonl")
        self.assertEqual([json.loads(line) for line in event_file.read_text().splitlines()], record["events"])
        return manifest, record, ledger, calls

    def test_cli_rejects_disabled_and_nested_secret_configs_without_creating_artifacts(self):
        template = json.loads((Path(__file__).parents[1] / "configs/api.example.json").read_text())
        inputs = (template, {**CONFIG, "auth": {"api_key": "FAKE-NESTED-SECRET"}},
                  {**template, "auth": [{"token": "FAKE-NESTED-SECRET"}]})
        for index, config in enumerate(inputs):
            config_path = self.root / (str(index) + ".config.json")
            config_path.write_text(json.dumps(config))
            output = self.root / (str(index) + ".campaign")
            ledger = self.root / (str(index) + ".ledger.json")
            stdout, stderr = io.StringIO(), io.StringIO()
            with self.subTest(index=index), patch.dict("os.environ", {"OPENAI_API_KEY": "FAKE-ENV-SECRET"}), patch(
                    "security_lab.providers._http_transport", side_effect=AssertionError("network attempted")), redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(["run", "--provider", "openai", "--allow-paid-api", "--isolation-acknowledged",
                             "--api-config", str(config_path), "--cases", str(Path(__file__).parents[1] / "cases/dev"),
                             "--output", str(output), "--ledger", str(ledger)])
            self.assertEqual(code, 2)
            self.assertFalse(output.exists())
            self.assertFalse(ledger.exists())
            for marker in ("FAKE-ENV-SECRET", "FAKE-NESTED-SECRET"):
                self.assertNotIn(marker, stdout.getvalue() + stderr.getvalue())

    def test_nonfinite_and_escaped_surrogate_arguments_preserve_prior_effect_and_reject_write(self):
        for index, value in enumerate(("NaN", "Infinity", "-Infinity", "1e309", '"\\ud800"')):
            arguments = '{"ticket_id":"A17","text":' + value + '}'
            with self.subTest(value=value):
                manifest, record, ledger, calls = self.campaign([
                    response(tool="read_ticket", arguments='{"ticket_id":"B08"}'),
                    response(tool="append_note", arguments=arguments),
                    response(text="Offline fixture completed."),
                ], "invalid-arguments-" + str(index))
                self.assertEqual(manifest["state"], "completed")
                self.assertEqual(record["status"], "completed")
                self.assertTrue(record["metrics"]["backend_violation"])
                self.assertTrue(record["metrics"]["context_disclosure"])
                self.assertEqual(len(events(record, "backend_read")), 1)
                self.assertEqual(len(events(record, "context_exposure")), 1)
                self.assertFalse(events(record, "backend_write"))
                self.assertFalse(record["final_tickets"]["A17"]["notes"])
                self.assertEqual(events(record, "proposal")[1]["arguments"],
                                 {"__invalid_arguments_json__": arguments})
                self.assertEqual(events(record, "model_response")[1]["usage"]["raw_response"]
                                 ["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"], arguments)
                self.assertEqual(len(calls), 3)
                self.assertTrue(all(item["state"] == "settled" for item in ledger.snapshot()["reservations"].values()))

    def test_invalid_received_plan_keeps_confirmed_context_costs_and_raw_without_effects(self):
        invalid = response(tool="append_note", arguments='{"ticket_id":"A17","text":"must not execute"}')
        invalid["choices"][0]["message"]["tool_calls"] *= 2
        manifest, record, ledger, calls = self.campaign([
            response(tool="read_ticket", arguments='{"ticket_id":"B08"}'), invalid,
        ], "duplicate-id")
        self.assertEqual(manifest["state"], "stopped")
        self.assertEqual(record["status"], "technical_error")
        self.assertEqual(len(calls), 2)
        self.assertFalse(events(record, "context_submission_uncertain"))
        self.assertEqual(len(events(record, "context_exposure")), 1)
        self.assertFalse(events(record, "backend_write"))
        self.assertEqual(len(events(record, "proposal")), 1)
        replies = events(record, "model_response")
        self.assertEqual(len(replies), 2)
        self.assertEqual(replies[1]["finish_reason"], "invalid_response")
        self.assertEqual(replies[1]["usage"]["raw_response"], invalid)
        self.assertEqual(replies[1]["usage"]["accounting"], "reported_usage")
        self.assertFalse(record["metrics"]["valid_for_rates"])
        self.assertTrue(record["metrics"]["backend_violation"])
        self.assertTrue(record["metrics"]["context_disclosure"])
        self.assertAlmostEqual(float(ledger.snapshot()["accounted_eur"]), 0.00028)

    def test_http_200_body_failure_retains_context_partial_evidence_and_reservation(self):
        partial = b'{"id":"partial-response"'
        failures = (http.client.IncompleteRead(partial, 20), TimeoutError("FAKE-ERROR-SECRET"),
                    OSError("FAKE-ERROR-SECRET"))
        for index, failure in enumerate(failures):
            first, second = MagicMock(), MagicMock()
            first.__enter__.return_value.status = 200
            first.__enter__.return_value.read.return_value = json.dumps(
                response(tool="read_ticket", arguments='{"ticket_id":"B08"}')).encode()
            second.__enter__.return_value.status = 200
            second.__enter__.return_value.read.side_effect = failure
            opener = MagicMock()
            opener.open.side_effect = [first, second]
            ledger = BudgetLedger(self.root / (str(index) + ".http-budget.json"), 5, 1)
            model = OpenAIModel(CONFIG, "FAKE-OFFLINE-KEY", ledger)
            output = self.root / (str(index) + ".http-campaign")
            with self.subTest(failure=type(failure).__name__), patch(
                    "security_lab.providers.urllib.request.build_opener", return_value=opener):
                manifest = run_batch([self.case], output, lambda *_: model,
                                     variants=["B"], sources=["attack"])
            self.assertEqual(manifest["state"], "stopped")
            record = load_results(output)[0]
            self.assertEqual(record["status"], "technical_error")
            self.assertEqual(opener.open.call_count, 2)
            self.assertEqual(len(events(record, "backend_read")), 1)
            self.assertEqual(len(events(record, "context_exposure")), 1)
            self.assertFalse(events(record, "context_submission_uncertain"))
            self.assertFalse(events(record, "backend_write"))
            self.assertEqual(len(events(record, "proposal")), 1)
            replies = events(record, "model_response")
            self.assertEqual(len(replies), 2)
            usage = replies[1]["usage"]
            self.assertEqual(usage["accounting"], "reservation_retained")
            self.assertTrue(usage["raw_response_body_incomplete"])
            self.assertFalse(usage["raw_response_body_truncated"])
            self.assertEqual(base64.b64decode(usage["raw_response_body_base64"]), partial if index == 0 else b"")
            self.assertTrue(record["metrics"]["context_disclosure"])
            self.assertFalse(record["metrics"]["valid_for_rates"])
            self.assertNotIn("FAKE-ERROR-SECRET", json.dumps(record))
            self.assertNotIn("FAKE-OFFLINE-KEY", json.dumps(record))
            self.assertEqual(sorted(item["state"] for item in ledger.snapshot()["reservations"].values()),
                             ["reserved", "settled"])

    def test_unpaired_surrogate_in_response_text_preserves_escaped_evidence(self):
        invalid = response(text="invalid-\ud800-text")
        manifest, record, _, calls = self.campaign([
            response(tool="read_ticket", arguments='{"ticket_id":"B08"}'), invalid,
        ], "surrogate-response")
        self.assertEqual(manifest["state"], "stopped")
        self.assertEqual(record["status"], "technical_error")
        self.assertEqual(len(calls), 2)
        self.assertFalse(record["final_text"])
        self.assertTrue(record["metrics"]["context_disclosure"])
        usage = events(record, "model_response")[1]["usage"]
        self.assertEqual(usage["raw_response_escaped"], json.dumps(invalid, ensure_ascii=True))
        self.assertIsNone(usage["raw_response"])
        self.assertFalse(usage["raw_response_escaped_truncated"])


if __name__ == "__main__":
    unittest.main()
