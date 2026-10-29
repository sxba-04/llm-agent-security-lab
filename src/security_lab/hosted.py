"""Explicit access boundary for a shared, mock-only hosted workbench.

This is operator authentication, not tenant isolation or reviewer identity.
The HTTPS reverse proxy is required. Ephemeral workspaces are explicit demos.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import secrets
from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse, Response


def _https_origin(value: str) -> str:
    """Accept one explicit HTTPS origin, never a URL prefix or wildcard."""
    if not isinstance(value, str) or value != value.strip():
        raise ValueError("Hosting-Adressen müssen vollständige HTTPS-Ursprünge sein.")
    value = value.removesuffix("/")
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" and parsed.hostname and parsed.netloc
                 and parsed.username is None and parsed.password is None
                 and not parsed.path and not parsed.query and not parsed.fragment
                 and re.fullmatch(r"[a-z0-9.-]+(?::[0-9]+)?", parsed.netloc))
        port = parsed.port
        if port is not None and not 1 <= port <= 65535:
            valid = False
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("Hosting-Adressen müssen vollständige HTTPS-Ursprünge ohne Pfad sein.")
    return value


@dataclass(frozen=True)
class HostedSettings:
    public_origin: str
    frontend_origin: str
    token_hashes: tuple[str, ...]
    storage_mode: str = "persistent"

    def __post_init__(self):
        object.__setattr__(self, "public_origin", _https_origin(self.public_origin))
        object.__setattr__(self, "frontend_origin", _https_origin(self.frontend_origin))
        if self.storage_mode not in ("persistent", "ephemeral"):
            raise ValueError("LAB_STORAGE_MODE muss persistent oder ephemeral sein.")
        if (not isinstance(self.token_hashes, tuple) or not 1 <= len(self.token_hashes) <= 8
                or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                       for value in self.token_hashes)
                or len(set(self.token_hashes)) != len(self.token_hashes)):
            raise ValueError("Ein bis acht unterschiedliche SHA-256-Zugangstoken-Hashes sind erforderlich.")

    @property
    def host(self) -> str:
        return urlsplit(self.public_origin).netloc


class HostedAccessMiddleware:
    """Fail closed before application data, effects or body parsing are reached."""

    allowed_methods = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"})
    allowed_headers = frozenset({"authorization", "content-type", "x-lab-token"})

    def __init__(self, app, settings: HostedSettings, token: str, max_request_bytes: int):
        self.app = app
        self.settings = settings
        self.token = token
        self.max_request_bytes = max_request_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        origin = headers.get("origin")
        origin_allowed = (len(headers.getlist("origin")) == 1
                          and origin in {self.settings.public_origin, self.settings.frontend_origin})

        async def secured_send(message):
            if message["type"] == "http.response.start":
                message = {**message, "headers": list(message.get("headers", []))}
                output = MutableHeaders(scope=message)
                output["Cache-Control"] = "no-store"
                output["X-Content-Type-Options"] = "nosniff"
                output["Referrer-Policy"] = "no-referrer"
                output["Strict-Transport-Security"] = "max-age=31536000"
                output.append("Vary", "Origin")
                if origin_allowed:
                    output["Access-Control-Allow-Origin"] = origin
                    output["Access-Control-Expose-Headers"] = "Content-Disposition"
            await send(message)

        async def reject(status, detail):
            response = JSONResponse({"detail": detail}, status_code=status,
                                    headers={"WWW-Authenticate": "Bearer"} if status == 401 else None)
            await response(scope, receive, secured_send)

        if len(headers.getlist("host")) != 1 or headers.get("host") != self.settings.host:
            return await reject(403, "Dieser Host ist für das gehostete Labor nicht zugelassen.")
        if ((origin is not None and not origin_allowed)
                or (origin is None and headers.get("sec-fetch-site") == "cross-site")):
            return await reject(403, "Diese Webseite ist für das gehostete Labor nicht zugelassen.")

        if scope["method"] == "OPTIONS":
            requested_method = headers.get("access-control-request-method", "")
            requested_headers = {value.strip().lower() for value in
                                 headers.get("access-control-request-headers", "").split(",") if value.strip()}
            if (not origin_allowed or requested_method not in self.allowed_methods
                    or not requested_headers <= self.allowed_headers):
                return await reject(403, "Diese browserseitige Anfrage ist nicht zugelassen.")
            return await Response(status_code=204, headers={
                "Access-Control-Allow-Methods": ", ".join(sorted(self.allowed_methods)),
                "Access-Control-Allow-Headers": ", ".join(sorted(self.allowed_headers)),
                "Access-Control-Max-Age": "600",
            })(scope, receive, secured_send)

        if scope["path"] == "/healthz" and scope["method"] == "GET":
            return await JSONResponse({"status": "ok"})(scope, receive, secured_send)

        authorization = headers.get("authorization", "")
        scheme, _, bearer = authorization.partition(" ")
        valid = False
        if (len(headers.getlist("authorization")) == 1 and scheme.lower() == "bearer"
                and re.fullmatch(r"[A-Za-z0-9_-]{43,128}", bearer)):
            supplied_hash = hashlib.sha256(bearer.encode("ascii")).hexdigest()
            # Evaluate every configured digest; do not identify operators by timing.
            for expected in self.settings.token_hashes:
                valid |= secrets.compare_digest(supplied_hash, expected)
        if not valid:
            return await reject(401, "Bitte mit einem gültigen Labor-Zugangstoken anmelden.")

        if scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}:
            supplied = headers.get("x-lab-token", "")
            if (len(headers.getlist("x-lab-token")) != 1
                    or not secrets.compare_digest(supplied.encode("utf-8"), self.token.encode("ascii"))):
                return await reject(403, "Das Sitzungstoken fehlt oder ist ungültig. Bitte neu anmelden.")
        try:
            length = int(headers.get("content-length", "0"))
            if len(headers.getlist("content-length")) > 1 or not 0 <= length <= self.max_request_bytes:
                raise ValueError
        except ValueError:
            return await reject(413, "Anfrage überschreitet die Größenbegrenzung.")

        received = 0
        oversized = False
        replaced_response = False
        response_started = False

        class TooLarge(Exception):
            pass

        async def limited_receive():
            nonlocal received, oversized
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_request_bytes:
                    oversized = True
                    raise TooLarge
            return message

        async def limited_send(message):
            nonlocal replaced_response, response_started
            if replaced_response:
                return
            if oversized and message["type"] == "http.response.start":
                # Multipart/JSON parsers may convert receive errors to 400.
                # Preserve the actual limit failure without exposing the body.
                replaced_response = True
                return await reject(413, "Anfrage überschreitet die Größenbegrenzung.")
            if message["type"] == "http.response.start":
                response_started = True
            await secured_send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        except TooLarge:
            if not response_started and not replaced_response:
                return await reject(413, "Anfrage überschreitet die Größenbegrenzung.")
            raise
