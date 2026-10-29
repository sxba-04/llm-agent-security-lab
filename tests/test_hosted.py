"""Hosted access boundaries and real mock/PDF/archive flows, without providers."""
from __future__ import annotations

import asyncio
import hashlib
from io import BytesIO
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from pypdf import PdfReader
    from security_lab.hosted import HostedAccessMiddleware, HostedSettings
    from security_lab.hosted_cli import configuration, main
    from security_lab.server import create_app, MAX_REQUEST_BYTES
except ImportError:
    TestClient = None


CASES = Path(__file__).resolve().parents[1] / "cases" / "dev"
PUBLIC = "https://lab-api.example.test"
FRONTEND = "https://sxba-04.github.io"
# Deliberately synthetic test credentials. Production must generate fresh values.
ACCESS_A = "synthetic_operator_a_" + "a" * 43
ACCESS_B = "synthetic_operator_b_" + "b" * 43


def fingerprint(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def settings():
    return HostedSettings(PUBLIC, FRONTEND, (fingerprint(ACCESS_A), fingerprint(ACCESS_B)))


@unittest.skipUnless(TestClient, "Install the web and dev extras for hosted tests")
class HostedTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(tempfile.TemporaryDirectory())
        self.workspace = Path(temporary) / "workspace"
        self.app = create_app(self.workspace, CASES, hosted_settings=settings())
        self.client = self.enterContext(TestClient(self.app, base_url=PUBLIC))
        self.headers = {"Authorization": "Bearer " + ACCESS_A, "Origin": FRONTEND}
        self.mutations = {**self.headers, "X-Lab-Token": self.client.get("/api/health", headers=self.headers).json()["csrf_token"]}

    def test_only_minimal_liveness_is_public(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["cache-control"], "no-store")
        for path in ("/api/health", "/api/cases", "/api/documents", "/api/campaigns", "/api/reviews",
                     "/api/cases/DEV-G1-01/articles/clean/pdf", "/api/campaigns/x/archive", "/healthz/"):
            with self.subTest(path=path):
                response = self.client.get(path, headers={"Origin": FRONTEND})
                self.assertEqual(response.status_code, 401)
                self.assertNotIn("csrf_token", response.text)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
                self.assertEqual(response.headers["access-control-allow-origin"], FRONTEND)
                self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.client.post("/healthz").status_code, 401)

    def test_authenticated_health_reports_configured_storage_mode(self):
        self.assertEqual(self.client.get("/api/health", headers=self.headers).json()["storage_mode"], "persistent")
        ephemeral = HostedSettings(PUBLIC, FRONTEND, (fingerprint(ACCESS_A),), storage_mode="ephemeral")
        with TestClient(create_app(self.workspace, CASES, hosted_settings=ephemeral), base_url=PUBLIC) as client:
            response = client.get("/api/health", headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["storage_mode"], "ephemeral")
            self.assertEqual(response.json()["mode"], "mock")
            self.assertEqual(client.get("/healthz").json(), {"status": "ok"})
            self.assertEqual(client.get("/api/health").status_code, 401)
        with TestClient(create_app(self.workspace, CASES), base_url="http://127.0.0.1") as client:
            self.assertEqual(client.get("/api/health").json()["storage_mode"], "local")

    def test_two_operator_tokens_and_invalid_credentials(self):
        for token in (ACCESS_A, ACCESS_B):
            response = self.client.get("/api/cases", headers={"Authorization": "Bearer " + token})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()["cases"]), 12)
        for authorization in ("", "Basic " + ACCESS_A, "Bearer short", "Bearer " + "x" * 43,
                              "Bearer " + ACCESS_A + " ", "Bearer " + "x" * 1024):
            with self.subTest(authorization=authorization[:15]):
                response = self.client.get("/api/health", headers={"Authorization": authorization})
                self.assertEqual(response.status_code, 401)
                self.assertNotIn(authorization if authorization else ACCESS_A, response.text)
        response = self.client.get("/api/health", headers=[("Authorization", "Bearer " + ACCESS_A),
                                                           ("Authorization", "Bearer " + ACCESS_B)])
        self.assertEqual(response.status_code, 401)

    def test_host_origin_and_forwarded_headers_do_not_grant_access(self):
        for headers in ({"Host": "evil.example"}, {"Host": "lab-api.example.test.evil.example"},
                        {"Origin": "null"}, {"Origin": "https://evil.example"},
                        {"Origin": FRONTEND + "/llm-agent-security-lab/"}):
            with self.subTest(headers=headers):
                response = self.client.get("/api/cases", headers={**self.headers, **headers})
                self.assertEqual(response.status_code, 403)
                if headers.get("Origin"):
                    self.assertNotIn("access-control-allow-origin", response.headers)
        response = self.client.get("/api/cases", headers={**self.headers, "Host": "evil.example",
                                   "X-Forwarded-Host": "lab-api.example.test", "X-Forwarded-Proto": "https"})
        self.assertEqual(response.status_code, 403)
        response = self.client.get("/api/cases", headers={"Authorization": "Bearer " + ACCESS_A,
                                                         "Sec-Fetch-Site": "cross-site"})
        self.assertEqual(response.status_code, 403)
        # Cross-site is expected for the configured Pages origin, not a bypass.
        response = self.client.get("/api/cases", headers={**self.headers, "Sec-Fetch-Site": "cross-site"})
        self.assertEqual(response.status_code, 200)

    def test_preflight_is_exact_and_does_not_reveal_data(self):
        headers = {"Origin": FRONTEND, "Access-Control-Request-Method": "POST",
                   "Access-Control-Request-Headers": "Authorization, X-Lab-Token, Content-Type"}
        response = self.client.options("/api/campaigns", headers=headers)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(response.headers["access-control-allow-origin"], FRONTEND)
        self.assertNotIn("access-control-allow-credentials", response.headers)
        for extra in ({"Origin": "https://evil.example"}, {"Access-Control-Request-Method": "TRACE"},
                      {"Access-Control-Request-Headers": "Authorization, X-Unexpected"}):
            self.assertEqual(self.client.options("/api/campaigns", headers={**headers, **extra}).status_code, 403)
        self.assertEqual(self.client.options("/api/campaigns").status_code, 403)

    def test_proxy_http_transport_does_not_redirect_tokens_to_http(self):
        # Render terminates TLS before Uvicorn. The app must not emit a slash
        # redirect constructed from the proxy's internal HTTP scheme.
        with TestClient(self.app, base_url="http://lab-api.example.test", follow_redirects=False) as client:
            response = client.get("/api/cases/", headers=self.headers)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn("location", response.headers)

    def test_mutations_require_both_tokens_and_keep_body_limits(self):
        body = {"case_ids": ["DEV-G1-01"], "variants": ["B"], "sources": ["clean"], "seed": 42}
        for headers, status in (({}, 401), (self.headers, 403),
                                ({**self.headers, "X-Lab-Token": "wrong"}, 403),
                                ({"X-Lab-Token": self.mutations["X-Lab-Token"]}, 401)):
            self.assertEqual(self.client.post("/api/campaigns", json=body, headers=headers).status_code, status)
        self.assertEqual(self.client.get("/api/campaigns", headers=self.headers).json()["campaigns"], [])
        for length in ("-1", "no", str(MAX_REQUEST_BYTES + 1)):
            self.assertEqual(self.client.post("/api/campaigns", content=b"{}",
                             headers={**self.mutations, "Content-Length": length}).status_code, 413)
        streamed = self.client.post("/api/campaigns", content=iter([b"x" * (MAX_REQUEST_BYTES + 1)]),
                                    headers={**self.mutations, "Content-Type": "application/json"})
        self.assertEqual(streamed.status_code, 413)
        self.assertEqual(streamed.headers["access-control-allow-origin"], FRONTEND)
        # Provider selection remains unavailable, even to authenticated operators.
        self.assertEqual(self.client.post("/api/campaigns", json={**body, "provider": "openai"},
                                         headers=self.mutations).status_code, 422)

    def test_pdf_import_campaign_archive_and_restart_preserve_evidence(self):
        response = self.client.get("/api/cases/DEV-G1-01/articles/clean/pdf", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertEqual(response.headers["access-control-expose-headers"], "Content-Disposition")
        self.assertTrue(PdfReader(BytesIO(response.content)).pages[0].extract_text())
        imported = self.client.post("/api/documents", files={"file": ("sample.pdf", response.content, "application/pdf")},
                                    headers=self.mutations)
        self.assertEqual(imported.status_code, 201, imported.text)
        document = imported.json()
        confirmed = self.client.post(f"/api/documents/{document['document_id']}/confirm",
                                     json={"text_sha256": document["text_sha256"]}, headers=self.mutations)
        self.assertEqual(confirmed.status_code, 200)
        body = {"case_ids": ["DEV-G1-01"], "variants": ["B", "P"], "sources": ["clean"], "seed": 42,
                "document_overrides": [{"case_id": "DEV-G1-01", "source": "clean", "document_id": document["document_id"]}]}
        started = self.client.post("/api/campaigns", json=body, headers=self.mutations)
        self.assertEqual(started.status_code, 202, started.text)
        identifier = started.json()["campaign_id"]
        deadline = time.monotonic() + 10
        while self.client.get("/api/health", headers=self.headers).json()["running"]:
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.01)
        archive = self.client.get(f"/api/campaigns/{identifier}/archive", headers=self.headers)
        self.assertEqual(archive.status_code, 200, archive.text[:200] if archive.status_code != 200 else "")
        self.assertTrue(archive.content.startswith(b"PK"))
        # A new process-equivalent application keeps files and rotates its CSRF
        # token; access-token revocation takes effect on the new instance.
        replacement = create_app(self.workspace, CASES, hosted_settings=HostedSettings(PUBLIC, FRONTEND, (fingerprint(ACCESS_B),)))
        with TestClient(replacement, base_url=PUBLIC) as client:
            self.assertEqual(client.get("/api/campaigns", headers=self.headers).status_code, 401)
            headers = {"Authorization": "Bearer " + ACCESS_B, "Origin": FRONTEND}
            detail = client.get(f"/api/campaigns/{identifier}", headers=headers)
            self.assertEqual(detail.status_code, 200)
            self.assertEqual(detail.json()["manifest"]["state"], "completed")
            self.assertNotEqual(client.get("/api/health", headers=headers).json()["csrf_token"], self.mutations["X-Lab-Token"])
            self.assertEqual(len(client.get("/api/documents", headers=headers).json()["documents"]), 1)

    def test_streamed_body_cannot_bypass_declared_length(self):
        async def app(scope, receive, send):
            while (await receive()).get("more_body"):
                pass
            raise AssertionError("Oversized body reached application effects")

        middleware = HostedAccessMiddleware(app, settings(), "csrf", max_request_bytes=4)
        scope = {"type": "http", "method": "POST", "path": "/api/documents", "headers": [
            (b"host", b"lab-api.example.test"), (b"authorization", ("Bearer " + ACCESS_A).encode()),
            (b"x-lab-token", b"csrf"), (b"content-length", b"1"), (b"origin", FRONTEND.encode())]}
        messages = iter([{"type": "http.request", "body": b"123", "more_body": True},
                         {"type": "http.request", "body": b"45", "more_body": False}])
        sent = []
        async def receive():
            return next(messages)
        async def send(message):
            sent.append(message)
        asyncio.run(middleware(scope, receive, send))
        self.assertEqual(sent[0]["status"], 413)


@unittest.skipUnless(TestClient, "Install the web and dev extras for hosted tests")
class HostedConfigurationTests(unittest.TestCase):
    def test_invalid_origins_and_token_hashes_fail_closed(self):
        for origin in ("", "http://example.test", "https://example.test/path", "https://user@example.test",
                       "https://example.test?x=1", "https://*.example.test", " https://example.test", "https://example.test:99999"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                HostedSettings(origin, FRONTEND, (fingerprint(ACCESS_A),))
        for hashes in ((), ("short",), ("A" * 64,), (fingerprint(ACCESS_A), fingerprint(ACCESS_A)), [fingerprint(ACCESS_A)]):
            with self.subTest(hashes=hashes), self.assertRaises(ValueError):
                HostedSettings(PUBLIC, FRONTEND, hashes)

    def test_launcher_requires_explicit_workspace_and_safe_port(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = {"RENDER_EXTERNAL_URL": PUBLIC, "LAB_FRONTEND_ORIGIN": FRONTEND,
                   "LAB_ACCESS_TOKEN_HASHES": fingerprint(ACCESS_A), "LAB_WORKSPACE": temporary}
            configured, workspace, port = configuration(env)
            self.assertEqual(configured.public_origin, PUBLIC)
            self.assertEqual(workspace, Path(temporary))
            self.assertEqual(port, 10000)
            self.assertEqual(configured.storage_mode, "persistent")
            configured, _, _ = configuration({**env, "LAB_STORAGE_MODE": "ephemeral"})
            self.assertEqual(configured.storage_mode, "ephemeral")
            for mode in ("", "temporary", "EPHEMERAL", " ephemeral"):
                with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "LAB_STORAGE_MODE"):
                    configuration({**env, "LAB_STORAGE_MODE": mode})
            for key in ("RENDER_EXTERNAL_URL", "LAB_FRONTEND_ORIGIN", "LAB_ACCESS_TOKEN_HASHES", "LAB_WORKSPACE"):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    configuration({name: value for name, value in env.items() if name != key})
            for value in ("", "runs", str(Path(temporary) / ".." / "escape"), str(Path(temporary).anchor)):
                with self.subTest(workspace=value), self.assertRaises(ValueError):
                    configuration({**env, "LAB_WORKSPACE": value})
            for port in ("wrong", "80", "65536"):
                with self.subTest(port=port), self.assertRaises(ValueError):
                    configuration({**env, "PORT": port})

    def test_hosted_launcher_runs_one_process_without_proxy_header_trust(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = {"LAB_PUBLIC_ORIGIN": PUBLIC, "LAB_FRONTEND_ORIGIN": FRONTEND,
                   "LAB_ACCESS_TOKEN_HASHES": fingerprint(ACCESS_A), "LAB_WORKSPACE": temporary, "PORT": "10001"}
            with patch.dict("os.environ", env, clear=True), patch("uvicorn.run") as run:
                self.assertEqual(main([]), 0)
            self.assertEqual(run.call_args.kwargs, {"host": "0.0.0.0", "port": 10001, "workers": 1,
                                                    "reload": False, "access_log": False, "proxy_headers": False})
