from pathlib import Path
import os
import subprocess

import pytest

RUNNER = Path(__file__).resolve().parents[2] / "deploy" / "runner"


def _read(name: str) -> str:
    return (RUNNER / name).read_text(encoding="utf-8")


def test_runner_env_example_is_research_pool_on_nas_without_secrets() -> None:
    text = _read("runner.env.example")
    assert "BOGDA_RESEARCH_POOL=dorm-x86" in text
    assert "BOGDA_WORKER_LIMIT=1" in text
    assert "/mnt/nas/.bogda/runner/artifacts" in text
    assert "BOGDA_APPROVAL_HMAC_KEY=" in text
    assert "pi-service" not in text
    assert "3100" not in text
    assert "token_hex" in text


def test_start_worker_refuses_pi_service_and_keeps_limit_one() -> None:
    text = _read("start-worker.sh")
    assert "--pool \"$POOL\"" in text
    assert "--limit \"$LIMIT\"" in text
    assert "dorm-x86" in text
    assert "never pi-service" in text
    assert "must stay 1" in text
    assert "/mnt/c" in text
    assert "tailscale funnel" not in text


def test_host_bootstrap_keeps_prefect_out_of_windows() -> None:
    text = _read("bootstrap-windows.ps1")
    assert "WSL2" in text
    assert "Wake Bridge" in text
    assert "Do not start a Prefect worker" in text
    assert "pi-service" in text
    assert "prefect worker start" not in text.lower()


def test_wsl_bootstrap_does_not_copy_host_skills() -> None:
    text = _read("bootstrap-wsl.sh")
    assert "Does not copy host skills" in text
    assert "~/.claude/skills" not in text
    assert "/mnt/c" in text
    assert "3100" in text
    assert "pi-service" in text


def test_mount_nas_requires_shared_layout() -> None:
    text = _read("mount-nas.sh")
    assert "/.bogda/inbox" in text
    assert "/.bogda/runner/artifacts" in text
    assert "prepare_runner_share.sh" in text
    assert "credentials=" in text


def test_start_worker_supports_relative_invocation(tmp_path: Path) -> None:
    """The documented relative command must survive the workdir chdir."""
    bash = os.environ.get("BOGDA_BASH")
    if not bash:
        pytest.skip("BOGDA_BASH is required for the shell regression")

    def shell_path(path: Path) -> str:
        value = path.as_posix()
        if os.name == "nt" and len(value) >= 2 and value[1] == ":":
            return f"/{value[0].lower()}{value[2:]}"
        return value

    script = RUNNER / "start-worker.sh"
    repo = tmp_path / "repo"
    runner = repo / "bogda" / "deploy" / "runner"
    runner.mkdir(parents=True)
    (repo / "bogda" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    copied = runner / "start-worker.sh"
    copied.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")

    home = tmp_path / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    fake_uv = home / ".local" / "bin" / "uv"
    fake_uv.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    work = tmp_path / "work"
    shared = tmp_path / "shared"
    shared.mkdir()
    env_file = tmp_path / "runner.env"
    env_file.write_text(
        "\n".join(
            [
                "BOGDA_RESEARCH_POOL=dorm-x86",
                "BOGDA_WORKER_LIMIT=1",
                "PREFECT_API_URL=http://example.invalid/api",
                "BOGDA_STORE_API_URL=http://example.invalid:3101",
                "BOGDA_APPROVAL_HMAC_KEY=test-only",
                f"BOGDA_ARTIFACT_ROOT={shell_path(shared)}",
                f"BOGDA_RUNNER_WORK={shell_path(work)}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [bash, "bogda/deploy/runner/start-worker.sh"],
        cwd=repo,
        env={
            **os.environ,
            "HOME": shell_path(home),
            "BOGDA_RUNNER_ENV": shell_path(env_file),
        },
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--pool dorm-x86 --type process --limit 1 --create-pool-if-not-found" in result.stdout


def test_prefect_cli_supports_worker_start_contract() -> None:
    """The installed Prefect CLI exposes every option start-worker invokes."""
    prefect = RUNNER.parents[1] / ".venv" / "Scripts" / "prefect.exe"
    if not prefect.exists():
        pytest.skip("local Bogda Prefect executable is unavailable")
    result = subprocess.run(
        [str(prefect), "worker", "start", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--create-pool-if-not-found" in result.stdout
    assert "--limit" in result.stdout
