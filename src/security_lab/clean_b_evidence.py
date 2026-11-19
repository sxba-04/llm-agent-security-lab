"""Read-only verification of the paid, single-use development campaign and its shared costs."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

from . import archives
from .batch import MANIFEST_FILE, digest, load_results
from .budget import BudgetLedger, euros
from .clean_b_run import ATTEMPT, CAMPAIGN, LEDGER, PLAN_V1
from .contracts import BudgetExceeded
from .documents import reject_symlinks

def unpublished_paid_write(path: Path, studies: Path) -> bool:
    """Only exact names emitted by the atomic writers after a paid marker exists."""
    relative = path.relative_to(studies).as_posix()
    return bool(re.fullmatch(
        r"clean-b-v1/(?:cases\.snapshot\.json|manifest\.json|summary\.json|records/run-[0-9]{5}\.json|"
        r"events/run-[0-9]{5}\.jsonl)\.[0-9a-f]{16}\.tmp|budget\.json\.[0-9a-f]{32}\.tmp|"
        r"clean-b-v1\.attempt\.json\.[0-9a-f]{16}\.tmp", relative))


def _attempt(raw: bytes) -> dict:
    attempt = archives._json(raw)
    if not isinstance(attempt, dict) or attempt.get("kind") != "clean_b_paid_attempt":
        raise ValueError("Invalid paid clean B attempt")
    plan = attempt.get("plan")
    if (not isinstance(plan, dict) or plan.get("plan_sha256") != PLAN_V1
            or digest({k: v for k, v in plan.items() if k != "plan_sha256"}) != PLAN_V1
            or attempt.get("approved_plan_sha256") != PLAN_V1 or attempt.get("campaign") != CAMPAIGN.as_posix()
            or attempt.get("provider_config") != {"provider": "openai", **plan["model_profile"], "enabled": True}
            or not isinstance(attempt.get("attempt_id"), str) or not re.fullmatch("[0-9a-f]{32}", attempt["attempt_id"])):
        raise ValueError("Paid clean B marker differs from the fixed plan or profile")
    provenance = attempt.get("provenance")
    if (not isinstance(provenance, dict) or not isinstance(provenance.get("git_commit"), str)
            or not re.fullmatch("[0-9a-f]{40}", provenance["git_commit"])
            or not isinstance(provenance.get("source_sha256"), dict) or not provenance["source_sha256"]):
        raise ValueError("Missing source provenance in paid clean B marker")
    for name, value in provenance["source_sha256"].items():
        archives._safe_name(name)
        if not isinstance(value, str) or not re.fullmatch("[0-9a-f]{64}", value):
            raise ValueError("Invalid source provenance in paid clean B marker")
    return attempt


def _reservations(workspace: Path, attempt: dict) -> tuple[dict, dict]:
    path = reject_symlinks(workspace / LEDGER, workspace)
    if not path.is_file() or path.stat().st_size > archives.MAX_FILE_BYTES:
        raise ValueError("Missing or oversized shared ledger for paid clean B attempt")
    try:
        entries = BudgetLedger(path)._load(require_existing=True)["reservations"]
    except BudgetExceeded as error:
        raise ValueError("Invalid shared ledger for paid clean B attempt") from error
    selected = {}
    indices = []
    for key, entry in entries.items():
        meta = entry.get("metadata", {})
        if not isinstance(meta, dict):
            raise ValueError("Invalid reservation metadata in shared study ledger")
        if meta.get("study_plan_sha256") != PLAN_V1 and meta.get("study_attempt_id") != attempt["attempt_id"]:
            continue
        index = meta.get("study_request_index")
        if (meta.get("study_plan_sha256") != PLAN_V1 or meta.get("study_attempt_id") != attempt["attempt_id"]
                or type(index) is not int or meta.get("model") != attempt["provider_config"]["model"]):
            raise ValueError("Paid clean B reservation belongs to a different attempt, plan or model")
        indices.append(index)
        selected[key] = entry
    if (sorted(indices) != list(range(1, len(indices) + 1))
            or len(indices) > attempt["provider_config"]["max_requests"]):
        raise ValueError("Invalid paid clean B reservation sequence")
    return entries, selected


def _receipt_ids(records: list[dict], reservations: dict, *, paid_series: bool = False) -> set[str]:
    seen = set()
    for record in records:
        for event in record["events"]:
            if event["type"] != "model_response":
                continue
            usage = event["data"]["usage"]
            key = usage.get("reservation_id")
            entry = reservations.get(key)
            if entry is None or key in seen or euros(usage["reserved_eur"]) != euros(entry["reserved_eur"]):
                raise ValueError("Model receipt differs from its shared ledger reservation")
            if paid_series:
                metadata = entry["metadata"]
                if (any(usage.get(k) != metadata[k] for k in ("study_attempt_id", "study_plan_sha256", "study_request_index"))
                        or type(usage.get("study_request_index")) is not int or usage["study_request_index"] != len(seen) + 1):
                    raise ValueError("Model receipt differs from the paid request index, attempt or plan")
            if usage.get("accounting") not in {"reported_usage", "reservation_retained", "settlement_failed"}:
                raise ValueError("Unknown model receipt accounting state")
            if usage.get("accounting") == "reported_usage" and (
                    entry["state"] != "settled"
                    or euros(usage["estimated_cost_eur"], allow_zero=True) != euros(entry["amount_eur"], allow_zero=True)):
                raise ValueError("Model receipt differs from its shared ledger settlement")
            seen.add(key)
    return seen


def verify_pilot_ledger(workspace: Path, reservations: dict) -> set[str]:
    """Bind the immutable A17 originals to an already loaded ledger, without acquiring a second lock."""
    pilot = reject_symlinks(workspace / "studies/luna-clean-first", workspace)
    if not pilot.exists():
        return set()

    def read(name: str, limit: int) -> bytes:
        path = reject_symlinks(pilot / name, workspace)
        if not path.is_file() or path.stat().st_size > limit:
            raise ValueError("Incomplete or oversized A17 evidence")
        return path.read_bytes()

    receipt = archives._json(read("receipt.json", 4096))
    raw = read("result.json", archives.MAX_FILE_BYTES)
    if (hashlib.sha256(read("attempt.json", 1024 * 1024)).hexdigest() != receipt["attempt_sha256"]
            or hashlib.sha256(raw).hexdigest() != receipt["result_sha256"]):
        raise ValueError("A17 originals differ from their receipt")
    result = archives._json(raw)
    if (result.get("case_id") != "DEV-G1-01" or result.get("variant") != "P" or result.get("is_mock") is not False
            or digest(result["events"]) != receipt["events_digest"] or result["status"] != receipt["status"]
            or result["technical_acceptance"] != receipt["technical_acceptance"]):
        raise ValueError("A17 result differs from the original evidence")
    seen = _receipt_ids([result], reservations)
    if result["status"] == "completed" and (not seen or len(seen) != result["model_calls"]):
        raise ValueError("A17 receipts do not cover the recorded calls")
    return seen


def _verify_record(record: dict, case: dict, plan: dict) -> None:
    if (record.get("original_article") != case["articles"]["clean"] or record.get("user_request") != case["user_request"]
            or record.get("expected") != case["expected"]):
        raise ValueError("Paid clean B record differs from its pinned case")
    if (record.get("is_mock") is not False or record.get("provider") != "openai"
            or record.get("model") != plan["model_profile"]["model"]):
        raise ValueError("Paid clean B record differs from the fixed model profile")
    requests = sum(e["type"] == "model_request" for e in record["events"])
    responses = sum(e["type"] == "model_response" for e in record["events"])
    unanswered = sum(e["type"] == "model_error" and e["data"].get("kind") in {"provider_error", "budget_exhausted"}
                     for e in record["events"])
    if (type(record.get("model_calls")) is not int or requests != record["model_calls"]
            or requests > plan["limits"]["max_model_calls"] or unanswered > 1 or requests != responses + unanswered
            or (record["status"] == "completed" and (not responses or unanswered))):
        raise ValueError("Paid clean B receipts do not cover the recorded calls")


def _verify_records(campaign: Path, attempt: dict, checksum: str, reservations: dict) -> tuple[str, int, list[str]]:
    plan = attempt["plan"]
    manifest = archives._json((campaign / MANIFEST_FILE).read_bytes())
    if (manifest.get("provider_config") != {**attempt["provider_config"], "clean_b_attempt_sha256": checksum}
            or manifest.get("schedule") != plan["schedule"] or manifest.get("limits") != plan["limits"]
            or manifest.get("order_seed") != plan["order_seed"] or manifest.get("cases_sha256") != plan["clean_cases_sha256"]
            or any(manifest["provenance"].get(k) != attempt["provenance"][k] for k in ("git_commit", "source_sha256"))):
        raise ValueError("Paid clean B campaign differs from the original attempt")
    records = load_results(campaign)
    cases = {c["case_id"]: c for c in archives._json((campaign / "cases.snapshot.json").read_bytes())}
    for record in records:
        _verify_record(record, cases[record["case_id"]], plan)
    seen = _receipt_ids(records, reservations, paid_series=True)
    state = manifest["state"]
    stopping = {"budget_exhausted", "technical_error"}
    if ((state == "stopped" and (not records or records[-1]["status"] not in stopping))
            or (state == "completed" and any(r["status"] in stopping | {"cancelled"} for r in records))):
        raise ValueError("Paid clean B campaign state differs from its recorded outcomes")
    if state == "completed" and (not seen or seen != reservations.keys()
                                 or any(e["state"] != "settled" for e in reservations.values())):
        raise ValueError("Completed paid clean B campaign has outstanding or unrecorded requests")
    if state == "stopped" and set(reservations) - seen:
        uncertain = any(e["type"] == "model_error" and e["data"].get("kind") == "provider_error"
                        for e in records[-1]["events"]) if records else False
        if not uncertain or len(reservations) != len(seen) + 1:
            raise ValueError("Stopped paid clean B campaign has unrelated unrecorded requests")
    unindexed = []
    if state == "running":
        indexed = {v[k] for v in manifest["runs"] for k in ("path", "events_path")}
        unindexed = sorted(p.relative_to(campaign).as_posix() for sub, suffix in (("records", "*.json"), ("events", "*.jsonl"))
                           for p in (campaign / sub).glob(suffix) if p.relative_to(campaign).as_posix() not in indexed)
        if unindexed and unindexed != [f"records/run-{len(records) + 1:05d}.json"]:
            raise ValueError("Unexpected unindexed files in interrupted paid clean B campaign")
    return ("interrupted" if state == "running" else state), len(records), unindexed


def _verify_initial_campaign(campaign: Path, plan: dict) -> None:
    if not campaign.is_dir():
        raise ValueError("Invalid partial paid clean B campaign directory")
    for path in campaign.iterdir():
        reject_symlinks(path, campaign)
        if (not path.is_file() or (path.name != "cases.snapshot.json"
                and not re.fullmatch(r"(?:cases\.snapshot|manifest)\.json\.[a-f0-9]{16}\.tmp", path.name))):
            raise ValueError("Unexpected paid clean B evidence before its first manifest")
    snapshot = campaign / "cases.snapshot.json"
    if snapshot.exists() and digest(archives._json(snapshot.read_bytes())) != plan["clean_cases_sha256"]:
        raise ValueError("Partial paid clean B case snapshot differs from its plan")


def verify_paid_attempt(workspace: Path) -> dict | None:
    """Read the consumed start without acquiring ledger locks, changing evidence or resuming a run."""
    marker = reject_symlinks(workspace / ATTEMPT, workspace)
    campaign = reject_symlinks(workspace / CAMPAIGN, workspace)
    if not marker.exists() and not campaign.exists():
        return None
    if not marker.is_file() or marker.stat().st_size > 1024 * 1024:
        raise ValueError("Missing or invalid paid clean B attempt")
    raw = marker.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    try:
        attempt = _attempt(raw)
        entries, reservations = _reservations(workspace, attempt)
        if verify_pilot_ledger(workspace, entries).intersection(reservations):
            raise ValueError("A17 and paid clean B share a reservation")
        manifest = reject_symlinks(campaign / MANIFEST_FILE, workspace)
        state, recorded, unindexed = "interrupted", 0, []
        if manifest.is_file():
            reject_symlinks(campaign / "cases.snapshot.json", workspace)
            state, recorded, unindexed = _verify_records(campaign, attempt, checksum, reservations)
        elif campaign.exists():
            _verify_initial_campaign(campaign, attempt["plan"])
    except (KeyError, TypeError, AttributeError, RecursionError) as error:
        raise ValueError("Malformed paid clean B evidence") from error
    fragments = sorted(p.relative_to(workspace).as_posix() for p in marker.parent.rglob("*.tmp")
                       if unpublished_paid_write(p, marker.parent))
    return {"attempt_sha256": checksum, "attempt_id": attempt["attempt_id"], "state": state,
            "unpublished_writes": fragments, "unindexed_campaign_files": unindexed,
            "campaign_present": manifest.is_file(), "recorded_runs": recorded, "planned_runs": len(attempt["plan"]["schedule"]),
            "reservations": len(reservations), "pending_reservations": sum(e["state"] == "reserved" for e in reservations.values()),
            "source_provenance": attempt["provenance"]}
