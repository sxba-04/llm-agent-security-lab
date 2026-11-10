"""One local, cost-reserved compatibility check on a pinned clean development ticket."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path

from .batch import digest, provenance, write_json_new
from .budget import BudgetLedger, PROJECT_CEILING_EUR
from .cases import validate_case
from .contracts import BudgetExceeded, ModelReply, ReceivedResponseError
from .core import run_case
from .providers import OpenAIModel, Transport, validate_config

ROOT = Path(__file__).resolve().parents[2]
CASE_ID = "DEV-G1-01"
CASE_SHA256 = "3464cf133c36836ddcab9dffb91c6129d79f89b3fc6a0374057f02d54aa54e67"
MODEL = "gpt-6-luna"
MAX_REQUESTS = 4
MAX_TOOL_CALLS = 3
RUN_BUDGET_EUR = "0.50"
RUN_TIMEOUT_SECONDS = 120
PRICE_REFERENCE = "https://developers.openai.com/api/docs/models/gpt-6-luna"


def load_pilot_case() -> dict:
    raw = (ROOT / "cases" / "dev" / "dev-g1-01.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CASE_SHA256:
        raise ValueError("Pilot fixture differs from the approved DEV-G1-01 revision")
    # Validate exactly the bytes that passed the hash check, then discard the
    # alternative article and scripted responses before constructing a model.
    case = json.loads(raw)
    validate_case(case)
    clean = {key: case[key] for key in ("case_id", "scenario_group", "goal", "user_request",
                                         "session", "tickets", "expected")}
    clean["articles"] = {"clean": case["articles"]["clean"]}
    return clean


def make_config(input_eur_per_million: str, output_eur_per_million: str, price_checked_on: str) -> dict:
    checked = date.fromisoformat(price_checked_on)
    if checked > date.today():
        raise ValueError("Price verification date cannot be in the future")
    return validate_config({
        "enabled": True, "model": MODEL,
        "max_input_tokens": 32768, "max_completion_tokens": 1024,
        "timeout_seconds": 45, "max_requests": MAX_REQUESTS, "run_budget_eur": RUN_BUDGET_EUR,
        "input_eur_per_million": input_eur_per_million, "output_eur_per_million": output_eur_per_million,
        "price_reference": PRICE_REFERENCE, "price_checked_on": checked.isoformat(),
    })


def _is_luna_identifier(value: str | None) -> bool:
    if value == MODEL:
        return True
    prefix = MODEL + "-"
    if not isinstance(value, str) or not value.startswith(prefix):
        return False
    suffix = value[len(prefix):]
    try:
        # Round-trip to the canonical ASCII YYYY-MM-DD representation. Python
        # also parses ISO week dates and dates without hyphens.
        return date.fromisoformat(suffix).isoformat() == suffix
    except ValueError:
        return False


def has_luna_standard_rate(usage: dict) -> bool:
    raw = usage.get("raw_response")
    return (isinstance(raw, dict) and _is_luna_identifier(usage.get("model"))
            and raw.get("service_tier", "default") == "default")


def run_first(workspace: Path, config: dict, api_key: str, *, transport: Transport | None = None) -> dict:
    checked = make_config(config["input_eur_per_million"], config["output_eur_per_million"],
                          config["price_checked_on"])
    if config != checked:
        raise ValueError("The pilot accepts only its fixed model, parameters and limits")
    case = load_pilot_case()
    ledger = BudgetLedger(workspace / "budget.json", PROJECT_CEILING_EUR, RUN_BUDGET_EUR)
    # Scope the live client to this one pinned case. A response with incomplete
    # billing or identity evidence must not authorize a tool or another request.
    class FirstTicketModel(OpenAIModel):
        def respond(self, messages: list[dict], tools: list[dict]) -> ModelReply:
            reply = super().respond(messages, tools)
            usage = reply.usage
            if (usage["accounting"] != "reported_usage" or usage["budget_overrun"]
                    or not has_luna_standard_rate(usage)):
                raise ReceivedResponseError({**usage, "pilot_receipt_invalid": True})
            return reply

    model = FirstTicketModel(checked, api_key, ledger, transport=transport)
    # The adapter includes these options in the payload *before* it estimates
    # cost. Keep this Luna-specific setting out of the general run command.
    model.sampling.update(reasoning_effort="none", service_tier="default")
    output = workspace / "luna-clean-first"
    # Exclusive publication is also the permanent attempt marker, including
    # transport uncertainty, concurrency, crashes and evidence write failure.
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    write_json_new(output / "attempt.json", {
        "case_id": CASE_ID, "case_sha256": CASE_SHA256, "variant": "P", "source": "clean",
        "config": checked, "request_options": model.sampling, "max_tool_calls": MAX_TOOL_CALLS,
        "run_timeout_seconds": RUN_TIMEOUT_SECONDS, "provenance": provenance(),
    })
    result = run_case(case, "P", "clean", model, max_tool_calls=MAX_TOOL_CALLS,
                      max_model_calls=MAX_REQUESTS, timeout_seconds=RUN_TIMEOUT_SECONDS)
    # A completed answer can omit the tool round trip entirely. This is a
    # technical acceptance check only; semantic correctness needs human review.
    returned_read = any(event["type"] == "context_exposure" and event["data"]["ticket_id"] == "A17"
                        for event in result["events"])
    result["technical_acceptance"] = bool(result["status"] == "completed" and returned_read
                                           and result["final_text"].strip())
    write_json_new(output / "result.json", result)
    write_json_new(output / "receipt.json", {
        "attempt_sha256": hashlib.sha256((output / "attempt.json").read_bytes()).hexdigest(),
        "result_sha256": hashlib.sha256((output / "result.json").read_bytes()).hexdigest(),
        "events_digest": digest(result["events"]), "status": result["status"],
        "technical_acceptance": result["technical_acceptance"],
    })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "run-first"))
    parser.add_argument("--input-eur-per-million", required=True)
    parser.add_argument("--output-eur-per-million", required=True)
    parser.add_argument("--price-checked-on", required=True, metavar="YYYY-MM-DD")
    parser.add_argument("--workspace", type=Path, default=ROOT / "runs",
                        help="Project's existing runs directory, shared with runs/budget.json")
    parser.add_argument("--allow-paid-api", action="store_true")
    parser.add_argument("--isolation-acknowledged", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = make_config(args.input_eur_per_million, args.output_eur_per_million, args.price_checked_on)
        if args.action == "plan":
            case = load_pilot_case()
            print(json.dumps({"case_id": case["case_id"], "source": "clean", "variant": "P",
                              "config": config, "request_options": {"reasoning_effort": "none", "service_tier": "default"},
                              "max_tool_calls": MAX_TOOL_CALLS,
                              "ledger": str(args.workspace / "budget.json"),
                              "evidence": str(args.workspace / "luna-clean-first")}, indent=2))
            return 0
        if not args.allow_paid_api or not args.isolation_acknowledged:
            raise ValueError("run-first requires --allow-paid-api and --isolation-acknowledged")
        result = run_first(args.workspace, config, os.environ.get("OPENAI_API_KEY", ""))
    except FileExistsError:
        parser.exit(2, "An attempt or evidence already exists. Inspect and reconcile the original run.\n")
    except (ValueError, OSError, BudgetExceeded) as error:
        parser.exit(2, f"Pilot stopped: {error}\n")
    print(json.dumps({"case_id": result["case_id"], "status": result["status"],
                      "model_calls": result["model_calls"], "tool_calls": result["tool_calls"],
                      "technical_acceptance": result["technical_acceptance"],
                      "evidence": str(args.workspace / "luna-clean-first")}))
    return 0 if result["technical_acceptance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
