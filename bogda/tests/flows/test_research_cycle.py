from pathlib import Path
from types import SimpleNamespace

from bogda.agents.contracts import AgentBudget
from bogda.agents.coordinator import TOOL_PROPOSE_EXPERIMENT, TOOL_WRITE_PLAN
from bogda.contracts import AutonomyMode, ExecutionStatus, ScientificStatus
from bogda.contracts.decisions import CheckpointKind
from bogda.flows import research_cycle


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
        "job_id": "cycle-1",
        "project_id": "bogda",
        "goal": "measure ridge",
        "autonomy_mode": AutonomyMode.SUPERVISED.value,
        "budget": AgentBudget(
            max_steps=8,
            max_model_calls=8,
            max_cost_cny="10.0",
            allowed_experiment_types=("shell",),
        ).model_dump(mode="json"),
        "allowed_tools": [TOOL_WRITE_PLAN, TOOL_PROPOSE_EXPERIMENT],
        "parameters": {"argv": argv},
        "expected_artifacts": [{"path": path} for path in artifacts],
    }


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
    assert Path(tmp_path, "cycle-1", RUN_ID, "attempt-0001", "result.txt").is_file()


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
    returned = research_cycle.run_research_cycle.fn(
        cycle_request(tmp_path, argv),
        str(tmp_path),
        cooperating_model(),
    )

    assert returned["execution_status"] == ExecutionStatus.FAILED.value
    assert returned["scientific_status"] == ScientificStatus.UNREVIEWED.value
    assert returned["status"] == "missing_artifacts"
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
    request["budget"]["max_steps"] = 1
    request["budget"]["max_model_calls"] = 1
    returned = research_cycle.run_research_cycle.fn(
        request,
        str(tmp_path),
        cooperating_model(),
    )

    assert returned["status"] == "budget_exhausted"
    assert returned["scientific_status"] == ScientificStatus.UNREVIEWED.value
    assert pauses == [CheckpointKind.PLAN_APPROVAL]
    assert returned.get("execution_status") != ExecutionStatus.COMPLETED.value
