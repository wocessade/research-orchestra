import json

from bogda.contracts import AutonomyMode, ExecutorKind, ModelTier, TaskIntent
from bogda.control import cli
from bogda.policy import PolicyStore


def test_result_command_prints_stored_result(monkeypatch, capsys) -> None:
    stored = {
        "run_id": "36c86e99-d0a1-4399-a30c-4d6c5044444c",
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
    monkeypatch.setattr(
        cli,
        "load_run_result",
        lambda run_id: cli.RunResult.model_validate(stored),
    )

    exit_code = cli.main(["result", stored["run_id"]])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["scientific_status"] == "unreviewed"


def test_result_command_returns_one_when_result_is_absent(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "load_run_result", lambda run_id: None)

    exit_code = cli.main(
        ["result", "36c86e99-d0a1-4399-a30c-4d6c5044444c"]
    )

    assert exit_code == 1
    assert "not found" in capsys.readouterr().err


def test_demo_request_freezes_resolved_mode_and_policy_revision(tmp_path) -> None:
    store = PolicyStore(tmp_path / "autonomy.json")
    store.set_mode("bogda", AutonomyMode.MANUAL, expected_revision=0)

    request = cli.demo_request(store)
    store.set_mode("bogda", AutonomyMode.AUTONOMOUS, expected_revision=1)

    assert request.autonomy_mode is AutonomyMode.MANUAL
    assert request.policy_revision == 1
    assert request.intent is TaskIntent.EXECUTE
    assert request.model_tier is ModelTier.AUTO
    assert request.executor is ExecutorKind.SHELL
    assert request.budget is None
    assert store.resolve_mode("bogda").effective_mode is AutonomyMode.AUTONOMOUS
