from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

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
    PaidModelCallService,
    PaidModelEventError,
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
    def get_snapshot(self) -> UsageSnapshotV1:
        return UsageSnapshotV1(
            provider="deepseek",
            available=True,
            total_balance=Decimal("10"),
            currency="CNY",
            observed_at=NOW - timedelta(seconds=30),
            source_status=UsageSourceStatus.UP,
        )


class FakeExecutor:
    def __init__(self, result: ModelCallResult) -> None:
        self.result = result
        self.calls = []

    def invoke(self, request):
        self.calls.append(request)
        return self.result


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


def service_for(tmp_path: Path, result: ModelCallResult, *, sink: MemorySink | None = None):
    actual_sink = sink or MemorySink()
    ledger = SingleFlightBudgetLedger(clock=lambda: NOW, id_factory=lambda: "reservation-1")
    budget = BudgetAdmissionService(
        usage=FakeUsage(),
        guard=BudgetGuard(ledger, now=NOW),
        ledger=ledger,
        event_sink=actual_sink,
        clock=lambda: NOW,
    )
    executor = FakeExecutor(result)
    service = PaidModelCallService(
        router=ModelRouter(),
        archive=FilePromptArchive(tmp_path / "archive"),
        budget=budget,
        event_sink=actual_sink,
        executor=executor,
        clock=lambda: NOW,
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
