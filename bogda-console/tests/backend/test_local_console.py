from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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


def healthy_observation(*, pid: int = MANAGED_PID, profile: str = "mock-all") -> dict[str, Any]:
    return {
        "state": {"pid": pid, "startTime": HEALTHY_START},
        "process": {"pid": pid, "running": True, "startTime": HEALTHY_START},
        "listener": {"port": 3101, "pid": pid},
        "capabilities": {"reachable": True, "httpStatus": 200, "profile": profile},
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


def bootstrap_child_observation() -> dict[str, Any]:
    return {
        "state": {"pid": MANAGED_PID, "startTime": HEALTHY_START},
        "process": {"pid": MANAGED_PID, "running": True, "startTime": HEALTHY_START},
        "listener": {"port": 3101, "pid": FOREIGN_PID},
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


def write_controlled_child(root: Path, *, profile: str) -> None:
    (root / "bogda_console.py").write_text(
        f"""
import http.server
import json
import os
import sys
import threading

for key in ("PREFECT_API_AUTH_STRING", "PREFECT_API_KEY", "DEEPSEEK_API_KEY"):
    value = os.environ.get(key)
    if value:
        print(f"stdout {{key}}={{value}}", flush=True)
        print(f"stderr {{key}}={{value}}", file=sys.stderr, flush=True)

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/v1/capabilities":
            self.send_response(404)
            self.end_headers()
            return
        payload = {{"data": {{"profile": {profile!r}}}}}
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return

server = http.server.ThreadingHTTPServer(("127.0.0.1", 3101), Handler)
shutdown = threading.Timer(2, server.shutdown)
shutdown.daemon = True
shutdown.start()
server.serve_forever()
""",
        encoding="utf-8",
    )


def copy_launcher(tmp_path: Path) -> Path:
    assert LAUNCHER.is_file(), f"missing launcher script: {LAUNCHER}"
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    target = scripts / "local-console.ps1"
    shutil.copy(LAUNCHER, target)
    return target


def point_launcher_to_python(script: Path) -> None:
    python = str(Path(getattr(sys, "_base_executable", sys.executable)).resolve()).replace("'", "''")
    text = script.read_text(encoding="utf-8")
    text = text.replace(
        '$Python = [System.IO.Path]::GetFullPath((Join-Path $Root ".venv\\Scripts\\python.exe"))',
        f"$Python = '{python}'",
    )
    text = text.replace(
        "}\n\nfunction Write-HostMessage",
        "}\n\n$ChildEnv['PYTHONPATH'] = $Root\n\nfunction Write-HostMessage",
        1,
    )
    script.write_text(text, encoding="utf-8")


def cleanup_controlled_state(state_dir: Path) -> None:
    state_path = state_dir / "state.json"
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            pid = int(state["pid"])
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            pid = None
        if pid is not None:
            subprocess.run(
                ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=5,
            )
    for name in ("state.json", "stdout.log", "stderr.log", "run_bogda_console.py"):
        path = state_dir / name
        if path.is_file():
            path.unlink()


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


def test_plan_honors_non_reserved_public_port(tmp_path: Path) -> None:
    completed = run_launcher(
        "plan",
        script=LAUNCHER,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        extra_env={"BOGDA_CONSOLE_PUBLIC_PORT": "3103"},
    )
    assert completed.returncode == 0, _output(completed)
    plan = parse_json(completed)
    assert plan["port"] == 3103
    assert plan["env"]["BOGDA_CONSOLE_PUBLIC_PORT"] == "3103"
    assert plan["host"] == "127.0.0.1"


def test_plan_forwards_real_profile_settings_without_exposing_credentials(tmp_path: Path) -> None:
    secrets = ["auth-sentinel", "prefect-key-sentinel", "deepseek-key-sentinel"]
    completed = run_launcher(
        "plan",
        script=LAUNCHER,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        extra_env={
            "BOGDA_CONSOLE_PROFILE": "real-readonly",
            "PREFECT_API_URL": "http://prefect.test/api",
            "PREFECT_API_AUTH_STRING": secrets[0],
            "PREFECT_API_KEY": secrets[1],
            "DEEPSEEK_API_KEY": secrets[2],
        },
    )
    assert completed.returncode == 0, _output(completed)
    output = _output(completed)
    plan = parse_json(completed)

    assert plan["env"]["BOGDA_CONSOLE_PROFILE"] == "real-readonly"
    assert plan["env"]["PREFECT_API_URL"] == "http://prefect.test/api"
    assert plan["env"]["PREFECT_API_AUTH_STRING"] == "[set]"
    assert plan["env"]["PREFECT_API_KEY"] == "[set]"
    assert plan["env"]["DEEPSEEK_API_KEY"] == "[set]"
    for secret in secrets:
        assert secret not in output


def test_plan_forwards_allowlisted_profile_scope_and_does_not_inherit_mock_scope(tmp_path: Path) -> None:
    completed = run_launcher(
        "plan",
        script=LAUNCHER,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        extra_env={
            "BOGDA_CONSOLE_PROFILE": "allowlisted-test",
            "PREFECT_API_URL": "http://prefect.test/api",
            "BOGDA_CONSOLE_REPLICA_COUNT": "1",
            "BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS": "deployment-z,deployment-a",
            "BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS": "schedule-z,schedule-a",
            "BOGDA_CONSOLE_ALLOWED_QUEUE_IDS": "queue-z,queue-a",
            "BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES": "pool-z,pool-a",
        },
    )
    assert completed.returncode == 0, _output(completed)
    env = parse_json(completed)["env"]
    assert env["BOGDA_CONSOLE_PROFILE"] == "allowlisted-test"
    assert env["PREFECT_API_URL"] == "http://prefect.test/api"
    assert env["BOGDA_CONSOLE_REPLICA_COUNT"] == "1"
    assert env["BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS"] == "deployment-z,deployment-a"
    assert env["BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS"] == "schedule-z,schedule-a"
    assert env["BOGDA_CONSOLE_ALLOWED_QUEUE_IDS"] == "queue-z,queue-a"
    assert env["BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES"] == "pool-z,pool-a"


def test_plan_real_profile_defaults_to_empty_allowlist_scope(tmp_path: Path) -> None:
    completed = run_launcher(
        "plan",
        script=LAUNCHER,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        extra_env={
            "BOGDA_CONSOLE_PROFILE": "real-readonly",
            "PREFECT_API_URL": "http://prefect.test/api",
        },
    )
    assert completed.returncode == 0, _output(completed)
    env = parse_json(completed)["env"]
    assert env["BOGDA_CONSOLE_ALLOWED_DEPLOYMENT_IDS"] == ""
    assert env["BOGDA_CONSOLE_ALLOWED_SCHEDULE_IDS"] == ""
    assert env["BOGDA_CONSOLE_ALLOWED_QUEUE_IDS"] == ""
    assert env["BOGDA_CONSOLE_ALLOWED_WORK_POOL_NAMES"] == ""


def test_probe_accepts_an_explicit_real_profile_as_healthy(tmp_path: Path) -> None:
    completed = run_launcher(
        "probe",
        script=LAUNCHER,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        observation=healthy_observation(profile="real-readonly"),
        extra_env={"BOGDA_CONSOLE_PROFILE": "real-readonly"},
    )
    assert completed.returncode == 0, _output(completed)
    payload = parse_json(completed)
    assert payload["status"] == "healthy"
    assert payload["launchReady"] is True


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


def test_powershell_7_live_status_handles_unreachable_capabilities(tmp_path: Path) -> None:
    pwsh = shutil.which("pwsh.exe")
    if pwsh is None:
        pytest.skip("PowerShell 7 is not installed")

    env = os.environ.copy()
    env["BOGDA_CONSOLE_STATE_DIR"] = str(tmp_path / "state")
    env["BOGDA_CONSOLE_LAUNCHER_DRY_RUN"] = "1"
    env.pop("BOGDA_CONSOLE_LAUNCHER_OBSERVATION", None)
    completed = subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(LAUNCHER),
            "status",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )

    output = _output(completed)
    assert completed.returncode in {0, 1, 2, 3}, output
    assert "status:" in output.lower()
    assert "property 'response' cannot be found" not in output.lower()


def test_probe_marks_healthy_child_listener_as_launch_ready(tmp_path: Path) -> None:
    completed = run_launcher(
        "probe",
        script=LAUNCHER,
        cwd=tmp_path,
        state_dir=tmp_path / "state",
        observation=bootstrap_child_observation(),
    )

    payload = parse_json(completed)
    assert payload["launchReady"] is True
    assert payload["launchPid"] == FOREIGN_PID


def test_start_redacts_configured_secrets_from_child_logs_and_failure_tail(
    tmp_path: Path,
) -> None:
    state_dirs = [tmp_path / "state", tmp_path / "failing" / "state"]
    try:
        script = copy_launcher(tmp_path)
        materialize_runtime(tmp_path, venv=False, dist=True)
        point_launcher_to_python(script)
        write_controlled_child(tmp_path, profile="real-readonly")
        secrets = {
            "PREFECT_API_AUTH_STRING": "AUTH_SENTINEL_FOR_LAUNCHER_TEST",
            "PREFECT_API_KEY": "PREFECT_KEY_SENTINEL_FOR_LAUNCHER_TEST",
            "DEEPSEEK_API_KEY": "DEEPSEEK_KEY_SENTINEL_FOR_LAUNCHER_TEST",
        }
        completed = run_launcher(
            "start",
            script=script,
            cwd=tmp_path,
            state_dir=tmp_path / "state",
            extra_env={
                "BOGDA_CONSOLE_PROFILE": "real-readonly",
                "PREFECT_API_AUTH_STRING": secrets["PREFECT_API_AUTH_STRING"],
                "PREFECT_API_KEY": secrets["PREFECT_API_KEY"],
                "DEEPSEEK_API_KEY": secrets["DEEPSEEK_API_KEY"],
            },
            dry_run=False,
        )
        assert completed.returncode == 0, _output(completed)
        output = _output(completed)
        assert all(secret not in output for secret in secrets.values())
        logs = list((tmp_path / "state").glob("*.log"))
        assert {path.name for path in logs} == {"stdout.log", "stderr.log"}
        for path in logs:
            text = path.read_text(encoding="utf-8")
            assert "[redacted]" in text
            assert all(secret not in text for secret in secrets.values())

        failing_root = tmp_path / "failing"
        failing_root.mkdir()
        failing_script = copy_launcher(failing_root)
        materialize_runtime(failing_root, venv=False, dist=True)
        point_launcher_to_python(failing_script)
        write_controlled_child(failing_root, profile="wrong-profile")
        failing_script_text = failing_script.read_text(encoding="utf-8")
        failing_script.write_text(
            failing_script_text.replace("$ReadyTimeoutSeconds = 15", "$ReadyTimeoutSeconds = 1"),
            encoding="utf-8",
        )
        failed = run_launcher(
            "start",
            script=failing_script,
            cwd=tmp_path / "failing",
            state_dir=tmp_path / "failing" / "state",
            extra_env={
                "BOGDA_CONSOLE_PROFILE": "real-readonly",
                **secrets,
            },
            dry_run=False,
        )
        assert failed.returncode != 0
        failure_output = _output(failed)
        assert all(secret not in failure_output for secret in secrets.values())
    finally:
        for state_dir in state_dirs:
            cleanup_controlled_state(state_dir)


def test_powershell_7_preserves_iso_start_time_from_saved_state(tmp_path: Path) -> None:
    pwsh = shutil.which("pwsh.exe")
    if pwsh is None:
        pytest.skip("PowerShell 7 is not installed")

    dummy = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        started = subprocess.run(
            [
                pwsh,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"(Get-Process -Id {dummy.pid}).StartTime.ToString('o')",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        ).stdout.strip()
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "state.json").write_text(
            json.dumps({"pid": dummy.pid, "startTime": started, "host": "127.0.0.1", "port": 3101}),
            encoding="utf-8",
        )

        env = os.environ.copy()
        env["BOGDA_CONSOLE_STATE_DIR"] = str(state_dir)
        env["BOGDA_CONSOLE_LAUNCHER_DRY_RUN"] = "1"
        env.pop("BOGDA_CONSOLE_LAUNCHER_OBSERVATION", None)
        completed = subprocess.run(
            [pwsh, "-NoProfile", "-NonInteractive", "-File", str(LAUNCHER), "status"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )

        assert completed.returncode == 1, _output(completed)
        assert "status: degraded" in _output(completed).lower()
    finally:
        dummy.terminate()
        dummy.wait(timeout=5)
