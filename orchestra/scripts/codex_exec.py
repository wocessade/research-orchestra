"""codex_exec.py — stdlib-only wrapper around `codex exec --json`.

Wraps the Codex CLI (codex-cli, e.g. 0.148.0) JSONL event stream into a
small structured result dict for CC orchestration:

    run_codex(prompt, model, timeout, cwd, skip_git_check, runner) -> dict
        {"status": "ok|error|timeout", "text": str, "session_id": str|null,
         "model": str|null, "elapsed_s": float, "events": int,
         "error_type": str|null, "raw_lines": [str]}

Design decisions (per mission 027 / D23):
  * The prompt is delivered via stdin, never argv (no shell-history leak).
  * Trust check: cwd must be inside a git repo (`git -C <cwd> rev-parse
    --git-dir`); otherwise `--skip-git-repo-check` is appended so codex
    does not refuse the run with "Not inside a trusted directory".
    `skip_git_check=True` forces the flag regardless.
  * The subprocess call is injectable (`runner`) so tests never touch the
    real codex CLI. Default runner is subprocess.run, which kills the
    child on TimeoutExpired.
  * Error classification: authentication / rate_limit / network / trust /
    sandbox / not_installed / unknown — sourced from the event stream and,
    when the process fails, from stderr/stdout text.
  * Transport noise events ("Reconnecting...", "Falling back from
    WebSockets to HTTPS transport") are ignored, not classified as network
    failures (verified against the real 0.148.0 smoke stream).

CLI:
    codex_exec.py run <prompt-file|-> [--model X] [--timeout N]
                       [--out DIR] [--json-out PATH] [--skip-git-check]
    exit codes: 0=ok 1=exec failed 2=not installed 3=timeout 4=auth failed
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

# Messages that are transport noise (codex's own WS->HTTPS fallback), not
# failures. Calibrated against the real 0.148.0 smoke stream.
_NOISE_MARKERS = (
    "reconnecting",
    "falling back from websockets to https transport",
    "request timed out",
)

_CLASSIFIERS = (
    # (error_type, keywords — matched case-insensitively)
    ("authentication", ("not logged in", "401", "authentication", "please run codex login", "unauthorized")),
    ("rate_limit", ("rate limit", "429", "too many requests")),
    ("trust", ("not inside a trusted directory", "trusted directory")),
    ("sandbox", ("sandbox", "not allowed to run")),
    ("network", ("network error", "failed to connect", "connection refused", "connection error", "econnrefused", "econnreset", "unable to reach")),
)


def classify_text(text: str) -> Optional[str]:
    """Classify an arbitrary blob of stderr/stdout/event-message text.

    Returns the first matching error_type or None. Noise markers are
    exempted so transport fallback chatter never classifies as failure.
    """
    if not text:
        return None
    lower = text.lower()
    for marker in _NOISE_MARKERS:
        if marker in lower:
            return None
    for error_type, keywords in _CLASSIFIERS:
        for kw in keywords:
            if kw in lower:
                return error_type
    return None


# ---------------------------------------------------------------------------
# Event stream parsing
# ---------------------------------------------------------------------------

def parse_events(lines: List[str]) -> Dict:
    """Parse the `codex exec --json` NDJSON event stream (pure function).

    Tolerates unknown event types and non-JSON lines (the real stream
    contains WS reconnect/transport noise). Calibrated on the real
    0.148.0 smoke capture: agent_message text is at item.completed.item.text,
    and there is no session_id field in the stream — the parser falls back
    to thread.started.thread_id.

    Returns a dict with keys: text, session_id, model, error_type, events.
    error_type is None on success, one of the classification values on a
    fatal event, or "unknown" for an empty/no-completion stream.
    """
    text_parts: List[str] = []
    session_id: Optional[str] = None
    model: Optional[str] = None
    thread_id: Optional[str] = None
    event_error: Optional[str] = None
    events = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        events += 1
        if not isinstance(obj, dict):
            continue

        etype = obj.get("type")
        if etype == "thread.started":
            thread_id = obj.get("thread_id") or None
        elif etype == "item.completed":
            item = obj.get("item")
            if isinstance(item, dict):
                itype = item.get("type")
                if itype == "agent_message":
                    text = item.get("text") or ""
                    if text:
                        text_parts.append(text)
                elif itype == "error":
                    msg = item.get("message") or ""
                    if classify_text(msg) and event_error is None:
                        event_error = classify_text(msg)
                sid = item.get("session_id")
                if sid and session_id is None:
                    session_id = sid
            sid = obj.get("session_id")
            if sid and session_id is None:
                session_id = sid
        elif etype == "error":
            msg = obj.get("message") or ""
            if classify_text(msg) and event_error is None:
                event_error = classify_text(msg)
        # Unknown event types are tolerated and skipped.

        m = obj.get("model")
        if m and model is None:
            model = m

    if session_id is None:
        session_id = thread_id

    if text_parts:
        error_type = event_error
    elif event_error is not None:
        error_type = event_error
    else:
        # Empty stream / no completed item -> error marker.
        error_type = "unknown"

    return {
        "text": "\n".join(text_parts),
        "session_id": session_id,
        "model": model,
        "error_type": error_type,
        "events": events,
    }


# ---------------------------------------------------------------------------
# Subprocess execution
# ---------------------------------------------------------------------------

def resolve_codex() -> str:
    """Resolve the codex executable via PATH.

    Windows npm global installs ship a `codex.cmd` shim (no codex.exe), so
    a bare "codex" arg would fail CreateProcess. shutil.which honors PATHEXT
    and returns the full path; CPython wraps .cmd/.bat execution in cmd.exe.
    Raises FileNotFoundError when codex is not installed.
    """
    exe = shutil.which("codex")
    if not exe:
        raise FileNotFoundError(2, "codex not found on PATH", "codex")
    return exe


def _kill_tree(proc) -> None:
    """Kill a process; on Windows kill the whole tree (taskkill /T).

    codex ships as a .cmd shim on Windows, so the child is actually
    cmd.exe wrapping a node process tree that inherits the pipe handles.
    Killing only cmd.exe would leave the pipes open and hang the drain.
    """
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=10,
            )
            return
        proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _default_runner(argv, input_bytes, timeout, cwd):
    """Default runner: Popen + communicate with a timeout.

    On TimeoutExpired the process tree is killed (see _kill_tree) and the
    pipes are drained with a short grace period before raising, so a
    lingering grandchild can never hang the caller. Raises
    subprocess.TimeoutExpired / FileNotFoundError as appropriate.
    """
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=cwd,
    )
    try:
        out, err = proc.communicate(input_bytes, timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            proc.communicate(timeout=5)
        except Exception:
            pass  # pipes held by a killed grandchild; nothing to drain
        raise
    return (
        proc.returncode,
        out.decode("utf-8", "replace"),
        err.decode("utf-8", "replace"),
    )


def _is_git_repo(cwd: str, runner: Callable) -> bool:
    """True if cwd is inside a git work tree (or git is unavailable)."""
    try:
        rc, _out, _err = runner(
            ["git", "-C", cwd, "rev-parse", "--git-dir"], b"", 10, cwd
        )
        return rc == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # git unavailable -> be conservative and let codex decide.
        return False


def run_codex(
    prompt: str,
    model: Optional[str],
    timeout: int,
    cwd: Optional[str],
    skip_git_check: bool = False,
    runner: Optional[Callable] = None,
) -> Dict:
    """Run `codex exec --json` with the prompt on stdin. Returns a result
    dict with keys: status, text, session_id, model, elapsed_s, events,
    error_type, raw_lines.

    runner (injectable for tests) has the signature
        runner(argv, input_bytes, timeout, cwd) -> (returncode, stdout, stderr)
    and may raise subprocess.TimeoutExpired / FileNotFoundError.
    """
    if runner is None:
        runner = _default_runner

    cwd = cwd or os.getcwd()
    started = time.monotonic()
    try:
        argv = [resolve_codex(), "exec", "--json"]
        if model:
            argv += ["--model", model]
        in_repo = _is_git_repo(cwd, runner)
        if skip_git_check or not in_repo:
            argv.append("--skip-git-repo-check")
        rc, stdout_text, stderr_text = runner(
            argv, prompt.encode("utf-8"), timeout, cwd
        )
        lines = stdout_text.splitlines()
        parsed = parse_events(lines)
        error_type = parsed["error_type"]
        if rc != 0:
            # Process failed: prefer stderr/stdout classification over the
            # event-stream verdict (which is "unknown" on an empty stream).
            text_type = classify_text(stderr_text + "\n" + stdout_text)
            if text_type is not None:
                error_type = text_type
            if error_type is None:
                error_type = "unknown"
        if rc == 0 and parsed["text"] and error_type is None:
            status = "ok"
        else:
            status = "error"
        return {
            "status": status,
            "text": parsed["text"],
            "session_id": parsed["session_id"],
            "model": parsed["model"] or model,
            "elapsed_s": time.monotonic() - started,
            "events": parsed["events"],
            "error_type": error_type,
            "raw_lines": lines,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "text": "",
            "session_id": None,
            "model": model,
            "elapsed_s": time.monotonic() - started,
            "events": 0,
            "error_type": None,
            "raw_lines": [],
        }
    except FileNotFoundError as exc:
        return {
            "status": "error",
            "text": "",
            "session_id": None,
            "model": model,
            "elapsed_s": time.monotonic() - started,
            "events": 0,
            "error_type": "not_installed",
            "raw_lines": [],
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex_exec.py",
        description="Run `codex exec --json` with error classification.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="Run one codex prompt.")
    run_p.add_argument(
        "prompt_file",
        help="Prompt source: a file path, or '-' to read from stdin.",
    )
    run_p.add_argument("--model", default=None, help="Codex model to use.")
    run_p.add_argument(
        "--timeout", type=int, default=120, help="Timeout in seconds (default 120)."
    )
    run_p.add_argument("--out", default=None, help="Dir for text.txt + events.jsonl.")
    run_p.add_argument("--json-out", default=None, help="Path for the result JSON.")
    run_p.add_argument(
        "--skip-git-check",
        action="store_true",
        help="Force --skip-git-repo-check even inside a git repo.",
    )
    return parser


def _exit_code(result: Dict) -> int:
    if result.get("status") == "ok":
        return 0
    if result.get("error_type") == "not_installed":
        return 2
    if result.get("status") == "timeout":
        return 3
    if result.get("error_type") == "authentication":
        return 4
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "run":
        return 1
    if args.prompt_file == "-":
        prompt = sys.stdin.read()
    else:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8")

    result = run_codex(
        prompt,
        model=args.model,
        timeout=args.timeout,
        cwd=os.getcwd(),
        skip_git_check=args.skip_git_check,
    )

    out_json = json.dumps(result, ensure_ascii=False)
    print(out_json)

    if args.json_out:
        Path(args.json_out).write_text(out_json + "\n", encoding="utf-8")
    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "text.txt").write_text(result.get("text", ""), encoding="utf-8")
        raw = result.get("raw_lines", [])
        (out_dir / "events.jsonl").write_text(
            "\n".join(raw) + ("\n" if raw else ""), encoding="utf-8"
        )

    return _exit_code(result)


if __name__ == "__main__":
    sys.exit(main())
