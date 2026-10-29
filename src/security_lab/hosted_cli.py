"""Explicit hosted launcher; ordinary security-lab-web remains loopback-only."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Mapping

from .hosted import HostedSettings


def configuration(environment: Mapping[str, str]) -> tuple[HostedSettings, Path, int]:
    settings = HostedSettings(
        public_origin=environment.get("LAB_PUBLIC_ORIGIN") or environment.get("RENDER_EXTERNAL_URL", ""),
        frontend_origin=environment.get("LAB_FRONTEND_ORIGIN", ""),
        token_hashes=tuple(value.strip() for value in environment.get("LAB_ACCESS_TOKEN_HASHES", "").split(",")
                           if value.strip()),
        storage_mode=environment.get("LAB_STORAGE_MODE", "persistent"),
    )
    workspace_value = environment.get("LAB_WORKSPACE", "")
    workspace = Path(workspace_value)
    if not workspace_value or not workspace.is_absolute() or ".." in workspace.parts or workspace == Path(workspace.anchor):
        raise ValueError("LAB_WORKSPACE muss auf ein absolutes Arbeitsverzeichnis zeigen.")
    try:
        port = int(environment.get("PORT", "10000"))
    except ValueError as exc:
        raise ValueError("PORT muss eine Zahl zwischen 1024 und 65535 sein.") from exc
    if not 1024 <= port <= 65535:
        raise ValueError("PORT muss zwischen 1024 und 65535 liegen.")
    return settings, workspace, port


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gehostete Labor-API mit Zugangstoken (nur Mock)")
    parser.add_argument("--cases", type=Path, default=Path("cases/dev"))
    args = parser.parse_args(argv)
    try:
        settings, workspace, port = configuration(os.environ)
    except ValueError as exc:
        parser.error(str(exc))
    import uvicorn
    from .server import create_app

    app = create_app(workspace, args.cases, hosted_settings=settings)
    print("Security Lab: geschützte gehostete API, ausschließlich Mock-Versuche; ein Prozess.")
    if settings.storage_mode == "ephemeral":
        print("Testbetrieb mit flüchtigem Speicher: PDFs, Versuche und Bewertungen können bei Ruhezustand, "
              "Neustart oder Deployment verloren gehen. Benötigte Archive vorher herunterladen.")
    # TLS terminates at the configured hosting proxy. Never trust arbitrary
    # forwarded hosts/protocols; the middleware checks the explicit public host.
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1, reload=False,
                access_log=False, proxy_headers=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
