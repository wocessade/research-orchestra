import pytest

from bogda.contracts import (
    AutonomyMode,
    ExecutorKind,
    JobRequest,
    ModelTier,
    ResourceClass,
    RunBudgetEnvelope,
    TaskIntent,
)
from bogda.model_runtime import (
    LOW_RISK_FALLBACK_INTENTS,
    ModelRouter,
    RouteDecisionKind,
)


def budget(
    requested_tier: ModelTier,
    *,
    fallback_tier: ModelTier | None = ModelTier.FLASH,
) -> RunBudgetEnvelope:
    return RunBudgetEnvelope(
        expected_cost="2.880000",
        authorized_ceiling="5.320000",
        minimum_remaining="10.000000",
        requested_tier=requested_tier,
        fallback_tier=fallback_tier,
        budget_source="project",
        pricing_version="deepseek-cn-2026-08-28",
    )


def request(
    intent: TaskIntent,
    *,
    model_tier: ModelTier = ModelTier.PRO,
    frozen_tier: ModelTier | None = None,
    fallback_tier: ModelTier | None = ModelTier.FLASH,
    with_budget: bool = True,
) -> JobRequest:
    return JobRequest(
        job_id="job-1",
        project_id="project-1",
        task_type="research",
        resource_class=ResourceClass.CPU,
        autonomy_mode=AutonomyMode.SUPERVISED,
        intent=intent,
        model_tier=model_tier,
        executor=ExecutorKind.DSH if with_budget else ExecutorKind.SHELL,
        budget=(
            budget(frozen_tier or model_tier, fallback_tier=fallback_tier)
            if with_budget
            else None
        ),
    )


@pytest.mark.parametrize("intent", [TaskIntent.DECIDE, TaskIntent.AUDIT])
def test_pro_unavailable_never_silently_downgrades_high_risk_intent(intent):
    decision = ModelRouter().select(
        request(intent), pro_available=False, allow_low_risk_fallback=True
    )

    assert decision.kind is RouteDecisionKind.PRO_REQUIRED
    assert decision.requested_tier is ModelTier.PRO
    assert decision.effective_tier is None


@pytest.mark.parametrize(
    "intent", [TaskIntent.EXECUTE, TaskIntent.BRIEF, TaskIntent.EXPLORE]
)
def test_low_risk_pro_can_use_explicit_frozen_flash_fallback(intent):
    decision = ModelRouter().select(
        request(intent, fallback_tier=ModelTier.FLASH),
        pro_available=False,
        allow_low_risk_fallback=True,
    )

    assert decision.kind is RouteDecisionKind.DOWNGRADED
    assert decision.requested_tier is ModelTier.PRO
    assert decision.effective_tier is ModelTier.FLASH


@pytest.mark.parametrize("intent", list(TaskIntent))
def test_explicit_flash_is_a_human_lock_for_every_intent(intent):
    decision = ModelRouter().select(
        request(intent, model_tier=ModelTier.FLASH),
        pro_available=False,
        allow_low_risk_fallback=False,
    )

    assert decision.kind is RouteDecisionKind.SELECTED
    assert decision.requested_tier is ModelTier.FLASH
    assert decision.effective_tier is ModelTier.FLASH


def test_available_pro_selects_pro():
    decision = ModelRouter().select(
        request(TaskIntent.DECIDE),
        pro_available=True,
        allow_low_risk_fallback=False,
    )

    assert decision.kind is RouteDecisionKind.SELECTED
    assert decision.effective_tier is ModelTier.PRO


@pytest.mark.parametrize(
    "intent", [TaskIntent.EXECUTE, TaskIntent.BRIEF, TaskIntent.EXPLORE]
)
def test_low_risk_pro_requires_pro_when_fallback_is_disabled(intent):
    decision = ModelRouter().select(
        request(intent), pro_available=False, allow_low_risk_fallback=False
    )

    assert decision.kind is RouteDecisionKind.PRO_REQUIRED
    assert decision.effective_tier is None


def test_paid_routing_requires_a_budget_envelope():
    request_without_budget = request(
        TaskIntent.EXECUTE, model_tier=ModelTier.AUTO, with_budget=False
    )

    with pytest.raises(ValueError, match="requires a budget envelope"):
        ModelRouter().select(
            request_without_budget,
            pro_available=True,
            allow_low_risk_fallback=True,
        )


@pytest.mark.parametrize("frozen_tier", [ModelTier.FLASH, ModelTier.PRO])
def test_auto_follows_the_concrete_tier_frozen_in_the_envelope(frozen_tier):
    decision = ModelRouter().select(
        request(
            TaskIntent.EXECUTE,
            model_tier=ModelTier.AUTO,
            frozen_tier=frozen_tier,
        ),
        pro_available=frozen_tier is ModelTier.PRO,
        allow_low_risk_fallback=False,
    )

    assert decision.kind is RouteDecisionKind.SELECTED
    assert decision.requested_tier is frozen_tier
    assert decision.effective_tier is frozen_tier


@pytest.mark.parametrize("intent", [TaskIntent.DECIDE, TaskIntent.AUDIT])
def test_auto_high_risk_rejects_a_frozen_flash_envelope(intent):
    with pytest.raises(ValueError, match="AUTO.*Flash"):
        ModelRouter().select(
            request(
                intent,
                model_tier=ModelTier.AUTO,
                frozen_tier=ModelTier.FLASH,
            ),
            pro_available=False,
            allow_low_risk_fallback=True,
        )


def test_low_risk_fallback_intents_are_centralized():
    assert LOW_RISK_FALLBACK_INTENTS == frozenset(
        {TaskIntent.EXECUTE, TaskIntent.BRIEF, TaskIntent.EXPLORE}
    )
