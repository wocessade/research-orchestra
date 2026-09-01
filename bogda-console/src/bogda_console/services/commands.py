from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Awaitable, Callable

import httpx

from bogda_console.adapters.mock_run_results import ReviewConflict
from bogda_console.config import Settings
from bogda_console.constants import RESEARCH_POOL
from bogda_console.contracts.models import (
    ApiErrorCode,
    ApiErrorDetails,
    AutonomyMode,
    AutonomyPolicySnapshot,
    CommandReceipt,
    DeploymentSummary,
    OwnerApprovalView,
    ArtifactCleanupView,
    QueueSnapshot,
    RunDetail,
    RunResultView,
    RunSummary,
    ScientificStatus,
    DecisionCenterSnapshot,
    ModelPolicySnapshot,
    ModelPolicyPatch,
)
from bogda_console.contracts.ports import (
    AutonomyPolicyConflict,
    AutonomyPolicyPort,
    PrefectCommandPort,
    PrefectQueryPort,
    RunResultPort,
    ModelControlCommandPort,
    ModelControlConflict,
    ModelControlUnavailable,
    ModelControlNotFound,
    ModelControlNotApplicable,
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
        policy: AutonomyPolicyPort | None = None,
        model_control: ModelControlCommandPort | None = None,
        approvals: Any | None = None,
        lifecycle: Any | None = None,
    ) -> None:
        self.settings = settings
        self.prefect = prefect
        self.results = results
        self.policy = policy
        self._model_control = model_control
        self._approvals = approvals
        self._lifecycle = lifecycle
        self._now = now or (lambda: datetime.now(UTC))
        self._locks: dict[str, asyncio.Lock] = {}

    async def submit(
        self, deployment_id: str, parameters: dict[str, Any], idempotency_key: str,
        run_preparation_id: str | None = None,
    ) -> CommandReceipt[RunSummary]:
        async with self._lock(f"deployment:{deployment_id}"):
            self._require_commands()
            if deployment_id not in self.settings.allowed_deployment_ids:
                self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, deployment_id)
            deployment = await self._pre_read(
                "prefect", lambda: self.prefect.get_deployment(deployment_id)
            )
            self._authorize_pool(deployment.work_pool_name, deployment_id)
            if deployment.work_pool_name == RESEARCH_POOL:
                pool = await self._pre_read(
                    "prefect", lambda: self.prefect.get_work_pool_concurrency(RESEARCH_POOL)
                )
                if pool.concurrency_limit != 1:
                    self._raise(
                        ApiErrorCode.INFRASTRUCTURE_MISCONFIGURED,
                        409,
                        f"{RESEARCH_POOL} concurrency limit must equal one",
                    )
            if run_preparation_id is not None:
                self._require_model_control_writes()
                await self._mutate(
                    "modelControl",
                    lambda: self._model_control.confirm_preparation(run_preparation_id, idempotency_key),
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

    async def resolve_decision(
        self,
        decision_id: str,
        action_id: str,
        expected_revision: int,
        rationale: str | None = None,
        *,
        actual_cost_cny: Decimal | None = None,
        new_call_id: str | None = None,
    ) -> CommandReceipt[DecisionCenterSnapshot]:
        async with self._lock(f"decision:{decision_id}"):
            self._require_decision_writes()
            snapshot = await self._mutate(
                "modelControl",
                lambda: self._model_control.resolve_decision(
                    decision_id,
                    action_id,
                    expected_revision,
                    rationale,
                    actual_cost_cny=actual_cost_cny,
                    new_call_id=new_call_id,
                ),
            )
            return self._receipt("resolveDecision", decision_id, snapshot)

    async def set_global_model_policy(self, patch: ModelPolicyPatch, expected_revision: int) -> CommandReceipt[ModelPolicySnapshot]:
        async with self._lock("model-policy:global"):
            self._require_model_control_writes()
            snapshot = await self._mutate("modelControl", lambda: self._model_control.set_global_policy(patch, expected_revision))
            return self._receipt("setGlobalModelPolicy", "global", snapshot)

    async def set_project_model_policy(self, project_id: str, patch: ModelPolicyPatch | None, expected_revision: int) -> CommandReceipt[ModelPolicySnapshot]:
        async with self._lock(f"model-policy:project:{project_id}"):
            self._require_model_control_writes()
            snapshot = await self._mutate("modelControl", lambda: self._model_control.set_project_policy(project_id, patch, expected_revision))
            return self._receipt("setProjectModelPolicy", project_id, snapshot)

    async def issue_approval(
        self,
        run_id: str,
        *,
        expected_cost: Decimal,
        authorized_ceiling: Decimal,
        minimum_remaining: Decimal,
        requested_tier: str,
        pricing_version: str,
        ttl_seconds: int = 3600,
    ) -> CommandReceipt[OwnerApprovalView]:
        async with self._lock(f"approval:{run_id}"):
            self._require_approval_writes()
            current = (await self._pre_read("prefect", lambda: self.prefect.get_run(run_id))).run
            self._authorize_run(current)
            from bogda.contracts import BudgetSource, ModelTier, RunBudgetEnvelope

            try:
                envelope = RunBudgetEnvelope(
                    expected_cost=expected_cost,
                    authorized_ceiling=authorized_ceiling,
                    minimum_remaining=minimum_remaining,
                    requested_tier=ModelTier(requested_tier),
                    fallback_tier=None,
                    budget_source=BudgetSource.RUN,
                    pricing_version=pricing_version,
                )
                credential = self._approvals.issue(
                    run_id=run_id,
                    envelope=envelope,
                    actor_id=self.settings.actor_id,
                    ttl=timedelta(seconds=ttl_seconds),
                )
            except Exception as error:
                self._raise(
                    ApiErrorCode.VALIDATION_ERROR,
                    400,
                    str(error),
                    source="approval",
                )
            return self._receipt(
                "issueOwnerApproval",
                run_id,
                OwnerApprovalView(
                    credentialId=credential.credential_id,
                    runId=credential.run_id,
                    envelopeDigest=credential.envelope_digest,
                    pricingVersion=credential.pricing_version,
                    authorizedCeilingCny=credential.authorized_ceiling_cny,
                    actorId=credential.actor_id,
                    issuedAt=credential.issued_at,
                    expiresAt=credential.expires_at,
                ),
            )

    async def cleanup_artifacts(
        self, run_id: str, *, confirm: str
    ) -> CommandReceipt[ArtifactCleanupView]:
        async with self._lock(f"artifacts:{run_id}"):
            self._require_cleanup_writes()
            from bogda.artifacts.lifecycle import ArtifactLifecycleError

            try:
                receipt = self._lifecycle.cleanup(
                    run_id, actor_id=self.settings.actor_id, confirm=confirm
                )
            except ArtifactLifecycleError as error:
                code = (
                    ApiErrorCode.COMMAND_NOT_APPLICABLE
                    if "confirm" in str(error)
                    else ApiErrorCode.VALIDATION_ERROR
                )
                status = 409 if code is ApiErrorCode.COMMAND_NOT_APPLICABLE else 400
                self._raise(code, status, str(error), source="artifacts")
            return self._receipt(
                "cleanupArtifacts",
                run_id,
                ArtifactCleanupView(
                    runId=receipt.run_id,
                    actorId=receipt.actor_id,
                    deletedKinds=list(receipt.deleted_kinds),
                ),
            )

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

    async def decide_checkpoint(
        self,
        run_id: str,
        expected_command_version: str,
        verdict: str,
        rationale: str | None,
    ) -> CommandReceipt[RunDetail]:
        async with self._lock(f"checkpoint:{run_id}"):
            self._require_commands()
            if not self.settings.review_enabled:
                self._raise(
                    ApiErrorCode.RESOURCE_NOT_ALLOWLISTED,
                    403,
                    "checkpoint decisions disabled",
                )
            detail = await self._pre_read("prefect", lambda: self.prefect.get_run(run_id))
            self._authorize_run(detail.run)
            checkpoint = detail.checkpoint
            if checkpoint is None or checkpoint.verdict is not None:
                self._raise(
                    ApiErrorCode.COMMAND_NOT_APPLICABLE,
                    409,
                    "run has no open research checkpoint",
                    detail,
                )
            self._check_version(
                checkpoint.command_version, expected_command_version, checkpoint
            )
            await self._mutate(
                "prefect",
                lambda: self.prefect.resume_run(
                    run_id,
                    {
                        "verdict": verdict,
                        "rationale": rationale,
                        "decided_by": "human",
                        "command_version": checkpoint.command_version,
                    },
                ),
            )
            post = await self._post_read("prefect", lambda: self.prefect.get_run(run_id))
            return self._receipt("decideCheckpoint", run_id, post)

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
            self._authorize_pool(deployment.work_pool_name, schedule_id)
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

    async def set_global_autonomy(
        self, mode: AutonomyMode | str, expected_revision: int
    ) -> CommandReceipt[AutonomyPolicySnapshot]:
        async with self._lock("autonomy-policy"):
            self._require_autonomy_writes()
            if self.policy is None:
                self._raise(
                    ApiErrorCode.AUTONOMY_POLICY_UNAVAILABLE,
                    503,
                    "autonomy policy is not wired",
                    source="autonomyPolicy",
                )
            current = await self._pre_read("autonomyPolicy", self.policy.get_policy)
            if current.revision != expected_revision:
                self._raise(
                    ApiErrorCode.RESOURCE_CHANGED,
                    409,
                    "resource changed after the action was opened",
                    current,
                    source="autonomyPolicy",
                )
            await self._mutate(
                "autonomyPolicy",
                lambda: self.policy.set_global_mode(AutonomyMode(mode), expected_revision),
            )
            post = await self._post_read("autonomyPolicy", self.policy.get_policy)
            return self._receipt("setGlobalAutonomy", "global", post)

    async def set_project_autonomy(
        self, project_id: str, mode: AutonomyMode | str | None, expected_revision: int
    ) -> CommandReceipt[AutonomyPolicySnapshot]:
        async with self._lock("autonomy-policy"):
            self._require_autonomy_writes()
            if self.policy is None:
                self._raise(
                    ApiErrorCode.AUTONOMY_POLICY_UNAVAILABLE,
                    503,
                    "autonomy policy is not wired",
                    source="autonomyPolicy",
                )
            current = await self._pre_read("autonomyPolicy", self.policy.get_policy)
            if current.revision != expected_revision:
                self._raise(
                    ApiErrorCode.RESOURCE_CHANGED,
                    409,
                    "resource changed after the action was opened",
                    current,
                    source="autonomyPolicy",
                )
            resolved = None if mode is None else AutonomyMode(mode)
            await self._mutate(
                "autonomyPolicy",
                lambda: self.policy.set_project_mode(project_id, resolved, expected_revision),
            )
            post = await self._post_read("autonomyPolicy", self.policy.get_policy)
            return self._receipt("setProjectAutonomy", project_id, post)

    def _authorize_pool(self, work_pool_name: str | None, resource_id: str) -> None:
        if not work_pool_name or work_pool_name not in self.settings.allowed_work_pool_names:
            self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, resource_id)

    def _authorize_run(self, run: RunSummary) -> None:
        if not run.deployment_id or run.deployment_id not in self.settings.allowed_deployment_ids:
            self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, run.run_id, run)
        self._authorize_pool(run.work_pool_name, run.run_id)

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

    def _require_autonomy_writes(self) -> None:
        if not self.settings.autonomy_writes_enabled:
            self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, "autonomy policy writes disabled")

    def _require_model_control_writes(self) -> None:
        if not self.settings.model_control_enabled:
            self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, "model controls disabled")
        if self._model_control is None:
            self._raise(ApiErrorCode.MODEL_CONTROL_UNAVAILABLE, 503, "model-control backend is not wired", source="modelControl")

    def _require_decision_writes(self) -> None:
        if not (
            self.settings.model_control_enabled or self.settings.recovery_writes_enabled
        ):
            self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, "model controls disabled")
        if self._model_control is None:
            self._raise(ApiErrorCode.MODEL_CONTROL_UNAVAILABLE, 503, "model-control backend is not wired", source="modelControl")

    def _require_approval_writes(self) -> None:
        if not self.settings.approval_writes_enabled:
            self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, "owner approval writes disabled")
        if self._approvals is None:
            self._raise(
                ApiErrorCode.NOT_FOUND,
                404,
                "approval store is not wired",
                source="approval",
            )

    def _require_cleanup_writes(self) -> None:
        if not self.settings.artifact_cleanup_enabled:
            self._raise(ApiErrorCode.RESOURCE_NOT_ALLOWLISTED, 403, "artifact cleanup disabled")
        if self._lifecycle is None:
            self._raise(
                ApiErrorCode.NOT_FOUND,
                404,
                "artifact root is not wired",
                source="artifacts",
            )

    @staticmethod
    def _unavailable_code(source: str) -> ApiErrorCode:
        return {
            "prefect": ApiErrorCode.PREFECT_UNAVAILABLE,
            "runResult": ApiErrorCode.RUN_RESULT_UNAVAILABLE,
            "autonomyPolicy": ApiErrorCode.AUTONOMY_POLICY_UNAVAILABLE,
            "modelControl": ApiErrorCode.MODEL_CONTROL_UNAVAILABLE,
        }.get(source, ApiErrorCode.INTERNAL_ERROR)

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
            self._raise(self._unavailable_code(source), 503, str(error), source=source)

    async def _mutate(self, source: str, operation: Callable[[], Awaitable[Any]]) -> Any:
        try:
            return await operation()
        except ReviewConflict:
            raise
        except AutonomyPolicyConflict as error:
            self._raise(
                ApiErrorCode.RESOURCE_CHANGED,
                409,
                "resource changed after the action was opened",
                error.current,
                source="autonomyPolicy",
            )
        except ModelControlConflict as error:
            self._raise(ApiErrorCode.RESOURCE_CHANGED, 409, "resource changed after the action was opened", error.current, source="modelControl")
        except ModelControlNotFound as error:
            self._raise(ApiErrorCode.NOT_FOUND, 404, str(error), source="modelControl")
        except ModelControlNotApplicable as error:
            self._raise(ApiErrorCode.COMMAND_NOT_APPLICABLE, 409, str(error), source="modelControl")
        except ModelControlUnavailable as error:
            self._raise(ApiErrorCode.MODEL_CONTROL_UNAVAILABLE, 503, str(error), source="modelControl")
        except (ConnectionError, TimeoutError, httpx.RequestError) as error:
            self._raise(self._unavailable_code(source), 503, str(error), source=source)
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
