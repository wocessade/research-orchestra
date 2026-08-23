import json

from bogda.control import cli


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
