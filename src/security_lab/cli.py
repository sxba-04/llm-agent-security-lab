"""Command-line entry point. All defaults are offline and free of API charges."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from .batch import SOURCES, VARIANTS, digest, load_results, provenance, run_batch, write_json
from .cases import load_cases


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Synthetic LLM agent security lab (offline by default)")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("demo", "run"):
        cmd = sub.add_parser(name, help="Run offline engineering demo" if name == "demo" else "Run a development campaign")
        cmd.add_argument("--cases", type=Path, default=Path("cases/dev"))
        cmd.add_argument("--output", type=Path, default=Path("runs") / (name + "-" + datetime.now().strftime("%Y%m%d-%H%M%S")))
        cmd.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
        cmd.add_argument("--sources", nargs="+", choices=SOURCES, default=list(SOURCES))
        cmd.add_argument("--repeats", type=int, default=1)
        cmd.add_argument("--seed", type=int, default=20261022)
        cmd.add_argument("--max-tool-calls", type=int, default=8)
        cmd.add_argument("--max-model-calls", type=int, default=12)
        cmd.add_argument("--timeout-seconds", type=float, default=120)
        if name == "run":
            cmd.add_argument("--provider", choices=("mock", "openai"), default="mock")
            cmd.add_argument("--api-config", type=Path)
            cmd.add_argument("--allow-paid-api", action="store_true")
            cmd.add_argument("--isolation-acknowledged", action="store_true",
                             help="Operator confirms independently verified outer containment; flag itself is no sandbox")
            cmd.add_argument("--ledger", type=Path, default=Path("runs/budget.json"))
    cmd = sub.add_parser("summarize", help="Recompute summary from hash-checked original records")
    cmd.add_argument("directory", type=Path)
    cmd.add_argument("--output", type=Path, required=True)
    cmd.add_argument("--reviews", type=Path, help="Combined human ratings bound to these original run hashes")
    cmd = sub.add_parser("review-export", help="Export blinded material and two empty rating templates")
    cmd.add_argument("directory", type=Path)
    cmd.add_argument("--output", type=Path, required=True)
    cmd = sub.add_parser("review-adjudicate", help="Resolve one disagreement while preserving both original ratings")
    cmd.add_argument("--input", type=Path, required=True)
    cmd.add_argument("--review-id", required=True)
    cmd.add_argument("--legitimate-rating", choices=("correct", "partial", "refused", "undecidable"), required=True)
    cmd.add_argument("--attack-success", choices=("yes", "no", "undecidable"), required=True)
    cmd.add_argument("--false-block", choices=("yes", "no", "undecidable"), required=True)
    cmd.add_argument("--rationale", required=True)
    cmd.add_argument("--adjudicators", nargs="+", required=True)
    cmd.add_argument("--output", type=Path, required=True)
    cmd = sub.add_parser("review-import", help="Combine two independent ratings without hiding disagreement")
    cmd.add_argument("--mapping", type=Path, required=True)
    cmd.add_argument("--ratings", nargs=2, type=Path, required=True)
    cmd.add_argument("--output", type=Path, required=True)
    cmd = sub.add_parser("freeze", help="Record a development snapshot; not a release of the main experiment")
    cmd.add_argument("--cases", type=Path, default=Path("cases/dev"))
    cmd.add_argument("--output", type=Path, required=True)
    cmd = sub.add_parser("validate", help="Validate case structure and paired source data")
    cmd.add_argument("--cases", type=Path, default=Path("cases/dev"))
    return p


def _factory(args: argparse.Namespace):
    from .models import ScriptedModel
    if getattr(args, "provider", "mock") == "mock":
        return lambda case, source: ScriptedModel(case, source), {"provider": "mock", "engineering_only": True}
    if not args.allow_paid_api or not args.isolation_acknowledged:
        raise ValueError("Live calls require --allow-paid-api and --isolation-acknowledged. No network request was made.")
    if args.api_config is None:
        raise ValueError("Specify --api-config with verified model, price and request limits")
    config = json.loads(args.api_config.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or any("key" in key.lower() or "secret" in key.lower() for key in config):
        raise ValueError("API configuration must be an object without credentials; use OPENAI_API_KEY")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key.strip():
        raise ValueError("OPENAI_API_KEY is not configured")
    from .budget import BudgetLedger
    from .providers import OpenAIModel
    ledger = BudgetLedger(args.ledger, limit_eur=250, request_limit_eur=1.0)
    model = OpenAIModel(config, api_key, ledger)
    # One provider instance shares its run cap across all cases, not one cap per case.
    return lambda case, source: model, {"provider": "openai", **config}


def main(argv: list[str] | None = None) -> int:
    p = parser()
    args = p.parse_args(argv)
    try:
        if args.command in ("demo", "run"):
            cases = load_cases(args.cases)
            if args.command == "demo":
                # One pair from each goal; whole catalog available with run.
                selected = {}
                for case in cases:
                    selected.setdefault(case["goal"], case)
                cases = list(selected.values())
            factory, config = _factory(args)
            manifest = run_batch(cases, args.output, factory, variants=args.variants, sources=args.sources,
                                 repeats=args.repeats, seed=args.seed, max_tool_calls=args.max_tool_calls,
                                 max_model_calls=args.max_model_calls, timeout_seconds=args.timeout_seconds,
                                 provider_config=config)
            print(f"{manifest['state']}: {manifest['completed_runs']}/{manifest['planned_runs']} runs -> {args.output}")
            if config.get("provider") == "mock":
                print("MOCK ENGINEERING CHECKS ONLY. These are not empirical LLM results.")
            return 0 if manifest["state"] == "completed" else 2
        if args.command == "validate":
            cases = load_cases(args.cases)
            print(f"Valid: {len(cases)} paired cases")
        elif args.command == "summarize":
            from .evaluation import summarize
            results = load_results(args.directory)
            if args.reviews:
                from .review import attach_reviews
                results = attach_reviews(results, json.loads(args.reviews.read_text(encoding="utf-8")))
            value = summarize(results)
            manifest = json.loads((args.directory / "manifest.json").read_text(encoding="utf-8"))
            protected = [(args.directory / entry["path"]).resolve() for entry in manifest["runs"]]
            protected += [(args.directory / name).resolve() for name in ("manifest.json", "cases.snapshot.json")]
            if args.output.resolve() in protected:
                raise ValueError("Summary output must not overwrite original campaign evidence")
            value.update(campaign_state=manifest["state"], planned_runs=len(manifest["schedule"]), completed_runs=len(manifest["runs"]))
            write_json(args.output, value)
            print(f"Summary -> {args.output}")
        elif args.command == "review-export":
            from .review import export_review
            export_review(load_results(args.directory), args.output)
            print(f"Blinded review material -> {args.output}")
        elif args.command == "review-import":
            from .review import combine_reviews
            combine_reviews(args.mapping, args.ratings, args.output)
            print(f"Independent ratings -> {args.output}")
        elif args.command == "review-adjudicate":
            from .review import adjudicate_review
            if args.output.exists():
                raise ValueError("Use a new output path to preserve earlier review versions")
            combined = json.loads(args.input.read_text(encoding="utf-8"))
            updated = adjudicate_review(combined, args.review_id,
                                        legitimate_rating=args.legitimate_rating,
                                        attack_success=args.attack_success,
                                        false_block=args.false_block,
                                        rationale=args.rationale, adjudicators=args.adjudicators)
            write_json(args.output, updated)
            print(f"Adjudication -> {args.output}")
        elif args.command == "freeze":
            if args.output.exists():
                raise ValueError("Snapshot path already exists; use a new version")
            cases = load_cases(args.cases)
            write_json(args.output, {"schema_version": 1, "stage": "development", "main_experiment_approved": False,
                                    "created_at": datetime.now(timezone.utc).isoformat(), "provenance": provenance(),
                                    "cases_sha256": digest(cases), "cases": cases})
            print(f"Development snapshot -> {args.output}")
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(f"Error: {exc}", file=__import__("sys").stderr)
        return 2
