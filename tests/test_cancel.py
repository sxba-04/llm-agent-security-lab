import unittest
from pathlib import Path

from security_lab.cases import load_cases
from security_lab.core import run_case
from security_lab.contracts import ModelReply, ToolCall
from security_lab.evaluation import evaluate_run
from security_lab.models import ScriptedModel


class CancelTests(unittest.TestCase):
    def test_cancel_before_first_request(self):
        case = load_cases(Path("cases/dev"))[0]
        result = run_case(case, "B", "clean", ScriptedModel(case, "clean"), should_cancel=lambda: True)
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["model_calls"], 0)
        self.assertFalse(evaluate_run(result)["valid_for_rates"])

    def test_cancel_after_response_preserves_proposal_without_effect(self):
        case = load_cases(Path("cases/dev"))[0]
        cancelled = False

        class Model:
            name = "cancel-test"
            is_mock = True

            def respond(self, messages, tools):
                nonlocal cancelled
                cancelled = True
                return ModelReply(tool_calls=[ToolCall("read_ticket", {"ticket_id": "B08"})])

        result = run_case(case, "B", "attack", Model(), should_cancel=lambda: cancelled)
        self.assertEqual(result["status"], "cancelled")
        kinds = [e["type"] for e in result["events"]]
        self.assertIn("model_response", kinds)
        self.assertIn("proposal", kinds)
        self.assertNotIn("backend_read", kinds)
        self.assertEqual(result["document_source"]["text_sha256"], next(e for e in result["events"] if e["type"] == "document_provided")["data"]["document"]["text_sha256"])
