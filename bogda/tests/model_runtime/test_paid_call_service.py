from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from itertools import count
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Callable

import pytest

from bogda.budget import (
    BudgetAdmissionService,
    BudgetGuard,
    SingleFlightBudgetLedger,
    UsageSnapshotV1,
    UsageSourceStatus,
)
from bogda.contracts import (
    AutonomyMode,
    BudgetSource,
    ExecutorKind,
    JobRequest,
    ModelTier,
    ResourceClass,
    RunBudgetEnvelope,
    RunEventType,
    TaskIntent,
)
from bogda.events.jsonl import RunEventSink
from bogda.model_runtime import (
    DshTokenUsageV1,
    FilePromptArchive,
    ModelCallOutcome,
    ModelCallResult,
    ModelRouter,
    PaidCallStatus,
    PaidModelBudgetError,
    PaidModelCallService,
    PaidModelClockError,
    PaidModelEventError,
    PaidModelExecutionError,
    PromptArtifactV1,
)


NOW = datetime(2026, 8, 28, 8, 0, tzinfo=timezone.utc)
PRICING = "deepseek-cn-2026-08-28"
PROMPT = "secret research prompt"


class MemorySink(RunEventSink):
    def __init__(self, fail_on: int | None = None) -> None:
        self.events = []
        self.fail_on = fail_on
        self.failed = False

    def append(self, event) -> None:
        if self.fail_on is not None and not self.failed and len(self.events) + 1 == self.fail_on:
            self.failed = True
            raise OSError("sink secret sentinel")
        self.events.append(event)


class FakeUsage:
    def __init__(self, balance: Decimal = Decimal("10")) -> None:
        self.balance = balance

    def get_snapshot(self) -> UsageSnapshotV1:
        return UsageSnapshotV1(
            provider="deepseek",
            available=True,
            total_balance=self.balance,
            currency="CNY",
            observed_at=NOW - timedelta(seconds=30),
            source_status=UsageSourceStatus.UP,
        )


class FakeExecutor:
    def __init__(self, result: ModelCallResult | BaseException) -> None:
        self.result = result
        self.calls = []

    def invoke(self, request):
        self.calls.append(request)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


class FirstCallBlockingArchive:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.first_entered = Event()
        self.release_first = Event()
        self.calls = 0
        self._lock = Lock()

    def archive(self, run_id: str, call_id: str, prompt: str) -> PromptArtifactV1:
        with self._lock:
            self.calls += 1
            call_number = self.calls
        if call_number == 1:
            self.first_entered.set()
            assert self.release_first.wait(5), "first archive call was not released"
        return PromptArtifactV1(
            path=str(self.root / run_id / f"{call_id}.prompt.md"),
            sha256=sha256(prompt.encode()).hexdigest(),
        )


class FailFirstBudgetReleasedSink(MemorySink):
    def append(self, event) -> None:
        if event.event is RunEventType.BUDGET_RELEASED and not self.failed:
            self.failed = True
            raise OSError("terminal event sentinel")
        super().append(event)


def usage(*, actual_cost: str | None = "0.25", reference: str = "receipt-1"):
    return DshTokenUsageV1(
        input_tokens=12,
        cache_read_tokens=3,
        output_tokens=8,
        actual_cost_cny=actual_cost,
        reference=reference,
    )


def request(
    *,
    intent: TaskIntent = TaskIntent.EXPLORE,
    tier: ModelTier = ModelTier.FLASH,
    fallback: ModelTier | None = None,
) -> JobRequest:
    return JobRequest(
        job_id="job-1",
        project_id="project-1",
        task_type="research",
        resource_class=ResourceClass.CPU,
        autonomy_mode=AutonomyMode.SUPERVISED,
        intent=intent,
        model_tier=tier,
        executor=ExecutorKind.DSH,
        budget=RunBudgetEnvelope(
            expected_cost=Decimal("1"),
            authorized_ceiling=Decimal("2"),
            minimum_remaining=Decimal("1"),
            requested_tier=tier,
            fallback_tier=fallback,
            budget_source=BudgetSource.RUN,
            pricing_version=PRICING,
        ),
    )


def service_for(
    tmp_path: Path,
    result: ModelCallResult | BaseException,
    *,
    sink: MemorySink | None = None,
    service_clock: Callable[[], datetime] | None = None,
    archive=None,
    usage_port: FakeUsage | None = None,
    id_factory: Callable[[], str] | None = None,
):
    actual_sink = sink or MemorySink()
    ledger = SingleFlightBudgetLedger(
        clock=lambda: NOW,
        id_factory=id_factory or (lambda: "reservation-1"),
    )
    budget = BudgetAdmissionService(
        usage=usage_port or FakeUsage(),
        guard=BudgetGuard(ledger, now=NOW),
        ledger=ledger,
        event_sink=actual_sink,
        clock=lambda: NOW,
    )
    executor = FakeExecutor(result)
    service = PaidModelCallService(
        router=ModelRouter(),
        archive=archive or FilePromptArchive(tmp_path / "archive"),
        budget=budget,
        event_sink=actual_sink,
        executor=executor,
        clock=service_clock or (lambda: NOW),
    )
    return service, actual_sink, ledger, executor


def finished_result(*, actual_cost: str | None = "0.25") -> ModelCallResult:
    return ModelCallResult(
        outcome=ModelCallOutcome.FINISHED,
        output="secret model output",
        usage=usage(actual_cost=actual_cost),
    )


def test_finished_call_archives_reserves_starts_finishes_then_reconciles(tmp_path: Path) -> None:
    service, sink, ledger, executor = service_for(tmp_path, finished_result())

    result = service.execute(
        "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
        pro_available=True, allow_low_risk_fallback=False,
    )

    assert result.status is PaidCallStatus.FINISHED
    assert result.actual_cost_cny == Decimal("0.25")
    assert executor.calls[0].prompt == PROMPT
    assert [event.event for event in sink.events] == [
        RunEventType.ROUTE_SELECTED,
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_RESERVED,
        RunEventType.MODEL_CALL_STARTED,
        RunEventType.MODEL_CALL_FINISHED,
        RunEventType.BUDGET_RELEASED,
    ]
    assert ledger.active_total == Decimal("0")


def test_provider_cost_is_used_exactly_and_local_cost_uses_cache_subset(tmp_path: Path) -> None:
    exact_service, _, _, _ = service_for(tmp_path / "exact", finished_result(actual_cost="0.0000007"))
    exact = exact_service.execute(
        "run-exact", "call-exact", request(), PROMPT, tmp_path / "attempt-exact",
        pro_available=True, allow_low_risk_fallback=False,
    )
    assert exact.actual_cost_cny == Decimal("0.0000007")

    local_service, _, _, _ = service_for(tmp_path / "local", finished_result(actual_cost=None))
    local = local_service.execute(
        "run-local", "call-local", request(), PROMPT, tmp_path / "attempt-local",
        pro_available=True, allow_low_risk_fallback=False,
    )
    # NOW is 16:00 in Beijing: peak Flash prices are used.
    assert local.actual_cost_cny == (
        Decimal("3") * Decimal("0.10")
        + Decimal("9") * Decimal("3.0")
        + Decimal("8") * Decimal("9.0")
    ) / Decimal("1000000")


def test_archive_failure_stops_before_admission_and_executor(tmp_path: Path) -> None:
    class BrokenArchive:
        def archive(self, run_id, call_id, prompt):
            raise RuntimeError("prompt secret sentinel")

    service, sink, ledger, executor = service_for(tmp_path, finished_result())
    service._archive = BrokenArchive()

    with pytest.raises(Exception) as raised:
        service.execute(
            "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
            pro_available=True, allow_low_risk_fallback=False,
        )

    assert "prompt secret sentinel" not in str(raised.value)
    assert [event.event for event in sink.events] == [RunEventType.ROUTE_SELECTED]
    assert ledger.active_total == Decimal("0")
    assert executor.calls == []


def test_pro_required_writes_upgrade_request_before_paid_boundary(tmp_path: Path) -> None:
    service, sink, ledger, executor = service_for(tmp_path, finished_result())

    result = service.execute(
        "run-1", "call-1", request(intent=TaskIntent.AUDIT, tier=ModelTier.PRO),
        PROMPT, tmp_path / "attempt", pro_available=False, allow_low_risk_fallback=True,
    )

    assert result.status is PaidCallStatus.PRO_REQUIRED
    assert [event.event for event in sink.events] == [RunEventType.TIER_UPGRADE_REQUESTED]
    assert sink.events[0].requested_tier is ModelTier.PRO
    assert sink.events[0].effective_tier is None
    assert sink.events[0].reason == "pro_unavailable"
    assert ledger.active_total == Decimal("0")
    assert executor.calls == []


def test_budget_denial_stops_before_executor(tmp_path: Path) -> None:
    service, sink, ledger, executor = service_for(tmp_path, finished_result())
    denied = request()
    denied = denied.model_copy(update={"budget": denied.budget.model_copy(update={"minimum_remaining": Decimal("9")})})

    result = service.execute(
        "run-1", "call-1", denied, PROMPT, tmp_path / "attempt",
        pro_available=True, allow_low_risk_fallback=False,
    )

    assert result.status is PaidCallStatus.BUDGET_PAUSED
    assert [event.event for event in sink.events] == [
        RunEventType.ROUTE_SELECTED, RunEventType.BUDGET_SNAPSHOT, RunEventType.BUDGET_PAUSED
    ]
    assert ledger.active_total == Decimal("0")
    assert executor.calls == []


def test_model_start_event_failure_releases_reservation_and_does_not_invoke(tmp_path: Path) -> None:
    sink = MemorySink(fail_on=4)
    service, sink, ledger, executor = service_for(tmp_path, finished_result(), sink=sink)

    with pytest.raises(PaidModelEventError) as raised:
        service.execute(
            "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
            pro_available=True, allow_low_risk_fallback=False,
        )

    assert "sink secret sentinel" not in str(raised.value)
    assert [event.event for event in sink.events] == [
        RunEventType.ROUTE_SELECTED,
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_RESERVED,
        RunEventType.BUDGET_RELEASED,
    ]
    assert ledger.active_total == Decimal("0")
    assert executor.calls == []


def test_not_started_releases_reservation(tmp_path: Path) -> None:
    service, sink, ledger, _ = service_for(tmp_path, ModelCallResult(outcome=ModelCallOutcome.NOT_STARTED))

    result = service.execute(
        "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
        pro_available=True, allow_low_risk_fallback=False,
    )

    assert result.status is PaidCallStatus.FAILED_NOT_STARTED
    assert sink.events[-1].event is RunEventType.BUDGET_RELEASED
    assert ledger.active_total == Decimal("0")


def test_unknown_usage_keeps_reservation_and_repeat_requires_reconciliation(tmp_path: Path) -> None:
    service, sink, ledger, executor = service_for(
        tmp_path,
        ModelCallResult(outcome=ModelCallOutcome.USAGE_UNKNOWN, output="partial secret"),
    )

    first = service.execute(
        "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
        pro_available=True, allow_low_risk_fallback=False,
    )
    second = service.execute(
        "run-1", "call-1", request(), "different secret prompt", tmp_path / "attempt-2",
        pro_available=True, allow_low_risk_fallback=False,
    )

    assert first.status is PaidCallStatus.USAGE_UNKNOWN
    assert second.status is PaidCallStatus.RECONCILIATION_REQUIRED
    assert ledger.active_total == Decimal("2")
    assert len(executor.calls) == 1
    assert [event.event for event in sink.events] == [
        RunEventType.ROUTE_SELECTED,
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_RESERVED,
        RunEventType.MODEL_CALL_STARTED,
        RunEventType.MODEL_CALL_USAGE_UNKNOWN,
    ]


def test_executor_exception_blocks_same_call_retry(tmp_path: Path) -> None:
    service, _, ledger, executor = service_for(
        tmp_path, RuntimeError("executor secret sentinel")
    )

    with pytest.raises(PaidModelExecutionError):
        service.execute(
            "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
            pro_available=True, allow_low_risk_fallback=False,
        )
    repeated = service.execute(
        "run-1", "call-1", request(), "different prompt", tmp_path / "attempt-2",
        pro_available=True, allow_low_risk_fallback=False,
    )

    assert repeated.status is PaidCallStatus.RECONCILIATION_REQUIRED
    assert ledger.active_total == Decimal("2")
    assert len(executor.calls) == 1


def test_usage_unknown_event_failure_blocks_same_call_retry(tmp_path: Path) -> None:
    sink = MemorySink(fail_on=5)
    service, _, ledger, executor = service_for(
        tmp_path,
        ModelCallResult(outcome=ModelCallOutcome.USAGE_UNKNOWN),
        sink=sink,
    )

    with pytest.raises(PaidModelEventError):
        service.execute(
            "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
            pro_available=True, allow_low_risk_fallback=False,
        )
    repeated = service.execute(
        "run-1", "call-1", request(), PROMPT, tmp_path / "attempt-2",
        pro_available=True, allow_low_risk_fallback=False,
    )

    assert repeated.status is PaidCallStatus.RECONCILIATION_REQUIRED
    assert ledger.active_total == Decimal("2")
    assert len(executor.calls) == 1


def test_finished_event_failure_blocks_same_call_retry(tmp_path: Path) -> None:
    sink = MemorySink(fail_on=5)
    service, _, ledger, executor = service_for(
        tmp_path, finished_result(), sink=sink
    )

    with pytest.raises(PaidModelEventError):
        service.execute(
            "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
            pro_available=True, allow_low_risk_fallback=False,
        )
    repeated = service.execute(
        "run-1", "call-1", request(), PROMPT, tmp_path / "attempt-2",
        pro_available=True, allow_low_risk_fallback=False,
    )

    assert repeated.status is PaidCallStatus.RECONCILIATION_REQUIRED
    assert ledger.active_total == Decimal("2")
    assert len(executor.calls) == 1


def test_reconcile_terminal_event_failure_blocks_duplicate_paid_execution(
    tmp_path: Path,
) -> None:
    sink = MemorySink(fail_on=6)
    service, _, ledger, executor = service_for(
        tmp_path, finished_result(), sink=sink
    )

    with pytest.raises(PaidModelBudgetError):
        service.execute(
            "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
            pro_available=True, allow_low_risk_fallback=False,
        )
    repeated = service.execute(
        "run-1", "call-1", request(), PROMPT, tmp_path / "attempt-2",
        pro_available=True, allow_low_risk_fallback=False,
    )

    assert ledger.lookup("reservation-1").state.value == "reconciled"
    assert repeated.status is PaidCallStatus.RECONCILIATION_REQUIRED
    assert len(executor.calls) == 1


def test_overlapping_same_call_cannot_execute_twice_after_terminal_event_failure(
    tmp_path: Path,
) -> None:
    archive = FirstCallBlockingArchive(tmp_path / "archive")
    sink = FailFirstBudgetReleasedSink()
    reservation_numbers = count(1)
    service, _, ledger, executor = service_for(
        tmp_path,
        finished_result(),
        sink=sink,
        archive=archive,
        id_factory=lambda: f"reservation-{next(reservation_numbers)}",
    )
    results = {}
    errors = {}
    done = {name: Event() for name in ("first", "overlap")}

    def invoke(name: str, attempt: str) -> None:
        try:
            results[name] = service.execute(
                "run-1",
                "call-1",
                request(),
                PROMPT,
                tmp_path / attempt,
                pro_available=True,
                allow_low_risk_fallback=False,
            )
        except BaseException as error:
            errors[name] = error
        finally:
            done[name].set()

    first = Thread(target=invoke, args=("first", "attempt-first"))
    overlap = Thread(target=invoke, args=("overlap", "attempt-overlap"))
    first.start()
    assert archive.first_entered.wait(5), "first call did not reach the archive"
    overlap.start()
    assert done["overlap"].wait(5), "overlapping call did not finish"
    archive.release_first.set()
    assert done["first"].wait(5), "first call did not finish"
    first.join()
    overlap.join()

    assert len(executor.calls) == 1
    assert archive.calls == 1
    event_types = [event.event for event in sink.events]
    assert event_types.count(RunEventType.ROUTE_SELECTED) == 1
    assert event_types.count(RunEventType.BUDGET_SNAPSHOT) == 1
    assert [result.status for result in results.values()] == [
        PaidCallStatus.RECONCILIATION_REQUIRED
    ]
    assert len(errors) == 1
    assert isinstance(next(iter(errors.values())), PaidModelBudgetError)
    assert ledger.lookup("reservation-1").state.value == "reconciled"


def test_pro_required_releases_claim_for_later_re_evaluation(tmp_path: Path) -> None:
    service, _, _, executor = service_for(tmp_path, finished_result())
    pro_request = request(intent=TaskIntent.AUDIT, tier=ModelTier.PRO)

    first = service.execute(
        "run-1", "call-1", pro_request, PROMPT, tmp_path / "attempt-first",
        pro_available=False, allow_low_risk_fallback=False,
    )
    retried = service.execute(
        "run-1", "call-1", pro_request, PROMPT, tmp_path / "attempt-retry",
        pro_available=True, allow_low_risk_fallback=False,
    )

    assert first.status is PaidCallStatus.PRO_REQUIRED
    assert retried.status is PaidCallStatus.FINISHED
    assert len(executor.calls) == 1


def test_budget_paused_releases_claim_for_later_re_evaluation(tmp_path: Path) -> None:
    usage_port = FakeUsage()
    service, _, _, executor = service_for(
        tmp_path, finished_result(), usage_port=usage_port
    )
    paused = request()
    paused = paused.model_copy(
        update={
            "budget": paused.budget.model_copy(
                update={"minimum_remaining": Decimal("9")}
            )
        }
    )

    first = service.execute(
        "run-1", "call-1", paused, PROMPT, tmp_path / "attempt-first",
        pro_available=True, allow_low_risk_fallback=False,
    )
    usage_port.balance = Decimal("20")
    retried = service.execute(
        "run-1", "call-1", paused, PROMPT, tmp_path / "attempt-retry",
        pro_available=True, allow_low_risk_fallback=False,
    )

    assert first.status is PaidCallStatus.BUDGET_PAUSED
    assert retried.status is PaidCallStatus.FINISHED
    assert len(executor.calls) == 1


def test_started_clock_failure_releases_before_executor(tmp_path: Path) -> None:
    class FailingStartedClock:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self) -> datetime:
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("clock secret sentinel")
            return NOW

    service, sink, ledger, executor = service_for(
        tmp_path, finished_result(), service_clock=FailingStartedClock()
    )

    with pytest.raises(PaidModelClockError) as raised:
        service.execute(
            "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
            pro_available=True, allow_low_risk_fallback=False,
        )

    assert "clock secret sentinel" not in str(raised.value)
    assert ledger.active_total == Decimal("0")
    assert executor.calls == []
    assert sink.events[-1].event is RunEventType.BUDGET_RELEASED


def test_provider_exact_cost_ignores_impossible_local_cache_split(
    tmp_path: Path,
) -> None:
    provider_usage = DshTokenUsageV1(
        input_tokens=2,
        cache_read_tokens=3,
        output_tokens=1,
        actual_cost_cny="0.125",
        reference="provider-exact",
    )
    service, _, ledger, _ = service_for(
        tmp_path,
        ModelCallResult(
            outcome=ModelCallOutcome.FINISHED,
            output="answer",
            usage=provider_usage,
        ),
    )

    result = service.execute(
        "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
        pro_available=True, allow_low_risk_fallback=False,
    )

    assert result.status is PaidCallStatus.FINISHED
    assert result.actual_cost_cny == Decimal("0.125")
    assert ledger.active_total == Decimal("0")


def test_impossible_receipt_retains_reservation_without_guessing_cost(tmp_path: Path) -> None:
    bad_usage = DshTokenUsageV1(
        input_tokens=2, cache_read_tokens=3, output_tokens=1, reference="bad-counts"
    )
    result_from_executor = ModelCallResult(
        outcome=ModelCallOutcome.FINISHED, output="answer", usage=bad_usage
    )
    service, sink, ledger, _ = service_for(tmp_path, result_from_executor)

    result = service.execute(
        "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
        pro_available=True, allow_low_risk_fallback=False,
    )

    assert result.status is PaidCallStatus.RECONCILIATION_REQUIRED
    assert result.actual_cost_cny is None
    assert ledger.active_total == Decimal("2")
    assert RunEventType.MODEL_CALL_FINISHED not in [event.event for event in sink.events]
    assert RunEventType.BUDGET_RELEASED not in [event.event for event in sink.events]


def test_events_contain_prompt_hash_and_path_but_neither_prompt_nor_output(tmp_path: Path) -> None:
    service, sink, _, _ = service_for(tmp_path, finished_result())

    service.execute(
        "run-1", "call-1", request(), PROMPT, tmp_path / "attempt",
        pro_available=True, allow_low_risk_fallback=False,
    )

    encoded = " ".join(event.model_dump_json() for event in sink.events)
    assert sha256(PROMPT.encode()).hexdigest() in encoded
    assert any(
        event.prompt_artifact == str(tmp_path / "archive" / "run-1" / "call-1.prompt.md")
        for event in sink.events
    )
    assert PROMPT not in encoded
    assert "secret model output" not in encoded


def test_record_budget_resume_appends_one_event_per_real_resume(tmp_path: Path) -> None:
    service, sink, _, _ = service_for(tmp_path, finished_result())

    service.record_budget_resume("run-1", "call-1", request())
    service.record_budget_resume("run-1", "call-1", request())

    resumed = [event for event in sink.events if event.event is RunEventType.BUDGET_RESUMED]
    assert len(resumed) == 2
    assert all(event.call_id == "call-1" for event in resumed)
    assert all(event.intent is TaskIntent.EXPLORE for event in resumed)
    assert all(event.requested_tier is ModelTier.FLASH for event in resumed)
    assert all(event.pricing_version == PRICING for event in resumed)
    assert all(event.reason == "budget_resumed" for event in resumed)
