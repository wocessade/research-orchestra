#!/usr/bin/env python3
"""
Claude Code Hooks 状态上报脚本

被 CC hooks 调用，将运行状态通过 HTTP POST 发送到树莓派后端。

用法:
  python reporter.py <status> [flags]

状态值:
  idle            - CC 空闲
  running         - CC 运行中 (工具调用或模型推理)
  waiting         - CC 等待用户操作 (权限确认 / MCP elicitation)
  error           - API 错误
  compact-warning - 上下文即将压缩 (不改变 LED 状态)

Flags:
  --session-start  标记会话开始
  --session-end    标记会话结束

环境变量:
  PI_MONITOR_URL   树莓派后端地址 (默认 http://raspberrypi.local:5000)
"""

import requests
import sys
import os
import time
import socket


# 树莓派地址: 环境变量 > raspberrypi.local > 手动修改
PI_URL = os.getenv("PI_MONITOR_URL", "http://raspberrypi.local:5000")


def get_hostname() -> str:
    return os.getenv("COMPUTERNAME", socket.gethostname())


def report(payload: dict) -> None:
    """发送状态到树莓派, 静默处理所有错误"""
    try:
        resp = requests.post(
            f"{PI_URL}/api/status",
            json=payload,
            timeout=5,
        )
        if resp.status_code != 200:
            print(
                f"[reporter] Warning: Pi returned {resp.status_code}",
                file=sys.stderr,
            )
    except requests.exceptions.ConnectionError:
        print(f"[reporter] Cannot reach Pi at {PI_URL}", file=sys.stderr)
    except requests.exceptions.Timeout:
        print(f"[reporter] Pi timeout", file=sys.stderr)
    except Exception as e:
        print(f"[reporter] Error: {e}", file=sys.stderr)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python reporter.py <status> [flags]", file=sys.stderr)
        sys.exit(1)

    status = sys.argv[1]

    payload = {
        "status": status,
        "timestamp": time.time(),
        "host": get_hostname(),
    }

    if "--session-start" in sys.argv:
        payload["session_start"] = True
    if "--session-end" in sys.argv:
        payload["session_end"] = True

    report(payload)


if __name__ == "__main__":
    main()
