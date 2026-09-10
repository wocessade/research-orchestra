from types import SimpleNamespace

import pytest
from prefect.artifacts import Artifact
from prefect.client.schemas.objects import FlowRunInput
from prefect.states import StateType
from uuid import UUID

from bogda.contracts import (
    AutonomyMode,
    ExecutorKind,
    ExecutionStatus,
    JobRequest,
    ResourceClass,
    RunResult,
    ScientificStatus,
)
from bogda.contracts.decisions import (
    CheckpointKind,
    DecisionVerdict,
    ResearchDecision,
    StageStatus,
)
from bogda.flows import research_checkpoint, shell_job


RUN_ID = "36c86e99-d0a1-4399-a30c-4d6c5044444c"


def request(mode: AutonomyMode = AutonomyMode.SUPERVISED) -> JobRequest:
    return JobRequest(
        job_id="job-1",
        project_id="project-1",
        task_type="shell",
        resource_class=ResourceClass.CPU,
        autonomy_mode=mode,
        parameters={"argv": ["python", "-V"]},
    )


def result_for(run_id: str) -> RunResult:
    return RunResult.model_validate(
        {
            "run_id": run_id,
            "job_id": "job-1",
            "execution_status": "Completed",
            "scientific_status": "unreviewed",
            "started_at": "2026-08-24T00:00:00Z",
            "finished_at": "2026-08-24T00:00:01Z",
            "executor": "shell",
            "attempt": 1,
            "declared_artifacts": [],
            "summary": "completed",
        }
    )


def fake_artifacts(monkeypatch, stored: dict):
    class FakeArtifact:
        def __init__(self, **values):
            self.values = values

        def create(self):
            stored.setdefault(self.values["key"], []).append(self.values["data"])
            return SimpleNamespace()

        @classmethod
        def get(cls, key):
            versions = stored.get(key)
            if not versions:
                return None
            return SimpleNamespace(data=versions[-1])

    monkeypatch.setattr(research_checkpoint, "Artifact", FakeArtifact)


def test_supervised_and_manual_require_type_b_gates_autonomous_does_not() -> None:
    assert request().executor is ExecutorKind.SHELL
    assert request().budget is None
    assert research_checkpoint.required_checkpoints(AutonomyMode.AUTONOMOUS) == ()
    assert CheckpointKind.EXPERIMENT_APPROVAL in research_checkpoint.required_checkpoints(
        AutonomyMode.SUPERVISED
    )
    assert CheckpointKind.SCIENTIFIC_REVIEW in research_checkpoint.required_checkpoints(
        AutonomyMode.MANUAL
    )
    assert CheckpointKind.PLAN_APPROVAL in research_checkpoint.required_checkpoints(
        AutonomyMode.MANUAL
    )


def test_all_checkpoint_keys_are_valid_prefect_artifact_keys() -> None:
    for kind in CheckpointKind:
        Artifact(
            key=research_checkpoint.decision_key(RUN_ID, kind),
            type=research_checkpoint.DECISION_TYPE,
            data={},
            flow_run_id=UUID(RUN_ID),
        )


@pytest.mark.parametrize("kind", list(CheckpointKind))
def test_pause_key_is_valid_prefect_run_input_key(monkeypatch, kind) -> None:
    captured: dict = {}

    def fake_pause(wait_for_input=None, timeout=None, key=None, poll_interval=None):
        captured["key"] = key
        return {}

    monkeypatch.setattr("prefect.flow_runs.pause_flow_run", fake_pause)

    research_checkpoint.prefect_receive(
        ResearchDecision(
            run_id=RUN_ID,
            kind=kind,
            stage=StageStatus.DONE,
            verdict=None,
            command_version="checkpoint-v1",
        )
    )

    FlowRunInput(
        flow_run_id=UUID(RUN_ID),
        key=f"paused-{captured['key']}-{RUN_ID}-schema",
        value="{}",
    )


def test_approve_marks_accepted_and_persists_decision(monkeypatch) -> None:
    stored: dict = {}
    fake_artifacts(monkeypatch, stored)

    decided = research_checkpoint.wait_for_decision(
        RUN_ID,
        CheckpointKind.EXPERIMENT_APPROVAL,
        receive=lambda pending: {
            "verdict": "approved",
            "rationale": "plan is enough to run",
            "decided_by": "owner",
        },
    )

    assert decided.stage is StageStatus.ACCEPTED
    assert decided.verdict is DecisionVerdict.APPROVED
    loaded = research_checkpoint.load_decision(RUN_ID, CheckpointKind.EXPERIMENT_APPROVAL)
    assert loaded == decided
    assert loaded.rationale == "plan is enough to run"


def test_reject_terminates_without_marking_accepted(monkeypatch) -> None:
    stored: dict = {}
    fake_artifacts(monkeypatch, stored)

    with pytest.raises(research_checkpoint.CheckpointRejected) as raised:
        research_checkpoint.wait_for_decision(
            RUN_ID,
            CheckpointKind.EXPERIMENT_APPROVAL,
            receive=lambda pending: {
                "verdict": "rejected",
                "rationale": "unsafe experiment",
                "decided_by": "owner",
            },
        )

    assert raised.value.decision.verdict is DecisionVerdict.REJECTED
    assert raised.value.decision.stage is StageStatus.DONE
    loaded = research_checkpoint.load_decision(RUN_ID, CheckpointKind.EXPERIMENT_APPROVAL)
    assert loaded.stage is StageStatus.DONE
    assert loaded.verdict is DecisionVerdict.REJECTED


def test_stale_resume_payload_does_not_accept(monkeypatch) -> None:
    stored: dict = {}
    fake_artifacts(monkeypatch, stored)
    payloads = [
        {"verdict": "approved", "rationale": "stale", "decided_by": "other", "command_version": "old"},
        {"verdict": "approved", "rationale": "current", "decided_by": "owner"},
    ]

    def receive(pending: ResearchDecision):
        payload = payloads.pop(0)
        if "command_version" not in payload:
            payload = {**payload, "command_version": pending.command_version}
        return payload

    decided = research_checkpoint.wait_for_decision(
        RUN_ID,
        CheckpointKind.SCIENTIFIC_REVIEW,
        receive=receive,
    )

    assert decided.rationale == "current"
    assert decided.stage is StageStatus.ACCEPTED
    assert payloads == []


def test_done_but_unaccepted_checkpoint_pauses_again(monkeypatch) -> None:
    stored: dict = {}
    fake_artifacts(monkeypatch, stored)
    calls: list[ResearchDecision] = []

    def receive(pending: ResearchDecision):
        calls.append(pending)
        if len(calls) == 1:
            return {}
        return {
            "verdict": "approved",
            "rationale": "after restart",
            "decided_by": "owner",
            "command_version": pending.command_version,
        }

    research_checkpoint.save_decision(
        ResearchDecision(
            run_id=RUN_ID,
            kind=CheckpointKind.EXPERIMENT_APPROVAL,
            stage=StageStatus.DONE,
            verdict=None,
            command_version="pending-v1",
        )
    )

    decided = research_checkpoint.wait_for_decision(
        RUN_ID,
        CheckpointKind.EXPERIMENT_APPROVAL,
        receive=receive,
    )

    assert len(calls) == 2
    assert calls[0].stage is StageStatus.DONE
    assert calls[0].verdict is None
    assert decided.stage is StageStatus.ACCEPTED
    assert decided.rationale == "after restart"


def test_type_a_completion_cannot_acquit_scientific_status(monkeypatch) -> None:
    saved: list[RunResult] = []
    decisions: list[CheckpointKind] = []

    class FakeShellTask:
        def with_options(self, *, retries):
            def invoke(_request_data, _attempts_root, task_run_id):
                return result_for(task_run_id).model_dump(mode="json")

            return invoke

    monkeypatch.setattr(
        shell_job,
        "get_run_context",
        lambda: SimpleNamespace(flow_run=SimpleNamespace(id=RUN_ID)),
    )
    monkeypatch.setattr(shell_job, "execute_shell_task", FakeShellTask())
    monkeypatch.setattr(shell_job, "save_run_result", saved.append)
    monkeypatch.setattr(
        shell_job,
        "wait_for_decision",
        lambda run_id, kind, receive=None: decisions.append(kind),
    )

    returned = shell_job.run_shell_job.fn(
        request(AutonomyMode.SUPERVISED).model_dump(mode="json"),
        "attempts",
    )
    result = RunResult.model_validate(returned)

    assert decisions == [
        CheckpointKind.EXPERIMENT_APPROVAL,
        CheckpointKind.SCIENTIFIC_REVIEW,
    ]
    assert result.execution_status is ExecutionStatus.COMPLETED
    assert result.scientific_status is ScientificStatus.UNREVIEWED
    assert saved[-1].scientific_status is ScientificStatus.UNREVIEWED


def test_autonomous_shell_skips_human_checkpoints(monkeypatch) -> None:
    decisions: list[CheckpointKind] = []

    class FakeShellTask:
        def with_options(self, *, retries):
            def invoke(_request_data, _attempts_root, task_run_id):
                return result_for(task_run_id).model_dump(mode="json")

            return invoke

    monkeypatch.setattr(
        shell_job,
        "get_run_context",
        lambda: SimpleNamespace(flow_run=SimpleNamespace(id=RUN_ID)),
    )
    monkeypatch.setattr(shell_job, "execute_shell_task", FakeShellTask())
    monkeypatch.setattr(shell_job, "save_run_result", lambda result: None)
    monkeypatch.setattr(
        shell_job,
        "wait_for_decision",
        lambda run_id, kind, receive=None: decisions.append(kind),
    )

    shell_job.run_shell_job.fn(
        request(AutonomyMode.AUTONOMOUS).model_dump(mode="json"),
        "attempts",
    )

    assert decisions == []


def test_rejected_checkpoint_cancels_flow_instead_of_failing(monkeypatch) -> None:
    executed = []

    class FakeShellTask:
        def with_options(self, *, retries):
            def invoke(_request_data, _attempts_root, _task_run_id):
                executed.append(True)
                return result_for(RUN_ID).model_dump(mode="json")

            return invoke

    def reject(run_id, kind, receive=None):
        raise research_checkpoint.CheckpointRejected(
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

    monkeypatch.setattr(
        shell_job,
        "get_run_context",
        lambda: SimpleNamespace(flow_run=SimpleNamespace(id=RUN_ID)),
    )
    monkeypatch.setattr(shell_job, "execute_shell_task", FakeShellTask())
    monkeypatch.setattr(shell_job, "save_run_result", lambda result: None)
    monkeypatch.setattr(shell_job, "wait_for_decision", reject)

    returned = shell_job.run_shell_job.fn(
        request().model_dump(mode="json"),
        "attempts",
    )

    assert executed == []
    assert getattr(returned, "type", None) is StateType.CANCELLED
    assert not getattr(returned, "is_failed", lambda: False)()
