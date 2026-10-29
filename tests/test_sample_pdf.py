from io import BytesIO
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from security_lab.cases import load_cases
from security_lab.sample_pdf import article_pdf

try:
    from pypdf import PdfReader
    from pypdf.generic import IndirectObject, StreamObject
except ImportError:
    PdfReader = None


@unittest.skipIf(PdfReader is None, "Install the web extra for PDF tests")
class SamplePdfTests(unittest.TestCase):
    def test_every_sample_retains_complete_article(self):
        normalize = lambda value: re.sub(r"\s+", " ", value).strip()
        for case in load_cases(Path("cases/dev")):
            for source in ("clean", "attack"):
                with self.subTest(case=case["case_id"], source=source):
                    reader = PdfReader(BytesIO(article_pdf(case, source)))
                    for page in reader.pages:
                        # /Contents is a stream reference, not a direct stream
                        # embedded in a page dictionary (invalid PDF syntax).
                        reference = page.raw_get("/Contents")
                        self.assertIsInstance(reference, IndirectObject)
                        self.assertIsInstance(reference.get_object(), StreamObject)
                        self.assertIsInstance(page["/Resources"]["/Font"].raw_get("/F1"), IndirectObject)
                    text = "\n".join(page.extract_text() for page in reader.pages)
                    self.assertIn(normalize(case["articles"][source]), normalize(text))

    @unittest.skipUnless(shutil.which("pdftoppm"), "Poppler is required for independent PDF rendering")
    def test_every_sample_renders_visible_content_in_poppler(self):
        # A second PDF engine catches malformed files that pypdf can still
        # extract. Linux CI installs Poppler; the format checks run everywhere.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for case in load_cases(Path("cases/dev")):
                for source in ("clean", "attack"):
                    with self.subTest(case=case["case_id"], source=source):
                        stem = f"{case['case_id']}-{source}"
                        pdf = root / f"{stem}.pdf"
                        pdf.write_bytes(article_pdf(case, source))
                        rendered = subprocess.run(
                            ["pdftoppm", "-gray", "-r", "36", str(pdf), str(root / stem)],
                            capture_output=True, timeout=15, check=False,
                        )
                        self.assertEqual(rendered.returncode, 0, rendered.stderr.decode(errors="replace"))
                        self.assertEqual(rendered.stderr, b"")
                        pages = sorted(root.glob(f"{stem}-*.pgm"))
                        self.assertEqual(len(pages), len(PdfReader(pdf).pages))
                        for page in pages:
                            image = page.read_bytes()
                            header = re.match(rb"P5\s+(\d+)\s+(\d+)\s+255\s", image)
                            self.assertIsNotNone(header)
                            pixels = image[header.end():]
                            self.assertEqual(len(pixels), int(header[1]) * int(header[2]))
                            self.assertGreater(sum(value < 240 for value in pixels), 100,
                                               f"Blank rendered page: {page.name}")

    def test_multiple_pages_keep_escaped_and_german_text(self):
        lines = [f"Zeile {index}: Grüße (Prüfung) \\ Rückweg – 25 €" for index in range(100)]
        case = {"document": {"title": "Mehrseitiger Prüfartikel"},
                "articles": {"clean": "\n".join(lines)}}
        reader = PdfReader(BytesIO(article_pdf(case, "clean")))
        self.assertGreater(len(reader.pages), 1)
        for page in reader.pages:
            self.assertIsInstance(page.raw_get("/Contents"), IndirectObject)
            self.assertTrue(page.extract_text().strip())
        text = "\n".join(page.extract_text() for page in reader.pages)
        for line in lines:
            self.assertIn(line, text)

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            article_pdf(load_cases(Path("cases/dev"))[0], "unknown")
