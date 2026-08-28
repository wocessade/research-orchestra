from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from math import isfinite
from pathlib import Path
from threading import RLock
from typing import Callable

from bogda.budget import BudgetAdmissionService
from bogda.budget.pricing import estimate_token_cost, period_at
from bogda.contracts import JobRequest, ModelTier, RunEventType, RunEventV1
from bogda.events.jsonl import RunEventSink
from bogda.model_runtime.contracts import (
    ModelCallOutcome,
    ModelCallRequest,
    ModelExecutionPort,
    PromptArchivePort,
)
from bogda.model_runtime.routing import ModelRouter, RouteDecisionKind


class PaidModelRuntimeError(RuntimeError):
    """Base class for safe paid-call coordinator failures."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class PaidModelEventError(PaidModelRuntimeError):
    """An audit event could not be written."""


class PaidModelCompensationError(PaidModelEventError):
    """A reservation could not be released after an event failure."""


class PaidModelArchiveError(PaidModelRuntimeError):
    """The prompt could not be archived."""


class PaidModelBudgetError(PaidModelRuntimeError):
    """The budget admission service failed safely."""


class PaidModelExecutionError(PaidModelRuntimeError):
    """The execution port failed safely."""


class PaidModelClockError(PaidModelRuntimeError):
    """The coordinator clock did not provide an aware timestamp."""


class PaidCallStatus(StrEnum):
    FINISHED = "finished"
    PRO_REQUIRED = "pro_required"
    BUDGET_PAUSED = "budget_paused"
    FAILED_NOT_STARTED = "failed_not_started"
    USAGE_UNKNOWN = "usage_unknown"
    RECONCILIATION_REQUIRED = "reconciliation_required"


@dataclass(frozen=True, slots=True)
class PaidCallResult:
    status: PaidCallStatus
    requested_tier: ModelTier
    effective_tier: ModelTier | None
    prompt_hash: str | None = None
    prompt_artifact: str | None = None
    reservation_id: str | None = None
    actual_cost_cny: Decimal | None = None
    usage_reference: str | None = None


class PaidModelCallService:
    """Coordinate one archived, admitted, audited paid model call."""

    def __init__(
        self,
        *,
        router: ModelRouter,
        archive: PromptArchivePort,
        budget: BudgetAdmissionService,
        event_sink: RunEventSink,
        executor: ModelExecutionPort,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = 300.0,
    ) -> None:
        if not callable(getattr(router, "select", None)):
            raise ValueError("router must implement ModelRouter")
        if not callable(getattr(archive, "archive", None)):
            raise ValueError("archive must implement PromptArchivePort")
        if not callable(getattr(budget, "admit", None)):
            raise ValueError("budget must implement BudgetAdmissionService")
        if not callable(getattr(event_sink, "append", None)):
            raise ValueError("event_sink must implement RunEventSink")
        if not callable(getattr(executor, "invoke", None)):
            raise ValueError("executor must implement ModelExecutionPort")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be callable")
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not isfinite(float(timeout_seconds))
            or timeout_seconds <= 0
        ):
            raise ValueError("timeout_seconds must be positive")
        self._router = router
        self._archive = archive
        self._budget = budget
        self._event_sink = event_sink
        self._executor = executor
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout_seconds = timeout_seconds
        self._call_states: dict[tuple[str, str], PaidCallStatus | object] = {}
        self._state_lock = RLock()

    def _now(self) -> datetime:
        try:
            value = self._clock()
        except Exception:
            raise PaidModelClockError("clock failed") from None
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise PaidModelClockError("clock must return a timezone-aware datetime")
        return value

    def _append(self, event: RunEventV1) -> None:
        try:
            self._event_sink.append(event)
        except Exception:
            raise PaidModelEventError("event write failed") from None

    @staticmethod
    def _result(
        status: PaidCallStatus,
        *,
        requested_tier: ModelTier,
        effective_tier: ModelTier | None,
        artifact=None,
        reservation_id: str | None = None,
        actual_cost_cny: Decimal | None = None,
        usage_reference: str | None = None,
    ) -> PaidCallResult:
        return PaidCallResult(
            status=status,
            requested_tier=requested_tier,
            effective_tier=effective_tier,
            prompt_hash=None if artifact is None else artifact.sha256,
            prompt_artifact=None if artifact is None else artifact.path,
            reservation_id=reservation_id,
            actual_cost_cny=actual_cost_cny,
            usage_reference=usage_reference,
        )

    def _claim(self, run_id: str, call_id: str) -> object | None:
        claim = object()
        with self._state_lock:
            key = (run_id, call_id)
            if key in self._call_states:
                return None
            self._call_states[key] = claim
        return claim

    def _clear_initial_claim(self, run_id: str, call_id: str, claim: object) -> None:
        with self._state_lock:
            key = (run_id, call_id)
            if self._call_states.get(key) is claim:
                self._call_states.pop(key)

    def _remember(self, run_id: str, call_id: str, status: PaidCallStatus) -> None:
        with self._state_lock:
            self._call_states[(run_id, call_id)] = status

    def _clear(self, run_id: str, call_id: str) -> None:
        with self._state_lock:
            self._call_states.pop((run_id, call_id), None)

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
        claim = self._claim(run_id, call_id)
        if claim is None:
            return self._result(
                PaidCallStatus.RECONCILIATION_REQUIRED,
                requested_tier=request.budget.requested_tier,
                effective_tier=None,
            )
        try:
            return self._execute_claimed(
                run_id,
                call_id,
                request,
                prompt,
                attempt_dir,
                pro_available=pro_available,
                allow_low_risk_fallback=allow_low_risk_fallback,
            )
        finally:
            self._clear_initial_claim(run_id, call_id, claim)

    def _execute_claimed(
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

        try:
            decision = self._router.select(
                request,
                pro_available=pro_available,
                allow_low_risk_fallback=allow_low_risk_fallback,
            )
        except Exception:
            raise PaidModelRuntimeError("model route failed") from None

        if decision.kind is RouteDecisionKind.PRO_REQUIRED:
            self._append(
                RunEventV1(
                    event=RunEventType.TIER_UPGRADE_REQUESTED,
                    run_id=run_id,
                    call_id=call_id,
                    occurred_at=self._now(),
                    intent=request.intent,
                    requested_tier=decision.requested_tier,
                    reason="pro_unavailable",
                )
            )
            return self._result(
                PaidCallStatus.PRO_REQUIRED,
                requested_tier=decision.requested_tier,
                effective_tier=None,
            )

        route_event = RunEventType.ROUTE_SELECTED
        route_reason = "route_selected"
        if decision.kind is RouteDecisionKind.DOWNGRADED:
            route_event = RunEventType.TIER_DOWNGRADED
            route_reason = "low_risk_fallback"
        self._append(
            RunEventV1(
                event=route_event,
                run_id=run_id,
                call_id=call_id,
                occurred_at=self._now(),
                intent=request.intent,
                requested_tier=decision.requested_tier,
                effective_tier=decision.effective_tier,
                reason=route_reason,
            )
        )

        try:
            artifact = self._archive.archive(run_id, call_id, prompt)
        except Exception:
            raise PaidModelArchiveError("prompt archive failed") from None

        try:
            admission = self._budget.admit(run_id, request.intent, request.budget)
        except Exception:
            raise PaidModelBudgetError("budget admission failed") from None
        if not admission.decision.allowed:
            return self._result(
                PaidCallStatus.BUDGET_PAUSED,
                requested_tier=decision.requested_tier,
                effective_tier=decision.effective_tier,
                artifact=artifact,
            )
        reservation = admission.reservation
        assert reservation is not None

        try:
            self._append(
                RunEventV1(
                    event=RunEventType.MODEL_CALL_STARTED,
                    run_id=run_id,
                    call_id=call_id,
                    occurred_at=self._now(),
                    intent=request.intent,
                    requested_tier=decision.requested_tier,
                    effective_tier=decision.effective_tier,
                    reservation_id=reservation.id,
                    prompt_hash=artifact.sha256,
                    prompt_artifact=artifact.path,
                    reason="model_call_started",
                )
            )
        except Exception as error:
            try:
                self._budget.release(
                    reservation.id,
                    intent=request.intent,
                    requested_tier=request.budget.requested_tier,
                    pricing_version=request.budget.pricing_version,
                )
            except Exception:
                self._remember(
                    run_id, call_id, PaidCallStatus.RECONCILIATION_REQUIRED
                )
                raise PaidModelCompensationError("reservation compensation failed") from None
            if isinstance(error, PaidModelRuntimeError):
                raise
            raise PaidModelEventError("model call start event failed") from None

        self._remember(run_id, call_id, PaidCallStatus.RECONCILIATION_REQUIRED)

        try:
            result = self._executor.invoke(
                ModelCallRequest(
                    run_id=run_id,
                    call_id=call_id,
                    effective_tier=decision.effective_tier,
                    attempt_dir=attempt_dir,
                    timeout_seconds=self._timeout_seconds,
                    prompt=prompt,
                )
            )
        except Exception:
            raise PaidModelExecutionError("model execution failed") from None

        if result.outcome is ModelCallOutcome.NOT_STARTED:
            try:
                self._budget.release(
                    reservation.id,
                    intent=request.intent,
                    requested_tier=request.budget.requested_tier,
                    pricing_version=request.budget.pricing_version,
                )
            except Exception:
                raise PaidModelBudgetError("reservation release failed") from None
            self._clear(run_id, call_id)
            return self._result(
                PaidCallStatus.FAILED_NOT_STARTED,
                requested_tier=decision.requested_tier,
                effective_tier=decision.effective_tier,
                artifact=artifact,
                reservation_id=reservation.id,
            )

        if result.outcome is ModelCallOutcome.USAGE_UNKNOWN:
            self._append(
                RunEventV1(
                    event=RunEventType.MODEL_CALL_USAGE_UNKNOWN,
                    run_id=run_id,
                    call_id=call_id,
                    occurred_at=self._now(),
                    intent=request.intent,
                    requested_tier=decision.requested_tier,
                    effective_tier=decision.effective_tier,
                    reservation_id=reservation.id,
                    prompt_hash=artifact.sha256,
                    prompt_artifact=artifact.path,
                    reason="usage_unknown",
                )
            )
            return self._result(
                PaidCallStatus.USAGE_UNKNOWN,
                requested_tier=decision.requested_tier,
                effective_tier=decision.effective_tier,
                artifact=artifact,
                reservation_id=reservation.id,
            )

        usage = result.usage
        assert usage is not None
        try:
            actual_cost = usage.actual_cost_cny
            if actual_cost is None:
                if usage.cache_read_tokens > usage.input_tokens:
                    raise ValueError("cache usage counts are impossible")
                pricing_now = self._now()
                actual_cost = estimate_token_cost(
                    decision.effective_tier,
                    period_at(pricing_now),
                    cache_hit_input_tokens=usage.cache_read_tokens,
                    cache_miss_input_tokens=usage.input_tokens - usage.cache_read_tokens,
                    output_tokens=usage.output_tokens,
                    as_of=pricing_now,
                )
            if not isinstance(actual_cost, Decimal) or not actual_cost.is_finite() or actual_cost < 0:
                raise ValueError("local pricing did not produce an exact cost")
        except Exception:
            return self._result(
                PaidCallStatus.RECONCILIATION_REQUIRED,
                requested_tier=decision.requested_tier,
                effective_tier=decision.effective_tier,
                artifact=artifact,
                reservation_id=reservation.id,
            )

        self._append(
            RunEventV1(
                event=RunEventType.MODEL_CALL_FINISHED,
                run_id=run_id,
                call_id=call_id,
                occurred_at=self._now(),
                intent=request.intent,
                requested_tier=decision.requested_tier,
                effective_tier=decision.effective_tier,
                reservation_id=reservation.id,
                prompt_hash=artifact.sha256,
                prompt_artifact=artifact.path,
                usage_reference=usage.reference,
                actual_cost_cny=actual_cost,
                reason="model_call_finished",
            )
        )
        try:
            self._budget.reconcile(
                reservation.id,
                actual_cost,
                intent=request.intent,
                requested_tier=request.budget.requested_tier,
                pricing_version=request.budget.pricing_version,
            )
        except Exception:
            raise PaidModelBudgetError("reservation reconciliation failed") from None
        self._clear(run_id, call_id)
        return self._result(
            PaidCallStatus.FINISHED,
            requested_tier=decision.requested_tier,
            effective_tier=decision.effective_tier,
            artifact=artifact,
            reservation_id=reservation.id,
            actual_cost_cny=actual_cost,
            usage_reference=usage.reference,
        )

    def record_budget_resume(self, run_id: str, call_id: str, request: JobRequest) -> None:
        if request.budget is None:
            raise PaidModelRuntimeError("budget resume requires a budget envelope")
        self._append(
            RunEventV1(
                event=RunEventType.BUDGET_RESUMED,
                run_id=run_id,
                call_id=call_id,
                occurred_at=self._now(),
                intent=request.intent,
                requested_tier=request.budget.requested_tier,
                pricing_version=request.budget.pricing_version,
                reason="budget_resumed",
            )
        )


__all__ = [
    "PaidCallResult",
    "PaidCallStatus",
    "PaidModelArchiveError",
    "PaidModelBudgetError",
    "PaidModelCallService",
    "PaidModelClockError",
    "PaidModelCompensationError",
    "PaidModelEventError",
    "PaidModelExecutionError",
    "PaidModelRuntimeError",
]
