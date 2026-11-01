"""Adversarial document identities must not select files outside managed storage."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from urllib.parse import quote

try:
    from fastapi.testclient import TestClient
    from security_lab.server import create_app
except ImportError:
    TestClient = None

from security_lab.cases import load_cases
from security_lab.documents import DocumentError, confirm_document, import_document, load_document
from security_lab.sample_pdf import article_pdf

CASES = Path(__file__).resolve().parents[1] / "cases" / "dev"


@unittest.skipUnless(TestClient, "Install the web and dev extras for API/PDF tests")
class DocumentPathBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.storage = self.root / "documents"
        self.pdf = article_pdf(load_cases(CASES)[0], "clean")

    def assert_rejected(self, storage, identifier, text_hash):
        with self.assertRaises(DocumentError):
            load_document(storage, identifier)
        with self.assertRaises(DocumentError):
            confirm_document(storage, identifier, text_hash)

    def test_forged_identifiers_cannot_load_or_confirm_an_external_document(self):
        outside = self.root / "outside"
        document = import_document(outside, "source.pdf", self.pdf)
        identifier = document["document_id"]
        directory = outside / identifier
        before = {path.name: path.read_bytes() for path in directory.iterdir()}
        malicious = (
            f"../outside/{identifier}", f"..\\outside\\{identifier}", str(directory),
            f"C:\\outside\\{identifier}", f"\\\\server\\share\\{identifier}",
            identifier + "/../outside", identifier + "\\..\\outside",
            identifier + ":stream", identifier + ".", identifier + " ",
            identifier + "\n", identifier + "\x00", identifier.upper(),
            "doc-" + "a" * 31, "doc-" + "a" * 33, "doc-" + "ａ" * 32,
        )
        for forged in malicious:
            with self.subTest(identifier=repr(forged)):
                self.assert_rejected(self.storage, forged, document["text_sha256"])
        self.assertFalse(self.storage.exists())
        self.assertEqual(before, {path.name: path.read_bytes() for path in directory.iterdir()})

    def test_each_document_file_symlink_is_rejected_without_touching_its_target(self):
        document = import_document(self.storage, "source.pdf", self.pdf)
        directory = self.storage / document["document_id"]
        outside = self.root / "outside"
        outside.mkdir()
        for name in ("document.json", "original.pdf", "extracted.txt", "confirmation.json"):
            with self.subTest(filename=name):
                path = directory / name
                original = path.read_bytes() if path.exists() else None
                external = outside / name
                external.write_bytes(original if original is not None else b"external sentinel")
                before = external.read_bytes()
                path.unlink(missing_ok=True)
                try:
                    path.symlink_to(external)
                except OSError:
                    if original is not None:
                        path.write_bytes(original)
                    self.skipTest("Actual filesystem symlink creation is unavailable")
                try:
                    self.assert_rejected(self.storage, document["document_id"], document["text_sha256"])
                    self.assertEqual(external.read_bytes(), before)
                    self.assertEqual(list(directory.glob("*.tmp")), [])
                finally:
                    path.unlink()
                    if original is not None:
                        path.write_bytes(original)
        self.assertFalse(load_document(self.storage, document["document_id"])["confirmed"])

    def test_document_directory_symlink_cannot_confirm_an_external_source(self):
        outside = self.root / "outside"
        document = import_document(outside, "source.pdf", self.pdf)
        self.storage.mkdir()
        link = self.storage / document["document_id"]
        try:
            link.symlink_to(outside / document["document_id"], target_is_directory=True)
        except OSError:
            self.skipTest("Actual filesystem symlink creation is unavailable")
        self.assert_rejected(self.storage, document["document_id"], document["text_sha256"])
        self.assertFalse((outside / document["document_id"] / "confirmation.json").exists())

    def test_api_rejects_decoded_path_payloads_and_preserves_the_valid_document(self):
        workspace = self.root / "workspace"
        app = create_app(workspace, CASES)
        client = self.enterContext(TestClient(app, base_url="http://127.0.0.1"))
        headers = {"X-Lab-Token": client.get("/api/health").json()["csrf_token"]}
        response = client.post("/api/documents", files={"file": ("source.pdf", self.pdf, "application/pdf")}, headers=headers)
        self.assertEqual(response.status_code, 201, response.text)
        document = response.json()
        identifier = document["document_id"]
        directory = workspace / "documents" / identifier
        before = {path.name: path.read_bytes() for path in directory.iterdir()}
        for forged in (identifier + "\n", identifier + ":stream", "..\\" + identifier,
                       identifier + "/../outside", "%2e%2e%2foutside", identifier + "."):
            with self.subTest(identifier=repr(forged)):
                response = client.post("/api/documents/" + quote(forged, safe="") + "/confirm",
                                       json={"text_sha256": document["text_sha256"]}, headers=headers)
                self.assertIn(response.status_code, (400, 404), response.text)
        self.assertEqual(before, {path.name: path.read_bytes() for path in directory.iterdir()})
        response = client.post(f"/api/documents/{identifier}/confirm",
                               json={"text_sha256": document["text_sha256"]}, headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["confirmed"])


if __name__ == "__main__":
    unittest.main()
