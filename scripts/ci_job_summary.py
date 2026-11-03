"""Append the actual checkout and job outcomes to the GitHub Actions summary.

Keeping this code in a Python file makes the interpreter boundary explicit;
Markdown backticks are output data, never shell command substitutions.
"""
from __future__ import annotations

import argparse
from collections.abc import Iterator, Mapping
import os
from pathlib import Path
import subprocess


def summary_lines(kind: str, environment: Mapping[str, str], commit: str) -> Iterator[str]:
    if kind == "python-checks":
        yield "## Python checks on " + environment["RUNNER_OS"] + "\n\n"
        yield "- Behavioral tests: **" + environment["LAB_TEST_OUTCOME"] + "**.\n"
        yield "- Synthetic campaign and archive roundtrip: **" + environment["LAB_CAMPAIGN_OUTCOME"] + "**.\n"
        yield "- Checked-out commit (PR merge when applicable): `" + commit + "`.\n"
        yield "- Artifacts expire after 14 days; download evidence you want to keep.\n"
    else:
        yield "## Job outcome\n\n"
        yield "- Campaign step: **" + environment["LAB_CAMPAIGN_OUTCOME"] + "**.\n"
        yield "- Checked-out commit: `" + commit + "`.\n"
        yield "- This workflow is mock-only and creates no public application endpoint.\n"
        yield "- Download artifacts within 14 days; they are not a permanent backup.\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("python-checks", "mock-campaign"))
    args = parser.parse_args(argv)
    checked_out_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
        for line in summary_lines(args.kind, os.environ, checked_out_commit):
            stream.write(line)


if __name__ == "__main__":
    main()
