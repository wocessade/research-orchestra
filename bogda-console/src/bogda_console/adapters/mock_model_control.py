from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from bogda_console.contracts.models import (
    BudgetState,
    DecisionAction,
    DecisionCenterSnapshot,
    DecisionItem,
    EvidenceReference,
    ModelBudgetSnapshot,
    ModelPolicySnapshot,
    ModelPolicyPatch,
    PriceCatalog,
    HardSafetyBaselines,
    RunPreparationPreview,
    WorkloadEstimate,
    AllowedRunPreferences,
    UrgencyGroup,
)
from bogda_console.contracts.ports import ModelControlConflict, ModelControlNotApplicable, ModelControlNotFound


class MockModelControlAdapter:
    """The sole deterministic in-memory authority for console model controls."""

    def __init__(self) -> None:
        self._revision = 0
        self._global: dict[str, object] = {
            "default_model_tier": "auto", "allow_auto_upgrade": True,
            "allow_flash_downgrade": True, "prefer_off_peak": True,
            "auto_resume": True, "minimum_remaining": Decimal("10.00"),
        }
        self._projects: dict[str, dict[str, object]] = {}
        self._items: dict[str, DecisionItem] = {
            "decision-1": DecisionItem(
                decisionId="decision-1", decisionKind="peak-override", title="Peak run",
                urgencyGroup=UrgencyGroup.NEEDS_OWNER_NOW,
                projectId="project-1", runId="run-1", reason="Preparation needs owner approval",
                risk="budget", estimatedCost=Decimal("1.00"), deadline=None,
                evidence=[EvidenceReference(kind="run", refId="run-1", label="Run")],
                actions=(
                    DecisionAction(actionId="approve", label="Approve", costImpact="Uses budget", requiresRationale=True),
                    DecisionAction(actionId="defer", label="Defer", costImpact="No additional spend"),
                ),
                revision=0, logSummary="Awaiting owner decision.",
            )
            ,"decision-usage-unknown": DecisionItem(
                decisionId="decision-usage-unknown", decisionKind="usage-unknown", title="Usage unknown",
                urgencyGroup=UrgencyGroup.NEEDS_OWNER_NOW, projectId="project-unknown", runId="run-unknown-usage",
                reason="The model call cost is unknown", risk="usage", estimatedCost=Decimal("0"),
                actions=(DecisionAction(actionId="reconcile", label="Reconcile", costImpact="No new call"),),
                revision=0, logSummary="Reconcile usage before recovery.",
            )
        }
        self._budgets = {"run-1": ModelBudgetSnapshot(
            runId="run-1", projectId="project-1", state=BudgetState.AWAITING_APPROVAL,
            currency="CNY", expectedCost=Decimal("1.00"), authorizedCeiling=Decimal("2.00"),
            usedCost=Decimal("0"), reservedCost=Decimal("0"), remainingCost=Decimal("2.00"),
            decisionId="decision-1", revision=0, intent="explore", requestedModelTier="pro",
            effectiveModelTier="flash", effectiveAutonomyMode="supervised", pricePeriod="off-peak",
        ), "run-unknown-usage": ModelBudgetSnapshot(
            runId="run-unknown-usage", projectId="project-unknown", state=BudgetState.USAGE_UNKNOWN,
            currency="CNY", expectedCost=Decimal("0"), authorizedCeiling=Decimal("0"),
            usedCost=Decimal("0"), reservedCost=Decimal("0"), remainingCost=Decimal("0"),
            decisionId="decision-usage-unknown", revision=0,
        ), "run-completed": ModelBudgetSnapshot(
            runId="run-completed", projectId="bogda-main", state=BudgetState.READY,
            currency="CNY", expectedCost=Decimal("1.20"), authorizedCeiling=Decimal("4.00"),
            usedCost=Decimal("1.20"), reservedCost=Decimal("0"), remainingCost=Decimal("2.80"),
            decisionId=None, revision=0, intent="execute", requestedModelTier="auto",
            effectiveModelTier="flash", effectiveAutonomyMode="supervised", pricePeriod="off-peak",
        ), "run-active": ModelBudgetSnapshot(
            runId="run-active", projectId="bogda-main", state=BudgetState.USAGE_UNKNOWN,
            currency="CNY", expectedCost=Decimal("0.80"), authorizedCeiling=Decimal("2.00"),
            usedCost=Decimal("0"), reservedCost=Decimal("0.80"), remainingCost=Decimal("1.20"),
            decisionId="decision-usage-unknown", revision=0, intent="execute", requestedModelTier="auto",
            effectiveModelTier="flash", effectiveAutonomyMode="supervised", pricePeriod="off-peak",
        )}
        self._preparations: dict[str, RunPreparationPreview] = {}
        self._confirmations: dict[str, tuple[str, str]] = {}
        self._decision_rationales: dict[str, str] = {}

    async def decision_center(self) -> DecisionCenterSnapshot:
        return DecisionCenterSnapshot(items=list(self._items.values()), revision=self._revision)

    async def run_budget(self, run_id: str) -> ModelBudgetSnapshot:
        if run_id not in self._budgets:
            raise ModelControlNotFound(run_id)
        return self._budgets[run_id]

    def _policy(self, project_id: str | None, source: str, values: dict[str, object], inherits: bool) -> ModelPolicySnapshot:
        return ModelPolicySnapshot(
            projectId=project_id, source=source,
            inheritsGlobal=inherits, revision=self._revision, usageSnapshotStaleAfterSeconds=120,
            criticalNotifications=True, workloadSafetyMargin=Decimal("1.20"),
            priceCatalog=PriceCatalog(status="ready", version="mock-v1", source="mock"),
            hardSafetyBaselines=HardSafetyBaselines(),
            **values,
        )

    async def model_policy(self, project_id: str | None = None) -> ModelPolicySnapshot:
        if project_id and project_id in self._projects:
            values = {**self._global, **self._projects[project_id]}
            return self._policy(project_id, "project", values, False)
        return self._policy(project_id, "global", dict(self._global), True)

    async def preview_run(
        self, project_id: str, intent: str, requested_model_tier: str,
        workload: WorkloadEstimate, allowed_preferences: AllowedRunPreferences, deadline=None,
    ) -> RunPreparationPreview:
        policy = await self.model_policy(project_id)
        effective = "pro" if requested_model_tier == "pro" else "flash"
        fallback = "flash" if effective == "pro" and allowed_preferences.allow_flash_downgrade else None
        preparation_id = f"prep_{uuid4().hex}"
        budget = ModelBudgetSnapshot(
            runId=preparation_id, projectId=project_id, state=BudgetState.READY,
            currency="CNY", expectedCost=Decimal("1.00"), authorizedCeiling=Decimal("2.00"),
            usedCost=Decimal("0"), reservedCost=Decimal("0"), remainingCost=Decimal("2.00"),
            decisionId=None, revision=self._revision, intent=intent, requestedModelTier=requested_model_tier,
            effectiveModelTier=effective, effectiveAutonomyMode="supervised", pricePeriod="off-peak",
        )
        preview = RunPreparationPreview(
            preparationId=preparation_id, projectId=project_id, intent=intent,
            requestedModelTier=requested_model_tier, effectiveModelTier=effective,
            effectiveAutonomyMode="supervised", fallbackModelTier=fallback, pricePeriod="off-peak",
            scheduledStart=None, workload=workload, allowedPreferences=allowed_preferences,
            deadline=deadline, budget=budget, policyRevision=policy.revision,
        )
        self._preparations[preparation_id] = preview
        return preview

    async def resolve_decision(self, decision_id: str, action_id: str, expected_revision: int, rationale: str | None = None) -> DecisionCenterSnapshot:
        current = await self.decision_center()
        if expected_revision != self._revision:
            raise ModelControlConflict(current)
        item = self._items.get(decision_id)
        if item is None:
            raise ModelControlNotFound(decision_id)
        action = next((action for action in item.actions if action.action_id == action_id), None)
        if action is None:
            raise ModelControlConflict(current)
        if action.requires_rationale and (not rationale or not rationale.strip()):
            raise ModelControlNotApplicable("rationale is required for this action")
        if rationale is not None:
            self._decision_rationales[decision_id] = rationale.strip()
        del self._items[decision_id]
        self._revision += 1
        return await self.decision_center()

    async def set_global_policy(self, patch: ModelPolicyPatch, expected_revision: int) -> ModelPolicySnapshot:
        current = await self.model_policy()
        if expected_revision != self._revision:
            raise ModelControlConflict(current)
        self._global.update(patch.model_dump(exclude_unset=True))
        self._revision += 1
        return await self.model_policy()

    async def set_project_policy(self, project_id: str, patch: ModelPolicyPatch | None, expected_revision: int) -> ModelPolicySnapshot:
        current = await self.model_policy(project_id)
        if expected_revision != self._revision:
            raise ModelControlConflict(current)
        if patch is None:
            self._projects.pop(project_id, None)
        else:
            self._projects[project_id] = patch.model_dump(exclude_unset=True)
        self._revision += 1
        return await self.model_policy(project_id)

    async def confirm_preparation(self, preparation_id: str, idempotency_key: str) -> RunPreparationPreview:
        preview = self._preparations.get(preparation_id)
        if preview is None:
            raise ModelControlNotFound(preparation_id)
        prior = self._confirmations.get(preparation_id)
        if prior is not None:
            if prior[0] != idempotency_key:
                raise ModelControlConflict(preview)
            return preview
        confirmed = preview.model_copy(update={"confirmed": True, "confirmed_at": datetime.now(UTC)})
        self._preparations[preparation_id] = confirmed
        self._confirmations[preparation_id] = (idempotency_key, preparation_id)
        return confirmed
