"""Bounded text-only PDF imports with immutable bytes and extraction provenance.

PDF parsing runs in a disposable subprocess. POSIX additionally applies address
space and CPU limits; Windows gets the same file/page/text limits and a hard
wall-clock timeout, but this is not a general-purpose operating-system sandbox.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any
import uuid

MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_PAGES = 50
MAX_TEXT_CHARS = 200_000
MAX_PAGE_STREAM_BYTES = 2 * 1024 * 1024
EXTRACTION_TIMEOUT_SECONDS = 15
DOCUMENT_ID = re.compile(r"doc-[0-9a-f]{32}\Z")


class DocumentError(ValueError):
    """An import cannot be used as a documented article source."""


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def reject_symlinks(path: Path, root: Path | None = None) -> Path:
    """Reject links/junctions in a managed path before resolving it."""
    if ".." in path.parts:
        raise DocumentError("Übergeordnete Pfadsegmente sind nicht zulässig.")
    path = path.absolute()
    parts = [path, *path.parents]
    if root is not None:
        root = root.absolute()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise DocumentError("Pfad liegt außerhalb des Arbeitsbereichs.") from exc
    for part in parts:
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise DocumentError("Symbolische Verknüpfungen sind im Arbeitsbereich nicht zulässig.")
    return path


def _managed(storage: Path, document_id: str) -> Path:
    if not DOCUMENT_ID.fullmatch(document_id):
        raise DocumentError("Ungültige Dokumentkennung.")
    return reject_symlinks(Path(storage) / document_id, Path(storage))


def _extract_worker(path: Path) -> dict[str, Any]:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except ImportError:
        pass  # Windows subprocess timeout still applies.
    from pypdf import PdfReader, __version__
    reader = PdfReader(str(path), strict=True)
    if reader.is_encrypted:
        raise DocumentError("Verschlüsselte PDFs werden nicht importiert.")
    count = len(reader.pages)
    if not 1 <= count <= MAX_PAGES:
        raise DocumentError(f"PDF muss 1 bis {MAX_PAGES} Seiten enthalten.")
    texts = []
    total = 0
    stream_total = 0
    for page in reader.pages:
        contents = page.get_contents()
        if contents is not None:
            length = len(contents.get_data())
            stream_total += length
            if length > MAX_PAGE_STREAM_BYTES or stream_total > 10 * MAX_PAGE_STREAM_BYTES:
                raise DocumentError("PDF-Inhaltsdaten überschreiten das Extraktionslimit.")
        text = page.extract_text() or ""
        total += len(text)
        if total > MAX_TEXT_CHARS:
            raise DocumentError("Der extrahierte Text ist zu lang.")
        texts.append(text)
    text = "\n\n".join(texts).strip()
    if not text:
        raise DocumentError("Kein auslesbarer Text. Bildscans benötigen eine separate OCR-Aufbereitung.")
    if len(text) > MAX_TEXT_CHARS:
        raise DocumentError("Der extrahierte Text ist zu lang.")
    return {"extracted_text": text, "page_count": count, "extractor": f"pypdf {__version__} / extract_text"}


def extract_pdf(path: Path, *, timeout_seconds: float = EXTRACTION_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Parse in a resource-bounded child without inheriting provider credentials."""
    environment = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "TEMP", "TMP", "TMPDIR"}}
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--extract", str(path.absolute())],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
            timeout=timeout_seconds, env=environment, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise DocumentError("PDF-Extraktion hat das Zeitlimit überschritten.") from exc
    if result.returncode != 0:
        raise DocumentError("PDF ist beschädigt, verschlüsselt, leer oder überschreitet ein Extraktionslimit.")
    if len(result.stdout) > MAX_TEXT_CHARS * 6 + 8192:
        raise DocumentError("PDF-Extraktion lieferte zu viele Daten.")
    try:
        extracted = json.loads(result.stdout)
        text = extracted["extracted_text"]
        pages = extracted["page_count"]
        extractor = extracted["extractor"]
        if (not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT_CHARS
                or type(pages) is not int or not 1 <= pages <= MAX_PAGES or not isinstance(extractor, str)):
            raise ValueError("Invalid extraction result")
    except (KeyError, TypeError, ValueError) as exc:
        raise DocumentError("Ungültiges Ergebnis der PDF-Extraktion.") from exc
    return extracted


def import_document(storage: Path, filename: str, content: bytes) -> dict[str, Any]:
    storage = reject_symlinks(Path(storage))
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_PDF_BYTES:
        raise DocumentError("PDF muss kleiner als 5 MiB und darf nicht leer sein.")
    name = Path(str(filename).replace("\\", "/")).name
    if not name.lower().endswith(".pdf") or len(name) > 180 or not content.startswith(b"%PDF-"):
        raise DocumentError("Eine gültige PDF-Datei mit .pdf-Endung ist erforderlich.")
    storage.mkdir(parents=True, exist_ok=True)
    document_id = "doc-" + uuid.uuid4().hex
    temporary = Path(tempfile.mkdtemp(prefix="import-", dir=storage))
    try:
        pdf = temporary / "original.pdf"
        pdf.write_bytes(content)
        extraction = extract_pdf(pdf)
        text_bytes = extraction.pop("extracted_text").encode("utf-8")
        (temporary / "extracted.txt").write_bytes(text_bytes)
        metadata = {
            "document_id": document_id, "filename": name, "sha256": _sha(content),
            "text_sha256": _sha(text_bytes), **extraction,
            "origin": "uploaded_pdf", "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (temporary / "document.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        temporary.rename(_managed(storage, document_id))
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return load_document(storage, document_id)


def load_document(storage: Path, document_id: str) -> dict[str, Any]:
    directory = _managed(Path(storage), document_id)
    for name in ("document.json", "original.pdf", "extracted.txt", "confirmation.json"):
        reject_symlinks(directory / name, Path(storage))
    try:
        if (directory / "document.json").stat().st_size > 16384 or (directory / "original.pdf").stat().st_size > MAX_PDF_BYTES or (directory / "extracted.txt").stat().st_size > MAX_TEXT_CHARS * 4:
            raise DocumentError("Gespeicherte Dokumentdaten überschreiten die Größenbegrenzung.")
        metadata = json.loads((directory / "document.json").read_text(encoding="utf-8"))
        if (not isinstance(metadata, dict) or metadata.get("origin") != "uploaded_pdf"
                or type(metadata.get("page_count")) is not int or not 1 <= metadata["page_count"] <= MAX_PAGES
                or not isinstance(metadata.get("filename"), str) or not isinstance(metadata.get("extractor"), str)):
            raise DocumentError("Ungültige Dokumentmetadaten.")
        original = (directory / "original.pdf").read_bytes()
        text_bytes = (directory / "extracted.txt").read_bytes()
    except FileNotFoundError:
        raise
    except (OSError, ValueError) as exc:
        raise DocumentError("Dokumentdaten können nicht geprüft werden.") from exc
    if (metadata.get("document_id") != document_id or _sha(original) != metadata.get("sha256")
            or _sha(text_bytes) != metadata.get("text_sha256")):
        raise DocumentError("Dokumentintegrität verletzt: Original oder Extraktion wurde verändert.")
    try:
        text = text_bytes.decode("utf-8")
        if not text.strip() or len(text) > MAX_TEXT_CHARS:
            raise DocumentError("Ungültiger gespeicherter Extraktionstext.")
    except UnicodeError as exc:
        raise DocumentError("Extraktion ist kein gültiger UTF-8-Text.") from exc
    confirmed = False
    if (directory / "confirmation.json").exists():
        if (directory / "confirmation.json").stat().st_size > 2048:
            raise DocumentError("Ungültige Bestätigungsdaten.")
        confirmation = json.loads((directory / "confirmation.json").read_text(encoding="utf-8"))
        if not isinstance(confirmation, dict) or confirmation.get("text_sha256") != metadata["text_sha256"]:
            raise DocumentError("Bestätigung gehört zu einer anderen Extraktion.")
        confirmed = True
    return {**metadata, "extracted_text": text, "confirmed": confirmed}


def list_documents(storage: Path) -> list[dict[str, Any]]:
    storage = reject_symlinks(Path(storage))
    if not storage.exists():
        return []
    return [load_document(storage, path.name) for path in sorted(storage.iterdir()) if DOCUMENT_ID.fullmatch(path.name)]


def confirm_document(storage: Path, document_id: str, text_sha256: str) -> dict[str, Any]:
    document = load_document(storage, document_id)
    if document["text_sha256"] != text_sha256:
        raise DocumentError("Die Bestätigung stimmt nicht mit dem angezeigten Text überein.")
    path = _managed(Path(storage), document_id) / "confirmation.json"
    if not path.exists():
        with path.open("x", encoding="utf-8") as stream:
            json.dump({"text_sha256": text_sha256, "confirmed_at": datetime.now(timezone.utc).isoformat()}, stream)
    return load_document(storage, document_id)


def apply_document_override(case: dict[str, Any], source: str, document: dict[str, Any]) -> dict[str, Any]:
    if source not in {"clean", "attack"} or document.get("confirmed") is not True:
        raise DocumentError("Nur bestätigte Extraktionen können clean oder attack ersetzen.")
    text = document["extracted_text"]
    expected = case["expected"]
    mappings = expected.get("required_fact_sources")
    required = [item["fact"] for item in mappings if item["source"] == "article"] if mappings is not None else expected["required_facts"]
    normalize = lambda value: " ".join(value.split())
    if any(normalize(fact) not in normalize(text) for fact in required):
        raise DocumentError("Der PDF-Text enthält nicht alle für diesen Fall benötigten Artikelfakten.")
    updated = copy.deepcopy(case)
    updated["articles"][source] = text
    updated.setdefault("article_sources", {})[source] = {
        key: document[key] for key in ("document_id", "filename", "sha256", "text_sha256", "page_count", "extractor", "origin", "confirmed")
    }
    from .cases import validate_case
    validate_case(updated)
    return updated


def copy_document_sources(storage: Path, document_ids: list[str], campaign: Path) -> None:
    """Copy reviewed originals into the immutable campaign's archive scope."""
    for document_id in sorted(set(document_ids)):
        document = load_document(storage, document_id)
        if not document["confirmed"]:
            raise DocumentError("Nicht bestätigte PDF-Quelle.")
        source = _managed(Path(storage), document_id)
        target = reject_symlinks(Path(campaign) / "sources" / document_id, Path(campaign))
        target.mkdir(parents=True, exist_ok=False)
        for name in ("original.pdf", "extracted.txt", "document.json", "confirmation.json"):
            with (target / name).open("xb") as stream:
                stream.write((source / name).read_bytes())


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--extract":
        raise SystemExit(2)
    try:
        print(json.dumps(_extract_worker(Path(sys.argv[2])), ensure_ascii=True, allow_nan=False))
    except Exception:
        raise SystemExit(1)
