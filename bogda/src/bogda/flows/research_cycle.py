from __future__ import annotations

from pathlib import Path
from typing import Any, Self
from uuid import UUID

from prefect import flow
from prefect.artifacts import Artifact
from prefect.context import get_run_context
from prefect.states import Cancelled
from pydantic import BaseModel, ConfigDict, Field, model_validator

from bogda.agents.contracts import AgentBudget, ExperimentProposal, ResearchPlan
from bogda.agents.coordinator import (
    TOOL_PROPOSE_EXPERIMENT,
    TOOL_WRITE_PLAN,
    Coordinator,
)
from bogda.artifacts import save_run_result
from bogda.contracts import (
    ArtifactSpec,
    AutonomyMode,
    ExecutorKind,
    ExecutionStatus,
    JobRequest,
    ResourceClass,
    ScientificStatus,
)
from bogda.contracts.decisions import CheckpointKind
from bogda.executors import run_shell
from bogda.flows.research_checkpoint import (
    CheckpointRejected,
    required_checkpoints,
    wait_for_decision,
)

PLAN_TYPE = "bogda.research-plan"
PROPOSAL_TYPE = "bogda.experiment-proposal"


def plan_key(run_id: str) -> str:
    return f"bogda-plan-{UUID(run_id)}"


def proposal_key(run_id: str) -> str:
    return f"bogda-proposal-{UUID(run_id)}"


def save_plan(run_id: str, plan: ResearchPlan) -> None:
    Artifact(
        key=plan_key(run_id),
        type=PLAN_TYPE,
        description=f"Bogda research plan for {run_id}",
        data=plan.model_dump(mode="json"),
        flow_run_id=UUID(run_id),
    ).create()


def save_proposal(run_id: str, proposal: ExperimentProposal) -> None:
    Artifact(
        key=proposal_key(run_id),
        type=PROPOSAL_TYPE,
        description=f"Bogda experiment proposal for {run_id}",
        data=proposal.model_dump(mode="json"),
        flow_run_id=UUID(run_id),
    ).create()


class ResearchCycleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_request: JobRequest
    goal: str = Field(min_length=1)
    coordinator_budget: AgentBudget
    allowed_tools: tuple[str, ...] = (
        TOOL_WRITE_PLAN,
        TOOL_PROPOSE_EXPERIMENT,
    )

    @model_validator(mode="after")
    def validate_executor(self) -> Self:
        if self.job_request.executor is not ExecutorKind.SHELL:
            raise ValueError("research cycle requires executor=shell")
        return self


class LegacyResearchCycleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    project_id: str
    goal: str = Field(min_length=1)
    autonomy_mode: AutonomyMode
    budget: AgentBudget
    allowed_tools: tuple[str, ...] = (
        TOOL_WRITE_PLAN,
        TOOL_PROPOSE_EXPERIMENT,
    )
    parameters: dict[str, Any] = Field(default_factory=dict)
    expected_artifacts: tuple[ArtifactSpec, ...] = ()

    def to_current(self) -> ResearchCycleInput:
        return ResearchCycleInput(
            job_request=JobRequest(
                job_id=self.job_id,
                project_id=self.project_id,
                task_type="research-cycle",
                resource_class=ResourceClass.CPU,
                autonomy_mode=self.autonomy_mode,
                parameters=self.parameters,
                expected_artifacts=self.expected_artifacts,
            ),
            goal=self.goal,
            coordinator_budget=self.budget,
            allowed_tools=self.allowed_tools,
        )


def cycle_request_from(payload: dict[str, Any]) -> ResearchCycleInput:
    if "job_request" in payload:
        return ResearchCycleInput.model_validate(payload)
    return LegacyResearchCycleInput.model_validate(payload).to_current()


def _pause(run_id: str, kind: CheckpointKind, mode: AutonomyMode) -> None:
    if kind in required_checkpoints(mode):
        wait_for_decision(run_id, kind)


def _payload(
    status: str,
    execution_status: ExecutionStatus | None = None,
) -> dict[str, Any]:
    data = {
        "status": status,
        "scientific_status": ScientificStatus.UNREVIEWED.value,
    }
    if execution_status is not None:
        data["execution_status"] = execution_status.value
    return data


@flow(name="bogda-research-cycle")
def run_research_cycle(
    request: dict[str, Any],
    attempts_root: str,
    model: Any,
) -> dict[str, Any]:
    cycle = cycle_request_from(request)
    parsed = cycle.job_request
    run_id = str(get_run_context().flow_run.id)
    coordinator = Coordinator(
        budget=cycle.coordinator_budget,
        allowed_tools=cycle.allowed_tools,
        model=model,
    )
    try:
        plan = coordinator.draft_plan(cycle.goal)
        save_plan(run_id, plan)
        _pause(run_id, CheckpointKind.PLAN_APPROVAL, parsed.autonomy_mode)
        if coordinator.exhausted:
            return _payload("budget_exhausted")

        proposal = coordinator.propose_experiment(plan)
        save_proposal(run_id, proposal)
        _pause(run_id, CheckpointKind.EXPERIMENT_APPROVAL, parsed.autonomy_mode)
        if proposal.experiment_type not in cycle.coordinator_budget.allowed_experiment_types:
            return _payload("disallowed_experiment")

        result = run_shell(parsed, Path(attempts_root), run_id)
        save_run_result(result)
        if result.execution_status is not ExecutionStatus.COMPLETED:
            status = (
                "missing_artifacts"
                if "missing" in result.summary
                else "failed"
            )
            return _payload(status, result.execution_status)

        coordinator.observe_results(f"summarize results for {parsed.job_id}")
        _pause(run_id, CheckpointKind.SCIENTIFIC_REVIEW, parsed.autonomy_mode)
        return _payload("awaiting_scientific_review", result.execution_status)
    except CheckpointRejected as error:
        return Cancelled(message=f"{error.decision.kind} rejected")
