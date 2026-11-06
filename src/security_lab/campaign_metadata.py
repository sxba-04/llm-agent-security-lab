"""Versioned display metadata, separate from immutable experimental evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import threading
from typing import Any

from .batch import write_json_new
from .documents import reject_symlinks

DIRECTORY = "campaign-metadata"
VERSION_FILE = re.compile(r"metadata-[0-9]{6}\.json\Z")
UNPUBLISHED_FILE = re.compile(r"metadata-([0-9]{6})\.json\.[0-9a-f]{16}\.tmp\Z")
MAX_UNPUBLISHED = 128
MAX_REVISIONS = 10_000
# The supported runtime is one process. Readers must not mistake the atomic
# publisher's temporary file for damaged history; cross-process writers still
# use create-if-absent publication and fail instead of overwriting a version.
_METADATA_LOCK = threading.RLock()


class MetadataConflict(ValueError):
    """The expected display revision was superseded; no write took place."""


def validate_labels(display_name: str, tags: list[str]) -> None:
    if not isinstance(display_name, str) or len(display_name) > 120:
        raise ValueError("Der Versuchsname darf höchstens 120 Zeichen enthalten.")
    if not isinstance(tags, list) or len(tags) > 12:
        raise ValueError("Höchstens zwölf Tags sind erlaubt.")
    values = [display_name, *tags]
    if any(not isinstance(value, str) or any(ord(char) < 32 or 127 <= ord(char) <= 159 or 0xD800 <= ord(char) <= 0xDFFF for char in value)
           for value in values):
        raise ValueError("Name und Tags dürfen keine Steuerzeichen oder ungültigen Unicode-Zeichen enthalten.")
    if any(not tag or tag != tag.strip() or len(tag) > 40 for tag in tags):
        raise ValueError("Tags benötigen 1 bis 40 Zeichen ohne äußere Leerzeichen.")
    if len({tag.casefold() for tag in tags}) != len(tags):
        raise ValueError("Tags dürfen nicht doppelt vorkommen.")
    if display_name != display_name.strip():
        raise ValueError("Der Versuchsname darf keine äußeren Leerzeichen enthalten.")


def _unique_fields(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Doppelte Felder in Versuchsmetadaten.")
        value[key] = item
    return value


def _read_version(path: Path) -> tuple[dict[str, Any], str]:
    with path.open("rb") as stream:
        raw = stream.read(8193)
    if len(raw) > 8192:
        raise ValueError("Versuchsmetadaten überschreiten die Größenbegrenzung.")
    value = json.loads(raw, object_pairs_hook=_unique_fields)
    if (not isinstance(value, dict) or set(value) != {
            "schema_version", "revision", "previous_sha256", "display_name", "tags", "updated_at"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or type(value["revision"]) is not int or not isinstance(value["updated_at"], str)):
        raise ValueError("Nicht unterstützte oder beschädigte Versuchsmetadaten.")
    validate_labels(value["display_name"], value["tags"])
    timestamp = datetime.fromisoformat(value["updated_at"])
    if timestamp.tzinfo is None:
        raise ValueError("Versuchsmetadaten benötigen einen eindeutigen Zeitstempel.")
    return value, hashlib.sha256(raw).hexdigest()


def load_metadata(campaign: Path) -> dict[str, Any]:
    """Validate the complete append-only history; old campaigns start at revision 0."""
    with _METADATA_LOCK:
        return _load_metadata(campaign)


def _load_metadata(campaign: Path) -> dict[str, Any]:
    directory = reject_symlinks(campaign / DIRECTORY, campaign)
    current: dict[str, Any] = {"schema_version": 1, "revision": 0, "display_name": "", "tags": [],
                              "updated_at": None, "previous_sha256": None}
    if not directory.exists():
        return current
    paths, unpublished = _metadata_files(directory, campaign)
    previous = None
    for revision, path in enumerate(sorted(paths), 1):
        reject_symlinks(path, campaign)
        current, checksum = _read_version(path)
        if (path.name != f"metadata-{revision:06d}.json" or current["revision"] != revision
                or current["previous_sha256"] != previous):
            raise ValueError("Die Metadatenhistorie ist unvollständig oder verändert.")
        previous = checksum
    if any(int(UNPUBLISHED_FILE.fullmatch(path.name)[1]) not in range(1, current["revision"] + 2)
           for path in unpublished):
        raise ValueError("Temporäre Metadaten gehören nicht zur vorhandenen Versionshistorie.")
    if unpublished:
        # These bytes may be partial or may duplicate an already published hard
        # link. Never parse/promote/delete them: the immutable final filenames
        # alone define the committed history, and archives preserve all bytes.
        current = {**current, "unpublished_writes": sorted(path.name for path in unpublished)}
    return current


def _metadata_files(directory: Path, campaign: Path) -> tuple[list[Path], list[Path]]:
    versions, unpublished = [], []
    for path in directory.iterdir():
        reject_symlinks(path, campaign)
        if not path.is_file() or path.stat().st_size > 8192:
            raise ValueError("Die Metadatenhistorie enthält einen ungültigen Dateityp oder überschreitet die Größenbegrenzung.")
        if VERSION_FILE.fullmatch(path.name) and len(versions) < MAX_REVISIONS:
            versions.append(path)
        elif UNPUBLISHED_FILE.fullmatch(path.name) and len(unpublished) < MAX_UNPUBLISHED:
            unpublished.append(path)
        else:
            raise ValueError("Unbekannte oder zu viele Dateien in der Metadatenhistorie.")
    return versions, unpublished


def is_unpublished_metadata_file(path: Path) -> bool:
    """Narrow archive exception for retained publisher residue inside a campaign."""
    if path.parent.name != DIRECTORY or not UNPUBLISHED_FILE.fullmatch(path.name):
        return False
    campaign = path.parent.parent
    if not (campaign / "manifest.json").is_file():
        return False
    return path.name in load_metadata(campaign).get("unpublished_writes", [])


def save_metadata(campaign: Path, display_name: str, tags: list[str], expected_revision: int) -> dict[str, Any]:
    with _METADATA_LOCK:
        return _save_metadata(campaign, display_name, tags, expected_revision)


def _save_metadata(campaign: Path, display_name: str, tags: list[str], expected_revision: int) -> dict[str, Any]:
    validate_labels(display_name, tags)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError("Ungültige Metadatenrevision.")
    current = load_metadata(campaign)
    if current["revision"] != expected_revision:
        raise MetadataConflict("Name oder Tags wurden inzwischen geändert. Den aktuellen Stand laden und die Änderung erneut prüfen.")
    if current["revision"] >= MAX_REVISIONS:
        raise ValueError("Die Metadatenhistorie hat ihre Größenbegrenzung erreicht.")
    previous = None
    directory = reject_symlinks(campaign / DIRECTORY, campaign)
    if expected_revision:
        _, previous = _read_version(directory / f"metadata-{expected_revision:06d}.json")
    value = {"schema_version": 1, "revision": expected_revision + 1, "previous_sha256": previous,
             "display_name": display_name, "tags": tags, "updated_at": datetime.now(timezone.utc).isoformat()}
    try:
        write_json_new(directory / f"metadata-{value['revision']:06d}.json", value)
    except FileExistsError as exc:
        raise MetadataConflict("Name oder Tags wurden gleichzeitig geändert. Bitte den aktuellen Stand laden.") from exc
    return value
