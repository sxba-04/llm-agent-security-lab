"""GitHub login contract and threat boundaries with synthetic provider replies."""
from __future__ import annotations

import hashlib
from http.client import BadStatusLine
import io
import json
from pathlib import Path
import tempfile
import ssl
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPSHandler, Request

from fastapi.testclient import TestClient

from security_lab.github_auth import (GitHubIdentityClient, GitHubSessions, GitHubSettings,
                                      LOGIN_SECONDS, LoginError, SESSION_SECONDS, pkce_challenge)
from security_lab.hosted import HostedSettings
from security_lab.hosted_cli import configuration
from security_lab.server import create_app

CASES = Path(__file__).resolve().parents[1] / "cases" / "dev"
PUBLIC = "https://lab-api.example.test"
FRONTEND = "https://sxba-04.github.io"
CALLBACK = FRONTEND + "/llm-agent-security-lab/"
ACCESS = "synthetic_access_" + "a" * 43
VERIFIER = "synthetic_verifier_" + "v" * 43
VERIFIER_B = "synthetic_verifier_" + "b" * 43
CODE = "synthetic_github_code"
CLIENT_SECRET = "synthetic_client_secret_" + "s" * 30


def oauth_settings():
    return GitHubSettings("synthetic_client_id", CLIENT_SECRET, CALLBACK, (123, 456))


def hosted_settings(github=True):
    return HostedSettings(PUBLIC, FRONTEND, (hashlib.sha256(ACCESS.encode()).hexdigest(),),
                          github=oauth_settings() if github else None)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.now = 1000000.0
        self.provider = Mock()
        self.provider.identity.return_value = {"id": 123, "login": "author-one", "private_data": "discard"}
        self.sessions = GitHubSessions(oauth_settings(), identity_client=self.provider, clock=lambda: self.now)

    def start(self, verifier=VERIFIER):
        return self.sessions.start(pkce_challenge(verifier), "client-a")

    def login(self, verifier=VERIFIER):
        started = self.start(verifier)
        return self.sessions.complete(CODE, started["state"], verifier, "client-a")

    def test_pkce_flow_minimum_scope_identity_and_unrelated_opaque_token(self):
        started = self.start()
        parsed = urlsplit(started["authorization_url"])
        self.assertEqual(parsed.scheme + "://" + parsed.netloc + parsed.path,
                         "https://github.com/login/oauth/authorize")
        params = parse_qs(parsed.query, keep_blank_values=True)
        self.assertEqual(params["redirect_uri"], [CALLBACK])
        self.assertEqual(params["scope"], [""])
        self.assertEqual(params["code_challenge"], [pkce_challenge(VERIFIER)])
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertNotIn(CLIENT_SECRET, started["authorization_url"])
        self.assertNotIn(VERIFIER, started["authorization_url"])
        result = self.sessions.complete(CODE, started["state"], VERIFIER, "client-a")
        self.provider.identity.assert_called_once_with(CODE, VERIFIER)
        self.assertEqual(result["user"], {"id": 123, "login": "author-one", "role": "researcher",
                                          "permissions": ["read", "write", "manage_own_sessions"]})
        self.assertEqual(result["expires_in"], SESSION_SECONDS)
        self.assertEqual(len(result["access_token"]), 43)
        self.assertNotIn(result["access_token"], self.sessions.sessions)
        self.assertEqual(self.sessions.authenticate(result["access_token"]).id, 123)

    def test_wrong_verifier_state_and_replay_never_call_provider(self):
        started = self.start()
        for state, verifier in (("x" * 43, VERIFIER), (started["state"], VERIFIER_B)):
            with self.subTest(state=state), self.assertRaises(LoginError):
                self.sessions.complete(CODE, state, verifier, "client-a")
        self.provider.identity.assert_not_called()
        self.sessions.complete(CODE, started["state"], VERIFIER, "client-a")
        with self.assertRaises(LoginError):
            self.sessions.complete(CODE, started["state"], VERIFIER, "client-a")
        self.assertEqual(self.provider.identity.call_count, 1)

    def test_expired_state_and_provider_error_require_new_start(self):
        started = self.start()
        self.now += LOGIN_SECONDS
        with self.assertRaises(LoginError):
            self.sessions.complete(CODE, started["state"], VERIFIER, "client-a")
        self.provider.identity.assert_not_called()
        started = self.start()
        self.provider.identity.side_effect = LoginError(502, "Unavailable")
        for _ in range(2):
            with self.assertRaises(LoginError):
                self.sessions.complete(CODE, started["state"], VERIFIER, "client-a")
        self.assertEqual(self.provider.identity.call_count, 1)

    def test_allowlist_uses_immutable_id_not_login(self):
        for identity in ({"id": 789, "login": "author-one"}, {"id": "123", "login": "author-one"},
                         {"id": True, "login": "author-one"}, {"id": 123, "login": "<script>"}):
            self.provider.identity.return_value = identity
            with self.subTest(identity=identity), self.assertRaises(LoginError) as raised:
                self.login()
            self.assertEqual(raised.exception.status, 403)
        self.assertEqual(self.sessions.sessions, {})
        self.provider.identity.return_value = {"id": 123, "login": "renamed-author"}
        self.assertEqual(self.login()["user"]["login"], "renamed-author")

    def test_expiry_revocation_and_restart(self):
        first = self.login()["access_token"]
        second = self.login()["access_token"]
        self.assertTrue(self.sessions.revoke(first))
        self.assertIsNone(self.sessions.authenticate(first))
        self.assertIsNotNone(self.sessions.authenticate(second))
        replacement = GitHubSessions(oauth_settings(), identity_client=self.provider)
        self.assertIsNone(replacement.authenticate(second))
        self.now += SESSION_SECONDS
        self.assertIsNone(self.sessions.authenticate(second))
        self.assertFalse(self.sessions.revoke(second))
        self.assertEqual(self.sessions.list_sessions(second), [])

    def test_session_management_only_owns_same_github_id(self):
        first = self.login()["access_token"]
        second = self.login()["access_token"]
        self.provider.identity.return_value = {"id": 456, "login": "author-two"}
        foreign = self.login()["access_token"]
        own = self.sessions.list_sessions(first)
        self.assertEqual(len(own), 2)
        self.assertEqual(sum(item["current"] for item in own), 1)
        self.assertTrue(own[0]["created_at"].endswith("Z"))
        foreign_id = self.sessions.list_sessions(foreign)[0]["id"]
        self.assertFalse(self.sessions.revoke(first, foreign_id))
        other_id = next(item["id"] for item in own if not item["current"])
        self.assertTrue(self.sessions.revoke(first, other_id))
        self.assertIsNone(self.sessions.authenticate(second))
        self.assertIsNotNone(self.sessions.authenticate(foreign))

    def test_per_client_and_global_rate_limits_prune(self):
        for _ in range(15):
            self.start()
        with self.assertRaises(LoginError) as raised:
            self.start()
        self.assertEqual(raised.exception.status, 429)
        for index in range(15):
            self.sessions.start(pkce_challenge(VERIFIER), f"other-{index}")
        with self.assertRaises(LoginError):
            self.sessions.start(pkce_challenge(VERIFIER), "yet-another")
        self.now += 61
        self.assertIn("state", self.start())
        self.assertLess(len(self.sessions.attempts), 10)

    def test_ninth_session_replaces_only_own_oldest_session(self):
        self.provider.identity.return_value = {"id": 456, "login": "author-two"}
        foreign = self.login()["access_token"]
        self.provider.identity.return_value = {"id": 123, "login": "author-one"}
        own = []
        for _ in range(9):
            self.now += 1
            own.append(self.login()["access_token"])
        self.assertIsNone(self.sessions.authenticate(own[0]))
        self.assertIsNotNone(self.sessions.authenticate(own[1]))
        self.assertIsNotNone(self.sessions.authenticate(foreign))
        self.assertEqual(len(self.sessions.list_sessions(own[-1])), 8)

    def test_pending_session_and_concurrency_limits_are_bounded(self):
        with patch("security_lab.github_auth.MAX_PENDING", 1):
            self.start()
            with self.assertRaises(LoginError):
                self.start()
        self.now += LOGIN_SECONDS + 1
        with patch("security_lab.github_auth.MAX_SESSIONS", 1):
            self.login()
            with self.assertRaises(LoginError):
                self.login()
        started = self.start()
        for _ in range(4):
            self.sessions.exchange_slots.acquire()
        try:
            with self.assertRaises(LoginError) as raised:
                self.sessions.complete(CODE, started["state"], VERIFIER, "client-a")
            self.assertEqual(raised.exception.status, 429)
        finally:
            for _ in range(4):
                self.sessions.exchange_slots.release()

    def test_malformed_inputs_fail_closed(self):
        for value in (None, 42, "", "x" * 42, "=" * 43):
            with self.subTest(value=value), self.assertRaises(LoginError):
                self.sessions.start(value, "client-a")
        for code, state, verifier in ((None, "x" * 43, VERIFIER), (CODE, None, VERIFIER),
                                      (CODE, "x" * 43, None), (CODE, "x" * 43, "short")):
            with self.assertRaises(LoginError):
                self.sessions.complete(code, state, verifier, "client-a")
        self.assertIsNone(self.sessions.authenticate("bad"))


class HTTPLoginTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(self.enterContext(tempfile.TemporaryDirectory())) / "workspace"
        self.app = create_app(self.workspace, CASES, hosted_settings=hosted_settings())
        self.provider = Mock()
        self.provider.identity.return_value = {"id": 123, "login": "author-one"}
        self.app.state.github_sessions.identity_client = self.provider
        self.client = self.enterContext(TestClient(self.app, base_url=PUBLIC))
        self.origin = {"Origin": FRONTEND}

    def login(self):
        start = self.client.post("/api/auth/github/start", headers=self.origin,
                                 json={"code_challenge": pkce_challenge(VERIFIER)})
        self.assertEqual(start.status_code, 200, start.text)
        return self.client.post("/api/auth/github/complete", headers=self.origin,
                                json={"code": CODE, "state": start.json()["state"], "code_verifier": VERIFIER})

    def test_config_public_and_data_protected_with_optional_feature(self):
        self.assertEqual(self.client.get("/api/auth/config").json(),
                         {"github_enabled": True, "access_code_enabled": True})
        self.assertEqual(self.client.get("/api/health").status_code, 401)
        self.assertEqual(self.client.get("/api/auth/sessions").status_code, 401)
        fallback = {"Authorization": "Bearer " + ACCESS}
        self.assertEqual(self.client.get("/api/health", headers=fallback).json()["user"], None)
        app = create_app(self.workspace, CASES, hosted_settings=hosted_settings(False))
        with TestClient(app, base_url=PUBLIC) as client:
            self.assertEqual(client.get("/api/auth/config").json()["github_enabled"], False)
            self.assertEqual(client.post("/api/auth/github/start", json={}, headers=self.origin).status_code, 401)
            csrf = client.get("/api/health", headers=fallback).json()["csrf_token"]
            self.assertEqual(client.post("/api/auth/logout", headers={**fallback, "X-Lab-Token": csrf}).json(), {"revoked": False})

    def test_browser_binding_origin_json_and_body_limit(self):
        for headers in ({}, {"Origin": "https://evil.test"}, {"Origin": PUBLIC},
                        [("Origin", FRONTEND), ("Origin", FRONTEND)]):
            response = self.client.post("/api/auth/github/start", headers=headers,
                                        json={"code_challenge": pkce_challenge(VERIFIER)})
            self.assertEqual(response.status_code, 403)
        response = self.client.post("/api/auth/github/start", headers=self.origin,
                                    data={"code_challenge": pkce_challenge(VERIFIER)})
        self.assertEqual(response.status_code, 403)
        oversized = self.client.post("/api/auth/github/start", headers=self.origin, json={"x": "x" * 4096})
        self.assertEqual(oversized.status_code, 413)
        self.provider.identity.assert_not_called()

    def test_malformed_payloads_never_echo_credentials(self):
        for payload in ({"code": "secret", "state": "secret", "code_verifier": "secret", "extra": True},
                        ["secret"], {"code": None, "state": 123, "code_verifier": False}):
            response = self.client.post("/api/auth/github/complete", headers=self.origin, json=payload)
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("secret", response.text)
        response = self.client.post("/api/auth/github/complete", headers={**self.origin, "Content-Type": "application/json"},
                                    content=b"not-json-secret")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("not-json-secret", response.text)
        self.provider.identity.assert_not_called()

    def test_excessive_json_nesting_is_sanitized_without_provider_calls(self):
        headers = {**self.origin, "Content-Type": "application/json"}
        response = self.client.post("/api/auth/github/complete", headers=headers,
                                    content="[" * 1500 + "0" + "]" * 1500)
        self.assertEqual(response.status_code, 400)
        # Parser depth limits differ across supported Python/platform builds.
        # Exercise the error boundary explicitly where this small body parses.
        with patch("security_lab.auth_routes.Request.json", side_effect=RecursionError("private-code")):
            response = self.client.post("/api/auth/github/complete", headers=headers, content="{}")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("private-code", response.text)
        self.provider.identity.assert_not_called()

    def test_login_csrf_download_session_revoke_logout_and_fallback(self):
        login = self.login()
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(login.headers["cache-control"], "no-store")
        self.assertEqual(login.headers["access-control-allow-origin"], FRONTEND)
        token = login.json()["access_token"]
        headers = {**self.origin, "Authorization": "Bearer " + token}
        health = self.client.get("/api/health", headers=headers).json()
        self.assertEqual(health["user"]["login"], "author-one")
        self.assertEqual(self.client.get("/api/cases/DEV-G1-01/articles/clean/pdf", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 403)
        mutations = {**headers, "X-Lab-Token": health["csrf_token"]}
        sessions = self.client.get("/api/auth/sessions", headers=headers).json()["sessions"]
        self.assertEqual(len(sessions), 1)
        foreign = self.client.delete("/api/auth/sessions/" + "a" * 32, headers=mutations)
        self.assertEqual(foreign.status_code, 404)
        self.assertEqual(self.client.delete("/api/auth/sessions/not-an-id", headers=mutations).status_code, 404)
        self.assertEqual(self.client.post("/api/auth/logout", headers=mutations).json(), {"revoked": True})
        self.assertEqual(self.client.get("/api/cases", headers=headers).status_code, 401)
        self.assertEqual(self.client.get("/api/cases", headers={"Authorization": "Bearer " + ACCESS}).status_code, 200)

    def test_current_session_can_be_revoked_and_preflight_remains_strict(self):
        token = self.login().json()["access_token"]
        headers = {**self.origin, "Authorization": "Bearer " + token}
        health = self.client.get("/api/health", headers=headers).json()
        sessions = self.client.get("/api/auth/sessions", headers=headers).json()["sessions"]
        response = self.client.delete("/api/auth/sessions/" + sessions[0]["id"],
                                      headers={**headers, "X-Lab-Token": health["csrf_token"]})
        self.assertEqual(response.json(), {"revoked": True})
        self.assertEqual(self.client.get("/api/health", headers=headers).status_code, 401)
        preflight = self.client.options("/api/auth/github/start", headers={**self.origin,
            "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        self.assertEqual(preflight.status_code, 204)

    def test_authentication_error_statuses_are_in_generated_api_contract(self):
        paths = self.app.openapi()["paths"]
        expected = {
            ("/api/auth/github/start", "post"): {"400", "403", "413", "429"},
            ("/api/auth/github/complete", "post"): {"400", "401", "403", "413", "429", "502"},
            ("/api/auth/sessions/{session_id}", "delete"): {"401", "403", "404"},
            ("/api/auth/logout", "post"): {"401", "403"},
        }
        for (path, method), statuses in expected.items():
            with self.subTest(path=path):
                self.assertLessEqual(statuses, set(paths[path][method]["responses"]))


class GitHubConfigurationTests(unittest.TestCase):
    def test_optional_and_partial_config(self):
        self.assertIsNone(GitHubSettings.from_environment({}))
        with self.assertRaises(ValueError):
            GitHubSettings.from_environment({"LAB_GITHUB_CLIENT_ID": "synthetic_client_id"})
        workspace = self.enterContext(tempfile.TemporaryDirectory())
        env = {"LAB_PUBLIC_ORIGIN": PUBLIC, "LAB_FRONTEND_ORIGIN": FRONTEND,
               "LAB_ACCESS_TOKEN_HASHES": hashlib.sha256(ACCESS.encode()).hexdigest(), "LAB_WORKSPACE": workspace,
               "LAB_GITHUB_CLIENT_ID": "synthetic_client_id", "LAB_GITHUB_CLIENT_SECRET": CLIENT_SECRET,
               "LAB_GITHUB_REDIRECT_URI": CALLBACK, "LAB_GITHUB_ALLOWED_USER_IDS": "123, 456"}
        self.assertEqual(configuration(env)[0].github.allowed_user_ids, (123, 456))
        for key, value in (("LAB_GITHUB_ALLOWED_USER_IDS", "author-one"), ("LAB_GITHUB_ALLOWED_USER_IDS", "123,123"),
                           ("LAB_GITHUB_CLIENT_SECRET", "short"), ("LAB_GITHUB_REDIRECT_URI", "https://evil.test/callback")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                configuration({**env, key: value})
        self.assertNotIn(CLIENT_SECRET, repr(oauth_settings()))

    def test_redirect_and_identifier_validation(self):
        for redirect in ("http://example.test/", CALLBACK + "?next=evil", CALLBACK + "#fragment",
                         "https://user:password@example.test/", FRONTEND + "/../evil/", FRONTEND + "//evil/"):
            with self.subTest(redirect=redirect), self.assertRaises(ValueError):
                GitHubSettings("synthetic_client_id", CLIENT_SECRET, redirect, (123,))
        for identifiers in ((), (123, 123), (True,), (0,), (-1,), (2**53,), [123]):
            with self.subTest(identifiers=identifiers), self.assertRaises(ValueError):
                GitHubSettings("synthetic_client_id", CLIENT_SECRET, CALLBACK, identifiers)
        with self.assertRaises(ValueError):
            GitHubSettings("bad client id", CLIENT_SECRET, CALLBACK, (123,))


class ProviderTransportTests(unittest.TestCase):
    def setUp(self):
        self.client = GitHubIdentityClient(oauth_settings())
        self.client.opener = Mock()

    def response(self, value):
        response = io.BytesIO(json.dumps(value).encode())
        return response

    def test_https_transport_requires_certificate_and_hostname_verification(self):
        client = GitHubIdentityClient(oauth_settings())
        handler = next(handler for handler in client.opener.handlers if isinstance(handler, HTTPSHandler))
        with patch.object(handler, "do_open") as connect:
            handler.https_open(Request("https://api.github.com/user"))
        context = connect.call_args.kwargs["context"]
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_only_fixed_https_endpoints_and_no_secret_in_identity_headers(self):
        github_token = "synthetic_provider_token_" + "a" * 30
        self.client.opener.open.side_effect = [self.response({"access_token": github_token, "token_type": "bearer"}),
                                               self.response({"id": 123, "login": "author-one"})]
        self.assertEqual(self.client.identity(CODE, VERIFIER)["id"], 123)
        calls = self.client.opener.open.call_args_list
        token_request = calls[0].args[0]
        self.assertEqual(token_request.full_url, "https://github.com/login/oauth/access_token")
        values = parse_qs(token_request.data.decode())
        self.assertEqual(values["client_secret"], [CLIENT_SECRET])
        self.assertEqual(values["code_verifier"], [VERIFIER])
        user_request = calls[1].args[0]
        self.assertEqual(user_request.full_url, "https://api.github.com/user")
        self.assertEqual(user_request.get_header("Authorization"), "Bearer " + github_token)
        self.assertNotIn(CLIENT_SECRET, repr(user_request.headers))
        self.assertEqual(calls[0].kwargs["timeout"], 10)

    def test_provider_errors_oversized_invalid_json_do_not_leak(self):
        for error in (URLError("provider-secret"), HTTPError("https://example.test/?secret", 302, "secret", {}, None),
                      OSError("private-key"), BadStatusLine("provider-secret")):
            self.client.opener.open.side_effect = error
            with self.subTest(error=type(error)), self.assertRaises(LoginError) as raised:
                self.client.identity(CODE, VERIFIER)
            self.assertEqual(raised.exception.status, 502)
            self.assertNotIn("secret", str(raised.exception))
        self.client.opener.open.side_effect = None
        for body in (b"x" * 65537, b"not-json-secret", b"[]", b"[" * 10000 + b"0" + b"]" * 10000):
            self.client.opener.open.return_value = io.BytesIO(body)
            with self.assertRaises(LoginError):
                self.client.identity(CODE, VERIFIER)
        self.client.opener.open.return_value = self.response({"error": "bad_verification_code"})
        with self.assertRaises(LoginError) as raised:
            self.client.identity(CODE, VERIFIER)
        self.assertEqual(raised.exception.status, 401)
        self.client.opener.open.return_value = self.response({"access_token": "a" * 30, "token_type": None})
        with self.assertRaises(LoginError):
            self.client.identity(CODE, VERIFIER)
