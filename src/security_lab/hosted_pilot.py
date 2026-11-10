"""Authenticated, single-use adapter for the pinned clean A17 pilot."""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import threading

from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool

from . import luna_pilot
from .budget import euros
from .contracts import ModelError
from .documents import reject_symlinks
from .hosted import HostedSettings

# Same conservative EUR rates as the documented pilot. Recheck before activation.
INPUT_EUR_PER_MILLION = "0.12"
OUTPUT_EUR_PER_MILLION = "0.60"
PRICE_CHECK_DATE = "2026-11-09"
UNAVAILABLE = "Der gehostete Luna-Pilot ist nicht startbereit."
BUSY = "Der Pilot oder die Workspace-Sicherung läuft bereits."


def _usage_totals(result: dict) -> tuple[int | None, int | None, str | None]:
    receipts = [event["data"]["usage"] for event in result["events"]
                if event["type"] == "model_response"]
    if len(receipts) != result["model_calls"] or not receipts:
        return None, None, None
    if any(item.get("accounting") not in {"reported_usage", "settlement_failed"} for item in receipts):
        return None, None, None
    input_tokens = sum(item["prompt_tokens"] for item in receipts)
    output_tokens = sum(item["completion_tokens"] for item in receipts)
    if not all(item["accounting"] == "reported_usage" and luna_pilot.has_luna_standard_rate(item)
               for item in receipts):
        return input_tokens, output_tokens, None
    cost = sum((euros(item["estimated_cost_eur"], allow_zero=True) for item in receipts), Decimal("0"))
    return input_tokens, output_tokens, format(cost, "f")


def _summary(result: dict) -> dict:
    if (result["case_id"], result["source"], result["variant"], result["model"], result["is_mock"]) != (
            luna_pilot.CASE_ID, "clean", "P", luna_pilot.MODEL, False):
        raise ValueError("Unexpected pilot evidence")
    input_tokens, output_tokens, cost = _usage_totals(result)
    return {"status": result["status"], "technical_acceptance": result["technical_acceptance"],
            "final_text": result["final_text"], "models": result["observed_models"],
            "model_calls": result["model_calls"], "tool_calls": result["tool_calls"],
            "input_tokens": input_tokens, "output_tokens": output_tokens, "estimated_cost_eur": cost}


class HostedPilot:
    """The operator role is enforced by the host's existing authentication/CSRF middleware."""

    def __init__(self, workspace: Path, settings: HostedSettings):
        self.workspace = workspace
        self.studies = workspace / "studies"
        self.output = self.studies / "luna-clean-first"
        self.settings = settings
        self.slot = threading.Lock()
        self.running = threading.Event()

    @contextmanager
    def exclusive(self):
        # Workspace backups and pilot writes must never overlap.
        if not self.slot.acquire(blocking=False):
            raise HTTPException(409, BUSY)
        try:
            yield
        finally:
            self.slot.release()

    def available(self) -> bool:
        return (self.settings.luna_pilot_enabled and self.settings.storage_mode == "persistent"
                and bool(os.environ.get("OPENAI_API_KEY", "").strip()))

    def evidence(self, name: str, limit: int) -> bytes:
        path = reject_symlinks(self.output / name, self.workspace)
        if not path.is_file() or path.stat().st_size > limit:
            raise ValueError("Incomplete pilot evidence")
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Oversized pilot evidence")
        return data

    def status(self) -> dict:
        if self.running.is_set():
            return {"state": "running", "result": None}
        try:
            if not reject_symlinks(self.output, self.workspace).exists():
                return {"state": "ready" if self.available() else "disabled", "result": None}
            receipt = json.loads(self.evidence("receipt.json", 4096))
            attempt = self.evidence("attempt.json", 1024 * 1024)
            result = self.evidence("result.json", 64 * 1024 * 1024)
            if (hashlib.sha256(attempt).hexdigest() != receipt["attempt_sha256"]
                    or hashlib.sha256(result).hexdigest() != receipt["result_sha256"]):
                raise ValueError("Pilot evidence digest differs")
            summary = _summary(json.loads(result))
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            # Includes interrupted runs, incomplete restores and unreadable evidence.
            return {"state": "failed", "result": None}
        return {"state": "completed" if summary["technical_acceptance"] else "failed", "result": summary}

    async def start_request(self, request: Request) -> dict:
        if request.headers.get("origin") not in {self.settings.frontend_origin, self.settings.public_origin}:
            raise HTTPException(403, "Der Pilot benötigt die konfigurierte Werkbank-Origin.")
        if request.query_params:
            raise HTTPException(400, "Der feste Pilot akzeptiert keine Parameter.")
        async for chunk in request.stream():
            if chunk:
                raise HTTPException(400, "Der feste Pilot akzeptiert keinen Anfrageinhalt.")
        return await run_in_threadpool(self.start)

    def start(self) -> dict:
        with self.exclusive():
            if reject_symlinks(self.output, self.workspace).exists():
                raise HTTPException(409, "Dieser Pilot wurde bereits gestartet. Bitte den Status abrufen.")
            if not self.available():
                raise HTTPException(503, UNAVAILABLE)
            reject_symlinks(self.studies / "budget.json", self.workspace)
            reject_symlinks(self.studies / "budget.json.lock", self.workspace)
            self.running.set()
            try:
                config = luna_pilot.make_config(INPUT_EUR_PER_MILLION, OUTPUT_EUR_PER_MILLION, PRICE_CHECK_DATE)
                luna_pilot.run_first(self.studies, config, os.environ["OPENAI_API_KEY"])
            except FileExistsError:
                raise HTTPException(409, "Der Versuchsordner ist bereits belegt. Bitte den Status abrufen.") from None
            except (OSError, ValueError, ModelError):
                raise HTTPException(503, "Pilot angehalten. Status und Belege prüfen.") from None
            finally:
                self.running.clear()
            return self.status()
