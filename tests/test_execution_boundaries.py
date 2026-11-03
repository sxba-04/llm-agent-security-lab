"""Received proposals remain evidence when execution stops before their effects."""
import unittest
from unittest.mock import patch

from security_lab.contracts import ModelReply, ToolCall
from security_lab.core import run_case
from tests.test_core import events, fixture


class _RespondThenStopModel:
    name = "offline-stop-boundary"
    is_mock = True

    def __init__(self, on_second_response):
        self.responses = 0
        self.on_second_response = on_second_response

    def respond(self, messages, tools):
        self.responses += 1
        if self.responses == 1:
            return ModelReply(tool_calls=[ToolCall("read_ticket", {"ticket_id": "B08"}, "read")])
        self.on_second_response()
        return ModelReply(tool_calls=[ToolCall("append_note", {"ticket_id": "A17", "text": "Must not execute"}, "write")])


class ExecutionBoundaryTests(unittest.TestCase):
    def assert_received_response_preserved(self, result):
        self.assertEqual(result["model_calls"], 2)
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(len(events(result, "model_response")), 2)
        self.assertEqual([call["call_id"] for call in events(result, "proposal")], ["read", "write"])
        self.assertEqual([item["ticket_id"] for item in events(result, "context_exposure")], ["B08"])
        self.assertFalse(events(result, "context_submission_uncertain"))
        self.assertFalse(events(result, "backend_write"))
        self.assertEqual(result["final_tickets"]["A17"]["notes"], [])
        self.assertEqual(result["events"][-1]["type"], "run_end")

    def test_cancellation_after_response_keeps_prior_read_and_proposals(self):
        cancelled = False

        def cancel():
            nonlocal cancelled
            cancelled = True

        model = _RespondThenStopModel(cancel)
        result = run_case(fixture(), "B", "attack", model, should_cancel=lambda: cancelled)
        self.assertEqual(result["status"], "cancelled")
        self.assert_received_response_preserved(result)

    def test_deadline_after_response_keeps_evidence_without_late_effect(self):
        clock = 0.0

        def exceed_deadline():
            nonlocal clock
            clock = 11.0

        model = _RespondThenStopModel(exceed_deadline)
        with patch("security_lab.core.time.monotonic", side_effect=lambda: clock):
            result = run_case(fixture(), "B", "attack", model, timeout_seconds=10)
        self.assertEqual(result["status"], "limit_exceeded")
        self.assertEqual(events(result, "limit"), [{"reason": "time"}])
        self.assert_received_response_preserved(result)
