from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Any
from uuid import UUID

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import ArtifactCreate
from prefect.client.schemas.filters import (
    ArtifactFilter,
    ArtifactFilterFlowRunId,
    ArtifactFilterKey,
    ArtifactFilterType,
    FlowRunFilter,
    FlowRunFilterDeploymentId,
    FlowRunFilterState,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import StateType
from prefect.client.schemas.sorting import ArtifactSort, DeploymentSort, FlowRunSort
from prefect.states import Cancelling
from pydantic import ValidationError

from bogda_console.adapters.mock_run_results import ReviewConflict
from bogda_console.contracts.models import (
    Availability,
    DeploymentSummary,
    Page,
    PoolSnapshot,
    PrefectStateSnapshot,
    ProjectContext,
    QueueSnapshot,
    ResearchCheckpointView,
    RunDetail,
    RunFilters,
    RunResultVersionSummary,
    RunResultView,
    RunSummary,
    ScheduleSummary,
    ScientificStatus,
    ValidRunResult,
    WorkerSnapshot,
    checkpoint_impact,
    command_version,
)


ClientFactory = Callable[[], AbstractAsyncContextManager[Any]]
RUN_RESULT_TYPE = "bogda.run-result"
DECISION_TYPE = "bogda.research-decision"
DECISION_KINDS = ("plan_approval", "experiment_approval", "scientific_review")


def _value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _decision_key(run_id: str, kind: str) -> str:
    return f"bogda-decision-{kind.replace('_', '-')}-{UUID(run_id)}"


class PrefectApiAdapter:
    """Thin Prefect 3.8.3 client mapping; it owns no scheduler or durable state."""

    source_mode = "real"

    def __init__(
        self,
        *,
        api_url: str,
        auth_string: str | None = None,
        api_key: str | None = None,
        client_factory: ClientFactory | None = None,
        allowed_deployment_ids: frozenset[str] = frozenset(),
    ) -> None:
        self.api_url = api_url
        self.auth_string = auth_string
        self.api_key = api_key
        self.allowed_deployment_ids = allowed_deployment_ids
        self._client_factory = client_factory or self._default_client

    @property
    def observed_at(self) -> None:
        return None

    def _default_client(self) -> PrefectClient:
        if self.auth_string is not None:
            return PrefectClient(self.api_url, auth_string=self.auth_string)
        return PrefectClient(self.api_url, api_key=self.api_key)

    async def health(self) -> bool:
        async with self._client_factory() as client:
            await client.hello()
        return True

    async def list_runs(self, filters: RunFilters, cursor: str | None, limit: int) -> Page[RunSummary]:
        offset = int(cursor or 0)
        flow_filter = self._flow_run_filter(filters)
        async with self._client_factory() as client:
            raw_runs = await client.read_flow_runs(
                flow_run_filter=flow_filter,
                sort=FlowRunSort.ID_DESC,
                limit=None if filters.project_id else limit + 1,
                offset=0 if filters.project_id else offset,
            )
            if filters.project_id:
                raw_runs = [run for run in raw_runs if run.parameters.get("project_id") == filters.project_id]
                raw_runs = raw_runs[offset : offset + limit + 1]
            page_raw = raw_runs[:limit]
            items = [await self._run_summary(client, run) for run in page_raw]
        return Page(items=items, nextCursor=str(offset + limit) if len(raw_runs) > limit else None)

    async def get_run(self, run_id: str) -> RunDetail:
        async with self._client_factory() as client:
            raw = await client.read_flow_run(UUID(run_id))
            run = await self._run_summary(client, raw)
            checkpoint = await self._checkpoint(client, run_id)
        parameters = dict(raw.parameters or {})
        return RunDetail(
            run=run,
            parameters=parameters,
            tags=list(raw.tags or []),
            projectContext=self._run_context(parameters),
            checkpoint=checkpoint,
        )

    async def list_registered_deployments(self, cursor: str | None, limit: int) -> Page[DeploymentSummary]:
        offset = int(cursor or 0)
        async with self._client_factory() as client:
            raw = await client.read_deployments(limit=limit + 1, offset=offset, sort=DeploymentSort.UPDATED_DESC)
            items = [await self._deployment(client, item) for item in raw[:limit]]
        return Page(items=items, nextCursor=str(offset + limit) if len(raw) > limit else None)

    async def get_deployment(self, deployment_id: str) -> DeploymentSummary:
        async with self._client_factory() as client:
            raw = await client.read_deployment(UUID(deployment_id))
            return await self._deployment(client, raw)

    async def list_work_pools(self) -> list[PoolSnapshot]:
        async with self._client_factory() as client:
            pools = await client.read_work_pools()
            return [await self._pool(client, pool) for pool in pools]

    async def list_work_queues(self, work_pool_name: str) -> list[QueueSnapshot]:
        async with self._client_factory() as client:
            queues = await client.read_work_queues(work_pool_name=work_pool_name)
            return [self._queue(queue) for queue in queues]

    async def list_workers(self, work_pool_name: str) -> list[WorkerSnapshot]:
        async with self._client_factory() as client:
            workers = await client.read_workers_for_work_pool(work_pool_name)
            return [self._worker(worker) for worker in workers]

    async def get_work_pool_concurrency(self, work_pool_name: str) -> PoolSnapshot:
        async with self._client_factory() as client:
            pool = await client.read_work_pool(work_pool_name)
            return await self._pool(client, pool)

    async def get_latest(self, run_id: str) -> RunResultView:
        async with self._client_factory() as client:
            artifacts = await self._read_artifacts(client, run_id, 0, 1)
        return self._artifact_view(artifacts[0]) if artifacts else RunResultView(availability=Availability.MISSING)

    async def list_versions(self, run_id: str, cursor: str | None, limit: int) -> Page[RunResultVersionSummary]:
        offset = int(cursor or 0)
        async with self._client_factory() as client:
            artifacts = await self._read_artifacts(client, run_id, offset, limit + 1)
        items = [self._version(artifact) for artifact in artifacts[:limit]]
        return Page(items=items, nextCursor=str(offset + limit) if len(artifacts) > limit else None)

    async def append_review(
        self,
        run_id: str,
        base_artifact_id: str,
        scientific_status: ScientificStatus | str,
        review_summary: str | None,
    ) -> RunResultView:
        async with self._client_factory() as client:
            artifacts = await self._read_artifacts(client, run_id, 0, 1)
            current = self._artifact_view(artifacts[0]) if artifacts else RunResultView(availability=Availability.MISSING)
            if current.artifact_id != base_artifact_id:
                raise ReviewConflict(current)
            if current.result is None:
                raise ValueError("latest RunResult is not valid")
            payload = current.result.model_dump(mode="json")
            payload["scientific_status"] = ScientificStatus(scientific_status).value
            payload["review_summary"] = review_summary
            created = await client.create_artifact(
                ArtifactCreate(
                    key=f"bogda-run-{run_id}",
                    type=RUN_RESULT_TYPE,
                    data=payload,
                    flow_run_id=UUID(run_id),
                )
            )
        return self._artifact_view(created)

    async def submit_registered_deployment(self, deployment_id: str, parameters: dict[str, Any], idempotency_key: str) -> RunSummary:
        async with self._client_factory() as client:
            raw = await client.create_flow_run_from_deployment(UUID(deployment_id), parameters=parameters, idempotency_key=idempotency_key)
            return await self._run_summary(client, raw)

    async def cancel_run(self, run_id: str) -> RunSummary:
        async with self._client_factory() as client:
            await client.set_flow_run_state(UUID(run_id), Cancelling(message="Cancellation requested from Bogda Console"))
            raw = await client.read_flow_run(UUID(run_id))
            return await self._run_summary(client, raw)

    async def resume_run(self, run_id: str, run_input: dict[str, Any]) -> None:
        async with self._client_factory() as client:
            await client.resume_flow_run(UUID(run_id), run_input=run_input)

    async def pause_schedule(self, deployment_id: str, schedule_id: str) -> DeploymentSummary:
        return await self._set_schedule(deployment_id, schedule_id, False)

    async def resume_schedule(self, deployment_id: str, schedule_id: str) -> DeploymentSummary:
        return await self._set_schedule(deployment_id, schedule_id, True)

    async def pause_work_queue(self, queue_id: str) -> QueueSnapshot:
        return await self._set_queue(queue_id, True)

    async def resume_work_queue(self, queue_id: str) -> QueueSnapshot:
        return await self._set_queue(queue_id, False)

    async def _set_schedule(self, deployment_id: str, schedule_id: str, active: bool) -> DeploymentSummary:
        async with self._client_factory() as client:
            await client.update_deployment_schedule(UUID(deployment_id), UUID(schedule_id), active=active)
            raw = await client.read_deployment(UUID(deployment_id))
            return await self._deployment(client, raw)

    async def _set_queue(self, queue_id: str, paused: bool) -> QueueSnapshot:
        async with self._client_factory() as client:
            await client.update_work_queue(UUID(queue_id), is_paused=paused)
            raw = await client.read_work_queue(UUID(queue_id))
            return self._queue(raw)

    async def _run_summary(self, client: Any, raw: Any) -> RunSummary:
        deployment = await client.read_deployment(raw.deployment_id) if raw.deployment_id else None
        state = raw.state
        state_type = _value(state.type if state is not None else raw.state_type)
        state_name = str(state.name if state is not None else raw.state_name)
        state_time = state.timestamp if state is not None else raw.updated
        snapshot = PrefectStateSnapshot(
            type=state_type,
            name=state_name,
            timestamp=state_time,
            terminal=state_type in {"COMPLETED", "FAILED", "CRASHED", "CANCELLED"},
            message=(state.message if state is not None else None),
        )
        parameters = dict(raw.parameters or {})
        return RunSummary(
            runId=str(raw.id),
            name=raw.name,
            deploymentId=str(raw.deployment_id) if raw.deployment_id else None,
            deploymentName=deployment.name if deployment else None,
            projectId=parameters.get("project_id"),
            workPoolName=raw.work_pool_name,
            workQueueName=raw.work_queue_name,
            state=snapshot,
            scheduledAt=raw.expected_start_time,
            startedAt=raw.start_time,
            endedAt=raw.end_time,
            commandVersion=command_version({"runId": str(raw.id), "type": state_type, "name": state_name, "timestamp": state_time}),
        )

    async def _deployment(self, client: Any, raw: Any) -> DeploymentSummary:
        flow = await client.read_flow(raw.flow_id)
        schedules = await client.read_deployment_schedules(raw.id)
        parameters = dict(raw.parameters or {})
        return DeploymentSummary(
            deploymentId=str(raw.id),
            name=raw.name,
            flowName=flow.name,
            projectContext=self._deployment_context(parameters),
            workPoolName=raw.work_pool_name,
            workQueueName=raw.work_queue_name,
            parameterSchema=dict(raw.parameter_openapi_schema or {}),
            allowlisted=str(raw.id) in self.allowed_deployment_ids,
            schedules=[self._schedule(schedule) for schedule in schedules],
        )

    async def _pool(self, client: Any, raw: Any) -> PoolSnapshot:
        queues = await client.read_work_queues(work_pool_name=raw.name)
        workers = await client.read_workers_for_work_pool(raw.name)
        return PoolSnapshot(
            name=raw.name,
            status=_value(raw.status),
            isPaused=raw.is_paused,
            concurrencyLimit=raw.concurrency_limit,
            activeSlots=raw.active_slots or 0,
            queues=[self._queue(queue) for queue in queues],
            workers=[self._worker(worker) for worker in workers],
        )

    @staticmethod
    def _queue(raw: Any) -> QueueSnapshot:
        version = command_version({"queueId": str(raw.id), "isPaused": raw.is_paused, "updatedAt": raw.updated})
        return QueueSnapshot(queueId=str(raw.id), name=raw.name, status=_value(raw.status), isPaused=raw.is_paused, concurrencyLimit=raw.concurrency_limit, commandVersion=version)

    @staticmethod
    def _worker(raw: Any) -> WorkerSnapshot:
        return WorkerSnapshot(workerId=str(raw.id), name=raw.name, status=_value(raw.status), lastHeartbeatTime=raw.last_heartbeat_time)

    @staticmethod
    def _schedule(raw: Any) -> ScheduleSummary:
        label = raw.slug or str(raw.schedule)
        version = command_version({"scheduleId": str(raw.id), "active": raw.active, "updatedAt": raw.updated})
        return ScheduleSummary(scheduleId=str(raw.id), label=label, active=raw.active, updatedAt=raw.updated, commandVersion=version)

    @staticmethod
    def _run_context(parameters: dict[str, Any]) -> ProjectContext | None:
        project_id = parameters.get("project_id")
        mode = parameters.get("autonomy_mode")
        if not project_id:
            return None
        return ProjectContext(projectId=project_id, effectiveAutonomyMode=mode if mode in {"manual", "supervised", "autonomous"} else None, modeSource="frozen-run-request" if mode in {"manual", "supervised", "autonomous"} else "unavailable", writable=False)

    @staticmethod
    def _deployment_context(parameters: dict[str, Any]) -> ProjectContext | None:
        project_id = parameters.get("project_id")
        mode = parameters.get("autonomy_mode")
        if not project_id:
            return None
        return ProjectContext(projectId=project_id, effectiveAutonomyMode=mode if mode in {"manual", "supervised", "autonomous"} else None, modeSource="deployment-default" if mode in {"manual", "supervised", "autonomous"} else "unavailable", writable=False)

    @staticmethod
    def _flow_run_filter(filters: RunFilters) -> FlowRunFilter | None:
        state = FlowRunFilterState(type=FlowRunFilterStateType(any_=[StateType(filters.execution_type)])) if filters.execution_type else None
        deployment = FlowRunFilterDeploymentId(any_=[UUID(filters.deployment_id)]) if filters.deployment_id else None
        return FlowRunFilter(state=state, deployment_id=deployment) if state or deployment else None

    @staticmethod
    async def _read_artifacts(client: Any, run_id: str, offset: int, limit: int) -> list[Any]:
        artifact_filter = ArtifactFilter(
            key=ArtifactFilterKey(any_=[f"bogda-run-{run_id}"]),
            type=ArtifactFilterType(any_=[RUN_RESULT_TYPE]),
            flow_run_id=ArtifactFilterFlowRunId(any_=[UUID(run_id)]),
        )
        return await client.read_artifacts(artifact_filter=artifact_filter, sort=ArtifactSort.CREATED_DESC, offset=offset, limit=limit)

    @staticmethod
    async def _checkpoint(client: Any, run_id: str) -> ResearchCheckpointView | None:
        for kind in DECISION_KINDS:
            artifacts = await client.read_artifacts(
                artifact_filter=ArtifactFilter(
                    key=ArtifactFilterKey(any_=[_decision_key(run_id, kind)]),
                    type=ArtifactFilterType(any_=[DECISION_TYPE]),
                ),
                sort=ArtifactSort.CREATED_DESC,
                limit=1,
            )
            if not artifacts:
                continue
            data = artifacts[0].data
            if isinstance(data, str):
                data = json.loads(data)
            if not isinstance(data, dict) or data.get("kind") != kind:
                continue
            if data.get("verdict"):
                continue
            version = data.get("command_version")
            if not version:
                continue
            return ResearchCheckpointView(
                kind=kind,
                stage=data.get("stage", "done"),
                verdict=None,
                rationale=data.get("rationale"),
                decidedBy=data.get("decided_by"),
                commandVersion=version,
                impact=checkpoint_impact(kind),
            )
        return None

    @staticmethod
    def _artifact_view(artifact: Any) -> RunResultView:
        try:
            result = ValidRunResult.model_validate(artifact.data)
        except ValidationError as error:
            issues = [f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in error.errors()]
            return RunResultView(availability=Availability.INVALID, artifactId=str(artifact.id), artifactCreatedAt=artifact.created, validationIssues=issues)
        return RunResultView(availability=Availability.AVAILABLE, artifactId=str(artifact.id), artifactCreatedAt=artifact.created, result=result, validationIssues=[])

    @classmethod
    def _version(cls, artifact: Any) -> RunResultVersionSummary:
        view = cls._artifact_view(artifact)
        return RunResultVersionSummary(
            artifactId=str(artifact.id),
            createdAt=artifact.created,
            availability="available" if view.result else "invalid",
            scientificStatus=view.result.scientific_status if view.result else None,
            reviewSummary=view.result.review_summary if view.result else None,
        )
