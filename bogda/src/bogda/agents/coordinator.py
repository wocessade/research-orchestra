from __future__ import annotations

from decimal import Decimal
from typing import Any, Mapping, Protocol

from bogda.agents.contracts import (
    AgentBudget,
    CoordinatorResult,
    ExperimentProposal,
    ResearchPlan,
)
from bogda.contracts import ScientificStatus
from bogda.contracts.decisions import CheckpointKind

TOOL_WRITE_PLAN = "write_plan"
TOOL_PROPOSE_EXPERIMENT = "propose_experiment"


def _money(value: Decimal | str | int) -> Decimal:
    if isinstance(value, float):
        raise ValueError("money values must not be floats")
    return value if isinstance(value, Decimal) else Decimal(str(value))


class ModelClient(Protocol):
    def complete(self, prompt: str) -> dict: ...


class UnknownTool(Exception):
    def __init__(self, tool: str | None):
        self.tool = tool
        super().__init__(f"unknown tool: {tool}")


class Coordinator:
    def __init__(
        self,
        budget: AgentBudget,
        allowed_tools: tuple[str, ...],
        model: ModelClient,
        cost_per_call: Decimal | str | int = Decimal("0.5"),
    ) -> None:
        self.budget = budget
        self.allowed_tools = allowed_tools
        self.model = model
        self.cost_per_call = _money(cost_per_call)
        self.steps_used = 0
        self.model_calls_used = 0
        self.cost_cny_used = Decimal("0")

    @property
    def exhausted(self) -> bool:
        return (
            self.steps_used >= self.budget.max_steps
            or self.model_calls_used >= self.budget.max_model_calls
            or self.cost_cny_used >= self.budget.max_cost_cny
        )

    def required_human_gates(
        self,
        plan: ResearchPlan | None,
        proposal: ExperimentProposal | None,
    ) -> tuple[CheckpointKind, ...]:
        gates: list[CheckpointKind] = []
        if plan is not None:
            gates.append(CheckpointKind.PLAN_APPROVAL)
        if proposal is not None:
            gates.append(CheckpointKind.EXPERIMENT_APPROVAL)
            gates.append(CheckpointKind.SCIENTIFIC_REVIEW)
        return tuple(gates)

    def scientific_status_from_model(self, payload: Mapping[str, Any]) -> ScientificStatus:
        return ScientificStatus.UNREVIEWED

    def draft_plan(self, goal: str) -> ResearchPlan:
        reply = self._complete(f"write a research plan for: {goal}")
        return self._require_plan(reply)

    def propose_experiment(self, plan: ResearchPlan) -> ExperimentProposal:
        reply = self._complete(f"propose an experiment for: {plan.goal}")
        return self._require_proposal(reply)

    def observe_results(self, prompt: str) -> ScientificStatus:
        reply = self._complete(prompt)
        return self.scientific_status_from_model(reply)

    def run(self, goal: str) -> CoordinatorResult:
        plan: ResearchPlan | None = None
        proposal: ExperimentProposal | None = None
        while True:
            if self.exhausted:
                return self._result(
                    "budget_exhausted",
                    CheckpointKind.EXPERIMENT_APPROVAL
                    if proposal is not None
                    else CheckpointKind.PLAN_APPROVAL,
                    plan,
                    proposal,
                )
            reply = self._complete(f"next action for: {goal}")
            tool = reply.get("tool")
            if tool not in self.allowed_tools:
                raise UnknownTool(tool)
            if tool == TOOL_WRITE_PLAN:
                plan = self._plan_from(reply)
                continue
            if tool == TOOL_PROPOSE_EXPERIMENT:
                proposal = self._proposal_from(reply)
                if proposal.experiment_type not in self.budget.allowed_experiment_types:
                    return self._result(
                        "disallowed_experiment",
                        CheckpointKind.EXPERIMENT_APPROVAL,
                        plan,
                        proposal,
                    )
                return self._result(
                    "awaiting_experiment_approval",
                    CheckpointKind.EXPERIMENT_APPROVAL,
                    plan,
                    proposal,
                )
            raise UnknownTool(tool)

    def _complete(self, prompt: str) -> dict:
        if self.exhausted:
            raise RuntimeError("budget exhausted")
        self.steps_used += 1
        self.model_calls_used += 1
        self.cost_cny_used += self.cost_per_call
        return self.model.complete(prompt)

    def _require_plan(self, reply: Mapping[str, Any]) -> ResearchPlan:
        tool = reply.get("tool")
        if tool != TOOL_WRITE_PLAN or tool not in self.allowed_tools:
            raise UnknownTool(tool)
        return self._plan_from(reply)

    def _require_proposal(self, reply: Mapping[str, Any]) -> ExperimentProposal:
        tool = reply.get("tool")
        if tool != TOOL_PROPOSE_EXPERIMENT or tool not in self.allowed_tools:
            raise UnknownTool(tool)
        return self._proposal_from(reply)

    def _plan_from(self, reply: Mapping[str, Any]) -> ResearchPlan:
        raw = reply["plan"]
        steps = raw["steps"]
        return ResearchPlan(
            goal=raw["goal"],
            steps=tuple(steps) if not isinstance(steps, str) else (steps,),
            rationale=raw["rationale"],
            sufficient=bool(raw.get("sufficient", False)),
        )

    def _proposal_from(self, reply: Mapping[str, Any]) -> ExperimentProposal:
        raw = reply["proposal"]
        artifacts = raw.get("expected_artifacts", ())
        return ExperimentProposal(
            experiment_type=raw["experiment_type"],
            description=raw["description"],
            expected_artifacts=tuple(artifacts)
            if not isinstance(artifacts, str)
            else (artifacts,),
            supports_conclusion=bool(raw.get("supports_conclusion", False)),
        )

    def _result(
        self,
        status: str,
        checkpoint: CheckpointKind | None,
        plan: ResearchPlan | None,
        proposal: ExperimentProposal | None,
    ) -> CoordinatorResult:
        return CoordinatorResult(
            status=status,
            checkpoint=checkpoint,
            scientific_status=ScientificStatus.UNREVIEWED,
            plan=plan,
            proposal=proposal,
            steps_used=self.steps_used,
            model_calls_used=self.model_calls_used,
            cost_cny_used=self.cost_cny_used,
        )
