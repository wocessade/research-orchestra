from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
from bogda.flows.paid_model_call import run_paid_model_call
from bogda.model_runtime import (
    DshTokenUsageV1,
    FilePromptArchive,
    ModelCallOutcome,
    ModelCallResult,
    ModelRouter,
    PaidCallStatus,
    PaidModelArchiveError,
    PaidModelCallService,
)


NOW = datetime(2026, 8, 28, 8, 0, tzinfo=timezone.utc)
PRICING = "deepseek-cn-2026-08-28"
PROMPT = "secret-free research prompt"


class MemorySink(RunEventSink):
    def __init__(self) -> None:
        self.events = []

    def append(self, event) -> None:
        self.events.append(event)


class FakeUsage:
    def __init__(self, balance: Decimal) -> None:
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
    def __init__(self, result: ModelCallResult) -> None:
        self.result = result
        self.calls = []

    def invoke(self, request) -> ModelCallResult:
        self.calls.append(request)
        return self.result


class RecordingService:
    def __init__(self, service: PaidModelCallService) -> None:
        self.service = service
        self.requests = []
        self.resume_events = []

    def execute(self, *args, **kwargs):
        self.requests.append(args[2])
        return self.service.execute(*args, **kwargs)

    def record_budget_resume(self, run_id, call_id, request) -> None:
        self.resume_events.append((run_id, call_id))
        self.service.record_budget_resume(run_id, call_id, request)


class RestoringSuspender:
    def __init__(self, usage: FakeUsage) -> None:
        self.usage = usage
        self.keys = []

    def suspend(self, key: str) -> None:
        self.keys.append(key)
        self.usage.balance = Decimal("20")


def make_request(
    *,
    intent: TaskIntent = TaskIntent.EXPLORE,
    model_tier: ModelTier = ModelTier.AUTO,
    requested_tier: ModelTier = ModelTier.FLASH,
    fallback_tier: ModelTier | None = None,
    minimum_remaining: str = "1",
) -> JobRequest:
    return JobRequest(
        job_id="job-1",
        project_id="project-1",
        task_type="research",
        resource_class=ResourceClass.CPU,
        autonomy_mode=AutonomyMode.SUPERVISED,
        intent=intent,
        model_tier=model_tier,
        executor=ExecutorKind.DSH,
        budget=RunBudgetEnvelope(
            expected_cost=Decimal("1"),
            authorized_ceiling=Decimal("2"),
            minimum_remaining=Decimal(minimum_remaining),
            requested_tier=requested_tier,
            fallback_tier=fallback_tier,
            budget_source=BudgetSource.RUN,
            pricing_version=PRICING,
        ),
    )


def finished_result(
    *, actual_cost: str = "0.25", reference: str = "receipt-1"
) -> ModelCallResult:
    return ModelCallResult(
        outcome=ModelCallOutcome.FINISHED,
        output="secret model output",
        usage=DshTokenUsageV1(
            input_tokens=12,
            cache_read_tokens=3,
            output_tokens=8,
            actual_cost_cny=actual_cost,
            reference=reference,
        ),
    )


def service_for(
    tmp_path: Path,
    result: ModelCallResult,
    *,
    usage: FakeUsage | None = None,
):
    sink = MemorySink()
    ledger = SingleFlightBudgetLedger(
        clock=lambda: NOW,
        id_factory=lambda: "reservation-1",
    )
    budget = BudgetAdmissionService(
        usage=usage or FakeUsage(Decimal("10")),
        guard=BudgetGuard(ledger, now=NOW),
        ledger=ledger,
        event_sink=sink,
        clock=lambda: NOW,
    )
    executor = FakeExecutor(result)
    service = PaidModelCallService(
        router=ModelRouter(),
        archive=FilePromptArchive(tmp_path / "prompts"),
        budget=budget,
        event_sink=sink,
        executor=executor,
        clock=lambda: NOW,
    )
    return service, sink, ledger, executor


def test_auto_flash_archives_before_paid_execution_and_exactly_reconciles(
    tmp_path: Path,
) -> None:
    service, sink, ledger, executor = service_for(tmp_path, finished_result())

    result = service.execute(
        "run-1",
        "call-1",
        make_request(),
        PROMPT,
        tmp_path / "attempt",
        pro_available=True,
        allow_low_risk_fallback=False,
    )

    assert result.status is PaidCallStatus.FINISHED
    assert result.effective_tier is ModelTier.FLASH
    assert result.actual_cost_cny == Decimal("0.25")
    assert Path(result.prompt_artifact).read_text(encoding="utf-8") == PROMPT
    assert executor.calls[0].effective_tier is ModelTier.FLASH
    assert ledger.lookup("reservation-1").state.value == "reconciled"
    assert [event.event for event in sink.events] == [
        RunEventType.ROUTE_SELECTED,
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_RESERVED,
        RunEventType.MODEL_CALL_STARTED,
        RunEventType.MODEL_CALL_FINISHED,
        RunEventType.BUDGET_RELEASED,
    ]
    serialized = "\n".join(event.model_dump_json() for event in sink.events)
    assert PROMPT not in serialized
    assert "secret model output" not in serialized


def test_auto_audit_requires_pro_without_flash_downgrade(tmp_path: Path) -> None:
    service, sink, ledger, executor = service_for(tmp_path, finished_result())
    request = make_request(
        intent=TaskIntent.AUDIT,
        requested_tier=ModelTier.PRO,
        fallback_tier=ModelTier.FLASH,
    )

    result = service.execute(
        "run-1",
        "call-1",
        request,
        PROMPT,
        tmp_path / "attempt",
        pro_available=False,
        allow_low_risk_fallback=True,
    )

    assert result.status is PaidCallStatus.PRO_REQUIRED
    assert [event.event for event in sink.events] == [
        RunEventType.TIER_UPGRADE_REQUESTED
    ]
    assert sink.events[0].requested_tier is ModelTier.PRO
    assert sink.events[0].effective_tier is None
    assert ledger.active_total == Decimal("0")
    assert executor.calls == []
    assert not (tmp_path / "prompts").exists()


def test_low_risk_frozen_flash_fallback_records_requested_and_effective_tiers(
    tmp_path: Path,
) -> None:
    service, sink, _, executor = service_for(tmp_path, finished_result())
    request = make_request(
        model_tier=ModelTier.PRO,
        requested_tier=ModelTier.PRO,
        fallback_tier=ModelTier.FLASH,
    )

    result = service.execute(
        "run-1",
        "call-1",
        request,
        PROMPT,
        tmp_path / "attempt",
        pro_available=False,
        allow_low_risk_fallback=True,
    )

    assert result.status is PaidCallStatus.FINISHED
    assert result.requested_tier is ModelTier.PRO
    assert result.effective_tier is ModelTier.FLASH
    assert executor.calls[0].effective_tier is ModelTier.FLASH
    assert sink.events[0].event is RunEventType.TIER_DOWNGRADED
    assert sink.events[0].requested_tier is ModelTier.PRO
    assert sink.events[0].effective_tier is ModelTier.FLASH
    for event in sink.events:
        if event.event in {
            RunEventType.TIER_DOWNGRADED,
            RunEventType.MODEL_CALL_STARTED,
            RunEventType.MODEL_CALL_FINISHED,
        }:
            assert event.requested_tier is ModelTier.PRO
            assert event.effective_tier is ModelTier.FLASH


def test_missing_usage_keeps_one_reservation_and_blocks_same_call_retry(
    tmp_path: Path,
) -> None:
    service, sink, ledger, executor = service_for(
        tmp_path,
        ModelCallResult(outcome=ModelCallOutcome.USAGE_UNKNOWN),
    )
    request = make_request()

    first = service.execute(
        "run-1",
        "call-1",
        request,
        PROMPT,
        tmp_path / "attempt",
        pro_available=True,
        allow_low_risk_fallback=False,
    )
    second = service.execute(
        "run-1",
        "call-1",
        request,
        PROMPT,
        tmp_path / "attempt-retry",
        pro_available=True,
        allow_low_risk_fallback=False,
    )

    assert first.status is PaidCallStatus.USAGE_UNKNOWN
    assert second.status is PaidCallStatus.RECONCILIATION_REQUIRED
    assert ledger.lookup("reservation-1").state.value == "active"
    assert ledger.active_total == Decimal("2")
    assert len(executor.calls) == 1
    assert [event.event for event in sink.events] == [
        RunEventType.ROUTE_SELECTED,
        RunEventType.BUDGET_SNAPSHOT,
        RunEventType.BUDGET_RESERVED,
        RunEventType.MODEL_CALL_STARTED,
        RunEventType.MODEL_CALL_USAGE_UNKNOWN,
    ]


def test_insufficient_balance_suspends_and_resumes_identical_envelope(
    tmp_path: Path,
) -> None:
    usage = FakeUsage(Decimal("10"))
    service, sink, ledger, executor = service_for(
        tmp_path,
        finished_result(),
        usage=usage,
    )
    recording_service = RecordingService(service)
    suspender = RestoringSuspender(usage)
    request = make_request(minimum_remaining="9")
    payload = request.model_dump(mode="json")

    returned = run_paid_model_call.fn(
        payload,
        PROMPT,
        recording_service,
        suspender,
        run_id="run-1",
        call_id="call-1",
        attempt_dir=tmp_path / "attempt",
        pro_available=True,
        allow_low_risk_fallback=False,
    )

    assert returned["status"] == "finished"
    assert suspender.keys == ["budget-run-1-call-1-1"]
    assert recording_service.resume_events == [("run-1", "call-1")]
    assert recording_service.requests[0] is recording_service.requests[1]
    assert recording_service.requests[0].budget == request.budget
    assert executor.calls[0].prompt == PROMPT
    assert ledger.active_total == Decimal("0")
    assert [event.event for event in sink.events].count(
        RunEventType.BUDGET_PAUSED
    ) == 1
    assert [event.event for event in sink.events].count(
        RunEventType.BUDGET_RESUMED
    ) == 1


def test_archive_failure_creates_no_reservation_or_executor_call(tmp_path: Path) -> None:
    class FailingArchive:
        def archive(self, run_id, call_id, prompt):
            raise RuntimeError("prompt secret sentinel")

    service, sink, ledger, executor = service_for(tmp_path, finished_result())
    service._archive = FailingArchive()

    with pytest.raises(PaidModelArchiveError):
        service.execute(
            "run-1",
            "call-1",
            make_request(),
            PROMPT,
            tmp_path / "attempt",
            pro_available=True,
            allow_low_risk_fallback=False,
        )

    assert ledger.active_total == Decimal("0")
    assert executor.calls == []
    assert [event.event for event in sink.events] == [RunEventType.ROUTE_SELECTED]
