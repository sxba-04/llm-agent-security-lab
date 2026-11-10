"""Explicit access boundary for a authenticated hosted workbench.

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

from .github_auth import GitHubSessions, GitHubSettings

HTTP_RESPONSE_START = "http.response.start"
REQUEST_TOO_LARGE = "Anfrage überschreitet die Größenbegrenzung."


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
                 and re.fullmatch(r"[a-z0-9.-]+(?::\d+)?", parsed.netloc, flags=re.ASCII))
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
    github: GitHubSettings | None = None
    luna_pilot_enabled: bool = False

    def __post_init__(self):
        object.__setattr__(self, "public_origin", _https_origin(self.public_origin))
        object.__setattr__(self, "frontend_origin", _https_origin(self.frontend_origin))
        if self.github is not None:
            redirect = urlsplit(self.github.redirect_uri)
            if f"{redirect.scheme}://{redirect.netloc}" != self.frontend_origin:
                raise ValueError("Die GitHub-Rückleitung muss zur konfigurierten Frontend-Origin gehören.")
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

    def __init__(self, app, settings: HostedSettings, token: str, max_request_bytes: int,
                 github_sessions: GitHubSessions | None = None):
        self.app = app
        self.settings = settings
        self.token = token
        self.max_request_bytes = max_request_bytes
        self.github_sessions = github_sessions

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                return await send({"type": "websocket.close", "code": 1008})
            return await self.app(scope, receive, send)
        return await _HostedRequest(self, scope, receive, send).run()


class _TooLarge(Exception):
    """Signal that a streamed body exceeded this request's configured limit."""


class _HostedRequest:
    """Request-local access checks, response headers and streaming state."""

    def __init__(self, middleware: HostedAccessMiddleware, scope, receive, send):
        self.middleware = middleware
        self.scope, self.receive, self.send = scope, receive, send
        self.headers = Headers(scope=scope)
        self.origin = self.headers.get("origin")
        self.origin_allowed = (len(self.headers.getlist("origin")) == 1
                               and self.origin in {middleware.settings.public_origin,
                                                   middleware.settings.frontend_origin})
        self.request_limit = middleware.max_request_bytes
        self.received = 0
        self.oversized = False
        self.replaced_response = False
        self.response_started = False

    async def secured_send(self, message):
        if message["type"] == HTTP_RESPONSE_START:
            message = {**message, "headers": list(message.get("headers", []))}
            output = MutableHeaders(scope=message)
            output["Cache-Control"] = "no-store"
            output["X-Content-Type-Options"] = "nosniff"
            output["Referrer-Policy"] = "no-referrer"
            output["Strict-Transport-Security"] = "max-age=31536000"
            output.append("Vary", "Origin")
            if self.origin_allowed:
                output["Access-Control-Allow-Origin"] = self.origin
                output["Access-Control-Expose-Headers"] = "Content-Disposition"
        await self.send(message)

    async def reject(self, status, detail, code=None):
        payload = {"detail": detail}
        if code is not None:
            payload["code"] = code
        response = JSONResponse(payload, status_code=status,
                                headers={"WWW-Authenticate": "Bearer"} if status == 401 else None)
        await response(self.scope, self.receive, self.secured_send)

    def _boundary_error(self) -> str | None:
        if len(self.headers.getlist("host")) != 1 or self.headers.get("host") != self.middleware.settings.host:
            return "Dieser Host ist für das gehostete Labor nicht zugelassen."
        if ((self.origin is not None and not self.origin_allowed)
                or (self.origin is None and self.headers.get("sec-fetch-site") == "cross-site")):
            return "Diese Webseite ist für das gehostete Labor nicht zugelassen."
        return None

    async def _preflight(self):
        requested_method = self.headers.get("access-control-request-method", "")
        requested_headers = {value.strip().lower() for value in
                             self.headers.get("access-control-request-headers", "").split(",") if value.strip()}
        if (not self.origin_allowed or requested_method not in self.middleware.allowed_methods
                or not requested_headers <= self.middleware.allowed_headers):
            return await self.reject(403, "Diese browserseitige Anfrage ist nicht zugelassen.")
        return await Response(status_code=204, headers={
            "Access-Control-Allow-Methods": ", ".join(sorted(self.middleware.allowed_methods)),
            "Access-Control-Allow-Headers": ", ".join(sorted(self.middleware.allowed_headers)),
            "Access-Control-Max-Age": "600",
        })(self.scope, self.receive, self.secured_send)

    def _public_response(self) -> Response | None:
        if self.scope["method"] != "GET":
            return None
        if self.scope["path"] == "/healthz":
            return JSONResponse({"status": "ok"})
        if self.scope["path"] == "/api/auth/config":
            return JSONResponse({"github_enabled": self.middleware.github_sessions is not None,
                                 "access_code_enabled": True})
        return None

    def _is_preauth(self) -> bool:
        return (self.middleware.github_sessions is not None and self.scope["method"] == "POST"
                and self.scope["path"] in {"/api/auth/github/start", "/api/auth/github/complete"})

    def _credentials(self):
        authorization = self.headers.get("authorization", "")
        scheme, _, bearer = authorization.partition(" ")
        valid = False
        principal = None
        if (len(self.headers.getlist("authorization")) == 1 and scheme.lower() == "bearer"
                and re.fullmatch(r"[A-Za-z0-9_-]{43,128}", bearer)):
            supplied_hash = hashlib.sha256(bearer.encode("ascii")).hexdigest()
            # Evaluate every configured digest; do not identify operators by timing.
            for expected in self.middleware.settings.token_hashes:
                valid |= secrets.compare_digest(supplied_hash, expected)
            if self.middleware.github_sessions is not None:
                principal = self.middleware.github_sessions.authenticate(bearer)
                valid |= principal is not None
        return valid, principal

    def _authentication_error(self, preauth: bool) -> tuple[int, str, str | None] | None:
        if preauth and (not self.origin_allowed or self.origin != self.middleware.settings.frontend_origin
                        or len(self.headers.getlist("content-type")) != 1
                        or self.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json"):
            return 403, "Die Anmeldung muss von der konfigurierten Werkbank aus gestartet werden.", None
        valid, principal = self._credentials()
        if not valid and not preauth:
            return 401, "Bitte mit GitHub oder einem gültigen Labor-Zugangscode anmelden.", None
        self.scope.setdefault("state", {})["lab_user"] = principal.public() if principal else None
        if not preauth and self.scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}:
            supplied = self.headers.get("x-lab-token", "")
            if (len(self.headers.getlist("x-lab-token")) != 1
                    or not secrets.compare_digest(supplied.encode("utf-8"), self.middleware.token.encode("ascii"))):
                return 403, "Das Sitzungstoken fehlt oder ist ungültig.", "csrf_token_invalid"
        return None

    def _valid_content_length(self) -> bool:
        try:
            length = int(self.headers.get("content-length", "0"))
        except ValueError:
            return False
        return len(self.headers.getlist("content-length")) <= 1 and 0 <= length <= self.request_limit

    async def limited_receive(self):
        message = await self.receive()
        if message["type"] == "http.request":
            self.received += len(message.get("body", b""))
            if self.received > self.request_limit:
                self.oversized = True
                raise _TooLarge
        return message

    async def limited_send(self, message):
        if self.replaced_response:
            return
        if self.oversized and message["type"] == HTTP_RESPONSE_START:
            # Multipart/JSON parsers may convert receive errors to 400.
            # Preserve the actual limit failure without exposing the body.
            self.replaced_response = True
            return await self.reject(413, REQUEST_TOO_LARGE)
        if message["type"] == HTTP_RESPONSE_START:
            self.response_started = True
        await self.secured_send(message)

    async def run(self):
        boundary_error = self._boundary_error()
        if boundary_error is not None:
            return await self.reject(403, boundary_error)
        if self.scope["method"] == "OPTIONS":
            return await self._preflight()
        public = self._public_response()
        if public is not None:
            return await public(self.scope, self.receive, self.secured_send)
        preauth = self._is_preauth()
        error = self._authentication_error(preauth)
        if error is not None:
            return await self.reject(*error)
        self.request_limit = 4096 if preauth else self.middleware.max_request_bytes
        if not self._valid_content_length():
            return await self.reject(413, REQUEST_TOO_LARGE)
        try:
            await self.middleware.app(self.scope, self.limited_receive, self.limited_send)
        except _TooLarge:
            if not self.response_started and not self.replaced_response:
                return await self.reject(413, REQUEST_TOO_LARGE)
            raise
