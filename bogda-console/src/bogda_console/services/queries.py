from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Awaitable, Callable, TypeVar

from bogda_console.config import Settings
from bogda_console.contracts.models import (
    ApiEnvelope,
    ApiError,
    ApiErrorCode,
    Availability,
    CapabilitySnapshot,
    DeploymentSummary,
    InfrastructureView,
    OverviewSnapshot,
    Page,
    RunDetail,
    RunFilters,
    RunResultVersionSummary,
    RunResultView,
    RunSummary,
    ScientificSummary,
)
from bogda_console.contracts.ports import PowerStatusPort, PrefectQueryPort, RunResultPort
from bogda_console.services.errors import SourceUnavailable
from bogda_console.services.snapshots import LastGoodReader, SourceRead


T = TypeVar("T")


class QueryService:
    def __init__(
        self,
        *,
        settings: Settings,
        prefect: PrefectQueryPort,
        results: RunResultPort,
        power: PowerStatusPort,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.prefect = prefect
        self.results = results
        self.power = power
        self._now = now or (lambda: datetime.now(UTC))
        self._readers: dict[str, LastGoodReader[Any]] = {}

    async def capabilities(self) -> ApiEnvelope[CapabilitySnapshot]:
        enabled = self.settings.commands_enabled
        return ApiEnvelope(
            data=CapabilitySnapshot(
                profile=self.settings.profile,
                projectId="bogda-main",
                effectiveAutonomyMode="supervised",
                canSubmitRegisteredDeployment=enabled,
                canCancelRun=enabled,
                canPauseSchedule=enabled,
                canPauseWorkQueue=enabled,
                canReviewScientificResult=self.settings.review_enabled,
                canSetAutonomyMode=False,
            ),
            sources={},
            errors=[],
        )

    async def runs(
        self, filters: RunFilters, cursor: str | None, limit: int
    ) -> ApiEnvelope[Page[RunSummary]]:
        prefect = await self._read(
            "prefect:runs",
            "prefect",
            getattr(self.prefect, "source_mode", "real"),
            getattr(self.prefect, "observed_at", None),
            lambda: self.prefect.list_runs(
                filters.model_copy(update={"scientific_status": None}), cursor, limit
            ),
        )
        if prefect.data is None:
            raise self._unavailable("prefect", ApiErrorCode.PREFECT_UNAVAILABLE, prefect)

        result_read = await self._read(
            "runResult:projection:" + ",".join(run.run_id for run in prefect.data.items),
            "runResult",
            getattr(self.results, "source_mode", "real"),
            getattr(self.results, "observed_at", None),
            lambda: self._result_projection(prefect.data.items),
        )
        if filters.scientific_status and result_read.data is None:
            raise self._unavailable(
                "runResult", ApiErrorCode.RUN_RESULT_UNAVAILABLE, result_read
            )

        projected: list[RunSummary] = []
        for run in prefect.data.items:
            view = result_read.data.get(run.run_id) if result_read.data else None
            scientific = self._scientific(view) if view else None
            item = run.model_copy(update={"scientific": scientific})
            if filters.scientific_status and (
                scientific is None
                or scientific.scientific_status != filters.scientific_status
            ):
                continue
            projected.append(item)
        errors = self._errors(prefect, "prefect", ApiErrorCode.PREFECT_UNAVAILABLE)
        errors += self._errors(
            result_read, "runResult", ApiErrorCode.RUN_RESULT_UNAVAILABLE
        )
        return ApiEnvelope(
            data=Page(items=projected, nextCursor=prefect.data.next_cursor),
            sources={"prefect": prefect.meta, "runResult": result_read.meta},
            errors=errors,
        )

    async def run_detail(self, run_id: str) -> ApiEnvelope[RunDetail]:
        prefect = await self._read(
            f"prefect:run:{run_id}",
            "prefect",
            getattr(self.prefect, "source_mode", "real"),
            getattr(self.prefect, "observed_at", None),
            lambda: self.prefect.get_run(run_id),
        )
        if prefect.data is None:
            if isinstance(prefect.error, KeyError):
                raise prefect.error
            raise self._unavailable("prefect", ApiErrorCode.PREFECT_UNAVAILABLE, prefect)
        result_read = await self._read(
            f"runResult:latest:{run_id}",
            "runResult",
            getattr(self.results, "source_mode", "real"),
            getattr(self.results, "observed_at", None),
            lambda: self.results.get_latest(run_id),
        )
        detail = prefect.data
        if result_read.data:
            detail = detail.model_copy(
                update={
                    "run": detail.run.model_copy(
                        update={"scientific": self._scientific(result_read.data)}
                    )
                }
            )
        errors = self._errors(prefect, "prefect", ApiErrorCode.PREFECT_UNAVAILABLE)
        errors += self._errors(
            result_read, "runResult", ApiErrorCode.RUN_RESULT_UNAVAILABLE
        )
        return ApiEnvelope(
            data=detail,
            sources={"prefect": prefect.meta, "runResult": result_read.meta},
            errors=errors,
        )

    async def result(self, run_id: str) -> ApiEnvelope[RunResultView]:
        read = await self._read(
            f"runResult:latest:{run_id}",
            "runResult",
            getattr(self.results, "source_mode", "real"),
            getattr(self.results, "observed_at", None),
            lambda: self.results.get_latest(run_id),
        )
        if read.data is None:
            raise self._unavailable("runResult", ApiErrorCode.RUN_RESULT_UNAVAILABLE, read)
        return ApiEnvelope(data=read.data, sources={"runResult": read.meta}, errors=[])

    async def result_versions(
        self, run_id: str, cursor: str | None, limit: int
    ) -> ApiEnvelope[Page[RunResultVersionSummary]]:
        read = await self._read(
            f"runResult:versions:{run_id}:{cursor}:{limit}",
            "runResult",
            getattr(self.results, "source_mode", "real"),
            getattr(self.results, "observed_at", None),
            lambda: self.results.list_versions(run_id, cursor, limit),
        )
        if read.data is None:
            raise self._unavailable("runResult", ApiErrorCode.RUN_RESULT_UNAVAILABLE, read)
        return ApiEnvelope(data=read.data, sources={"runResult": read.meta}, errors=[])

    async def deployments(
        self, cursor: str | None, limit: int
    ) -> ApiEnvelope[Page[DeploymentSummary]]:
        read = await self._read(
            f"prefect:deployments:{cursor}:{limit}",
            "prefect",
            getattr(self.prefect, "source_mode", "real"),
            getattr(self.prefect, "observed_at", None),
            lambda: self.prefect.list_registered_deployments(cursor, limit),
        )
        if read.data is None:
            raise self._unavailable("prefect", ApiErrorCode.PREFECT_UNAVAILABLE, read)
        return ApiEnvelope(
            data=read.data,
            sources={"prefect": read.meta},
            errors=self._errors(read, "prefect", ApiErrorCode.PREFECT_UNAVAILABLE),
        )

    async def infrastructure(self) -> ApiEnvelope[InfrastructureView]:
        prefect = await self._read(
            "prefect:infrastructure",
            "prefect",
            getattr(self.prefect, "source_mode", "real"),
            getattr(self.prefect, "observed_at", None),
            self.prefect.list_work_pools,
        )
        power = await self._read(
            "power:dorm",
            "power",
            getattr(self.power, "source_mode", "mock"),
            getattr(self.power, "observed_at", None),
            self.power.get_dorm_status,
        )
        if prefect.data is None and power.data is None:
            raise self._unavailable("prefect", ApiErrorCode.PREFECT_UNAVAILABLE, prefect)
        errors = self._errors(prefect, "prefect", ApiErrorCode.PREFECT_UNAVAILABLE)
        errors += self._errors(power, "power", ApiErrorCode.POWER_UNAVAILABLE)
        return ApiEnvelope(
            data=InfrastructureView(pools=prefect.data, dormPower=power.data),
            sources={"prefect": prefect.meta, "power": power.meta},
            errors=errors,
        )

    async def overview(self) -> ApiEnvelope[OverviewSnapshot]:
        try:
            runs = await self.runs(RunFilters(), None, 12)
        except SourceUnavailable:
            runs = None
        try:
            infrastructure = await self.infrastructure()
        except SourceUnavailable:
            infrastructure = None
        if runs is None and infrastructure is None:
            raise SourceUnavailable(
                ApiErrorCode.PREFECT_UNAVAILABLE,
                "No overview source is available",
                source="prefect",
                retryable=True,
            )
        items = runs.data.items if runs and runs.data else []
        execution_counts: dict[str, int] = {}
        science_counts: dict[str, int] = {}
        attention: list[RunSummary] = []
        for run in items:
            execution_counts[run.state.type] = execution_counts.get(run.state.type, 0) + 1
            if run.scientific and run.scientific.scientific_status:
                key = str(run.scientific.scientific_status)
                science_counts[key] = science_counts.get(key, 0) + 1
            if run.state.terminal and (
                run.scientific is None
                or run.scientific.availability != Availability.AVAILABLE
                or run.scientific.scientific_status == "unreviewed"
            ):
                attention.append(run)
        pools = infrastructure.data.pools if infrastructure and infrastructure.data else None
        pool_map = {pool.name: pool for pool in pools or []}
        data = OverviewSnapshot(
            execution={"countsByPrefectType": execution_counts, "recentRuns": items}
            if runs
            else None,
            science={
                "countsByScientificStatus": science_counts,
                "attentionRuns": attention,
            }
            if runs
            else None,
            infrastructure={
                "piService": pool_map.get("pi-service"),
                "dormX86": pool_map.get("dorm-x86"),
            }
            if infrastructure
            else None,
            power=(infrastructure.data.dorm_power if infrastructure and infrastructure.data else None),
        )
        sources = {}
        errors = []
        for envelope in (runs, infrastructure):
            if envelope:
                sources.update(envelope.sources)
                errors.extend(envelope.errors)
        return ApiEnvelope(data=data, sources=sources, errors=errors)

    async def _result_projection(
        self, runs: list[RunSummary]
    ) -> dict[str, RunResultView]:
        projected: dict[str, RunResultView] = {}
        for run in runs:
            projected[run.run_id] = await self.results.get_latest(run.run_id)
        return projected

    async def _read(
        self,
        key: str,
        source: str,
        source_mode: str,
        observed_at: datetime | None,
        fetch: Callable[[], Awaitable[T]],
    ) -> SourceRead[T]:
        reader = self._readers.setdefault(
            key,
            LastGoodReader(
                source=source,
                source_mode=source_mode,
                stale_after_seconds=60,
                now=self._now,
            ),
        )

        async def observed_fetch() -> tuple[T, datetime | None]:
            return await fetch(), observed_at

        return await reader.read(observed_fetch)

    @staticmethod
    def _scientific(view: RunResultView) -> ScientificSummary:
        return ScientificSummary(
            availability=view.availability,
            artifactId=view.artifact_id,
            artifactCreatedAt=view.artifact_created_at,
            scientificStatus=(view.result.scientific_status if view.result else None),
            reviewSummary=(view.result.review_summary if view.result else None),
            validationIssues=view.validation_issues,
        )

    @staticmethod
    def _errors(
        read: SourceRead[Any], source: str, code: ApiErrorCode
    ) -> list[ApiError]:
        if read.error is None:
            return []
        return [
            ApiError(
                code=code,
                message=str(read.error),
                source=source,
                retryable=True,
            )
        ]

    @staticmethod
    def _unavailable(
        source: str, code: ApiErrorCode, read: SourceRead[Any]
    ) -> SourceUnavailable:
        return SourceUnavailable(
            code,
            str(read.error or f"{source} unavailable"),
            source=source,
            retryable=True,
            status_code=503,
        )
