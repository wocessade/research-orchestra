"""Map durable usage-unknown recovery onto the console decision port."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from bogda.model_runtime.recovery import (
    UsageUnknownCase,
    UsageUnknownConflictError,
    UsageUnknownNotFoundError,
    UsageUnknownRecoveryService,
    UsageUnknownRevisionConflictError,
    UsageUnknownState,
    UsageUnknownStateError,
)
from bogda_console.contracts.models import (
    BudgetState,
    DecisionAction,
    DecisionCenterSnapshot,
    DecisionItem,
    EvidenceReference,
    ModelBudgetSnapshot,
    UrgencyGroup,
)
from bogda_console.contracts.ports import (
    ModelControlConflict,
    ModelControlNotApplicable,
    ModelControlNotFound,
    ModelControlUnavailable,
)


class CoreUsageUnknownAdapter:
    """Real-profile transport for usage-unknown cases only."""

    source_mode = "real"

    def __init__(self, recovery: UsageUnknownRecoveryService) -> None:
        self._recovery = recovery

    def _snapshot(self) -> DecisionCenterSnapshot:
        cases = self._recovery.list_open_cases()
        items = tuple(self._item(case) for case in cases)
        revision = max((case.revision for case in cases), default=0)
        return DecisionCenterSnapshot(items=items, revision=revision)

    @staticmethod
    def _item(case: UsageUnknownCase) -> DecisionItem:
        if case.state is UsageUnknownState.AWAITING_RECONCILIATION:
            actions = (
                DecisionAction(
                    actionId="reconcile",
                    label="对账",
                    costImpact="No new call",
                    actualCostRequired=True,
                ),
            )
            reason = "The model call cost is unknown"
        else:
            actions = (
                DecisionAction(
                    actionId="approve-retry",
                    label="批准重试",
                    costImpact="New paid call",
                    newCallIdRequired=True,
                ),
                DecisionAction(
                    actionId="terminate",
                    label="终止",
                    costImpact="No new call",
                ),
            )
            reason = "Usage reconciled; owner must approve a new call id or terminate"
        return DecisionItem(
            decisionId=case.case_id,
            decisionKind="usage-unknown",
            title="Usage unknown",
            urgencyGroup=UrgencyGroup.NEEDS_OWNER_NOW,
            projectId="bogda-main",
            runId=case.run_id,
            reason=reason,
            risk="usage",
            estimatedCost=case.actual_cost_cny or Decimal("0"),
            actions=actions,
            revision=case.revision,
            logSummary=f"call {case.call_id} state {case.state.value}",
            evidence=(
                EvidenceReference(kind="run", refId=case.run_id, label="Run"),
            ),
        )

    async def decision_center(self) -> DecisionCenterSnapshot:
        return self._snapshot()

    async def run_budget(self, run_id: str) -> ModelBudgetSnapshot:
        cases = [
            case for case in self._recovery.list_open_cases() if case.run_id == run_id
        ]
        if not cases:
            raise ModelControlNotFound(run_id)
        case = cases[0]
        return ModelBudgetSnapshot(
            runId=run_id,
            projectId="bogda-main",
            state=BudgetState.USAGE_UNKNOWN,
            currency="CNY",
            expectedCost=Decimal("0"),
            authorizedCeiling=Decimal("0"),
            usedCost=case.actual_cost_cny or Decimal("0"),
            reservedCost=Decimal("0"),
            remainingCost=Decimal("0"),
            decisionId=case.case_id,
            revision=case.revision,
        )

    async def model_policy(self, project_id: str | None = None) -> Any:
        raise ModelControlUnavailable("real model-control policy is not wired")

    async def preview_run(self, *args: Any, **kwargs: Any) -> Any:
        raise ModelControlUnavailable("real run preparation is not wired")

    async def set_global_policy(self, *args: Any, **kwargs: Any) -> Any:
        raise ModelControlUnavailable("real model-control policy is not wired")

    async def set_project_policy(self, *args: Any, **kwargs: Any) -> Any:
        raise ModelControlUnavailable("real model-control policy is not wired")

    async def confirm_preparation(self, *args: Any, **kwargs: Any) -> Any:
        raise ModelControlUnavailable("real run preparation is not wired")

    async def resolve_decision(
        self,
        decision_id: str,
        action_id: str,
        expected_revision: int,
        rationale: str | None = None,
        *,
        actual_cost_cny: Decimal | None = None,
        new_call_id: str | None = None,
    ) -> DecisionCenterSnapshot:
        try:
            if action_id == "reconcile":
                if actual_cost_cny is None:
                    raise ModelControlNotApplicable("actual cost is required for this action")
                self._recovery.reconcile(
                    decision_id,
                    actual_cost_cny,
                    expected_revision=expected_revision,
                )
            elif action_id == "approve-retry":
                if not new_call_id:
                    raise ModelControlNotApplicable("new_call_id is required for this action")
                self._recovery.approve_retry(
                    decision_id,
                    new_call_id=new_call_id,
                    expected_revision=expected_revision,
                )
            elif action_id == "terminate":
                self._recovery.terminate(
                    decision_id, expected_revision=expected_revision
                )
            else:
                raise ModelControlNotApplicable("action is not valid for usage-unknown")
        except UsageUnknownNotFoundError as error:
            raise ModelControlNotFound(decision_id) from error
        except UsageUnknownRevisionConflictError as error:
            raise ModelControlConflict(self._snapshot()) from error
        except (UsageUnknownStateError, UsageUnknownConflictError) as error:
            raise ModelControlNotApplicable(str(error)) from error
        return self._snapshot()
