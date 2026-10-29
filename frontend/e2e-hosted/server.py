"""Disposable HTTPS test servers; never a deployment entry point.

The certificate and bearer below are synthetic fixtures. Each process gets its
own temporary directory under runs/browser-hosted, outside published assets.
"""
from __future__ import annotations

import argparse
from functools import partial
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import subprocess
import tempfile
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ORIGIN = "https://127.0.0.1:4173"
API_ORIGIN = "https://127.0.0.1:8876"
BASE_PATH = "/llm-agent-security-lab/"
# Public test data, intentionally not a real deployment credential.
TEST_TOKEN = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


class StaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *args):
        pass

    def send_head(self):
        path = urlsplit(self.path).path
        if not path.startswith(BASE_PATH):
            self.send_error(404)
            return None
        self.path = self.path[len(BASE_PATH) - 1:]
        return super().send_head()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("api", "static"))
    args = parser.parse_args()
    base = ROOT / "runs" / "browser-hosted"
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=args.mode + "-", dir=base) as temporary:
        directory = Path(temporary)
        key = directory / "localhost.key"
        cert = directory / "localhost.crt"
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256",
            "-keyout", str(key), "-out", str(cert), "-days", "1",
            "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
        ], check=True, capture_output=True, timeout=15)
        if args.mode == "api":
            import uvicorn
            from security_lab.hosted import HostedSettings
            from security_lab.server import create_app

            settings = HostedSettings(API_ORIGIN, FRONTEND_ORIGIN,
                                      (hashlib.sha256(TEST_TOKEN.encode("ascii")).hexdigest(),))
            app = create_app(directory / "workspace", ROOT / "cases" / "dev",
                             hosted_settings=settings)
            uvicorn.run(app, host="127.0.0.1", port=8876, workers=1,
                        ssl_keyfile=str(key), ssl_certfile=str(cert),
                        proxy_headers=False, access_log=False)
        else:
            dist = ROOT / "frontend" / "dist-hosted"
            if not (dist / "index.html").is_file():
                raise SystemExit("Build the hosted frontend before starting the HTTPS fixture.")
            handler = partial(StaticHandler, directory=str(dist))
            server = ThreadingHTTPServer(("127.0.0.1", 4173), handler)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert, key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            try:
                server.serve_forever()
            finally:
                server.server_close()


if __name__ == "__main__":
    main()
