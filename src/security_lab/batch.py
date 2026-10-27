"""Paired randomized campaigns and immutable, hash-checked run records."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import random
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Callable

from . import __version__
from .contracts import Model

VARIANTS = ("B", "F", "P", "FP")
SOURCES = ("clean", "attack")


def digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8", errors="surrogatepass")
    return hashlib.sha256(raw).hexdigest()


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    try:
        with tmp.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        # Windows readers can briefly deny replacement of an open target. Keep
        # the same flushed temporary file and retry only its atomic publication,
        # never the model/tool work that produced it or unrelated I/O failures.
        deadline = time.monotonic() + 1.0
        delay = 0.01
        while True:
            try:
                tmp.replace(path)
                break
            except OSError as exc:
                if getattr(exc, "winerror", None) not in {5, 32, 33}:
                    raise
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise
                time.sleep(min(delay, remaining))
                delay = min(delay * 2, 0.1)
    finally:
        tmp.unlink(missing_ok=True)


def write_json(path: Path, value: Any) -> None:
    # JSON escapes preserve unpaired surrogate evidence without invalid UTF-8.
    raw = json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + "\n"
    _atomic_bytes(Path(path), raw.encode("utf-8"))


def write_json_new(path: Path, value: Any) -> None:
    """Publish a complete immutable JSON file without replacing any destination.

    A same-directory hard link provides atomic create-if-absent semantics on
    supported filesystems (including NTFS). There is deliberately no fallback
    to an exists-check followed by replace: another writer could win that race.
    Unsupported filesystems fail closed. A hard process termination may leave
    an identifiable .tmp file, but never a partially published final version.
    """
    content = (json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    created = False
    try:
        with temporary.open("xb") as stream:
            created = True
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        if created:
            temporary.unlink(missing_ok=True)


def provenance() -> dict:
    root = Path(__file__).resolve().parents[2]
    source_hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted((root / "src").rglob("*.py"))}
    for name in ("pyproject.toml", "uv.lock", ".python-version"):
        p = root / name
        if p.exists():
            source_hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    def git(*args: str) -> str | None:
        try:
            return subprocess.check_output(["git", *args], cwd=root, stderr=subprocess.DEVNULL,
                                           timeout=5, text=True).strip()
        except (OSError, subprocess.SubprocessError):
            return None
    return {"version": __version__, "python": sys.version, "git_commit": git("rev-parse", "HEAD"),
            "git_status": git("status", "--porcelain"), "source_sha256": source_hashes}


def schedule(cases: list[dict], variants: list[str], sources: list[str], repeats: int,
             seed: int) -> list[dict]:
    if not cases or type(repeats) is not int or repeats < 1 or repeats > 100:
        raise ValueError("At least one case and 1..100 repetitions are required")
    if not variants or not sources or len(set(variants)) != len(variants) or len(set(sources)) != len(sources):
        raise ValueError("Nonempty unique conditions required")
    if set(variants) - set(VARIANTS) or set(sources) - set(SOURCES):
        raise ValueError("Unknown variant or source")
    ids = [case.get("case_id") for case in cases]
    if not all(isinstance(case_id, str) and case_id for case_id in ids) or len(set(ids)) != len(ids):
        raise ValueError("Cases require unique nonempty case IDs")
    if type(seed) is not int:
        raise ValueError("Schedule seed must be an integer")
    rng = random.Random(seed)
    order = []
    for case in sorted(cases, key=lambda item: item["case_id"]):
        for repetition in range(1, repeats + 1):
            block = [{"case_id": case["case_id"], "repetition": repetition,
                      "variant": variant, "source": source}
                     for variant in variants for source in sources]
            rng.shuffle(block)
            order.extend(block)
    return order


def run_batch(cases: list[dict], output: Path, factory: Callable[[dict, str], Model], *,
              variants: list[str], sources: list[str], repeats: int = 1, seed: int = 20261022,
              max_tool_calls: int = 8, max_model_calls: int = 12,
              timeout_seconds: float = 120, provider_config: dict | None = None,
              should_cancel: Callable[[], bool] | None = None,
              on_progress: Callable[[dict], None] | None = None) -> dict:
    """Persist a campaign incrementally; cancellation never erases evidence.

    Progress callbacks receive a detached manifest after durable writes. A current
    cancelled run is archived with its partial effects and excluded from valid
    evaluation denominators. Cancellation is cooperative between model/tool steps.
    """
    from .core import run_case
    from .evaluation import evaluate_run, summarize
    order = schedule(cases, variants, sources, repeats, seed)
    if (type(max_tool_calls) is not int or type(max_model_calls) is not int
            or isinstance(timeout_seconds, bool)
            or not (1 <= max_tool_calls <= 100 and 1 <= max_model_calls <= 100
                    and 0 < timeout_seconds <= 3600)):
        raise ValueError("Invalid execution limits")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    fixture_seed = secrets.token_hex(32)
    manifest = {"schema_version": 2, "created_at": datetime.now(timezone.utc).isoformat(),
                "state": "running", "stage": "development", "provenance": provenance(),
                "cases_sha256": digest(cases), "order_seed": seed, "fixture_seed": fixture_seed,
                "limits": {"max_tool_calls": max_tool_calls, "max_model_calls": max_model_calls,
                           "timeout_seconds": timeout_seconds}, "provider_config": provider_config,
                "schedule": order, "runs": [], "completed_runs": 0, "planned_runs": len(order)}
    write_json(output / "cases.snapshot.json", cases)
    write_json(output / "manifest.json", manifest)
    by_id = {case["case_id"]: case for case in cases}
    results = []

    def progress() -> None:
        write_json(output / "manifest.json", manifest)
        if on_progress is not None:
            on_progress(copy.deepcopy(manifest))

    def finish_report() -> None:
        report = summarize(results)
        report.update(campaign_state=manifest["state"], planned_runs=len(order), completed_runs=len(results))
        report.update(evidence_completeness(manifest))
        write_json(output / "summary.json", report)

    try:
        progress()
        for index, entry in enumerate(order, 1):
            if should_cancel is not None and should_cancel():
                manifest["state"] = "cancelled"
                break
            case = by_id[entry["case_id"]]
            kwargs = {"should_cancel": should_cancel} if should_cancel is not None else {}
            result = run_case(case, entry["variant"], entry["source"], factory(case, entry["source"]),
                              repetition=entry["repetition"], run_id=f"run-{index:05d}",
                              fixture_seed=fixture_seed, **manifest["limits"], **kwargs)
            result["metrics"] = evaluate_run(result)
            relative = f"records/{result['run_id']}.json"
            write_json(output / relative, result)
            event_relative = f"events/{result['run_id']}.jsonl"
            event_bytes = "".join(json.dumps(event, ensure_ascii=True, allow_nan=False) + "\n"
                                  for event in result["events"]).encode("utf-8")
            item = {"path": relative, "sha256": digest(result),
                    "events_path": event_relative, "events_state": "pending",
                    "events_sha256": hashlib.sha256(event_bytes).hexdigest(),
                    "status": result["status"]}
            # The record is canonical and already contains the full event log.
            # Commit its index before writing the redundant JSONL view, so a
            # failed derived write cannot orphan otherwise intact evidence.
            manifest["runs"].append(item)
            results.append(result)
            manifest["completed_runs"] = len(results)
            write_json(output / "manifest.json", manifest)
            try:
                _atomic_bytes(output / event_relative, event_bytes)
            except BaseException:
                item["events_state"] = "failed"
                raise
            item["events_state"] = "complete"
            if result["status"] == "cancelled":
                manifest["state"] = "cancelled"
            elif result["status"] in ("budget_exhausted", "technical_error"):
                manifest["state"] = "stopped"
            progress()
            if manifest["state"] != "running":
                break
        else:
            manifest["state"] = "completed"
    except BaseException:
        manifest["state"] = "interrupted"
        manifest["completed_runs"] = len(results)
        write_json(output / "manifest.json", manifest)
        finish_report()
        raise
    finish_report()
    progress()
    return manifest


def _json_read(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"Nonfinite JSON value: {value}")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)


def _campaign_path(directory: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError("Invalid campaign path")
    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts) or PurePosixPath(relative).is_absolute():
        raise ValueError("Invalid campaign path")
    path = directory
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise ValueError("Campaign files must not be symbolic links")
    if not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Campaign path escapes directory")
    return path


def evidence_completeness(manifest: dict) -> dict:
    """Distinguish verified canonical records from missing derived event files."""
    incomplete = [item.get("events_path") for item in manifest.get("runs", [])
                  if item.get("events_state", "complete") != "complete"]
    return {"evidence_complete": not incomplete, "incomplete_event_files": incomplete}


def verify_document_sources(directory: Path, cases: list[dict], results: list[dict], *,
                            require_files: bool = True) -> list[str]:
    """Bind PDF evidence to the case snapshot and the exact supplied article.

    Normal record loading checks available files; archive validation additionally
    requires every referenced original, extraction and confirmation. This permits
    reading canonical records during an in-progress source-copy transaction.
    """
    references: dict[str, dict] = {}
    by_case = {case["case_id"]: case for case in cases}
    for case in cases:
        for source, metadata in case.get("article_sources", {}).items():
            if metadata.get("origin") != "uploaded_pdf" and "sha256" not in metadata:
                continue
            required = {"document_id", "filename", "sha256", "text_sha256", "page_count", "extractor", "origin", "confirmed"}
            if not required <= metadata.keys() or metadata.get("confirmed") is not True:
                raise ValueError("Incomplete or unconfirmed PDF source provenance")
            document_id = metadata["document_id"]
            if not isinstance(document_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", document_id):
                raise ValueError("Invalid PDF source document ID")
            text_hash = hashlib.sha256(case["articles"][source].encode("utf-8")).hexdigest()
            if text_hash != metadata["text_sha256"]:
                raise ValueError("PDF source text hash differs from case article")
            if document_id in references and references[document_id] != metadata:
                raise ValueError("Conflicting PDF source provenance for one document")
            references[document_id] = metadata
    for result in results:
        case = by_case.get(result.get("case_id"), {})
        metadata = case.get("article_sources", {}).get(result.get("source"), {})
        if metadata.get("document_id") not in references:
            continue
        supplied = result.get("document_source", {})
        if any(supplied.get(key) != value for key, value in metadata.items()):
            raise ValueError("Run PDF provenance differs from case snapshot")
        if result.get("original_article", result.get("article_text")) != case["articles"][result["source"]]:
            raise ValueError("Run PDF article differs from case snapshot")
        provided = [event.get("data", {}) for event in result.get("events", [])
                    if event.get("type") == "document_provided"]
        if len(provided) != 1 or provided[0].get("document") != supplied or provided[0].get("text") != case["articles"][result["source"]]:
            raise ValueError("Run PDF source event differs from supplied article")
    # Also check any extra managed source included in the campaign. A changed
    # source must not become trustworthy merely because the archive rehashes it.
    source_root = _campaign_path(directory, "sources")
    document_ids = set(references)
    if source_root.exists():
        for child in source_root.iterdir():
            if not child.is_dir() or child.is_symlink():
                raise ValueError("Campaign sources must contain document directories")
            document_ids.add(child.name)
    verified = []
    for document_id in sorted(document_ids):
        base = _campaign_path(directory, "sources/" + document_id)
        if not base.exists() and not require_files:
            continue
        try:
            metadata = _json_read(_campaign_path(directory, f"sources/{document_id}/document.json"))
            confirmation = _json_read(_campaign_path(directory, f"sources/{document_id}/confirmation.json"))
            original = _campaign_path(directory, f"sources/{document_id}/original.pdf").read_bytes()
            extracted = _campaign_path(directory, f"sources/{document_id}/extracted.txt").read_bytes()
        except FileNotFoundError as exc:
            raise ValueError("Referenced PDF source evidence is missing") from exc
        if (metadata.get("document_id") != document_id
                or hashlib.sha256(original).hexdigest() != metadata.get("sha256")
                or hashlib.sha256(extracted).hexdigest() != metadata.get("text_sha256")
                or confirmation.get("text_sha256") != metadata.get("text_sha256")):
            raise ValueError("PDF source evidence hash or confirmation mismatch")
        extracted.decode("utf-8")
        expected = references.get(document_id)
        if expected and any(metadata.get(key) != value for key, value in expected.items() if key != "confirmed"):
            raise ValueError("PDF source metadata differs from case snapshot")
        verified.append(document_id)
    return verified


def load_results(directory: Path) -> list[dict]:
    """Verify case, record and event evidence, including legacy v1 campaigns.

    Canonical records must be complete. An explicitly pending/failed redundant
    event file may be absent in a running/interrupted campaign; full events are
    retained in its verified record and the manifest exposes the incomplete view.
    """
    directory = Path(directory)
    manifest = _json_read(_campaign_path(directory, "manifest.json"))
    cases = _json_read(_campaign_path(directory, "cases.snapshot.json"))
    if digest(cases) != manifest["cases_sha256"]:
        raise ValueError("Case snapshot hash mismatch")
    order, entries = manifest.get("schedule"), manifest.get("runs")
    if not isinstance(order, list) or not isinstance(entries, list) or len(entries) > len(order):
        raise ValueError("Invalid campaign schedule/run count")
    state = manifest.get("state")
    if state not in {"running", "completed", "stopped", "cancelled", "interrupted"}:
        raise ValueError("Invalid campaign state")
    if state == "completed" and len(entries) != len(order):
        raise ValueError("Completed campaign has missing runs")
    if manifest.get("planned_runs", len(order)) != len(order) or manifest.get("completed_runs", len(entries)) != len(entries):
        raise ValueError("Manifest progress count mismatch")
    results, seen = [], set()
    indexed = set()
    for position, item in enumerate(entries):
        path = _campaign_path(directory, item["path"])
        value = _json_read(path)
        if digest(value) != item["sha256"]:
            raise ValueError(f"Run hash mismatch: {path.name}")
        run_id = value.get("run_id")
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", run_id) or run_id in seen:
            raise ValueError("Invalid or duplicate run ID")
        seen.add(run_id)
        if item["path"] != f"records/{run_id}.json":
            raise ValueError("Run path does not match run ID")
        if any(value.get(key) != order[position].get(key) for key in ("case_id", "repetition", "variant", "source")):
            raise ValueError("Run does not match scheduled position")
        if item.get("status") != value.get("status"):
            raise ValueError("Run status does not match manifest")
        event_relative = item.get("events_path", f"events/{run_id}.jsonl")
        if event_relative != f"events/{run_id}.jsonl":
            raise ValueError("Event path does not match run ID")
        event_path = _campaign_path(directory, event_relative)
        event_state = item.get("events_state", "complete")
        if event_state not in {"pending", "complete", "failed"}:
            raise ValueError("Invalid event evidence state")
        if event_state != "complete" and state not in {"running", "interrupted"}:
            raise ValueError("Finalized campaign has incomplete event evidence")
        indexed.update({path.absolute(), event_path.absolute()})
        results.append(value)
        if not event_path.exists() and event_state != "complete":
            continue
        event_bytes = event_path.read_bytes()
        if "events_sha256" in item and hashlib.sha256(event_bytes).hexdigest() != item["events_sha256"]:
            raise ValueError(f"Event file hash mismatch: {event_path.name}")
        lines = event_bytes.decode("utf-8").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        event_values = [json.loads(line) for line in lines]
        if digest(event_values) != digest(value.get("events", [])):
            raise ValueError(f"Event evidence differs from record: {event_path.name}")
    if state != "running":
        actual = {p.absolute() for sub, suffix in (("records", "*.json"), ("events", "*.jsonl"))
                  for p in (directory / sub).glob(suffix)}
        if actual - indexed:
            raise ValueError("Unindexed run evidence; campaign is inconsistent or was interrupted during a write")
    verify_document_sources(directory, cases, results, require_files=False)
    return results
