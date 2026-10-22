"""Paired randomized campaigns and immutable, hash-checked run records."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Callable

from . import __version__
from .contracts import Model

VARIANTS = ("B", "F", "P", "FP")
SOURCES = ("clean", "attack")


def digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def provenance() -> dict:
    root = Path(__file__).resolve().parents[2]
    source_hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted((root / "src").rglob("*.py"))}
    for name in ("pyproject.toml", "uv.lock", ".python-version"):
        p = root / name
        if p.exists():
            source_hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    def git(*args: str) -> str | None:
        try:
            return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL,
                                           timeout=5, text=True).strip()
        except (OSError, subprocess.SubprocessError):
            return None
    return {"version": __version__, "python": sys.version, "git_commit": git("rev-parse", "HEAD"),
            "git_status": git("status", "--porcelain"), "source_sha256": source_hashes}


def schedule(cases: list[dict], variants: list[str], sources: list[str], repeats: int,
             seed: int) -> list[dict]:
    if not cases or repeats < 1 or repeats > 100:
        raise ValueError("At least one case and 1..100 repetitions are required")
    if not variants or not sources or len(set(variants)) != len(variants) or len(set(sources)) != len(sources):
        raise ValueError("Nonempty unique conditions required")
    if set(variants) - set(VARIANTS) or set(sources) - set(SOURCES):
        raise ValueError("Unknown variant or source")
    rng = random.Random(seed)
    order = []
    for case in sorted(cases, key=lambda item: item["case_id"]):
        for repetition in range(1, repeats + 1):
            block = [{"case_id": case["case_id"], "repetition": repetition,
                      "variant": variant, "source": source}
                     for variant in variants for source in sources]
            rng.shuffle(block)
            order.extend(block)
    return order


def run_batch(cases: list[dict], output: Path, factory: Callable[[dict, str], Model], *,
              variants: list[str], sources: list[str], repeats: int = 1, seed: int = 20261022,
              max_tool_calls: int = 8, max_model_calls: int = 12,
              timeout_seconds: float = 120, provider_config: dict | None = None) -> dict:
    from .core import run_case
    from .evaluation import evaluate_run, summarize
    order = schedule(cases, variants, sources, repeats, seed)
    if not (1 <= max_tool_calls <= 100 and 1 <= max_model_calls <= 100 and 0 < timeout_seconds <= 3600):
        raise ValueError("Invalid execution limits")
    # Existing campaign paths are never silently overwritten or appended to.
    output.mkdir(parents=True, exist_ok=False)
    fixture_seed = secrets.token_hex(32)
    manifest = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "state": "running", "stage": "development", "provenance": provenance(),
                "cases_sha256": digest(cases), "order_seed": seed, "fixture_seed": fixture_seed,
                "limits": {"max_tool_calls": max_tool_calls, "max_model_calls": max_model_calls,
                           "timeout_seconds": timeout_seconds}, "provider_config": provider_config,
                "schedule": order, "runs": []}
    write_json(output / "cases.snapshot.json", cases)
    write_json(output / "manifest.json", manifest)
    by_id = {case["case_id"]: case for case in cases}
    results = []
    try:
        for index, entry in enumerate(order, 1):
            case = by_id[entry["case_id"]]
            result = run_case(case, entry["variant"], entry["source"], factory(case, entry["source"]),
                              repetition=entry["repetition"], run_id=f"run-{index:05d}",
                              fixture_seed=fixture_seed, **manifest["limits"])
            result["metrics"] = evaluate_run(result)
            relative = f"records/{result['run_id']}.json"
            write_json(output / relative, result)
            event_path = output / "events" / (result["run_id"] + ".jsonl")
            event_path.parent.mkdir(exist_ok=True)
            with event_path.open("w", encoding="utf-8", newline="\n") as stream:
                for event in result["events"]:
                    stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
            manifest["runs"].append({"path": relative, "sha256": digest(result),
                                     "status": result["status"]})
            results.append(result)
            write_json(output / "manifest.json", manifest)
            if result["status"] in ("budget_exhausted", "technical_error"):
                # Stop rather than spend repeatedly on a broken endpoint/configuration.
                manifest["state"] = "stopped"
                break
        else:
            manifest["state"] = "completed"
    except BaseException:
        manifest["state"] = "interrupted"
        write_json(output / "manifest.json", manifest)
        raise
    manifest["completed_runs"] = len(results)
    manifest["planned_runs"] = len(order)
    write_json(output / "manifest.json", manifest)
    report = summarize(results)
    report["campaign_state"] = manifest["state"]
    report["planned_runs"] = len(order)
    report["completed_runs"] = len(results)
    write_json(output / "summary.json", report)
    return manifest


def load_results(directory: Path) -> list[dict]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    cases = json.loads((directory / "cases.snapshot.json").read_text(encoding="utf-8"))
    if digest(cases) != manifest["cases_sha256"]:
        raise ValueError("Case snapshot hash mismatch")
    results, seen = [], set()
    root = directory.resolve()
    for item in manifest["runs"]:
        path = (directory / item["path"]).resolve()
        if not path.is_relative_to(root) or path in seen:
            raise ValueError("Invalid or duplicate run path")
        seen.add(path)
        value = json.loads(path.read_text(encoding="utf-8"))
        if digest(value) != item["sha256"]:
            raise ValueError(f"Run hash mismatch: {path.name}")
        results.append(value)
    return results
