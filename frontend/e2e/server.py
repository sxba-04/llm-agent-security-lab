"""Disposable local browser fixture, never the user's research workspace."""
from pathlib import Path
import tempfile

from security_lab.web_cli import main as launch_workbench


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="security-lab-browser-local-") as directory:
        return launch_workbench([
            "--workspace", directory, "--cases", str(ROOT / "cases" / "dev"),
            "--frontend-dir", str(ROOT / "frontend" / "dist"),
        ])


if __name__ == "__main__":
    raise SystemExit(main())
