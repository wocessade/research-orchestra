from pathlib import Path
from types import SimpleNamespace

import pytest
from prefect.states import StateType

from bogda.agents.contracts import AgentBudget
from bogda.agents.coordinator import TOOL_PROPOSE_EXPERIMENT, TOOL_WRITE_PLAN
from bogda.contracts import (
    AutonomyMode,
    ExecutionStatus,
    ExecutorKind,
    ModelTier,
    ScientificStatus,
    TaskIntent,
)
from bogda.contracts.decisions import (
    CheckpointKind,
    DecisionVerdict,
    ResearchDecision,
    StageStatus,
)
from bogda.flows import research_cycle
from bogda.flows.research_checkpoint import CheckpointRejected
from bogda.flows.shell_job import JobExecutionError


RUN_ID = "36c86e99-d0a1-4399-a30c-4d6c5044444c"


class ScriptedModel:
    def __init__(self, replies: list[dict]):
        self.replies = list(replies)

    def complete(self, prompt: str) -> dict:
        if not self.replies:
            raise AssertionError(f"unexpected model call: {prompt}")
        return self.replies.pop(0)


def cycle_request(tmp_path: Path, argv: list[str], artifacts: tuple[str, ...] = ("result.txt",)) -> dict:
    return {
        "job_request": {
            "job_id": "cycle-1",
            "project_id": "bogda",
            "task_type": "research-cycle",
            "resource_class": "cpu",
            "autonomy_mode": AutonomyMode.SUPERVISED.value,
            "policy_revision": 7,
            "intent": "audit",
            "model_tier": "auto",
            "executor": "shell",
            "schedule_policy": {
                "earliest_start": "2026-08-28T20:00:00+08:00"
            },
            "parameters": {"argv": argv},
            "expected_artifacts": [{"path": path} for path in artifacts],
        },
        "goal": "measure ridge",
        "coordinator_budget": AgentBudget(
            max_steps=8,
            max_model_calls=8,
            max_cost_cny="10.0",
            allowed_experiment_types=("shell",),
        ).model_dump(mode="json"),
        "allowed_tools": [TOOL_WRITE_PLAN, TOOL_PROPOSE_EXPERIMENT],
    }


def test_cycle_input_preserves_canonical_job_request_axes(tmp_path) -> None:
    parsed = research_cycle.cycle_request_from(
        cycle_request(tmp_path, ["python", "-V"])
    )

    assert parsed.job_request.policy_revision == 7
    assert parsed.job_request.intent is TaskIntent.AUDIT
    assert parsed.job_request.model_tier is ModelTier.AUTO
    assert parsed.job_request.executor is ExecutorKind.SHELL
    assert parsed.job_request.schedule_policy.earliest_start is not None
    assert parsed.coordinator_budget.max_cost_cny == AgentBudget(
        max_steps=8,
        max_model_calls=8,
        max_cost_cny="10.0",
        allowed_experiment_types=("shell",),
    ).max_cost_cny


def test_cycle_input_adapts_legacy_flat_payload_with_conservative_axes(tmp_path) -> None:
    current = cycle_request(tmp_path, ["python", "-V"])
    job = current["job_request"]
    legacy = {
        "job_id": job["job_id"],
        "project_id": job["project_id"],
        "goal": current["goal"],
        "autonomy_mode": job["autonomy_mode"],
        "budget": current["coordinator_budget"],
        "allowed_tools": current["allowed_tools"],
        "parameters": job["parameters"],
        "expected_artifacts": job["expected_artifacts"],
    }

    parsed = research_cycle.cycle_request_from(legacy)

    assert parsed.job_request.job_id == "cycle-1"
    assert parsed.job_request.intent is TaskIntent.EXECUTE
    assert parsed.job_request.model_tier is ModelTier.AUTO
    assert parsed.job_request.executor is ExecutorKind.SHELL
    assert parsed.job_request.policy_revision == 0
    assert parsed.coordinator_budget.max_steps == 8


def test_cycle_input_rejects_dsh_before_coordinator_work(tmp_path) -> None:
    payload = cycle_request(tmp_path, ["python", "-V"])
    payload["job_request"].update(
        {
            "executor": "dsh",
            "model_tier": "pro",
            "budget": {
                "expected_cost": "1",
                "authorized_ceiling": "2",
                "minimum_remaining": "10",
                "requested_tier": "pro",
                "fallback_tier": "flash",
                "budget_source": "project",
                "pricing_version": "deepseek-cn-2026-08-28",
            },
        }
    )

    with pytest.raises(ValueError, match="research cycle requires executor=shell"):
        research_cycle.cycle_request_from(payload)


def cooperating_model() -> ScriptedModel:
    return ScriptedModel(
        [
            {
                "tool": TOOL_WRITE_PLAN,
                "plan": {
                    "goal": "measure ridge",
                    "steps": ["run python"],
                    "rationale": "计划已足够",
                    "sufficient": True,
                },
            },
            {
                "tool": TOOL_PROPOSE_EXPERIMENT,
                "proposal": {
                    "experiment_type": "shell",
                    "description": "write result",
                    "expected_artifacts": ["result.txt"],
                    "supports_conclusion": True,
                },
            },
            {
                "tool": "summarize",
                "summary": "结果支持结论",
                "scientific_status": "accepted",
            },
        ]
    )


def test_supervised_cycle_pauses_at_type_b_gates_and_cannot_acquit(monkeypatch, tmp_path) -> None:
    gates: list[CheckpointKind] = []

    monkeypatch.setattr(
        research_cycle,
        "get_run_context",
        lambda: SimpleNamespace(flow_run=SimpleNamespace(id=RUN_ID)),
    )
    monkeypatch.setattr(
        research_cycle,
        "wait_for_decision",
        lambda run_id, kind, receive=None: gates.append(kind),
    )
    monkeypatch.setattr(research_cycle, "save_run_result", lambda result: None)
    monkeypatch.setattr(research_cycle, "save_plan", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(research_cycle, "save_proposal", lambda *_args, **_kwargs: None)

    argv = [
        __import__("sys").executable,
        "-c",
        "from pathlib import Path; Path('result.txt').write_text('ok', encoding='utf-8')",
    ]
    returned = research_cycle.run_research_cycle.fn(
        cycle_request(tmp_path, argv),
        str(tmp_path),
        cooperating_model(),
    )

    assert gates == [
        CheckpointKind.PLAN_APPROVAL,
        CheckpointKind.EXPERIMENT_APPROVAL,
        CheckpointKind.SCIENTIFIC_REVIEW,
    ]
    assert returned["scientific_status"] == ScientificStatus.UNREVIEWED.value
    assert returned["execution_status"] == ExecutionStatus.COMPLETED.value
    assert returned["status"] == "awaiting_scientific_review"
    assert Path(tmp_path, RUN_ID, "attempt-0001", "result.txt").is_file()


def test_missing_required_artifact_is_type_a_failure_not_accepted(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        research_cycle,
        "get_run_context",
        lambda: SimpleNamespace(flow_run=SimpleNamespace(id=RUN_ID)),
    )
    monkeypatch.setattr(research_cycle, "wait_for_decision", lambda *_args, **_kwargs: None)
    saved = []
    monkeypatch.setattr(research_cycle, "save_run_result", saved.append)
    monkeypatch.setattr(research_cycle, "save_plan", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(research_cycle, "save_proposal", lambda *_args, **_kwargs: None)

    argv = [__import__("sys").executable, "-c", "pass"]
    with pytest.raises(JobExecutionError) as raised:
        research_cycle.run_research_cycle.fn(
            cycle_request(tmp_path, argv),
            str(tmp_path),
            cooperating_model(),
        )

    assert raised.value.result.execution_status is ExecutionStatus.FAILED
    assert raised.value.result.scientific_status is ScientificStatus.UNREVIEWED
    assert "missing" in raised.value.result.summary
    assert saved[-1].scientific_status is ScientificStatus.UNREVIEWED


def test_budget_wall_does_not_loop_or_self_approve(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        research_cycle,
        "get_run_context",
        lambda: SimpleNamespace(flow_run=SimpleNamespace(id=RUN_ID)),
    )
    pauses = []
    monkeypatch.setattr(
        research_cycle,
        "wait_for_decision",
        lambda run_id, kind, receive=None: pauses.append(kind),
    )
    monkeypatch.setattr(research_cycle, "save_run_result", lambda result: None)
    monkeypatch.setattr(research_cycle, "save_plan", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(research_cycle, "save_proposal", lambda *_args, **_kwargs: None)

    request = cycle_request(tmp_path, ["python", "-V"])
    request["coordinator_budget"]["max_steps"] = 1
    request["coordinator_budget"]["max_model_calls"] = 1
    returned = research_cycle.run_research_cycle.fn(
        request,
        str(tmp_path),
        cooperating_model(),
    )

    assert returned["status"] == "budget_exhausted"
    assert returned["scientific_status"] == ScientificStatus.UNREVIEWED.value
    assert pauses == [CheckpointKind.PLAN_APPROVAL]
    assert returned.get("execution_status") != ExecutionStatus.COMPLETED.value


def test_rejected_checkpoint_cancels_cycle_instead_of_failing(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        research_cycle,
        "get_run_context",
        lambda: SimpleNamespace(flow_run=SimpleNamespace(id=RUN_ID)),
    )
    monkeypatch.setattr(research_cycle, "save_run_result", lambda result: None)
    monkeypatch.setattr(research_cycle, "save_plan", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(research_cycle, "save_proposal", lambda *_args, **_kwargs: None)

    def reject(run_id, kind, receive=None):
        raise CheckpointRejected(
            ResearchDecision(
                run_id=run_id,
                kind=kind,
                stage=StageStatus.DONE,
                verdict=DecisionVerdict.REJECTED,
                rationale="no",
                decided_by="owner",
                command_version="v1",
            )
        )

    monkeypatch.setattr(research_cycle, "wait_for_decision", reject)

    returned = research_cycle.run_research_cycle.fn(
        cycle_request(tmp_path, ["python", "-V"]),
        str(tmp_path),
        cooperating_model(),
    )

    assert getattr(returned, "type", None) is StateType.CANCELLED
    assert not getattr(returned, "is_failed", lambda: False)()
