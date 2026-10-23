"""Same-origin, loopback-only API for the offline research workbench."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import secrets
import tempfile
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers

from . import __version__, review
from .batch import load_results
from .cases import load_cases
from .documents import (MAX_PDF_BYTES, DocumentError, apply_document_override, confirm_document,
                        import_document, list_documents, load_document, reject_symlinks)
from .evaluation import summarize
from .jobs import CampaignJobs, checked_tree

REVIEW_ID = re.compile(r"review-[0-9a-f]{32}\Z")
MAX_REQUEST_BYTES = MAX_PDF_BYTES + 65536


class LocalAccessMiddleware:
    """Reject DNS rebinding/cross-origin writes and cap streamed request bodies."""
    def __init__(self, app, token: str):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        host = headers.get("host", "")
        try:
            parsed = urlsplit("http://" + host)
            host_ok = parsed.hostname in {"127.0.0.1", "localhost", "::1"} and parsed.username is None and parsed.path == "" and not parsed.query and not parsed.fragment
            _ = parsed.port
        except ValueError:
            host_ok = False
        if len(headers.getlist("host")) != 1 or not host_ok:
            return await JSONResponse({"detail": "Nur lokale Hostnamen sind zugelassen."}, 403)(scope, receive, send)
        origin = headers.get("origin")
        expected_origin = scope.get("scheme", "http") + "://" + host
        if (origin is not None and origin != expected_origin) or headers.get("sec-fetch-site") == "cross-site":
            return await JSONResponse({"detail": "Anfragen anderer Webseiten sind nicht zugelassen."}, 403)(scope, receive, send)
        if scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}:
            supplied = headers.get("x-lab-token", "")
            if not secrets.compare_digest(supplied, self.token):
                return await JSONResponse({"detail": "Lokales Sitzungstoken fehlt oder ist ungültig."}, 403)(scope, receive, send)
        try:
            length = int(headers.get("content-length", "0"))
            if length < 0 or length > MAX_REQUEST_BYTES:
                raise ValueError
        except ValueError:
            return await JSONResponse({"detail": "Anfrage überschreitet die Größenbegrenzung."}, 413)(scope, receive, send)
        received = 0
        class TooLarge(Exception):
            pass
        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_REQUEST_BYTES:
                    raise TooLarge
            return message
        try:
            await self.app(scope, limited_receive, send)
        except TooLarge:
            await JSONResponse({"detail": "Anfrage überschreitet die Größenbegrenzung."}, 413)(scope, receive, send)


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class DocumentOverride(StrictBody):
    case_id: str = Field(min_length=1, max_length=120)
    source: Literal["clean", "attack"]
    document_id: str = Field(pattern=r"^doc-[0-9a-f]{32}$")


class CampaignRequest(StrictBody):
    case_ids: list[str] = Field(min_length=1, max_length=60)
    variants: list[Literal["B", "F", "P", "FP"]] = Field(min_length=1, max_length=4)
    sources: list[Literal["clean", "attack"]] = Field(min_length=1, max_length=2)
    repeats: Annotated[StrictInt, Field(ge=1, le=5)] = 1
    seed: Annotated[StrictInt, Field(ge=0, le=2**32 - 1)] = 20261023
    document_overrides: list[DocumentOverride] = Field(default_factory=list, max_length=120)


class ConfirmRequest(StrictBody):
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RatingDraft(StrictBody):
    review_id: str = Field(min_length=1, max_length=80)
    legitimate_rating: Literal["", "correct", "partial", "refused", "undecidable"] = ""
    attack_success: Literal["", "yes", "no", "undecidable"] = ""
    false_block: Literal["", "yes", "no", "undecidable"] = ""
    notes: str = Field(default="", max_length=4000)


class RatingsRequest(StrictBody):
    rater: str = Field(max_length=120)
    ratings: list[RatingDraft] = Field(max_length=480)


class AdjudicationRequest(StrictBody):
    review_id: str = Field(min_length=1, max_length=80)
    legitimate_rating: Literal["correct", "partial", "refused", "undecidable"]
    attack_success: Literal["yes", "no", "undecidable"]
    false_block: Literal["yes", "no", "undecidable"]
    rationale: str = Field(min_length=1, max_length=4000)
    adjudicators: list[str] = Field(min_length=1, max_length=10)


def _read_json(path: Path, root: Path) -> Any:
    reject_symlinks(path, root)
    return json.loads(path.read_text(encoding="utf-8"))


def _write_new(path: Path, value: Any, root: Path) -> None:
    reject_symlinks(path, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def _version_path(directory: Path, prefix: str) -> Path:
    checked_tree(directory)
    directory.mkdir(parents=True, exist_ok=True)
    versions = [int(path.stem.split("-")[-1]) for path in directory.glob(prefix + "-*.json")]
    return directory / f"{prefix}-{max(versions, default=0) + 1:06d}.json"


def create_app(workspace: Path, cases_dir: Path, frontend_dir: Path | None = None) -> FastAPI:
    """Create a local mock-only workbench; credentials are never read here."""
    workspace = reject_symlinks(Path(workspace))
    cases_dir = checked_tree(Path(cases_dir))
    jobs = CampaignJobs(workspace)
    review_root = reject_symlinks(workspace / "reviews", workspace)
    review_root.mkdir(exist_ok=True)
    token = secrets.token_urlsafe(32)
    lock = threading.RLock()
    extraction_slot = threading.BoundedSemaphore(1)

    @asynccontextmanager
    async def lifespan(app):
        yield
        jobs.shutdown()

    app = FastAPI(title="LLM Agent Security Lab", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(LocalAccessMiddleware, token=token)
    app.state.jobs = jobs
    app.state.workspace = workspace

    @app.exception_handler(DocumentError)
    async def document_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def missing_file(request, error):
        return JSONResponse({"detail": "Die angeforderte lokale Datei wurde nicht gefunden."}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid_data(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    def campaign_directory(identifier: str, *, finished: bool = False) -> Path:
        try:
            directory = jobs.directory(identifier)
        except KeyError as exc:
            raise HTTPException(404, "Versuch nicht gefunden.") from exc
        if finished:
            # CLI workers are not registered in this app. Only a durable terminal
            # state makes the campaign's record set safe to export or review.
            if jobs.is_active(identifier) or _read_json(directory / "manifest.json", workspace).get("state") not in {
                "completed", "cancelled", "stopped", "interrupted"
            }:
                raise HTTPException(409, "Bitte den laufenden Versuch zuerst abschließen oder abbrechen.")
        return directory

    def review_locations() -> list[Path]:
        locations = [review_root]
        for campaign in jobs.list():
            # Keep damaged evidence visible in the campaign list, but do not
            # resolve its review sets or let it block unrelated healthy sets.
            if campaign.get("valid_evidence") is False or campaign.get("state") == "damaged":
                continue
            locations.append(campaign_directory(campaign["campaign_id"]) / "reviews")
        return locations

    def review_directory(identifier: str) -> Path:
        if not REVIEW_ID.fullmatch(identifier):
            raise HTTPException(404, "Bewertungssatz nicht gefunden.")
        matches = []
        for root in review_locations():
            directory = checked_tree(root / identifier)
            if (directory / "metadata.json").is_file():
                matches.append(directory)
        if len(matches) != 1:
            raise HTTPException(404, "Bewertungssatz nicht gefunden oder mehrdeutig.")
        return matches[0]

    def packets(directory: Path) -> list[dict[str, Any]]:
        return review.verify_packets(directory / "mapping.json", directory / "reviews.jsonl")

    def latest_combined(directory: Path) -> dict[str, Any]:
        versions = sorted((directory / "combined").glob("combined-*.json"))
        if not versions:
            raise HTTPException(404, "Noch keine zusammengeführten Bewertungen.")
        combined = _read_json(versions[-1], workspace)
        review.validate_combined(combined)
        return combined

    def ratings_locked(directory: Path) -> bool:
        return any((directory / "combined").glob("combined-*.json"))

    def require_open_ratings(directory: Path) -> None:
        # Call under the shared write lock so simultaneous saves/combines cannot
        # bypass the transition from drafts to immutable combined decisions.
        if ratings_locked(directory):
            raise HTTPException(409, "Dieser Bewertungssatz wurde bereits zusammengeführt. "
                                "Einzelbewertungen sind eingefroren; offene Abweichungen können entschieden werden. "
                                "Für eine neue Bewertung einen neuen Bewertungssatz exportieren.")

    def latest_ratings(directory: Path, slot: str) -> dict[str, Any]:
        versions = sorted((directory / f"drafts-{slot}").glob("draft-*.json"))
        return _read_json(versions[-1], workspace) if versions else {"rater": "", "ratings": []}

    @app.get("/api/health")
    def health():
        return {"version": __version__, "mode": "mock", "csrf_token": token, "running": jobs.running}

    @app.get("/api/cases")
    def cases():
        checked_tree(cases_dir)
        return {"cases": load_cases(cases_dir)}

    @app.get("/api/cases/{case_id}/articles/{source}/pdf")
    def sample_pdf(case_id: str, source: Literal["clean", "attack"]):
        from .sample_pdf import article_pdf
        from fastapi.responses import Response
        case = next((item for item in load_cases(cases_dir) if item["case_id"] == case_id), None)
        if case is None:
            raise HTTPException(404, "Fall nicht gefunden.")
        return Response(article_pdf(case, source), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{case_id}-{source}.pdf"'})

    @app.get("/api/campaigns")
    def campaigns():
        return {"campaigns": jobs.list()}

    @app.post("/api/campaigns", status_code=202)
    def start_campaign(body: CampaignRequest):
        for values in (body.case_ids, body.variants, body.sources):
            if len(values) != len(set(values)):
                raise HTTPException(400, "Doppelte Fall- oder Variantenkennungen sind nicht erlaubt.")
        planned = len(body.case_ids) * len(body.variants) * len(body.sources) * body.repeats
        if planned > 480:
            raise HTTPException(400, "Die lokale Oberfläche erlaubt höchstens 480 Aufgabenläufe pro Versuch.")
        checked_tree(cases_dir)
        catalog = {case["case_id"]: case for case in load_cases(cases_dir)}
        if set(body.case_ids) - catalog.keys():
            raise HTTPException(400, "Unbekannte Fallkennung.")
        selected = {identifier: catalog[identifier] for identifier in body.case_ids}
        assigned = set()
        documents = []
        for override in body.document_overrides:
            pair = (override.case_id, override.source)
            if pair in assigned or override.case_id not in selected or override.source not in body.sources:
                raise HTTPException(400, "PDF-Zuordnung ist doppelt oder gehört nicht zur gewählten Fall-/Quellenauswahl.")
            document = load_document(jobs.documents, override.document_id)
            selected[override.case_id] = apply_document_override(selected[override.case_id], override.source, document)
            assigned.add(pair)
            documents.append(override.document_id)
        projected_text = sum(sum(len(case["articles"][source]) for source in body.sources) for case in selected.values()) * len(body.variants) * body.repeats
        if projected_text > 8_000_000:
            raise HTTPException(400, "Diese Kombination ist zu groß für einen lokalen Versuch. Weniger Fälle oder Wiederholungen wählen.")
        try:
            return jobs.start(list(selected.values()), variants=body.variants, sources=body.sources,
                              repeats=body.repeats, seed=body.seed, document_ids=documents)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/campaigns/{campaign_id}")
    def campaign(campaign_id: str):
        directory = campaign_directory(campaign_id)
        manifest = jobs.manifest(campaign_id)
        summary_path = directory / "summary.json"
        summary = _read_json(summary_path, workspace) if summary_path.exists() else None
        return {"manifest": manifest, "summary": summary}

    @app.get("/api/campaigns/{campaign_id}/records")
    def records(campaign_id: str):
        directory = campaign_directory(campaign_id)
        if not (directory / "manifest.json").exists():
            return {"records": []}
        return {"records": load_results(directory)}

    @app.post("/api/campaigns/{campaign_id}/cancel")
    def cancel(campaign_id: str):
        campaign_directory(campaign_id)
        return jobs.cancel(campaign_id)

    @app.get("/api/campaigns/{campaign_id}/archive")
    def archive(campaign_id: str):
        from .archives import export_campaign, verify_archive
        directory = campaign_directory(campaign_id, finished=True)
        exports = reject_symlinks(workspace / "exports", workspace)
        exports.mkdir(exist_ok=True)
        handle, filename = tempfile.mkstemp(prefix="campaign-", suffix=".zip", dir=exports)
        import os
        os.close(handle)
        path = Path(filename)
        path.unlink()
        try:
            with lock:
                export_campaign(directory, path)
                verify_archive(path)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return FileResponse(path, media_type="application/zip", filename=campaign_id + ".zip",
                            background=BackgroundTask(path.unlink, missing_ok=True))

    @app.post("/api/documents", status_code=201)
    async def upload_document(file: Annotated[UploadFile, File()]):
        if not extraction_slot.acquire(blocking=False):
            await file.close()
            raise HTTPException(409, "Es wird bereits ein PDF importiert. Bitte den Import abschließen lassen.")
        try:
            content = await file.read(MAX_PDF_BYTES + 1)
            if len(content) > MAX_PDF_BYTES:
                raise HTTPException(413, "PDF darf höchstens 5 MiB groß sein.")
            return await run_in_threadpool(import_document, jobs.documents, file.filename or "", content)
        finally:
            await file.close()
            extraction_slot.release()

    @app.get("/api/documents")
    def documents_list():
        return {"documents": list_documents(jobs.documents)}

    @app.post("/api/documents/{document_id}/confirm")
    def confirm(document_id: str, body: ConfirmRequest):
        with lock:
            return confirm_document(jobs.documents, document_id, body.text_sha256)

    @app.post("/api/campaigns/{campaign_id}/review-export", status_code=201)
    def review_export(campaign_id: str):
        directory = campaign_directory(campaign_id, finished=True)
        results = load_results(directory)
        if not results:
            raise HTTPException(400, "Der Versuch enthält keine bewertbaren Protokolle.")
        with lock:
            identifier = "review-" + uuid.uuid4().hex
            destination = directory / "reviews" / identifier
            review.export_review(results, destination)
            metadata = {"review_set_id": identifier, "campaign_id": campaign_id, "packet_count": len(results),
                        "created_at": datetime.now(timezone.utc).isoformat()}
            _write_new(destination / "metadata.json", metadata, workspace)
        return {"review_set_id": identifier, "packet_count": len(results)}

    @app.get("/api/reviews")
    def review_list():
        result = []
        for root in review_locations():
            if root.exists():
                for directory in root.iterdir():
                    if REVIEW_ID.fullmatch(directory.name):
                        directory = review_directory(directory.name)
                        result.append(_read_json(directory / "metadata.json", workspace))
        return {"review_sets": sorted(result, key=lambda item: item["created_at"], reverse=True)}

    @app.get("/api/reviews/{review_set_id}/packets")
    def review_packets(review_set_id: str):
        return {"packets": packets(review_directory(review_set_id))}

    @app.get("/api/reviews/{review_set_id}/ratings/{slot}")
    def ratings_get(review_set_id: str, slot: Literal["a", "b"]):
        directory = review_directory(review_set_id)
        packets(directory)
        with lock:
            return {**latest_ratings(directory, slot), "locked": ratings_locked(directory)}

    @app.put("/api/reviews/{review_set_id}/ratings/{slot}")
    def ratings_put(review_set_id: str, slot: Literal["a", "b"], body: RatingsRequest):
        directory = review_directory(review_set_id)
        known = {packet["review_id"] for packet in packets(directory)}
        values = [rating.model_dump() for rating in body.ratings]
        supplied = [rating["review_id"] for rating in values]
        if len(set(supplied)) != len(supplied) or set(supplied) - known:
            raise HTTPException(400, "Bewertungskennungen sind doppelt oder gehören nicht zu diesem Satz.")
        complete = bool(body.rater.strip()) and set(supplied) == known and all(
            row["legitimate_rating"] and row["attack_success"] and row["false_block"] and row["notes"].strip() for row in values)
        with lock:
            require_open_ratings(directory)
            _write_new(_version_path(directory / f"drafts-{slot}", "draft"),
                       {"rater": body.rater, "ratings": values}, workspace)
        return {"saved": len(values), "complete": complete}

    @app.post("/api/reviews/{review_set_id}/combine")
    def combine(review_set_id: str):
        directory = review_directory(review_set_id)
        with lock:
            require_open_ratings(directory)
            packets(directory)
            submission = directory / "submissions" / ("submission-" + uuid.uuid4().hex)
            submission.mkdir(parents=True, exist_ok=False)
            paths = []
            for slot in ("a", "b"):
                draft = latest_ratings(directory, slot)
                path = submission / f"ratings_{slot}.csv"
                with path.open("x", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=review.RATING_FIELDS)
                    writer.writeheader()
                    for rating in draft["ratings"]:
                        writer.writerow({**rating, "rater": draft["rater"]})
                paths.append(path)
            output = _version_path(directory / "combined", "combined")
            return review.combine_reviews(directory / "mapping.json", paths, output,
                                          packets_path=directory / "reviews.jsonl")

    @app.get("/api/reviews/{review_set_id}/combined")
    def combined_get(review_set_id: str):
        directory = review_directory(review_set_id)
        packets(directory)
        with lock:
            return latest_combined(directory)

    @app.post("/api/reviews/{review_set_id}/adjudicate")
    def adjudicate(review_set_id: str, body: AdjudicationRequest):
        directory = review_directory(review_set_id)
        with lock:
            packets(directory)
            combined = review.adjudicate_review(latest_combined(directory), **body.model_dump())
            _write_new(_version_path(directory / "combined", "combined"), combined, workspace)
        return combined

    @app.get("/api/campaigns/{campaign_id}/summary")
    def campaign_summary(campaign_id: str, review_set_id: str | None = None):
        results = load_results(campaign_directory(campaign_id))
        if review_set_id:
            directory = review_directory(review_set_id)
            metadata = _read_json(directory / "metadata.json", workspace)
            if metadata["campaign_id"] != campaign_id:
                raise HTTPException(400, "Bewertungssatz gehört zu einem anderen Versuch.")
            packets(directory)
            results = review.attach_reviews(results, latest_combined(directory))
        from .comparisons import paired_comparisons
        report = summarize(results)
        report["paired_comparisons"] = paired_comparisons(results)
        return report

    if frontend_dir is not None:
        frontend = checked_tree(Path(frontend_dir))
        @app.get("/{requested:path}")
        def frontend_file(requested: str):
            if requested.startswith("api/") or requested == "api":
                raise HTTPException(404, "API-Endpunkt nicht gefunden.")
            parts = Path(requested).parts
            if any(part in {"..", "."} for part in parts) or "\\" in requested:
                raise HTTPException(404, "Datei nicht gefunden.")
            candidate = reject_symlinks(frontend / requested, frontend)
            if not candidate.is_file():
                candidate = reject_symlinks(frontend / "index.html", frontend)
            if not candidate.is_file():
                raise HTTPException(404, "Frontend-Build fehlt.")
            return FileResponse(candidate)
    return app
