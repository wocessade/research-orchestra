from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable

import httpx

from bogda_console.adapters.mock_run_results import ReviewConflict
from bogda_console.config import Settings
from bogda_console.contracts.models import (
    ApiErrorCode,
    ApiErrorDetails,
    CommandReceipt,
    DeploymentSummary,
    QueueSnapshot,
    RunResultView,
    RunSummary,
    ScientificStatus,
)
from bogda_console.contracts.ports import (
    PrefectCommandPort,
    PrefectQueryPort,
    RunResultPort,
)
from bogda_console.services.errors import ServiceError


class CommandService:
    def __init__(
        self,
        *,
        settings: Settings,
        prefect: PrefectQueryPort | PrefectCommandPort,
        results: RunResultPort,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings
        self.prefect = prefect
        self.results = results
        self._now = now or (lambda: datetime.now(UTC))
        self._locks: dict[str, asyncio.Lock] = {}

    async def submit(
        self, deployment_id: str, parameters: dict[str, Any], idempotency_key: str
    ) -> CommandReceipt[RunSummary]:
        async with self._lock(f"deployment:{deployment_id}"):
            self._require_commands()
            if deployment_id not in self.settings.allowed_deployment_ids:
                self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, deployment_id)
            deployment = await self._pre_read(
                "prefect", lambda: self.prefect.get_deployment(deployment_id)
            )
            if deployment.work_pool_name == "dorm-x86":
                pool = await self._pre_read(
                    "prefect", lambda: self.prefect.get_work_pool_concurrency("dorm-x86")
                )
                if pool.concurrency_limit != 1:
                    self._raise(
                        ApiErrorCode.INFRASTRUCTURE_MISCONFIGURED,
                        409,
                        "dorm-x86 concurrency limit must equal one",
                    )
            submitted = await self._mutate(
                "prefect",
                lambda: self.prefect.submit_registered_deployment(
                    deployment_id, parameters, idempotency_key
                ),
            )
            post = await self._post_read(
                "prefect", lambda: self.prefect.get_run(submitted.run_id)
            )
            return self._receipt("submit", submitted.run_id, post.run)

    async def cancel(
        self, run_id: str, expected_command_version: str
    ) -> CommandReceipt[RunSummary]:
        async with self._lock(f"run:{run_id}"):
            self._require_commands()
            current = (await self._pre_read("prefect", lambda: self.prefect.get_run(run_id))).run
            self._authorize_run(current)
            self._check_version(current.command_version, expected_command_version, current)
            if current.state.terminal:
                self._raise(
                    ApiErrorCode.COMMAND_NOT_APPLICABLE,
                    409,
                    "terminal Flow Run cannot be cancelled",
                    current,
                )
            await self._mutate("prefect", lambda: self.prefect.cancel_run(run_id))
            post = (await self._post_read("prefect", lambda: self.prefect.get_run(run_id))).run
            if post.state.name not in {"Cancelling", "Cancelled"}:
                self._raise(
                    ApiErrorCode.COMMAND_OUTCOME_MISMATCH,
                    409,
                    "Prefect did not report Cancelling or Cancelled",
                    post,
                )
            return self._receipt("cancel", run_id, post)

    async def pause_schedule(
        self, deployment_id: str, schedule_id: str, expected_command_version: str
    ) -> CommandReceipt[DeploymentSummary]:
        return await self._schedule(
            "pauseSchedule", deployment_id, schedule_id, expected_command_version, False
        )

    async def resume_schedule(
        self, deployment_id: str, schedule_id: str, expected_command_version: str
    ) -> CommandReceipt[DeploymentSummary]:
        return await self._schedule(
            "resumeSchedule", deployment_id, schedule_id, expected_command_version, True
        )

    async def pause_queue(
        self, queue_id: str, expected_command_version: str
    ) -> CommandReceipt[QueueSnapshot]:
        return await self._queue("pauseQueue", queue_id, expected_command_version, True)

    async def resume_queue(
        self, queue_id: str, expected_command_version: str
    ) -> CommandReceipt[QueueSnapshot]:
        return await self._queue("resumeQueue", queue_id, expected_command_version, False)

    async def review(
        self,
        run_id: str,
        base_artifact_id: str,
        scientific_status: ScientificStatus | str,
        review_summary: str | None,
    ) -> CommandReceipt[RunResultView]:
        async with self._lock(f"review:{run_id}"):
            if not self.settings.review_enabled:
                self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, "review disabled")
            run = (await self._pre_read("prefect", lambda: self.prefect.get_run(run_id))).run
            self._authorize_run(run)
            current = await self._pre_read("runResult", lambda: self.results.get_latest(run_id))
            if current.artifact_id != base_artifact_id:
                self._raise(
                    ApiErrorCode.REVIEW_CONFLICT,
                    409,
                    "RunResult changed after the review form opened",
                    current,
                )
            if current.result is None:
                self._raise(
                    ApiErrorCode.COMMAND_NOT_APPLICABLE,
                    409,
                    "latest RunResult is not valid",
                    current,
                )
            try:
                await self._mutate(
                    "runResult",
                    lambda: self.results.append_review(
                        run_id,
                        base_artifact_id,
                        ScientificStatus(scientific_status),
                        review_summary,
                    ),
                )
            except ReviewConflict as error:
                self._raise(
                    ApiErrorCode.REVIEW_CONFLICT,
                    409,
                    str(error),
                    error.current_resource,
                )
            post = await self._post_read("runResult", lambda: self.results.get_latest(run_id))
            return self._receipt("review", run_id, post)

    async def _schedule(
        self,
        command: str,
        deployment_id: str,
        schedule_id: str,
        expected_command_version: str,
        active: bool,
    ) -> CommandReceipt[DeploymentSummary]:
        async with self._lock(f"schedule:{schedule_id}"):
            self._require_commands()
            if (
                deployment_id not in self.settings.allowed_deployment_ids
                or schedule_id not in self.settings.allowed_schedule_ids
            ):
                self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, schedule_id)
            deployment = await self._pre_read(
                "prefect", lambda: self.prefect.get_deployment(deployment_id)
            )
            schedule = next(
                (item for item in deployment.schedules if item.schedule_id == schedule_id), None
            )
            if schedule is None:
                self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, schedule_id)
            self._check_version(
                schedule.command_version, expected_command_version, deployment
            )
            if schedule.active == active:
                self._raise(
                    ApiErrorCode.COMMAND_NOT_APPLICABLE,
                    409,
                    "schedule already has requested state",
                    deployment,
                )
            if active:
                await self._mutate(
                    "prefect", lambda: self.prefect.resume_schedule(deployment_id, schedule_id)
                )
            else:
                await self._mutate(
                    "prefect", lambda: self.prefect.pause_schedule(deployment_id, schedule_id)
                )
            post = await self._post_read(
                "prefect", lambda: self.prefect.get_deployment(deployment_id)
            )
            post_schedule = next(item for item in post.schedules if item.schedule_id == schedule_id)
            if post_schedule.active != active:
                self._raise(
                    ApiErrorCode.COMMAND_OUTCOME_MISMATCH,
                    409,
                    "schedule state did not change",
                    post,
                )
            return self._receipt(command, schedule_id, post)

    async def _queue(
        self,
        command: str,
        queue_id: str,
        expected_command_version: str,
        paused: bool,
    ) -> CommandReceipt[QueueSnapshot]:
        async with self._lock(f"queue:{queue_id}"):
            self._require_commands()
            if queue_id not in self.settings.allowed_queue_ids:
                self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, queue_id)
            pools = await self._pre_read("prefect", self.prefect.list_work_pools)
            pool = next(
                (pool for pool in pools if any(queue.queue_id == queue_id for queue in pool.queues)),
                None,
            )
            if pool is None or pool.name not in self.settings.allowed_work_pool_names:
                self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, queue_id)
            current = next(queue for queue in pool.queues if queue.queue_id == queue_id)
            self._check_version(current.command_version, expected_command_version, current)
            if current.is_paused == paused:
                self._raise(
                    ApiErrorCode.COMMAND_NOT_APPLICABLE,
                    409,
                    "Queue already has requested state",
                    current,
                )
            if paused:
                await self._mutate("prefect", lambda: self.prefect.pause_work_queue(queue_id))
            else:
                await self._mutate("prefect", lambda: self.prefect.resume_work_queue(queue_id))
            post_pools = await self._post_read("prefect", self.prefect.list_work_pools)
            post = next(
                queue
                for item in post_pools
                for queue in item.queues
                if queue.queue_id == queue_id
            )
            if post.is_paused != paused:
                self._raise(
                    ApiErrorCode.COMMAND_OUTCOME_MISMATCH,
                    409,
                    "Queue state did not change",
                    post,
                )
            return self._receipt(command, queue_id, post)

    def _authorize_run(self, run: RunSummary) -> None:
        if not run.deployment_id or run.deployment_id not in self.settings.allowed_deployment_ids:
            self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, run.run_id, run)

    def _check_version(self, current: str, expected: str, resource: Any) -> None:
        if current != expected:
            self._raise(
                ApiErrorCode.RESOURCE_CHANGED,
                409,
                "resource changed after the action was opened",
                resource,
            )

    def _require_commands(self) -> None:
        if not self.settings.commands_enabled:
            self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, "commands disabled")

    def _receipt(self, command: str, resource_id: str, snapshot: Any):
        return CommandReceipt(
            command=command,
            resourceId=resource_id,
            acceptedAt=self._now(),
            snapshot=snapshot,
        )

    def _lock(self, key: str) -> asyncio.Lock:
        return self._locks.setdefault(key, asyncio.Lock())

    async def _pre_read(self, source: str, operation: Callable[[], Awaitable[Any]]) -> Any:
        try:
            return await operation()
        except (ServiceError, KeyError):
            raise
        except Exception as error:
            code = (
                ApiErrorCode.PREFECT_UNAVAILABLE
                if source == "prefect"
                else ApiErrorCode.RUN_RESULT_UNAVAILABLE
            )
            self._raise(code, 503, str(error), source=source)

    async def _mutate(self, source: str, operation: Callable[[], Awaitable[Any]]) -> Any:
        try:
            return await operation()
        except ReviewConflict:
            raise
        except (ConnectionError, TimeoutError, httpx.RequestError) as error:
            code = (
                ApiErrorCode.PREFECT_UNAVAILABLE
                if source == "prefect"
                else ApiErrorCode.RUN_RESULT_UNAVAILABLE
            )
            self._raise(code, 503, str(error), source=source)
        except Exception as error:
            self._raise(ApiErrorCode.COMMAND_REJECTED, 409, str(error), source=source)

    async def _post_read(self, source: str, operation: Callable[[], Awaitable[Any]]) -> Any:
        try:
            return await operation()
        except Exception as error:
            self._raise(
                ApiErrorCode.COMMAND_OUTCOME_UNKNOWN,
                503,
                str(error),
                source=source,
            )

    @staticmethod
    def _raise(
        code: ApiErrorCode,
        status: int,
        message: str,
        resource: Any | None = None,
        source: str | None = None,
    ) -> None:
        details = None
        if resource is not None:
            if hasattr(resource, "model_dump"):
                current = resource.model_dump(mode="json", by_alias=True)
            elif isinstance(resource, dict):
                current = resource
            else:
                current = None
            if current is not None:
                details = ApiErrorDetails(currentResource=current)
        raise ServiceError(
            code,
            message,
            source=source or ("prefect" if code != ApiErrorCode.REVIEW_CONFLICT else "runResult"),
            retryable=False,
            status_code=status,
            details=details,
        )
