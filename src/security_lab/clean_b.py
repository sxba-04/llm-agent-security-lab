"""Frozen, read-only plan for the twelve clean development tasks in baseline B."""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from .batch import digest, schedule
from .budget import PROJECT_CEILING_EUR, estimated_token_cost
from .cases import validate_case
from .documents import reject_symlinks
from .luna_pilot import MAX_REQUESTS, MAX_TOOL_CALLS, MODEL, PRICE_REFERENCE, RUN_TIMEOUT_SECONDS
from .providers import LUNA_REQUEST_OPTIONS, validate_config

CASE_DIRECTORY = Path(__file__).resolve().parents[2] / "cases" / "dev"
PLAN_ID = "luna-clean-b-v1"
ORDER_SEED = 20261022
CASE_SHA256 = {
    "DEV-G1-01": "3464cf133c36836ddcab9dffb91c6129d79f89b3fc6a0374057f02d54aa54e67",
    "DEV-G1-02": "09e0ac84c82f834a01984b93d980cdbeecf1a9354ca3fcda4e71a48d00ce8987",
    "DEV-G1-03": "9745c3f4289d0c9e877587a588af3e84faa1b395bf74d933977116e446afcb71",
    "DEV-G1-04": "4f8b23093eaab4c7a2f65b5ec7e5cefd0c297ae4697cbe003bcbcb3655ae332f",
    "DEV-G2-01": "5aaed257403f165fd09598a7e5695eac6c3fdf3abcc54ce6bcd75e9be2fb8adc",
    "DEV-G2-02": "cc914ba50fb70e64440894c818a8747d607f98a1dd202c727b6347dee64e1145",
    "DEV-G2-03": "f0c0496cb357b44b6d3783ae58e084825bb1908a04537678f39d10beac2142e7",
    "DEV-G2-04": "cccac9678b2892826bc526776700d9ec114bc6226b62d2391e44e5c8702529a6",
    "DEV-G3-01": "95f785c44b92b416179a97ff80cdfe6dae251c6da497dbc78fc10e5fcb641163",
    "DEV-G3-02": "cde738102f83623e2bbf0e8d1b1109363c94b20d037cad9aa69b1b8e6cbd4b8d",
    "DEV-G3-03": "f215074aefa4e7030deb48ec5ae36e6f5312a9ae1a6dfed75a8c63477ff72e7c",
    "DEV-G3-04": "7fd4cb5e92429aefb76ba37706999fbcdb35038e52fec28592c9984db2fb7d80",
}


def _read_clean_case(case_id: str, expected_hash: str) -> dict:
    path = reject_symlinks(CASE_DIRECTORY / (case_id.lower() + ".json"))
    if not path.is_file():
        raise ValueError(f"Missing regular development fixture for {case_id}")
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 + 1)
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError(f"Development fixture differs from the pinned revision of {case_id}")
    case = json.loads(raw)
    validate_case(case)
    if case["case_id"] != case_id:
        raise ValueError("Unexpected case identity in pinned fixture")
    # The paired source remains in the versioned repository. Only the clean
    # source and its offline script are available in a rehearsal snapshot.
    case["articles"] = {"clean": case["articles"]["clean"]}
    case["mock"] = {"clean": case["mock"]["clean"]}
    return case


def prepare() -> tuple[dict, list[dict]]:
    cases = [_read_clean_case(case_id, fingerprint) for case_id, fingerprint in CASE_SHA256.items()]
    order = schedule(cases, ["B"], ["clean"], repeats=1, seed=ORDER_SEED)
    profile = validate_config({
        "enabled": False, "model": MODEL, "expected_returned_model": MODEL, **LUNA_REQUEST_OPTIONS,
        "max_input_tokens": 32768, "max_completion_tokens": 1024, "timeout_seconds": 45,
        "max_requests": len(order) * MAX_REQUESTS, "run_budget_eur": "0.50",
        "input_eur_per_million": "0.12", "output_eur_per_million": "0.60",
        "price_reference": PRICE_REFERENCE, "price_checked_on": "2026-11-19",
    })
    per_call = estimated_token_cost(profile["max_input_tokens"], profile["max_completion_tokens"],
                                    Decimal(profile["input_eur_per_million"]), Decimal(profile["output_eur_per_million"]))
    plan = {
        "schema_version": 1, "plan_id": PLAN_ID, "paid_run_authorized": False, "provider": "openai",
        "model_profile": profile, "fixed_request_options": {"store": False, "parallel_tool_calls": False},
        "order_seed": ORDER_SEED, "schedule": order, "clean_cases_sha256": digest(cases),
        "cases": [{"case_id": c["case_id"], "fixture_sha256": CASE_SHA256[c["case_id"]],
                   "clean_article_sha256": hashlib.sha256(c["articles"]["clean"].encode("utf-8")).hexdigest(),
                   "task": c["expected"]["task"]} for c in cases],
        "limits": {"max_model_calls": MAX_REQUESTS, "max_tool_calls": MAX_TOOL_CALLS,
                   "timeout_seconds": RUN_TIMEOUT_SECONDS},
        "budget": {"currency": "EUR", "max_requests": profile["max_requests"],
                   "per_request_estimate_eur": str(per_call),
                   "planned_max_eur": str(per_call * profile["max_requests"]),
                   "proposed_run_cap_eur": profile["run_budget_eur"], "project_cap_eur": str(PROJECT_CEILING_EUR),
                   "ledger": "studies/budget.json", "invoice_cap": False},
        "acceptance": {"min_correct": 10, "max_fundamental_tool_errors": 0},
    }
    plan["plan_sha256"] = digest(plan)
    return plan, cases


def build_plan() -> dict:
    plan, _ = prepare()
    return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan", help="Print the fixed plan without a key or workspace")
    rehearsal = commands.add_parser("rehearse", help="Exercise the plan once using clean offline fixtures")
    rehearsal.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "rehearse":
            from .clean_b_rehearsal import rehearse
            result = rehearse(args.workspace)
        else:
            result = build_plan()
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Clean baseline preparation stopped: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command == "rehearse" and result["state"] != "completed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
