"""Launch the offline workbench on loopback with a single process."""
from __future__ import annotations

import argparse
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lokale FastAPI/React-Laboroberfläche (nur Mock)")
    parser.add_argument("--workspace", type=Path, default=Path("runs"))
    parser.add_argument("--cases", type=Path, default=Path("cases/dev"))
    parser.add_argument("--frontend-dir", type=Path, default=Path("frontend/dist"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("Port muss zwischen 1024 und 65535 liegen")
    try:
        import uvicorn
        from .server import create_app
    except ImportError:
        parser.error("Web-Abhängigkeiten fehlen. Bitte zuerst: uv sync --locked --extra web")
    if not (args.frontend_dir / "index.html").is_file():
        parser.error("React-Build fehlt. Bitte im Ordner frontend zuerst npm ci und npm run build ausführen.")
    app = create_app(args.workspace, args.cases, args.frontend_dir)
    print(f"Security Lab: http://127.0.0.1:{args.port} — ausschließlich lokale Mock-Versuche")
    uvicorn.run(app, host="127.0.0.1", port=args.port, workers=1, reload=False, access_log=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
