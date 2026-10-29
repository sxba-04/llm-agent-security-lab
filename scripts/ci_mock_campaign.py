"""Run a bounded synthetic campaign and preserve explicit CI artifacts.

The workflow passes choices through environment variables, never shell source.
This helper can also be run locally; every output directory must be new.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PRESETS = {"demo24": ("demo", 24), "catalog96": ("run", 96)}
REPETITIONS = {"1", "2", "3"}


def options(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", default=os.environ.get("LAB_MOCK_PRESET", "demo24"))
    parser.add_argument("--repeats", default=os.environ.get("LAB_MOCK_REPEATS", "1"))
    parser.add_argument("--output", type=Path, default=Path("runs/actions-mock"))
    args = parser.parse_args(argv)
    # Validate environment defaults as strictly as explicit command arguments.
    if args.preset not in PRESETS or args.repeats not in REPETITIONS:
        parser.error("preset must be demo24/catalog96 and repeats must be 1, 2 or 3")
    args.repeats = int(args.repeats)
    return args


def _cli(*args: object, capture: bool = False) -> str:
    process = subprocess.run(
        [sys.executable, "-m", "security_lab", *map(str, args)],
        cwd=ROOT, check=True, text=True, encoding="utf-8",
        stdout=subprocess.PIPE if capture else None,
    )
    return process.stdout or ""


def _json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write("\n")


def _job_summary(report: dict) -> None:
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if not destination:
        return
    with Path(destination).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write("## Synthetic mock campaign\n\n")
        stream.write(f"- Preset: `{report['preset']}`; repetitions: {report['repeats']}.\n")
        if report["completed"]:
            stream.write(f"- Completed: **{report['completed_runs']}/{report['planned_runs']}** runs.\n")
            stream.write(f"- Recomputed records: {report['verified_records']}; valid technical runs: {report['valid_runs']}.\n")
            stream.write("- Campaign archive and restored originals passed integrity/completeness checks.\n")
            stream.write("- Download the campaign artifact from this run; it includes unrated review material.\n")
        else:
            stream.write("- **Incomplete or failed.** Inspect the failed step and available artifacts; no successful campaign is claimed.\n")
        stream.write("\nMock data checks the software only. Human judgments remain empty; this is not empirical LLM evidence.\n")
        stream.write("Archives contain synthetic campaign evidence, not a complete source checkout or a deployed application.\n")


def execute(args: argparse.Namespace) -> dict:
    destination = args.output.resolve()
    # Never reuse or clear an existing evidence directory.
    destination.mkdir(parents=True, exist_ok=False)
    campaign = destination / "campaign"
    command, per_repeat = PRESETS[args.preset]
    report = {"preset": args.preset, "repeats": args.repeats, "completed": False,
              "engineering_only": True, "planned_runs": per_repeat * args.repeats}
    try:
        run_args = [command, "--output", campaign, "--repeats", args.repeats]
        if command == "run":
            run_args += ["--provider", "mock"]
        _cli(*run_args)
        _cli("summarize", campaign, "--output", destination / "summary.json")
        _cli("review-export", campaign, "--output", campaign / "reviews" / "ci-review")
        subprocess.run([sys.executable, str(ROOT / "analysis/export_tables.py"),
                        str(destination / "summary.json"), str(destination / "metrics.csv")],
                       cwd=ROOT, check=True)
        _cli("archive", campaign, "--output", destination / "campaign.zip", capture=True)
        verified = json.loads(_cli("verify-archive", destination / "campaign.zip", capture=True))
        _json(destination / "verification.json", verified)
        restored = json.loads(_cli("restore-archive", destination / "campaign.zip",
                                   "--output", destination / "restored", capture=True))
        _cli("summarize", destination / "restored", "--output", destination / "restored-summary.json")
        summary = json.loads((destination / "summary.json").read_text(encoding="utf-8"))
        restored_summary = json.loads((destination / "restored-summary.json").read_text(encoding="utf-8"))
        manifest = json.loads((campaign / "manifest.json").read_text(encoding="utf-8"))
        expected = report["planned_runs"]
        if (manifest["state"] != "completed" or manifest["completed_runs"] != expected
                or summary["n_runs"] != expected or summary["engineering_only"] is not True
                or summary["mixed_execution_modes"] is not False or summary != restored_summary
                or not all(item.get("verified") is True and item.get("verified_integrity") is True
                           and item.get("evidence_complete") is True and item.get("engineering_only") is True
                           for item in (verified, restored))):
            raise ValueError("Mock campaign or restored evidence failed completeness checks")
        valid = sum(group["n_valid"] for group in summary["groups"])
        if valid != expected:
            raise ValueError("Mock campaign contains invalid technical runs")
        report.update(completed=True, completed_runs=manifest["completed_runs"],
                      verified_records=summary["n_runs"], valid_runs=valid,
                      source_commit=manifest["provenance"]["git_commit"],
                      archive_sha256=verified["archive_sha256"])
        return report
    finally:
        _json(destination / "result.json", report)
        _job_summary(report)


def main(argv: list[str] | None = None) -> int:
    args = options(argv)
    try:
        report = execute(args)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f"Mock campaign failed: {error}", file=sys.stderr)
        return 1
    print(f"Verified mock campaign: {report['completed_runs']}/{report['planned_runs']} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
