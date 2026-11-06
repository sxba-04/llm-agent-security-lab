"""Bounded, verifiable research-workspace snapshots and isolated restoration.

Live callers must hold the workbench's write, worker and PDF-import locks. The
standalone command is a maintenance operation after all workspace writers stop.
Hashes prove consistency, never authorship; incomplete experiments stay incomplete.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any
import zipfile

from . import archives
from .batch import MANIFEST_FILE, digest, load_results
from .documents import DOCUMENT_ID, load_document, reject_symlinks
from .jobs import ACTIVE_STATES, _worker_lease

INDEX_NAME = "workspace-index.json"
FORMAT_KIND = "security-lab-workspace"
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
KNOWN_ROOTS = {"campaigns", "documents", "reviews", "workers", "studies", "metadata", "operations"}
OPERATIONAL_EVIDENCE_DIRS = {"persistence-20261102"}
MAX_SOURCE_COMMITS = 32
SOURCE_LOCKFILES = ("pyproject.toml", "uv.lock", "frontend/package-lock.json")
SOURCE_PREFIX = "source/"


def _git(root: Path, *arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=root, stderr=subprocess.DEVNULL, timeout=30)


def _campaign_directories(workspace: Path) -> list[Path]:
    directories = []
    for parent in (workspace, workspace / "campaigns"):
        reject_symlinks(parent, workspace)
        if not parent.is_dir():
            continue
        for child in sorted(parent.iterdir()):
            if _has_campaign_manifest(child, workspace, required=parent == workspace / "campaigns"):
                directories.append(child)
    return directories


def _has_campaign_manifest(directory: Path, workspace: Path, *, required: bool = False) -> bool:
    reject_symlinks(directory, workspace)
    manifest = directory / MANIFEST_FILE
    reject_symlinks(manifest, workspace)
    if manifest.exists() and not manifest.is_file():
        raise ValueError("Campaign manifest is not a regular file; preserve and inspect the original evidence")
    present = directory.is_dir() and manifest.is_file()
    if required and not present:
        raise ValueError("Managed campaign has missing manifest; preserve and inspect the original evidence")
    return present


def _check_worker_ownership(workspace: Path) -> None:
    for path in (workspace / "workers").glob("*.json"):
        reject_symlinks(path, workspace)
        value = archives._json(path.read_bytes())
        if (not isinstance(value, dict) or value.get("kind") != "workbench_mock_worker"
                or value.get("schema_version") != 1 or value.get("campaign_id") != path.stem):
            raise ValueError("Invalid worker ownership metadata")
        manifest = workspace / "campaigns" / path.stem / MANIFEST_FILE
        reject_symlinks(manifest, workspace)
        if not manifest.is_file():
            raise ValueError("Worker ownership refers to missing campaign evidence")


def _check_workspace(workspace: Path) -> dict[str, Any]:
    _check_worker_ownership(workspace)
    campaigns = {}
    for directory in _campaign_directories(workspace):
        campaigns[directory.relative_to(workspace).as_posix()] = archives.verify_campaign_directory(directory)
    documents = []
    storage = workspace / "documents"
    if storage.exists():
        for path in sorted(storage.iterdir()):
            if not DOCUMENT_ID.fullmatch(path.name) or not path.is_dir():
                raise ValueError("Workspace contains an unfinished or unknown document import")
            load_document(storage, path.name)
            documents.append(path.name)
    root_reviews = _check_root_reviews(workspace)
    return {"campaigns": campaigns, "documents": documents, "verified_root_reviews": root_reviews,
            "supplementary_operations": _operational_evidence(workspace),
            "evidence_complete": all(value["evidence_complete"] for value in campaigns.values()),
            "campaigns_complete": all(value["campaign_state"] == "completed" and value["completed_runs"] == value["planned_runs"]
                                      for value in campaigns.values()),
            "engineering_only": all(value["engineering_only"] for value in campaigns.values())}


def _operational_directories(workspace: Path) -> list[Path]:
    """Only the separately documented historical persistence proof is in scope."""
    root = workspace / "operations"
    reject_symlinks(root, workspace)
    if not root.exists():
        return []
    if not root.is_dir():
        raise ValueError("Operational evidence root must be a directory")
    directories = []
    for child in sorted(root.iterdir()):
        reject_symlinks(child, workspace)
        if child.name not in OPERATIONAL_EVIDENCE_DIRS or not child.is_dir():
            raise ValueError("Unknown operational evidence; review its scope before backup")
        directories.append(child)
    return directories


def _operational_evidence(workspace: Path) -> list[dict[str, Any]]:
    evidence = []
    for directory in _operational_directories(workspace):
        files = archives._export_files(directory)
        evidence.append({"path": directory.relative_to(workspace).as_posix(),
                         "files": [name for name, _, _ in files], "file_count": len(files),
                         "bytes": sum(stamp[0] for _, _, stamp in files),
                         "verification": "backup_inventory_and_sha256_only",
                         "semantic_evidence_verified": False,
                         "included_in_scientific_campaign_totals": False})
    return evidence


def _workspace_children(workspace: Path) -> list[Path]:
    """Fail on unknown roots instead of silently omitting research or secrets."""
    children = []
    for child in workspace.iterdir():
        if child.name == "exports" and _is_download_cache(child, workspace):
            continue
        reject_symlinks(child, workspace)
        if not child.is_dir() or (child.name not in KNOWN_ROOTS and not (child / MANIFEST_FILE).is_file()):
            raise ValueError("Unknown workspace entry; inspect it before creating a full backup")
        if child.name == "operations":
            _operational_directories(workspace)
        children.append(child)
    return sorted(children)


def _is_download_cache(directory: Path, workspace: Path) -> bool:
    """A legacy campaign named exports takes precedence over the ZIP cache."""
    if _has_campaign_manifest(directory, workspace):
        return False
    if not directory.is_dir():
        raise ValueError("Workspace export cache is not a directory")
    for path in directory.iterdir():
        reject_symlinks(path, workspace)
        if not path.is_file() or path.suffix.lower() != ".zip":
            raise ValueError("Ambiguous exports directory; preserve and inspect files before backup")
    return True


def _workspace_child_files(child: Path) -> list[tuple[str, Path, tuple]]:
    return [("workspace/" + child.name + "/" + name, path, stamp)
            for name, path, stamp in archives._export_files(child)
            if not (child.name == "workers" and "/" not in name and name.endswith(".lock"))]


def _workspace_files(workspace: Path) -> list[tuple[str, Path, tuple]]:
    files = []
    total = 0
    folded = set()
    for child in _workspace_children(workspace):
        for name, path, stamp in _workspace_child_files(child):
            if name.casefold() in folded:
                raise ValueError("Colliding workspace paths")
            folded.add(name.casefold())
            total += stamp[0]
            if total > archives.MAX_TOTAL_BYTES or len(files) >= archives.MAX_FILES:
                raise ValueError("Workspace exceeds backup limits")
            files.append((name, path, stamp))
    return files


def _check_root_reviews(workspace: Path) -> list[str]:
    """Older workbenches kept rating sets outside their campaign directory."""
    from .review import verify_packets
    root = workspace / "reviews"
    if not root.exists() or not any(root.iterdir()):
        return []
    inputs = {}
    campaign_runs = [{row["run_id"]: {"case_id": row["case_id"], "sha256": digest(row)}
                      for row in load_results(directory)}
                     for directory in _campaign_directories(workspace)]
    for directory in sorted(root.iterdir()):
        mapping, packets = directory / "mapping.json", directory / "reviews.jsonl"
        if not directory.is_dir() or not mapping.is_file() or not packets.is_file():
            raise ValueError("Legacy review set has incomplete mapping or packets")
        verify_packets(mapping, packets)
        entries = archives._json(mapping.read_bytes())["private_review_mapping"]
        if not any(_mapping_matches_campaign(entries, rows) for rows in campaign_runs):
            raise ValueError("Legacy review set has no matching campaign evidence")
        inputs[(archives._sha(mapping), archives._sha(packets))] = {
            "mapping": mapping, "packets": packets, "entries": entries}
    _check_root_review_versions(root, inputs)
    return sorted(path.name for path in root.iterdir())


def _check_root_review_versions(root: Path, inputs: dict) -> None:
    files = [path for path in root.rglob("*") if path.is_file()]
    versions = []
    for path in files:
        if path.suffix.lower() == ".json":
            is_version, value = archives._read_review_version(path, root, inputs, set())
            if is_version:
                versions.append((value, archives._review_version_source(value, inputs)))
    by_hash = {value["content_sha256"]: value for value, _ in versions}
    hashes = {}
    for value, source in versions:
        if value["review_version"] == 1:
            archives._verify_initial_review(value, source, files, hashes)
        else:
            archives._verify_review_successor(value, by_hash)


def _mapping_matches_campaign(entries: dict, rows: dict) -> bool:
    if {entry["run_id"] for entry in entries.values()} != set(rows):
        return False
    return all(entry["result_sha256"] == rows[entry["run_id"]]["sha256"]
               and entry.get("case_id") == rows[entry["run_id"]].get("case_id")
               for entry in entries.values())


def _check_no_active_workers(workspace: Path, stack: ExitStack) -> None:
    for path in sorted((workspace / "workers").glob("*.lock")):
        lease = _worker_lease(path)
        if lease is None:
            raise ValueError("An active worker prevents a consistent workspace backup")
        stack.callback(lease.close)
    for directory in _campaign_directories(workspace):
        manifest = archives._json((directory / MANIFEST_FILE).read_bytes())
        if manifest.get("state") in ACTIVE_STATES:
            raise ValueError("An active or unclosed campaign prevents a workspace backup")


def _requested_commits(check: dict, current: str) -> list[str]:
    requested = {current}
    for campaign in check["campaigns"].values():
        commit = campaign["source_provenance"].get("git_commit")
        if isinstance(commit, str) and COMMIT_PATTERN.fullmatch(commit):
            requested.add(commit)
    if len(requested) > MAX_SOURCE_COMMITS:
        raise ValueError("Too many source revisions for one bounded backup")
    return sorted(requested)


def _extract_source_snapshot(path: Path, target: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        total = 0
        seen = set()
        entries = archive.infolist()
        if len(entries) > archives.MAX_FILES:
            raise ValueError("Source checkout exceeds backup file limit")
        for info in entries:
            if info.is_dir():
                archives._safe_name(info.filename.rstrip("/"))
                continue
            name = archives._safe_name(info.filename)
            archives._validate_archive_member(info)
            if name.casefold() in seen:
                raise ValueError("Colliding source paths")
            seen.add(name.casefold())
            total += info.file_size
            if total > archives.MAX_TOTAL_BYTES:
                raise ValueError("Source checkout exceeds backup size limit")
            content = archives._read_member(archive, info)
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)


def _freeze_sources(source_root: Path, temporary: Path, check: dict) -> dict:
    try:
        current = _git(source_root, "rev-parse", "HEAD").decode("ascii").strip()
        if not COMMIT_PATTERN.fullmatch(current):
            raise ValueError("Source checkout has no valid commit")
        if _git(source_root, "status", "--porcelain", "--untracked-files=no").strip():
            raise ValueError("Commit or revert tracked source changes before taking a research backup")
        missing = []
        included = []
        for commit in _requested_commits(check, current):
            archive_path = temporary / (commit + ".zip")
            try:
                _git(source_root, "archive", "--format=zip", "--output=" + str(archive_path), commit)
            except subprocess.CalledProcessError:
                if commit == current:
                    raise
                missing.append(commit)
                continue
            _extract_source_snapshot(archive_path, temporary / "source" / commit)
            archive_path.unlink()
            included.append(commit)
        for name in SOURCE_LOCKFILES:
            if not (temporary / "source" / current / name).is_file():
                raise ValueError("Current source snapshot is missing required lockfiles")
        return {"current_commit": current, "included_commits": included, "missing_commits": missing}
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise ValueError("A readable Git source checkout is required for a full backup") from exc


def _source_coverage(check: dict, sources: Path) -> dict[str, bool]:
    coverage = {}
    for name, campaign in check["campaigns"].items():
        provenance = campaign["source_provenance"]
        commit, hashes = provenance.get("git_commit"), provenance.get("source_sha256")
        matches = isinstance(commit, str) and bool(COMMIT_PATTERN.fullmatch(commit)) and isinstance(hashes, dict) and bool(hashes)
        if matches:
            for relative, expected in hashes.items():
                archives._safe_name(relative)
                path = sources / commit / relative
                if not path.is_file() or archives._sha(path) != expected:
                    matches = False
                    break
        coverage[name] = bool(matches)
    return coverage


def _assert_unchanged(workspace: Path, files: list[tuple], indexed: dict) -> None:
    if _workspace_files(workspace) != files:
        raise ValueError("Workspace changed during backup; retry after all writers stop")
    for name, path, _ in files:
        if path.is_symlink() or archives._sha(path) != indexed[name]["sha256"]:
            raise ValueError("Workspace changed during backup; retry after all writers stop")


def _write_snapshot(path: Path, files: list[tuple], source_info: dict) -> dict:
    index = {"schema_version": 1, "kind": FORMAT_KIND,
             "created_at": datetime.now(timezone.utc).isoformat(),
             "excluded": ["exports without a campaign manifest (regular ZIP download cache only)",
                          "workers/*.lock (live OS locks)"],
             "sources": source_info, "files": {}}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        total = 0
        seen = set()
        for name, source, stamp in files:
            if name.casefold() in seen or len(seen) >= archives.MAX_FILES:
                raise ValueError("Backup exceeds its file limit or contains colliding paths")
            seen.add(name.casefold())
            current = source.stat()
            if source.is_symlink() or (current.st_size, current.st_mtime_ns, current.st_ino) != stamp:
                raise ValueError("Evidence changed during backup")
            content = source.read_bytes()
            total += len(content)
            if len(content) > archives.MAX_FILE_BYTES or total > archives.MAX_TOTAL_BYTES:
                raise ValueError("Backup exceeds its size limit")
            index["files"][name] = {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
            archive.writestr(name, content)
        archive.writestr(INDEX_NAME, json.dumps(index, ensure_ascii=True, indent=2, allow_nan=False).encode())
    return index


def export_workspace(workspace: str | Path, source_root: str | Path, output_path: str | Path) -> dict[str, Any]:
    """Snapshot quiescent research data and immutable Git source revisions.

    The live workbench additionally excludes all UI mutations using its locks.
    CLI callers must stop all writers first. No model calls or repair operations
    occur. A missing historical commit is explicitly reported, never invented.
    """
    workspace, source_root, output_path = Path(workspace), Path(source_root), Path(output_path)
    reject_symlinks(workspace)
    if not workspace.is_dir():
        raise ValueError("Workspace must be an existing directory")
    if output_path.resolve().is_relative_to(workspace.resolve()):
        raise ValueError("Workspace backup must be written outside the live workspace")
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError("Backup output already exists")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ExitStack() as stack, tempfile.TemporaryDirectory(prefix="security-lab-backup-") as scratch:
        _check_no_active_workers(workspace, stack)
        files = _workspace_files(workspace)
        check = _check_workspace(workspace)
        temporary = Path(scratch)
        source_info = _freeze_sources(source_root, temporary, check)
        source_files = [(SOURCE_PREFIX + name, path, stamp) for name, path, stamp in archives._export_files(temporary / "source")]
        handle, name = tempfile.mkstemp(prefix=".workspace-", suffix=".zip", dir=output_path.parent)
        os.close(handle)
        candidate = Path(name)
        try:
            index = _write_snapshot(candidate, files + source_files, source_info)
            _assert_unchanged(workspace, files, index["files"])
            if _git(source_root, "rev-parse", "HEAD").decode().strip() != source_info["current_commit"] or _git(source_root, "status", "--porcelain", "--untracked-files=no").strip():
                raise ValueError("Source checkout changed during backup")
            report = verify_workspace_backup(candidate)
            if set(report["campaigns"]) != set(check["campaigns"]):
                raise ValueError("Workspace campaign inventory differs from the verified backup")
            with candidate.open("rb+") as stream:
                os.fsync(stream.fileno())
            os.link(candidate, output_path)
            return {**report, "archive_path": str(output_path)}
        finally:
            candidate.unlink(missing_ok=True)


def _workspace_index(archive: zipfile.ZipFile, names: dict) -> dict:
    if INDEX_NAME not in names:
        raise ValueError("Workspace backup index missing")
    index = archives._json(archives._read_member(archive, names[INDEX_NAME]))
    if not isinstance(index, dict) or type(index.get("schema_version")) is not int or index["schema_version"] != 1 or index.get("kind") != FORMAT_KIND:
        raise ValueError("Unsupported workspace backup schema")
    files = index.get("files")
    if not isinstance(files, dict) or set(files) != set(names) - {INDEX_NAME}:
        raise ValueError("Workspace backup inventory mismatch")
    if any(not name.startswith(("workspace/", SOURCE_PREFIX)) for name in files):
        raise ValueError("Unexpected workspace backup path")
    _validate_source_info(index.get("sources"), files)
    return index


def _validate_source_info(sources: Any, files: dict) -> None:
    if not isinstance(sources, dict) or not isinstance(sources.get("current_commit"), str) or not COMMIT_PATTERN.fullmatch(sources["current_commit"]):
        raise ValueError("Invalid source snapshot metadata")
    for field in ("included_commits", "missing_commits"):
        values = sources.get(field)
        if not isinstance(values, list) or len(values) > MAX_SOURCE_COMMITS or any(not isinstance(value, str) or not COMMIT_PATTERN.fullmatch(value) for value in values) or len(set(values)) != len(values):
            raise ValueError("Invalid source snapshot revisions")
    included = set(sources["included_commits"])
    if sources["current_commit"] not in included or included.intersection(sources["missing_commits"]):
        raise ValueError("Inconsistent source snapshot revisions")
    actual = {name.split("/")[1] for name in files if name.startswith(SOURCE_PREFIX)}
    if actual != included:
        raise ValueError("Source snapshot inventory mismatch")


def _verify_into(path: Path, destination: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > archives.MAX_ARCHIVE_BYTES:
        raise ValueError("Invalid or oversized workspace backup")
    try:
        with zipfile.ZipFile(path) as archive:
            names = archives._archive_members(archive)
            index = _workspace_index(archive, names)
            archives._extract_verified_members(archive, names, index["files"], destination)
        workspace = destination / "workspace"
        workspace.mkdir(exist_ok=True)
        _workspace_files(workspace)
        check = _check_workspace(workspace)
        for name in SOURCE_LOCKFILES:
            if not (destination / "source" / index["sources"]["current_commit"] / name).is_file():
                raise ValueError("Required source lockfiles missing")
        coverage = _source_coverage(check, destination / "source")
        return {"verified": True, "authenticity_verified": False, "schema_version": 1,
                "archive_sha256": archives._sha(path), "files": len(index["files"]),
                "expanded_bytes": sum(item["size"] for item in index["files"].values()),
                "source_snapshots": index["sources"], "campaign_source_verified": coverage,
                "source_evidence_complete": all(coverage.values()) and not index["sources"]["missing_commits"],
                **check}
    except (zipfile.BadZipFile, zipfile.LargeZipFile, UnicodeError, OSError, KeyError, TypeError) as exc:
        raise ValueError("Invalid or inconsistent workspace backup") from exc


def verify_workspace_backup(path: str | Path) -> dict[str, Any]:
    """Check bounded paths, exact inventory, hashes and shared evidence validators."""
    with tempfile.TemporaryDirectory(prefix="security-lab-backup-check-") as temporary:
        return _verify_into(Path(path), Path(temporary))


def restore_workspace_backup(path: str | Path, destination: str | Path) -> dict[str, Any]:
    """Exclusively reserve a new container, then publish its snapshot atomically."""
    path, destination = Path(path), Path(destination)
    reject_symlinks(destination)
    if destination.exists():
        raise FileExistsError("Restore destination already exists; use a new separate directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".workspace-restore-", dir=destination.parent))
    try:
        report = _verify_into(path, temporary)
        original = temporary / "original-backup.zip"
        shutil.copyfile(path, original)
        if archives._sha(original) != report["archive_sha256"]:
            raise ValueError("Backup changed during restoration")
        receipt = {**report, "restored_at": datetime.now(timezone.utc).isoformat(), "original_archive": original.name}
        (temporary / "restore-receipt.json").write_text(json.dumps(receipt, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        # mkdir is the no-clobber reservation on POSIX and Windows. Renaming a
        # directory directly onto destination could replace a rival empty dir.
        destination.mkdir(exist_ok=False)
        snapshot = destination / "snapshot"
        try:
            temporary.rename(snapshot)
        except BaseException:
            try:
                destination.rmdir()  # only removes our still-empty reservation
            except OSError:
                pass  # retain unexpected concurrent contents, never delete them
            raise
        return {**report, "destination": str(destination), "workspace": str(snapshot / "workspace"),
                "original_archive": str(snapshot / original.name)}
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify and restore isolated research workspace backups; no model calls.")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Run only after every workspace writer has stopped")
    export.add_argument("--workspace", required=True, type=Path)
    export.add_argument("--source", default=Path(__file__).resolve().parents[2], type=Path)
    export.add_argument("--output", required=True, type=Path)
    export.add_argument("--writers-stopped", required=True, action="store_true", help="Acknowledge maintenance mode; not a substitute for stopping writers")
    verify = commands.add_parser("verify")
    verify.add_argument("archive", type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("archive", type=Path)
    restore.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            report = export_workspace(args.workspace, args.source, args.output)
        elif args.command == "verify":
            report = verify_workspace_backup(args.archive)
        else:
            report = restore_workspace_backup(args.archive, args.destination)
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"Backup failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
