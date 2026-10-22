"""Small shared contracts; no provider SDK required."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str = "call_1"


@dataclass
class ModelReply:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = "stop"


class Model(Protocol):
    name: str
    is_mock: bool
    def respond(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelReply: ...


class ModelError(RuntimeError):
    """Provider/transport failure: must not be scored as successful defense."""


class BudgetExceeded(ModelError):
    """A configured spending reservation or request limit was exhausted."""
