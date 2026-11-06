"""Bounded, offline resource measurements using disposable synthetic evidence.

This is an instrument benchmark, never an LLM experiment or a claim about a
different machine. It cannot target a live workspace or remote service.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import sys
import tempfile
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 * 1024


def timed(operation):
    start = time.perf_counter()
    value = operation()
    return value, round((time.perf_counter() - start) * 1000, 3)


def memory_usage() -> dict:
    """Report high-water RSS separately; child and parent maxima cannot be summed."""
    try:
        import resource
    except ImportError:
        return {"parent_peak_rss_mib": None, "children_peak_rss_mib": None,
                "method": "resource.getrusage unavailable on this platform"}
    scale = MIB if sys.platform == "darwin" else 1024
    return {"parent_peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / scale, 3),
            "children_peak_rss_mib": round(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / scale, 3),
            "method": "process-lifetime getrusage high-water RSS; child maximum separate, not concurrent total"}


def request(client, path: str):
    response = client.get(path)
    if response.status_code != 200:
        raise ValueError("Synthetic endpoint probe did not return 200")
    return response


def list_probe(client, jobs, count: int, samples: int) -> dict:
    jobs._list_cache.clear()  # Explicit cold application cache; OS caches stay warm.
    response, cold = timed(lambda: request(client, "/api/campaigns"))
    rows = response.json()["campaigns"]
    if len(rows) != count or any(not row["valid_evidence"] for row in rows):
        raise ValueError("Synthetic list evidence is not valid")
    values = [timed(lambda: request(client, "/api/campaigns"))[1] for _ in range(samples)]
    return {"campaigns": count, "cold_application_cache_ms": cold,
            "warm_median_ms": round(statistics.median(values), 3), "warm_max_ms": max(values),
            "warm_samples_ms": values, "response_bytes": len(response.content)}


def concurrent_probe(client, jobs, case: dict) -> dict:
    """Hold the first synthetic model step so the overlap is deterministic."""
    from security_lab.models import ScriptedModel
    entered, release = threading.Event(), threading.Event()

    def gated_model(*args):
        entered.set()
        if not release.wait(timeout=10):
            raise RuntimeError("Synthetic concurrency probe timed out")
        return ScriptedModel(*args)

    body = {"case_ids": [case["case_id"]], "variants": ["B"], "sources": ["clean"], "repeats": 1, "seed": 42}
    headers = {"X-Lab-Token": request(client, "/api/health").json()["csrf_token"]}
    with patch("security_lab.jobs.ScriptedModel", side_effect=gated_model):
        first = client.post("/api/campaigns", json=body, headers=headers)
        try:
            if first.status_code != 202 or not entered.wait(timeout=10):
                raise ValueError("Synthetic worker did not start")
            second, elapsed = timed(lambda: client.post("/api/campaigns", json=body, headers=headers))
            if second.status_code != 409:
                raise ValueError("Concurrent start was not rejected")
        finally:
            release.set()
            if first.status_code == 202:
                jobs._jobs[first.json()["campaign_id"]]["thread"].join(timeout=15)
        if jobs.running:
            raise ValueError("Synthetic worker did not terminate")
    return {"second_start_status": second.status_code, "rejection_ms": elapsed,
            "method": "first mock factory gated with an event; real HTTP handlers, no network listener"}


def pdf_probe(workspace: Path, pages: int) -> dict:
    from security_lab.documents import import_document
    from security_lab.sample_pdf import article_pdf
    text = "\n".join(["Synthetische Belastungsprobe: Nur technische Testdaten, keine Bewertung."] * (pages * 24 - 1))
    content = article_pdf({"document": {"title": "Synthetic resource probe"}, "articles": {"clean": text}}, "clean")
    result, elapsed = timed(lambda: import_document(workspace / "documents", "synthetic-probe.pdf", content))
    return {"input_bytes": len(content), "pages": result["page_count"],
            "text_characters": len(result["extracted_text"]), "import_ms": elapsed,
            "confirmation": "not confirmed; synthetic load fixture only"}


def long_evidence_probe(workspace: Path, client, jobs, case: dict, characters: int) -> dict:
    from security_lab.batch import run_batch
    from security_lab.models import ScriptedModel
    long_case = copy.deepcopy(case)
    long_case["articles"]["clean"] = ("Synthetic long evidence. " * (characters // 25 + 1))[:characters]
    campaign = workspace / "long-evidence"
    _, elapsed = timed(lambda: run_batch([long_case], campaign, ScriptedModel,
                                        variants=["B"], sources=["clean"], seed=42))
    identifier = next(row["campaign_id"] for row in jobs.list() if jobs.directory(row["campaign_id"]) == campaign)
    response, read_ms = timed(lambda: request(client, f"/api/campaigns/{identifier}/records"))
    return {"article_characters": len(long_case["articles"]["clean"]), "campaign_ms": elapsed,
            "records_endpoint_ms": read_ms, "response_bytes": len(response.content)}


def execute(counts: list[int], samples: int, pdf_pages: int, text_characters: int) -> dict:
    from fastapi.testclient import TestClient
    from security_lab.batch import provenance, run_batch
    from security_lab.cases import load_cases
    from security_lab.models import ScriptedModel
    from security_lab.server import create_app
    started, cpu_started = time.perf_counter(), time.process_time()
    report = {"schema_version": 1, "engineering_only": True, "live_model_calls": 0,
              "created_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
              "python": platform.python_version(), "logical_cpus": os.cpu_count(),
              "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "source": provenance(), "parameters": {"campaign_counts": counts, "warm_samples": samples,
                                                      "pdf_pages": pdf_pages, "text_characters": text_characters},
              "scope": "temporary workspace; in-process ASGI, no TCP/TLS/browser; no 512 MiB limit imposed"}
    with tempfile.TemporaryDirectory(prefix="security-lab-resource-probe-") as temporary:
        workspace = Path(temporary) / "workspace"
        workspace.mkdir()
        case = load_cases(ROOT / "cases" / "dev")[0]
        base = workspace / "fixture-0001"
        _, seed_ms = timed(lambda: run_batch([case], base, ScriptedModel,
                                            variants=["B", "F", "P", "FP"], sources=["clean", "attack"], seed=42))
        app = create_app(workspace, ROOT / "cases" / "dev")
        with TestClient(app, base_url="http://127.0.0.1") as client:
            existing = 1
            reports = []
            for count in counts:
                for index in range(existing + 1, count + 1):
                    shutil.copytree(base, workspace / f"fixture-{index:04d}")
                existing = count
                reports.append(list_probe(client, app.state.jobs, count, samples))
            report["listing"] = reports
            report["fixture"] = {"seed_campaign_ms": seed_ms, "runs_per_campaign": 8,
                                 "copied_campaigns": max(counts) - 1,
                                 "note": "Identical copies scale storage only; not independent scientific observations."}
            report["pdf"] = pdf_probe(workspace, pdf_pages)
            report["long_evidence"] = long_evidence_probe(workspace, client, app.state.jobs, case, text_characters)
            report["concurrent_start"] = concurrent_probe(client, app.state.jobs, case)
            files = [path for path in workspace.rglob("*") if path.is_file()]
            report["storage"] = {"file_count": len(files), "total_bytes": sum(path.stat().st_size for path in files)}
    report["memory"] = memory_usage()
    report["wall_seconds"] = round(time.perf_counter() - started, 3)
    report["parent_cpu_seconds"] = round(time.process_time() - cpu_started, 3)
    report["limitations"] = ["Not a Render/Windows production measurement.",
                             "RSS is a process high-water mark; child values do not prove concurrent aggregate use.",
                             "OS caches are not flushed; cold means application listing cache only.",
                             "No index/database decision from one machine or one synthetic corpus."]
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaigns", type=int, nargs="+", default=[1, 10, 30])
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--pdf-pages", type=int, default=40)
    parser.add_argument("--text-characters", type=int, default=180_000)
    parser.add_argument("--output", type=Path, help="Optional new JSON file; never overwrites an existing result.")
    args = parser.parse_args(argv)
    counts = sorted(set(args.campaigns))
    if not counts or min(counts) < 1 or max(counts) > 100 or not 1 <= args.samples <= 10:
        parser.error("use 1..100 campaigns and 1..10 samples")
    if not 1 <= args.pdf_pages <= 50 or not 1 <= args.text_characters <= 200_000:
        parser.error("use 1..50 PDF pages and 1..200000 text characters")
    if args.output and (args.output.exists() or not args.output.parent.is_dir()):
        parser.error("output must be a new file in an existing directory")
    try:
        report = execute(counts, args.samples, args.pdf_pages, args.text_characters)
        content = json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(content)
            print("Synthetic resource measurements saved; no live model calls.")
        else:
            print(content, end="")
    except (OSError, ValueError, ImportError) as error:
        print(f"Resource probe failed ({type(error).__name__}); no successful report claimed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
