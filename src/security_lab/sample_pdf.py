"""Generate text-based synthetic article PDFs for the import demonstration."""
from __future__ import annotations

from io import BytesIO
import textwrap


def article_pdf(case: dict, source: str) -> bytes:
    """Package an existing article without inventing new research content.

    Uses PDF's standard Helvetica font and WinAnsi encoding. Unsupported glyphs
    are rejected, never silently replaced; the controlled German fixtures fit.
    """
    if source not in {"clean", "attack"}:
        raise ValueError("Expected clean or attack")
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

    title = case.get("document", {}).get("title", "Synthetischer Wissensartikel")
    lines = [title, "", *sum((textwrap.wrap(p, width=88, break_long_words=False,
                                         break_on_hyphens=False) + [""]
                             for p in case["articles"][source].splitlines()), [])]
    writer = PdfWriter()
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica"),
                             NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})
    for offset in range(0, len(lines), 48):
        page = writer.add_blank_page(width=595, height=842)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        commands = [b"BT /F1 10 Tf 14 TL 48 790 Td"]
        for line in lines[offset:offset + 48]:
            raw = line.encode("cp1252")
            escaped = raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
            commands.append(b"(" + escaped + b") Tj T*")
        commands.append(b"ET")
        stream = DecodedStreamObject()
        stream.set_data(b"\n".join(commands))
        page[NameObject("/Contents")] = stream
    writer.add_metadata({"/Title": title, "/Author": "LLM Agent Security Lab",
                         "/Subject": "Synthetische Entwicklungsdaten, keine empirischen Ergebnisse"})
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
