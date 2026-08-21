"""控制台 glue 入口（stdlib only）。

子命令：
  refresh  聚合 status/radar/messages/双 ICS/HTML 到 out/（降级不报错）
  serve    stdlib http.server 静态服务 out/（127.0.0.1:3100，messages 热重）
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from feed_messages import append_alert, build_messages_html, parse_messages
from feed_radar import (
    build_digest_html,
    find_radar,
    scan_attempts,
    scan_experiments,
)
from feed_schedule import (
    build_ics,
    expand_personal,
    expand_system,
    parse_schedule,
)
from feed_status import DEFAULT_MONITOR_API, aggregate, fetch_dashboard

_WINDOW_BEFORE = timedelta(days=30)
_WINDOW_AFTER = timedelta(days=60)
DEFAULT_SSH_HOST = "192.168.0.250"
DEFAULT_SSH_USER = "liuxfs"
DEFAULT_REMOTE_ROOT = "/mnt/broker"


def _write_raw(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def _ssh_target() -> tuple[str, str, str]:
    host = os.environ.get("ORCHESTRA_SSH_HOST") or DEFAULT_SSH_HOST
    user = os.environ.get("ORCHESTRA_SSH_USER") or DEFAULT_SSH_USER
    remote = (os.environ.get("ORCHESTRA_REMOTE_ROOT") or DEFAULT_REMOTE_ROOT).rstrip("/")
    return host, user, remote


def _no_window_kwargs() -> dict:
    """Windows：隐藏 scp/ssh 控制台窗口。"""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def sync_pull(results_root: Path) -> str:
    """拉回 4B results/logs。Windows 优先 OpenSSH scp；否则 bash+sync_pull.sh。"""
    host, user, remote = _ssh_target()
    env = os.environ.copy()
    env["ORCHESTRA_SSH_HOST"] = host
    env["ORCHESTRA_SSH_USER"] = user
    env["ORCHESTRA_REMOTE_ROOT"] = remote
    scp = shutil.which("scp")
    bash = shutil.which("bash")
    prefer_scp = sys.platform == "win32" and scp
    hide = _no_window_kwargs()
    if prefer_scp or (scp and not bash):
        dest_results = Path(results_root)
        dest_logs = dest_results.parent / "logs"
        dest_results.mkdir(parents=True, exist_ok=True)
        dest_logs.mkdir(parents=True, exist_ok=True)
        try:
            r1 = subprocess.run(
                [scp, "-rq", f"{user}@{host}:{remote}/results/.", str(dest_results)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=300, **hide)
            r2 = subprocess.run(
                [scp, "-rq", f"{user}@{host}:{remote}/logs/.", str(dest_logs)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=300, **hide)
            err = " ".join(
                t.strip() for t in (r1.stderr, r2.stderr)
                if isinstance(t, str) and t.strip())
            note = (f"sync_pull scp results={r1.returncode} logs={r2.returncode} "
                    f"host={host}")
            if err:
                note += f" ({err[:180]})"
            return note
        except subprocess.TimeoutExpired:
            return "sync_pull scp timeout"
    if bash:
        script = Path(__file__).resolve().parent.parent / "scripts" / "sync_pull.sh"
        try:
            proc = subprocess.run(
                [bash, str(script)], cwd=str(script.parent),
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=300, env=env, **hide)
            err = proc.stderr.strip() if isinstance(proc.stderr, str) else ""
            note = f"sync_pull exit={proc.returncode} host={host}"
            if err:
                note += f" ({err[:180]})"
            return note
        except subprocess.TimeoutExpired:
            return "sync_pull timeout"
    return "sync_pull skipped（缺 bash 与 scp）"


def cmd_refresh(args) -> int:
    console = Path(args.console_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    notes = []

    try:
        sched = parse_schedule(
            (console / "console-schedule.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        sched = None
        notes.append(f"schedule 解析失败: {exc}")
        append_alert(console / "messages.md", f"日程解析失败（ICS 沿用上次产物）：{exc}")

    today = datetime.now().date()
    if sched is not None:
        _write_raw(
            out / "system.ics",
            build_ics(expand_system(sched["system"], today - _WINDOW_BEFORE,
                                    today + _WINDOW_AFTER), "System"))
        _write_raw(
            out / "personal.ics",
            build_ics(expand_personal(sched["personal"], today - _WINDOW_BEFORE,
                                      today + _WINDOW_AFTER), "Personal"))
    else:
        # 解析失败：已有 ICS 沿用；首次运行无产物时落空日历，保证八产物齐全
        for name, cal in (("system.ics", "System"), ("personal.ics", "Personal")):
            if not (out / name).exists():
                _write_raw(out / name, build_ics([], cal))

    api = os.environ.get("ORCHESTRA_MONITOR_API", DEFAULT_MONITOR_API)
    token = os.environ.get("ORCHESTRA_MONITOR_TOKEN")
    state, err = fetch_dashboard(api, token)
    status = aggregate(state, err, sched)
    results_root = Path(args.results_root)
    status["attempts"] = scan_attempts(results_root)
    status["experiments"] = scan_experiments(Path(args.research_root))
    (out / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.no_sync:
        notes.append(sync_pull(results_root))

    radar = find_radar(results_root)
    (out / "radar.json").write_text(
        json.dumps(radar, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "digest.html").write_text(build_digest_html(radar), encoding="utf-8")

    try:
        msgs = parse_messages(
            (console / "messages.md").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        msgs = {"latest": [], "pending": [], "alerts": []}
        notes.append(f"messages 读取失败: {exc}")
    (out / "messages.json").write_text(
        json.dumps(msgs, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "messages.html").write_text(build_messages_html(msgs), encoding="utf-8")

    with (out / "feed.log").open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} refresh; "
                + ("; ".join(notes) or "ok") + "\n")
    return 0


def cmd_serve(args) -> int:
    from feed_serve import make_server
    here = Path(__file__).resolve().parent
    server = make_server(
        Path(args.out_dir), args.bind, args.port,
        results_root=Path(getattr(args, "results_root", here.parent / "results")))
    if sys.stdout is not None:  # pythonw 无 stdout，print 会崩
        print(f"console feed serving {args.out_dir} "
              f"at http://{args.bind}:{args.port}/ "
              f"(UI + 八产物；Ctrl+C 退出)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv=None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(prog="console_feed")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh")
    r.add_argument("--console-dir", default=str(here))
    r.add_argument("--out-dir", default=str(here / "out"))
    r.add_argument("--results-root", default=str(here.parent / "results"))
    r.add_argument("--research-root", default=str(here.parents[1] / ".research"))
    r.add_argument("--no-sync", action="store_true")
    r.set_defaults(fn=cmd_refresh)
    s = sub.add_parser("serve")
    s.add_argument("--out-dir", default=str(here / "out"))
    s.add_argument("--bind", default="127.0.0.1")
    s.add_argument("--port", type=int, default=3100)
    s.add_argument("--results-root", default=str(here.parent / "results"))
    s.set_defaults(fn=cmd_serve)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
