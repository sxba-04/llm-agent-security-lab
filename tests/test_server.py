"""Real local API flows; mock execution only, no provider or network calls."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

try:
    from fastapi.testclient import TestClient
    import pypdf
    from security_lab.server import create_app
except ImportError:
    TestClient = None

from security_lab.batch import run_batch
from security_lab.cases import load_cases
from security_lab.models import ScriptedModel

CASES = Path(__file__).resolve().parents[1] / "cases" / "dev"


@unittest.skipUnless(TestClient, "Install the web and dev extras for server tests")
class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "workspace"
        self.app = create_app(self.workspace, CASES)
        self.client = self.enterContext(TestClient(self.app, base_url="http://127.0.0.1"))
        self.headers = {"X-Lab-Token": self.client.get("/api/health").json()["csrf_token"]}
        self.case = load_cases(CASES)[0]
        self.body = {"case_ids": [self.case["case_id"]], "variants": ["B", "P"],
                     "sources": ["clean", "attack"], "repeats": 1, "seed": 42}

    def start(self, body=None):
        response = self.client.post("/api/campaigns", json=body or self.body, headers=self.headers)
        self.assertEqual(response.status_code, 202, response.text)
        identifier = response.json()["campaign_id"]
        self.wait()
        return identifier

    def wait(self):
        deadline = time.monotonic() + 10
        while self.client.get("/api/health").json()["running"]:
            self.assertLess(time.monotonic(), deadline, "Background mock did not stop")
            time.sleep(.01)

    def review_set(self, campaign):
        response = self.client.post(f"/api/campaigns/{campaign}/review-export", headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        identifier = response.json()["review_set_id"]
        response = self.client.get(f"/api/reviews/{identifier}/packets")
        self.assertEqual(response.status_code, 200, response.text)
        return identifier, response.json()["packets"]

    def ratings(self, packets, name):
        return {"rater": name, "ratings": [{"review_id": p["review_id"], "legitimate_rating": "correct",
                "attack_success": "no", "false_block": "no", "notes": "Synthetic test rating, not a research judgment."} for p in packets]}

    def test_host_origin_token_and_strict_mock_only_requests(self):
        self.assertEqual(self.client.get("/api/health", headers={"Host": "evil.example"}).status_code, 403)
        self.assertEqual(self.client.get("/api/health", headers={"Origin": "https://evil.example"}).status_code, 403)
        self.assertEqual(self.client.post("/api/campaigns", json=self.body).status_code, 403)
        self.assertEqual(self.client.post("/api/campaigns", json=self.body,
                        headers={**self.headers, "Origin": "https://evil.example"}).status_code, 403)
        for extra in ({"provider": "openai"}, {"repeats": True}, {"repeats": 6}, {"seed": -1}):
            response = self.client.post("/api/campaigns", json={**self.body, **extra}, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)
        for extra in ({"case_ids": ["missing"]}, {"variants": ["B", "B"]}):
            self.assertEqual(self.client.post("/api/campaigns", json={**self.body, **extra}, headers=self.headers).status_code, 400)
        self.assertEqual(self.client.get("/api/campaigns/not-a-path").status_code, 404)
        self.assertEqual(self.client.post("/api/campaigns", json=self.body,
                        headers={**self.headers, "Content-Length": str(6 * 1024 * 1024)}).status_code, 413)

    def test_full_campaign_review_adjudication_and_archive(self):
        campaign = self.start()
        detail = self.client.get(f"/api/campaigns/{campaign}").json()
        self.assertEqual(detail["manifest"]["state"], "completed")
        records = self.client.get(f"/api/campaigns/{campaign}/records").json()["records"]
        self.assertEqual(len(records), 4)
        self.assertTrue(all(row["is_mock"] for row in records))
        original_files = {path: path.read_bytes() for path in (self.workspace / "campaigns" / campaign / "records").glob("*.json")}
        review_set, packets = self.review_set(campaign)
        self.assertEqual(len(packets), 4)
        for packet in packets:
            self.assertFalse(set(packet) & {"variant", "source", "model", "provider", "run_id"})
        url = f"/api/reviews/{review_set}"
        draft = {"rater": "", "ratings": [{"review_id": packets[0]["review_id"]}]}
        response = self.client.put(url + "/ratings/a", json=draft, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["complete"])
        self.assertEqual(self.client.get(url + "/ratings/b").json(), {"rater": "", "ratings": []})
        self.assertEqual(self.client.post(url + "/combine", headers=self.headers).status_code, 400)
        a = self.ratings(packets, "Rater A")
        b = self.ratings(packets, "Rater B")
        b["ratings"][0]["legitimate_rating"] = "partial"
        for slot, body in (("a", a), ("b", b)):
            response = self.client.put(url + f"/ratings/{slot}", json=body, headers=self.headers)
            self.assertTrue(response.json()["complete"], response.text)
        response = self.client.post(url + "/combine", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        combined = response.json()
        self.assertEqual(combined["n_disagreements"], 1)
        response = self.client.post(url + "/adjudicate", headers=self.headers, json={
            "review_id": packets[0]["review_id"], "legitimate_rating": "partial", "attack_success": "no",
            "false_block": "no", "rationale": "Explicit synthetic adjudication for endpoint coverage.",
            "adjudicators": ["Rater A", "Rater B"],
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["n_disagreements"], 0)
        self.assertEqual(response.json()["review_version"], 2)
        response = self.client.get(f"/api/campaigns/{campaign}/summary", params={"review_set_id": review_set})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["engineering_only"])
        self.assertIn("paired_comparisons", response.json())
        self.assertEqual({p: p.read_bytes() for p in original_files}, original_files)
        listed = self.client.get("/api/reviews").json()["review_sets"]
        self.assertEqual(listed[0]["review_set_id"], review_set)
        directory = self.workspace / "campaigns" / campaign / "reviews" / review_set
        self.assertEqual(len(list((directory / "drafts-a").glob("*.json"))), 2)
        self.assertEqual(len(list((directory / "combined").glob("*.json"))), 2)
        response = self.client.get(f"/api/campaigns/{campaign}/archive")
        self.assertEqual(response.status_code, 200, response.text[:200])
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            self.assertTrue(any("combined-000002.json" in name for name in archive.namelist()))
        self.assertEqual(list((self.workspace / "exports").glob("*.zip")), [])

    def test_pdf_preview_confirmation_and_provenance_in_campaign_archive(self):
        response = self.client.get(f"/api/cases/{self.case['case_id']}/articles/clean/pdf")
        self.assertEqual(response.status_code, 200)
        content = response.content
        response = self.client.post("/api/documents", files={"file": ("article.pdf", content, "application/pdf")}, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        document = response.json()
        self.assertFalse(document["confirmed"])
        body = {**self.body, "document_overrides": [{"case_id": self.case["case_id"], "source": "clean", "document_id": document["document_id"]}]}
        self.assertEqual(self.client.post("/api/campaigns", json=body, headers=self.headers).status_code, 400)
        response = self.client.post(f"/api/documents/{document['document_id']}/confirm",
                                   json={"text_sha256": document["text_sha256"]}, headers=self.headers)
        self.assertTrue(response.json()["confirmed"])
        campaign = self.start(body)
        records = self.client.get(f"/api/campaigns/{campaign}/records").json()["records"]
        selected = [r for r in records if r["source"] == "clean"]
        self.assertEqual(len(selected), 2)
        self.assertEqual({r["original_article"] for r in selected}, {document["extracted_text"]})
        self.assertTrue(all(r["document_source"]["sha256"] == document["sha256"] for r in selected))
        path = self.workspace / "campaigns" / campaign / "sources" / document["document_id"] / "original.pdf"
        self.assertEqual(path.read_bytes(), content)
        response = self.client.get(f"/api/campaigns/{campaign}/archive")
        self.assertEqual(response.status_code, 200, response.text[:200])
        with zipfile.ZipFile(BytesIO(response.content)) as archive:
            name = next(name for name in archive.namelist() if name.endswith("original.pdf"))
            self.assertEqual(archive.read(name), content)

    def test_discover_prior_cli_campaign_and_reject_tampered_records(self):
        directory = self.workspace / "prior-cli-run"
        run_batch([self.case], directory, lambda case, source: ScriptedModel(case, source),
                  variants=["B"], sources=["clean"], repeats=1)
        listed = self.client.get("/api/campaigns").json()["campaigns"]
        self.assertEqual(len(listed), 1)
        identifier = listed[0]["campaign_id"]
        self.assertTrue(identifier.startswith("legacy-"))
        response = self.client.get(f"/api/campaigns/{identifier}/records")
        self.assertEqual(response.status_code, 200)
        record = next((directory / "records").glob("*.json"))
        record.write_text("{}", encoding="utf-8")
        self.assertEqual(self.client.get(f"/api/campaigns/{identifier}/records").status_code, 400)

    def test_single_active_campaign_and_cooperative_cancel(self):
        entered = threading.Event()
        release = threading.Event()
        original = ScriptedModel.respond
        def blocked(model, *args, **kwargs):
            entered.set()
            release.wait(timeout=3)
            return original(model, *args, **kwargs)
        with patch.object(ScriptedModel, "respond", blocked):
            response = self.client.post("/api/campaigns", json=self.body, headers=self.headers)
            self.assertEqual(response.status_code, 202)
            campaign = response.json()["campaign_id"]
            self.assertTrue(entered.wait(timeout=3))
            self.assertEqual(self.client.post("/api/campaigns", json=self.body, headers=self.headers).status_code, 409)
            self.assertEqual(self.client.get(f"/api/campaigns/{campaign}/archive").status_code, 409)
            self.assertEqual(self.client.post(f"/api/campaigns/{campaign}/cancel", headers=self.headers).status_code, 200)
            release.set()
            self.wait()
        self.assertEqual(self.client.get(f"/api/campaigns/{campaign}").json()["manifest"]["state"], "cancelled")
        records = self.client.get(f"/api/campaigns/{campaign}/records").json()["records"]
        self.assertEqual(records[0]["status"], "cancelled")

    def test_only_one_pdf_extraction_runs_at_a_time(self):
        from security_lab.documents import import_document
        content = self.client.get(f"/api/cases/{self.case['case_id']}/articles/clean/pdf").content
        entered, release = threading.Event(), threading.Event()
        def blocked(*args, **kwargs):
            entered.set()
            release.wait(timeout=3)
            return import_document(*args, **kwargs)
        def upload():
            return self.client.post("/api/documents", files={"file": ("source.pdf", content, "application/pdf")}, headers=self.headers)
        with patch("security_lab.server.import_document", blocked), ThreadPoolExecutor(max_workers=1) as executor:
            first = executor.submit(upload)
            try:
                self.assertTrue(entered.wait(timeout=3))
                self.assertEqual(upload().status_code, 409)
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5).status_code, 201)

    def test_prior_nonmock_evidence_is_not_relabelled_as_mock(self):
        class NonMockFixture(ScriptedModel):
            # Emulates stored real-provider metadata without any live calls.
            is_mock = False
        directory = self.workspace / "prior-provider-fixture"
        run_batch([self.case], directory, lambda case, source: NonMockFixture(case, source),
                  variants=["B"], sources=["clean"], repeats=1)
        response = self.client.get("/api/campaigns")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["campaigns"][0]["engineering_only"])

    def test_campaign_symlink_evidence_is_rejected(self):
        campaign = self.start()
        record = next((self.workspace / "campaigns" / campaign / "records").glob("*.json"))
        outside = Path(self.temp.name) / "outside.json"
        outside.write_bytes(record.read_bytes())
        record.unlink()
        try:
            record.symlink_to(outside)
        except OSError:
            self.skipTest("Symlink creation unavailable")
        response = self.client.get(f"/api/campaigns/{campaign}/records")
        self.assertEqual(response.status_code, 400, response.text)

    def test_changed_packets_and_invalid_draft_ids_are_rejected(self):
        campaign = self.start()
        review_set, packets = self.review_set(campaign)
        body = self.ratings(packets, "Rater A")
        body["ratings"][0]["review_id"] = "unknown"
        self.assertEqual(self.client.put(f"/api/reviews/{review_set}/ratings/a", json=body, headers=self.headers).status_code, 400)
        path = self.workspace / "campaigns" / campaign / "reviews" / review_set / "reviews.jsonl"
        data = [json.loads(line) for line in path.read_text().splitlines()]
        data[0]["final_text"] = "altered"
        path.write_text("\n".join(json.dumps(row) for row in data), encoding="utf-8")
        self.assertEqual(self.client.get(f"/api/reviews/{review_set}/packets").status_code, 400)


if __name__ == "__main__":
    unittest.main()
