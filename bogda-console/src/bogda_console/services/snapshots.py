from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Awaitable, Callable, Generic, TypeVar

from bogda_console.contracts.models import Freshness, SourceMeta, SourceMode


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class SourceRead(Generic[T]):
    data: T | None
    meta: SourceMeta
    error: Exception | None = None


class LastGoodReader(Generic[T]):
    def __init__(
        self,
        *,
        source: str,
        source_mode: SourceMode | str,
        stale_after_seconds: int,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.source = source
        self.source_mode = SourceMode(source_mode)
        self.stale_after_seconds = stale_after_seconds
        self._now = now or (lambda: datetime.now(UTC))
        self._last_data: T | None = None
        self._last_observed_at: datetime | None = None
        self._last_successful_at: datetime | None = None

    def clear(self) -> None:
        self._last_data = None
        self._last_observed_at = None
        self._last_successful_at = None

    async def read(
        self, fetch: Callable[[], Awaitable[tuple[T, datetime | None]]]
    ) -> SourceRead[T]:
        received_at = self._now()
        try:
            data, observed_at = await fetch()
            received_at = self._now()
            self._last_data = data
            self._last_observed_at = observed_at
            self._last_successful_at = received_at
            freshness = self._freshness(observed_at, received_at)
            return SourceRead(data, self._meta(freshness, observed_at, received_at))
        except Exception as error:
            received_at = self._now()
            if self._last_data is None:
                return SourceRead(
                    None,
                    self._meta(Freshness.UNAVAILABLE, None, received_at),
                    error,
                )
            return SourceRead(
                self._last_data,
                self._meta(Freshness.STALE, self._last_observed_at, received_at),
                error,
            )

    def prime(self, data: T, observed_at: datetime | None, last_successful_at: datetime) -> None:
        self._last_data = data
        self._last_observed_at = observed_at
        self._last_successful_at = last_successful_at

    def _freshness(self, observed_at: datetime | None, received_at: datetime) -> Freshness:
        if observed_at is None:
            return Freshness.FRESH
        age = (received_at - observed_at).total_seconds()
        return Freshness.FRESH if age <= self.stale_after_seconds else Freshness.STALE

    def _meta(
        self, freshness: Freshness, observed_at: datetime | None, received_at: datetime
    ) -> SourceMeta:
        return SourceMeta(
            source=self.source,
            sourceMode=self.source_mode,
            observedAt=observed_at,
            receivedAt=received_at,
            lastSuccessfulAt=self._last_successful_at,
            staleAfterSeconds=self.stale_after_seconds,
            freshness=freshness,
        )
