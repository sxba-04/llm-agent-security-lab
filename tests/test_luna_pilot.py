"""Network-free acceptance tests for the isolated, clean-ticket pilot."""
import hashlib
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from security_lab import luna_pilot as pilot


TEST_CREDENTIAL = "offline-only-pilot-credential"


def reply(*, ticket_id=None, model="gpt-6-luna"):
    message = {"role": "assistant", "content": "Synthetische Testantwort."}
    reason = "stop"
    if ticket_id is not None:
        reason = "tool_calls"
        message.update(content=None, tool_calls=[{
            "id": "offline-call",
            "type": "function",
            "function": {"name": "read_ticket", "arguments": json.dumps({"ticket_id": ticket_id})},
        }])
    return {
        "id": "offline-response",
        "model": model,
        "choices": [{"message": message, "finish_reason": reason}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 20, "total_tokens": 140},
    }


def response_receipts(record):
    return [event["data"]["usage"]["raw_response"] for event in record["events"]
            if event["type"] == "model_response"]


class LunaPilotTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name) / "workspace"
        self.config = pilot.make_config("1.00", "5.00", date.today().isoformat())

    def execute(self, transport):
        return pilot.run_first(self.workspace, self.config, TEST_CREDENTIAL, transport=transport)

    def test_plan_and_incomplete_start_acknowledgement_never_read_credentials(self):
        options = ["--input-eur-per-million", "1", "--output-eur-per-million", "5",
                   "--price-checked-on", date.today().isoformat(), "--workspace", str(self.workspace)]
        with patch.object(pilot, "os") as environment, patch.object(pilot, "run_first") as run:
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(pilot.main(["plan", *options]), 0)
            plan = json.loads(output.getvalue())
            self.assertEqual((plan["case_id"], plan["variant"], plan["source"]), ("DEV-G1-01", "P", "clean"))
            for flags in ([], ["--allow-paid-api"], ["--isolation-acknowledged"]):
                with self.subTest(flags=flags), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                    pilot.main(["run-first", *options, *flags])
                self.assertEqual(error.exception.code, 2)
            environment.environ.get.assert_not_called()
            run.assert_not_called()
        self.assertFalse(self.workspace.exists())

    def test_authorized_read_uses_only_fixed_clean_source_and_settles_usage(self):
        transport = Mock(side_effect=[reply(ticket_id="A17"), reply()])
        record = self.execute(transport)
        self.assertEqual(record["case_id"], "DEV-G1-01")
        self.assertEqual((record["source"], record["variant"], record["status"]), ("clean", "P", "completed"))
        self.assertEqual(transport.call_count, 2)
        payload = transport.call_args_list[0].args[0]
        self.assertEqual(payload["model"], "gpt-6-luna")
        self.assertEqual(payload["reasoning_effort"], "none")
        self.assertEqual(payload["service_tier"], "default")
        self.assertTrue(record["technical_acceptance"])
        self.assertFalse(payload["store"])
        self.assertFalse(payload["parallel_tool_calls"])
        self.assertNotIn("temperature", payload)
        self.assertNotIn("seed", payload)
        self.assertEqual({tool["function"]["name"] for tool in payload["tools"]}, {"read_ticket", "append_note"})
        fixture = pilot.load_pilot_case()
        self.assertEqual(record["original_article"], fixture["articles"]["clean"])
        self.assertIn(fixture["articles"]["clean"], payload["messages"][-1]["content"])
        tool_result = transport.call_args_list[1].args[0]["messages"][-1]
        self.assertEqual(json.loads(tool_result["content"])["ticket"]["id"], "A17")
        usage = [event["data"]["usage"] for event in record["events"] if event["type"] == "model_response"]
        self.assertEqual([value["accounting"] for value in usage], ["reported_usage"] * 2)
        self.assertEqual(record["initial_tickets"], record["final_tickets"])
        folder = self.workspace / "luna-clean-first"
        receipt = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
        for basename in ("attempt", "result"):
            expected_hash = hashlib.sha256((folder / (basename + ".json")).read_bytes()).hexdigest()
            self.assertEqual(receipt[basename + "_sha256"], expected_hash)
        for path in self.workspace.rglob("*"):
            if path.is_file():
                self.assertNotIn(TEST_CREDENTIAL.encode(), path.read_bytes())

    def test_alias_and_consistent_dated_snapshot_preserve_receipt_and_request_alias(self):
        for reported in ("gpt-6-luna", "gpt-6-luna-2024-02-29"):
            with self.subTest(reported=reported):
                responses = [reply(model=reported, ticket_id="A17"), reply(model=reported)]
                transport = Mock(side_effect=responses)
                record = pilot.run_first(self.workspace / reported, self.config, TEST_CREDENTIAL, transport=transport)
                self.assertEqual([call.args[0]["model"] for call in transport.call_args_list], ["gpt-6-luna"] * 2)
                self.assertEqual(record["observed_models"], [reported])
                self.assertTrue(record["technical_acceptance"])
                self.assertEqual(record["status"], "completed")
                self.assertEqual(response_receipts(record), responses)

    def test_changed_reported_identity_stops_before_the_next_ticket_action(self):
        alias = "gpt-6-luna"
        snapshot = "gpt-6-luna-2026-11-01"
        pairs = ((snapshot, "gpt-6-luna-2026-11-02"), (snapshot, alias), (alias, snapshot))
        for index, (first, second) in enumerate(pairs):
            with self.subTest(first=first, second=second):
                responses = [reply(model=first, ticket_id="A17"), reply(model=second, ticket_id="A17")]
                transport = Mock(side_effect=responses)
                record = pilot.run_first(self.workspace / str(index), self.config, TEST_CREDENTIAL,
                                         transport=transport)
                self.assertEqual(transport.call_count, 2)
                self.assertEqual(record["status"], "technical_error")
                self.assertFalse(record["technical_acceptance"])
                reads = [event for event in record["events"] if event["type"] == "backend_read"]
                self.assertEqual(len(reads), 1)
                self.assertEqual(response_receipts(record), responses)

    def test_foreign_family_or_invalid_dated_suffix_has_no_ticket_effect(self):
        names = ("gpt-6-sol-2026-11-01", "gpt-6-luna-２０２６-１１-０１",
                 "gpt-6-luna-2026-W45-1", "gpt-6-luna-2026-02-29", "gpt-6-luna-20261101")
        for index, reported in enumerate(names):
            with self.subTest(reported=reported):
                response = reply(model=reported, ticket_id="A17")
                transport = Mock(return_value=response)
                record = pilot.run_first(self.workspace / str(index), self.config, TEST_CREDENTIAL,
                                         transport=transport)
                transport.assert_called_once()
                self.assertEqual(record["status"], "technical_error")
                self.assertFalse(record["technical_acceptance"])
                self.assertEqual(record["tool_calls"], 0)
                self.assertEqual(record["observed_models"], [reported])
                self.assertEqual(response_receipts(record), [response])

    def test_policy_rejects_unassigned_ticket_before_it_can_be_read(self):
        transport = Mock(side_effect=[reply(ticket_id="B08"), reply()])
        record = self.execute(transport)
        self.assertFalse(record["technical_acceptance"])
        decisions = [event["data"] for event in record["events"] if event["type"] == "policy_decision"]
        self.assertEqual([(item["enabled"], item["allowed"]) for item in decisions], [(True, False)])
        self.assertFalse(any(event["type"] in {"backend_read", "backend_write"} for event in record["events"]))
        tool_result = transport.call_args_list[1].args[0]["messages"][-1]
        self.assertEqual(json.loads(tool_result["content"]), {"error": "not_authorized"})

    def test_partial_evidence_directory_prevents_repeat_without_a_marker(self):
        output = self.workspace / "luna-clean-first"
        output.mkdir(parents=True)
        (output / "result.json").write_text("{}", encoding="utf-8")
        transport = Mock()
        with self.assertRaises(FileExistsError):
            self.execute(transport)
        transport.assert_not_called()

    def test_incomplete_or_unexpected_receipt_stops_before_tool_or_second_request(self):
        overrun = {"prompt_tokens": 100000, "completion_tokens": 20, "total_tokens": 100020}
        cases = (("model", None), ("model", "another-model"), ("usage", None), ("usage", overrun),
                 ("service_tier", "priority"))
        for index, (key, value) in enumerate(cases):
            with self.subTest(key=key, value=value):
                transport = Mock(return_value={**reply(ticket_id="A17"), key: value})
                record = pilot.run_first(self.workspace / str(index), self.config, TEST_CREDENTIAL,
                                         transport=transport)
                transport.assert_called_once()
                self.assertEqual(record["status"], "technical_error")
                self.assertEqual(record["tool_calls"], 0)
                self.assertFalse(record["technical_acceptance"])

    def test_modified_model_or_limits_rejected_before_transport(self):
        for field, value in (("model", "different-model"), ("max_requests", 20), ("run_budget_eur", "8")):
            with self.subTest(field=field):
                config = {**self.config, field: value}
                transport = Mock()
                with self.assertRaises(ValueError):
                    pilot.run_first(self.workspace / field, config, TEST_CREDENTIAL, transport=transport)
                transport.assert_not_called()

    def test_modified_catalog_rejected_before_transport(self):
        repository_copy = self.workspace.parent / "repository"
        case_directory = repository_copy / "cases" / "dev"
        shutil.copytree(pilot.ROOT / "cases" / "dev", case_directory)
        path = case_directory / "dev-g1-01.json"
        case = json.loads(path.read_text(encoding="utf-8"))
        case["articles"]["clean"] += " Lokale Bearbeitung."
        path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
        transport = Mock()
        with patch.object(pilot, "ROOT", repository_copy), self.assertRaises(ValueError):
            self.execute(transport)
        transport.assert_not_called()

    def test_uncertain_response_preserves_reservation_and_rejects_second_start(self):
        transport = Mock(side_effect=OSError(TEST_CREDENTIAL))
        record = self.execute(transport)
        self.assertEqual(record["status"], "technical_error")
        transport.assert_called_once()
        self.assertNotIn(TEST_CREDENTIAL, json.dumps(record))
        self.assertFalse(any(event["type"] == "model_response" for event in record["events"]))
        with self.assertRaises(FileExistsError):
            self.execute(transport)
        transport.assert_called_once()
        ledgers = []
        for path in self.workspace.rglob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "reservations" in data:
                ledgers.append(data)
        self.assertEqual(len(ledgers), 1)
        reservations = list(ledgers[0]["reservations"].values())
        self.assertEqual(len(reservations), 1)
        self.assertEqual(reservations[0]["state"], "reserved")
        self.assertGreater(float(reservations[0]["amount_eur"]), 0)
