"""Offline study planning, evidence linking and read-only pilot preparation.

This module never constructs a provider, reads a credential or authorizes a paid
run. A study groups existing evidence; it does not relabel development data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from .batch import SOURCES, VARIANTS, digest, load_results, provenance, schedule, write_json_new
from .budget import PROJECT_CEILING_EUR, euros
from .cases import load_cases, validate_case
from .providers import validate_config

SCHEMA_VERSION = 1
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_EVIDENCE_FILES = 50000
MOCK_CONFIG = {"provider": "mock", "engineering_only": True}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
GIT_COMMIT = re.compile(r"[0-9a-f]{40}\Z")


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("JSON input must be a bounded regular file, not a symlink")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result
    def finite(value):
        raise ValueError("Nonfinite JSON number")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=finite)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def _hash_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def make_plan(cases: list[dict], *, name: str, repeats: int = 3, seed: int = 20261022,
              max_part_runs: int = 480, provider_config: dict | None = None) -> dict:
    """Keep every case's repetitions and all eight conditions in one part."""
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ValueError("Study name requires 1..120 characters")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 1000:
        raise ValueError("Study plans require 1..1000 cases")
    for case in cases:
        validate_case(case)
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("Cases require unique case IDs")
    # Validate scheduler parameters without allocating an entire large study.
    schedule(cases[:1], list(VARIANTS), list(SOURCES), repeats, seed)
    if type(max_part_runs) is not int or not 8 <= max_part_runs <= 480:
        raise ValueError("Part limit must be 8..480; the UI limit is unchanged")
    cases_per_part = max_part_runs // (8 * repeats)
    if not cases_per_part:
        raise ValueError("One complete case with all repetitions must fit in a part")
    ordered = sorted(cases, key=lambda case: case["case_id"])
    config = MOCK_CONFIG.copy() if provider_config is None else {"provider": "openai", **validate_config(provider_config)}
    parts = []
    for offset in range(0, len(ordered), cases_per_part):
        subset = ordered[offset:offset + cases_per_part]
        part_seed = seed + len(parts)
        order = schedule(subset, list(VARIANTS), list(SOURCES), repeats, part_seed)
        parts.append({"part_id": f"part-{len(parts) + 1:02d}", "case_ids": [c["case_id"] for c in subset],
                      "order_seed": part_seed, "planned_runs": len(order), "schedule_sha256": digest(order)})
    return {"schema_version": SCHEMA_VERSION, "kind": "study_plan", "name": name.strip(),
            "stage": "preparation", "main_experiment_approved": False,
            "repeats": repeats, "base_seed": seed, "max_part_runs": max_part_runs,
            "variants": list(VARIANTS), "sources": list(SOURCES), "cases": ordered,
            "cases_sha256": digest(ordered), "provider_config": config,
            "limits": {"max_tool_calls": 8, "max_model_calls": 12, "timeout_seconds": 120},
            "parts": parts, "planned_runs": sum(part["planned_runs"] for part in parts),
            "provenance": provenance()}


def validate_plan(plan: dict) -> None:
    if type(plan.get("schema_version")) is not int or plan.get("schema_version") != SCHEMA_VERSION or plan.get("kind") != "study_plan":
        raise ValueError("Unsupported study plan schema; no automatic migration")
    if plan.get("stage") != "preparation" or plan.get("main_experiment_approved") is not False:
        raise ValueError("A preparation plan cannot declare main-experiment approval")
    config = plan.get("provider_config")
    if not isinstance(config, dict) or config.get("provider") not in {"mock", "openai"}:
        raise ValueError("Invalid study provider configuration")
    provider = None if config["provider"] == "mock" else {k: v for k, v in config.items() if k != "provider"}
    expected = make_plan(plan["cases"], name=plan["name"], repeats=plan["repeats"],
                         seed=plan["base_seed"], max_part_runs=plan["max_part_runs"], provider_config=provider)
    for key in ("cases", "cases_sha256", "parts", "planned_runs", "variants", "sources", "limits", "provider_config"):
        if plan.get(key) != expected[key]:
            raise ValueError("Study plan mismatch: " + key)
    _validate_provenance(plan.get("provenance"))


def _validate_provenance(recorded: Any) -> None:
    from .archives import _safe_name
    if not isinstance(recorded, dict) or not isinstance(recorded.get("source_sha256"), dict):
        raise ValueError("Study plan requires frozen code and lockfile fingerprints")
    hashes = recorded["source_sha256"]
    if not {"pyproject.toml", "uv.lock", ".python-version"}.issubset(hashes):
        raise ValueError("Frozen study provenance is missing required lockfile fingerprints")
    for relative, fingerprint in hashes.items():
        _safe_name(relative)
        if not isinstance(fingerprint, str) or not SHA256.fullmatch(fingerprint):
            raise ValueError("Invalid frozen source fingerprint")
    commit = recorded.get("git_commit")
    if commit is not None and (not isinstance(commit, str) or not GIT_COMMIT.fullmatch(commit)):
        raise ValueError("Invalid frozen source commit")


def export_part_cases(plan: dict, part_id: str, output: Path) -> None:
    validate_plan(plan)
    part = next((item for item in plan["parts"] if item["part_id"] == part_id), None)
    if part is None:
        raise ValueError("Unknown study part")
    output.mkdir(parents=True, exist_ok=False)
    for index, case in enumerate(c for c in plan["cases"] if c["case_id"] in part["case_ids"]):
        write_json_new(output / f"case-{index + 1:03d}.json", case)


def _inventory(directory: Path) -> dict[str, str]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Campaign must be a regular directory")
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Study evidence must not contain symlinks")
        if path.is_file():
            if len(files) >= MAX_EVIDENCE_FILES:
                raise ValueError("Study evidence file limit exceeded")
            files[path.relative_to(directory).as_posix()] = _hash_file(path)
    return files


def _link_part(plan: dict, part: dict, directory: Path) -> dict:
    before = _inventory(directory)
    manifest = _read_json(directory / "manifest.json")
    if manifest.get("state") == "running":
        raise ValueError("Finish or cancel each campaign before linking evidence")
    subset = [case for case in plan["cases"] if case["case_id"] in part["case_ids"]]
    expected = {"cases_sha256": digest(subset), "order_seed": part["order_seed"],
                "limits": plan["limits"], "provider_config": plan["provider_config"]}
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(part["part_id"] + " campaign mismatch: " + key)
    if digest(manifest.get("schedule")) != part["schedule_sha256"]:
        raise ValueError("Campaign schedule differs from the frozen part")
    recorded = manifest.get("provenance")
    if not isinstance(recorded, dict) or recorded.get("source_sha256") != plan["provenance"]["source_sha256"]:
        raise ValueError("Campaign code/lockfiles differ from frozen study code")
    from .archives import verify_campaign_directory
    checked = verify_campaign_directory(directory)
    expected_mock = plan["provider_config"]["provider"] == "mock"
    if any(result.get("is_mock") is not expected_mock for result in load_results(directory)):
        raise ValueError("Recorded mock/live mode differs from the study provider; no relabeling is allowed")
    if before != _inventory(directory):
        raise ValueError("Campaign changed during evidence linking; retry after writers stop")
    return {"part_id": part["part_id"], "campaign_label": directory.name,
            "files_sha256": before, "campaign_manifest_sha256": digest(manifest),
            "fixture_seed": manifest.get("fixture_seed"), "state": manifest["state"],
            "planned_runs": part["planned_runs"], "recorded_runs": checked["completed_runs"],
            "verified_document_sources": checked["verified_document_sources"],
            "verified_review_versions": checked["verified_review_versions"],
            "evidence_complete": checked["evidence_complete"],
            "incomplete_event_files": checked["incomplete_event_files"]}


def link_campaigns(plan: dict, campaigns: list[Path]) -> dict:
    validate_plan(plan)
    if len(campaigns) != len(plan["parts"]):
        raise ValueError("Provide exactly one campaign per study part, in plan order")
    if len({path.resolve() for path in campaigns}) != len(campaigns):
        raise ValueError("A restored copy or repeated path is not a new study part")
    links = [_link_part(plan, part, directory) for part, directory in zip(plan["parts"], campaigns)]
    return {"schema_version": SCHEMA_VERSION, "kind": "study_evidence", "name": plan["name"],
            "plan_sha256": digest(plan), "parts": links, "planned_runs": plan["planned_runs"],
            "recorded_runs": sum(item["recorded_runs"] for item in links),
            "execution_complete": all(item["state"] == "completed" for item in links),
            "evidence_complete": all(item["evidence_complete"] for item in links),
            "engineering_only": plan["provider_config"]["provider"] == "mock",
            "authenticity_verified": False, "human_approval_verified": False}


def verify_study(plan: dict, linked: dict, campaigns: list[Path]) -> dict:
    if type(linked.get("schema_version")) is not int or linked.get("schema_version") != SCHEMA_VERSION or linked.get("kind") != "study_evidence":
        raise ValueError("Unsupported study evidence schema; no automatic migration")
    current = link_campaigns(plan, campaigns)
    # Friendly local directory names may differ after restoration.
    for old, new in zip(linked.get("parts", []), current["parts"]):
        new["campaign_label"] = old.get("campaign_label")
    if current != linked:
        raise ValueError("Study evidence changed, is missing, or belongs to another plan")
    return {"verified_integrity": True, "authenticity_verified": False,
            "execution_complete": current["execution_complete"],
            "evidence_complete": current["evidence_complete"], "recorded_runs": current["recorded_runs"],
            "engineering_only": current["engineering_only"]}


def _record_gates(records: dict[str, Path] | None) -> list[dict]:
    gates = []
    for key in ("author_acceptance", "outer_isolation", "external_restore"):
        path = (records or {}).get(key)
        if path and (path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES):
            raise ValueError("Preflight records must be bounded regular files")
        gates.append({"gate": key, "status": "supplied_unverified" if path else "missing",
                      **({"record_sha256": _hash_file(path)} if path else {})})
    return gates


def _priced_budget(plan: dict, cost: dict, already_spent_eur: str | None) -> list[dict]:
    config = plan["provider_config"]
    request = (euros(config["input_eur_per_million"]) * config["max_input_tokens"]
               + euros(config["output_eur_per_million"]) * config["max_completion_tokens"]) / 1000000
    total_requests = sum(min(config["max_requests"], part["planned_runs"] * plan["limits"]["max_model_calls"])
                         for part in plan["parts"])
    planned_cap = euros(config["run_budget_eur"]) * len(plan["parts"])
    cost.update(max_requests=total_requests, per_request_estimate_eur=str(request),
                token_limit_estimate_eur=str(request * total_requests), aggregate_configured_budget_eur=str(planned_cap))
    status = "exceeds_project_budget" if planned_cap > PROJECT_CEILING_EUR else "unknown_spend"
    if already_spent_eur is not None:
        spent = euros(already_spent_eur, allow_zero=True)
        cost["declared_already_spent_eur"] = str(spent)
        status = "within_declared_budget" if spent + planned_cap <= PROJECT_CEILING_EUR else "exceeds_project_budget"
    return [{"gate": "project_budget", "status": status},
            {"gate": "per_request_reservation", "status": "within_cli_limit" if request <= 1 else "exceeds_cli_limit"}]


def _cost_preflight(plan: dict, already_spent_eur: str | None) -> tuple[dict, list[dict]]:
    config = plan["provider_config"]
    cost: dict[str, Any] = {"currency": "EUR", "price_verified": False, "invoice_cap": False}
    if config["provider"] == "mock":
        cost.update(mode="mock", model_calls=0, estimated_eur="0")
        return cost, []
    gates = [{"gate": "provider_enabled", "status": "configured" if config["enabled"] else "disabled"}]
    cost.update(mode="openai", model=config["model"], price_checked_on=config["price_checked_on"],
                price_reference=config["price_reference"])
    if config["input_eur_per_million"] is None or config["output_eur_per_million"] is None:
        gates.append({"gate": "configured_prices", "status": "missing"})
    else:
        gates.extend(_priced_budget(plan, cost, already_spent_eur))
    return cost, gates


def preflight(plan: dict, *, already_spent_eur: str | None = None,
              records: dict[str, Path] | None = None) -> dict:
    """Read inputs only. Supplied human records are referenced, never certified."""
    validate_plan(plan)
    gates = [{"gate": "frozen_plan", "status": "checked"},
             {"gate": "code_and_locks", "status": "checked" if plan["provenance"]["source_sha256"] == provenance()["source_sha256"] else "changed"}]
    gates.extend(_record_gates(records))
    cost, cost_gates = _cost_preflight(plan, already_spent_eur)
    gates.extend(cost_gates)
    return {"schema_version": SCHEMA_VERSION, "kind": "pilot_preflight", "plan_sha256": digest(plan),
            "planned_runs": plan["planned_runs"], "gates": gates, "cost": cost,
            "network_requests_made": 0, "paid_run_authorized": False, "main_experiment_approved": False,
            "next_step": "Review author acceptance, isolation, external restore, scope and prices; separately authorize paid CLI execution."}


def _new_output(path: Path, value: dict, protected: list[Path]) -> None:
    target = path.resolve()
    if any(target == source.resolve() or (source.is_dir() and target.is_relative_to(source.resolve())) for source in protected):
        raise ValueError("Output must be separate from input plans and original campaign evidence")
    write_json_new(path, value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_cmd = commands.add_parser("plan", help="Freeze an offline preparation plan")
    plan_cmd.add_argument("--cases", type=Path, default=Path("cases/dev"))
    plan_cmd.add_argument("--name", required=True)
    plan_cmd.add_argument("--repeats", type=int, default=3)
    plan_cmd.add_argument("--seed", type=int, default=20261022)
    plan_cmd.add_argument("--max-part-runs", type=int, default=480)
    plan_cmd.add_argument("--api-config", type=Path)
    plan_cmd.add_argument("--output", type=Path, required=True)
    for command in ("export-cases", "link", "verify", "preflight"):
        cmd = commands.add_parser(command)
        cmd.add_argument("plan", type=Path)
        if command in {"link", "verify"}:
            cmd.add_argument("--campaigns", nargs="+", type=Path, required=True)
        if command in {"export-cases", "link"}:
            cmd.add_argument("--output", type=Path, required=True)
        if command == "export-cases":
            cmd.add_argument("--part", required=True)
        if command == "verify":
            cmd.add_argument("--evidence", type=Path, required=True)
        if command == "preflight":
            cmd.add_argument("--already-spent-eur")
            for gate in ("author-acceptance", "outer-isolation", "external-restore"):
                cmd.add_argument("--" + gate, type=Path)
    return parser


def _run_command(args: argparse.Namespace) -> None:
    if args.command == "plan":
        config = _read_json(args.api_config) if args.api_config else None
        value = make_plan(load_cases(args.cases), name=args.name, repeats=args.repeats,
                          seed=args.seed, max_part_runs=args.max_part_runs, provider_config=config)
        _new_output(args.output, value, [args.cases])
        print(json.dumps({"plan": str(args.output), "planned_runs": value["planned_runs"], "parts": value["parts"]}))
        return
    plan = _read_json(args.plan)
    if args.command == "export-cases":
        export_part_cases(plan, args.part, args.output)
        print("Frozen cases exported; no campaign started.")
    elif args.command == "link":
        value = link_campaigns(plan, args.campaigns)
        _new_output(args.output, value, [args.plan, *args.campaigns])
        print(json.dumps(value, ensure_ascii=True))
    elif args.command == "verify":
        print(json.dumps(verify_study(plan, _read_json(args.evidence), args.campaigns)))
    else:
        records = {key: getattr(args, key) for key in ("author_acceptance", "outer_isolation", "external_restore") if getattr(args, key)}
        print(json.dumps(preflight(plan, already_spent_eur=args.already_spent_eur, records=records), indent=2))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _run_command(args)
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"Study error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
