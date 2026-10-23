"""One cancellable mock campaign worker and safe discovery of local campaigns."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import threading
from datetime import datetime, timezone
from typing import Any
import uuid

from . import batch
from .documents import copy_document_sources, reject_symlinks
from .models import ScriptedModel

NEW_ID = re.compile(r"campaign-[0-9a-f]{32}\Z")


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
        self._lock = threading.RLock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._active: str | None = None

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
                if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                    continue
                if not path.is_dir() or not (path / "manifest.json").is_file():
                    continue
                reject_symlinks(path / "manifest.json", self.workspace)
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

    def manifest(self, campaign_id: str) -> dict[str, Any]:
        path = self.directory(campaign_id) / "manifest.json"
        with self._lock:
            job = self._jobs.get(campaign_id)
            if not path.exists() and job:
                return copy.deepcopy(job["progress"])
        value = json.loads(path.read_text(encoding="utf-8"))
        with self._lock:
            if job and job.get("failure"):
                value = {**value, "state": "failed", "error": "Der lokale Versuch konnte nicht abgeschlossen werden."}
        return value

    def brief(self, campaign_id: str) -> dict[str, Any]:
        manifest = self.manifest(campaign_id)
        with self._lock:
            owned_mock = campaign_id in self._jobs
        if owned_mock:
            engineering_only = True
        else:
            records = batch.load_results(self.directory(campaign_id))
            engineering_only = all(record.get("is_mock") is True for record in records) if records else manifest.get("provider_config") is None
        return {"campaign_id": campaign_id, "created_at": manifest.get("created_at"),
                "state": manifest.get("state", "unknown"),
                "completed_runs": manifest.get("completed_runs", len(manifest.get("runs", []))),
                "planned_runs": manifest.get("planned_runs", len(manifest.get("schedule", []))),
                "engineering_only": engineering_only}

    def list(self) -> list[dict[str, Any]]:
        return sorted([self.brief(identifier) for identifier in self._discover()],
                      key=lambda row: row.get("created_at") or "", reverse=True)

    def start(self, cases: list[dict[str, Any]], *, variants: list[str], sources: list[str],
              repeats: int, seed: int, document_ids: list[str]) -> dict[str, Any]:
        with self._lock:
            if self._active is not None:
                raise RuntimeError("Es läuft bereits ein Versuch.")
            campaign_id = "campaign-" + uuid.uuid4().hex
            path = self.campaigns / campaign_id
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
            thread = threading.Thread(target=execute, name="security-lab-mock", daemon=True)
            job["thread"] = thread
            brief = self.brief(campaign_id)
            thread.start()
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
