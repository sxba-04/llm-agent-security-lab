"""The hosted operator boundary and fixed clean pilot use simulated provider responses."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from test_hosted import ACCESS_A, CASES, FRONTEND, PUBLIC, TestClient
from test_luna_pilot import reply

if TestClient:
    from security_lab.hosted_cli import configuration
    from security_lab.server import create_app
    from test_hosted import settings

PILOT = "/api/pilot/luna"
KEY = "offline-only-hosted-pilot"


@unittest.skipUnless(TestClient, "Install the web and dev extras")
class HostedPilotTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(self.enterContext(tempfile.TemporaryDirectory())) / "lab"
        self.enterContext(patch.dict("os.environ", OPENAI_API_KEY=KEY))
        self.auth = {"Authorization": "Bearer " + ACCESS_A, "Origin": FRONTEND}
        self.client, self.headers = self.connection()

    def connection(self, **options):
        config = replace(settings(), **{"luna_pilot_enabled": True, **options})
        app = create_app(self.workspace, CASES, hosted_settings=config)
        client = self.enterContext(TestClient(app, base_url=PUBLIC))
        health = client.get("/api/health", headers=self.auth).json()
        self.assertIn("luna_pilot_v1", health["capabilities"])
        return client, {**self.auth, "X-Lab-Token": health["csrf_token"]}

    def status(self):
        return self.client.get(PILOT, headers=self.auth).json()

    def test_only_authenticated_operators_can_start_a_fixed_bodyless_request(self):
        self.assertEqual(self.client.get(PILOT).status_code, 401)
        zero_requests = self.enterContext(patch("security_lab.providers._http_transport"))
        for target, headers, data, status in [
            (PILOT, {}, {}, 401),
            (PILOT, self.auth, {}, 403),
            (PILOT, {**self.headers, "Origin": "https://elsewhere.example"}, {}, 403),
            (PILOT, {k: v for k, v in self.headers.items() if k != "Origin"}, {}, 403),
            (PILOT + "?source=other", self.headers, {}, 400),
            (PILOT, self.headers, {"json": {}}, 400),
            (PILOT, self.headers, {"content": iter([b"extra"])}, 400),
        ]:
            with self.subTest(target=target, status=status):
                self.assertEqual(self.client.post(target, headers=headers, **data).status_code, status)
        self.assertEqual(self.status()["state"], "ready")
        self.assertFalse((self.workspace / "studies").exists())
        zero_requests.assert_not_called()

    def test_default_off_missing_key_ephemeral_and_local_launcher(self):
        for configuration in ({"luna_pilot_enabled": False}, {"storage_mode": "ephemeral"}):
            client, headers = self.connection(**configuration)
            self.assertEqual(client.get(PILOT, headers=headers).json()["state"], "disabled")
            self.assertEqual(client.post(PILOT, headers=headers).status_code, 503)
        with patch.dict("os.environ", OPENAI_API_KEY=""):
            self.assertEqual(self.status()["state"], "disabled")
            self.assertEqual(self.client.post(PILOT, headers=self.headers).status_code, 503)
        with TestClient(create_app(self.workspace, CASES), base_url="http://localhost") as local:
            self.assertNotIn("luna_pilot_v1", local.get("/api/health").json()["capabilities"])
            self.assertEqual(local.get(PILOT).status_code, 404)

    def test_real_runner_reports_aggregate_and_survives_a_restart_without_replay(self):
        model = "gpt-6-luna-2026-11-01"
        transport = Mock(side_effect=[reply(model=model, ticket_id="A17"), reply(model=model)])
        with patch("security_lab.providers._http_transport", transport):
            response = self.client.post(PILOT, headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"state": "completed", "result": {
                "status": "completed", "technical_acceptance": True, "final_text": "Synthetische Testantwort.",
                "models": [model], "input_tokens": 240, "output_tokens": 40,
                "estimated_cost_eur": "0.0000528", "model_calls": 2, "tool_calls": 1}})
            self.assertNotIn(KEY, response.text)
            self.assertNotIn("raw_response", response.text)
            replacement, headers = self.connection(luna_pilot_enabled=False)
            self.assertEqual(replacement.get(PILOT, headers=headers).json(), response.json())
            self.assertEqual(replacement.post(PILOT, headers=headers).status_code, 409)
            ledger = json.loads((self.workspace / "studies" / "budget.json").read_bytes())
            self.assertEqual([r["state"] for r in ledger["reservations"].values()], ["settled"] * 2)
            self.assertEqual(transport.call_count, 2)

    def test_uncertain_outcome_or_corrupt_evidence_never_becomes_ready(self):
        with patch("security_lab.providers._http_transport", side_effect=TimeoutError) as transport:
            response = self.client.post(PILOT, headers=self.headers).json()
            self.assertEqual(response["state"], "failed")
            self.assertIsNone(response["result"]["estimated_cost_eur"])
            self.assertIsNone(response["result"]["input_tokens"])
            self.assertIsNone(response["result"]["output_tokens"])
            output = self.workspace / "studies" / "luna-clean-first"
            (output / "result.json").write_text("{}", encoding="utf-8")
            self.assertEqual(self.status(), {"state": "failed", "result": None})
            self.assertEqual(self.client.post(PILOT, headers=self.headers).status_code, 409)
            transport.assert_called_once()

    def test_status_concurrent_start_and_backup_do_not_duplicate_work(self):
        sent, finish = threading.Event(), threading.Event()

        def transport(*_):
            sent.set()
            if not finish.wait(10):
                raise TimeoutError
            return reply()

        with patch("security_lab.providers._http_transport", side_effect=transport) as model, ThreadPoolExecutor() as pool:
            first = pool.submit(self.client.post, PILOT, headers=self.headers)
            try:
                self.assertTrue(sent.wait(10))
                self.assertEqual(self.status(), {"state": "running", "result": None})
                self.assertEqual(self.client.post(PILOT, headers=self.headers).status_code, 409)
                self.assertEqual(self.client.get("/api/workspace/backup", headers=self.auth).status_code, 409)
            finally:
                finish.set()
            self.assertEqual(first.result(timeout=10).json()["state"], "failed")
            model.assert_called_once()

    def test_only_explicit_configuration_enables_pilot(self):
        env = {"LAB_PUBLIC_ORIGIN": PUBLIC, "LAB_FRONTEND_ORIGIN": FRONTEND,
               "LAB_ACCESS_TOKEN_HASHES": settings().token_hashes[0], "LAB_WORKSPACE": str(self.workspace)}
        self.assertFalse(configuration(env)[0].luna_pilot_enabled)
        self.assertTrue(configuration({**env, "LAB_LUNA_PILOT_ENABLED": "true"})[0].luna_pilot_enabled)
