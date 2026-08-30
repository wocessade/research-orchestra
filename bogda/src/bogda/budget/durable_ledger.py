"""SQLite budget ledger that survives process restart.

Same `BudgetLedger` contract as `SingleFlightBudgetLedger`.  One ACTIVE
reservation at a time.  Callers still pass `expected_revision` for CAS.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from sqlite3 import Connection, connect
from threading import RLock
from typing import Callable
from uuid import uuid4

from bogda.budget.ledger import (
    InvalidReservationError,
    LedgerFacts,
    LedgerRevisionConflictError,
    Reservation,
    ReservationConflictError,
    ReservationState,
    UnknownReservationError,
    _require_aware,
    _require_decimal,
    _require_revision,
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    revision INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reservations (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    reserved TEXT NOT NULL,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    actual_cost TEXT,
    released_amount TEXT,
    overspend TEXT
);
INSERT OR IGNORE INTO meta (id, revision) VALUES (1, 0);
"""


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise InvalidReservationError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _dec(value: str | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value)


def _row_to_reservation(row: tuple[object, ...]) -> Reservation:
    return Reservation(
        id=str(row[0]),
        run_id=str(row[1]),
        reserved=Decimal(str(row[2])),
        state=ReservationState(str(row[3])),
        created_at=_parse_dt(str(row[4])),
        updated_at=_parse_dt(str(row[5])),
        actual_cost=_dec(row[6] if row[6] is None else str(row[6])),
        released_amount=_dec(row[7] if row[7] is None else str(row[7])),
        overspend=_dec(row[8] if row[8] is None else str(row[8])),
    )


class SqliteBudgetLedger:
    """File-backed single-flight ledger.  Reopen the same path after crash."""

    def __init__(
        self,
        path: Path,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(path, Path):
            raise ValueError("path must be a Path")
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: uuid4().hex)
        if not callable(self._clock) or not callable(self._id_factory):
            raise ValueError("clock and id_factory must be callable")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._conn: Connection = connect(path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _timestamp(self, now: datetime | None) -> datetime:
        try:
            timestamp = self._clock() if now is None else now
        except Exception as exc:
            raise InvalidReservationError("clock failed") from exc
        return _require_aware(timestamp, "timestamp")

    def _revision_unlocked(self) -> int:
        row = self._conn.execute("SELECT revision FROM meta WHERE id = 1").fetchone()
        if row is None:
            raise InvalidReservationError("ledger meta row is missing")
        return int(row[0])

    def _bump_revision_unlocked(self) -> None:
        self._conn.execute("UPDATE meta SET revision = revision + 1 WHERE id = 1")

    def _get_unlocked(self, reservation_id: str) -> Reservation:
        if not isinstance(reservation_id, str) or not reservation_id:
            raise UnknownReservationError("reservation id is unknown")
        row = self._conn.execute(
            "SELECT id, run_id, reserved, state, created_at, updated_at, "
            "actual_cost, released_amount, overspend FROM reservations WHERE id = ?",
            (reservation_id,),
        ).fetchone()
        if row is None:
            raise UnknownReservationError("reservation id is unknown")
        return _row_to_reservation(row)

    def _insert_unlocked(self, reservation: Reservation) -> None:
        self._conn.execute(
            "INSERT INTO reservations ("
            "id, run_id, reserved, state, created_at, updated_at, "
            "actual_cost, released_amount, overspend"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                reservation.id,
                reservation.run_id,
                str(reservation.reserved),
                reservation.state.value,
                reservation.created_at.isoformat(),
                reservation.updated_at.isoformat(),
                None if reservation.actual_cost is None else str(reservation.actual_cost),
                None
                if reservation.released_amount is None
                else str(reservation.released_amount),
                None if reservation.overspend is None else str(reservation.overspend),
            ),
        )

    def _update_unlocked(self, reservation: Reservation) -> None:
        self._conn.execute(
            "UPDATE reservations SET run_id = ?, reserved = ?, state = ?, "
            "created_at = ?, updated_at = ?, actual_cost = ?, released_amount = ?, "
            "overspend = ? WHERE id = ?",
            (
                reservation.run_id,
                str(reservation.reserved),
                reservation.state.value,
                reservation.created_at.isoformat(),
                reservation.updated_at.isoformat(),
                None if reservation.actual_cost is None else str(reservation.actual_cost),
                None
                if reservation.released_amount is None
                else str(reservation.released_amount),
                None if reservation.overspend is None else str(reservation.overspend),
                reservation.id,
            ),
        )

    def _active_total_unlocked(self) -> Decimal:
        row = self._conn.execute(
            "SELECT reserved FROM reservations WHERE state = ?",
            (ReservationState.ACTIVE.value,),
        ).fetchall()
        total = Decimal("0")
        for (reserved,) in row:
            total += Decimal(str(reserved))
        return total

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision_unlocked()

    @property
    def active_total(self) -> Decimal:
        with self._lock:
            return self._active_total_unlocked()

    def facts(self) -> LedgerFacts:
        with self._lock:
            return LedgerFacts(
                revision=self._revision_unlocked(),
                active_total=self._active_total_unlocked(),
            )

    def lookup(self, reservation_id: str) -> Reservation:
        with self._lock:
            return self._get_unlocked(reservation_id)

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
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                if expected != self._revision_unlocked():
                    raise LedgerRevisionConflictError(
                        "ledger revision changed before reservation"
                    )
                active = self._conn.execute(
                    "SELECT 1 FROM reservations WHERE state = ? LIMIT 1",
                    (ReservationState.ACTIVE.value,),
                ).fetchone()
                if active is not None:
                    raise ReservationConflictError("an active reservation already exists")
                timestamp = self._timestamp(now)
                try:
                    reservation_id = self._id_factory()
                except Exception as exc:
                    raise InvalidReservationError("id factory failed") from exc
                if not isinstance(reservation_id, str) or not reservation_id:
                    raise InvalidReservationError(
                        "id factory must return a non-empty string"
                    )
                exists = self._conn.execute(
                    "SELECT 1 FROM reservations WHERE id = ?", (reservation_id,)
                ).fetchone()
                if exists is not None:
                    raise ReservationConflictError("reservation id already exists")
                reservation = Reservation(
                    id=reservation_id,
                    run_id=run_id,
                    reserved=reserved,
                    state=ReservationState.ACTIVE,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                self._insert_unlocked(reservation)
                self._bump_revision_unlocked()
                self._conn.commit()
                return reservation
            except Exception:
                self._conn.rollback()
                raise

    def release(
        self, reservation_id: str, *, now: datetime | None = None
    ) -> Reservation:
        if now is not None:
            _require_aware(now, "timestamp")
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                reservation = self._get_unlocked(reservation_id)
                if reservation.state is ReservationState.RELEASED:
                    self._conn.commit()
                    return reservation
                if reservation.state is ReservationState.RECONCILED:
                    raise ReservationConflictError(
                        "reconciled reservation cannot be released"
                    )
                timestamp = self._timestamp(now)
                released = Reservation(
                    id=reservation.id,
                    run_id=reservation.run_id,
                    reserved=reservation.reserved,
                    state=ReservationState.RELEASED,
                    created_at=reservation.created_at,
                    updated_at=timestamp,
                    released_amount=reservation.reserved,
                )
                self._update_unlocked(released)
                self._bump_revision_unlocked()
                self._conn.commit()
                return released
            except Exception:
                self._conn.rollback()
                raise

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
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                reservation = self._get_unlocked(reservation_id)
                if reservation.state is ReservationState.RECONCILED:
                    if reservation.actual_cost == actual:
                        self._conn.commit()
                        return reservation
                    raise ReservationConflictError(
                        "reconciliation conflicts with recorded actual cost"
                    )
                if reservation.state is ReservationState.RELEASED:
                    raise ReservationConflictError(
                        "released reservation cannot be reconciled"
                    )
                timestamp = self._timestamp(now)
                released_amount = max(reservation.reserved - actual, Decimal("0"))
                overspend = max(actual - reservation.reserved, Decimal("0"))
                reconciled = Reservation(
                    id=reservation.id,
                    run_id=reservation.run_id,
                    reserved=reservation.reserved,
                    state=ReservationState.RECONCILED,
                    created_at=reservation.created_at,
                    updated_at=timestamp,
                    actual_cost=actual,
                    released_amount=released_amount,
                    overspend=overspend,
                )
                self._update_unlocked(reconciled)
                self._bump_revision_unlocked()
                self._conn.commit()
                return reconciled
            except Exception:
                self._conn.rollback()
                raise


__all__ = ["SqliteBudgetLedger"]
