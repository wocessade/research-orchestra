from __future__ import annotations

from datetime import UTC, datetime

import pytest

from bogda_console.services.snapshots import LastGoodReader


@pytest.mark.asyncio
async def test_failed_refresh_returns_stale_last_good_without_changing_observed_at() -> None:
    reader = LastGoodReader(
        source="prefect",
        source_mode="mock",
        stale_after_seconds=30,
        now=lambda: datetime(2026, 8, 24, 2, tzinfo=UTC),
    )

    async def success():
        return {"runs": ["run-1"]}, datetime(2026, 8, 24, 1, 59, 50, tzinfo=UTC)

    async def failure():
        raise ConnectionError("offline")

    first = await reader.read(success)
    second = await reader.read(failure)
    assert first.meta.freshness == "fresh"
    assert second.data == {"runs": ["run-1"]}
    assert second.meta.freshness == "stale"
    assert second.meta.observed_at == first.meta.observed_at
    assert second.error is not None


@pytest.mark.asyncio
async def test_failure_without_snapshot_is_unavailable() -> None:
    reader = LastGoodReader(
        source="power",
        source_mode="mock",
        stale_after_seconds=30,
        now=lambda: datetime(2026, 8, 24, 2, tzinfo=UTC),
    )

    async def failure():
        raise ConnectionError("offline")

    result = await reader.read(failure)
    assert result.data is None
    assert result.meta.freshness == "unavailable"
    assert result.meta.observed_at is None
    assert result.meta.last_successful_at is None


@pytest.mark.asyncio
async def test_old_successful_observation_is_stale() -> None:
    reader = LastGoodReader(
        source="power",
        source_mode="mock",
        stale_after_seconds=30,
        now=lambda: datetime(2026, 8, 24, 2, tzinfo=UTC),
    )

    async def old_success():
        return "maintenance", datetime(2026, 8, 24, 1, 50, tzinfo=UTC)

    result = await reader.read(old_success)
    assert result.data == "maintenance"
    assert result.meta.freshness == "stale"
