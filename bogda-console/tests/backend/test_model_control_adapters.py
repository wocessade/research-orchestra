from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from bogda_console.adapters.mock_model_control import MockModelControlAdapter
from bogda_console.adapters.unwired_model_control import UnwiredModelControlAdapter
from bogda_console.contracts.models import (
    BudgetState,
    DecisionAction,
    DecisionCenterSnapshot,
    DecisionItem,
    EvidenceReference,
    ModelBudgetSnapshot,
    ModelPolicySnapshot,
)
from bogda_console.contracts.ports import (
    ModelControlConflict,
    ModelControlUnavailable,
)


DEADLINE = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def test_wire_models_are_closed_camel_case_and_money_is_a_json_string() -> None:
    item = DecisionItem(
        decisionId="decision-1",
        urgencyGroup="needs-owner-now",
        projectId="project-1",
        runId="run-1",
        reason="Pro requires approval",
        risk="quality",
        estimatedCost=Decimal("1.2300"),
        deadline=DEADLINE,
        evidence=[EvidenceReference(kind="run", refId="run-1", label="Run")],
        actions=[DecisionAction(actionId="approve", label="Approve", costImpact="Uses budget")],
        revision=3,
        logSummary="Owner approval required.",
    )

    payload = item.model_dump(by_alias=True, mode="json")
    assert payload["decisionId"] == "decision-1"
    assert payload["estimatedCost"] == "1.2300"
    assert payload["deadline"].endswith("Z")
    with pytest.raises(ValidationError):
        DecisionItem.model_validate({**payload, "unknownField": True})


@pytest.mark.parametrize("state", list(BudgetState))
def test_budget_states_are_distinct(state: BudgetState) -> None:
    snapshot = ModelBudgetSnapshot(
        runId="run-1",
        projectId="project-1",
        state=state,
        currency="CNY",
        expectedCost=Decimal("1.00"),
        authorizedCeiling=Decimal("2.00"),
        usedCost=Decimal("0"),
        reservedCost=Decimal("1.00"),
        remainingCost=Decimal("1.00"),
        decisionId="decision-1",
        revision=1,
    )
    assert snapshot.state == state.value


@pytest.mark.asyncio
async def test_mock_has_one_pending_item_and_run_budget_references_it() -> None:
    adapter = MockModelControlAdapter()
    center = await adapter.decision_center()
    budget = await adapter.run_budget("run-1")

    assert isinstance(center, DecisionCenterSnapshot)
    assert len(center.items) == 1
    assert budget.decision_id == center.items[0].decision_id
    assert budget.decision_id is not None
    assert not hasattr(budget, "decision")


@pytest.mark.asyncio
async def test_stale_revision_conflict_returns_current_authoritative_resource() -> None:
    adapter = MockModelControlAdapter()
    current = await adapter.model_policy()
    await adapter.set_global_policy({"defaultModelTier": "flash"}, expected_revision=0)

    with pytest.raises(ModelControlConflict) as caught:
        await adapter.set_global_policy({"defaultModelTier": "pro"}, expected_revision=0)

    assert caught.value.current == await adapter.model_policy()
    assert caught.value.current.revision == current.revision + 1


@pytest.mark.asyncio
async def test_policy_override_exposes_source_revision_and_restore_inheritance() -> None:
    adapter = MockModelControlAdapter()
    overridden = await adapter.set_project_policy(
        "project-1", {"defaultModelTier": "pro"}, expected_revision=0
    )
    project_policy = await adapter.model_policy("project-1")
    assert isinstance(project_policy, ModelPolicySnapshot)
    assert project_policy.source == "project"
    assert project_policy.revision == overridden.revision
    assert project_policy.inherits_global is False

    restored = await adapter.set_project_policy(
        "project-1", None, expected_revision=overridden.revision
    )
    inherited = await adapter.model_policy("project-1")
    assert restored.revision == inherited.revision
    assert inherited.source == "global"
    assert inherited.inherits_global is True


@pytest.mark.asyncio
async def test_preview_confirmation_is_opaque_and_idempotent() -> None:
    adapter = MockModelControlAdapter()
    preview = await adapter.preview_run("project-1", "explore", "auto", DEADLINE)
    first = await adapter.confirm_preparation(preview.preparation_id, "idem-1")
    second = await adapter.confirm_preparation(preview.preparation_id, "idem-1")
    assert first == second
    assert preview.preparation_id.startswith("prep_")
    with pytest.raises(ModelControlConflict):
        await adapter.confirm_preparation(preview.preparation_id, "different-idem")


@pytest.mark.asyncio
async def test_unwired_adapter_never_fabricates_data() -> None:
    adapter = UnwiredModelControlAdapter()
    with pytest.raises(ModelControlUnavailable):
        await adapter.decision_center()
    with pytest.raises(ModelControlUnavailable):
        await adapter.set_global_policy({}, expected_revision=0)
