"""Run the local Python, React, build and browser checks without installing tools."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-browsers", action="store_true", help="Include Firefox and WebKit smoke tests.")
    args = parser.parse_args(argv)
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    uv = shutil.which("uv")
    if not npm or not uv:
        print("uv and npm must already be installed. Run the separate setup steps first.")
        return 1
    # The Playwright webServer starts uv too. Propagate the same no-install
    # boundary into that child, rather than only protecting direct uv calls.
    environment = {**os.environ, "UV_NO_SYNC": "true", "UV_NO_BUILD": "true"}
    steps = [
        ("Python lint (bounded rule set)", ROOT, [uv, "run", "--no-sync", "--locked", "ruff", "check", "."]),
        ("Python tests", ROOT, [uv, "run", "--no-sync", "--locked", "--extra", "web", "--group", "dev", "python", "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("React tests", ROOT / "frontend", [npm, "test"]),
        ("TypeScript and production build", ROOT / "frontend", [npm, "run", "build"]),
        ("Browser tests", ROOT / "frontend", [npm, "run", "test:e2e" if args.all_browsers else "test:e2e:chromium"]),
    ]
    for title, directory, command in steps:
        print("\n" + title, flush=True)
        try:
            result = subprocess.run(command, cwd=directory, check=False, env=environment)
        except OSError:
            print("Unable to start this check. No successful overall result is claimed.")
            return 1
        if result.returncode:
            print("Check failed; remaining steps were not run.")
            return result.returncode
    print("Lint, Python, React, build and selected browser checks passed. Mock-only technical validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
