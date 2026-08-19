#!/usr/bin/env python3
"""
【已停用】Claude Code Hooks 状态上报脚本

2026-08：用户已取消全部 CC hooks；settings 不再调用本脚本。
目录保留便于手动调试或日后恢复；勿再写入 Claude settings.json 的 hooks。

用法:
  python reporter.py <status> [flags]

  （历史）CC hooks 会把 JSON 打到 stdin (含 cost / context_window)。
  本脚本合并 argv + stdin 后 POST 到树莓派。

状态值:
  idle | running | waiting | error | compact-warning

Flags:
  --session-start / --session-end
  --context N / --round N / --bump-round
  (命令行可覆盖 stdin 同名字段)

环境变量:
  PI_MONITOR_URL    默认 http://liuxfs.local:5000
  MONITOR_TOKEN     与 Pi 端一致时启用鉴权
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time

import requests

PI_URL = os.getenv("PI_MONITOR_URL", "http://liuxfs.local:5000").rstrip("/")
MONITOR_TOKEN = os.getenv("MONITOR_TOKEN", "")


def get_hostname() -> str:
    return os.getenv("COMPUTERNAME", socket.gethostname())


def report(payload: dict) -> None:
    headers = {}
    if MONITOR_TOKEN:
        headers["X-Monitor-Token"] = MONITOR_TOKEN

    url = f"{PI_URL}/api/status"
    last_err = None
    # 短重试: 覆盖瞬时网络抖动 / 旧版同步刷屏阻塞
    for attempt in range(3):
        try:
            resp = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=5,
            )
            if resp.status_code == 401:
                print(
                    "[reporter] Unauthorized — set MONITOR_TOKEN to match Pi",
                    file=sys.stderr,
                )
                return
            if resp.status_code == 200:
                return
            print(
                f"[reporter] Warning: Pi returned {resp.status_code}",
                file=sys.stderr,
            )
            last_err = f"http_{resp.status_code}"
        except requests.exceptions.ConnectionError as e:
            last_err = e
            print(f"[reporter] Cannot reach Pi at {PI_URL}", file=sys.stderr)
        except requests.exceptions.Timeout as e:
            last_err = e
            print("[reporter] Pi timeout", file=sys.stderr)
        except Exception as e:
            last_err = e
            print(f"[reporter] Error: {e}", file=sys.stderr)
            return

        if attempt < 2:
            time.sleep(0.4 * (attempt + 1))

    if last_err is not None:
        print(f"[reporter] Gave up after retries ({last_err})", file=sys.stderr)


def _read_stdin_hook() -> dict:
    """读取 CC hooks 注入的 JSON (无输入/非 JSON 时返回 {})."""
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
        if not raw or not raw.strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _merge_hook_fields(payload: dict, hook: dict) -> None:
    """从 hooks stdin 提取会话费用 / 上下文% / session_id / model."""
    if not hook:
        return

    sid = hook.get("session_id") or hook.get("sessionId")
    if sid:
        payload["session_id"] = sid

    model = hook.get("model")
    if isinstance(model, dict):
        name = model.get("display_name") or model.get("id")
        if name:
            payload["model"] = name
    elif isinstance(model, str):
        payload["model"] = model

    cost = hook.get("cost")
    if isinstance(cost, dict) and cost.get("total_cost_usd") is not None:
        try:
            payload["session_cost_usd"] = float(cost["total_cost_usd"])
        except (TypeError, ValueError):
            pass
    elif hook.get("total_cost_usd") is not None:
        try:
            payload["session_cost_usd"] = float(hook["total_cost_usd"])
        except (TypeError, ValueError):
            pass

    # 已由命令行指定 context 则不覆盖
    if "context_percent" in payload:
        return

    ctx = hook.get("context_window") or hook.get("contextWindow") or {}
    if not isinstance(ctx, dict):
        return
    try:
        used = float(
            ctx.get("total_input_tokens")
            or ctx.get("current_usage")
            or ctx.get("used_tokens")
            or 0
        )
        size = float(
            ctx.get("context_window_size")
            or ctx.get("size")
            or ctx.get("max_tokens")
            or 0
        )
        if size > 0:
            payload["context_percent"] = max(0, min(100, round(100.0 * used / size)))
    except (TypeError, ValueError):
        pass


def _parse_args(argv: list[str]) -> dict:
    if len(argv) < 2:
        print(
            "Usage: python reporter.py <status> "
            "[--session-start] [--session-end] "
            "[--context N] [--round N] [--bump-round]",
            file=sys.stderr,
        )
        sys.exit(1)

    status = argv[1]
    payload: dict = {
        "status": status,
        "timestamp": time.time(),
        "host": get_hostname(),
    }

    args = argv[2:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--session-start":
            payload["session_start"] = True
        elif a == "--session-end":
            payload["session_end"] = True
        elif a == "--bump-round":
            payload["bump_round"] = True
        elif a == "--context" and i + 1 < len(args):
            payload["context_percent"] = args[i + 1]
            i += 1
        elif a == "--round" and i + 1 < len(args):
            payload["round"] = args[i + 1]
            i += 1
        elif a.startswith("--context="):
            payload["context_percent"] = a.split("=", 1)[1]
        elif a.startswith("--round="):
            payload["round"] = a.split("=", 1)[1]
        i += 1

    return payload


def main() -> None:
    payload = _parse_args(sys.argv)
    hook = _read_stdin_hook()
    _merge_hook_fields(payload, hook)
    report(payload)


if __name__ == "__main__":
    main()
