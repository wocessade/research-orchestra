"""Atomic process-local budget reservations.

The single-flight ledger is deliberately process-local.  Its protocol keeps
the atomic revision check at the boundary so a durable transactional store can
replace it later without changing the guard policy.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from threading import RLock
from typing import Callable, Protocol, runtime_checkable
from uuid import uuid4


class BudgetLedgerError(ValueError):
    """Base class for explicit, fail-closed ledger errors."""


class InvalidReservationError(BudgetLedgerError):
    """A reservation value, identity, timestamp, or state is invalid."""


class LedgerRevisionConflictError(BudgetLedgerError):
    """The caller evaluated an obsolete ledger revision."""


class ReservationConflictError(BudgetLedgerError):
    """A reservation mutation conflicts with the current reservation state."""


class UnknownReservationError(BudgetLedgerError):
    """The requested reservation id is not present in the ledger."""


class ReservationState(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"
    RECONCILED = "reconciled"


def _require_decimal(value: object, name: str, *, positive: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise InvalidReservationError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise InvalidReservationError(f"{name} must be finite")
    if positive and value <= 0:
        raise InvalidReservationError(f"{name} must be positive")
    if not positive and value < 0:
        raise InvalidReservationError(f"{name} must be non-negative")
    return value


def _require_aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise InvalidReservationError(f"{name} must be timezone-aware")
    return value


def _require_revision(value: object) -> int:
    if type(value) is not int or value < 0:
        raise LedgerRevisionConflictError("expected_revision must be a non-negative integer")
    return value


@dataclass(frozen=True, slots=True)
class Reservation:
    """Immutable, explainable reservation and terminal accounting facts."""

    id: str
    run_id: str
    reserved: Decimal
    state: ReservationState
    created_at: datetime
    updated_at: datetime
    actual_cost: Decimal | None = None
    released_amount: Decimal | None = None
    overspend: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise InvalidReservationError("reservation id must be a non-empty string")
        if not isinstance(self.run_id, str) or not self.run_id:
            raise InvalidReservationError("run_id must be a non-empty string")
        _require_decimal(self.reserved, "reserved", positive=True)
        if not isinstance(self.state, ReservationState):
            raise InvalidReservationError("state must be a ReservationState")
        created = _require_aware(self.created_at, "created_at")
        updated = _require_aware(self.updated_at, "updated_at")
        if updated < created:
            raise InvalidReservationError("updated_at cannot precede created_at")
        if self.actual_cost is not None:
            _require_decimal(self.actual_cost, "actual_cost")
        if self.released_amount is not None:
            _require_decimal(self.released_amount, "released_amount")
        if self.overspend is not None:
            _require_decimal(self.overspend, "overspend")
        if self.state is ReservationState.ACTIVE:
            if any(
                value is not None
                for value in (self.actual_cost, self.released_amount, self.overspend)
            ):
                raise InvalidReservationError("active reservation has terminal facts")
        elif self.state is ReservationState.RELEASED:
            if (
                self.actual_cost is not None
                or self.released_amount != self.reserved
                or self.overspend is not None
            ):
                raise InvalidReservationError("released reservation facts are inconsistent")
        elif (
            self.actual_cost is None
            or self.released_amount is None
            or self.overspend is None
            or self.released_amount != max(self.reserved - self.actual_cost, Decimal("0"))
            or self.overspend != max(self.actual_cost - self.reserved, Decimal("0"))
        ):
            raise InvalidReservationError("reconciled reservation facts are inconsistent")


@runtime_checkable
class BudgetLedger(Protocol):
    """Replaceable atomic ledger boundary for budget admission."""

    @property
    def revision(self) -> int:
        ...

    @property
    def active_total(self) -> Decimal:
        ...

    def lookup(self, reservation_id: str) -> Reservation:
        ...

    def reserve(
        self,
        *,
        run_id: str,
        amount: Decimal,
        expected_revision: int,
        now: datetime | None = None,
    ) -> Reservation:
        ...

    def release(
        self, reservation_id: str, *, now: datetime | None = None
    ) -> Reservation:
        ...

    def reconcile(
        self,
        reservation_id: str,
        actual_cost: Decimal,
        *,
        now: datetime | None = None,
    ) -> Reservation:
        ...


class SingleFlightBudgetLedger:
    """Thread-safe process-local ledger allowing one active paid reservation.

    This implementation provides single-flight protection only within one
    Python process.  Callers must use the protocol so a future durable atomic
    implementation can provide cross-process guarantees without changing the
    guard contract.
    """

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: uuid4().hex)
        if not callable(self._clock) or not callable(self._id_factory):
            raise ValueError("clock and id_factory must be callable")
        self._lock = RLock()
        self._revision = 0
        self._reservations: dict[str, Reservation] = {}

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    @property
    def active_total(self) -> Decimal:
        with self._lock:
            return sum(
                (
                    reservation.reserved
                    for reservation in self._reservations.values()
                    if reservation.state is ReservationState.ACTIVE
                ),
                Decimal("0"),
            )

    def _timestamp(self, now: datetime | None) -> datetime:
        try:
            timestamp = self._clock() if now is None else now
        except Exception as exc:
            raise InvalidReservationError("clock failed") from exc
        return _require_aware(timestamp, "timestamp")

    def _get(self, reservation_id: str) -> Reservation:
        if not isinstance(reservation_id, str) or not reservation_id:
            raise UnknownReservationError("reservation id is unknown")
        try:
            return self._reservations[reservation_id]
        except KeyError:
            raise UnknownReservationError("reservation id is unknown") from None

    def lookup(self, reservation_id: str) -> Reservation:
        with self._lock:
            return self._get(reservation_id)

    def reserve(
        self,
        *,
        run_id: str,
        amount: Decimal,
        expected_revision: int,
        now: datetime | None = None,
    ) -> Reservation:
        if not isinstance(run_id, str) or not run_id:
            raise InvalidReservationError("run_id must be a non-empty string")
        reserved = _require_decimal(amount, "amount", positive=True)
        expected = _require_revision(expected_revision)
        with self._lock:
            if expected != self._revision:
                raise LedgerRevisionConflictError(
                    "ledger revision changed before reservation"
                )
            if any(
                reservation.state is ReservationState.ACTIVE
                for reservation in self._reservations.values()
            ):
                raise ReservationConflictError("an active reservation already exists")
            timestamp = self._timestamp(now)
            try:
                reservation_id = self._id_factory()
            except Exception as exc:
                raise InvalidReservationError("id factory failed") from exc
            if not isinstance(reservation_id, str) or not reservation_id:
                raise InvalidReservationError("id factory must return a non-empty string")
            if reservation_id in self._reservations:
                raise ReservationConflictError("reservation id already exists")
            reservation = Reservation(
                id=reservation_id,
                run_id=run_id,
                reserved=reserved,
                state=ReservationState.ACTIVE,
                created_at=timestamp,
                updated_at=timestamp,
            )
            self._reservations[reservation.id] = reservation
            self._revision += 1
            return reservation

    def release(
        self, reservation_id: str, *, now: datetime | None = None
    ) -> Reservation:
        if now is not None:
            _require_aware(now, "timestamp")
        with self._lock:
            reservation = self._get(reservation_id)
            if reservation.state is ReservationState.RELEASED:
                return reservation
            if reservation.state is ReservationState.RECONCILED:
                raise ReservationConflictError("reconciled reservation cannot be released")
            timestamp = self._timestamp(now)
            released = replace(
                reservation,
                state=ReservationState.RELEASED,
                updated_at=timestamp,
                released_amount=reservation.reserved,
            )
            self._reservations[reservation.id] = released
            self._revision += 1
            return released

    def reconcile(
        self,
        reservation_id: str,
        actual_cost: Decimal,
        *,
        now: datetime | None = None,
    ) -> Reservation:
        actual = _require_decimal(actual_cost, "actual_cost")
        if now is not None:
            _require_aware(now, "timestamp")
        with self._lock:
            reservation = self._get(reservation_id)
            if reservation.state is ReservationState.RECONCILED:
                if reservation.actual_cost == actual:
                    return reservation
                raise ReservationConflictError(
                    "reconciliation conflicts with recorded actual cost"
                )
            if reservation.state is ReservationState.RELEASED:
                raise ReservationConflictError("released reservation cannot be reconciled")
            timestamp = self._timestamp(now)
            released_amount = max(reservation.reserved - actual, Decimal("0"))
            overspend = max(actual - reservation.reserved, Decimal("0"))
            reconciled = replace(
                reservation,
                state=ReservationState.RECONCILED,
                updated_at=timestamp,
                actual_cost=actual,
                released_amount=released_amount,
                overspend=overspend,
            )
            self._reservations[reservation.id] = reconciled
            self._revision += 1
            return reconciled


__all__ = [
    "BudgetLedger",
    "BudgetLedgerError",
    "InvalidReservationError",
    "LedgerRevisionConflictError",
    "Reservation",
    "ReservationConflictError",
    "ReservationState",
    "SingleFlightBudgetLedger",
    "UnknownReservationError",
]
