from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest


CONSOLE_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = CONSOLE_ROOT / "scripts" / "local-console.ps1"

HEALTHY_START = "2026-08-24T12:00:00"
MANAGED_PID = 4242
FOREIGN_PID = 9999

EXPECTED_ENV = {
    "BOGDA_CONSOLE_PROFILE": "mock-all",
    "BOGDA_CONSOLE_TEST_MODE": "0",
    "BOGDA_CONSOLE_PUBLIC_HOST": "127.0.0.1",
    "BOGDA_CONSOLE_PUBLIC_PORT": "3101",
    "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-service,deployment-dorm",
    "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS": "schedule-service,schedule-dorm",
    "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS": "queue-service,queue-cpu,queue-gpu",
    "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "pi-service,dorm-x86",
}


def _output(completed: subprocess.CompletedProcess[str]) -> str:
    return f"{completed.stdout}\n{completed.stderr}"


def parse_json(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    text = completed.stdout.strip()
    start = text.find("{")
    end = text.rfind("}")
    assert start != -1 and end != -1, _output(completed)
    return json.loads(text[start : end + 1])


def write_observation(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def healthy_observation(*, pid: int = MANAGED_PID) -> dict[str, Any]:
    return {
        "state": {"pid": pid, "startTime": HEALTHY_START},
        "process": {"pid": pid, "running": True, "startTime": HEALTHY_START},
        "listener": {"port": 3101, "pid": pid},
        "capabilities": {"reachable": True, "httpStatus": 200, "profile": "mock-all"},
    }


def stopped_observation() -> dict[str, Any]:
    return {
        "state": None,
        "process": {"pid": None, "running": False, "startTime": None},
        "listener": {"port": 3101, "pid": None},
        "capabilities": {"reachable": False, "httpStatus": None, "profile": None},
    }


def foreign_observation(*, listener_pid: int = FOREIGN_PID) -> dict[str, Any]:
    return {
        "state": None,
        "process": {"pid": None, "running": False, "startTime": None},
        "listener": {"port": 3101, "pid": listener_pid},
        "capabilities": {"reachable": True, "httpStatus": 200, "profile": "mock-all"},
    }


def stale_observation() -> dict[str, Any]:
    return {
        "state": {"pid": MANAGED_PID, "startTime": HEALTHY_START},
        "process": {"pid": MANAGED_PID, "running": True, "startTime": "2026-08-24T18:00:00"},
        "listener": {"port": 3101, "pid": MANAGED_PID},
        "capabilities": {"reachable": True, "httpStatus": 200, "profile": "mock-all"},
    }


def degraded_observation() -> dict[str, Any]:
    return {
        "state": {"pid": MANAGED_PID, "startTime": HEALTHY_START},
        "process": {"pid": MANAGED_PID, "running": True, "startTime": HEALTHY_START},
        "listener": {"port": 3101, "pid": None},
        "capabilities": {"reachable": False, "httpStatus": None, "profile": None},
    }


def materialize_runtime(root: Path, *, venv: bool, dist: bool) -> None:
    if venv:
        python = root / ".venv" / "Scripts" / "python.exe"
        python.parent.mkdir(parents=True, exist_ok=True)
        python.write_bytes(b"fake-python")
    if dist:
        dist_dir = root / "frontend" / "dist"
        (dist_dir / "assets").mkdir(parents=True, exist_ok=True)
        (dist_dir / "index.html").write_text("<html></html>", encoding="utf-8")


def copy_launcher(tmp_path: Path) -> Path:
    assert LAUNCHER.is_file(), f"missing launcher script: {LAUNCHER}"
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    target = scripts / "local-console.ps1"
    shutil.copy(LAUNCHER, target)
    return target


def run_launcher(
    action: str,
    *,
    script: Path,
    cwd: Path,
    state_dir: Path,
    observation: dict[str, Any] | None = None,
    extra_env: dict[str, str] | None = None,
    dry_run: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["BOGDA_CONSOLE_STATE_DIR"] = str(state_dir)
    env["BOGDA_CONSOLE_LAUNCHER_DRY_RUN"] = "1" if dry_run else "0"
    if observation is not None:
        obs_path = state_dir / "observation.json"
        state_dir.mkdir(parents=True, exist_ok=True)
        write_observation(obs_path, observation)
        env["BOGDA_CONSOLE_LAUNCHER_OBSERVATION"] = str(obs_path)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            action,
        ],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )


def test_launcher_script_exists() -> None:
    assert LAUNCHER.is_file()


def test_plan_resolves_console_root_from_arbitrary_cwd(tmp_path: Path) -> None:
    foreign_cwd = tmp_path / "elsewhere"
    foreign_cwd.mkdir()
    completed = run_launcher(
        "plan",
        script=LAUNCHER,
        cwd=foreign_cwd,
        state_dir=tmp_path / "state",
    )
    assert completed.returncode == 0, _output(completed)
    plan = parse_json(completed)
    assert Path(plan["root"]) == CONSOLE_ROOT
    assert Path(plan["python"]) == CONSOLE_ROOT / ".venv" / "Scripts" / "python.exe"
    assert Path(plan["frontendDist"]) == CONSOLE_ROOT / "frontend" / "dist"


def test_plan_pins_loopback_3101_and_does_not_bind_3100(tmp_path: Path) -> None:
    completed = run_launcher(
        "plan",
        script=LAUNCHER,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        extra_env={
            "BOGDA_CONSOLE_PUBLIC_PORT": "3100",
            "BOGDA_CONSOLE_PUBLIC_HOST": "0.0.0.0",
        },
    )
    assert completed.returncode == 0, _output(completed)
    plan = parse_json(completed)
    assert plan["host"] == "127.0.0.1"
    assert plan["port"] == 3101
    env = plan["env"]
    assert env["BOGDA_CONSOLE_PUBLIC_PORT"] == "3101"
    assert env["BOGDA_CONSOLE_PUBLIC_HOST"] == "127.0.0.1"
    assert "3100" not in json.dumps(env)
    assert env == EXPECTED_ENV
    command = " ".join(plan["command"])
    assert "-m bogda_console" in command
    assert "3100" not in command


def test_start_refuses_missing_venv_and_prints_readme_repair(tmp_path: Path) -> None:
    script = copy_launcher(tmp_path)
    materialize_runtime(tmp_path, venv=False, dist=True)
    foreign_cwd = tmp_path / "not-the-root"
    foreign_cwd.mkdir()
    completed = run_launcher(
        "start",
        script=script,
        cwd=foreign_cwd,
        state_dir=tmp_path / "state",
        observation=stopped_observation(),
    )
    output = _output(completed)
    assert completed.returncode != 0
    assert ".venv" in output
    assert "py -3.11 -m venv .venv" in output
    assert ".venv\\Scripts\\python.exe -m pip install -e ." in output
    assert "Start-Process" not in output
    assert "python.exe" not in output.lower() or "missing" in output.lower() or ".venv" in output


def test_start_refuses_missing_frontend_dist_and_prints_readme_repair(tmp_path: Path) -> None:
    script = copy_launcher(tmp_path)
    materialize_runtime(tmp_path, venv=True, dist=False)
    completed = run_launcher(
        "start",
        script=script,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        observation=stopped_observation(),
    )
    output = _output(completed)
    assert completed.returncode != 0
    assert "frontend\\dist" in output or "frontend/dist" in output
    assert "npm ci" in output
    assert "npm run build" in output


def test_start_is_idempotent_when_managed_process_is_healthy(tmp_path: Path) -> None:
    script = copy_launcher(tmp_path)
    materialize_runtime(tmp_path, venv=True, dist=True)
    completed = run_launcher(
        "start",
        script=script,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        observation=healthy_observation(),
    )
    output = _output(completed).lower()
    assert completed.returncode == 0, _output(completed)
    assert "already running" in output
    assert str(FOREIGN_PID) not in _output(completed)
    assert "stop-process" not in output


def test_start_refuses_foreign_listener_and_does_not_stop_it(tmp_path: Path) -> None:
    script = copy_launcher(tmp_path)
    materialize_runtime(tmp_path, venv=True, dist=True)
    completed = run_launcher(
        "start",
        script=script,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        observation=foreign_observation(),
    )
    output = _output(completed).lower()
    assert completed.returncode != 0
    assert "foreign" in output
    assert str(FOREIGN_PID) in _output(completed)
    assert "not stopping" in output or "not stop" in output
    assert "stop-process" not in output


def test_stop_refuses_stale_pid_start_time_and_does_not_kill(tmp_path: Path) -> None:
    script = copy_launcher(tmp_path)
    materialize_runtime(tmp_path, venv=True, dist=True)
    completed = run_launcher(
        "stop",
        script=script,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        observation=stale_observation(),
    )
    output = _output(completed).lower()
    assert completed.returncode != 0
    assert "start time" in output or "starttime" in output or "stale" in output
    assert "stop-process" not in output
    assert "would stop" not in output


@pytest.mark.parametrize(
    ("observation", "expected", "exit_code"),
    [
        (healthy_observation(), "healthy", 0),
        (degraded_observation(), "degraded", 1),
        (stopped_observation(), "stopped", 2),
        (foreign_observation(), "foreign-listener", 3),
    ],
)
def test_status_reports_four_states(
    tmp_path: Path,
    observation: dict[str, Any],
    expected: str,
    exit_code: int,
) -> None:
    script = copy_launcher(tmp_path)
    materialize_runtime(tmp_path, venv=True, dist=True)
    completed = run_launcher(
        "status",
        script=script,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        observation=observation,
    )
    output = _output(completed).lower()
    assert completed.returncode == exit_code, _output(completed)
    assert expected in output


def test_stop_only_targets_matching_managed_pid(tmp_path: Path) -> None:
    script = copy_launcher(tmp_path)
    materialize_runtime(tmp_path, venv=True, dist=True)
    completed = run_launcher(
        "stop",
        script=script,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        observation=healthy_observation(),
    )
    output = _output(completed)
    assert completed.returncode == 0, output
    assert str(MANAGED_PID) in output
    assert str(FOREIGN_PID) not in output
    lowered = output.lower()
    assert "get-process python" not in lowered
    assert "stop-process -name python" not in lowered


def test_probe_does_not_touch_live_3101_when_observation_is_injected(tmp_path: Path) -> None:
    script = copy_launcher(tmp_path)
    completed = run_launcher(
        "probe",
        script=script,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        observation=foreign_observation(),
    )
    assert completed.returncode == 3, _output(completed)
    payload = parse_json(completed)
    assert payload["status"] == "foreign-listener"
    assert payload["listenerPid"] == FOREIGN_PID
    assert payload["stopDecision"] == "refuse-foreign"
    assert payload["startDecision"] == "refuse-foreign"
    assert 3100 not in {payload.get("port"), payload.get("listenerPort")}
