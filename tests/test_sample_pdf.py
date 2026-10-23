from io import BytesIO
from pathlib import Path
import re
import unittest

from security_lab.cases import load_cases
from security_lab.sample_pdf import article_pdf

try:
    from pypdf import PdfReader
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
                    text = "\n".join(page.extract_text() for page in reader.pages)
                    self.assertIn(normalize(case["articles"][source]), normalize(text))

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            article_pdf(load_cases(Path("cases/dev"))[0], "unknown")
