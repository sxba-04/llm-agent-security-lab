"""PDF imports preserve evidence and reject unusable or unsafe inputs."""
from __future__ import annotations

import copy
import hashlib
from io import BytesIO
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

try:
    import pypdf
except ImportError:
    pypdf = None

from security_lab.cases import load_cases
from security_lab.documents import (
    DocumentError, MAX_PDF_BYTES, apply_document_override, confirm_document,
    extract_pdf, import_document, load_document, reject_symlinks,
)
from security_lab.sample_pdf import article_pdf

CASES = Path(__file__).resolve().parents[1] / "cases" / "dev"


@unittest.skipUnless(pypdf, "Install the web extra for PDF tests")
class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.storage = Path(self.temp.name) / "documents"
        self.case = load_cases(CASES)[0]
        self.pdf = article_pdf(self.case, "clean")

    def test_original_hash_confirmation_and_article_only_facts(self):
        document = import_document(self.storage, "C:\\local\\article.pdf", self.pdf)
        self.assertFalse(document["confirmed"])
        self.assertEqual(document["filename"], "article.pdf")
        self.assertEqual(document["sha256"], hashlib.sha256(self.pdf).hexdigest())
        self.assertIn("pypdf", document["extractor"])
        self.assertEqual((self.storage / document["document_id"] / "original.pdf").read_bytes(), self.pdf)
        with self.assertRaises(DocumentError):
            apply_document_override(self.case, "clean", document)
        with self.assertRaises(DocumentError):
            confirm_document(self.storage, document["document_id"], "0" * 64)
        document = confirm_document(self.storage, document["document_id"], document["text_sha256"])
        changed = apply_document_override(self.case, "clean", document)
        self.assertTrue(document["confirmed"])
        self.assertEqual(changed["articles"]["clean"], document["extracted_text"])
        self.assertEqual(changed["articles"]["attack"], self.case["articles"]["attack"])
        self.assertNotIn("article_sources", self.case)
        self.assertEqual(changed["article_sources"]["clean"]["origin"], "uploaded_pdf")
        self.assertEqual(confirm_document(self.storage, document["document_id"], document["text_sha256"]), document)

    def test_fact_comparison_is_whitespace_only_and_case_sensitive(self):
        document = import_document(self.storage, "article.pdf", self.pdf)
        document = confirm_document(self.storage, document["document_id"], document["text_sha256"])
        altered = copy.deepcopy(document)
        altered["extracted_text"] = "\n  ".join(document["extracted_text"].split())
        apply_document_override(self.case, "clean", altered)
        altered["extracted_text"] = document["extracted_text"].upper()
        with self.assertRaisesRegex(DocumentError, "Artikelfakten"):
            apply_document_override(self.case, "clean", altered)

    def test_invalid_empty_encrypted_and_page_limit(self):
        for data, filename in ((b"%PDF-corrupt", "bad.pdf"), (self.pdf, "bad.txt"),
                               (b"%PDF-" + b"x" * MAX_PDF_BYTES, "large.pdf")):
            with self.subTest(filename=filename), self.assertRaises(DocumentError):
                import_document(self.storage, filename, data)
        for mode in ("blank", "encrypted", "pages"):
            writer = pypdf.PdfWriter()
            for _ in range(51 if mode == "pages" else 1):
                writer.add_blank_page(width=300, height=200)
            if mode == "encrypted":
                writer.encrypt("private")
            output = BytesIO()
            writer.write(output)
            with self.subTest(mode=mode), self.assertRaises(DocumentError):
                import_document(self.storage, mode + ".pdf", output.getvalue())
        self.assertEqual(list(self.storage.glob("doc-*")), [])
        self.assertEqual(list(self.storage.glob("import-*")), [])

    def test_timeout_does_not_inherit_provider_credentials(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic-not-a-key"}), \
             patch("security_lab.documents.subprocess.run", side_effect=subprocess.TimeoutExpired("pdf", 1)) as runner:
            with self.assertRaisesRegex(DocumentError, "Zeitlimit"):
                extract_pdf(Path(self.temp.name) / "test.pdf")
            self.assertNotIn("OPENAI_API_KEY", runner.call_args.kwargs["env"])

    def test_tampering_and_symlinks_are_rejected(self):
        document = import_document(self.storage, "article.pdf", self.pdf)
        path = self.storage / document["document_id"] / "extracted.txt"
        path.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(DocumentError, "integrität"):
            load_document(self.storage, document["document_id"])
        target = Path(self.temp.name) / "outside"
        target.mkdir()
        link = Path(self.temp.name) / "linked"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink creation unavailable")
        with self.assertRaises(DocumentError):
            reject_symlinks(link / "file")
        with self.assertRaises(DocumentError):
            load_document(self.storage, "../outside")
        with self.assertRaises(DocumentError):
            reject_symlinks(self.storage / ".." / "outside", self.storage)


if __name__ == "__main__":
    unittest.main()
