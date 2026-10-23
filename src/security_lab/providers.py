"""Opt-in OpenAI transport. Tests use injected transports, never live requests.

API reference checked 2026-10-22:
https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create

A byte-based reservation is deliberately conservative but is NOT a formally
proven tokenizer bound or provider invoice cap. Pricing, FX, tax and account
usage outside this application must be reconciled before paid campaigns.
"""
from __future__ import annotations

from decimal import Decimal
import base64
import hashlib
import http.client
import json
import math
import ssl
from typing import Any, Callable
import urllib.error
import urllib.request

from .budget import BudgetLedger, euros
from .contracts import BudgetExceeded, ModelError, ModelReply, ReceivedResponseError, ToolCall

API_URL = "https://api.openai.com/v1/chat/completions"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
Transport = Callable[[dict[str, Any], str, float], dict[str, Any]]


def _strict_json(value: Any) -> bytes:
    """Reject nonfinite numbers and lone Unicode surrogates at any depth."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


def _safe_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        value.encode("utf-8")
    except UnicodeError:
        return None
    return value


def _response_evidence(raw: Any) -> dict[str, Any]:
    """Preserve an exact decoded response or bounded, ASCII-escaped evidence.

    Nonfinite literals and unpaired surrogates are preserved inside a string,
    never reintroduced as invalid values in an audit JSON document.
    """
    try:
        encoded = _strict_json(raw)
        if len(encoded) <= MAX_RESPONSE_BYTES:
            return {"raw_response": raw}
    except (TypeError, ValueError, UnicodeError, RecursionError):
        pass
    try:
        escaped = json.dumps(raw, ensure_ascii=True, allow_nan=True).encode("ascii")
    except (TypeError, ValueError, RecursionError):
        # Only an injected, non-JSON transport can reach this branch.
        return {"raw_response": None, "raw_response_unserializable": True}
    return {"raw_response": None, "raw_response_escaped": escaped[:MAX_RESPONSE_BYTES].decode("ascii"),
            "raw_response_escaped_truncated": len(escaped) > MAX_RESPONSE_BYTES,
            "raw_response_escaped_bytes": len(escaped),
            "raw_response_escaped_sha256": hashlib.sha256(escaped).hexdigest()}


def _received_body_error(body: bytes, *, truncated: bool = False,
                         incomplete: bool = False) -> ReceivedResponseError:
    return ReceivedResponseError({"raw_response": None,
                                  "raw_response_body_base64": base64.b64encode(body[:MAX_RESPONSE_BYTES]).decode("ascii"),
                                  "raw_response_body_truncated": truncated,
                                  "raw_response_body_incomplete": incomplete,
                                  "accounting": "reservation_retained"})


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
            try:
                body = response.read(MAX_RESPONSE_BYTES + 1)
            except (http.client.HTTPException, TimeoutError, OSError) as error:
                # The successful response headers already confirm receipt.
                # A later body failure must not turn that into uncertainty or
                # discard the bytes available from an IncompleteRead.
                partial = getattr(error, "partial", b"")
                if not isinstance(partial, bytes):
                    partial = b""
                raise _received_body_error(partial, truncated=len(partial) > MAX_RESPONSE_BYTES,
                                           incomplete=True) from None
            if len(body) > MAX_RESPONSE_BYTES:
                raise _received_body_error(body, truncated=True)
        try:
            value = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeError, RecursionError):
            raise _received_body_error(body) from None
        if not isinstance(value, dict):
            raise ReceivedResponseError(_response_evidence(value))
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


def validate_config(config: Any) -> dict[str, Any]:
    """Return only validated, primitive configuration suitable for audit logs.

    Credentials are supplied separately through the local environment. Unknown
    fields are rejected, including nested metadata that might contain secrets.
    Disabled templates may retain empty model/price placeholders; construction
    of a paid model still requires an enabled, fully configured template.
    """
    allowed = {"enabled", "model", "expected_returned_model", "max_completion_tokens",
               "max_input_tokens", "max_requests", "input_eur_per_million",
               "output_eur_per_million", "run_budget_eur", "price_reference",
               "price_checked_on", "timeout_seconds", "temperature", "seed"}
    if not isinstance(config, dict) or set(config) - allowed:
        raise ValueError("API configuration contains unsupported fields")
    if type(config.get("enabled")) is not bool:
        raise ValueError("enabled must be a boolean")
    enabled = config["enabled"]
    validated: dict[str, Any] = {"enabled": enabled}
    for key in ("model", "price_reference", "price_checked_on"):
        value = _safe_text(config.get(key))
        if value is None or (enabled and not value.strip()):
            raise ValueError(key + " must be a valid configured string")
        validated[key] = value.strip()
    if "expected_returned_model" in config:
        value = _safe_text(config["expected_returned_model"])
        if value is None or not value.strip():
            raise ValueError("expected_returned_model must be a nonempty identifier")
        validated["expected_returned_model"] = value.strip()
    for key in ("max_completion_tokens", "max_input_tokens", "max_requests"):
        validated[key] = _positive_integer(config.get(key), key)
    for key in ("input_eur_per_million", "output_eur_per_million", "run_budget_eur"):
        value = config.get(key)
        if value is None and not enabled and key != "run_budget_eur":
            validated[key] = None
        else:
            # Do not permit arbitrary objects, containers or numeric subclasses.
            if type(value) not in (str, int, float):
                raise ValueError(key + " must be a finite positive amount")
            validated[key] = str(euros(value))
    timeout = config.get("timeout_seconds", 45)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError("timeout_seconds must be between 0 and 120")
    validated["timeout_seconds"] = timeout
    if "temperature" in config:
        value = config["temperature"]
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 2:
            raise ValueError("temperature must be a finite number between 0 and 2")
        validated["temperature"] = value
    if "seed" in config:
        if type(config["seed"]) is not int:
            raise ValueError("seed must be an integer")
        validated["seed"] = config["seed"]
    return validated


class OpenAIModel:
    """Configured, cost-reserved Chat Completions client with no hidden retries."""
    is_mock = False
    provider = "openai"

    def __init__(self, config: dict[str, Any], api_key: str, ledger: BudgetLedger,
                 transport: Transport | None = None):
        config = validate_config(config)
        if config["enabled"] is not True:
            raise ValueError("Paid API configuration is disabled")
        if not isinstance(api_key, str) or not api_key.strip() or any(c in api_key for c in "\r\n"):
            raise ValueError("A locally configured API key is required")
        self.name = config["model"]
        self._returned_model: str | None = config.get("expected_returned_model")
        self._model_version_changed = False
        self.max_completion_tokens = config["max_completion_tokens"]
        self.max_input_tokens = config["max_input_tokens"]
        self.max_requests = config["max_requests"]
        self.input_rate = euros(config["input_eur_per_million"])
        self.output_rate = euros(config["output_eur_per_million"])
        self.run_budget = euros(config["run_budget_eur"])
        if self.run_budget > ledger.limit:
            raise ValueError("Run budget exceeds ledger limit")
        self.timeout = float(config["timeout_seconds"])
        self.sampling = {key: config[key] for key in ("temperature", "seed") if key in config}
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
        except (TypeError, ValueError, UnicodeError, RecursionError):
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
        except ReceivedResponseError as error:
            # A complete HTTP response arrived, even when its bytes are invalid
            # JSON/UTF-8. This differs from an uncertain transport failure.
            error.usage = {**self._account_response(None, reservation, reservation_id), **error.usage}
            raise
        except ModelError:
            raise
        except Exception:
            raise ModelError("API transport failed; no automatic retry; reservation retained") from None
        # Receipt/accounting are independent of whether generated actions parse.
        # Never discard a paid response because its executable plan is invalid.
        usage = self._account_response(raw, reservation, reservation_id)
        try:
            reply = self._parse(raw)
        except ModelError:
            raise ReceivedResponseError(usage) from None
        reply.usage = usage
        return reply

    def _account_response(self, raw: Any, reservation: Decimal, reservation_id: str) -> dict[str, Any]:
        fields = raw if isinstance(raw, dict) else {}
        usage = fields.get("usage")
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
        actual_model = _safe_text(fields.get("model"))
        if actual_model and actual_model.strip():
            if self._returned_model is None:
                self._returned_model = actual_model
            elif actual_model != self._returned_model:
                self._model_version_changed = True
        safe_usage: dict[str, Any] = {}
        if isinstance(usage, dict):
            try:
                if len(_strict_json(usage)) <= MAX_RESPONSE_BYTES:
                    safe_usage = usage
            except (TypeError, ValueError, UnicodeError, RecursionError):
                # Retain useful reported tokens even if unrelated usage metadata
                # is malformed. Full metadata survives in escaped raw evidence.
                if valid_usage:
                    safe_usage = {key: usage[key] for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
        return {**safe_usage, **accounting, "model_version_changed": self._model_version_changed,
                "expected_returned_model": self._returned_model,
                "response_id": _safe_text(fields.get("id")), "model": actual_model,
                "reserved_eur": str(reservation), "reservation_id": reservation_id,
                **_response_evidence(raw)}

    @staticmethod
    def _parse(raw: Any) -> ModelReply:
        try:
            if not isinstance(raw, dict) or len(_strict_json(raw)) > MAX_RESPONSE_BYTES:
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
            for call in calls:
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
                    # json.loads accepts NaN/Infinity and overflowed exponents;
                    # it can also decode an escaped lone surrogate. Neither may
                    # enter proposals, tool state or the next API request.
                    _strict_json(arguments)
                except (ValueError, TypeError, UnicodeError, RecursionError):
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
        except (ValueError, KeyError, TypeError, UnicodeError, RecursionError):
            raise ModelError("Invalid API response structure") from None
