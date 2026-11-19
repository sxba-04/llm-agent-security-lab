"""Hosted controls for the once-only, pinned clean B series."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import os
from pathlib import Path
import threading

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from . import clean_b_run
from .budget import BudgetLedger
from .clean_b import CASE_SHA256, build_plan
from .clean_b_evidence import verify_paid_attempt, verify_pilot_ledger
from .contracts import ModelError
from .documents import reject_symlinks
from .hosted import HostedSettings, validate_fixed_start


def _status(state: str, recorded: int | None) -> dict:
    return {"state": state, "planned_runs": len(CASE_SHA256), "recorded_runs": recorded}


class HostedCleanB:
    def __init__(self, workspace: Path, settings: HostedSettings, study_slot: threading.Lock):
        self.workspace = workspace
        self.settings = settings
        self.study_slot = study_slot
        self._guard = threading.Lock()
        self._shutdown = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="clean-b")
        self._recorded: int | None = None

    def _approved(self) -> bool:
        return (self.settings.clean_b_approved_plan_sha256 == clean_b_run.PLAN_V1
                and self.settings.storage_mode == "persistent" and not self._shutdown.is_set()
                and bool(os.environ.get("OPENAI_API_KEY", "").strip()))

    def _readiness(self) -> str:
        if not self._approved():
            return "disabled"
        plan = build_plan()
        if plan["plan_sha256"] != self.settings.clean_b_approved_plan_sha256:
            return "unavailable"
        ledger = BudgetLedger(reject_symlinks(self.workspace / clean_b_run.LEDGER, self.workspace))
        if reject_symlinks(ledger.lock_path, self.workspace).exists():
            return "unavailable"
        reservations = ledger.review_study(plan["budget"]["proposed_run_cap_eur"], study_plan_sha256=plan["plan_sha256"])
        verify_pilot_ledger(self.workspace, reservations)
        return "ready"

    def status(self) -> dict:
        with self._guard:
            if self._recorded is not None:
                return _status("running", self._recorded)
            try:
                evidence = verify_paid_attempt(self.workspace)
                if evidence is None:
                    state = self._readiness()
                    return _status(state, None if state == "unavailable" else 0)
                state = evidence["state"]
                return _status("interrupted" if state == "cancelled" else state, evidence["recorded_runs"])
            except (OSError, ValueError, ModelError, KeyError, TypeError, RecursionError):
                return _status("unavailable", None)

    async def start_request(self, request: Request) -> dict:
        await validate_fixed_start(request, self.settings)
        return await run_in_threadpool(self.start)

    def start(self) -> dict:
        with self._guard, ExitStack() as release_on_error:
            if not self.study_slot.acquire(blocking=False):
                raise HTTPException(409, "Ein Modellversuch oder die Workspace-Sicherung läuft bereits.")
            release_on_error.callback(self.study_slot.release)
            try:
                for relative in (clean_b_run.ATTEMPT, clean_b_run.CAMPAIGN):
                    if reject_symlinks(self.workspace / relative, self.workspace).exists():
                        raise FileExistsError
                if not self._approved():
                    raise HTTPException(503, "Der feste B-Lauf ist nicht startbereit.")
                job = clean_b_run.prepare_start(self.workspace, self.settings.clean_b_approved_plan_sha256,
                                                os.environ["OPENAI_API_KEY"])
                self._executor.submit(self._run, job)
            except FileExistsError:
                raise HTTPException(409, "Der B-Start ist bereits belegt. Bitte den Status abrufen.") from None
            except (OSError, ValueError, RuntimeError, KeyError):
                raise HTTPException(503, "Start angehalten. Status, Freigabe und Budgetbelege prüfen.") from None
            # The durable claim and worker now own the slot until final persistence.
            release_on_error.pop_all()
            self._recorded = 0
            return _status("running", 0)

    def _progress(self, manifest: dict) -> None:
        with self._guard:
            self._recorded = manifest["completed_runs"]

    def _run(self, job: clean_b_run.PreparedCleanBRun) -> None:
        try:
            clean_b_run.execute(job, should_cancel=self._shutdown.is_set, on_progress=self._progress)
        finally:
            with self._guard:
                self._recorded = None
                self.study_slot.release()

    def shutdown(self) -> None:
        with self._guard:
            self._shutdown.set()
        self._executor.shutdown(wait=True)
