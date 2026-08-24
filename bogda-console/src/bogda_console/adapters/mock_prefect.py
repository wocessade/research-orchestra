from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from bogda_console.contracts.models import (
    DeploymentSummary,
    Page,
    PoolSnapshot,
    PrefectStateSnapshot,
    ProjectContext,
    QueueSnapshot,
    RunDetail,
    RunFilters,
    RunSummary,
    ScheduleSummary,
    WorkerSnapshot,
    command_version,
)


class MockPrefectAdapter:
    source_mode = "mock"

    def __init__(self, fixture: dict[str, Any]) -> None:
        self._fixture = copy.deepcopy(fixture)
        self._prefect = self._fixture["prefect"]
        self._clock = datetime.fromisoformat(self._fixture["clock"].replace("Z", "+00:00"))
        self._submit_counter = 0
        self.cancel_calls: list[str] = []
        self.submit_calls: list[str] = []

    @property
    def observed_at(self) -> datetime:
        return self._date(self._prefect["source"]["observedAt"])

    async def health(self) -> bool:
        if not self._prefect["source"]["available"]:
            raise ConnectionError("mock Prefect unavailable")
        return True

    def _require_available(self) -> None:
        if not self._prefect["source"]["available"]:
            raise ConnectionError("mock Prefect unavailable")

    async def list_runs(
        self, filters: RunFilters, cursor: str | None, limit: int
    ) -> Page[RunSummary]:
        self._require_available()
        runs = [self._run(item) for item in self._prefect["runs"]]
        if filters.execution_type:
            runs = [run for run in runs if run.state.type == filters.execution_type]
        if filters.deployment_id:
            runs = [run for run in runs if run.deployment_id == filters.deployment_id]
        if filters.project_id:
            runs = [run for run in runs if run.project_id == filters.project_id]
        offset = int(cursor or 0)
        page = runs[offset : offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(runs) else None
        return Page(items=page, nextCursor=next_cursor)

    async def get_run(self, run_id: str) -> RunDetail:
        self._require_available()
        raw = self._find_run(run_id)
        return RunDetail(
            run=self._run(raw),
            parameters=raw.get("parameters", {}),
            tags=raw.get("tags", []),
            projectContext=self._project_context(raw),
        )

    async def list_registered_deployments(
        self, cursor: str | None, limit: int
    ) -> Page[DeploymentSummary]:
        self._require_available()
        deployments = [self._deployment(raw) for raw in self._prefect["deployments"]]
        offset = int(cursor or 0)
        items = deployments[offset : offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(deployments) else None
        return Page(items=items, nextCursor=next_cursor)

    async def get_deployment(self, deployment_id: str) -> DeploymentSummary:
        self._require_available()
        return self._deployment(self._find_deployment(deployment_id))

    async def list_work_pools(self) -> list[PoolSnapshot]:
        self._require_available()
        return [self._pool(raw) for raw in self._prefect["pools"]]

    async def list_work_queues(self, work_pool_name: str) -> list[QueueSnapshot]:
        return (await self.get_work_pool_concurrency(work_pool_name)).queues

    async def list_workers(self, work_pool_name: str) -> list[WorkerSnapshot]:
        return (await self.get_work_pool_concurrency(work_pool_name)).workers

    async def get_work_pool_concurrency(self, work_pool_name: str) -> PoolSnapshot:
        self._require_available()
        for raw in self._prefect["pools"]:
            if raw["name"] == work_pool_name:
                return self._pool(raw)
        raise KeyError(work_pool_name)

    async def get_work_queue(self, queue_id: str) -> QueueSnapshot:
        self._require_available()
        _, raw = self._find_queue(queue_id)
        return self._queue(raw)

    async def submit_registered_deployment(
        self, deployment_id: str, parameters: dict[str, Any], idempotency_key: str
    ) -> RunSummary:
        self._require_available()
        deployment = self._find_deployment(deployment_id)
        self._submit_counter += 1
        run_id = f"mock-submitted-{self._submit_counter}"
        raw = {
            "runId": run_id,
            "name": f"{deployment['name']} · {self._submit_counter}",
            "deploymentId": deployment_id,
            "deploymentName": deployment["name"],
            "projectId": deployment.get("projectId"),
            "workPoolName": deployment.get("workPoolName"),
            "workQueueName": deployment.get("workQueueName"),
            "state": {
                "type": "SCHEDULED",
                "name": "Scheduled",
                "timestamp": self._clock.isoformat(),
                "terminal": False,
            },
            "scheduledAt": self._clock.isoformat(),
            "startedAt": None,
            "endedAt": None,
            "parameters": copy.deepcopy(parameters),
            "tags": [],
        }
        self._prefect["runs"].insert(0, raw)
        self.submit_calls.append(deployment_id)
        return self._run(raw)

    async def cancel_run(self, run_id: str) -> RunSummary:
        self._require_available()
        raw = self._find_run(run_id)
        raw["state"] = {
            "type": "CANCELLED",
            "name": "Cancelling",
            "timestamp": self._clock.isoformat(),
            "terminal": False,
            "message": "Cancellation requested",
        }
        self.cancel_calls.append(run_id)
        return self._run(raw)

    async def pause_schedule(
        self, deployment_id: str, schedule_id: str
    ) -> DeploymentSummary:
        return await self._set_schedule(deployment_id, schedule_id, False)

    async def resume_schedule(
        self, deployment_id: str, schedule_id: str
    ) -> DeploymentSummary:
        return await self._set_schedule(deployment_id, schedule_id, True)

    async def pause_work_queue(self, queue_id: str) -> QueueSnapshot:
        return await self._set_queue(queue_id, True)

    async def resume_work_queue(self, queue_id: str) -> QueueSnapshot:
        return await self._set_queue(queue_id, False)

    async def _set_schedule(
        self, deployment_id: str, schedule_id: str, active: bool
    ) -> DeploymentSummary:
        self._require_available()
        deployment = self._find_deployment(deployment_id)
        for schedule in deployment["schedules"]:
            if schedule["scheduleId"] == schedule_id:
                schedule["active"] = active
                schedule["updatedAt"] = self._clock.isoformat()
                return self._deployment(deployment)
        raise KeyError(schedule_id)

    async def _set_queue(self, queue_id: str, paused: bool) -> QueueSnapshot:
        self._require_available()
        _, raw = self._find_queue(queue_id)
        raw["isPaused"] = paused
        raw["status"] = "PAUSED" if paused else "READY"
        raw["updatedAt"] = self._clock.isoformat()
        return self._queue(raw)

    def _find_run(self, run_id: str) -> dict[str, Any]:
        for raw in self._prefect["runs"]:
            if raw["runId"] == run_id:
                return raw
        raise KeyError(run_id)

    def _find_deployment(self, deployment_id: str) -> dict[str, Any]:
        for raw in self._prefect["deployments"]:
            if raw["deploymentId"] == deployment_id:
                return raw
        raise KeyError(deployment_id)

    def _find_queue(self, queue_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        for pool in self._prefect["pools"]:
            for queue in pool["queues"]:
                if queue["queueId"] == queue_id:
                    return pool, queue
        raise KeyError(queue_id)

    def _run(self, raw: dict[str, Any]) -> RunSummary:
        state = PrefectStateSnapshot.model_validate(raw["state"])
        version = command_version(
            {
                "runId": raw["runId"],
                "type": state.type,
                "name": state.name,
                "timestamp": state.timestamp,
            }
        )
        return RunSummary(
            runId=raw["runId"],
            name=raw["name"],
            deploymentId=raw.get("deploymentId"),
            deploymentName=raw.get("deploymentName"),
            projectId=raw.get("projectId"),
            workPoolName=raw.get("workPoolName"),
            workQueueName=raw.get("workQueueName"),
            state=state,
            scheduledAt=self._optional_date(raw.get("scheduledAt")),
            startedAt=self._optional_date(raw.get("startedAt")),
            endedAt=self._optional_date(raw.get("endedAt")),
            scientific=None,
            commandVersion=version,
        )

    def _deployment(self, raw: dict[str, Any]) -> DeploymentSummary:
        schedules = []
        for item in raw.get("schedules", []):
            updated = self._optional_date(item.get("updatedAt"))
            schedules.append(
                ScheduleSummary(
                    scheduleId=item["scheduleId"],
                    label=item["label"],
                    active=item["active"],
                    updatedAt=updated,
                    commandVersion=command_version(
                        {
                            "scheduleId": item["scheduleId"],
                            "active": item["active"],
                            "updatedAt": updated,
                        }
                    ),
                )
            )
        return DeploymentSummary(
            deploymentId=raw["deploymentId"],
            name=raw["name"],
            flowName=raw["flowName"],
            projectContext=ProjectContext(
                projectId=raw.get("projectId", "bogda-main"),
                effectiveAutonomyMode=raw.get("autonomyMode"),
                modeSource=("deployment-default" if raw.get("autonomyMode") else "unavailable"),
                writable=False,
            ),
            workPoolName=raw.get("workPoolName"),
            workQueueName=raw.get("workQueueName"),
            parameterSchema=raw.get("parameterSchema", {}),
            allowlisted=raw.get("allowlisted", False),
            schedules=schedules,
        )

    def _project_context(self, raw: dict[str, Any]) -> ProjectContext | None:
        project_id = raw.get("projectId")
        if not project_id:
            return None
        deployment = self._find_deployment(raw["deploymentId"]) if raw.get("deploymentId") else None
        mode = deployment.get("autonomyMode") if deployment else None
        return ProjectContext(
            projectId=project_id,
            effectiveAutonomyMode=mode,
            modeSource="frozen-run-request" if mode else "unavailable",
            writable=False,
        )

    def _pool(self, raw: dict[str, Any]) -> PoolSnapshot:
        return PoolSnapshot(
            name=raw["name"],
            status=raw["status"],
            isPaused=raw["isPaused"],
            concurrencyLimit=raw.get("concurrencyLimit"),
            activeSlots=raw.get("activeSlots", 0),
            queues=[self._queue(queue) for queue in raw.get("queues", [])],
            workers=[WorkerSnapshot.model_validate(worker) for worker in raw.get("workers", [])],
        )

    def _queue(self, raw: dict[str, Any]) -> QueueSnapshot:
        updated = self._optional_date(raw.get("updatedAt"))
        return QueueSnapshot(
            queueId=raw["queueId"],
            name=raw["name"],
            status=raw["status"],
            isPaused=raw["isPaused"],
            concurrencyLimit=raw.get("concurrencyLimit"),
            commandVersion=command_version(
                {
                    "queueId": raw["queueId"],
                    "isPaused": raw["isPaused"],
                    "updatedAt": updated,
                }
            ),
        )

    @staticmethod
    def _date(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _optional_date(self, value: str | None) -> datetime | None:
        return self._date(value) if value else None
