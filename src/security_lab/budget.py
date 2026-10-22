"""Conservative local EUR accounting, not a provider-side invoice guarantee.

Use one persistent ledger on one execution machine. Independent copies on other
machines or requests made outside this application are not covered. Unknown
request outcomes keep their reservation until manually reconciled with billing.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from .contracts import BudgetExceeded

PROJECT_CEILING_EUR = Decimal("250")


def euros(value: Any, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("EUR amount must be a finite number")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("EUR amount must be a finite number") from None
    if not amount.is_finite() or amount < 0 or (not allow_zero and amount == 0):
        raise ValueError("EUR amount must be positive" if not allow_zero else "EUR amount must be nonnegative")
    return amount


class BudgetLedger:
    """Atomic reservations protected by a cross-process exclusive lock file.

    A stale lock is never silently removed: inspect/reconcile after a process
    crash. Every pending reservation counts fully against the configured cap.
    """

    def __init__(self, path: str | Path, limit_eur: Any = 250,
                 request_limit_eur: Any = 1.0):
        self.path = Path(path)
        self.limit = euros(limit_eur)
        self.request_limit = euros(request_limit_eur)
        if self.limit > PROJECT_CEILING_EUR:
            raise ValueError("Project budget must not exceed EUR 250")
        if self.request_limit > self.limit:
            raise ValueError("Per-request limit exceeds project limit")
        self.lock_path = self.path.with_name(self.path.name + ".lock")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise BudgetExceeded("Budget ledger is locked; inspect concurrent or interrupted execution") from None
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
                handle.flush()
                os.fsync(handle.fileno())
            yield
        finally:
            self.lock_path.unlink(missing_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": 1, "currency": "EUR", "halted": False, "reservations": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if (not isinstance(value, dict) or value.get("schema_version") != 1
                    or value.get("currency") != "EUR" or type(value.get("halted")) is not bool
                    or not isinstance(value.get("reservations"), dict)):
                raise ValueError
            for entry in value["reservations"].values():
                if (not isinstance(entry, dict) or entry.get("state") not in {"reserved", "settled"}
                        or not isinstance(entry.get("created_at"), str)):
                    raise ValueError
                euros(entry["amount_eur"], allow_zero=True)
                euros(entry["reserved_eur"])
            return value
        except (OSError, ValueError, KeyError, TypeError):
            raise BudgetExceeded("Budget ledger is unreadable or invalid; reconcile it before further requests") from None

    def _save(self, value: dict[str, Any]) -> None:
        temporary = self.path.with_name(self.path.name + "." + uuid4().hex + ".tmp")
        try:
            descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _total(value: dict[str, Any]) -> Decimal:
        return sum((euros(item["amount_eur"], allow_zero=True)
                    for item in value["reservations"].values()), Decimal("0"))

    def reserve(self, amount_eur: Any, metadata: dict[str, Any] | None = None) -> str:
        amount = euros(amount_eur)
        if amount > self.request_limit:
            raise BudgetExceeded("Request reservation exceeds the per-request EUR limit")
        with self._locked():
            value = self._load()
            if value["halted"]:
                raise BudgetExceeded("Budget ledger is halted after an accounting overrun; reconcile first")
            if self._total(value) + amount > self.limit:
                raise BudgetExceeded("Request reservation would exceed the configured project budget")
            reservation_id = uuid4().hex
            value["reservations"][reservation_id] = {
                "amount_eur": str(amount), "reserved_eur": str(amount), "state": "reserved",
                "created_at": datetime.now(timezone.utc).isoformat(), "metadata": metadata or {},
            }
            self._save(value)
            return reservation_id

    def settle(self, reservation_id: str, actual_eur: Any) -> bool:
        """Record known usage; an overrun is preserved and halts future requests."""
        actual = euros(actual_eur, allow_zero=True)
        with self._locked():
            value = self._load()
            entry = value["reservations"].get(reservation_id)
            if entry is None or entry["state"] != "reserved":
                raise BudgetExceeded("Unknown or already settled budget reservation")
            within = actual <= euros(entry["reserved_eur"])
            entry["amount_eur"] = str(actual)
            entry["state"] = "settled"
            entry["settled_at"] = datetime.now(timezone.utc).isoformat()
            if not within or self._total(value) > self.limit:
                value["halted"] = True
                within = False
            self._save(value)
            return within

    def snapshot(self) -> dict[str, Any]:
        with self._locked():
            value = self._load()
            total = self._total(value)
            return {
                "currency": "EUR", "limit_eur": str(self.limit), "accounted_eur": str(total),
                "remaining_eur": str(max(Decimal("0"), self.limit - total)),
                "halted": value["halted"], "reservations": value["reservations"],
            }
