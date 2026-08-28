from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from bogda_console.adapters.mock_model_control import MockModelControlAdapter
from bogda_console.adapters.unwired_model_control import UnwiredModelControlAdapter
from bogda_console.contracts.models import (
    BudgetState,
    AllowedRunPreferences,
    DecisionAction,
    DecisionCenterSnapshot,
    DecisionItem,
    DecisionKind,
    EvidenceReference,
    ModelBudgetSnapshot,
    ModelArtifactReference,
    ModelEventRow,
    ModelPolicyPatch,
    ModelPolicySnapshot,
    PriceCatalog,
    RunPreparationPreview,
    WorkloadEstimate,
)
from bogda_console.contracts.ports import (
    ModelControlConflict,
    ModelControlNotFound,
    ModelControlUnavailable,
)


DEADLINE = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)


def test_wire_models_are_closed_camel_case_and_money_is_a_json_string() -> None:
    item = DecisionItem(
        decisionId="decision-1",
        decisionKind="peak-override",
        title="Peak run",
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
    assert len(center.items) >= 1
    assert budget.decision_id == next(item for item in center.items if item.run_id == "run-1").decision_id
    assert budget.decision_id is not None
    assert not hasattr(budget, "decision")


@pytest.mark.asyncio
async def test_stale_revision_conflict_returns_current_authoritative_resource() -> None:
    adapter = MockModelControlAdapter()
    current = await adapter.model_policy()
    await adapter.set_global_policy(ModelPolicyPatch(defaultModelTier="flash"), expected_revision=0)

    with pytest.raises(ModelControlConflict) as caught:
        await adapter.set_global_policy(ModelPolicyPatch(defaultModelTier="pro"), expected_revision=0)

    assert caught.value.current == await adapter.model_policy()
    assert caught.value.current.revision == current.revision + 1


@pytest.mark.asyncio
async def test_policy_override_exposes_source_revision_and_restore_inheritance() -> None:
    adapter = MockModelControlAdapter()
    overridden = await adapter.set_project_policy(
        "project-1", ModelPolicyPatch(defaultModelTier="pro"), expected_revision=0
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
async def test_policy_patch_changes_authoritative_value_and_preserves_inherited_project_id() -> None:
    adapter = MockModelControlAdapter()
    updated = await adapter.set_global_policy(
        ModelPolicyPatch(defaultModelTier="flash"), expected_revision=0
    )
    assert updated.default_model_tier == "flash"
    inherited = await adapter.model_policy("project-2")
    assert inherited.project_id == "project-2"
    assert inherited.source == "global"

    with pytest.raises(ValidationError):
        ModelPolicyPatch.model_validate({"surprise": True})
    with pytest.raises(ValidationError):
        ModelPolicyPatch.model_validate({"defaultModelTier": None})
    with pytest.raises(ValidationError):
        ModelPolicyPatch()


@pytest.mark.asyncio
async def test_preview_confirmation_is_opaque_and_idempotent() -> None:
    adapter = MockModelControlAdapter()
    preview = await adapter.preview_run(
        "project-1", "explore", "auto",
        WorkloadEstimate(inputTokens=1, outputTokens=1, expectedCalls=1, runtimeMinutes=1),
        AllowedRunPreferences(preferOffPeak=True, allowAutoUpgrade=True, allowFlashDowngrade=True, autoResume=True),
        DEADLINE,
    )
    first = await adapter.confirm_preparation(preview.preparation_id, "idem-1")
    second = await adapter.confirm_preparation(preview.preparation_id, "idem-1")
    assert first == second
    assert preview.preparation_id.startswith("prep_")
    with pytest.raises(ModelControlConflict):
        await adapter.confirm_preparation(preview.preparation_id, "different-idem")


def test_decision_kinds_actions_and_budget_operational_fields_are_typed() -> None:
    item = DecisionItem(
        decisionId="d1", decisionKind=DecisionKind.PEAK_OVERRIDE, title="Peak run",
        urgencyGroup="has-deadline", projectId="p1", reason="Deadline is near", risk="cost",
        estimatedCost=Decimal("1"), actions=[DecisionAction(
            actionId="run", label="Run now", costImpact="Higher", qualityImpact="None",
            irreversibleConsequence="Consumes budget", requiresRationale=True,
        )], revision=0, logSummary="Log it.",
    )
    assert item.decision_kind == DecisionKind.PEAK_OVERRIDE.value
    assert item.title == "Peak run"
    assert item.actions[0].requires_rationale is True

    budget = ModelBudgetSnapshot(
        runId="r1", projectId="p1", state="scheduled-off-peak", currency="CNY",
        expectedCost=Decimal("1"), authorizedCeiling=Decimal("2"), usedCost=Decimal("0"),
        reservedCost=Decimal("0"), remainingCost=Decimal("2"), decisionId="d1", revision=0,
        intent="explore", requestedModelTier="pro", effectiveModelTier="flash",
        effectiveAutonomyMode="supervised", pricePeriod="off-peak",
        scheduledStart=DEADLINE, recoveryConditions=("wait-for-balance",),
        events=(ModelEventRow(eventId="e1", eventType="budget_paused", occurredAt=DEADLINE),),
        artifacts=(ModelArtifactReference(artifactId="a1", kind="log", uri="artifact://a1"),),
    )
    assert budget.events[0].event_type == "budget_paused"
    assert "prompt" not in budget.events[0].model_dump()
    unavailable = RunPreparationPreview.model_validate(
        {"preparation_id": "p1", "project_id": "p1", "intent": "decide",
         "requested_model_tier": "pro", "effective_model_tier": None, "fallback_model_tier": None,
         "effective_autonomy_mode": "supervised", "price_period": "off-peak",
         "workload": {"input_tokens": 1, "output_tokens": 1, "expected_calls": 1, "runtime_minutes": 1},
         "allowed_preferences": {"prefer_off_peak": True, "allow_auto_upgrade": False,
                                  "allow_flash_downgrade": False, "auto_resume": False},
         "budget": budget, "policy_revision": 0}
    )
    assert unavailable.effective_model_tier is None
    assert unavailable.fallback_model_tier is None
    assert ModelEventRow(eventId="e2", eventType="model_call_usage_unknown", occurredAt=DEADLINE)


@pytest.mark.asyncio
async def test_unknown_run_is_not_fabricated_and_usage_unknown_has_canonical_decision() -> None:
    adapter = MockModelControlAdapter()
    with pytest.raises(ModelControlNotFound):
        await adapter.run_budget("missing")
    budget = await adapter.run_budget("run-unknown-usage")
    center = await adapter.decision_center()
    assert budget.state == "usage-unknown"
    assert budget.decision_id in {item.decision_id for item in center.items}


def test_policy_and_preview_include_safety_catalog_workload_and_preference_fields() -> None:
    policy = ModelPolicySnapshot(
        projectId="p1", source="global", inheritsGlobal=True, defaultModelTier="auto",
        allowAutoUpgrade=True, allowFlashDowngrade=True, preferOffPeak=True, autoResume=True,
        minimumRemaining=Decimal("10"), workloadSafetyMargin=Decimal("1.2"), criticalNotifications=True,
        usageSnapshotStaleAfterSeconds=120,
        priceCatalog=PriceCatalog(status="ready", version="v1", source="official",
                                   effectiveAt=DEADLINE, reviewBy=DEADLINE), revision=0,
    )
    assert policy.hard_safety_baselines.minimum_remaining_enforced is True
    with pytest.raises(ValidationError):
        ModelPolicySnapshot.model_validate({**policy.model_dump(), "hardSafetyBaselines": {"x": True}})

@pytest.mark.asyncio
async def test_preview_contains_frozen_autonomy_workload_schedule_and_allowed_preferences() -> None:
    adapter = MockModelControlAdapter()
    workload = WorkloadEstimate(inputTokens=321, outputTokens=654, expectedCalls=7, runtimeMinutes=19)
    preferences = AllowedRunPreferences(
        preferOffPeak=False, allowAutoUpgrade=False, allowFlashDowngrade=True, autoResume=False
    )
    preview = await adapter.preview_run(
        "project-1", "explore", "pro", workload=workload, allowed_preferences=preferences, deadline=DEADLINE
    )
    assert preview.effective_autonomy_mode == "supervised"
    assert preview.fallback_model_tier == "flash"
    assert preview.price_period in {"peak", "off-peak"}
    assert preview.workload.expected_calls >= 1
    assert preview.workload == workload
    assert preview.allowed_preferences == preferences
    assert preview.scheduled_start is None


def test_budget_can_preserve_unavailable_effective_tier() -> None:
    budget = ModelBudgetSnapshot(
        runId="blocked-1", projectId="p1", state="awaiting-approval", currency="CNY",
        expectedCost=Decimal("1"), authorizedCeiling=Decimal("2"), usedCost=Decimal("0"),
        reservedCost=Decimal("0"), remainingCost=Decimal("2"), decisionId="d1", revision=0,
        intent="decide", requestedModelTier="pro", effectiveModelTier=None,
        effectiveAutonomyMode="supervised", pricePeriod="off-peak",
    )
    assert budget.effective_model_tier is None


def test_budget_omitted_effective_tier_is_unknown_not_fabricated_flash() -> None:
    budget = ModelBudgetSnapshot(
        runId="omitted-1", projectId="p1", state="awaiting-approval", currency="CNY",
        expectedCost=Decimal("1"), authorizedCeiling=Decimal("2"), usedCost=Decimal("0"),
        reservedCost=Decimal("0"), remainingCost=Decimal("2"), decisionId="d1", revision=0,
    )
    assert budget.effective_model_tier is None


@pytest.mark.asyncio
async def test_mock_fallback_requires_pro_and_explicit_flash_downgrade() -> None:
    adapter = MockModelControlAdapter()
    workload = WorkloadEstimate(inputTokens=1, outputTokens=1, expectedCalls=1, runtimeMinutes=1)
    no_downgrade = AllowedRunPreferences(
        preferOffPeak=True, allowAutoUpgrade=True, allowFlashDowngrade=False, autoResume=True
    )
    blocked = await adapter.preview_run("p1", "decide", "pro", workload, no_downgrade)
    assert blocked.effective_model_tier == "pro"
    assert blocked.fallback_model_tier is None

    flash = await adapter.preview_run("p1", "explore", "flash", workload, no_downgrade)
    assert flash.effective_model_tier == "flash"
    assert flash.fallback_model_tier is None


def test_workload_safety_margin_cannot_underbudget() -> None:
    with pytest.raises(ValidationError):
        ModelPolicySnapshot(
            projectId="p1", source="global", inheritsGlobal=True, defaultModelTier="auto",
            allowAutoUpgrade=True, allowFlashDowngrade=True, preferOffPeak=True, autoResume=True,
            minimumRemaining=Decimal("10"), workloadSafetyMargin=Decimal("0.99"), criticalNotifications=True,
            priceCatalog=PriceCatalog(status="ready"), revision=0,
        )


@pytest.mark.asyncio
async def test_unwired_adapter_never_fabricates_data() -> None:
    adapter = UnwiredModelControlAdapter()
    with pytest.raises(ModelControlUnavailable):
        await adapter.decision_center()
    with pytest.raises(ModelControlUnavailable):
        await adapter.set_global_policy({}, expected_revision=0)
