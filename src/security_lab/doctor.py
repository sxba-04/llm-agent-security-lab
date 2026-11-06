"""Read-only local setup diagnostics; never installs packages or sends HTTP requests.

Run with ``python -B -m security_lab.doctor`` to suppress interpreter bytecode
writes as well. Environment values, certificate paths and command output are
never included in the report; only validated versions and diagnostic states.
"""
from __future__ import annotations

import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
MIB = 1024 * 1024


def check(name: str, status: str, detail: str, action: str = "") -> dict:
    return {"name": name, "status": status, "detail": detail, "action": action}


def tool_version(name: str) -> str | None:
    """Run a fixed version query without printing stderr or arbitrary output."""
    executable = shutil.which(name + ".cmd" if os.name == "nt" and name == "npm" else name)
    if executable is None:
        return None
    try:
        result = subprocess.run([executable, "--version"], capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=5,
                                check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"(?<![\w.])v?(\d+\.\d+(?:\.\d+)?)\b", result.stdout[:512])
    return match.group(1) if result.returncode == 0 and match else None


def version_checks() -> list[dict]:
    version = sys.version_info[:3]
    status = "ok" if version[:2] == (3, 12) else "warning" if version >= (3, 12) else "error"
    rows = [check("python", status, ".".join(map(str, version)),
                  "Referenzlaufzeit: Python 3.12 aus .python-version; weitere Versionen sind nicht zugesichert.")]
    for name in ("git", "uv", "node", "npm"):
        value = tool_version(name)
        state = "ok" if value else "error"
        if name == "node" and value:
            parts = tuple(map(int, value.split(".")))
            state = "ok" if (24, 15, 0) <= parts < (25,) else "error"
        rows.append(check(name, state, value or "Nicht verfügbar oder Versionsabfrage fehlgeschlagen.",
                          "Node 24 ab 24.15.0 verwenden." if name == "node" else "Werkzeug über den erlaubten Installationsweg bereitstellen."))
    for package in ("fastapi", "pypdf", "python-multipart", "uvicorn", "httpx"):
        try:
            value = metadata.version(package)
        except metadata.PackageNotFoundError:
            value = None
        rows.append(check("package:" + package, "ok" if value else "error", value or "Nicht installiert.",
                          "Separat ausführen: uv sync --locked --extra web --group dev"))
    return rows


def build_check(root: Path) -> dict:
    frontend = root / "frontend"
    built = frontend / "dist" / "index.html"
    if not built.is_file():
        return check("frontend-build", "error", "Frontend-Build fehlt.", "In frontend zuerst npm ci, danach npm run build ausführen.")
    sources = [frontend / name for name in ("index.html", "package-lock.json", "package.json")]
    for folder in ("src", "public"):
        sources.extend(path for path in (frontend / folder).rglob("*") if path.is_file())
    stale = any(path.exists() and path.stat().st_mtime_ns > built.stat().st_mtime_ns for path in sources)
    return check("frontend-build", "warning" if stale else "ok",
                 "Quelldateien sind neuer als der Build." if stale else "Build vorhanden; Zeitstempel sind plausibel.",
                 "npm run build aktualisiert den Build. Zeitstempel ersetzen keinen Build-/Funktionstest.")


def port_check(port: int) -> dict:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.3)
        occupied = connection.connect_ex(("127.0.0.1", port)) == 0
    return check("port:" + str(port), "warning" if occupied else "ok",
                 "Ein Dienst nimmt TCP-Verbindungen an." if occupied else "Kein erreichbarer TCP-Dienst auf 127.0.0.1.",
                 "Vor Browsertests den eigenen Laborserver beenden; kein Prozess wird automatisch beendet. Die Probe reserviert den Port nicht.")


def workspace_checks(workspace: Path) -> list[dict]:
    ancestor = workspace.absolute()
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    if not ancestor.is_dir():
        return [check("workspace", "error", "Workspace oder vorhandener Vorfahr ist kein Verzeichnis.", "Einen Verzeichnispfad wählen.")]
    writable = os.access(ancestor, os.W_OK | os.X_OK)
    readable = os.access(ancestor, os.R_OK)
    usage = shutil.disk_usage(ancestor)
    fraction = usage.free / usage.total if usage.total > 0 else 0
    low = usage.free < 256 * MIB or fraction < 0.1
    return [check("workspace-access", "ok" if writable and readable else "error",
                  "Lese-/Schreibzugriff laut Betriebssystem verfügbar." if writable and readable else "Zugriffsrechte reichen nicht aus.",
                  "Nur Rechteabfrage, kein Schreibtest. ACLs, Quoten und Virenscanner können spätere Dateizugriffe zusätzlich begrenzen."),
            check("workspace-present", "ok" if workspace.is_dir() else "warning",
                  "Workspace existiert." if workspace.is_dir() else "Workspace fehlt; vorhandener Vorfahr wurde geprüft.",
                  "Der Diagnosebefehl legt keine Verzeichnisse an."),
            check("disk-space", "warning" if low else "ok", f"{usage.free // MIB} MiB frei ({fraction:.1%}).",
                  "Unter 256 MiB oder 10 % freiem Speicher: Belege extern sichern und Speicher prüfen. Dateisystemwerte sind keine Dienst-/Nutzerquote.")]


def _proxy_check(name: str, value: str) -> dict:
    try:
        parsed = urlsplit(value)
        valid = bool(parsed.hostname) and parsed.scheme in {"http", "https", "socks5", "socks5h"}
        valid = valid and (parsed.port is None or 1 <= parsed.port <= 65535)
    except ValueError:
        valid = False
    return check("proxy:" + name, "ok" if valid else "error",
                 "Konfiguriert; URL-Form plausibel." if valid else "Konfiguriert; URL-Form ungültig.",
                 "Wert wird nicht ausgegeben. Erreichbarkeit und Unterstützung durch jedes Werkzeug separat prüfen.")


def _certificate_check(name: str, value: str) -> dict:
    try:
        ssl.create_default_context(cafile=value)
        valid = True
    except (OSError, ssl.SSLError, ValueError):
        valid = False
    return check("ca:" + name, "ok" if valid else "error",
                 "Zertifikatsdatei lesbar und als CA-Bündel ladbar." if valid else "Zertifikatsdatei fehlt oder ist kein ladbares CA-Bündel.",
                 "Freigegebenes Unternehmenszertifikat korrekt konfigurieren; Pfad und Inhalt werden nicht ausgegeben.")


def _tls_policy_check(environment: dict[str, str]) -> dict:
    unsafe = (environment.get("PYTHONHTTPSVERIFY") == "0"
              or environment.get("NODE_TLS_REJECT_UNAUTHORIZED") == "0"
              or environment.get("NPM_CONFIG_STRICT_SSL", "").lower() == "false"
              or environment.get("npm_config_strict_ssl", "").lower() == "false"
              or bool(environment.get("UV_INSECURE_HOST")) or bool(environment.get("PIP_TRUSTED_HOST")))
    return check("tls-policy", "error" if unsafe else "info",
                 "Eine bekannte Umgebungsoption umgeht TLS-Prüfungen." if unsafe else "Keine bekannte TLS-Abschaltung in den geprüften Umgebungsvariablen.",
                 "TLS-Verifikation aktiv lassen. Diese Prüfung liest keine Werkzeugkonfigurationsdateien und beweist keine erfolgreiche TLS-Verbindung.")


def network_configuration_checks(environment: dict[str, str]) -> list[dict]:
    rows = [_proxy_check(name, environment[name]) for name in
            ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy") if environment.get(name)]
    if not rows:
        rows.append(check("proxy", "info", "Keine Proxy-Umgebungsvariable gesetzt.", "Git-/npm-/Systemeinstellungen werden nicht ausgelesen; Unternehmensvorgaben beachten."))
    rows.extend(_certificate_check(name, environment[name]) for name in
                ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS") if environment.get(name))
    rows.append(_tls_policy_check(environment))
    return rows


def diagnose(root: Path, workspace: Path, ports: list[int]) -> dict:
    checks = version_checks()
    for name, operation in (("frontend-build", lambda: [build_check(root)]),
                            ("workspace", lambda: workspace_checks(workspace))):
        try:
            checks.extend(operation())
        except OSError:
            checks.append(check(name, "error", "Pfad oder Dateisysteminformationen sind nicht lesbar."))
    for port in ports:
        try:
            checks.append(port_check(port))
        except OSError:
            checks.append(check("port:" + str(port), "warning", "TCP-Probe nicht möglich."))
    checks.extend(network_configuration_checks(dict(os.environ)))
    return {"schema_version": 1, "read_only": True, "network_requests": "loopback TCP probes only; no HTTP or external network",
            "ready": not any(row["status"] == "error" for row in checks), "checks": checks}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--workspace", type=Path, default=Path("runs"))
    parser.add_argument("--port", type=int, action="append", help="Loopback port; repeat for more ports (default 8765).")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    ports = args.port or [8765]
    if any(not 1 <= port <= 65535 for port in ports):
        parser.error("port must be between 1 and 65535")
    report = diagnose(args.root, args.workspace, ports)
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        for item in report["checks"]:
            print(f"[{item['status'].upper()}] {item['name']}: {item['detail']}")
            if item["status"] != "ok" and item["action"]:
                print("  " + item["action"])
        print("Keine Installation, Dateiänderung oder externe Netzwerkanfrage ausgeführt.")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
