"""Offline HTTP contracts for the hosted single-start clean baseline."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from security_lab.backup import export_workspace, restore_workspace_backup
from security_lab.budget import BudgetLedger
from security_lab.clean_b import build_plan
from test_hosted import ACCESS_A, ACCESS_B, CASES, FRONTEND, PUBLIC, TestClient
from test_luna_pilot import reply

if TestClient:
    from security_lab.hosted_cli import configuration
    from security_lab.server import create_app
    from test_hosted import settings


RUN = "/api/studies/clean-b/run"
PILOT = "/api/pilot/luna"
BACKUP = "/api/workspace/backup"
CLAIM = Path("studies/clean-b-v1.attempt.json")
LEDGER = Path("studies/budget.json")
KEY = "offline-only-clean-baseline"


@unittest.skipUnless(TestClient, "Install the web and dev extras")
class HostedCleanBTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.workspace = self.root / "lab"
        self.plan_hash = build_plan()["plan_sha256"]
        self.auth = {"Authorization": "Bearer " + ACCESS_A, "Origin": FRONTEND}
        self.enterContext(patch.dict("os.environ", OPENAI_API_KEY=KEY))
        self.transport = self.enterContext(patch("security_lab.providers._http_transport",
                                                 side_effect=AssertionError("Unexpected provider request")))

    def connection(self, workspace=None, **overrides):
        config = replace(settings(), **overrides)
        app = create_app(workspace or self.workspace, CASES, hosted_settings=config)
        client = self.enterContext(TestClient(app, base_url=PUBLIC))
        token = client.get("/api/health", headers=self.auth).json()["csrf_token"]
        return client, {**self.auth, "X-Lab-Token": token}

    def settled_ledger(self):
        ledger = BudgetLedger(self.workspace / LEDGER)
        previous = ledger.reserve("0.001", {"fixture": "prior settled request"})
        ledger.settle(previous, "0.0002")
        return previous

    def status(self, client):
        response = client.get(RUN, headers=self.auth)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn(KEY, response.text)
        return response.json()

    def await_terminal(self, client):
        deadline = time.monotonic() + 15
        while True:
            status = self.status(client)
            if status["state"] != "running":
                return status
            if time.monotonic() >= deadline:
                self.fail("Clean B worker stayed in running state")
            time.sleep(0.02)

    def test_approval_storage_key_and_shared_ledger_are_required_before_claim(self):
        approved = {"clean_b_approved_plan_sha256": self.plan_hash}
        client, headers = self.connection()
        self.assertEqual(self.status(client)["state"], "disabled")
        self.assertEqual(client.post(RUN, headers=headers).status_code, 503)
        self.assertFalse((self.workspace / "studies").exists())

        client, headers = self.connection(**approved)
        self.assertEqual(self.status(client)["state"], "unavailable")
        self.assertEqual(client.post(RUN, headers=headers).status_code, 503)
        self.assertFalse((self.workspace / CLAIM).exists())
        self.assertFalse((self.workspace / LEDGER).exists())
        self.settled_ledger()
        original = (self.workspace / LEDGER).read_bytes()
        for options, key in [({}, KEY), ({"clean_b_approved_plan_sha256": "0" * 64}, KEY),
                             ({**approved, "storage_mode": "ephemeral"}, KEY), (approved, "")]:
            with self.subTest(options=options, has_key=bool(key)), patch.dict("os.environ", OPENAI_API_KEY=key):
                client, headers = self.connection(**options)
                self.assertIn(self.status(client)["state"], {"disabled", "unavailable"})
                self.assertEqual(client.post(RUN, headers=headers).status_code, 503)
                self.assertEqual(list((self.workspace / "studies").iterdir()), [self.workspace / LEDGER])
                self.assertEqual((self.workspace / LEDGER).read_bytes(), original)

        client, headers = self.connection(**approved)
        ledger = BudgetLedger(self.workspace / LEDGER)
        ledger.reserve("0.01")
        original = ledger.path.read_bytes()
        self.assertEqual(client.post(RUN, headers=headers).status_code, 503)
        self.assertFalse((self.workspace / CLAIM).exists())
        self.assertEqual(ledger.path.read_bytes(), original)
        self.transport.assert_not_called()

    def test_http_boundary_rejects_start_overrides_and_unauthenticated_access(self):
        self.settled_ledger()
        original = (self.workspace / LEDGER).read_bytes()
        client, headers = self.connection(clean_b_approved_plan_sha256=self.plan_hash)
        self.assertEqual(client.get(RUN).status_code, 401)
        for target, sent, body, expected in [
            (RUN, {}, {}, 401),
            (RUN, self.auth, {}, 403),
            (RUN, {k: v for k, v in headers.items() if k != "Origin"}, {}, 403),
            (RUN, {**headers, "Origin": FRONTEND + ".elsewhere.example"}, {}, 403),
            (RUN + "?case=other", headers, {}, 400),
            (RUN, headers, {"json": {}}, 400),
            (RUN, headers, {"content": iter([b"extra"])}, 400),
        ]:
            with self.subTest(target=target, expected=expected):
                self.assertEqual(client.post(target, headers=sent, **body).status_code, expected)
        self.assertEqual(self.status(client)["state"], "ready")
        self.assertFalse((self.workspace / CLAIM).exists())
        self.assertEqual((self.workspace / LEDGER).read_bytes(), original)
        self.transport.assert_not_called()
        with TestClient(create_app(self.workspace, CASES), base_url="http://localhost") as local:
            self.assertEqual(local.get(RUN).status_code, 404)
            token = local.get("/api/health").json()["csrf_token"]
            self.assertEqual(local.post(RUN, headers={"X-Lab-Token": token}).status_code, 404)

    def test_accepted_start_is_already_claimed_and_excludes_other_operators_and_backup(self):
        previous = self.settled_ledger()
        client, headers = self.connection(clean_b_approved_plan_sha256=self.plan_hash, luna_pilot_enabled=True)
        second_auth = {"Authorization": "Bearer " + ACCESS_B, "Origin": FRONTEND}
        second_token = client.get("/api/health", headers=second_auth).json()["csrf_token"]
        second_headers = {**second_auth, "X-Lab-Token": second_token}
        received, finish = threading.Event(), threading.Event()

        def transport(*_):
            received.set()
            if not finish.wait(timeout=15):
                raise TimeoutError("Test did not release the simulated provider")
            return {**reply(), "service_tier": "default"}

        self.transport.side_effect = transport
        try:
            accepted = client.post(RUN, headers=headers)
            self.assertEqual(accepted.status_code, 202, accepted.text)
            original_claim = (self.workspace / CLAIM).read_bytes()
            self.assertTrue(received.wait(timeout=15))
            active = self.status(client)
            self.assertEqual((active["state"], active["planned_runs"], active["recorded_runs"]),
                             ("running", 12, 0))
            self.assertEqual(client.post(RUN, headers=second_headers).status_code, 409)
            self.assertEqual(client.post(PILOT, headers=second_headers).status_code, 409)
            self.assertEqual(client.get(BACKUP, headers=self.auth).status_code, 409)
        finally:
            finish.set()
        final = self.await_terminal(client)
        self.assertEqual((final["state"], final["planned_runs"], final["recorded_runs"]), ("completed", 12, 12))
        self.assertEqual(self.transport.call_count, 12)
        ledger = json.loads((self.workspace / LEDGER).read_bytes())["reservations"]
        self.assertEqual(len(ledger), 13)
        self.assertEqual(ledger[previous]["amount_eur"], "0.0002")
        self.assertFalse((self.workspace / "studies/luna-clean-first").exists())

        restarted, headers = self.connection(clean_b_approved_plan_sha256=self.plan_hash)
        self.assertEqual(self.status(restarted), final)
        self.assertEqual(restarted.post(RUN, headers=headers).status_code, 409)
        # Export with a clean local source checkout even when development has uncommitted changes.
        source = self.root / "source"
        subprocess.run(["git", "clone", "--quiet", "--local", str(CASES.parents[1]), str(source)],
                       check=True, capture_output=True)
        archive = self.root / "saved.zip"
        export_workspace(self.workspace, source, archive)
        restored = Path(restore_workspace_backup(archive, self.root / "restored")["workspace"])
        self.assertEqual((restored / CLAIM).read_bytes(), original_claim)
        restored_client, headers = self.connection(restored, clean_b_approved_plan_sha256=self.plan_hash)
        self.assertEqual(self.status(restored_client), final)
        self.assertEqual(restored_client.post(RUN, headers=headers).status_code, 409)
        self.assertEqual(self.transport.call_count, 12)

    def test_uncertain_transport_stops_once_with_original_reservation_and_no_restart(self):
        self.settled_ledger()
        client, headers = self.connection(clean_b_approved_plan_sha256=self.plan_hash)
        self.transport.side_effect = TimeoutError("Uncertain simulated transport")
        self.assertEqual(client.post(RUN, headers=headers).status_code, 202)
        final = self.await_terminal(client)
        self.assertEqual((final["state"], final["recorded_runs"]), ("stopped", 1))
        ledger = json.loads((self.workspace / LEDGER).read_bytes())["reservations"]
        self.assertEqual(sorted(entry["state"] for entry in ledger.values()), ["reserved", "settled"])
        restarted, headers = self.connection()
        self.assertEqual(self.status(restarted), final)
        self.assertEqual(restarted.post(RUN, headers=headers).status_code, 409)
        self.transport.assert_called_once()

    def test_worker_failure_after_claim_is_interrupted_and_cannot_be_replayed(self):
        self.settled_ledger()
        original = (self.workspace / LEDGER).read_bytes()
        client, headers = self.connection(clean_b_approved_plan_sha256=self.plan_hash)
        with patch("security_lab.clean_b_run.execute", side_effect=OSError("Synthetic disk failure")) as worker:
            self.assertEqual(client.post(RUN, headers=headers).status_code, 202)
            final = self.await_terminal(client)
            worker.assert_called_once()
        self.assertTrue((self.workspace / CLAIM).is_file())
        self.assertEqual((final["state"], final["recorded_runs"]), ("interrupted", 0))
        restarted, headers = self.connection(clean_b_approved_plan_sha256=self.plan_hash)
        self.assertEqual(self.status(restarted), final)
        self.assertEqual(restarted.post(RUN, headers=headers).status_code, 409)
        self.assertEqual((self.workspace / LEDGER).read_bytes(), original)
        self.transport.assert_not_called()

    def test_environment_defaults_to_no_approved_plan(self):
        env = {"LAB_PUBLIC_ORIGIN": PUBLIC, "LAB_FRONTEND_ORIGIN": FRONTEND,
               "LAB_ACCESS_TOKEN_HASHES": settings().token_hashes[0], "LAB_WORKSPACE": str(self.workspace)}
        self.assertIsNone(configuration(env)[0].clean_b_approved_plan_sha256)
        configured = configuration({**env, "LAB_CLEAN_B_APPROVED_PLAN_SHA256": self.plan_hash})[0]
        self.assertEqual(configured.clean_b_approved_plan_sha256, self.plan_hash)
