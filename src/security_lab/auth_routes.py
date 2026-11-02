"""HTTP adapters for hosted identity; experiment routes remain unchanged."""
from __future__ import annotations

import json
import re

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from .github_auth import GitHubSessions, INVALID_LOGIN, LoginError


def _bearer(request: Request) -> str:
    return request.headers.get("authorization", "").partition(" ")[2]


async def _body(request: Request, fields: set[str]) -> dict:
    try:
        value = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise LoginError(400, INVALID_LOGIN) from None
    if not isinstance(value, dict) or set(value) != fields:
        raise LoginError(400, INVALID_LOGIN)
    return value


def register_auth_routes(app, sessions: GitHubSessions | None) -> None:
    @app.exception_handler(LoginError)
    async def login_error(request, error):
        return JSONResponse({"detail": error.detail}, status_code=error.status)

    @app.post("/api/auth/logout")
    def logout(request: Request):
        return {"revoked": sessions.revoke(_bearer(request)) if sessions else False}

    @app.get("/api/auth/sessions")
    def own_sessions(request: Request):
        return {"sessions": sessions.list_sessions(_bearer(request)) if sessions else []}

    @app.delete("/api/auth/sessions/{session_id}", responses={404: {"description": "Own session not found."}})
    def revoke_session(session_id: str, request: Request):
        if (not re.fullmatch(r"[0-9a-f]{32}", session_id) or sessions is None
                or not sessions.revoke(_bearer(request), session_id)):
            raise HTTPException(404, "Eigene Sitzung nicht gefunden.")
        return {"revoked": True}

    if sessions is None:
        return

    def client_address(request: Request) -> str:
        return request.client.host if request.client else "unknown"

    @app.post("/api/auth/github/start", responses={429: {"description": "Login capacity or rate limit reached."}})
    async def start(request: Request):
        body = await _body(request, {"code_challenge"})
        return sessions.start(body["code_challenge"], client_address(request))

    @app.post("/api/auth/github/complete", responses={429: {"description": "Login capacity or rate limit reached."},
                                                     502: {"description": "GitHub identity provider unavailable."}})
    async def complete(request: Request):
        body = await _body(request, {"code", "state", "code_verifier"})
        return await run_in_threadpool(sessions.complete, body["code"], body["state"],
                                       body["code_verifier"], client_address(request))
