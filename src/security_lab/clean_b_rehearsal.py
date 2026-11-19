"""Once per workspace, exercise the fixed clean B schedule with the local test model."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .batch import MANIFEST_FILE, load_results, run_batch, schedule, write_json_new
from .clean_b import prepare
from .documents import reject_symlinks
from .models import ScriptedModel


REHEARSAL = Path("studies/clean-b-rehearsal-v1")
ATTEMPT = REHEARSAL.with_suffix(".attempt.json")


def rehearse(workspace: Path) -> dict:
    """Publish a complete plan before creating the separate mock campaign."""
    campaign = reject_symlinks(workspace / REHEARSAL, workspace)
    attempt = reject_symlinks(workspace / ATTEMPT, workspace)
    if campaign.exists() or attempt.exists():
        raise FileExistsError("The clean B rehearsal already has evidence in this workspace")

    plan, cases = prepare()
    order = schedule(cases, ["B"], ["clean"], 1, plan["order_seed"])
    if order != plan["schedule"]:
        raise ValueError("The mock schedule differs from the fixed clean B plan")

    # The atomic file publication is the start claim. It survives a crash
    # before the campaign directory exists and is included in file-only backups.
    profile = {"provider": "mock", "engineering_only": True, "model": ScriptedModel.name}
    write_json_new(attempt, {"kind": "clean_b_offline_rehearsal", "plan": plan,
                             "provider_config": profile, "provider_cost_eur": "0",
                             "campaign": REHEARSAL.as_posix()})
    attempt_sha256 = hashlib.sha256(attempt.read_bytes()).hexdigest()
    manifest = run_batch(cases, campaign, ScriptedModel, variants=["B"], sources=["clean"],
                         repeats=1, seed=plan["order_seed"], **plan["limits"],
                         provider_config={**profile, "rehearsal_attempt_sha256": attempt_sha256})
    records = load_results(campaign)
    return {"state": manifest["state"], "plan_id": plan["plan_id"], "engineering_only": True,
            "provider_cost_eur": "0", "planned_runs": manifest["planned_runs"], "recorded_runs": len(records),
            "mock_model_calls": sum(record["model_calls"] for record in records),
            "tool_calls": sum(record["tool_calls"] for record in records),
            "attempt": ATTEMPT.as_posix(), "manifest": (REHEARSAL / MANIFEST_FILE).as_posix()}
