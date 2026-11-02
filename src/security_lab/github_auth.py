"""Bounded, in-memory GitHub identity login for the two-author workbench.

GitHub credentials never become lab tokens. OAuth verifies identity once, with
PKCE and a browser-held verifier, then issues a separately revocable lab session.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import base64
import hashlib
from http.client import HTTPException
import json
import re
import secrets
import threading
import time
from typing import Callable, Mapping
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, Request, build_opener

SESSION_SECONDS = 8 * 60 * 60
LOGIN_SECONDS = 10 * 60
MAX_PENDING = 64
MAX_SESSIONS = 64
MAX_USER_SESSIONS = 8
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43,128}\Z")
CHALLENGE_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
VERIFIER_PATTERN = re.compile(r"[A-Za-z0-9._~-]{43,128}\Z")
LOGIN_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
PERMISSIONS = ("read", "write", "manage_own_sessions")
INVALID_LOGIN = "Die GitHub-Anmeldung ist ungültig oder abgelaufen. Bitte erneut beginnen."


class LoginError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class GitHubSettings:
    client_id: str
    client_secret: str = field(repr=False)
    redirect_uri: str
    allowed_user_ids: tuple[int, ...]

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9_.-]{5,100}", self.client_id):
            raise ValueError("LAB_GITHUB_CLIENT_ID ist ungültig.")
        if not isinstance(self.client_secret, str) or not re.fullmatch(r"[A-Za-z0-9_-]{20,200}", self.client_secret):
            raise ValueError("LAB_GITHUB_CLIENT_SECRET ist ungültig.")
        parsed = urlsplit(self.redirect_uri)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment
                or not re.fullmatch(r"/[A-Za-z0-9_/-]*", parsed.path)
                or "//" in parsed.path or self.redirect_uri != self.redirect_uri.strip()):
            raise ValueError("LAB_GITHUB_REDIRECT_URI muss eine feste HTTPS-Frontend-Adresse sein.")
        if (not isinstance(self.allowed_user_ids, tuple) or not 1 <= len(self.allowed_user_ids) <= 8
                or any(type(value) is not int or not 1 <= value <= 2**53 - 1 for value in self.allowed_user_ids)
                or len(set(self.allowed_user_ids)) != len(self.allowed_user_ids)):
            raise ValueError("LAB_GITHUB_ALLOWED_USER_IDS benötigt ein bis acht eindeutige GitHub-Konto-IDs.")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> GitHubSettings | None:
        keys = ("LAB_GITHUB_CLIENT_ID", "LAB_GITHUB_CLIENT_SECRET", "LAB_GITHUB_REDIRECT_URI",
                "LAB_GITHUB_ALLOWED_USER_IDS")
        values = [environment.get(key, "") for key in keys]
        if not any(values):
            return None
        if not all(values):
            raise ValueError("Die GitHub-Anmeldung benötigt alle vier LAB_GITHUB-Einstellungen.")
        ids = values[3].split(",")
        if any(not re.fullmatch(r"[1-9]\d{0,15}", value.strip(), re.ASCII) for value in ids):
            raise ValueError("LAB_GITHUB_ALLOWED_USER_IDS muss numerische GitHub-Konto-IDs enthalten.")
        return cls(values[0], values[1], values[2], tuple(int(value) for value in ids))


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def pkce_challenge(verifier: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


def _timestamp(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).isoformat().replace("+00:00", "Z")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHubIdentityClient:
    """Contact only fixed GitHub HTTPS endpoints, never a user-provided URL."""

    def __init__(self, settings: GitHubSettings):
        self.settings = settings
        # HTTPSHandler's standard context verifies certificates and hostnames.
        # No custom TLS context or redirect can weaken that default boundary.
        self.opener = build_opener(_NoRedirect(), HTTPSHandler())

    def _json(self, request: Request) -> dict:
        try:
            with self.opener.open(request, timeout=10) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError("Oversized identity response")
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError("Invalid identity response")
                return value
        except (OSError, ValueError, HTTPException, RecursionError):
            # Never propagate provider bodies/URLs: they can contain credentials.
            raise LoginError(502, "GitHub ist für die Anmeldung derzeit nicht erreichbar. Bitte erneut versuchen.") from None

    def identity(self, code: str, verifier: str) -> dict:
        token_data = self._json(Request("https://github.com/login/oauth/access_token", data=urlencode({
            "client_id": self.settings.client_id, "client_secret": self.settings.client_secret,
            "code": code, "redirect_uri": self.settings.redirect_uri, "code_verifier": verifier,
        }).encode("ascii"), headers={"Accept": "application/json", "User-Agent": "security-lab-identity",
                                    "Content-Type": "application/x-www-form-urlencoded"}, method="POST"))
        access_token = token_data.get("access_token")
        token_type = token_data.get("token_type")
        if (not isinstance(access_token, str) or not re.fullmatch(r"\w{20,4096}", access_token, re.ASCII)
                or not isinstance(token_type, str) or token_type.lower() != "bearer"):
            raise LoginError(401, INVALID_LOGIN)
        # No repo/email scope is requested. The token is used once and discarded.
        return self._json(Request("https://api.github.com/user", headers={
            "Authorization": "Bearer " + access_token, "Accept": "application/vnd.github+json",
            "User-Agent": "security-lab-identity", "X-GitHub-Api-Version": "2022-11-28",
        }))


@dataclass(frozen=True)
class Principal:
    id: int
    login: str

    def public(self) -> dict:
        return {"id": self.id, "login": self.login, "role": "researcher", "permissions": list(PERMISSIONS)}


@dataclass
class _Pending:
    challenge: str
    expires_at: float


@dataclass
class _Session:
    id: str
    principal: Principal
    created_at: float
    expires_at: float


class GitHubSessions:
    """One-process session store. Restart revokes sessions and pending logins."""

    def __init__(self, settings: GitHubSettings, *, identity_client=None, clock: Callable[[], float] = time.time):
        self.settings = settings
        self.identity_client = identity_client or GitHubIdentityClient(settings)
        self.clock = clock
        self.lock = threading.RLock()
        self.pending: dict[str, _Pending] = {}
        self.sessions: dict[str, _Session] = {}
        self.attempts: dict[str, deque] = {}
        self.exchange_slots = threading.BoundedSemaphore(4)

    def _prune(self, now: float) -> None:
        self.pending = {key: value for key, value in self.pending.items() if value.expires_at > now}
        self.sessions = {key: value for key, value in self.sessions.items() if value.expires_at > now}
        for queue in self.attempts.values():
            while queue and queue[0] <= now - 60:
                queue.popleft()
        self.attempts = {key: queue for key, queue in self.attempts.items() if queue}

    def _rate_limit(self, operation: str, client: str) -> float:
        now = self.clock()
        self._prune(now)
        # The transport address is used, never attacker-controlled forwarded IPs.
        # Behind Render this may be shared: the global cap remains authoritative.
        keys = ((operation + ":global", 30), (operation + ":ip:" + client, 15))
        if len(self.attempts) > 256 or any(len(self.attempts.get(key, ())) >= limit for key, limit in keys):
            raise LoginError(429, "Zu viele Anmeldeversuche. Bitte eine Minute warten.")
        for key, _ in keys:
            self.attempts.setdefault(key, deque()).append(now)
        return now

    def start(self, challenge: str, client: str) -> dict:
        if not isinstance(challenge, str) or not CHALLENGE_PATTERN.fullmatch(challenge):
            raise LoginError(400, INVALID_LOGIN)
        with self.lock:
            now = self._rate_limit("start", client)
            if len(self.pending) >= MAX_PENDING:
                raise LoginError(429, "Zu viele offene Anmeldungen. Bitte später erneut versuchen.")
            state = secrets.token_urlsafe(32)
            self.pending[_fingerprint(state)] = _Pending(challenge, now + LOGIN_SECONDS)
        query = urlencode({"client_id": self.settings.client_id, "redirect_uri": self.settings.redirect_uri,
                           "state": state, "scope": "", "code_challenge": challenge,
                           "code_challenge_method": "S256", "allow_signup": "false", "prompt": "select_account"})
        return {"authorization_url": "https://github.com/login/oauth/authorize?" + query,
                "state": state, "expires_in": LOGIN_SECONDS}

    def _consume_login(self, code: str, state: str, verifier: str, client: str) -> None:
        with self.lock:
            self._rate_limit("complete", client)
            if (not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", code)
                    or not isinstance(state, str) or not TOKEN_PATTERN.fullmatch(state)
                    or not isinstance(verifier, str) or not VERIFIER_PATTERN.fullmatch(verifier)):
                raise LoginError(400, INVALID_LOGIN)
            key = _fingerprint(state)
            pending = self.pending.get(key)
            if pending is None or not secrets.compare_digest(pending.challenge, pkce_challenge(verifier)):
                raise LoginError(401, INVALID_LOGIN)
            # Consume before any provider request; provider failures never replay.
            del self.pending[key]

    def complete(self, code: str, state: str, verifier: str, client: str) -> dict:
        self._consume_login(code, state, verifier, client)
        if not self.exchange_slots.acquire(blocking=False):
            raise LoginError(429, "Die Anmeldung ist ausgelastet. Bitte erneut beginnen.")
        try:
            identity = self.identity_client.identity(code, verifier)
        finally:
            self.exchange_slots.release()
        identifier = identity.get("id")
        login = identity.get("login")
        if (type(identifier) is not int or identifier not in self.settings.allowed_user_ids
                or not isinstance(login, str) or not LOGIN_PATTERN.fullmatch(login)):
            raise LoginError(403, "Dieses GitHub-Konto ist für die Werkbank nicht freigegeben.")
        principal = Principal(identifier, login)
        with self.lock:
            now = self.clock()
            self._prune(now)
            own = sorted(((key, value) for key, value in self.sessions.items()
                          if value.principal.id == identifier), key=lambda item: item[1].created_at)
            if len(own) >= MAX_USER_SESSIONS:
                # Repeated reloads must not lock an author out for eight hours.
                # Only this authenticated account's oldest session is revoked.
                del self.sessions[own[0][0]]
            if len(self.sessions) >= MAX_SESSIONS:
                raise LoginError(429, "Zu viele aktive Sitzungen. Bitte bestehende Sitzungen zuerst abmelden.")
            token = secrets.token_urlsafe(32)
            self.sessions[_fingerprint(token)] = _Session(secrets.token_hex(16), principal, now, now + SESSION_SECONDS)
        return {"access_token": token, "token_type": "Bearer", "expires_in": SESSION_SECONDS, "user": principal.public()}

    def authenticate(self, token: str) -> Principal | None:
        if not TOKEN_PATTERN.fullmatch(token):
            return None
        with self.lock:
            self._prune(self.clock())
            session = self.sessions.get(_fingerprint(token))
            return session.principal if session else None

    def list_sessions(self, token: str) -> list[dict]:
        with self.lock:
            self._prune(self.clock())
            current = self.sessions.get(_fingerprint(token))
            if current is None:
                return []
            return [{"id": item.id, "created_at": _timestamp(item.created_at),
                     "expires_at": _timestamp(item.expires_at), "current": item is current}
                    for item in self.sessions.values() if item.principal.id == current.principal.id]

    def revoke(self, token: str, session_id: str | None = None) -> bool:
        with self.lock:
            self._prune(self.clock())
            key = _fingerprint(token)
            current = self.sessions.get(key)
            if current is None:
                return False
            if session_id is None:
                del self.sessions[key]
                return True
            target = next((key for key, value in self.sessions.items()
                           if value.id == session_id and value.principal.id == current.principal.id), None)
            if target is None:
                return False
            del self.sessions[target]
            return True
