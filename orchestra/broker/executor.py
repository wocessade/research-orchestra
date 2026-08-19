"""执行器：dsh headless 与 shell 双通道，产出落 attempt-N 目录（增量落盘）。"""
from __future__ import annotations

import json
import os
import signal
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
    started_iso = _now()  # 真实开始时刻（state.json 用；哨兵审计：勿用完成时刻）
    stdout, stderr, status, error = "", "", "done", None
    # start_new_session：子进程自成进程组，超时 killpg 连同 dsh 孙进程一起终止
    # （哨兵审计 CONCERN-5：只杀直接子进程会留孤儿继续跑完 → 重复计费+重复邮件）
    kwargs = {"start_new_session": True} if os.name == "posix" else {}
    proc = None
    try:
        proc = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", **kwargs,
        )
        stdout, stderr = proc.communicate(timeout=spec.timeout)
        stdout, stderr = stdout or "", stderr or ""
        if proc.returncode != 0:
            status, error = "failed", f"exit code {proc.returncode}"
    except subprocess.TimeoutExpired:
        if proc is not None:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            stdout, stderr = proc.communicate()
            stdout, stderr = stdout or "", stderr or ""
        status, error = "failed", f"timeout after {spec.timeout}s"
    except FileNotFoundError as e:
        status, error = "failed", f"executable not found: {e.filename}"
    except OSError as e:
        status, error = "failed", f"spawn error: {e}"

    (outdir / "stdout.log").write_text(stdout, encoding="utf-8", errors="replace")
    (outdir / "stderr.log").write_text(stderr, encoding="utf-8", errors="replace")
    state = {
        "slug": spec.slug, "executor": spec.executor, "attempt": attempt,
        "status": status, "error": error, "started_at": started_iso,
        "elapsed_s": round(time.time() - started, 1),
    }
    (outdir / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return status, error
