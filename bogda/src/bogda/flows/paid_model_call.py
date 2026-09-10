from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from prefect import flow
from prefect.context import get_run_context
from prefect.flow_runs import suspend_flow_run

from bogda.contracts import JobRequest
from bogda.model_runtime import PaidCallResult, PaidCallStatus, PaidModelCallService


class BudgetSuspender(Protocol):
    def suspend(self, key: str) -> None:
        ...


class PrefectBudgetSuspender:
    def suspend(self, key: str) -> None:
        suspend_flow_run(key=key, timeout=None)


def _payload_request(request_data: dict[str, Any]) -> dict[str, Any]:
    nested = request_data.get("job_request", request_data.get("request"))
    if isinstance(nested, dict):
        return nested
    metadata = {
        "run_id",
        "call_id",
        "attempt_dir",
        "pro_available",
        "allow_low_risk_fallback",
    }
    return {key: value for key, value in request_data.items() if key not in metadata}


def _payload_value(
    request_data: dict[str, Any], key: str, explicit: Any
) -> Any:
    return explicit if explicit is not None else request_data.get(key)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if hasattr(value, "value"):
        return value.value
    return value


def _result_payload(result: PaidCallResult) -> dict[str, Any]:
    return {
        "status": _json_value(result.status),
        "requested_tier": _json_value(result.requested_tier),
        "effective_tier": _json_value(result.effective_tier),
        "prompt_hash": result.prompt_hash,
        "prompt_artifact": result.prompt_artifact,
        "reservation_id": result.reservation_id,
        "actual_cost_cny": _json_value(result.actual_cost_cny),
        "usage_reference": result.usage_reference,
    }


@flow(name="bogda-paid-model-call", persist_result=True)
def run_paid_model_call(
    request_data: dict[str, Any],
    prompt: str,
    service: Any = None,
    suspender: Any = None,
    *,
    run_id: str | None = None,
    call_id: str | None = None,
    attempt_dir: str | Path | None = None,
    pro_available: bool | None = None,
    allow_low_risk_fallback: bool | None = None,
) -> dict[str, Any]:
    request = JobRequest.model_validate(_payload_request(request_data))
    resolved_run_id = _payload_value(request_data, "run_id", run_id)
    resolved_call_id = _payload_value(request_data, "call_id", call_id)
    resolved_attempt_dir = _payload_value(request_data, "attempt_dir", attempt_dir)
    resolved_pro_available = _payload_value(
        request_data, "pro_available", pro_available
    )
    resolved_fallback = _payload_value(
        request_data, "allow_low_risk_fallback", allow_low_risk_fallback
    )
    if not isinstance(resolved_run_id, str) or not resolved_run_id:
        resolved_run_id = str(get_run_context().flow_run.id)
    if not isinstance(resolved_call_id, str) or not resolved_call_id:
        resolved_call_id = "call-1"
    if resolved_attempt_dir is None:
        artifact_root = os.environ.get("BOGDA_ARTIFACT_ROOT", "").strip()
        if not artifact_root:
            raise ValueError("attempt_dir is required")
        resolved_attempt_dir = Path(artifact_root) / resolved_run_id / "attempt-0001"
    if not isinstance(resolved_pro_available, bool):
        raise ValueError("pro_available must be a boolean")
    if not isinstance(resolved_fallback, bool):
        raise ValueError("allow_low_risk_fallback must be a boolean")

    if service is None:
        from bogda.wiring.paid_runtime import build_paid_service_from_env

        service = build_paid_service_from_env(run_id=resolved_run_id)
    if not callable(getattr(service, "execute", None)):
        raise ValueError("service must implement PaidModelCallService.execute")

    budget_suspender = suspender or PrefectBudgetSuspender()
    suspension_round = 1
    while True:
        result = service.execute(
            resolved_run_id,
            resolved_call_id,
            request,
            prompt,
            Path(resolved_attempt_dir),
            pro_available=resolved_pro_available,
            allow_low_risk_fallback=resolved_fallback,
        )
        if result.status is not PaidCallStatus.BUDGET_PAUSED:
            return _result_payload(result)
        budget_suspender.suspend(
            f"budget-{resolved_run_id}-{resolved_call_id}-{suspension_round}"
        )
        service.record_budget_resume(resolved_run_id, resolved_call_id, request)
        suspension_round += 1
