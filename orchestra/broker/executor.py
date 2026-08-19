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
import artifact_validators

_MODE_GUIDANCE = {
    "execute": (
        "完成指定工作并验证产物。不要把任务描述改写成答案；最终只报告实际完成内容、"
        "验证结果、产物位置和仍存在的阻塞。"
    ),
    "explore": (
        "先展开多个合理方向，再依据证据收敛。不要预设唯一结论；明确替代解释、"
        "反证、未知项和下一步验证方式。"
    ),
    "decide": (
        "围绕决策标准比较可行选项，给出推荐及其适用条件。必须说明主要取舍、"
        "次优方案以及什么新证据会改变结论。"
    ),
    "audit": (
        "只报告有具体影响的问题。每项包含主张、证据、触发条件、影响、反证或"
        "不确定性、修复方向和验证方法；证据不足时明确标记，不强行下结论。"
    ),
    "brief": (
        "直接给出结果和最必要依据。删除背景复述、同义重复和没有新增信息的总结，"
        "但不得省略失败、风险或关键不确定性。"
    ),
}

_DETAIL_GUIDANCE = {
    "brief": "采用紧凑输出：结果、关键依据、异常或下一步各只保留必要信息。",
    "standard": "采用标准输出：结果、主要依据、关键限制和验证情况完整但不重复。",
    "deep": (
        "采用深入输出：保留证据链、替代方案、反证、不确定性和验证细节；"
        "只有新增信息才能增加篇幅。"
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_dsh_prompt(spec: TaskSpec, outdir: Path) -> str:
    """统一注入任务模式和详略级别，避免各模板重复堆风格规则。"""
    return (
        f"工作目录: {outdir}\n"
        "所有产出文件必须写入该目录。\n\n"
        f"任务模式: {spec.mode}\n"
        f"{_MODE_GUIDANCE[spec.mode]}\n"
        f"输出详略: {spec.detail}\n"
        f"{_DETAIL_GUIDANCE[spec.detail]}\n\n"
        "任务正文:\n"
        f"{spec.body}"
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_child(root: Path, relative: str) -> Path:
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    if not _is_within(candidate, resolved_root):
        raise ValueError(f"path escapes workspace: {relative}")
    return candidate


def _allocate_attempt_dir(base: Path) -> tuple[int, Path]:
    base.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 1000000):
        outdir = base / f"attempt-{attempt}"
        try:
            outdir.mkdir(exist_ok=False)
            return attempt, outdir
        except FileExistsError:
            continue
    raise OSError("cannot allocate attempt directory")


def validate_task_outputs(spec: TaskSpec, outdir: Path) -> list[str]:
    """校验任务声明的必需文件、JSON 文件和 validation status。"""
    errors = []
    parsed_json = {}
    for relative in spec.required_outputs:
        try:
            path = _safe_child(outdir, relative)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"missing required output: {relative}")
            continue
        try:
            if path.stat().st_size == 0:
                errors.append(f"empty required output: {relative}")
        except OSError as exc:
            errors.append(f"cannot stat output {relative}: {exc}")

    for relative in spec.json_outputs:
        try:
            path = _safe_child(outdir, relative)
        except ValueError:
            continue
        if not path.is_file():
            continue
        try:
            parsed_json[relative] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON output {relative}: {exc}")

    if spec.validation_output is not None:
        validation = parsed_json.get(spec.validation_output)
        if validation is not None:
            if not isinstance(validation, dict):
                errors.append(
                    f"validation output must be an object: {spec.validation_output}"
                )
            elif validation.get("status") != "passed":
                errors.append(
                    f"validation status is not passed: {spec.validation_output}"
                )
    if spec.validator is not None:
        errors.extend(artifact_validators.validate_artifacts(spec.validator, outdir))
    return errors


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
    results_root_path = Path(results_root).resolve()
    results_root_path.mkdir(parents=True, exist_ok=True)
    base = _safe_child(results_root_path, spec.result_dir)
    attempt, outdir = _allocate_attempt_dir(base)

    stdout, stderr, status, error = "", "", "done", None
    if spec.executor == "dsh":
        prompt = build_dsh_prompt(spec, outdir)
        cmd = ["dsh", "--profile", dsh_profile]
        if spec.model:
            patch_path = f"/mnt/broker/dsh-patches/{spec.model}.yml"
            if not os.path.exists(patch_path):
                status, error = "failed", f"model patch not found: {patch_path}"
            else:
                cmd += ["--patch", patch_path]
        if status == "done":
            cmd.append(prompt)
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
    output_validation = {
        "status": "not_configured" if not spec.required_outputs else "not_run",
        "errors": [],
    }
    # start_new_session：子进程自成进程组，超时 killpg 连同 dsh 孙进程一起终止
    # （哨兵审计 CONCERN-5：只杀直接子进程会留孤儿继续跑完 → 重复计费+重复邮件）
    kwargs = {"start_new_session": True} if os.name == "posix" else {}
    proc = None
    if status == "done":
        try:
            proc = subprocess.Popen(
                cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", **kwargs,
            )
            stdout, stderr = proc.communicate(timeout=spec.timeout)
            stdout, stderr = stdout or "", stderr or ""
            if proc.returncode != 0:
                status, error = "failed", f"exit code {proc.returncode}"
            elif spec.required_outputs:
                validation_errors = validate_task_outputs(spec, outdir)
                output_validation = {
                    "status": "failed" if validation_errors else "passed",
                    "errors": validation_errors,
                }
                if validation_errors:
                    status = "failed"
                    error = "artifact validation failed: " + "; ".join(validation_errors)
        except subprocess.TimeoutExpired:
            if proc is not None:
                if os.name == "posix":
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    # taskkill /T 树杀（027 finding）；DEVNULL 静默、非零退出不抛、
                    # timeout=10 兜底（taskkill 自身挂死时不卡死 executor）
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            check=False, timeout=10,
                        )
                    except OSError:
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
        "mode": spec.mode, "detail": spec.detail,
        "status": status, "error": error, "started_at": started_iso,
        "output_validation": output_validation,
        "elapsed_s": round(time.time() - started, 1),
    }
    (outdir / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return status, error
