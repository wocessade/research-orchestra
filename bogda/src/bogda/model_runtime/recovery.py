"""Durable owner-controlled recovery for paid calls with unknown usage."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from sqlite3 import Connection, connect
from threading import RLock
from typing import Callable, Protocol, runtime_checkable
from uuid import uuid4

from bogda.budget.service import BudgetAdmissionService
from bogda.contracts import ModelTier, RunEventType, RunEventV1, TaskIntent
from bogda.events.jsonl import RunEventSink


class UsageUnknownError(ValueError):
    """Base class for safe usage-unknown recovery failures."""


class UsageUnknownConflictError(UsageUnknownError):
    """A durable case or owner command conflicts with recorded facts."""


class UsageUnknownNotFoundError(UsageUnknownError):
    """The requested recovery case does not exist."""


class UsageUnknownRevisionConflictError(UsageUnknownConflictError):
    """An owner command was evaluated against a stale case revision."""


class UsageUnknownStateError(UsageUnknownError):
    """The requested owner command is not valid for the case state."""


class UsageUnknownBudgetError(UsageUnknownError):
    """The durable budget authority rejected reconciliation."""


class UsageUnknownEventError(UsageUnknownError):
    """The recovery event could not be appended safely."""


class UsageUnknownState(StrEnum):
    AWAITING_RECONCILIATION = "awaiting_reconciliation"
    AWAITING_RETRY_DECISION = "awaiting_retry_decision"
    RETRY_APPROVED = "retry_approved"
    TERMINATED = "terminated"


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _intent(value: object) -> TaskIntent:
    try:
        return value if isinstance(value, TaskIntent) else TaskIntent(value)
    except (TypeError, ValueError):
        raise ValueError("intent is invalid") from None


def _tier(value: object, name: str) -> ModelTier:
    try:
        return value if isinstance(value, ModelTier) else ModelTier(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} is invalid") from None


def _optional_tier(value: object) -> ModelTier | None:
    if value is None:
        return None
    return _tier(value, "effective_tier")


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise ValueError(f"{name} must be a Decimal")
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


def _revision(value: object) -> int:
    if type(value) is not int or value < 0:
        raise UsageUnknownRevisionConflictError(
            "expected_revision must be a non-negative integer"
        )
    return value


@dataclass(frozen=True, slots=True)
class UsageUnknownCase:
    """Immutable durable context and owner-decision state for one paid call."""

    case_id: str
    run_id: str
    call_id: str
    reservation_id: str
    intent: TaskIntent
    requested_tier: ModelTier
    effective_tier: ModelTier | None
    pricing_version: str
    state: UsageUnknownState
    revision: int
    created_at: datetime
    updated_at: datetime
    actual_cost_cny: Decimal | None = None
    new_call_id: str | None = None
    prompt_hash: str | None = None
    prompt_artifact: str | None = None

    def __post_init__(self) -> None:
        _text(self.case_id, "case_id")
        _text(self.run_id, "run_id")
        _text(self.call_id, "call_id")
        _text(self.reservation_id, "reservation_id")
        if not isinstance(self.intent, TaskIntent):
            raise ValueError("intent is invalid")
        if not isinstance(self.requested_tier, ModelTier):
            raise ValueError("requested_tier is invalid")
        if self.effective_tier is not None and not isinstance(
            self.effective_tier, ModelTier
        ):
            raise ValueError("effective_tier is invalid")
        _text(self.pricing_version, "pricing_version")
        if not isinstance(self.state, UsageUnknownState):
            raise ValueError("state is invalid")
        if type(self.revision) is not int or self.revision < 0:
            raise ValueError("revision must be a non-negative integer")
        created = _aware(self.created_at, "created_at")
        updated = _aware(self.updated_at, "updated_at")
        if updated < created:
            raise ValueError("updated_at cannot precede created_at")
        if self.actual_cost_cny is not None:
            _decimal(self.actual_cost_cny, "actual_cost_cny")
        if self.new_call_id is not None:
            _text(self.new_call_id, "new_call_id")
        if self.prompt_hash is not None:
            _text(self.prompt_hash, "prompt_hash")
        if self.prompt_artifact is not None:
            _text(self.prompt_artifact, "prompt_artifact")

    @property
    def original_call_id(self) -> str:
        return self.call_id


@runtime_checkable
class UsageUnknownRecoveryPort(Protocol):
    """Port used by the paid-call coordinator to persist an unknown case."""

    def open_case(
        self,
        *,
        run_id: str,
        call_id: str,
        reservation_id: str,
        intent: TaskIntent,
        requested_tier: ModelTier,
        effective_tier: ModelTier | None,
        pricing_version: str,
        prompt_hash: str | None = None,
        prompt_artifact: str | None = None,
        case_id: str | None = None,
    ) -> UsageUnknownCase:
        ...

    def blocks_original_call(self, run_id: str, call_id: str) -> bool:
        ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage_unknown_cases (
    case_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    call_id TEXT NOT NULL,
    reservation_id TEXT NOT NULL,
    intent TEXT NOT NULL,
    requested_tier TEXT NOT NULL,
    effective_tier TEXT,
    pricing_version TEXT NOT NULL,
    state TEXT NOT NULL,
    revision INTEGER NOT NULL,
    actual_cost_cny TEXT,
    new_call_id TEXT,
    prompt_hash TEXT,
    prompt_artifact TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (run_id, call_id, reservation_id)
);
"""


def _parse_timestamp(value: object, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise UsageUnknownError(f"stored {name} is invalid") from None
    return _aware(parsed, name)


def _parse_decimal(value: object, name: str) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except Exception:
        raise UsageUnknownError(f"stored {name} is invalid") from None
    return _decimal(parsed, name)


def _row_to_case(row: tuple[object, ...]) -> UsageUnknownCase:
    return UsageUnknownCase(
        case_id=str(row[0]),
        run_id=str(row[1]),
        call_id=str(row[2]),
        reservation_id=str(row[3]),
        intent=_intent(row[4]),
        requested_tier=_tier(row[5], "requested_tier"),
        effective_tier=_optional_tier(row[6]),
        pricing_version=str(row[7]),
        state=UsageUnknownState(str(row[8])),
        revision=int(row[9]),
        actual_cost_cny=_parse_decimal(row[10], "actual_cost_cny"),
        new_call_id=None if row[11] is None else str(row[11]),
        prompt_hash=None if row[12] is None else str(row[12]),
        prompt_artifact=None if row[13] is None else str(row[13]),
        created_at=_parse_timestamp(row[14], "created_at"),
        updated_at=_parse_timestamp(row[15], "updated_at"),
    )


def _context_tuple(case: UsageUnknownCase) -> tuple[object, ...]:
    return (
        case.run_id,
        case.call_id,
        case.reservation_id,
        case.intent,
        case.requested_tier,
        case.effective_tier,
        case.pricing_version,
        case.prompt_hash,
        case.prompt_artifact,
    )


class SqliteUsageUnknownStore:
    """SQLite persistence for usage-unknown cases and their owner state."""

    def __init__(
        self,
        path: Path,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(path, Path):
            raise ValueError("path must be a Path")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be callable")
        if id_factory is not None and not callable(id_factory):
            raise ValueError("id_factory must be callable")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: uuid4().hex)
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
            return _aware(self._clock() if now is None else now, "timestamp")
        except UsageUnknownError:
            raise
        except Exception:
            raise UsageUnknownError("clock failed") from None

    def _get_unlocked(self, case_id: str) -> UsageUnknownCase:
        _text(case_id, "case_id")
        row = self._conn.execute(
            "SELECT case_id, run_id, call_id, reservation_id, intent, "
            "requested_tier, effective_tier, pricing_version, state, revision, "
            "actual_cost_cny, new_call_id, prompt_hash, prompt_artifact, "
            "created_at, updated_at FROM usage_unknown_cases WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        if row is None:
            raise UsageUnknownNotFoundError("usage unknown case is unknown")
        try:
            return _row_to_case(row)
        except UsageUnknownError:
            raise
        except Exception:
            raise UsageUnknownError("stored usage unknown case is invalid") from None

    def get_case(self, case_id: str) -> UsageUnknownCase:
        with self._lock:
            return self._get_unlocked(case_id)

    def get(self, case_id: str) -> UsageUnknownCase:
        return self.get_case(case_id)

    def lookup(self, case_id: str) -> UsageUnknownCase:
        return self.get_case(case_id)

    def blocks_original_call(self, run_id: str, call_id: str) -> bool:
        run = _text(run_id, "run_id")
        call = _text(call_id, "call_id")
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM usage_unknown_cases "
                "WHERE run_id = ? AND call_id = ? LIMIT 1",
                (run, call),
            ).fetchone()
        return row is not None

    @staticmethod
    def _candidate(
        *,
        case_id: str,
        run_id: str,
        call_id: str,
        reservation_id: str,
        intent: object,
        requested_tier: object,
        effective_tier: object,
        pricing_version: str,
        timestamp: datetime,
        prompt_hash: str | None,
        prompt_artifact: str | None,
    ) -> UsageUnknownCase:
        return UsageUnknownCase(
            case_id=_text(case_id, "case_id"),
            run_id=_text(run_id, "run_id"),
            call_id=_text(call_id, "call_id"),
            reservation_id=_text(reservation_id, "reservation_id"),
            intent=_intent(intent),
            requested_tier=_tier(requested_tier, "requested_tier"),
            effective_tier=_optional_tier(effective_tier),
            pricing_version=_text(pricing_version, "pricing_version"),
            state=UsageUnknownState.AWAITING_RECONCILIATION,
            revision=0,
            created_at=timestamp,
            updated_at=timestamp,
            prompt_hash=prompt_hash,
            prompt_artifact=prompt_artifact,
        )

    def open_case(
        self,
        *,
        run_id: str,
        call_id: str,
        reservation_id: str,
        intent: TaskIntent,
        requested_tier: ModelTier,
        effective_tier: ModelTier | None = None,
        pricing_version: str,
        prompt_hash: str | None = None,
        prompt_artifact: str | None = None,
        case_id: str | None = None,
        now: datetime | None = None,
    ) -> UsageUnknownCase:
        timestamp = self._timestamp(now)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                requested_case_id = None if case_id is None else _text(case_id, "case_id")
                existing_row = None
                if requested_case_id is not None:
                    existing_row = self._conn.execute(
                        "SELECT case_id, run_id, call_id, reservation_id, intent, "
                        "requested_tier, effective_tier, pricing_version, state, revision, "
                        "actual_cost_cny, new_call_id, prompt_hash, prompt_artifact, "
                        "created_at, updated_at FROM usage_unknown_cases WHERE case_id = ?",
                        (requested_case_id,),
                    ).fetchone()
                if existing_row is None:
                    existing_row = self._conn.execute(
                        "SELECT case_id, run_id, call_id, reservation_id, intent, "
                        "requested_tier, effective_tier, pricing_version, state, revision, "
                        "actual_cost_cny, new_call_id, prompt_hash, prompt_artifact, "
                        "created_at, updated_at FROM usage_unknown_cases "
                        "WHERE run_id = ? AND call_id = ? AND reservation_id = ?",
                        (run_id, call_id, reservation_id),
                    ).fetchone()
                candidate_id = requested_case_id
                if existing_row is not None:
                    existing = _row_to_case(existing_row)
                    candidate = self._candidate(
                        case_id=existing.case_id,
                        run_id=run_id,
                        call_id=call_id,
                        reservation_id=reservation_id,
                        intent=intent,
                        requested_tier=requested_tier,
                        effective_tier=effective_tier,
                        pricing_version=pricing_version,
                        timestamp=existing.created_at,
                        prompt_hash=prompt_hash,
                        prompt_artifact=prompt_artifact,
                    )
                    if _context_tuple(existing) != _context_tuple(candidate):
                        raise UsageUnknownConflictError("case context conflicts")
                    self._conn.commit()
                    return existing
                if candidate_id is None:
                    try:
                        candidate_id = self._id_factory()
                    except Exception:
                        raise UsageUnknownError("case id factory failed") from None
                if not isinstance(candidate_id, str) or not candidate_id.strip():
                    raise UsageUnknownError("case id factory must return a non-empty string")
                candidate = self._candidate(
                    case_id=candidate_id,
                    run_id=run_id,
                    call_id=call_id,
                    reservation_id=reservation_id,
                    intent=intent,
                    requested_tier=requested_tier,
                    effective_tier=effective_tier,
                    pricing_version=pricing_version,
                    timestamp=timestamp,
                    prompt_hash=prompt_hash,
                    prompt_artifact=prompt_artifact,
                )
                self._conn.execute(
                    "INSERT INTO usage_unknown_cases ("
                    "case_id, run_id, call_id, reservation_id, intent, requested_tier, "
                    "effective_tier, pricing_version, state, revision, actual_cost_cny, "
                    "new_call_id, prompt_hash, prompt_artifact, created_at, updated_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        candidate.case_id,
                        candidate.run_id,
                        candidate.call_id,
                        candidate.reservation_id,
                        candidate.intent.value,
                        candidate.requested_tier.value,
                        None
                        if candidate.effective_tier is None
                        else candidate.effective_tier.value,
                        candidate.pricing_version,
                        candidate.state.value,
                        candidate.revision,
                        None,
                        None,
                        candidate.prompt_hash,
                        candidate.prompt_artifact,
                        candidate.created_at.isoformat(),
                        candidate.updated_at.isoformat(),
                    ),
                )
                self._conn.commit()
                return candidate
            except Exception:
                self._conn.rollback()
                raise

    def update_case(
        self,
        case: UsageUnknownCase,
        *,
        expected_revision: int,
    ) -> UsageUnknownCase:
        if not isinstance(case, UsageUnknownCase):
            raise ValueError("case must be a UsageUnknownCase")
        expected = _revision(expected_revision)
        if case.revision != expected + 1:
            raise UsageUnknownRevisionConflictError("case revision is not monotonic")
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                current = self._get_unlocked(case.case_id)
                if current.revision != expected:
                    raise UsageUnknownRevisionConflictError("stale case revision")
                if _context_tuple(current) != _context_tuple(case):
                    raise UsageUnknownConflictError("case context conflicts")
                if case.created_at != current.created_at:
                    raise UsageUnknownConflictError("case creation timestamp conflicts")
                cursor = self._conn.execute(
                    "UPDATE usage_unknown_cases SET state = ?, revision = ?, "
                    "actual_cost_cny = ?, new_call_id = ?, updated_at = ? "
                    "WHERE case_id = ? AND revision = ?",
                    (
                        case.state.value,
                        case.revision,
                        None if case.actual_cost_cny is None else str(case.actual_cost_cny),
                        case.new_call_id,
                        case.updated_at.isoformat(),
                        case.case_id,
                        expected,
                    ),
                )
                if cursor.rowcount != 1:
                    raise UsageUnknownRevisionConflictError("stale case revision")
                self._conn.commit()
                return case
            except Exception:
                self._conn.rollback()
                raise

    def save_case(
        self,
        case: UsageUnknownCase,
        *,
        expected_revision: int,
    ) -> UsageUnknownCase:
        return self.update_case(case, expected_revision=expected_revision)


class UsageUnknownRecoveryService:
    """Reconcile an unknown paid call before authorizing one owner decision."""

    def __init__(
        self,
        *,
        store: SqliteUsageUnknownStore,
        budget: BudgetAdmissionService,
        event_sink: RunEventSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not callable(getattr(store, "open_case", None)):
            raise ValueError("store must implement SqliteUsageUnknownStore")
        if not callable(getattr(store, "get_case", None)):
            raise ValueError("store must implement get_case")
        if not callable(getattr(store, "update_case", None)):
            raise ValueError("store must implement update_case")
        if not callable(getattr(budget, "reconcile", None)):
            raise ValueError("budget must implement reconcile")
        if not callable(getattr(event_sink, "append", None)):
            raise ValueError("event_sink must implement RunEventSink")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be callable")
        self._store = store
        self._budget = budget
        self._event_sink = event_sink
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        try:
            return _aware(self._clock(), "timestamp")
        except UsageUnknownError:
            raise
        except Exception:
            raise UsageUnknownError("clock failed") from None

    def _append(self, event: RunEventV1) -> None:
        try:
            self._event_sink.append(event)
        except Exception:
            raise UsageUnknownEventError("event write failed") from None

    def open_case(
        self,
        *,
        run_id: str,
        call_id: str,
        reservation_id: str,
        intent: TaskIntent,
        requested_tier: ModelTier,
        effective_tier: ModelTier | None = None,
        pricing_version: str,
        prompt_hash: str | None = None,
        prompt_artifact: str | None = None,
        case_id: str | None = None,
    ) -> UsageUnknownCase:
        return self._store.open_case(
            run_id=run_id,
            call_id=call_id,
            reservation_id=reservation_id,
            intent=intent,
            requested_tier=requested_tier,
            effective_tier=effective_tier,
            pricing_version=pricing_version,
            prompt_hash=prompt_hash,
            prompt_artifact=prompt_artifact,
            case_id=case_id,
        )

    def get_case(self, case_id: str) -> UsageUnknownCase:
        return self._store.get_case(case_id)

    def blocks_original_call(self, run_id: str, call_id: str) -> bool:
        return self._store.blocks_original_call(run_id, call_id)

    def _current(self, case_id: str, expected_revision: int) -> UsageUnknownCase:
        expected = _revision(expected_revision)
        case = self._store.get_case(case_id)
        if case.revision != expected:
            raise UsageUnknownRevisionConflictError("stale case revision")
        return case

    @staticmethod
    def _finished_event(
        case: UsageUnknownCase,
        *,
        actual_cost_cny: Decimal,
        occurred_at: datetime,
    ) -> RunEventV1:
        return RunEventV1(
            event=RunEventType.MODEL_CALL_FINISHED,
            run_id=case.run_id,
            call_id=case.call_id,
            occurred_at=occurred_at,
            intent=case.intent,
            requested_tier=case.requested_tier,
            effective_tier=case.effective_tier,
            reservation_id=case.reservation_id,
            actual_cost_cny=actual_cost_cny,
            usage_reference=f"manual-reconciliation:{case.case_id}",
            pricing_version=case.pricing_version,
            prompt_hash=case.prompt_hash,
            prompt_artifact=case.prompt_artifact,
            reason="manual_usage_reconciliation",
        )

    @staticmethod
    def _resumed_event(
        case: UsageUnknownCase,
        *,
        new_call_id: str,
        occurred_at: datetime,
    ) -> RunEventV1:
        return RunEventV1(
            event=RunEventType.BUDGET_RESUMED,
            run_id=case.run_id,
            call_id=new_call_id,
            occurred_at=occurred_at,
            intent=case.intent,
            requested_tier=case.requested_tier,
            effective_tier=case.effective_tier,
            reservation_id=case.reservation_id,
            pricing_version=case.pricing_version,
            reason="budget_resumed",
        )

    def reconcile(
        self,
        case_id: str,
        actual_cost_cny: Decimal,
        *,
        expected_revision: int,
    ) -> UsageUnknownCase:
        actual = _decimal(actual_cost_cny, "actual_cost_cny")
        case = self._current(case_id, expected_revision)
        if case.state is UsageUnknownState.AWAITING_RETRY_DECISION:
            if case.actual_cost_cny != actual:
                raise UsageUnknownConflictError(
                    "reconciliation conflicts with recorded cost"
                )
            return case
        if case.state is not UsageUnknownState.AWAITING_RECONCILIATION:
            raise UsageUnknownStateError("case is not awaiting reconciliation")
        try:
            self._budget.reconcile(
                case.reservation_id,
                actual,
                intent=case.intent,
                requested_tier=case.requested_tier,
                pricing_version=case.pricing_version,
            )
        except UsageUnknownError:
            raise
        except Exception:
            raise UsageUnknownBudgetError("reservation reconciliation failed") from None
        timestamp = self._now()
        self._append(
            self._finished_event(
                case,
                actual_cost_cny=actual,
                occurred_at=timestamp,
            )
        )
        updated = replace(
            case,
            state=UsageUnknownState.AWAITING_RETRY_DECISION,
            revision=case.revision + 1,
            updated_at=timestamp,
            actual_cost_cny=actual,
        )
        return self._store.update_case(updated, expected_revision=case.revision)

    def approve_retry(
        self,
        case_id: str,
        *,
        new_call_id: str,
        expected_revision: int,
    ) -> UsageUnknownCase:
        new_call = _text(new_call_id, "new_call_id")
        case = self._current(case_id, expected_revision)
        if new_call == case.call_id:
            raise UsageUnknownConflictError(
                "new_call_id must differ from the original call_id"
            )
        if case.state is UsageUnknownState.RETRY_APPROVED:
            if case.new_call_id == new_call:
                return case
            raise UsageUnknownStateError("retry is already approved")
        if case.state is UsageUnknownState.TERMINATED:
            raise UsageUnknownStateError("case is already terminated")
        if case.state is not UsageUnknownState.AWAITING_RETRY_DECISION:
            raise UsageUnknownStateError("case requires reconciliation first")
        timestamp = self._now()
        self._append(
            self._resumed_event(
                case,
                new_call_id=new_call,
                occurred_at=timestamp,
            )
        )
        updated = replace(
            case,
            state=UsageUnknownState.RETRY_APPROVED,
            revision=case.revision + 1,
            updated_at=timestamp,
            new_call_id=new_call,
        )
        return self._store.update_case(updated, expected_revision=case.revision)

    def terminate(
        self,
        case_id: str,
        *,
        expected_revision: int,
    ) -> UsageUnknownCase:
        case = self._current(case_id, expected_revision)
        if case.state is UsageUnknownState.TERMINATED:
            return case
        if case.state is UsageUnknownState.RETRY_APPROVED:
            raise UsageUnknownStateError("retry is already approved")
        if case.state is not UsageUnknownState.AWAITING_RETRY_DECISION:
            raise UsageUnknownStateError("case requires reconciliation first")
        timestamp = self._now()
        updated = replace(
            case,
            state=UsageUnknownState.TERMINATED,
            revision=case.revision + 1,
            updated_at=timestamp,
        )
        return self._store.update_case(updated, expected_revision=case.revision)


__all__ = [
    "SqliteUsageUnknownStore",
    "UsageUnknownCase",
    "UsageUnknownBudgetError",
    "UsageUnknownConflictError",
    "UsageUnknownError",
    "UsageUnknownEventError",
    "UsageUnknownNotFoundError",
    "UsageUnknownRecoveryPort",
    "UsageUnknownRecoveryService",
    "UsageUnknownRevisionConflictError",
    "UsageUnknownState",
    "UsageUnknownStateError",
]
