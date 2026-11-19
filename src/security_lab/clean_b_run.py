"""Server-side, single-use execution of the approved clean B development plan."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from threading import Lock
from uuid import uuid4

from .batch import digest, provenance, run_batch, write_json_new
from .budget import BudgetLedger, PROJECT_CEILING_EUR
from .clean_b import prepare
from .documents import reject_symlinks
from .jobs import _worker_lease
from .providers import OpenAIModel

CAMPAIGN = Path("studies/clean-b-v1")
ATTEMPT = CAMPAIGN.with_suffix(".attempt.json")
LEDGER = Path("studies/budget.json")
WORKER_LOCK = Path("workers/clean-b-v1.lock")
PLAN_V1 = "f926db9da2ea2ba15d2449d1cfa552907cf6260af4bf4798650136b5f335dff3"


@dataclass(frozen=True, repr=False)
class PreparedCleanBRun:
    workspace: Path
    attempt_sha256: str
    cases_json: bytes
    model: OpenAIModel
    _started: Lock = field(default_factory=Lock, init=False)


def _writer_lease(workspace: Path):
    lock = reject_symlinks(workspace / WORKER_LOCK, workspace)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lease = _worker_lease(lock)
    if lease is None:
        raise FileExistsError("A workspace backup or clean B worker already holds the writer lock")
    return lease


def prepare_start(workspace: Path, approved_plan_sha256: str, api_key: str) -> PreparedCleanBRun:
    """Validate the server's fixed inputs, then consume this workspace's single start."""
    from .clean_b_evidence import verify_pilot_ledger

    workspace = reject_symlinks(Path(workspace))
    marker = reject_symlinks(workspace / ATTEMPT, workspace)
    campaign = reject_symlinks(workspace / CAMPAIGN, workspace)
    if marker.exists() or campaign.exists():
        raise FileExistsError("The clean B series already has an attempt in this workspace")
    plan, cases = prepare()
    if plan["plan_sha256"] != PLAN_V1 or approved_plan_sha256 != PLAN_V1:
        raise ValueError("The server approval does not match the fixed clean B plan")
    source = provenance()
    if not re.fullmatch(r"[0-9a-f]{40}", source.get("git_commit") or "") or not source.get("source_sha256"):
        raise ValueError("The clean B run needs source provenance for subsequent verification")

    profile = {**plan["model_profile"], "enabled": True}
    ledger = BudgetLedger(reject_symlinks(workspace / LEDGER, workspace), PROJECT_CEILING_EUR,
                          profile["run_budget_eur"])
    reject_symlinks(ledger.lock_path, workspace)
    attempt_id = uuid4().hex
    model = OpenAIModel(profile, api_key, ledger, study_attempt_id=attempt_id,
                        study_plan_sha256=approved_plan_sha256)
    attempt = {"kind": "clean_b_paid_attempt", "created_at": datetime.now(timezone.utc).isoformat(),
               "attempt_id": attempt_id, "approved_plan_sha256": approved_plan_sha256,
               "campaign": CAMPAIGN.as_posix(), "plan": plan, "provider_config": {"provider": "openai", **profile},
               "provenance": source}
    cases_json = json.dumps(cases, ensure_ascii=False, allow_nan=False).encode("utf-8")
    with ledger.preflight_study(profile["run_budget_eur"], study_plan_sha256=approved_plan_sha256) as reservations:
        verify_pilot_ledger(workspace, reservations)
        with _writer_lease(workspace):
            write_json_new(marker, attempt)
            raw = marker.read_bytes()
            if json.loads(raw) != attempt:
                raise ValueError("The newly published clean B attempt differs from preparation")
    return PreparedCleanBRun(workspace, hashlib.sha256(raw).hexdigest(), cases_json, model)


def execute(job: PreparedCleanBRun, *, should_cancel: Callable[[], bool] | None = None,
            on_progress: Callable[[dict], None] | None = None) -> dict:
    """Execute a prepared job once. A crash, cancellation or storage failure consumes the attempt."""
    # Deliberately never release: a queued job must not be submitted again after a failure.
    if not job._started.acquire(blocking=False):
        raise FileExistsError("This prepared clean B job was already consumed")
    workspace = job.workspace
    with _writer_lease(workspace):
        marker = reject_symlinks(workspace / ATTEMPT, workspace)
        raw = marker.read_bytes()
        if hashlib.sha256(raw).hexdigest() != job.attempt_sha256:
            raise ValueError("The clean B attempt changed after preparation")
        attempt = json.loads(raw)
        plan = attempt["plan"]
        cases = json.loads(job.cases_json)
        if digest(cases) != plan["clean_cases_sha256"]:
            raise ValueError("The prepared cases differ from the clean B plan")
        campaign = reject_symlinks(workspace / CAMPAIGN, workspace)
        ledger = reject_symlinks(workspace / LEDGER, workspace)
        reject_symlinks(ledger.with_name(ledger.name + ".lock"), workspace)

        def check_progress(current: dict) -> None:
            if current["state"] == "running" and current["completed_runs"] == 0:
                source_changed = any(current["provenance"][key] != attempt["provenance"][key]
                                     for key in ("git_commit", "source_sha256"))
                if current["schedule"] != plan["schedule"] or source_changed:
                    raise ValueError("The execution schedule or source changed after approval")
            if on_progress is not None:
                on_progress(current)

        return run_batch(cases, campaign, lambda _case, _source: job.model, variants=["B"], sources=["clean"],
                         repeats=1, seed=plan["order_seed"], **plan["limits"],
                         should_cancel=should_cancel, on_progress=check_progress,
                         provider_config={**attempt["provider_config"], "clean_b_attempt_sha256": job.attempt_sha256})
