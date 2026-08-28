from decimal import Decimal

import pytest
from pydantic import ValidationError

from bogda.agents.contracts import (
    AgentBudget,
    CoordinatorResult,
    ExperimentProposal,
    ResearchPlan,
)
from bogda.agents.coordinator import (
    Coordinator,
    TOOL_PROPOSE_EXPERIMENT,
    TOOL_WRITE_PLAN,
    UnknownTool,
)
from bogda.contracts import ScientificStatus
from bogda.contracts.decisions import CheckpointKind


class ScriptedModel:
    def __init__(self, replies: list[dict]):
        self.replies = list(replies)
        self.calls = 0

    def complete(self, prompt: str) -> dict:
        self.calls += 1
        if not self.replies:
            raise AssertionError(f"unexpected model call: {prompt}")
        return self.replies.pop(0)


def make_coordinator(model: ScriptedModel, **budget_fields) -> Coordinator:
    budget = AgentBudget(
        max_steps=budget_fields.get("max_steps", 8),
        max_model_calls=budget_fields.get("max_model_calls", 8),
        max_cost_cny=budget_fields.get("max_cost_cny", "10.0"),
        allowed_experiment_types=("shell",),
    )
    return Coordinator(
        budget=budget,
        allowed_tools=(TOOL_WRITE_PLAN, TOOL_PROPOSE_EXPERIMENT),
        model=model,
        cost_per_call=budget_fields.get("cost_per_call", "0.5"),
    )


def test_budget_exhaustion_stops_for_a_human_checkpoint() -> None:
    model = ScriptedModel(
        [
            {
                "tool": TOOL_WRITE_PLAN,
                "plan": {
                    "goal": "measure ridge",
                    "steps": ["draft"],
                    "rationale": "first pass",
                    "sufficient": True,
                },
            }
        ]
    )
    result = make_coordinator(model, max_steps=1, max_model_calls=1).run("measure ridge")

    assert result.status == "budget_exhausted"
    assert result.checkpoint is CheckpointKind.PLAN_APPROVAL
    assert result.scientific_status is ScientificStatus.UNREVIEWED
    assert result.plan is not None


def test_unknown_tool_is_rejected_without_acquitting() -> None:
    model = ScriptedModel([{"tool": "purchase", "item": "gpu"}])
    with pytest.raises(UnknownTool) as raised:
        make_coordinator(model).run("buy hardware")
    assert raised.value.tool == "purchase"


def test_disallowed_experiment_type_does_not_execute() -> None:
    model = ScriptedModel(
        [
            {
                "tool": TOOL_WRITE_PLAN,
                "plan": {
                    "goal": "measure ridge",
                    "steps": ["run gpu job"],
                    "rationale": "needs gpu",
                },
            },
            {
                "tool": TOOL_PROPOSE_EXPERIMENT,
                "proposal": {
                    "experiment_type": "gpu",
                    "description": "train a net",
                    "expected_artifacts": ["weights.bin"],
                    "supports_conclusion": True,
                },
            },
        ]
    )
    result = make_coordinator(model).run("measure ridge")
    assert result.status == "disallowed_experiment"
    assert result.checkpoint is CheckpointKind.EXPERIMENT_APPROVAL
    assert result.scientific_status is ScientificStatus.UNREVIEWED
    assert result.proposal is not None
    assert result.proposal.experiment_type == "gpu"


def test_model_claiming_plan_is_enough_still_requires_plan_approval() -> None:
    model = ScriptedModel(
        [
            {
                "tool": TOOL_WRITE_PLAN,
                "plan": {
                    "goal": "measure ridge",
                    "steps": ["done already"],
                    "rationale": "计划已足够",
                    "sufficient": True,
                },
            }
        ]
    )
    brain = make_coordinator(model)
    plan = brain.draft_plan("measure ridge")
    assert isinstance(plan, ResearchPlan)
    assert plan.sufficient is True
    assert CheckpointKind.PLAN_APPROVAL in brain.required_human_gates(plan, None)


def test_model_claiming_results_support_conclusion_cannot_set_accepted() -> None:
    proposal = ExperimentProposal(
        experiment_type="shell",
        description="python -V",
        expected_artifacts=("version.txt",),
        supports_conclusion=True,
    )
    brain = make_coordinator(ScriptedModel([]))
    status = brain.scientific_status_from_model(
        {"scientific_status": "accepted", "summary": "结果支持结论"}
    )
    assert status is ScientificStatus.UNREVIEWED
    assert CheckpointKind.SCIENTIFIC_REVIEW in brain.required_human_gates(
        ResearchPlan(goal="g", steps=("s",), rationale="r"),
        proposal,
    )


def test_agent_cost_accounting_uses_decimal() -> None:
    model = ScriptedModel(
        [
            {
                "tool": TOOL_WRITE_PLAN,
                "plan": {"goal": "g", "steps": ["s"], "rationale": "r"},
            }
        ]
    )
    result = make_coordinator(
        model,
        max_steps=1,
        max_model_calls=1,
        max_cost_cny="0.30",
        cost_per_call="0.10",
    ).run("g")
    assert result.cost_cny_used == Decimal("0.10")
    assert isinstance(result.cost_cny_used, Decimal)


def test_public_money_boundaries_reject_float_input() -> None:
    with pytest.raises(ValidationError, match="money values must not be floats"):
        AgentBudget(max_steps=1, max_model_calls=1, max_cost_cny=0.1)
    with pytest.raises(ValidationError, match="money values must not be floats"):
        CoordinatorResult(cost_cny_used=0.1)
    with pytest.raises(ValueError, match="money values must not be floats"):
        Coordinator(
            budget=AgentBudget(max_steps=1, max_model_calls=1, max_cost_cny="1"),
            allowed_tools=(TOOL_WRITE_PLAN,),
            model=ScriptedModel([]),
            cost_per_call=0.1,
        )
