"""Disposable local browser fixture, never the user's research workspace."""
from pathlib import Path
import tempfile

from security_lab.web_cli import main


ROOT = Path(__file__).resolve().parents[2]

if __name__ == "__main__":
    base = ROOT / "runs" / "browser-ci"
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="workspace-", dir=base) as directory:
        raise SystemExit(main([
            "--workspace", directory, "--cases", str(ROOT / "cases" / "dev"),
            "--frontend-dir", str(ROOT / "frontend" / "dist"),
        ]))
