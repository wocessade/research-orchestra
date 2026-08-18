"""执行器：dsh headless 与 shell 双通道，产出落 attempt-N 目录（增量落盘）。"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from taskfile import TaskSpec

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def check_net(host: str = "api.deepseek.com", port: int = 443, timeout: int = 3) -> bool:
    """required 任务的断网门：TCP 连通即视为有网。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def run_task(spec: TaskSpec, tasks_dir: str, results_root: str,
             dsh_profile: str = "headless") -> tuple[str, str | None]:
    """执行一个 TaskSpec。返回 (status, error)；status ∈ done|failed。"""
    base = Path(results_root) / spec.result_dir
    attempt = 1
    while (base / f"attempt-{attempt}").exists():
        attempt += 1
    outdir = base / f"attempt-{attempt}"
    outdir.mkdir(parents=True, exist_ok=True)

    if spec.executor == "dsh":
        prompt = f"工作目录: {outdir}\n所有产出文件必须写入该目录。\n\n{spec.body}"
        cmd = ["dsh", "--profile", dsh_profile, prompt]
    elif os.name == "nt":
        cmd = ["cmd", "/c", spec.body]
    else:
        cmd = ["/bin/sh", "-c", spec.body]

    # 统一 cwd = attempt 输出目录（任务工作区）：
    # - dsh 沙箱为 workspace-write，仅 cwd 与 /tmp 可写（E2E 实测：写工作区外被拒）
    # - shell 任务同样以 attempt 目录为工作区，产出落 attempt-N/，不污染 tasks/ 队列目录
    cwd = str(outdir)

    started = time.time()
    stdout, stderr, status, error = "", "", "done", None
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True,
            timeout=spec.timeout, encoding="utf-8", errors="replace",
        )
        stdout, stderr = proc.stdout or "", proc.stderr or ""
        if proc.returncode != 0:
            status, error = "failed", f"exit code {proc.returncode}"
    except subprocess.TimeoutExpired as e:
        stdout, stderr = e.stdout or "", e.stderr or ""
        status, error = "failed", f"timeout after {spec.timeout}s"
    except FileNotFoundError as e:
        status, error = "failed", f"executable not found: {e.filename}"

    (outdir / "stdout.log").write_text(stdout, encoding="utf-8", errors="replace")
    (outdir / "stderr.log").write_text(stderr, encoding="utf-8", errors="replace")
    state = {
        "slug": spec.slug, "executor": spec.executor, "attempt": attempt,
        "status": status, "error": error, "started_at": _now(),
        "elapsed_s": round(time.time() - started, 1),
    }
    (outdir / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return status, error
