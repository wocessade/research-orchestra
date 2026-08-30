from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from bogda.budget.estimation import (
    HistoricalUsageProfile,
    TokenWorkload,
    WorkloadEstimate,
    WorkloadEstimator,
)
from bogda.budget.pricing import (
    BEIJING_TIMEZONE,
    PricePeriod,
    _peak_windows,
    period_for_window,
)
from bogda.contracts import ModelTier, PricePreference, SchedulePolicy, TaskIntent


class ScheduleDisposition(StrEnum):
    START_NOW = "start_now"
    WAIT_FOR_OFF_PEAK = "wait_for_off_peak"
    WAIT_FOR_EARLIEST = "wait_for_earliest"


@dataclass(frozen=True, slots=True)
class PriceAwareSchedulePlan:
    disposition: ScheduleDisposition
    reason: str
    scheduled_start: datetime
    current_period: PricePeriod
    scheduled_period: PricePeriod
    current_estimate: WorkloadEstimate
    scheduled_estimate: WorkloadEstimate
    estimated_savings: Decimal
    deadline_forced: bool


def _require_aware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _next_pricing_boundary(instant: datetime) -> datetime:
    local = instant.astimezone(BEIJING_TIMEZONE)
    current_day: date = local.date()
    while True:
        boundaries = [
            boundary
            for window in _peak_windows(current_day)
            for boundary in window
            if boundary > local
        ]
        if boundaries:
            return min(boundaries)
        current_day += timedelta(days=1)


def _next_off_peak_start(start: datetime, duration: timedelta) -> datetime | None:
    candidate = start
    weekly_horizon = start + timedelta(days=7)
    while candidate < weekly_horizon:
        if period_for_window(candidate, candidate + duration) is PricePeriod.OFF_PEAK:
            return candidate
        candidate = _next_pricing_boundary(candidate)
    return None


class PriceAwareScheduler:
    """Plan a paid-call start around the reviewed Asia/Shanghai price windows."""

    def __init__(self, *, estimator: WorkloadEstimator | None = None) -> None:
        self._estimator = estimator or WorkloadEstimator()

    def plan(
        self,
        *,
        intent: TaskIntent,
        tier: ModelTier,
        workload: TokenWorkload,
        runtime_minutes: int,
        policy: SchedulePolicy,
        now: datetime,
        history: HistoricalUsageProfile | None = None,
    ) -> PriceAwareSchedulePlan:
        """Return a deterministic plan without sleeping or enqueueing."""

        now = _require_aware(now, "now")
        if type(runtime_minutes) is not int or runtime_minutes <= 0:
            raise ValueError("runtime_minutes must be positive")
        duration = timedelta(minutes=runtime_minutes)
        earliest_start = policy.earliest_start or now
        effective_start = max(now, earliest_start)
        deadline = policy.deadline
        if deadline is not None and effective_start + duration > deadline:
            raise ValueError("runtime cannot finish before deadline")
        waiting_for_earliest = effective_start > now

        current_estimate = self._estimator.estimate(
            intent=intent,
            tier=tier,
            workload=workload,
            start=now,
            end=now + duration,
            as_of=now,
            history=history,
        )

        if policy.price_preference is PricePreference.IMMEDIATE:
            scheduled_start = effective_start
            scheduled_estimate = self._estimator.estimate(
                intent=intent,
                tier=tier,
                workload=workload,
                start=scheduled_start,
                end=scheduled_start + duration,
                as_of=now,
                history=history,
            )
            return self._build_plan(
                disposition=(
                    ScheduleDisposition.WAIT_FOR_EARLIEST
                    if waiting_for_earliest
                    else ScheduleDisposition.START_NOW
                ),
                reason="immediate",
                scheduled_start=scheduled_start,
                current_estimate=current_estimate,
                scheduled_estimate=scheduled_estimate,
                deadline_forced=False,
            )

        candidate = _next_off_peak_start(effective_start, duration)
        candidate_fits = (
            candidate is not None
            and (deadline is None or candidate + duration <= deadline)
        )
        if candidate_fits:
            scheduled_start = candidate
            scheduled_estimate = self._estimator.estimate(
                intent=intent,
                tier=tier,
                workload=workload,
                start=scheduled_start,
                end=scheduled_start + duration,
                as_of=now,
                history=history,
            )
            waiting = scheduled_start != now
            return self._build_plan(
                disposition=(
                    ScheduleDisposition.WAIT_FOR_EARLIEST
                    if waiting_for_earliest and scheduled_start == effective_start
                    else ScheduleDisposition.WAIT_FOR_OFF_PEAK
                    if waiting
                    else ScheduleDisposition.START_NOW
                ),
                reason=(
                    "cheapest_before_deadline"
                    if waiting
                    else "already_off_peak"
                ),
                scheduled_start=scheduled_start,
                current_estimate=current_estimate,
                scheduled_estimate=scheduled_estimate,
                deadline_forced=False,
            )

        scheduled_start = effective_start
        scheduled_estimate = self._estimator.estimate(
            intent=intent,
            tier=tier,
            workload=workload,
            start=scheduled_start,
            end=scheduled_start + duration,
            as_of=now,
            history=history,
        )
        return self._build_plan(
            disposition=(
                ScheduleDisposition.WAIT_FOR_EARLIEST
                if waiting_for_earliest
                else ScheduleDisposition.START_NOW
            ),
            reason="deadline_forced" if deadline is not None else "already_off_peak",
            scheduled_start=scheduled_start,
            current_estimate=current_estimate,
            scheduled_estimate=scheduled_estimate,
            deadline_forced=deadline is not None,
        )

    @staticmethod
    def _build_plan(
        *,
        disposition: ScheduleDisposition,
        reason: str,
        scheduled_start: datetime,
        current_estimate: WorkloadEstimate,
        scheduled_estimate: WorkloadEstimate,
        deadline_forced: bool,
    ) -> PriceAwareSchedulePlan:
        return PriceAwareSchedulePlan(
            disposition=disposition,
            reason=reason,
            scheduled_start=scheduled_start,
            current_period=current_estimate.period,
            scheduled_period=scheduled_estimate.period,
            current_estimate=current_estimate,
            scheduled_estimate=scheduled_estimate,
            estimated_savings=max(
                current_estimate.authorized_ceiling
                - scheduled_estimate.authorized_ceiling,
                Decimal("0"),
            ),
            deadline_forced=deadline_forced,
        )


__all__ = [
    "PriceAwareSchedulePlan",
    "PriceAwareScheduler",
    "ScheduleDisposition",
]
