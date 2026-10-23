"""Bounded campaign ZIP export, verification and safe re-import.

Hashes establish internal integrity, not authorship or authenticity. An archive
contains campaign evidence and recorded source-code hashes; it does not silently
claim to contain a complete runnable source checkout.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from typing import Any
import zipfile

from .batch import digest, evidence_completeness, load_results, verify_document_sources

INDEX_NAME = "archive-index.json"
MAX_FILES = 10000
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000


def _safe_name(name: str) -> str:
    if not isinstance(name, str) or not name or len(name) > 500 or "\\" in name or ":" in name:
        raise ValueError("Unsafe archive path")
    parts = name.split("/")
    if PurePosixPath(name).is_absolute() or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Unsafe archive path")
    for part in parts:
        if any(ord(char) < 32 for char in part) or part.endswith((" ", ".")):
            raise ValueError("Unsafe archive path")
        # Reject Windows device names and case-insensitive path collisions.
        if part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise ValueError("Unsafe Windows archive path")
    return name


def _json(raw: bytes) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key in archive metadata")
            result[key] = value
        return result
    def reject(value):
        raise ValueError("Nonfinite archive metadata")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject)


def _sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def _campaign_check(directory: Path) -> dict[str, Any]:
    results = load_results(directory)
    manifest = _json((directory / "manifest.json").read_bytes())
    if manifest["state"] == "running":
        raise ValueError("An active or unclosed campaign cannot be archived")
    cases = _json((directory / "cases.snapshot.json").read_bytes())
    documents = verify_document_sources(directory, cases, results, require_files=True)
    # A packet/mapping pair can be internally intact but belong to a different
    # campaign with the same local run IDs. Bind it to the canonical records.
    from .review import verify_packets
    by_id = {result["run_id"]: result for result in results}
    for mapping in directory.rglob("mapping.json"):
        packets = mapping.parent / "reviews.jsonl"
        if not packets.is_file():
            raise ValueError("Review mapping has no packet file")
        verify_packets(mapping, packets)
        entries = _json(mapping.read_bytes())["private_review_mapping"]
        if {entry["run_id"] for entry in entries.values()} != set(by_id):
            raise ValueError("Review mapping does not cover this campaign's run set")
        for entry in entries.values():
            result = by_id[entry["run_id"]]
            if entry.get("result_sha256") != digest(result) or entry.get("case_id") != result.get("case_id"):
                raise ValueError("Review provenance differs from campaign record")
    return {"campaign_state": manifest["state"], "completed_runs": len(results),
            "planned_runs": len(manifest["schedule"]), "engineering_only": all(r.get("is_mock") is True for r in results),
            "verified_integrity": True, **evidence_completeness(manifest),
            "verified_document_sources": documents,
            "source_code_included": False, "source_provenance": manifest.get("provenance", {})}


def _read_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    if info.file_size < 0 or info.file_size > MAX_FILE_BYTES:
        raise ValueError("Archive member exceeds file size limit")
    if info.file_size > max(1, info.compress_size) * MAX_COMPRESSION_RATIO:
        raise ValueError("Archive member exceeds compression ratio limit")
    with archive.open(info) as stream:
        data = stream.read(MAX_FILE_BYTES + 1)
    if len(data) != info.file_size or len(data) > MAX_FILE_BYTES:
        raise ValueError("Archive member size mismatch")
    return data


def _verify_into(path: Path, destination: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Invalid or oversized archive file")
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_FILES + 1:
                raise ValueError("Invalid archive member count")
            names: dict[str, zipfile.ZipInfo] = {}
            folded = set()
            total = 0
            for entry in entries:
                name = _safe_name(entry.filename)
                if entry.is_dir():
                    raise ValueError("Archive must contain regular files only")
                mode = entry.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                if file_type not in (0, stat.S_IFREG):
                    raise ValueError("Archive contains a link or special file")
                if entry.flag_bits & 1:
                    raise ValueError("Encrypted archive entries are unsupported")
                if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                    raise ValueError("Unsupported archive compression")
                if name in names or name.casefold() in folded:
                    raise ValueError("Duplicate archive path")
                names[name] = entry
                folded.add(name.casefold())
                total += entry.file_size
                if total > MAX_TOTAL_BYTES:
                    raise ValueError("Archive exceeds total expanded size limit")
            if INDEX_NAME not in names:
                raise ValueError("Archive integrity index missing")
            index = _json(_read_member(archive, names[INDEX_NAME]))
            if not isinstance(index, dict) or index.get("schema_version") != 1 or index.get("kind") != "security-lab-campaign":
                raise ValueError("Unknown archive format")
            indexed = index.get("files")
            if not isinstance(indexed, dict) or set(indexed) != set(names) - {INDEX_NAME}:
                raise ValueError("Archive file inventory mismatch")
            if index.get("source_code_included") is not False:
                raise ValueError("Unsupported source-code completeness claim")
            for name, expected in indexed.items():
                if not isinstance(expected, dict) or type(expected.get("size")) is not int:
                    raise ValueError("Malformed archive hash entry")
                data = _read_member(archive, names[name])
                if len(data) != expected["size"] or hashlib.sha256(data).hexdigest() != expected.get("sha256"):
                    raise ValueError(f"Archive hash mismatch: {name}")
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(data)
            checked = _campaign_check(destination)
            return {"verified": True, "authenticity_verified": False,
                    "archive_sha256": _sha(path), "files": len(indexed),
                    "expanded_bytes": sum(item["size"] for item in indexed.values()),
                    **checked}
    except (zipfile.BadZipFile, zipfile.LargeZipFile, UnicodeError, OSError, KeyError, TypeError) as exc:
        raise ValueError("Invalid or inconsistent campaign archive") from exc


def verify_archive(path: str | Path) -> dict[str, Any]:
    """Validate bounded ZIP contents, hashes and campaign/review cross-checks."""
    with tempfile.TemporaryDirectory(prefix="security-lab-verify-") as temporary:
        return _verify_into(Path(path), Path(temporary))


def export_campaign(directory: str | Path, output_path: str | Path) -> dict[str, Any]:
    """Export original campaign bytes without following external references.

    Every regular file inside the campaign, including source PDFs and review
    history, is included. Source code outside that directory is never harvested.
    The output ZIP must be outside the campaign and must not already exist.
    """
    directory, output_path = Path(directory), Path(output_path)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Campaign must be a real directory")
    if output_path.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Archive output must be outside the campaign")
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError("Archive output already exists")
    files = []
    folded = set()
    total = 0
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Campaign contains a symbolic link")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("Campaign contains a special file")
        name = _safe_name(path.relative_to(directory).as_posix())
        if name == INDEX_NAME or name.casefold() in folded:
            raise ValueError("Reserved or colliding campaign path")
        if name.endswith(".tmp"):
            raise ValueError("Campaign contains an unfinished temporary write")
        folded.add(name.casefold())
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError("Campaign file exceeds archive size limit")
        total += size
        if total > MAX_TOTAL_BYTES or len(files) >= MAX_FILES:
            raise ValueError("Campaign exceeds archive limits")
        current = path.stat()
        files.append((name, path, (current.st_size, current.st_mtime_ns, current.st_ino)))
    _campaign_check(directory)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".campaign-", suffix=".zip", dir=output_path.parent)
    os.close(handle)
    temp_path = Path(temporary)
    try:
        index = {"schema_version": 1, "kind": "security-lab-campaign",
                 "created_at": datetime.now(timezone.utc).isoformat(),
                 "source_code_included": False,
                 "scope": "Original campaign evidence; obtain source code separately using the manifest's Git commit and source hashes.",
                 "files": {}}
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, path, original_stat in files:
                current = path.stat()
                if (current.st_size, current.st_mtime_ns, current.st_ino) != original_stat or path.is_symlink():
                    raise ValueError("Campaign changed during export")
                data = path.read_bytes()
                if len(data) > MAX_FILE_BYTES:
                    raise ValueError("Campaign changed during export")
                index["files"][name] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
                archive.writestr(name, data)
            archive.writestr(INDEX_NAME, json.dumps(index, ensure_ascii=True, indent=2, allow_nan=False).encode("utf-8"))
        current_files = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if not p.is_dir()}
        if current_files != {name for name, _, _ in files}:
            raise ValueError("Campaign changed during export")
        for _, path, original_stat in files:
            current = path.stat()
            if path.is_symlink() or (current.st_size, current.st_mtime_ns, current.st_ino) != original_stat:
                raise ValueError("Campaign changed during export")
        report = verify_archive(temp_path)
        # Exclusive destination creation prevents an unnoticed overwrite.
        with output_path.open("xb") as destination, temp_path.open("rb") as source:
            shutil.copyfileobj(source, destination)
            destination.flush()
            os.fsync(destination.fileno())
        return {**report, "archive_path": str(output_path)}
    finally:
        temp_path.unlink(missing_ok=True)


def import_campaign(archive: str | Path, destination: str | Path) -> dict[str, Any]:
    """Import verified evidence to a new directory and retain the original ZIP."""
    archive, destination = Path(archive), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Import destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".campaign-import-", dir=destination.parent))
    try:
        report = _verify_into(archive, temporary)
        imported_sha = report["archive_sha256"]
        preserved = temporary / "provenance" / f"archive-{imported_sha}.zip"
        preserved.parent.mkdir(exist_ok=True)
        if preserved.exists():
            raise ValueError("Imported archive conflicts with its provenance copy")
        shutil.copyfile(archive, preserved)
        if _sha(preserved) != imported_sha:
            raise ValueError("Archive changed during import")
        metadata = {"archive_sha256": imported_sha, "source_code_included": False,
                    "imported_at": datetime.now(timezone.utc).isoformat(),
                    "original_archive": preserved.relative_to(temporary).as_posix()}
        (preserved.parent / f"import-{imported_sha}.json").write_text(
            json.dumps(metadata, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        if destination.exists():
            raise FileExistsError("Import destination already exists")
        temporary.rename(destination)
        return {**report, "destination": str(destination),
                "original_archive": str(destination / metadata["original_archive"])}
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
