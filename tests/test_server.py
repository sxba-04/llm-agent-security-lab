"""Real local API flows; mock execution only, no provider or network calls."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
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
from security_lab.archives import import_campaign
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
        self.assertEqual(self.client.get(url + "/ratings/b").json(), {"rater": "", "ratings": [], "locked": False})
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

    def test_archived_reviews_follow_restored_campaign_without_changing_evidence(self):
        campaign = self.start({**self.body, "variants": ["B"], "sources": ["clean"]})
        review_set, packets = self.review_set(campaign)
        url = f"/api/reviews/{review_set}"
        for slot, name in (("a", "Rater A"), ("b", "Rater B")):
            response = self.client.put(url + f"/ratings/{slot}", headers=self.headers,
                                       json=self.ratings(packets, name))
            self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post(url + "/combine", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        original_combined = response.json()
        source = self.workspace / "campaigns" / campaign / "reviews" / review_set
        original_files = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
        response = self.client.get(f"/api/campaigns/{campaign}/archive")
        self.assertEqual(response.status_code, 200, response.text[:200])
        archive = Path(self.temp.name) / "reviewed.zip"
        archive.write_bytes(response.content)

        # A separate healthy set must remain available beside restored copies.
        other_campaign = self.start({**self.body, "variants": ["B"], "sources": ["clean"], "seed": 73})
        other_set, _ = self.review_set(other_campaign)
        for same_workspace in (False, True):
            with self.subTest(same_workspace=same_workspace):
                workspace = self.workspace if same_workspace else Path(self.temp.name) / "fresh-workspace"
                restored = workspace / "restored-copy"
                import_campaign(archive, restored)
                with TestClient(create_app(workspace, CASES), base_url="http://127.0.0.1") as client:
                    campaigns = client.get("/api/campaigns").json()["campaigns"]
                    current = next(row["campaign_id"] for row in campaigns if row["campaign_id"].startswith("legacy-"))
                    response = client.get("/api/reviews")
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(response.json()["damaged_review_sets"], [])
                    sets = response.json()["review_sets"]
                    copied = next(row for row in sets if row["campaign_id"] == current)
                    self.assertNotEqual(copied["review_set_id"], review_set)
                    self.assertRegex(copied["review_set_id"], r"^review-copy-[0-9a-f]{64}$")
                    self.assertEqual(copied["original_review_set_id"], review_set)
                    self.assertEqual(copied["original_campaign_id"], campaign)
                    copied_url = f'/api/reviews/{copied["review_set_id"]}'
                    self.assertEqual(client.get(copied_url + "/packets").json()["packets"], packets)
                    self.assertEqual(client.get(copied_url + "/combined").json(), original_combined)
                    response = client.get(f"/api/campaigns/{current}/summary",
                                          params={"review_set_id": copied["review_set_id"]})
                    self.assertEqual(response.status_code, 200, response.text)
                    if same_workspace:
                        self.assertEqual(len(sets), 3)
                        self.assertEqual(len({row["review_set_id"] for row in sets}), 3)
                        self.assertEqual(next(row for row in sets if row["campaign_id"] == campaign)["review_set_id"], review_set)
                        self.assertEqual(client.get(f"/api/reviews/{other_set}/packets").status_code, 200)
                        self.assertEqual(client.get(f"/api/campaigns/{campaign}/summary",
                                                    params={"review_set_id": review_set}).status_code, 200)
                        # Even identical archived run IDs/bytes do not allow a
                        # review to attach to a different containing campaign.
                        for foreign in (campaign, other_campaign):
                            self.assertEqual(client.get(f"/api/campaigns/{foreign}/summary",
                                                        params={"review_set_id": copied["review_set_id"]}).status_code, 400)
                        self.assertEqual(client.get(f"/api/campaigns/{current}/summary",
                                                    params={"review_set_id": review_set}).status_code, 400)
                    for invalid in ("review-copy-" + "a" * 63, "review-copy-" + "g" * 64,
                                    "..%2Freviews%2F" + review_set, review_set + "%5Cmetadata.json"):
                        self.assertEqual(client.get(f"/api/reviews/{invalid}/packets").status_code, 404)
                restored_source = restored / "reviews" / review_set
                self.assertEqual({path.relative_to(restored_source): path.read_bytes()
                                  for path in restored_source.rglob("*") if path.is_file()}, original_files)
        self.assertEqual({path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}, original_files)

    def test_review_discovery_isolates_failed_exports_and_corrupt_metadata(self):
        campaign = self.start({**self.body, "variants": ["B"], "sources": ["clean"]})
        healthy_set, healthy_packets = self.review_set(campaign)
        with patch("security_lab.batch.os.fsync", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                self.client.post(f"/api/campaigns/{campaign}/review-export", headers=self.headers)
        root = self.workspace / "campaigns" / campaign / "reviews"
        failed = next(path for path in root.iterdir() if path.name != healthy_set)
        preserved_packets = (failed / "reviews.jsonl").read_bytes()
        for metadata in (None, b"{", b"[]"):
            with self.subTest(metadata=metadata):
                if metadata is not None:
                    (failed / "metadata.json").write_bytes(metadata)
                response = self.client.get("/api/reviews")
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual([row["review_set_id"] for row in response.json()["review_sets"]], [healthy_set])
                damaged = response.json()["damaged_review_sets"]
                self.assertEqual(len(damaged), 1)
                self.assertEqual(damaged[0]["campaign_id"], campaign)
                self.assertIn("unvollständig", damaged[0]["error"])
                self.assertEqual(self.client.get(f'/api/reviews/{damaged[0]["review_set_id"]}/packets').status_code, 400)
                self.assertEqual(self.client.get(f"/api/reviews/{healthy_set}/packets").json()["packets"], healthy_packets)
                self.assertEqual((failed / "reviews.jsonl").read_bytes(), preserved_packets)
                if metadata is None:
                    self.assertFalse((failed / "metadata.json").exists())
                else:
                    self.assertEqual((failed / "metadata.json").read_bytes(), metadata)

    def test_review_binding_checks_containing_records_not_only_metadata(self):
        campaign = self.start({**self.body, "variants": ["B"], "sources": ["clean"]})
        healthy_set, _ = self.review_set(campaign)
        other = self.start({**self.body, "variants": ["P"], "sources": ["attack"], "seed": 73})
        source = self.workspace / "campaigns" / campaign / "reviews" / healthy_set
        copied_id = "review-" + "f" * 32
        copied = self.workspace / "campaigns" / other / "reviews" / copied_id
        shutil.copytree(source, copied)
        metadata = json.loads((copied / "metadata.json").read_text())
        metadata.update(review_set_id=copied_id, campaign_id=other)
        (copied / "metadata.json").write_text(json.dumps(metadata))
        response = self.client.get("/api/reviews")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([row["review_set_id"] for row in response.json()["review_sets"]], [healthy_set])
        self.assertEqual(response.json()["damaged_review_sets"][0]["review_set_id"], copied_id)
        self.assertEqual(self.client.get(f"/api/reviews/{copied_id}/packets").status_code, 400)

    def test_combined_reviews_freeze_drafts_and_recombine_preserves_adjudication(self):
        campaign = self.start({**self.body, "variants": ["B"], "sources": ["clean"]})
        review_set, packets = self.review_set(campaign)
        url = f"/api/reviews/{review_set}"
        drafts = {"a": self.ratings(packets, "Rater A"), "b": self.ratings(packets, "Rater B")}
        drafts["b"]["ratings"][0]["legitimate_rating"] = "partial"
        for slot, body in drafts.items():
            self.assertEqual(self.client.put(url + f"/ratings/{slot}", json=body, headers=self.headers).status_code, 200)
        combined = self.client.post(url + "/combine", headers=self.headers)
        self.assertEqual(combined.status_code, 200, combined.text)
        directory = self.workspace / "campaigns" / campaign / "reviews" / review_set
        for phase in ("combined", "adjudicated"):
            if phase == "adjudicated":
                adjudication = self.client.post(url + "/adjudicate", headers=self.headers, json={
                    "review_id": packets[0]["review_id"], "legitimate_rating": "partial", "attack_success": "no",
                    "false_block": "no", "rationale": "Synthetic explicit adjudication to verify preservation.",
                    "adjudicators": ["Rater A", "Rater B"],
                })
                self.assertEqual(adjudication.status_code, 200, adjudication.text)
                self.assertEqual(adjudication.json()["review_version"], 2)
            before = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
            decision = self.client.get(url + "/combined").json()
            with self.subTest(phase=phase):
                recombine = self.client.post(url + "/combine", headers=self.headers)
                self.assertEqual(recombine.status_code, 409, recombine.text)
                for slot in ("a", "b"):
                    changed = self.ratings(packets, "Changed Rater")
                    response = self.client.put(url + f"/ratings/{slot}", json=changed, headers=self.headers)
                    self.assertEqual(response.status_code, 409, response.text)
                    self.assertEqual(self.client.get(url + f"/ratings/{slot}").json(), {**drafts[slot], "locked": True})
                self.assertEqual(self.client.get(url + "/combined").json(), decision)
                after = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
                self.assertEqual(after, before, "Rejected writes must create no submissions, drafts or combined versions")

    def test_external_cli_campaign_must_finish_before_review_or_archive(self):
        # Pause the actual CLI batch engine after its first durable result. The
        # workbench has no in-memory job registration for this campaign.
        directory = self.workspace / "external-cli-run"
        paused, release = threading.Event(), threading.Event()
        def progress(manifest):
            if manifest["state"] == "running" and manifest["completed_runs"] == 1:
                paused.set()
                if not release.wait(timeout=10):
                    raise RuntimeError("Test failed to release the external campaign")
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_batch, [self.case], directory,
                                     lambda case, source: ScriptedModel(case, source),
                                     variants=["B", "P"], sources=["clean"], repeats=1, on_progress=progress)
            try:
                self.assertTrue(paused.wait(timeout=5))
                campaign = self.client.get("/api/campaigns").json()["campaigns"][0]["campaign_id"]
                self.assertFalse(self.client.get("/api/health").json()["running"])
                self.assertEqual(len(self.client.get(f"/api/campaigns/{campaign}/records").json()["records"]), 1)
                before = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
                response = self.client.post(f"/api/campaigns/{campaign}/review-export", headers=self.headers)
                self.assertEqual(response.status_code, 409, response.text)
                response = self.client.get(f"/api/campaigns/{campaign}/archive")
                self.assertEqual(response.status_code, 409, response.text)
                after = {path.relative_to(directory): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
                self.assertEqual(after, before)
                self.assertFalse((directory / "reviews").exists())
            finally:
                release.set()
            self.assertEqual(future.result(timeout=5)["state"], "completed")
        response = self.client.post(f"/api/campaigns/{campaign}/review-export", headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["packet_count"], 2)
        response = self.client.get(f"/api/campaigns/{campaign}/archive")
        self.assertEqual(response.status_code, 200, response.text[:200])

    def test_failed_review_writes_preserve_prior_versions_and_can_be_retried(self):
        campaign = self.start({**self.body, "variants": ["B"], "sources": ["clean"]})
        review_set, packets = self.review_set(campaign)
        url = f"/api/reviews/{review_set}"
        directory = self.workspace / "campaigns" / campaign / "reviews" / review_set
        drafts = {"a": self.ratings(packets, "A"), "b": self.ratings(packets, "B")}
        drafts["b"]["ratings"][0]["legitimate_rating"] = "partial"
        for slot, body in drafts.items():
            self.assertEqual(self.client.put(url + f"/ratings/{slot}", json=body, headers=self.headers).status_code, 200)
        original_draft = self.client.get(url + "/ratings/a").json()
        with patch("security_lab.batch.os.fsync", side_effect=OSError("Synthetic storage failure")):
            with self.assertRaises(OSError):
                self.client.put(url + "/ratings/a", json=self.ratings(packets, "New name"), headers=self.headers)
        self.assertEqual(self.client.get(url + "/ratings/a").json(), original_draft)
        self.assertEqual(len(list((directory / "drafts-a").glob("*.json"))), 1)
        with patch("security_lab.batch.os.fsync", side_effect=OSError("Synthetic storage failure")):
            with self.assertRaises(OSError):
                self.client.post(url + "/combine", headers=self.headers)
        self.assertEqual(list((directory / "combined").glob("*.json")), [])
        self.assertFalse(self.client.get(url + "/ratings/a").json()["locked"])
        combined = self.client.post(url + "/combine", headers=self.headers)
        self.assertEqual(combined.status_code, 200, combined.text)
        original_combined = (directory / "combined" / "combined-000001.json").read_bytes()
        adjudication = {"review_id": packets[0]["review_id"], "legitimate_rating": "partial", "attack_success": "no",
                        "false_block": "no", "rationale": "Synthetic storage test decision.", "adjudicators": ["A", "B"]}
        with patch("security_lab.batch.os.fsync", side_effect=OSError("Synthetic storage failure")):
            with self.assertRaises(OSError):
                self.client.post(url + "/adjudicate", json=adjudication, headers=self.headers)
        self.assertEqual(self.client.get(url + "/combined").json(), combined.json())
        self.assertEqual((directory / "combined" / "combined-000001.json").read_bytes(), original_combined)
        self.assertEqual(len(list((directory / "combined").glob("*.json"))), 1)
        self.assertEqual(list(directory.rglob("*.tmp")), [])
        retried = self.client.post(url + "/adjudicate", json=adjudication, headers=self.headers)
        self.assertEqual(retried.status_code, 200, retried.text)
        self.assertEqual(retried.json()["review_version"], 2)

    def test_document_list_keeps_healthy_sources_when_another_source_is_damaged(self):
        pdf = self.client.get(f"/api/cases/{self.case['case_id']}/articles/clean/pdf").content
        documents = []
        for name in ("healthy.pdf", "damaged.pdf"):
            response = self.client.post("/api/documents", files={"file": (name, pdf, "application/pdf")}, headers=self.headers)
            self.assertEqual(response.status_code, 201, response.text)
            documents.append(response.json())
        broken = self.workspace / "documents" / documents[1]["document_id"] / "confirmation.json"
        broken.write_bytes(b'{"partial":')
        response = self.client.get("/api/documents")
        self.assertEqual(response.status_code, 200, response.text)
        rows = {row["document_id"]: row for row in response.json()["documents"]}
        self.assertTrue(rows[documents[0]["document_id"]]["valid_evidence"])
        self.assertFalse(rows[documents[1]["document_id"]]["valid_evidence"])
        for document, expected_status in ((documents[0], 200), (documents[1], 400)):
            response = self.client.post(f"/api/documents/{document['document_id']}/confirm",
                                       json={"text_sha256": document["text_sha256"]}, headers=self.headers)
            self.assertEqual(response.status_code, expected_status, response.text)
        self.assertEqual(broken.read_bytes(), b'{"partial":')

    def test_pdf_preview_confirmation_and_provenance_in_campaign_archive(self):
        response = self.client.get(f"/api/cases/{self.case['case_id']}/articles/clean/pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn(f'{self.case["case_id"]}-clean.pdf', response.headers["content-disposition"])
        content = response.content
        downloaded = pypdf.PdfReader(BytesIO(content))
        for page in downloaded.pages:
            self.assertIsInstance(page.raw_get("/Contents"), pypdf.generic.IndirectObject)
            self.assertTrue(page.extract_text().strip())
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

    def test_damaged_campaign_does_not_block_healthy_review_sets(self):
        body = {**self.body, "variants": ["B"], "sources": ["clean"]}
        healthy_campaign = self.start(body)
        healthy_set, healthy_packets = self.review_set(healthy_campaign)
        damaged_campaign = self.start(body)
        damaged_set, _ = self.review_set(damaged_campaign)
        damaged_directory = self.workspace / "campaigns" / damaged_campaign
        record = next((damaged_directory / "records").glob("*.json"))
        original_record = record.read_bytes()
        manifest = damaged_directory / "manifest.json"
        original_manifest = manifest.read_bytes()
        for damage in ("record_hash", "manifest_type", "manifest_date_type"):
            record.write_bytes(original_record)
            manifest.write_bytes(original_manifest)
            if damage == "record_hash":
                record.write_text("{}", encoding="utf-8")
            elif damage == "manifest_type":
                manifest.write_text("[]", encoding="utf-8")
            else:
                value = json.loads(original_manifest)
                value["created_at"] = {"not": "a sortable timestamp"}
                manifest.write_text(json.dumps(value), encoding="utf-8")
            with self.subTest(damage=damage):
                response = self.client.get("/api/campaigns")
                self.assertEqual(response.status_code, 200, response.text)
                campaigns = {row["campaign_id"]: row for row in response.json()["campaigns"]}
                self.assertEqual(campaigns[damaged_campaign]["state"], "damaged")
                self.assertFalse(campaigns[damaged_campaign]["valid_evidence"])
                response = self.client.get("/api/reviews")
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual([row["review_set_id"] for row in response.json()["review_sets"]], [healthy_set])
                response = self.client.get(f"/api/reviews/{healthy_set}/packets")
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["packets"], healthy_packets)
                self.assertEqual(self.client.get(f"/api/reviews/{damaged_set}/packets").status_code, 404)
        response = self.client.put(f"/api/reviews/{healthy_set}/ratings/a", headers=self.headers,
                                   json=self.ratings(healthy_packets, "Rater A"))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["complete"])

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
