from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from bogda.contracts import (
    AutonomyMode,
    BudgetSource,
    ExecutorKind,
    JobRequest,
    ModelTier,
    ResourceClass,
    RunBudgetEnvelope,
    TaskIntent,
)
from bogda.flows import paid_model_call
from bogda.model_runtime import PaidCallResult, PaidCallStatus


PROMPT = "secret-free research prompt"


def request_payload() -> dict:
    return JobRequest(
        job_id="job-1",
        project_id="project-1",
        task_type="research",
        resource_class=ResourceClass.CPU,
        autonomy_mode=AutonomyMode.SUPERVISED,
        intent=TaskIntent.EXPLORE,
        model_tier=ModelTier.FLASH,
        executor=ExecutorKind.DSH,
        budget=RunBudgetEnvelope(
            expected_cost=Decimal("1"),
            authorized_ceiling=Decimal("2"),
            minimum_remaining=Decimal("1"),
            requested_tier=ModelTier.FLASH,
            budget_source=BudgetSource.RUN,
            pricing_version="deepseek-cn-2026-08-28",
        ),
    ).model_dump(mode="json")


def result(status: PaidCallStatus | str) -> PaidCallResult:
    return PaidCallResult(
        status=status,
        requested_tier=ModelTier.FLASH,
        effective_tier=ModelTier.FLASH,
    )


class ScriptedService:
    def __init__(self, results: list[PaidCallResult]) -> None:
        self.results = iter(results)
        self.requests: list[JobRequest] = []
        self.calls: list[tuple[str, str, str, Path, bool, bool]] = []
        self.resume_events: list[tuple[str, str]] = []

    def execute(
        self,
        run_id: str,
        call_id: str,
        request: JobRequest,
        prompt: str,
        attempt_dir: Path,
        *,
        pro_available: bool,
        allow_low_risk_fallback: bool,
    ) -> PaidCallResult:
        self.requests.append(request)
        self.calls.append(
            (
                run_id,
                call_id,
                prompt,
                attempt_dir,
                pro_available,
                allow_low_risk_fallback,
            )
        )
        return next(self.results)

    def record_budget_resume(
        self, run_id: str, call_id: str, request: JobRequest
    ) -> None:
        self.resume_events.append((run_id, call_id))


class RecordingSuspender:
    def __init__(self) -> None:
        self.keys: list[str] = []

    def suspend(self, key: str) -> None:
        self.keys.append(key)


def call_flow(
    service: ScriptedService,
    suspender: RecordingSuspender | None = None,
    *,
    run_id: str = "run-1",
    call_id: str = "call-1",
    attempt_dir: Path = Path("attempts/run-1"),
    pro_available: bool = True,
    allow_low_risk_fallback: bool = False,
) -> dict:
    return paid_model_call.run_paid_model_call.fn(
        request_payload(),
        PROMPT,
        service,
        suspender,
        run_id=run_id,
        call_id=call_id,
        attempt_dir=attempt_dir,
        pro_available=pro_available,
        allow_low_risk_fallback=allow_low_risk_fallback,
    )


def test_flow_self_identifies_from_context_when_ids_omitted(monkeypatch) -> None:
    service = ScriptedService([result(PaidCallStatus.FINISHED)])
    monkeypatch.setattr(
        paid_model_call,
        "get_run_context",
        lambda: SimpleNamespace(flow_run=SimpleNamespace(id="flow-run-id-1")),
    )
    monkeypatch.setenv("BOGDA_ARTIFACT_ROOT", "/tmp/artifact-root")

    returned = paid_model_call.run_paid_model_call.fn(
        request_payload(),
        PROMPT,
        service,
        RecordingSuspender(),
        pro_available=True,
        allow_low_risk_fallback=False,
    )

    assert returned["status"] == "finished"
    assert service.calls[0][0] == "flow-run-id-1"
    assert service.calls[0][1] == "call-1"
    assert str(service.calls[0][3]) == str(
        Path("/tmp/artifact-root") / "flow-run-id-1" / "attempt-0001"
    )


def test_flow_constructs_service_from_env_when_omitted(monkeypatch) -> None:
    built: list[str] = []
    service = ScriptedService([result(PaidCallStatus.FINISHED)])

    def fake_factory(*, run_id: str):
        built.append(run_id)
        return service

    monkeypatch.setattr(
        "bogda.wiring.paid_runtime.build_paid_service_from_env", fake_factory
    )

    returned = paid_model_call.run_paid_model_call.fn(
        request_payload(),
        PROMPT,
        None,
        RecordingSuspender(),
        run_id="run-9",
        call_id="call-9",
        attempt_dir=Path("attempts/run-9"),
        pro_available=True,
        allow_low_risk_fallback=False,
    )

    assert built == ["run-9"]
    assert returned["status"] == "finished"


def test_budget_pause_suspends_then_rechecks_same_request() -> None:
    service = ScriptedService(
        [result(PaidCallStatus.BUDGET_PAUSED), result(PaidCallStatus.FINISHED)]
    )
    suspender = RecordingSuspender()

    returned = call_flow(service, suspender)

    assert suspender.keys == ["budget-run-1-call-1-1"]
    assert service.resume_events == [("run-1", "call-1")]
    assert service.requests[0] is service.requests[1]
    assert service.requests[0].budget == service.requests[1].budget
    assert returned["status"] == "finished"


def test_multiple_budget_pauses_use_numbered_keys_and_resume_once_each() -> None:
    service = ScriptedService(
        [
            result(PaidCallStatus.BUDGET_PAUSED),
            result(PaidCallStatus.BUDGET_PAUSED),
            result(PaidCallStatus.FINISHED),
        ]
    )
    suspender = RecordingSuspender()

    returned = call_flow(service, suspender)

    assert suspender.keys == [
        "budget-run-1-call-1-1",
        "budget-run-1-call-1-2",
    ]
    assert service.resume_events == [("run-1", "call-1"), ("run-1", "call-1")]
    assert len(service.calls) == 3
    assert returned["status"] == "finished"


@pytest.mark.parametrize(
    "status",
    [
        PaidCallStatus.PRO_REQUIRED,
        PaidCallStatus.USAGE_UNKNOWN,
        PaidCallStatus.RECONCILIATION_REQUIRED,
        PaidCallStatus.FAILED_NOT_STARTED,
        PaidCallStatus.FINISHED,
        "scheduled",
    ],
)
def test_non_budget_status_returns_without_suspension_or_retry(
    status: PaidCallStatus | str,
) -> None:
    service = ScriptedService([result(status)])
    suspender = RecordingSuspender()

    returned = call_flow(service, suspender)

    assert returned["status"] == str(status)
    assert suspender.keys == []
    assert service.resume_events == []
    assert len(service.calls) == 1


def test_return_is_json_safe_and_preserves_result_fields() -> None:
    service = ScriptedService(
        [
            PaidCallResult(
                status=PaidCallStatus.FINISHED,
                requested_tier=ModelTier.FLASH,
                effective_tier=ModelTier.FLASH,
                prompt_hash="a" * 64,
                prompt_artifact="attempts/prompt.md",
                reservation_id="reservation-1",
                actual_cost_cny=Decimal("0.25"),
                usage_reference="receipt-1",
            )
        ]
    )

    returned = call_flow(service)

    assert json.dumps(returned)
    assert returned == {
        "status": "finished",
        "requested_tier": "flash",
        "effective_tier": "flash",
        "prompt_hash": "a" * 64,
        "prompt_artifact": "attempts/prompt.md",
        "reservation_id": "reservation-1",
        "actual_cost_cny": "0.25",
        "usage_reference": "receipt-1",
    }


def test_flow_is_persistent_and_real_suspender_forwards_to_prefect(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        paid_model_call,
        "suspend_flow_run",
        lambda **kwargs: calls.append(kwargs),
    )

    assert paid_model_call.run_paid_model_call.persist_result is True
    paid_model_call.PrefectBudgetSuspender().suspend("budget-run-1-call-1-1")

    assert calls == [{"key": "budget-run-1-call-1-1", "timeout": None}]
