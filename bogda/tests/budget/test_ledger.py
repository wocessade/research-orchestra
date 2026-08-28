from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import count
from threading import Barrier, Thread

import pytest

from bogda.budget.ledger import (
    BudgetLedgerError,
    InvalidReservationError,
    LedgerRevisionConflictError,
    ReservationState,
    Reservation,
    ReservationConflictError,
    SingleFlightBudgetLedger,
    UnknownReservationError,
)


NOW = datetime(2026, 8, 28, 8, 0, 0, 123456, tzinfo=timezone.utc)


def make_ledger() -> SingleFlightBudgetLedger:
    ids = count(1)
    return SingleFlightBudgetLedger(
        clock=lambda: NOW,
        id_factory=lambda: f"reservation-{next(ids)}",
    )


def test_reserve_returns_immutable_explainable_reservation_and_updates_revision() -> None:
    ledger = make_ledger()

    reservation = ledger.reserve(
        run_id="run-1",
        amount=Decimal("1.2300"),
        expected_revision=0,
    )

    assert reservation.id == "reservation-1"
    assert reservation.run_id == "run-1"
    assert reservation.reserved == Decimal("1.2300")
    assert reservation.state is ReservationState.ACTIVE
    assert reservation.created_at == NOW
    assert reservation.updated_at == NOW
    assert ledger.revision == 1
    assert ledger.active_total == Decimal("1.2300")
    assert ledger.lookup(reservation.id) == reservation
    with pytest.raises((AttributeError, TypeError)):
        reservation.state = ReservationState.RELEASED  # type: ignore[misc]


def test_reserve_rejects_float_bool_zero_negative_and_naive_amounts() -> None:
    ledger = make_ledger()
    for amount in (1.0, True, Decimal("0"), Decimal("-1")):
        with pytest.raises(InvalidReservationError):
            ledger.reserve(run_id="run", amount=amount, expected_revision=0)

    with pytest.raises(InvalidReservationError):
        ledger.reserve(run_id="run", amount=Decimal("NaN"), expected_revision=0)

    naive_clock = SingleFlightBudgetLedger(clock=lambda: NOW.replace(tzinfo=None))
    with pytest.raises(InvalidReservationError, match="timezone-aware"):
        naive_clock.reserve(
            run_id="run", amount=Decimal("1"), expected_revision=0
        )


def test_reserve_requires_current_revision_and_single_active_reservation() -> None:
    ledger = make_ledger()
    first = ledger.reserve(
        run_id="run-1", amount=Decimal("1"), expected_revision=0
    )

    with pytest.raises(LedgerRevisionConflictError):
        ledger.reserve(run_id="run-2", amount=Decimal("1"), expected_revision=0)
    with pytest.raises(ReservationConflictError):
        ledger.reserve(run_id="run-2", amount=Decimal("1"), expected_revision=1)
    assert ledger.lookup(first.id).state is ReservationState.ACTIVE
    assert ledger.revision == 1


def test_competing_reserves_have_one_winner() -> None:
    ledger = make_ledger()
    barrier = Barrier(2)
    results: list[object] = []

    def attempt(run_id: str) -> None:
        barrier.wait()
        try:
            results.append(
                ledger.reserve(
                    run_id=run_id,
                    amount=Decimal("1"),
                    expected_revision=0,
                )
            )
        except BudgetLedgerError as exc:
            results.append(exc)

    threads = [Thread(target=attempt, args=(f"run-{index}",)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert ledger.revision == 1
    assert ledger.active_total == Decimal("1")


def test_release_is_idempotent_but_reconcile_after_release_conflicts() -> None:
    ledger = make_ledger()
    reservation = ledger.reserve(
        run_id="run", amount=Decimal("2"), expected_revision=0
    )

    released = ledger.release(reservation.id)
    assert released.state is ReservationState.RELEASED
    assert released.released_amount == Decimal("2")
    assert ledger.revision == 2
    assert ledger.release(reservation.id) == released
    assert ledger.revision == 2
    with pytest.raises(ReservationConflictError):
        ledger.reconcile(reservation.id, Decimal("1"))


def test_idempotent_replays_still_reject_explicit_naive_times() -> None:
    ledger = make_ledger()
    reservation = ledger.reserve(
        run_id="run", amount=Decimal("2"), expected_revision=0
    )
    released = ledger.release(reservation.id)

    with pytest.raises(InvalidReservationError, match="timezone-aware"):
        ledger.release(reservation.id, now=NOW.replace(tzinfo=None))

    reconciled_ledger = make_ledger()
    reconciled = reconciled_ledger.reserve(
        run_id="run", amount=Decimal("2"), expected_revision=0
    )
    reconciled_ledger.reconcile(reconciled.id, Decimal("1"))
    with pytest.raises(InvalidReservationError, match="timezone-aware"):
        reconciled_ledger.reconcile(
            reconciled.id,
            Decimal("1"),
            now=NOW.replace(tzinfo=None),
        )


def test_reservation_terminal_facts_are_consistent() -> None:
    with pytest.raises(InvalidReservationError):
        Reservation(
            id="r",
            run_id="run",
            reserved=Decimal("1"),
            state=ReservationState.ACTIVE,
            created_at=NOW,
            updated_at=NOW,
            actual_cost=Decimal("1"),
        )
    with pytest.raises(InvalidReservationError):
        Reservation(
            id="r",
            run_id="run",
            reserved=Decimal("1"),
            state=ReservationState.RELEASED,
            created_at=NOW,
            updated_at=NOW,
        )
    with pytest.raises(InvalidReservationError):
        Reservation(
            id="r",
            run_id="run",
            reserved=Decimal("1"),
            state=ReservationState.RECONCILED,
            created_at=NOW,
            updated_at=NOW,
            actual_cost=Decimal("1"),
            released_amount=Decimal("1"),
        )


@pytest.mark.parametrize(
    ("actual", "released", "overspend"),
    [
        (Decimal("1.25"), Decimal("0.75"), Decimal("0")),
        (Decimal("2"), Decimal("0"), Decimal("0")),
        (Decimal("2.25"), Decimal("0"), Decimal("0.25")),
    ],
)
def test_reconcile_records_actual_cost_and_release_facts(
    actual: Decimal, released: Decimal, overspend: Decimal
) -> None:
    ledger = make_ledger()
    reservation = ledger.reserve(
        run_id="run", amount=Decimal("2"), expected_revision=0
    )

    reconciled = ledger.reconcile(reservation.id, actual)

    assert reconciled.state is ReservationState.RECONCILED
    assert reconciled.actual_cost == actual
    assert reconciled.released_amount == released
    assert reconciled.overspend == overspend
    assert ledger.active_total == Decimal("0")
    assert ledger.revision == 2
    assert ledger.reconcile(reservation.id, actual) == reconciled
    assert ledger.revision == 2
    with pytest.raises(ReservationConflictError):
        ledger.reconcile(reservation.id, actual + Decimal("0.01"))


def test_unknown_reservation_ids_fail_explicitly() -> None:
    ledger = make_ledger()
    for operation in (
        lambda: ledger.lookup("missing"),
        lambda: ledger.release("missing"),
        lambda: ledger.reconcile("missing", Decimal("1")),
    ):
        with pytest.raises(UnknownReservationError):
            operation()


def test_reconcile_rejects_float_bool_and_negative_actual_cost() -> None:
    ledger = make_ledger()
    reservation = ledger.reserve(
        run_id="run", amount=Decimal("2"), expected_revision=0
    )
    for actual in (1.0, True, Decimal("-1"), Decimal("Infinity")):
        with pytest.raises(InvalidReservationError):
            ledger.reconcile(reservation.id, actual)


def test_clock_is_used_for_each_real_mutation() -> None:
    times = iter((NOW, NOW + timedelta(seconds=1), NOW + timedelta(seconds=2)))
    ledger = SingleFlightBudgetLedger(clock=lambda: next(times), id_factory=lambda: "r")
    reservation = ledger.reserve(
        run_id="run", amount=Decimal("1"), expected_revision=0
    )
    assert reservation.created_at == NOW
    released = ledger.release(reservation.id)
    assert released.updated_at == NOW + timedelta(seconds=1)
