#!/usr/bin/env python3
"""带持久状态的雷达邮件通知；遇到不确定发送状态时拒绝自动重发。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import artifact_validators

NOT_SENT_EXIT_CODE = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, value) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _attempt_number(path: Path) -> int:
    try:
        return int(path.name.split("-", 1)[1])
    except (IndexError, ValueError):
        return -1


def latest_successful_render(root: Path) -> Path:
    for attempt in sorted(root.glob("attempt-*"), key=_attempt_number, reverse=True):
        try:
            state = json.loads((attempt / "state.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if state.get("status") == "done" and not artifact_validators.validate_render(attempt):
            return attempt
    raise ValueError(f"no validated render attempt under {root}")


def notify(render_root: Path, state_root: Path, output_dir: Path, date: str,
           sender: Path) -> int:
    attempt = latest_successful_render(render_root)
    digest = attempt / "digest.txt"
    digest_sha = hashlib.sha256(digest.read_bytes()).hexdigest()
    state_root.mkdir(parents=True, exist_ok=True)
    state_path = state_root / f"radar-{date}.json"
    lock_path = state_root / f"radar-{date}.lock"
    output_path = output_dir / "notification.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    if state_path.exists():
        try:
            prior = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prior = {"status": "unknown", "reason": "corrupt persistent state"}
        if prior.get("status") == "sent":
            _write_json(output_path, {
                "status": "skipped", "reason": "already_sent",
                "digest_sha256": digest_sha,
            })
            return 0
        if prior.get("status") in ("sending", "unknown"):
            unknown = dict(prior, status="unknown", reason="previous send outcome is ambiguous")
            _write_json(state_path, unknown)
            _write_json(output_path, unknown)
            return 2

    if not sender.is_file():
        raise ValueError(f"email sender not found: {sender}")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    except FileExistsError:
        if state_path.exists():
            # state 已写（sending 写于 subprocess 之前）⟹ 无法证明本次未发送 ⟹ 拒绝接管
            unknown = {
                "status": "unknown", "reason": "notification lock already exists",
                "digest_sha256": digest_sha,
            }
            _write_json(output_path, unknown)
            return 2
        # state 缺失 ⟹ "sending" 从未写入 ⟹ 发送器从未启动 ⟹ 可证明未发送 ⟹
        # 安全接管：删除 stale 锁后重试本次发送
        print(f"taking over stale notification lock: {lock_path}", file=sys.stderr)
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
        except FileExistsError:
            unknown = {
                "status": "unknown", "reason": "notification lock already exists",
                "digest_sha256": digest_sha,
            }
            _write_json(output_path, unknown)
            return 2

    sending = {
        "status": "sending",
        "date": date,
        "digest_sha256": digest_sha,
        "idempotency_key": f"radar-{date}-{digest_sha[:16]}",
        "started_at": _now(),
    }
    _write_json(state_path, sending)
    try:
        try:
            proc = subprocess.run(
                [sys.executable, str(sender), f"文献日报 {date}", str(digest)],
                text=True, capture_output=True, check=False,
            )
        except OSError as exc:
            not_sent = dict(
                sending, status="not_sent", reason=f"sender was not started: {exc}",
            )
            _write_json(state_path, not_sent)
            _write_json(output_path, not_sent)
            return 1
        if proc.returncode != 0:
            if proc.returncode == NOT_SENT_EXIT_CODE:
                not_sent = dict(
                    sending, status="not_sent",
                    reason=f"sender explicitly reported not sent (exit {proc.returncode})",
                    stderr=proc.stderr[-1000:],
                )
                _write_json(state_path, not_sent)
                _write_json(output_path, not_sent)
                return 1
            unknown = dict(
                sending, status="unknown", reason=f"sender exit {proc.returncode}",
                stderr=proc.stderr[-1000:],
            )
            _write_json(state_path, unknown)
            _write_json(output_path, unknown)
            return 2
        sent = dict(sending, status="sent", sent_at=_now(), reason=None)
        _write_json(state_path, sent)
        _write_json(output_path, sent)
        return 0
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-root", required=True)
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--date", required=True)
    parser.add_argument("--sender", default="/usr/local/bin/send_email.py")
    args = parser.parse_args(argv)
    return notify(
        Path(args.render_root), Path(args.state_root), Path(args.output_dir),
        args.date, Path(args.sender),
    )


if __name__ == "__main__":
    raise SystemExit(main())
