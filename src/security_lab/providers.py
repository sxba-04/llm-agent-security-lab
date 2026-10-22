"""Opt-in OpenAI transport. Tests use injected transports, never live requests.

API reference checked 2026-10-22:
https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create

A byte-based reservation is deliberately conservative but is NOT a formally
proven tokenizer bound or provider invoice cap. Pricing, FX, tax and account
usage outside this application must be reconciled before paid campaigns.
"""
from __future__ import annotations

from decimal import Decimal
import json
import math
import ssl
from typing import Any, Callable
import urllib.error
import urllib.request

from .budget import BudgetLedger, euros
from .contracts import BudgetExceeded, ModelError, ModelReply, ToolCall

API_URL = "https://api.openai.com/v1/chat/completions"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
Transport = Callable[[dict[str, Any], str, float], dict[str, Any]]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_transport(payload: dict[str, Any], api_key: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        API_URL, data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"},
        method="POST",
    )
    # Default ProxyHandler remains enabled; TLS verification is never disabled.
    opener = urllib.request.build_opener(
        _NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context())
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise ModelError("Unexpected API HTTP status; reservation retained")
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ModelError("API response exceeded the size limit; reservation retained")
        value = json.loads(body.decode("utf-8"))
        if not isinstance(value, dict):
            raise ModelError("Invalid API response structure; reservation retained")
        return value
    except urllib.error.HTTPError as error:
        # Do not include response bodies, URLs, proxy credentials or headers.
        raise ModelError(f"API HTTP {error.code}; no automatic retry; reservation retained") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise ModelError("API transport or JSON error; no automatic retry; reservation retained") from None


def _positive_integer(value: Any, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(name + " must be a positive integer")
    return value


class OpenAIModel:
    """Configured, cost-reserved Chat Completions client with no hidden retries."""
    is_mock = False

    def __init__(self, config: dict[str, Any], api_key: str, ledger: BudgetLedger,
                 transport: Transport | None = None):
        if not isinstance(config, dict) or config.get("enabled") is not True:
            raise ValueError("Paid API configuration is disabled")
        model = config.get("model")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("An explicit API model identifier is required")
        if not isinstance(api_key, str) or not api_key.strip() or any(c in api_key for c in "\r\n"):
            raise ValueError("A locally configured API key is required")
        self.name = model.strip()
        expected_model = config.get("expected_returned_model")
        if expected_model is not None and (not isinstance(expected_model, str) or not expected_model.strip()):
            raise ValueError("expected_returned_model must be a nonempty identifier when configured")
        self._returned_model: str | None = expected_model.strip() if expected_model is not None else None
        self._model_version_changed = False
        self.max_completion_tokens = _positive_integer(config.get("max_completion_tokens"), "max_completion_tokens")
        self.max_input_tokens = _positive_integer(config.get("max_input_tokens"), "max_input_tokens")
        self.max_requests = _positive_integer(config.get("max_requests"), "max_requests")
        self.input_rate = euros(config.get("input_eur_per_million"))
        self.output_rate = euros(config.get("output_eur_per_million"))
        self.run_budget = euros(config.get("run_budget_eur"))
        if self.run_budget > ledger.limit:
            raise ValueError("Run budget exceeds ledger limit")
        for key in ("price_reference", "price_checked_on"):
            if not isinstance(config.get(key), str) or not config[key].strip():
                raise ValueError(key + " is required for auditable price estimates")
        timeout = config.get("timeout_seconds", 45)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError("timeout_seconds must be between 0 and 120")
        self.timeout = float(timeout)
        self.sampling: dict[str, Any] = {}
        if "temperature" in config:
            value = config["temperature"]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 2:
                raise ValueError("temperature must be a finite number between 0 and 2")
            self.sampling["temperature"] = value
        if "seed" in config:
            if type(config["seed"]) is not int:
                raise ValueError("seed must be an integer")
            self.sampling["seed"] = config["seed"]
        self._key = api_key
        self._ledger = ledger
        self._transport = transport or _http_transport
        self._accounted = Decimal("0")
        self._requests = 0

    def _cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        # Cached input is deliberately charged at the full configured rate.
        return (input_tokens * self.input_rate + output_tokens * self.output_rate) / Decimal("1000000")

    def respond(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ModelReply:
        if not isinstance(messages, list) or not isinstance(tools, list):
            raise ModelError("Messages and tools must be lists")
        if any(not isinstance(m, dict) or m.get("role") not in {"system", "developer", "user", "assistant", "tool"}
               or (m.get("content") is not None and not isinstance(m["content"], str)) for m in messages):
            raise ModelError("Only text messages are supported by the budgeted adapter")
        payload = {"model": self.name, "messages": messages, "tools": tools,
                   "parallel_tool_calls": False, "max_completion_tokens": self.max_completion_tokens,
                   "store": False, **self.sampling}
        try:
            # Byte count plus generous framing margin; excludes hidden provider changes.
            input_bound = 2 * len(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")) + 4096
        except (TypeError, ValueError):
            raise ModelError("Request is not valid JSON") from None
        if input_bound > self.max_input_tokens:
            raise BudgetExceeded("Conservative input estimate exceeds max_input_tokens")
        reservation = self._cost(input_bound, self.max_completion_tokens)
        if self._requests >= self.max_requests or self._accounted + reservation > self.run_budget:
            raise BudgetExceeded("Model instance request or EUR budget exhausted")
        reservation_id = self._ledger.reserve(reservation, {"model": self.name, "input_bound": input_bound,
                                                          "max_completion_tokens": self.max_completion_tokens})
        self._requests += 1
        self._accounted += reservation
        try:
            raw = self._transport(payload, self._key, self.timeout)
        except ModelError:
            raise
        except Exception:
            raise ModelError("API transport failed; no automatic retry; reservation retained") from None
        reply = self._parse(raw)
        usage = raw.get("usage")
        valid_usage = isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0
                                                    for k in ("prompt_tokens", "completion_tokens", "total_tokens"))
        if valid_usage and usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]:
            valid_usage = False
        if valid_usage:
            actual = self._cost(usage["prompt_tokens"], usage["completion_tokens"])
            try:
                within = self._ledger.settle(reservation_id, actual)
            except (BudgetExceeded, OSError):
                # The request already completed. Preserve evidence and let the
                # runner stop AFTER recording submitted context and response.
                # Do not misclassify this as a pre-request budget refusal.
                self._accounted += max(actual, reservation) - reservation
                accounting = {"estimated_cost_eur": str(actual), "accounting": "settlement_failed",
                              "accounting_error": True, "budget_overrun": actual > reservation}
            else:
                self._accounted += actual - reservation
                accounting = {"estimated_cost_eur": str(actual), "accounting": "reported_usage",
                              "accounting_error": False, "budget_overrun": not within}
        else:
            accounting = {"estimated_cost_eur": None, "accounting": "reservation_retained",
                          "accounting_error": False, "budget_overrun": False}
        actual_model = raw["model"]
        if self._returned_model is None:
            self._returned_model = actual_model
        elif actual_model != self._returned_model:
            self._model_version_changed = True
        reply.usage = {**(usage if isinstance(usage, dict) else {}), **accounting,
                       "model_version_changed": self._model_version_changed,
                       "expected_returned_model": self._returned_model,
                       "response_id": raw.get("id"), "model": raw.get("model"),
                       "reserved_eur": str(reservation), "reservation_id": reservation_id,
                       "raw_response": raw}
        return reply

    @staticmethod
    def _parse(raw: Any) -> ModelReply:
        try:
            if not isinstance(raw, dict) or len(json.dumps(raw, allow_nan=False).encode("utf-8")) > MAX_RESPONSE_BYTES:
                raise ValueError
            if not isinstance(raw.get("model"), str) or not raw["model"].strip():
                raise ValueError
            choices = raw["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError
            choice = choices[0]
            message = choice["message"]
            finish = choice["finish_reason"]
            if not isinstance(message, dict) or message.get("role") != "assistant" or finish not in {"stop", "length", "tool_calls", "content_filter"}:
                raise ValueError
            text = message.get("content")
            if text is not None and not isinstance(text, str):
                raise ValueError
            refusal = message.get("refusal")
            if refusal is not None:
                if not isinstance(refusal, str):
                    raise ValueError
                text = text or refusal
                finish = "content_filter"
            calls = message.get("tool_calls") or []
            if not isinstance(calls, list) or len(calls) > 64:
                raise ValueError
            result_calls = []
            call_ids: set[str] = set()
            for index, call in enumerate(calls):
                if not isinstance(call, dict) or call.get("type") != "function" or not isinstance(call.get("function"), dict):
                    raise ValueError
                function = call["function"]
                name = function.get("name")
                call_id = call.get("id")
                if not isinstance(name, str) or not name or not isinstance(call_id, str) or not call_id:
                    raise ValueError
                if call_id in call_ids:
                    raise ValueError
                call_ids.add(call_id)
                arguments_text = function.get("arguments")
                try:
                    arguments = json.loads(arguments_text) if isinstance(arguments_text, str) else None
                except (ValueError, TypeError):
                    arguments = None
                if not isinstance(arguments, dict):
                    # Keep generated invalid arguments as an observable model proposal.
                    # The common syntax gateway rejects this extra field; raw response
                    # remains available in usage for exact evidence.
                    arguments = {"__invalid_arguments_json__": arguments_text}
                result_calls.append(ToolCall(name, arguments, call_id))
            if (finish == "tool_calls" and not result_calls) or (result_calls and finish == "stop"):
                raise ValueError
            return ModelReply(text=text, tool_calls=result_calls, finish_reason=finish)
        except (ValueError, KeyError, TypeError):
            raise ModelError("Invalid API response structure; reservation retained") from None
