"""Real-profile model control backed by the box-local policy store and budget kernel."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4

from bogda.budget.estimation import TokenWorkload, WorkloadEstimator
from bogda.budget.pricing import (
    PricePeriod,
    current_catalog,
    next_off_peak_start,
    period_at,
    period_for_window,
)
from bogda.contracts import ModelTier, TaskIntent
from bogda.policy import (
    ModelPolicyRevisionConflict,
    ModelPolicyStore,
    PolicyStore,
    PolicyStoreError,
)
from bogda_console.adapters.core_model_control import CoreUsageUnknownAdapter
from bogda_console.contracts.models import (
    AllowedRunPreferences,
    AutonomyMode,
    BudgetState,
    ModelBudgetSnapshot,
    ModelEventRow,
    ModelPolicyPatch,
    ModelPolicySnapshot,
    PriceCatalog,
    RunPreparationPreview,
    WorkloadEstimate,
)
from bogda_console.contracts.ports import (
    ModelControlConflict,
    ModelControlNotApplicable,
    ModelControlNotFound,
    ModelControlUnavailable,
)

_PRO_INTENTS = {TaskIntent.DECIDE, TaskIntent.AUDIT}


class LocalModelControlAdapter:
    """Model policy, run preparation and run budgets over real box-local state."""

    source_mode = "real"

    def __init__(
        self,
        *,
        store: ModelPolicyStore,
        recovery: CoreUsageUnknownAdapter,
        preparations_path: str | Path,
        autonomy: PolicyStore | None = None,
        balance: Any | None = None,
        ledger: Any | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._recovery = recovery
        self._preparations_path = Path(preparations_path)
        self._autonomy = autonomy
        self._balance = balance
        self._ledger = ledger
        self._now = now or (lambda: datetime.now(UTC))

    # -- decisions: usage-unknown recovery stays authoritative -----------------

    async def decision_center(self) -> Any:
        return await self._recovery.decision_center()

    async def resolve_decision(self, *args: Any, **kwargs: Any) -> Any:
        return await self._recovery.resolve_decision(*args, **kwargs)

    async def run_budget(self, run_id: str) -> ModelBudgetSnapshot:
        try:
            return await self._recovery.run_budget(run_id)
        except ModelControlNotFound:
            pass
        if self._ledger is None or not hasattr(self._ledger, "list_for_run"):
            raise ModelControlNotFound(run_id)
        reservations = self._ledger.list_for_run(run_id)
        if not reservations:
            raise ModelControlNotFound(run_id)
        authorized = sum((item.reserved for item in reservations), Decimal("0"))
        used = sum((item.actual_cost or Decimal("0") for item in reservations), Decimal("0"))
        active = sum(
            (
                item.reserved
                for item in reservations
                if item.actual_cost is None and item.released_amount is None
            ),
            Decimal("0"),
        )
        events: list[ModelEventRow] = []
        for index, item in enumerate(reservations, start=1):
            events.append(
                ModelEventRow(
                    eventId=item.id,
                    eventType="budget_reserved",
                    occurredAt=item.created_at,
                    summary=f"reserved {item.reserved} CNY",
                )
            )
            if item.released_amount is not None:
                events.append(
                    ModelEventRow(
                        eventId=f"{item.id}-release",
                        eventType="budget_released",
                        occurredAt=item.updated_at,
                        summary=f"released {item.released_amount} CNY",
                    )
                )
        return ModelBudgetSnapshot(
            runId=run_id,
            projectId="bogda-main",
            state=BudgetState.READY,
            currency="CNY",
            expectedCost=authorized,
            authorizedCeiling=authorized,
            usedCost=used,
            reservedCost=active,
            remainingCost=max(authorized - used - active, Decimal("0")),
            revision=0,
            events=tuple(events),
        )

    # -- policy ---------------------------------------------------------------

    def _catalog_view(self) -> tuple[PriceCatalog, Any | None]:
        try:
            catalog = current_catalog(self._now())
        except ValueError:
            return PriceCatalog(status="missing"), None
        return (
            PriceCatalog(
                status="ready",
                version=catalog.version,
                source=catalog.source,
                effective_at=catalog.effective_at,
                review_by=catalog.review_by,
            ),
            catalog,
        )

    async def model_policy(self, project_id: str | None = None) -> ModelPolicySnapshot:
        try:
            resolved = self._store.resolve(project_id)
        except PolicyStoreError as error:
            raise ModelControlUnavailable(str(error)) from error
        values = resolved.values
        catalog_view, _ = self._catalog_view()
        return ModelPolicySnapshot(
            projectId=project_id,
            source=resolved.source,
            inheritsGlobal=resolved.inherits_global,
            defaultModelTier=values.default_model_tier.value,
            allowAutoUpgrade=values.allow_auto_upgrade,
            allowFlashDowngrade=values.allow_flash_downgrade,
            preferOffPeak=values.prefer_off_peak,
            autoResume=values.auto_resume,
            minimumRemaining=values.minimum_remaining,
            criticalNotifications=values.critical_notifications,
            workloadSafetyMargin=values.workload_safety_margin,
            priceCatalog=catalog_view,
            revision=resolved.policy_revision,
        )

    async def set_global_policy(
        self, patch: ModelPolicyPatch, expected_revision: int
    ) -> ModelPolicySnapshot:
        try:
            self._store.set_global(
                patch.model_dump(exclude_unset=True), expected_revision=expected_revision
            )
        except ModelPolicyRevisionConflict as error:
            raise ModelControlConflict(await self.model_policy()) from error
        return await self.model_policy()

    async def set_project_policy(
        self,
        project_id: str,
        patch: ModelPolicyPatch | None,
        expected_revision: int,
    ) -> ModelPolicySnapshot:
        values = None if patch is None else patch.model_dump(exclude_unset=True)
        try:
            self._store.set_project(
                project_id, values, expected_revision=expected_revision
            )
        except ModelPolicyRevisionConflict as error:
            raise ModelControlConflict(await self.model_policy(project_id)) from error
        return await self.model_policy(project_id)

    # -- run preparation ------------------------------------------------------

    def _effective_tier(
        self,
        requested: str,
        default_tier: str,
        intent: TaskIntent,
        preferences: AllowedRunPreferences,
    ) -> str:
        if requested == "flash":
            return "flash"
        if requested == "pro":
            return "pro"
        if default_tier == "flash":
            return "flash"
        if default_tier == "pro":
            return "pro"
        if intent in _PRO_INTENTS and preferences.allow_auto_upgrade:
            return "pro"
        return "flash"

    def _autonomy_mode(self, project_id: str) -> AutonomyMode:
        if self._autonomy is None:
            return AutonomyMode.SUPERVISED
        resolved = self._autonomy.resolve_mode(project_id)
        return AutonomyMode(resolved.effective_mode.value)

    async def preview_run(
        self,
        project_id: str,
        intent: str,
        requested_model_tier: str,
        workload: WorkloadEstimate,
        allowed_preferences: AllowedRunPreferences,
        deadline: datetime | None = None,
    ) -> RunPreparationPreview:
        now = self._now()
        try:
            intent_enum = TaskIntent(intent)
            requested = ModelTier(requested_model_tier)
        except ValueError as error:
            raise ModelControlNotApplicable(str(error)) from error
        if deadline is not None and deadline <= now:
            raise ModelControlNotApplicable("deadline is already in the past")

        policy = await self.model_policy(project_id)
        if policy.price_catalog.status != "ready":
            raise ModelControlUnavailable("price catalog is not reviewable")

        effective = self._effective_tier(
            requested.value, policy.default_model_tier, intent_enum, allowed_preferences
        )
        fallback = (
            "flash"
            if effective == "pro" and allowed_preferences.allow_flash_downgrade
            else None
        )

        runtime = timedelta(minutes=workload.runtime_minutes)
        start = now
        if allowed_preferences.prefer_off_peak and period_at(now) is PricePeriod.PEAK:
            candidate = next_off_peak_start(now).astimezone(UTC)
            if deadline is None or candidate <= deadline:
                start = candidate
        end = start + runtime if runtime > timedelta() else start + timedelta(minutes=1)
        period = period_for_window(start, end)

        token_workload = TokenWorkload(
            expected_calls=workload.expected_calls,
            cache_hit_input_tokens=0,
            cache_miss_input_tokens=workload.input_tokens,
            output_tokens=workload.output_tokens,
            allowed_retries=0,
        )
        try:
            estimate = WorkloadEstimator().estimate(
                intent=intent_enum,
                tier=ModelTier(effective),
                workload=token_workload,
                start=start,
                end=end,
                as_of=now,
            )
        except ValueError as error:
            raise ModelControlNotApplicable(str(error)) from error

        ceiling = estimate.authorized_ceiling * policy.workload_safety_margin
        balance_state, balance = await self._balance_state(ceiling, policy)
        budget = ModelBudgetSnapshot(
            runId="preview",
            projectId=project_id,
            state=balance_state,
            currency="CNY",
            expectedCost=estimate.expected_cost,
            authorizedCeiling=ceiling,
            usedCost=Decimal("0"),
            reservedCost=Decimal("0"),
            remainingCost=balance,
            revision=0,
            intent=intent,  # type: ignore[arg-type]
            requestedModelTier=requested_model_tier,  # type: ignore[arg-type]
            effectiveModelTier=effective,  # type: ignore[arg-type]
            effectiveAutonomyMode=self._autonomy_mode(project_id),
            pricePeriod="peak" if period is PricePeriod.PEAK else "off-peak",
            scheduledStart=start,
        )
        preparation_id = f"prep_{uuid4().hex}"
        preview = RunPreparationPreview(
            preparationId=preparation_id,
            projectId=project_id,
            intent=intent,  # type: ignore[arg-type]
            requestedModelTier=requested_model_tier,  # type: ignore[arg-type]
            effectiveModelTier=effective,  # type: ignore[arg-type]
            effectiveAutonomyMode=budget.effective_autonomy_mode,
            fallbackModelTier=fallback,  # type: ignore[arg-type]
            pricePeriod=budget.price_period,
            scheduledStart=start,
            workload=workload,
            allowedPreferences=allowed_preferences,
            deadline=deadline,
            budget=budget,
            policyRevision=policy.revision,
        )
        self._save_preparation(preview, idempotency_key=None)
        return preview

    async def _balance_state(
        self, ceiling: Decimal, policy: ModelPolicySnapshot
    ) -> tuple[BudgetState, Decimal]:
        if self._balance is None:
            return BudgetState.READY, ceiling
        try:
            snapshot = await self._balance.get_balance()
        except Exception as error:  # fail closed: never price against empty data
            raise ModelControlUnavailable(
                f"usage source unavailable: {error}"
            ) from error
        state = (
            BudgetState.READY
            if snapshot.total_balance - ceiling >= policy.minimum_remaining
            else BudgetState.INSUFFICIENT
        )
        return state, max(snapshot.total_balance - ceiling, Decimal("0"))

    async def confirm_preparation(
        self, preparation_id: str, idempotency_key: str
    ) -> RunPreparationPreview:
        records = self._load_preparations()
        record = records.get(preparation_id)
        if record is None:
            raise ModelControlNotFound(preparation_id)
        stored_key = record.get("idempotency_key")
        if stored_key is not None:
            if stored_key != idempotency_key:
                raise ModelControlConflict(
                    RunPreparationPreview.model_validate(record["preparation"])
                )
            return RunPreparationPreview.model_validate(record["preparation"])
        preview = RunPreparationPreview.model_validate(record["preparation"])
        confirmed = preview.model_copy(
            update={"confirmed": True, "confirmed_at": datetime.now(UTC)}
        )
        record["preparation"] = confirmed.model_dump(mode="json", by_alias=True)
        record["idempotency_key"] = idempotency_key
        self._write_preparations(records)
        return confirmed

    def _load_preparations(self) -> dict[str, dict[str, Any]]:
        if not self._preparations_path.exists():
            return {}
        try:
            payload = json.loads(
                self._preparations_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return {}
        records = payload.get("preparations")
        if not isinstance(records, dict):
            return {}
        return {
            str(key): dict(value)
            for key, value in records.items()
            if isinstance(value, dict)
        }

    def _save_preparation(
        self, preview: RunPreparationPreview, *, idempotency_key: str | None
    ) -> None:
        records = self._load_preparations()
        records[preview.preparation_id] = {
            "preparation": preview.model_dump(mode="json", by_alias=True),
            "idempotency_key": idempotency_key,
        }
        self._write_preparations(records)

    def _write_preparations(self, records: Mapping[str, Mapping[str, Any]]) -> None:
        self._preparations_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._preparations_path.with_name(
            f".{self._preparations_path.name}.tmp"
        )
        temporary.write_text(
            json.dumps(
                {"preparations": dict(records)}, ensure_ascii=False, indent=2
            ),
            encoding="utf-8",
        )
        temporary.replace(self._preparations_path)
