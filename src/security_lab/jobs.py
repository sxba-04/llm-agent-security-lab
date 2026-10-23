"""One cancellable mock campaign worker and safe discovery of local campaigns."""
from __future__ import annotations

import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import stat
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any
import uuid

from . import batch
from .documents import copy_document_sources, reject_symlinks
from .models import ScriptedModel

NEW_ID = re.compile(r"campaign-[0-9a-f]{32}\Z")
ACTIVE_STATES = {"queued", "running", "cancelling"}
MAX_LIST_CACHE_ENTRIES = 128
MAX_FINGERPRINT_ENTRIES = 10_000


def _worker_lease(path: Path):
    """Acquire a nonblocking OS lock released automatically on process death.

    A PID alone is insufficient: it can be reused and does not prove that a
    worker in another workbench process has stopped. Both supported platforms
    hold this lock for the entire worker lifetime, including final persistence.
    """
    reject_symlinks(path)
    stream = path.open("a+b")
    try:
        if path.stat().st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        stream.close()
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            return None
        raise
    except BaseException:
        stream.close()
        raise
    return stream


def checked_tree(directory: Path) -> Path:
    directory = reject_symlinks(Path(directory))
    if directory.exists():
        for path in directory.rglob("*"):
            reject_symlinks(path, directory)
    return directory


class CampaignJobs:
    def __init__(self, workspace: Path):
        self.workspace = reject_symlinks(Path(workspace))
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.campaigns = reject_symlinks(self.workspace / "campaigns", self.workspace)
        self.campaigns.mkdir(exist_ok=True)
        self.documents = reject_symlinks(self.workspace / "documents", self.workspace)
        self.workers = reject_symlinks(self.workspace / "workers", self.workspace)
        self.workers.mkdir(exist_ok=True)
        self._instance_id = uuid.uuid4().hex
        self._lock = threading.RLock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._active: str | None = None
        # Only lightweight listing results are cached, never records or a
        # replacement for explicit brief()/record/archive integrity checks.
        self._list_cache: OrderedDict[str, tuple[bytes, dict[str, Any]]] = OrderedDict()

    @property
    def running(self) -> bool:
        with self._lock:
            return self._active is not None

    def is_active(self, campaign_id: str) -> bool:
        with self._lock:
            return self._active == campaign_id

    def _discover(self) -> dict[str, Path]:
        discovered = {}
        for parent in (self.workspace, self.campaigns):
            reject_symlinks(parent, self.workspace)
            for path in parent.iterdir():
                try:
                    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                        continue
                    if not path.is_dir():
                        continue
                    manifest = path / "manifest.json"
                    if not manifest.exists() and not manifest.is_symlink():
                        # An owned UI campaign that lost its manifest still
                        # needs a damaged row; unrelated folders do not.
                        if parent != self.campaigns or not NEW_ID.fullmatch(path.name) or not (self.workers / f"{path.name}.json").exists():
                            continue
                except OSError:
                    # Include an inaccessible candidate so brief() can report
                    # its failure without aborting discovery of its neighbours.
                    pass
                if parent == self.campaigns and NEW_ID.fullmatch(path.name):
                    identifier = path.name
                else:
                    identifier = "legacy-" + hashlib.sha256(path.relative_to(self.workspace).as_posix().encode()).hexdigest()[:24]
                discovered[identifier] = path
        with self._lock:
            discovered.update({identifier: job["path"] for identifier, job in self._jobs.items()})
        return discovered

    def directory(self, campaign_id: str) -> Path:
        path = self._discover().get(campaign_id)
        if path is None:
            raise KeyError(campaign_id)
        return checked_tree(path)

    def _owner(self, campaign_id: str) -> dict[str, Any] | None:
        if not NEW_ID.fullmatch(campaign_id):
            return None
        path = reject_symlinks(self.workers / f"{campaign_id}.json", self.workspace)
        if not path.exists():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(value, dict) or value.get("schema_version") != 1
                or value.get("kind") != "workbench_mock_worker" or value.get("campaign_id") != campaign_id
                or not isinstance(value.get("instance_id"), str) or not value["instance_id"]):
            raise ValueError("Invalid workbench worker ownership")
        return value

    def _worker_info(self, campaign_id: str, state: str) -> dict[str, Any]:
        with self._lock:
            if self._active == campaign_id:
                return {"managed_worker": True, "worker_active": True, "can_cancel": True}
        owner = self._owner(campaign_id)
        if owner is None:
            return {"managed_worker": False, "worker_active": None if state in ACTIVE_STATES else False,
                    "can_cancel": False}
        lease = _worker_lease(self.workers / f"{campaign_id}.lock")
        if lease is None:
            return {"managed_worker": True, "worker_active": True, "can_cancel": False}
        lease.close()
        return {"managed_worker": True, "worker_active": False, "can_cancel": False}

    def _recover_orphan(self, campaign_id: str, directory: Path, value: dict[str, Any]) -> dict[str, Any]:
        """Close only a positively identified UI worker whose OS lease is free."""
        with self._lock:
            if self._active == campaign_id or value.get("state") != "running":
                return value
            owner = self._owner(campaign_id)
            if owner is None:
                return value  # CLI/old unowned campaigns may still be running.
            lease = _worker_lease(self.workers / f"{campaign_id}.lock")
            if lease is None:
                return value  # Another workbench process is demonstrably alive.
            try:
                path = directory / "manifest.json"
                original = path.read_bytes()
                manifest = json.loads(original)
                if manifest.get("state") != "running":
                    return manifest
                records = batch.load_results(directory)
                # Running manifests may temporarily omit the next record. Do
                # not silently drop such crash evidence when closing the set.
                indexed = {entry["path"] for entry in manifest["runs"]}
                indexed.update(entry.get("events_path", "events/" + Path(entry["path"]).stem + ".jsonl")
                               for entry in manifest["runs"])
                actual = {path.relative_to(directory).as_posix()
                          for folder, suffix in (("records", "*.json"), ("events", "*.jsonl"))
                          for path in (directory / folder).glob(suffix)}
                if actual - indexed:
                    raise ValueError("Unindexed crash evidence requires manual inspection")
                if path.read_bytes() != original:
                    raise ValueError("Campaign changed during crash recovery")
                receipt = directory / "provenance" / ("recovery-" + uuid.uuid4().hex)
                receipt.mkdir(parents=True, exist_ok=False)
                batch._atomic_bytes(receipt / "manifest.original.json", original)
                summary_path = directory / "summary.json"
                summary_original = summary_path.read_bytes() if summary_path.exists() else None
                if summary_original is not None:
                    batch._atomic_bytes(receipt / "summary.original.json", summary_original)
                recovery = {"schema_version": 1, "reason": "orphaned_workbench_worker",
                            "recovered_at": datetime.now(timezone.utc).isoformat(),
                            "worker_instance_id": owner["instance_id"], "verified_records": len(records),
                            "original_manifest_sha256": hashlib.sha256(original).hexdigest(),
                            "original_summary_sha256": hashlib.sha256(summary_original).hexdigest() if summary_original is not None else None}
                batch.write_json(receipt / "receipt.json", recovery)
                manifest.update(state="interrupted", recovery={**recovery, "receipt": receipt.relative_to(directory).as_posix()})
                batch.write_json(path, manifest)
                from .evaluation import summarize
                summary = summarize(records)
                summary.update(campaign_state="interrupted", planned_runs=len(manifest["schedule"]),
                               completed_runs=len(records), **batch.evidence_completeness(manifest))
                batch.write_json(summary_path, summary)
                return manifest
            finally:
                lease.close()

    def manifest(self, campaign_id: str) -> dict[str, Any]:
        path = self.directory(campaign_id) / "manifest.json"
        with self._lock:
            job = self._jobs.get(campaign_id)
            if not path.exists() and job:
                return copy.deepcopy(job["progress"])
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("Invalid campaign manifest")
        if (not isinstance(value.get("state"), str)
                or value.get("created_at") is not None and not isinstance(value["created_at"], str)
                or any(key in value and (type(value[key]) is not int or value[key] < 0)
                       for key in ("completed_runs", "planned_runs"))):
            raise ValueError("Invalid campaign display metadata")
        value = self._recover_orphan(campaign_id, path.parent, value)
        with self._lock:
            if job and job.get("failure"):
                value = {**value, "state": "failed", "error": "Der lokale Versuch konnte nicht abgeschlossen werden."}
        return value

    def brief(self, campaign_id: str) -> dict[str, Any]:
        manifest: dict[str, Any] = {}
        try:
            manifest = self.manifest(campaign_id)
            worker = self._worker_info(campaign_id, manifest.get("state", "unknown"))
            with self._lock:
                current = self._active == campaign_id
            if current:
                engineering_only = True
            else:
                records = batch.load_results(self.directory(campaign_id))
                engineering_only = all(record.get("is_mock") is True for record in records) if records else manifest.get("provider_config") is None
            return {"campaign_id": campaign_id, "created_at": manifest.get("created_at"),
                    "state": manifest.get("state", "unknown"),
                    "completed_runs": manifest.get("completed_runs", len(manifest.get("runs", []))),
                    "planned_runs": manifest.get("planned_runs", len(manifest.get("schedule", []))),
                    "engineering_only": engineering_only, "valid_evidence": True, **worker}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            # One corrupt/inaccessible campaign must not hide unrelated evidence
            # or prevent review discovery. Original files are never repaired here.
            try:
                worker = self._worker_info(campaign_id, str(manifest.get("state", "unknown")))
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                worker = {"managed_worker": False, "worker_active": None, "can_cancel": False}
            return {"campaign_id": campaign_id, "created_at": None, "state": "damaged",
                    "completed_runs": 0, "planned_runs": 0, "engineering_only": False,
                    "valid_evidence": False, "error": "Die Kampagnenbelege sind beschädigt oder unvollständig. Originaldateien bleiben unverändert; vor einer Auswertung ist eine Prüfung erforderlich.",
                    **worker}

    def _listing_fingerprint(self, campaign_id: str, directory: Path) -> bytes | None:
        """Stat a bounded tree without opening file contents or following links.

        This is a local change detector, not an integrity proof: explicit opens
        still verify hashes. Identity, size and nanosecond modification/change
        times catch ordinary rewrites, replacements and restored-mtime edits.
        Files can still change after a stat; hostile metadata preservation is
        outside this lightweight listing cache's guarantee.
        """
        directory = reject_symlinks(directory)
        digest = hashlib.sha256()

        def stamp(path: Path, name: str):
            try:
                value = path.lstat()
            except FileNotFoundError:
                digest.update(json.dumps([name, "missing"]).encode())
                return None
            attributes = getattr(value, "st_file_attributes", 0)
            fields = [name, value.st_dev, value.st_ino, value.st_mode, value.st_size,
                      value.st_mtime_ns, value.st_ctime_ns, attributes]
            digest.update(json.dumps(fields, ensure_ascii=True, separators=(",", ":")).encode())
            return value

        root_stat = stamp(directory, str(directory))
        if root_stat is None:
            return digest.digest()
        pending = [directory]
        count = 0
        while pending:
            parent = pending.pop()
            with os.scandir(parent) as entries:
                children = []
                for entry in entries:
                    count += 1
                    if count > MAX_FINGERPRINT_ENTRIES:
                        return None  # Fall back to fresh validation, no cache.
                    children.append(entry.name)
            for name in sorted(children):
                path = parent / name
                value = stamp(path, path.relative_to(directory).as_posix())
                if value is not None and stat.S_ISDIR(value.st_mode) and not (
                    getattr(value, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                ):
                    pending.append(path)
        # Ownership affects crash recovery and displayed worker capabilities.
        for suffix in ("json", "lock"):
            path = reject_symlinks(self.workers / f"{campaign_id}.{suffix}", self.workspace)
            stamp(path, "worker/" + path.name)
        return digest.digest()

    def _listed_brief(self, campaign_id: str, directory: Path) -> dict[str, Any]:
        try:
            before = self._listing_fingerprint(campaign_id, directory)
        except (OSError, ValueError):
            before = None
        with self._lock:
            cached = self._list_cache.get(campaign_id)
            if before is not None and cached is not None and cached[0] == before:
                self._list_cache.move_to_end(campaign_id)
                return copy.deepcopy(cached[1])
            self._list_cache.pop(campaign_id, None)
        result = self.brief(campaign_id)
        # Never cache a live/unknown worker. Process death changes its lease,
        # not necessarily file metadata, and must still trigger recovery.
        if (before is not None and result.get("worker_active") is False
                and result.get("state") in {"completed", "cancelled", "stopped", "interrupted", "failed", "damaged"}):
            try:
                after = self._listing_fingerprint(campaign_id, directory)
            except (OSError, ValueError):
                after = None
            if before == after:
                with self._lock:
                    self._list_cache[campaign_id] = (after, copy.deepcopy(result))
                    self._list_cache.move_to_end(campaign_id)
                    while len(self._list_cache) > MAX_LIST_CACHE_ENTRIES:
                        self._list_cache.popitem(last=False)
        return result

    def list(self) -> list[dict[str, Any]]:
        discovered = self._discover()
        with self._lock:
            for identifier in list(self._list_cache):
                if identifier not in discovered:
                    del self._list_cache[identifier]
        return sorted([self._listed_brief(identifier, directory) for identifier, directory in discovered.items()],
                      key=lambda row: row.get("created_at") or "", reverse=True)

    def start(self, cases: list[dict[str, Any]], *, variants: list[str], sources: list[str],
              repeats: int, seed: int, document_ids: list[str]) -> dict[str, Any]:
        with self._lock:
            if self._active is not None:
                raise RuntimeError("Es läuft bereits ein Versuch.")
            campaign_id = "campaign-" + uuid.uuid4().hex
            path = self.campaigns / campaign_id
            lease = _worker_lease(self.workers / f"{campaign_id}.lock")
            if lease is None:
                raise RuntimeError("Der lokale Worker konnte nicht reserviert werden.")
            owner = {"schema_version": 1, "kind": "workbench_mock_worker", "campaign_id": campaign_id,
                     "instance_id": self._instance_id, "pid": os.getpid(), "created_at": datetime.now(timezone.utc).isoformat()}
            try:
                batch.write_json(self.workers / f"{campaign_id}.json", owner)
            except BaseException:
                lease.close()
                raise
            cancel = threading.Event()
            job = {"path": path, "cancel": cancel, "progress": {
                "state": "queued", "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_runs": 0, "planned_runs": len(cases) * len(variants) * len(sources) * repeats,
                "runs": [], "schedule": [],
            }}
            self._jobs[campaign_id] = job
            self._active = campaign_id
            def progress(manifest: dict[str, Any]) -> None:
                # The first callback follows durable fixture/manifest writes and
                # precedes any model step, so cancelled runs keep PDF evidence.
                if not job.get("ownership_saved"):
                    batch.write_json(path / "worker.json", owner)
                    job["ownership_saved"] = True
                if document_ids and not job.get("sources_copied"):
                    copy_document_sources(self.documents, document_ids, path)
                    job["sources_copied"] = True
                with self._lock:
                    job["progress"] = copy.deepcopy(manifest)
            def execute() -> None:
                try:
                    batch.run_batch(cases, path, lambda case, source: ScriptedModel(case, source),
                                    variants=variants, sources=sources, repeats=repeats, seed=seed,
                                    should_cancel=cancel.is_set, on_progress=progress)
                except Exception:
                    with self._lock:
                        job["failure"] = True
                        job["progress"]["state"] = "failed"
                finally:
                    with self._lock:
                        self._active = None
                        lease.close()
            thread = threading.Thread(target=execute, name="security-lab-mock", daemon=True)
            job["thread"] = thread
            brief = self.brief(campaign_id)
            try:
                thread.start()
            except BaseException:
                job["failure"] = True
                self._active = None
                lease.close()
                raise
            return brief

    def cancel(self, campaign_id: str) -> dict[str, Any]:
        self.directory(campaign_id)
        with self._lock:
            job = self._jobs.get(campaign_id)
            if self._active != campaign_id or not job:
                return {"campaign_id": campaign_id, "state": self.manifest(campaign_id).get("state")}
            job["cancel"].set()
        return {"campaign_id": campaign_id, "state": "cancelling"}

    def shutdown(self) -> None:
        with self._lock:
            active = self._jobs.get(self._active) if self._active else None
            if active:
                active["cancel"].set()
        if active:
            active["thread"].join(timeout=5)
