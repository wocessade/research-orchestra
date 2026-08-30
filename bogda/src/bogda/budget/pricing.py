from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self
from zoneinfo import ZoneInfo

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from bogda.contracts import ModelTier


BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")
MILLION = Decimal("1000000")


class PricePeriod(StrEnum):
    OFF_PEAK = "off_peak"
    PEAK = "peak"


class TokenPrices(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cache_hit_input: Decimal = Field(gt=0)
    cache_miss_input: Decimal = Field(gt=0)
    output: Decimal = Field(gt=0)

    @field_validator("cache_hit_input", "cache_miss_input", "output", mode="before")
    @classmethod
    def reject_float_money(cls, value: object) -> object:
        if isinstance(value, float):
            raise ValueError("money values must not be floats")
        return value

    @field_serializer("cache_hit_input", "cache_miss_input", "output")
    def serialize_money(self, value: Decimal) -> str:
        return format(value, "f")


class _PriceRows(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    off_peak: TokenPrices
    peak: TokenPrices


class PricingCatalogV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    version: str = Field(min_length=1)
    currency: Literal["CNY"] = "CNY"
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    effective_at: datetime
    review_by: datetime
    source: str = Field(min_length=1)
    flash: _PriceRows
    pro: _PriceRows

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_schema_version_type(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @field_validator("effective_at", "review_by")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("catalog timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def validate_review_window(self) -> Self:
        if self.review_by <= self.effective_at:
            raise ValueError("review_by must be after effective_at")
        return self


def _require_aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def period_at(instant: datetime) -> PricePeriod:
    """Return the DeepSeek period at an instant evaluated in Beijing time."""

    local = _require_aware(instant, "instant").astimezone(BEIJING_TIMEZONE)
    if local.weekday() >= 5:
        return PricePeriod.OFF_PEAK
    if time(9) <= local.time() < time(12):
        return PricePeriod.PEAK
    if time(14) <= local.time() < time(18):
        return PricePeriod.PEAK
    return PricePeriod.OFF_PEAK


def _peak_windows(day: date) -> tuple[tuple[datetime, datetime], ...]:
    if day.weekday() >= 5:
        return ()
    return (
        (
            datetime.combine(day, time(9), tzinfo=BEIJING_TIMEZONE),
            datetime.combine(day, time(12), tzinfo=BEIJING_TIMEZONE),
        ),
        (
            datetime.combine(day, time(14), tzinfo=BEIJING_TIMEZONE),
            datetime.combine(day, time(18), tzinfo=BEIJING_TIMEZONE),
        ),
    )


def period_for_window(start: datetime, end: datetime) -> PricePeriod:
    """Price a positive interval at peak if any portion overlaps a peak window."""

    start = _require_aware(start, "start")
    end = _require_aware(end, "end")
    if end <= start:
        raise ValueError("pricing window must be positive")

    local_start = start.astimezone(BEIJING_TIMEZONE)
    local_end = end.astimezone(BEIJING_TIMEZONE)
    current = local_start.date()
    while current <= local_end.date():
        for peak_start, peak_end in _peak_windows(current):
            if max(local_start, peak_start) < min(local_end, peak_end):
                return PricePeriod.PEAK
        current += timedelta(days=1)
    return PricePeriod.OFF_PEAK


def _coerce_tier(tier: ModelTier) -> ModelTier:
    try:
        tier = ModelTier(tier)
    except (TypeError, ValueError) as exc:
        raise ValueError("unknown model tier") from exc
    if tier is ModelTier.AUTO:
        raise ValueError("AUTO is invalid for a price lookup")
    return tier


def _coerce_period(period: PricePeriod) -> PricePeriod:
    try:
        return PricePeriod(period)
    except (TypeError, ValueError) as exc:
        raise ValueError("unknown price period") from exc


def _validate_catalog_as_of(as_of: datetime, catalog: PricingCatalogV1) -> None:
    as_of = _require_aware(as_of, "as_of")
    if as_of < catalog.effective_at:
        raise ValueError("pricing catalog is not effective yet")
    if as_of > catalog.review_by:
        raise ValueError("pricing catalog review deadline has passed")


def prices_for(
    tier: ModelTier, period: PricePeriod, *, as_of: datetime, catalog: PricingCatalogV1 | None = None
) -> TokenPrices:
    """Return the reviewed price row for a concrete model tier and period."""

    resolved = catalog or DEEPSEEK_CN_2026_08_28
    if not isinstance(resolved, PricingCatalogV1):
        raise ValueError("catalog must be a PricingCatalogV1")
    tier = _coerce_tier(tier)
    period = _coerce_period(period)
    _validate_catalog_as_of(as_of, resolved)
    rows = resolved.flash if tier is ModelTier.FLASH else resolved.pro
    return rows.off_peak if period is PricePeriod.OFF_PEAK else rows.peak


def _validate_token_count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be a non-negative integer")
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def estimate_token_cost(
    tier: ModelTier,
    period: PricePeriod,
    *,
    cache_hit_input_tokens: int = 0,
    cache_miss_input_tokens: int = 0,
    output_tokens: int = 0,
    as_of: datetime,
    catalog: PricingCatalogV1 | None = None,
) -> Decimal:
    """Estimate CNY from token counts and supplied prices per million tokens."""

    hit_tokens = _validate_token_count(cache_hit_input_tokens, "cache_hit_input_tokens")
    miss_tokens = _validate_token_count(
        cache_miss_input_tokens, "cache_miss_input_tokens"
    )
    output_tokens = _validate_token_count(output_tokens, "output_tokens")
    prices = prices_for(tier, period, as_of=as_of, catalog=catalog)
    return (
        Decimal(hit_tokens) * prices.cache_hit_input
        + Decimal(miss_tokens) * prices.cache_miss_input
        + Decimal(output_tokens) * prices.output
    ) / MILLION


DEEPSEEK_CN_2026_08_28 = PricingCatalogV1(
    version="deepseek-cn-2026-08-28",
    effective_at=datetime(2026, 8, 28, 0, 0, tzinfo=BEIJING_TIMEZONE),
    review_by=datetime(2026, 9, 28, 0, 0, tzinfo=BEIJING_TIMEZONE),
    source="Owner-supplied DeepSeek V4 CN pricing table dated 2026-08-28",
    flash=_PriceRows(
        off_peak=TokenPrices(
            cache_hit_input=Decimal("0.05"),
            cache_miss_input=Decimal("1.5"),
            output=Decimal("4.5"),
        ),
        peak=TokenPrices(
            cache_hit_input=Decimal("0.10"),
            cache_miss_input=Decimal("3.0"),
            output=Decimal("9.0"),
        ),
    ),
    pro=_PriceRows(
        off_peak=TokenPrices(
            cache_hit_input=Decimal("0.15"),
            cache_miss_input=Decimal("4.5"),
            output=Decimal("13.5"),
        ),
        peak=TokenPrices(
            cache_hit_input=Decimal("0.30"),
            cache_miss_input=Decimal("9.0"),
            output=Decimal("27.0"),
        ),
    ),
)


__all__ = [
    "DEEPSEEK_CN_2026_08_28",
    "PricePeriod",
    "PricingCatalogV1",
    "TokenPrices",
    "estimate_token_cost",
    "period_at",
    "period_for_window",
    "prices_for",
]
