from datetime import datetime, timezone
from decimal import Decimal
from itertools import count
from pathlib import Path

import pytest

from bogda.budget.durable_ledger import SqliteBudgetLedger
from bogda.budget.ledger import (
    LedgerRevisionConflictError,
    ReservationConflictError,
    ReservationState,
    UnknownReservationError,
)


NOW = datetime(2026, 8, 30, 5, 0, 0, tzinfo=timezone.utc)


def make_ledger(path: Path) -> SqliteBudgetLedger:
    ids = count(1)
    return SqliteBudgetLedger(
        path,
        clock=lambda: NOW,
        id_factory=lambda: f"reservation-{next(ids)}",
    )


def test_reserve_survives_process_reopen(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite"
    first = make_ledger(path)
    reservation = first.reserve(
        run_id="run-1",
        amount=Decimal("1.2500"),
        expected_revision=0,
    )
    first.close()

    second = SqliteBudgetLedger(path)
    loaded = second.lookup(reservation.id)
    assert loaded.run_id == "run-1"
    assert loaded.reserved == Decimal("1.2500")
    assert loaded.state is ReservationState.ACTIVE
    assert second.revision == 1
    assert second.active_total == Decimal("1.2500")
    with pytest.raises(ReservationConflictError):
        second.reserve(
            run_id="run-2",
            amount=Decimal("1"),
            expected_revision=1,
        )
    second.close()


def test_stale_revision_conflicts_after_reopen(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite"
    ledger = make_ledger(path)
    ledger.reserve(run_id="run", amount=Decimal("1"), expected_revision=0)
    ledger.close()

    reopened = SqliteBudgetLedger(path)
    with pytest.raises(LedgerRevisionConflictError):
        reopened.reserve(run_id="other", amount=Decimal("1"), expected_revision=0)
    reopened.close()


def test_unknown_lookup_and_release_reconcile_parity(tmp_path: Path) -> None:
    path = tmp_path / "ledger.sqlite"
    ledger = make_ledger(path)
    with pytest.raises(UnknownReservationError):
        ledger.lookup("missing")
    reservation = ledger.reserve(
        run_id="run", amount=Decimal("2"), expected_revision=0
    )
    released = ledger.release(reservation.id)
    assert released.state is ReservationState.RELEASED
    assert ledger.release(reservation.id) == released
    with pytest.raises(ReservationConflictError):
        ledger.reconcile(reservation.id, Decimal("1"))
    ledger.close()

    reopened = SqliteBudgetLedger(path)
    assert reopened.lookup(reservation.id).state is ReservationState.RELEASED
    assert reopened.active_total == Decimal("0")
    reopened.close()
