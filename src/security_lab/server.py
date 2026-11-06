"""Mock-only API; local by default, explicitly authenticated when hosted."""
from __future__ import annotations

import csv
import hashlib
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

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers

from . import __version__, review
from .batch import digest, load_results, write_json_new
from .cases import load_cases
from .documents import (MAX_PDF_BYTES, DocumentError, apply_document_override, confirm_document,
                        import_document, list_documents, load_document, reject_symlinks)
from .evaluation import summarize
from .jobs import CampaignJobs, checked_tree
from .hosted import HostedAccessMiddleware, HostedSettings
from .github_auth import GitHubSessions
from .auth_routes import register_auth_routes
from .campaign_metadata import MetadataConflict, load_metadata, save_metadata, validate_labels
from .comparison_csv import comparison_csv
from .operations import storage_status

REVIEW_ID = re.compile(r"review-[0-9a-f]{32}\Z")
REVIEW_API_ID = re.compile(r"(?:review-[0-9a-f]{32}|review-copy-[0-9a-f]{64})\Z")
REVIEW_ERROR = "Die Bewertungsbelege sind beschädigt oder unvollständig. Originaldateien bleiben erhalten."
REVIEW_MAPPING_FILE = "mapping.json"
MAX_REQUEST_BYTES = MAX_PDF_BYTES + 65536
REQUEST_TOO_LARGE = "Anfrage überschreitet die Größenbegrenzung."


def _valid_local_host(headers: Headers) -> bool:
    if len(headers.getlist("host")) != 1:
        return False
    try:
        # URL parsing only; local access never opens a connection here.
        parsed = urlsplit("//" + headers.get("host", ""))
        valid = (parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                 and parsed.username is None and parsed.path == ""
                 and not parsed.query and not parsed.fragment)
        _ = parsed.port  # Accessing the property validates the port syntax/range.
        return valid
    except ValueError:
        return False


def _local_request_error(scope, headers: Headers, token: str) -> tuple[int, str] | None:
    if not _valid_local_host(headers):
        return 403, "Nur lokale Hostnamen sind zugelassen."
    origin = headers.get("origin")
    expected_origin = scope.get("scheme", "http") + "://" + headers["host"]
    if (origin is not None and origin != expected_origin) or headers.get("sec-fetch-site") == "cross-site":
        return 403, "Anfragen anderer Webseiten sind nicht zugelassen."
    if scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}:
        supplied = headers.get("x-lab-token", "")
        if not secrets.compare_digest(supplied.encode("utf-8"), token.encode("ascii")):
            return 403, "Lokales Sitzungstoken fehlt oder ist ungültig."
    try:
        length = int(headers.get("content-length", "0"))
        if not 0 <= length <= MAX_REQUEST_BYTES:
            return 413, REQUEST_TOO_LARGE
    except ValueError:
        return 413, REQUEST_TOO_LARGE
    return None


class LocalAccessMiddleware:
    """Reject DNS rebinding/cross-origin writes and cap streamed request bodies."""
    def __init__(self, app, token: str):
        self.app, self.token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        error = _local_request_error(scope, headers, self.token)
        if error is not None:
            status, detail = error
            return await JSONResponse({"detail": detail}, status)(scope, receive, send)
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
            await JSONResponse({"detail": REQUEST_TOO_LARGE}, 413)(scope, receive, send)


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class APIError(BaseModel):
    """Document existing error payloads without changing exception handling."""
    detail: str


API_ERROR_RESPONSES = {
    400: {"model": APIError, "description": "Invalid input or damaged evidence."},
    403: {"model": APIError, "description": "Host, origin or mutation token is not allowed."},
    404: {"model": APIError, "description": "Requested resource or evidence file was not found."},
    413: {"model": APIError, "description": "Request exceeds the configured size limit."},
}
CONFLICT_RESPONSE = {
    409: {"model": APIError, "description": "Operation conflicts with the current workbench state."},
}


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
    display_name: str = Field(default="", max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=12)


class CampaignMetadataRequest(StrictBody):
    display_name: str = Field(max_length=120)
    tags: list[str] = Field(max_length=12)
    expected_revision: Annotated[StrictInt, Field(ge=0)]


class ConfirmRequest(StrictBody):
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RatingDraft(StrictBody):
    review_id: str = Field(min_length=1, max_length=80)
    legitimate_rating: Literal["", "correct", "partial", "refused", "undecidable"] = ""
    attack_success: Literal["", "yes", "no", "undecidable"] = ""
    false_block: Literal["", "yes", "no", "undecidable"] = ""
    notes: str = Field(default="", max_length=4000)


class RatingsRequest(StrictBody):
    expected_revision: Annotated[StrictInt, Field(ge=0)] | None = None
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
    write_json_new(path, value)


def _version_path(directory: Path, prefix: str) -> Path:
    checked_tree(directory)
    directory.mkdir(parents=True, exist_ok=True)
    versions = [int(path.stem.split("-")[-1]) for path in directory.glob(prefix + "-*.json")]
    return directory / f"{prefix}-{max(versions, default=0) + 1:06d}.json"


class _WorkbenchAPI:
    """Per-app workspace operations and handlers, with no shared global state."""

    def __init__(self, workspace: Path, cases_dir: Path, hosted_settings: HostedSettings | None):
        self.workspace = reject_symlinks(Path(workspace))
        self.cases_dir = checked_tree(Path(cases_dir))
        self.jobs = CampaignJobs(self.workspace)
        self.review_root = reject_symlinks(self.workspace / "reviews", self.workspace)
        self.review_root.mkdir(exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.extraction_slot = threading.BoundedSemaphore(1)
        self.hosted_settings = hosted_settings

    def register(self, app: FastAPI) -> None:
        app.get("/api/health")(self.health)
        app.get("/api/cases")(self.cases)
        app.get("/api/cases/{case_id}/articles/{source}/pdf")(self.sample_pdf)
        app.get("/api/campaigns")(self.campaigns)
        app.post("/api/campaigns", status_code=202, responses=CONFLICT_RESPONSE)(self.start_campaign)
        app.get("/api/campaigns/{campaign_id}")(self.campaign)
        app.get("/api/campaigns/{campaign_id}/records")(self.records)
        app.get("/api/campaigns/{campaign_id}/metadata")(self.campaign_metadata)
        app.put("/api/campaigns/{campaign_id}/metadata", responses=CONFLICT_RESPONSE)(self.campaign_metadata_put)
        app.get("/api/campaigns/{campaign_id}/comparison.csv")(self.comparison_export)
        app.get("/api/workspace/backup", responses=CONFLICT_RESPONSE)(self.workspace_backup)
        app.post("/api/campaigns/{campaign_id}/cancel")(self.cancel)
        app.get("/api/campaigns/{campaign_id}/archive", responses=CONFLICT_RESPONSE)(self.archive)
        app.post("/api/documents", status_code=201, responses=CONFLICT_RESPONSE)(self.upload_document)
        app.get("/api/documents")(self.documents_list)
        app.post("/api/documents/{document_id}/confirm")(self.confirm)
        app.post("/api/campaigns/{campaign_id}/review-export", status_code=201, responses=CONFLICT_RESPONSE)(self.review_export)
        app.get("/api/reviews")(self.review_list)
        app.get("/api/reviews/{review_set_id}/packets")(self.review_packets)
        app.get("/api/reviews/{review_set_id}/ratings/{slot}")(self.ratings_get)
        app.put("/api/reviews/{review_set_id}/ratings/{slot}", responses=CONFLICT_RESPONSE)(self.ratings_put)
        app.post("/api/reviews/{review_set_id}/combine", responses=CONFLICT_RESPONSE)(self.combine)
        app.get("/api/reviews/{review_set_id}/combined")(self.combined_get)
        app.post("/api/reviews/{review_set_id}/adjudicate")(self.adjudicate)
        app.get("/api/campaigns/{campaign_id}/summary")(self.campaign_summary)

    def campaign_directory(self, identifier: str, *, finished: bool = False) -> Path:
        try:
            directory = self.jobs.directory(identifier)
        except KeyError as exc:
            raise HTTPException(404, "Versuch nicht gefunden.") from exc
        if finished:
            # CLI workers are not registered in this app. Only a durable terminal
            # state makes the campaign's record set safe to export or review.
            if self.jobs.is_active(identifier) or _read_json(directory / "manifest.json", self.workspace).get("state") not in {
                "completed", "cancelled", "stopped", "interrupted"
            }:
                raise HTTPException(409, "Bitte den laufenden Versuch zuerst abschließen oder abbrechen.")
        return directory

    def review_locations(self) -> list[tuple[Path, str | None]]:
        locations = [(self.review_root, None)]
        for campaign in self.jobs.list():
            # Keep damaged evidence visible in the campaign list, but do not
            # resolve its review sets or let it block unrelated healthy sets.
            if campaign.get("valid_evidence") is False or campaign.get("state") == "damaged":
                continue
            locations.append((self.campaign_directory(campaign["campaign_id"]) / "reviews", campaign["campaign_id"]))
        return locations

    def review_index(self) -> list[dict[str, Any]]:
        """Resolve API identities from locations, without changing archived evidence.

        A restored campaign may have a new local ID and can coexist with its
        original. Bind its review to the containing canonical records, retaining
        the archived IDs separately. Never interpret an API ID as a path.
        """
        entries = [entry for root, campaign_id in self.review_locations()
                   for entry in self._reviews_at(root, campaign_id)]
        self._assign_review_identifiers(entries)
        return entries

    def _reviews_at(self, root: Path, campaign_id: str | None) -> list[dict[str, Any]]:
        if not root.exists():
            return []
        try:
            reject_symlinks(root, self.workspace)
            directories = list(root.iterdir())
            by_id = ({result["run_id"]: result for result in load_results(root.parent)}
                     if campaign_id is not None else None)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            # A damaged campaign is reported by /api/campaigns. Do not let
            # its review container make other campaigns unavailable.
            return []
        return [self._indexed_review(directory, campaign_id, by_id) for directory in directories
                if REVIEW_ID.fullmatch(directory.name)]

    def _review_metadata(self, directory: Path) -> dict[str, Any]:
        checked_tree(directory)
        metadata = _read_json(directory / "metadata.json", self.workspace)
        if (not isinstance(metadata, dict) or metadata.get("review_set_id") != directory.name
                or not isinstance(metadata.get("campaign_id"), str) or not metadata["campaign_id"]
                or not isinstance(metadata.get("created_at"), str) or not metadata["created_at"]
                or type(metadata.get("packet_count")) is not int or metadata["packet_count"] < 1):
            raise ValueError("Invalid review display metadata")
        return metadata

    def _verify_review_campaign(self, directory: Path, by_id: dict[str, Any]) -> None:
        mapping = _read_json(directory / REVIEW_MAPPING_FILE, self.workspace)["private_review_mapping"]
        if {item["run_id"] for item in mapping.values()} != set(by_id):
            raise ValueError("Review mapping does not cover its containing campaign")
        for item in mapping.values():
            result = by_id[item["run_id"]]
            if item["result_sha256"] != digest(result) or item.get("case_id") != result.get("case_id"):
                raise ValueError("Review provenance differs from its containing campaign")

    def _indexed_review(self, directory: Path, campaign_id: str | None,
                        by_id: dict[str, Any] | None) -> dict[str, Any]:
        entry = {"directory": directory, "campaign_id": campaign_id, "metadata": {}, "error": None}
        try:
            metadata = self._review_metadata(directory)
            entry["metadata"] = metadata
            if len(self.packets(directory)) != metadata["packet_count"]:
                raise ValueError("Review packet count differs from metadata")
            if by_id is not None:
                self._verify_review_campaign(directory, by_id)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            entry["error"] = REVIEW_ERROR
        return entry

    def _assign_review_identifiers(self, entries: list[dict[str, Any]]) -> None:
        groups: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            groups.setdefault(entry["directory"].name, []).append(entry)
        for stored_id, copies in groups.items():
            original = [entry for entry in copies if entry["campaign_id"] is not None
                        and entry["campaign_id"] == entry["metadata"].get("campaign_id")]
            preferred = original[0] if len(original) == 1 else None
            if not original and len(copies) == 1 and copies[0]["campaign_id"] is None:
                preferred = copies[0]  # Existing detached review directories.
            for entry in copies:
                relative = entry["directory"].relative_to(self.workspace).as_posix()
                entry["identifier"] = (stored_id if entry is preferred else
                                       "review-copy-" + hashlib.sha256(relative.encode("utf-8")).hexdigest())

    def review_entry(self, identifier: str) -> dict[str, Any]:
        if not REVIEW_API_ID.fullmatch(identifier):
            raise HTTPException(404, "Bewertungssatz nicht gefunden.")
        matches = [entry for entry in self.review_index() if entry["identifier"] == identifier]
        if len(matches) != 1:
            raise HTTPException(404, "Bewertungssatz nicht gefunden oder mehrdeutig.")
        if matches[0]["error"]:
            raise HTTPException(400, matches[0]["error"])
        return matches[0]

    def review_directory(self, identifier: str) -> Path:
        return self.review_entry(identifier)["directory"]

    def packets(self, directory: Path) -> list[dict[str, Any]]:
        return review.verify_packets(directory / REVIEW_MAPPING_FILE, directory / "reviews.jsonl")

    def latest_combined(self, directory: Path) -> dict[str, Any]:
        versions = sorted((directory / "combined").glob("combined-*.json"))
        if not versions:
            raise HTTPException(404, "Noch keine zusammengeführten Bewertungen.")
        combined = _read_json(versions[-1], self.workspace)
        review.validate_combined(combined)
        return combined

    def ratings_locked(self, directory: Path) -> bool:
        return any((directory / "combined").glob("combined-*.json"))

    def require_open_ratings(self, directory: Path) -> None:
        # Call under the shared write lock so simultaneous saves/combines cannot
        # bypass the transition from drafts to immutable combined decisions.
        if self.ratings_locked(directory):
            raise HTTPException(409, "Dieser Bewertungssatz wurde bereits zusammengeführt. "
                                "Einzelbewertungen sind eingefroren; offene Abweichungen können entschieden werden. "
                                "Für eine neue Bewertung einen neuen Bewertungssatz exportieren.")

    def latest_ratings(self, directory: Path, slot: str) -> dict[str, Any]:
        versions = sorted((directory / f"drafts-{slot}").glob("draft-*.json"))
        return {**_read_json(versions[-1], self.workspace), "revision": int(versions[-1].stem.split("-")[-1])} if versions else {"rater": "", "ratings": [], "revision": 0}

    def health(self, request: Request):
        return {"version": __version__, "api_contract": 2, "capabilities": ["campaign_metadata_v1", "review_revisions_v1", "comparison_csv_v1", "workspace_backup_v1"], "mode": "mock", "csrf_token": self.token, "running": self.jobs.running,
                "storage_mode": self.hosted_settings.storage_mode if self.hosted_settings else "local",
                "storage": storage_status(self.workspace),
                "user": getattr(request.state, "lab_user", None)}

    def cases(self):
        checked_tree(self.cases_dir)
        return {"cases": load_cases(self.cases_dir)}

    def sample_pdf(self, case_id: str, source: Literal["clean", "attack"]):
        from .sample_pdf import article_pdf
        from fastapi.responses import Response
        case = next((item for item in load_cases(self.cases_dir) if item["case_id"] == case_id), None)
        if case is None:
            raise HTTPException(404, "Fall nicht gefunden.")
        return Response(article_pdf(case, source), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{case_id}-{source}.pdf"'})

    def campaigns(self):
        return {"campaigns": self.jobs.list()}

    def start_campaign(self, body: CampaignRequest):
        with self.lock:
            return self._start_campaign(body)

    def _start_campaign(self, body: CampaignRequest):
        validate_labels(body.display_name, body.tags)
        for values in (body.case_ids, body.variants, body.sources):
            if len(values) != len(set(values)):
                raise HTTPException(400, "Doppelte Fall- oder Variantenkennungen sind nicht erlaubt.")
        planned = len(body.case_ids) * len(body.variants) * len(body.sources) * body.repeats
        if planned > 480:
            raise HTTPException(400, "Die lokale Oberfläche erlaubt höchstens 480 Aufgabenläufe pro Versuch.")
        checked_tree(self.cases_dir)
        catalog = {case["case_id"]: case for case in load_cases(self.cases_dir)}
        if set(body.case_ids) - catalog.keys():
            raise HTTPException(400, "Unbekannte Fallkennung.")
        selected = {identifier: catalog[identifier] for identifier in body.case_ids}
        documents = self._apply_document_overrides(body, selected)
        projected_text = sum(sum(len(case["articles"][source]) for source in body.sources) for case in selected.values()) * len(body.variants) * body.repeats
        if projected_text > 8_000_000:
            raise HTTPException(400, "Diese Kombination ist zu groß für einen lokalen Versuch. Weniger Fälle oder Wiederholungen wählen.")
        try:
            return self.jobs.start(list(selected.values()), variants=body.variants, sources=body.sources,
                                   repeats=body.repeats, seed=body.seed, document_ids=documents,
                                   display_name=body.display_name, tags=body.tags)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc

    def _apply_document_overrides(self, body: CampaignRequest, selected: dict[str, Any]) -> list[str]:
        assigned = set()
        documents = []
        for override in body.document_overrides:
            pair = (override.case_id, override.source)
            if pair in assigned or override.case_id not in selected or override.source not in body.sources:
                raise HTTPException(400, "PDF-Zuordnung ist doppelt oder gehört nicht zur gewählten Fall-/Quellenauswahl.")
            document = load_document(self.jobs.documents, override.document_id)
            selected[override.case_id] = apply_document_override(selected[override.case_id], override.source, document)
            assigned.add(pair)
            documents.append(override.document_id)
        return documents

    def campaign(self, campaign_id: str):
        directory = self.campaign_directory(campaign_id)
        manifest = self.jobs.manifest(campaign_id)
        summary_path = directory / "summary.json"
        summary = _read_json(summary_path, self.workspace) if summary_path.exists() else None
        return {"manifest": manifest, "summary": summary}

    def campaign_metadata(self, campaign_id: str):
        with self.lock:
            return load_metadata(self.campaign_directory(campaign_id))

    def campaign_metadata_put(self, campaign_id: str, body: CampaignMetadataRequest):
        with self.lock:
            directory = self.campaign_directory(campaign_id, finished=True)
            try:
                return save_metadata(directory, body.display_name, body.tags, body.expected_revision)
            except MetadataConflict as exc:
                raise HTTPException(409, str(exc)) from exc

    def comparison_export(self, campaign_id: str, review_set_id: str | None = None,
                          metric: str = "", source: str = "", goal: str = ""):
        with self.lock:
            report = self.campaign_summary(campaign_id, review_set_id)
            metadata = load_metadata(self.campaign_directory(campaign_id))
            content = comparison_csv(report, campaign_id, display_name=metadata["display_name"],
                                     review_set_id=review_set_id or "", metric=metric, source=source, goal=goal)
        return Response("\ufeff" + content, media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{campaign_id}-comparison.csv"',
                                 "Cache-Control": "no-store"})

    def workspace_backup(self):
        from .backup import export_workspace
        if not self.extraction_slot.acquire(blocking=False):
            raise HTTPException(409, "Bitte zuerst den laufenden PDF-Import abschließen lassen.")
        temporary = None
        try:
            temporary = tempfile.TemporaryDirectory(prefix="security-lab-backup-")
            output = Path(temporary.name) / "security-lab-workspace.zip"
            with self.lock, self.jobs._lock:
                if self.jobs.running:
                    raise HTTPException(409, "Bitte den aktiven Versuch vor der Sicherung abschließen oder abbrechen.")
                export_workspace(self.workspace, Path(__file__).resolve().parents[2], output)
            return FileResponse(output, media_type="application/zip", filename="security-lab-workspace.zip",
                                headers={"Cache-Control": "no-store"}, background=BackgroundTask(temporary.cleanup))
        except BaseException:
            if temporary is not None:
                temporary.cleanup()
            raise
        finally:
            self.extraction_slot.release()

    def records(self, campaign_id: str):
        directory = self.campaign_directory(campaign_id)
        if not (directory / "manifest.json").exists():
            return {"records": []}
        return {"records": load_results(directory)}

    def cancel(self, campaign_id: str):
        self.campaign_directory(campaign_id)
        return self.jobs.cancel(campaign_id)

    def archive(self, campaign_id: str):
        from .archives import export_campaign, verify_archive
        directory = self.campaign_directory(campaign_id, finished=True)
        exports = reject_symlinks(self.workspace / "exports", self.workspace)
        exports.mkdir(exist_ok=True)
        handle, filename = tempfile.mkstemp(prefix="campaign-", suffix=".zip", dir=exports)
        import os
        os.close(handle)
        path = Path(filename)
        path.unlink()
        try:
            with self.lock:
                export_campaign(directory, path)
                verify_archive(path)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return FileResponse(path, media_type="application/zip", filename=campaign_id + ".zip",
                            background=BackgroundTask(path.unlink, missing_ok=True))

    async def upload_document(self, file: Annotated[UploadFile, File()]):
        if not self.extraction_slot.acquire(blocking=False):
            await file.close()
            raise HTTPException(409, "Es wird bereits ein PDF importiert. Bitte den Import abschließen lassen.")
        try:
            content = await file.read(MAX_PDF_BYTES + 1)
            if len(content) > MAX_PDF_BYTES:
                raise HTTPException(413, "PDF darf höchstens 5 MiB groß sein.")
            return await run_in_threadpool(import_document, self.jobs.documents, file.filename or "", content)
        finally:
            await file.close()
            self.extraction_slot.release()

    def documents_list(self):
        return {"documents": list_documents(self.jobs.documents)}

    def confirm(self, document_id: str, body: ConfirmRequest):
        with self.lock:
            return confirm_document(self.jobs.documents, document_id, body.text_sha256)

    def review_export(self, campaign_id: str):
        directory = self.campaign_directory(campaign_id, finished=True)
        results = load_results(directory)
        if not results:
            raise HTTPException(400, "Der Versuch enthält keine bewertbaren Protokolle.")
        with self.lock:
            identifier = "review-" + uuid.uuid4().hex
            destination = directory / "reviews" / identifier
            review.export_review(results, destination)
            metadata = {"review_set_id": identifier, "campaign_id": campaign_id, "packet_count": len(results),
                        "created_at": datetime.now(timezone.utc).isoformat()}
            _write_new(destination / "metadata.json", metadata, self.workspace)
        return {"review_set_id": identifier, "packet_count": len(results)}

    def review_list(self):
        result, damaged = [], []
        for entry in self.review_index():
            metadata = entry["metadata"]
            current_campaign = entry["campaign_id"] or metadata.get("campaign_id")
            if entry["error"]:
                damaged.append({"review_set_id": entry["identifier"], "campaign_id": current_campaign,
                                "error": entry["error"]})
            else:
                result.append({**metadata, "review_set_id": entry["identifier"], "campaign_id": current_campaign,
                               "original_review_set_id": metadata["review_set_id"],
                               "original_campaign_id": metadata["campaign_id"]})
        return {"review_sets": sorted(result, key=lambda item: item["created_at"], reverse=True),
                "damaged_review_sets": damaged}

    def review_packets(self, review_set_id: str):
        return {"packets": self.packets(self.review_directory(review_set_id))}

    def ratings_get(self, review_set_id: str, slot: Literal["a", "b"]):
        directory = self.review_directory(review_set_id)
        self.packets(directory)
        with self.lock:
            return {**self.latest_ratings(directory, slot), "locked": self.ratings_locked(directory)}

    def ratings_put(self, review_set_id: str, slot: Literal["a", "b"], body: RatingsRequest):
        directory = self.review_directory(review_set_id)
        known = {packet["review_id"] for packet in self.packets(directory)}
        values = [rating.model_dump() for rating in body.ratings]
        supplied = [rating["review_id"] for rating in values]
        if len(set(supplied)) != len(supplied) or set(supplied) - known:
            raise HTTPException(400, "Bewertungskennungen sind doppelt oder gehören nicht zu diesem Satz.")
        complete = bool(body.rater.strip()) and set(supplied) == known and all(
            row["legitimate_rating"] and row["attack_success"] and row["false_block"] and row["notes"].strip() for row in values)
        with self.lock:
            self.require_open_ratings(directory)
            current = self.latest_ratings(directory, slot)["revision"]
            # An old client may create a first draft, but cannot overwrite a
            # revision it never read. The new UI sends its observed revision.
            if body.expected_revision is None and current:
                raise HTTPException(409, "Diese Oberfläche sendet keine Bewertungsrevision. Bitte die Oberfläche aktualisieren; der vorhandene Entwurf bleibt erhalten.")
            if body.expected_revision is not None and body.expected_revision != current:
                raise HTTPException(409, "Dieses Formular wurde inzwischen anderswo gespeichert. Deine Eingaben wurden nicht überschrieben. Vergleiche sie mit dem aktuellen Stand, bevor du erneut speicherst.")
            revision = current + 1
            try:
                _write_new(directory / f"drafts-{slot}" / f"draft-{revision:06d}.json",
                           {"rater": body.rater, "ratings": values}, self.workspace)
            except FileExistsError as exc:
                raise HTTPException(409, "Das Formular wurde gleichzeitig gespeichert. Bitte den aktuellen Stand prüfen.") from exc
        return {"saved": len(values), "complete": complete, "revision": revision}

    def combine(self, review_set_id: str):
        directory = self.review_directory(review_set_id)
        with self.lock:
            self.require_open_ratings(directory)
            self.packets(directory)
            submission = directory / "submissions" / ("submission-" + uuid.uuid4().hex)
            submission.mkdir(parents=True, exist_ok=False)
            paths = []
            for slot in ("a", "b"):
                draft = self.latest_ratings(directory, slot)
                path = submission / f"ratings_{slot}.csv"
                with path.open("x", encoding="utf-8", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=review.RATING_FIELDS)
                    writer.writeheader()
                    for rating in draft["ratings"]:
                        writer.writerow({**rating, "rater": draft["rater"]})
                paths.append(path)
            output = _version_path(directory / "combined", "combined")
            return review.combine_reviews(directory / REVIEW_MAPPING_FILE, paths, output,
                                          packets_path=directory / "reviews.jsonl")

    def combined_get(self, review_set_id: str):
        directory = self.review_directory(review_set_id)
        self.packets(directory)
        with self.lock:
            return self.latest_combined(directory)

    def adjudicate(self, review_set_id: str, body: AdjudicationRequest):
        directory = self.review_directory(review_set_id)
        with self.lock:
            self.packets(directory)
            combined = review.adjudicate_review(self.latest_combined(directory), **body.model_dump())
            _write_new(_version_path(directory / "combined", "combined"), combined, self.workspace)
        return combined

    def campaign_summary(self, campaign_id: str, review_set_id: str | None = None):
        results = load_results(self.campaign_directory(campaign_id))
        if review_set_id:
            entry = self.review_entry(review_set_id)
            directory = entry["directory"]
            bound_campaign = entry["campaign_id"] or entry["metadata"]["campaign_id"]
            if bound_campaign != campaign_id:
                raise HTTPException(400, "Bewertungssatz gehört zu einem anderen Versuch.")
            self.packets(directory)
            results = review.attach_reviews(results, self.latest_combined(directory))
        from .comparisons import paired_comparisons
        report = summarize(results)
        report["paired_comparisons"] = paired_comparisons(results)
        return report


def _register_frontend(app: FastAPI, frontend_dir: Path) -> None:
    frontend = checked_tree(Path(frontend_dir))

    @app.get("/{requested:path}", responses={404: API_ERROR_RESPONSES[404]})
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


def create_app(workspace: Path, cases_dir: Path, frontend_dir: Path | None = None,
               *, hosted_settings: HostedSettings | None = None) -> FastAPI:
    """Create a mock-only workbench; hosting must be configured explicitly."""
    api = _WorkbenchAPI(workspace, cases_dir, hosted_settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        api.jobs.shutdown()

    app = FastAPI(title="LLM Agent Security Lab", version=__version__, lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None,
                  responses=API_ERROR_RESPONSES.copy(),
                  redirect_slashes=hosted_settings is None)
    if hosted_settings is None:
        app.add_middleware(LocalAccessMiddleware, token=api.token)
    else:
        app.router.responses[401] = {"model": APIError, "description": "A valid operator access code is required."}
        github_sessions = GitHubSessions(hosted_settings.github) if hosted_settings.github else None
        app.add_middleware(HostedAccessMiddleware, settings=hosted_settings,
                           token=api.token, max_request_bytes=MAX_REQUEST_BYTES, github_sessions=github_sessions)
        register_auth_routes(app, github_sessions)
        app.state.github_sessions = github_sessions
    app.state.jobs = api.jobs
    app.state.workspace = api.workspace

    @app.exception_handler(DocumentError)
    async def document_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def missing_file(request, error):
        return JSONResponse({"detail": "Die angeforderte lokale Datei wurde nicht gefunden."}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid_data(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    api.register(app)
    if frontend_dir is not None:
        _register_frontend(app, frontend_dir)
    return app
