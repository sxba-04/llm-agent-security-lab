"""Deterministic engineering fixtures, explicitly not an LLM benchmark."""
from __future__ import annotations
import copy
import json
import re
from typing import Any
from .contracts import ModelError, ModelReply, ToolCall


class ScriptedModel:
    """Replay a case's demonstration script without network access.

    Secret placeholders can only resolve from tool messages already delivered
    to this model. They cannot inspect the case's hidden backend fixtures.
    """
    name = "scripted-mock-v1"
    provider = "mock"
    is_mock = True

    def __init__(self, case: dict[str, Any], source: str):
        self._script = copy.deepcopy(case["mock"][source])
        self._position = 0

    @staticmethod
    def _expand(value: str, messages: list[dict[str, Any]]) -> str:
        observed: dict[str, str] = {}
        for message in messages:
            if message.get("role") != "tool":
                continue
            try:
                payload = json.loads(message["content"])
            except (KeyError, TypeError, ValueError):
                continue
            ticket = payload.get("ticket") if isinstance(payload, dict) else None
            if isinstance(ticket, dict) and isinstance(ticket.get("secret"), str):
                observed[str(ticket.get("id"))] = ticket["secret"]
        return re.sub(r"\{\{secret:([A-Za-z0-9_-]+)\}\}",
                      lambda match: observed.get(match.group(1), "[not observed]"), value)

    def respond(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelReply:
        if self._position >= len(self._script):
            return ModelReply(text="Keine weiteren Schritte im kontrollierten Testskript.")
        step = self._script[self._position]
        self._position += 1
        if "name" in step:
            args = copy.deepcopy(step["arguments"])
            for key, value in args.items():
                if isinstance(value, str):
                    args[key] = self._expand(value, messages)
            return ModelReply(tool_calls=[ToolCall(step["name"], args, f"call_{self._position}")], finish_reason="tool_calls")
        if "text" in step:
            return ModelReply(text=self._expand(step["text"], messages))
        raise ModelError("Invalid mock script")
