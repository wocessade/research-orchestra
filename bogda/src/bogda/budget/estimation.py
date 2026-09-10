"""Deterministic workload-based budget estimation.

``TokenWorkload`` token counts are the total baseline workload for all
``expected_calls``.  They are deliberately not per-call counts, so the
estimator prices that token partition once and uses the average call cost only
when reserving for retries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR, localcontext
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping, TypeVar

from bogda.budget.pricing import (
    MILLION,
    PricePeriod,
    PricingCatalogV1,
    TokenPrices,
    current_catalog,
    period_for_window,
)
from bogda.contracts import BudgetSource, ModelTier, RunBudgetEnvelope, TaskIntent


_EnumT = TypeVar("_EnumT", bound=StrEnum)
_DECIMAL_PRECISION = 50


def _require_decimal(value: object, name: str, *, non_negative: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise ValueError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    if non_negative and value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _require_count(value: object, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        if minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _require_enum(value: object, enum_type: type[_EnumT], name: str) -> _EnumT:
    if isinstance(value, bool):
        raise ValueError(f"{name} is invalid")
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is invalid") from exc


@dataclass(frozen=True, slots=True)
class TokenWorkload:
    """Total baseline token workload, not token counts per expected call."""

    expected_calls: int
    cache_hit_input_tokens: int
    cache_miss_input_tokens: int
    output_tokens: int
    allowed_retries: int = 0

    def __post_init__(self) -> None:
        _require_count(self.expected_calls, "expected_calls", minimum=1)
        _require_count(self.cache_hit_input_tokens, "cache_hit_input_tokens")
        _require_count(self.cache_miss_input_tokens, "cache_miss_input_tokens")
        _require_count(self.output_tokens, "output_tokens")
        _require_count(self.allowed_retries, "allowed_retries")
        if self.total_input_tokens + self.output_tokens == 0:
            raise ValueError("baseline workload must contain at least one token")

    @property
    def total_input_tokens(self) -> int:
        return self.cache_hit_input_tokens + self.cache_miss_input_tokens


@dataclass(frozen=True, slots=True)
class HistoricalUsageProfile:
    """Optional historical costs and verified cache-hit evidence."""

    p50_cost: Decimal | None = None
    p90_cost: Decimal | None = None
    verified_cache_hit_ratio: Decimal | None = None

    def __post_init__(self) -> None:
        for name in ("p50_cost", "p90_cost"):
            value = getattr(self, name)
            if value is not None:
                _require_decimal(value, name, non_negative=True)
        if self.p50_cost is not None and self.p90_cost is not None:
            if self.p90_cost < self.p50_cost:
                raise ValueError("p90_cost must be >= p50_cost")
        if self.verified_cache_hit_ratio is not None:
            ratio = _require_decimal(
                self.verified_cache_hit_ratio, "verified_cache_hit_ratio"
            )
            if not Decimal("0") <= ratio <= Decimal("1"):
                raise ValueError("verified_cache_hit_ratio must be between 0 and 1")


DEFAULT_CONTINGENCY_POLICY: Mapping[tuple[TaskIntent, ModelTier], Decimal] = MappingProxyType(
    {
        # Flash is the economical baseline; Pro gets more headroom for work
        # that commonly expands through exploration, decisions, or auditing.
        (TaskIntent.EXECUTE, ModelTier.FLASH): Decimal("1.20"),
        (TaskIntent.EXPLORE, ModelTier.FLASH): Decimal("1.30"),
        (TaskIntent.DECIDE, ModelTier.FLASH): Decimal("1.35"),
        (TaskIntent.AUDIT, ModelTier.FLASH): Decimal("1.30"),
        (TaskIntent.BRIEF, ModelTier.FLASH): Decimal("1.15"),
        (TaskIntent.EXECUTE, ModelTier.PRO): Decimal("1.30"),
        (TaskIntent.EXPLORE, ModelTier.PRO): Decimal("1.60"),
        (TaskIntent.DECIDE, ModelTier.PRO): Decimal("1.70"),
        (TaskIntent.AUDIT, ModelTier.PRO): Decimal("1.60"),
        (TaskIntent.BRIEF, ModelTier.PRO): Decimal("1.25"),
    }
)


def _validate_policy(
    policy: Mapping[tuple[TaskIntent, ModelTier], Decimal],
) -> Mapping[tuple[TaskIntent, ModelTier], Decimal]:
    if not isinstance(policy, Mapping):
        raise ValueError("contingency_policy must be a mapping")
    concrete_pairs = {
        (intent, tier)
        for intent in TaskIntent
        for tier in (ModelTier.FLASH, ModelTier.PRO)
    }
    actual_pairs: set[tuple[TaskIntent, ModelTier]] = set()
    normalized: dict[tuple[TaskIntent, ModelTier], Decimal] = {}
    for key, factor in policy.items():
        if (
            not isinstance(key, tuple)
            or len(key) != 2
            or not isinstance(key[0], TaskIntent)
            or not isinstance(key[1], ModelTier)
        ):
            raise ValueError("contingency_policy keys must be (TaskIntent, ModelTier)")
        intent, tier = key
        if tier is ModelTier.AUTO:
            raise ValueError("contingency_policy must not contain AUTO")
        actual_pairs.add((intent, tier))
        normalized[(intent, tier)] = _require_decimal(factor, "contingency factor")
        if normalized[(intent, tier)] < 1:
            raise ValueError("contingency factors must be at least 1")
    missing = concrete_pairs - actual_pairs
    extra = actual_pairs - concrete_pairs
    if missing:
        raise ValueError("contingency_policy is missing concrete intent/tier pairs")
    if extra:
        raise ValueError("contingency_policy contains unsupported intent/tier pairs")
    return MappingProxyType(normalized)


@dataclass(frozen=True, slots=True)
class WorkloadEstimate:
    """Explainable result used to build a Phase A budget envelope."""

    intent: TaskIntent
    tier: ModelTier
    workload: TokenWorkload
    effective_cache_hit_input_tokens: int
    effective_cache_miss_input_tokens: int
    effective_output_tokens: int
    expected_cost: Decimal
    retry_reserve: Decimal
    contingency_factor: Decimal
    historical_p90_cost: Decimal | None
    authorized_ceiling: Decimal
    period: PricePeriod
    pricing_version: str

    def __post_init__(self) -> None:
        _require_enum(self.intent, TaskIntent, "intent")
        tier = _require_enum(self.tier, ModelTier, "tier")
        if tier is ModelTier.AUTO:
            raise ValueError("AUTO tier must be resolved before estimation")
        if not isinstance(self.workload, TokenWorkload):
            raise ValueError("workload must be a TokenWorkload")
        _require_count(
            self.effective_cache_hit_input_tokens,
            "effective_cache_hit_input_tokens",
        )
        _require_count(
            self.effective_cache_miss_input_tokens,
            "effective_cache_miss_input_tokens",
        )
        _require_count(self.effective_output_tokens, "effective_output_tokens")
        if (
            self.effective_cache_hit_input_tokens
            + self.effective_cache_miss_input_tokens
            != self.workload.total_input_tokens
        ):
            raise ValueError("effective input partition must preserve total input")
        if self.effective_output_tokens != self.workload.output_tokens:
            raise ValueError("effective output partition must preserve output tokens")
        for name in (
            "expected_cost",
            "retry_reserve",
            "contingency_factor",
            "authorized_ceiling",
        ):
            value = _require_decimal(getattr(self, name), name, non_negative=True)
            if name == "contingency_factor" and value < 1:
                raise ValueError("contingency_factor must be at least 1")
        if self.authorized_ceiling < self.expected_cost:
            raise ValueError("authorized_ceiling must be >= expected_cost")
        if self.historical_p90_cost is not None:
            _require_decimal(
                self.historical_p90_cost, "historical_p90_cost", non_negative=True
            )
        if not isinstance(self.period, PricePeriod):
            raise ValueError("period must be a PricePeriod")
        if not isinstance(self.pricing_version, str) or not self.pricing_version:
            raise ValueError("pricing_version must be a non-empty string")

    @property
    def effective_token_partition(self) -> tuple[int, int, int]:
        return (
            self.effective_cache_hit_input_tokens,
            self.effective_cache_miss_input_tokens,
            self.effective_output_tokens,
        )

    @property
    def historical_p90(self) -> Decimal | None:
        return self.historical_p90_cost


def _catalog_price_row(
    catalog: PricingCatalogV1, tier: ModelTier, period: PricePeriod
) -> TokenPrices:
    rows = catalog.flash if tier is ModelTier.FLASH else catalog.pro
    return rows.off_peak if period is PricePeriod.OFF_PEAK else rows.peak


class WorkloadEstimator:
    """Estimate a fixed workload against one reviewed pricing catalog."""

    def __init__(
        self,
        *,
        catalog: PricingCatalogV1 | None = None,
        contingency_policy: Mapping[tuple[TaskIntent, ModelTier], Decimal]
        | None = None,
    ) -> None:
        if catalog is not None and not isinstance(catalog, PricingCatalogV1):
            raise ValueError("catalog must be a PricingCatalogV1")
        self._catalog = catalog
        self._contingency_policy = _validate_policy(
            DEFAULT_CONTINGENCY_POLICY
            if contingency_policy is None
            else contingency_policy
        )

    def estimate(
        self,
        *,
        intent: TaskIntent,
        tier: ModelTier,
        workload: TokenWorkload,
        start: datetime,
        end: datetime,
        as_of: datetime,
        history: HistoricalUsageProfile | None = None,
    ) -> WorkloadEstimate:
        intent = _require_enum(intent, TaskIntent, "intent")
        tier = _require_enum(tier, ModelTier, "tier")
        if tier is ModelTier.AUTO:
            raise ValueError("AUTO tier must be resolved before estimation")
        if not isinstance(workload, TokenWorkload):
            raise ValueError("workload must be a TokenWorkload")
        if history is not None and not isinstance(history, HistoricalUsageProfile):
            raise ValueError("history must be a HistoricalUsageProfile")
        for value, name in ((start, "start"), (end, "end"), (as_of, "as_of")):
            if not isinstance(value, datetime) or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if end <= start:
            raise ValueError("estimation window must be positive")
        catalog = self._catalog if self._catalog is not None else current_catalog(as_of)
        if start < catalog.effective_at:
            raise ValueError("pricing catalog is not effective for the full window")
        if end > catalog.review_by:
            raise ValueError("pricing catalog review deadline does not cover window")
        if as_of < catalog.effective_at:
            raise ValueError("pricing catalog is not effective at as_of")
        if as_of > catalog.review_by:
            raise ValueError("pricing catalog review deadline has passed")

        period = period_for_window(start, end)
        prices = _catalog_price_row(catalog, tier, period)

        if history is not None and history.verified_cache_hit_ratio is not None:
            with localcontext() as context:
                context.prec = _DECIMAL_PRECISION
                evidence_cap = int(
                    (
                        Decimal(workload.total_input_tokens)
                        * history.verified_cache_hit_ratio
                    ).to_integral_value(rounding=ROUND_FLOOR)
                )
            effective_hit = min(workload.cache_hit_input_tokens, evidence_cap)
        else:
            effective_hit = 0
        effective_miss = workload.total_input_tokens - effective_hit

        with localcontext() as context:
            context.prec = _DECIMAL_PRECISION
            expected_cost = (
                Decimal(effective_hit) * prices.cache_hit_input
                + Decimal(effective_miss) * prices.cache_miss_input
                + Decimal(workload.output_tokens) * prices.output
            ) / MILLION
            retry_reserve = (
                expected_cost / Decimal(workload.expected_calls)
            ) * Decimal(workload.allowed_retries)
            contingency_factor = self._contingency_policy[(intent, tier)]
            historical_p90 = history.p90_cost if history is not None else None
            authorized_ceiling = max(
                expected_cost * contingency_factor,
                historical_p90 if historical_p90 is not None else Decimal("0"),
            ) + retry_reserve

        return WorkloadEstimate(
            intent=intent,
            tier=tier,
            workload=workload,
            effective_cache_hit_input_tokens=effective_hit,
            effective_cache_miss_input_tokens=effective_miss,
            effective_output_tokens=workload.output_tokens,
            expected_cost=expected_cost,
            retry_reserve=retry_reserve,
            contingency_factor=contingency_factor,
            historical_p90_cost=historical_p90,
            authorized_ceiling=authorized_ceiling,
            period=period,
            pricing_version=catalog.version,
        )

    def to_budget_envelope(
        self,
        estimate: WorkloadEstimate,
        *,
        budget_source: BudgetSource,
        minimum_remaining: Decimal,
        fallback_tier: ModelTier | None,
    ) -> RunBudgetEnvelope:
        if not isinstance(estimate, WorkloadEstimate):
            raise ValueError("estimate must be a WorkloadEstimate")
        source = _require_enum(budget_source, BudgetSource, "budget_source")
        remaining = _require_decimal(
            minimum_remaining, "minimum_remaining", non_negative=True
        )
        if fallback_tier is not None:
            fallback_tier = _require_enum(fallback_tier, ModelTier, "fallback_tier")
            if fallback_tier is not ModelTier.FLASH:
                raise ValueError("fallback_tier must be flash or null")
        return RunBudgetEnvelope(
            expected_cost=estimate.expected_cost,
            authorized_ceiling=estimate.authorized_ceiling,
            minimum_remaining=remaining,
            requested_tier=estimate.tier,
            fallback_tier=fallback_tier,
            budget_source=source,
            pricing_version=estimate.pricing_version,
        )


__all__ = [
    "DEFAULT_CONTINGENCY_POLICY",
    "HistoricalUsageProfile",
    "TokenWorkload",
    "WorkloadEstimate",
    "WorkloadEstimator",
]
