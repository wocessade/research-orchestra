"""usage-monitor GET /api/dashboard 拉取与状态聚合（stdlib only）。

只读消费既有端点；token 走环境变量。文案全部预计算为展示字符串。
"""
from __future__ import annotations

import http.client
import json
import time
import urllib.error
import urllib.request
from datetime import datetime

from feed_schedule import next_system_events, upcoming_personal

DEFAULT_MONITOR_API = "http://192.168.0.200:5000/api/orchestra"
FRESH_S = 120  # orchestra 最后上报 2 分钟内判在线
TIMEOUT_S = 5.0


def dashboard_url(api_url: str) -> str:
    if api_url.endswith("/api/orchestra"):
        return api_url[: -len("/api/orchestra")] + "/api/dashboard"
    return api_url.rstrip("/") + "/api/dashboard"


def fetch_dashboard(api_url: str, token: str | None,
                    timeout: float = TIMEOUT_S) -> tuple[dict | None, str | None]:
    """返回 (state, error)；token 未配返回 (None, 'no_token')。"""
    if not token:
        return None, "no_token"
    req = urllib.request.Request(dashboard_url(api_url),
                                 headers={"X-Monitor-Token": token})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if not isinstance(payload, dict):
                return None, "invalid_dashboard"
            return payload, None
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as exc:
        return None, str(exc)


def _rel(ts, now: float) -> str:
    if not isinstance(ts, (int, float)):
        return "—"
    if not ts:
        return "—"
    s = int(now - ts)
    if s < 60:
        return "刚刚"
    m = s // 60
    if m < 60:
        return f"{m}min 前"
    h = m // 60
    if h < 24:
        return f"{h}h 前"
    return f"{h // 24}d 前"


def _in(ts: float, now: float) -> str:
    s = int(ts - now)
    if s < 60:
        return "不足 1min"
    m = s // 60
    if m < 60:
        return f"{m}min 后"
    h = m // 60
    return f"{h}h{m % 60:02d}min 后"


def _device(online: bool, load1=None, mem_pct=None, age_text: str = "—") -> str:
    parts = ["在线" if online else "离线"]
    if load1 is not None:
        parts.append(f"load {load1}")
    if mem_pct is not None:
        parts.append(f"mem {mem_pct}%")
    if online and age_text != "—":
        parts.append(age_text)
    return " · ".join(parts)


def aggregate(dashboard: dict | None, fetch_error: str | None,
              schedule: dict | None, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    orch = (dashboard or {}).get("orchestra", {}) or {}
    lr = (dashboard or {}).get("orchestra_last_report", {}) or {}
    last_ts = lr.get("broker") or lr.get("ts")
    b_online = last_ts is not None and (now - last_ts) <= FRESH_S
    host = orch.get("host", {}) or {}
    self_status = (dashboard or {}).get("self_status", {}) or {}
    walnut_online = dashboard is not None
    walnut_load = self_status.get("load1")
    walnut_mem = self_status.get("mem_pct")
    nexts = []
    if schedule and schedule.get("system"):
        for n in next_system_events(schedule["system"], datetime.fromtimestamp(now)):
            nexts.append({"label": n["label"], "at": n["at"].strftime("%H:%M"),
                          "in_text": _in(n["at"].timestamp(), now)})
    if fetch_error == "no_token":
        four_b = walnut = "未配置 token"
    else:
        four_b = _device(b_online, host.get("load1"), host.get("mem_pct"),
                         _rel(last_ts, now))
        walnut = _device(walnut_online, walnut_load, walnut_mem)
    return {
        "generated_at": int(now),
        "generated_text": datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M"),
        "4b": four_b,
        "walnut": walnut,
        "windows": _device(True),
        "queue_len": orch.get("queue_len"),
        "active_tasks": orch.get("active_tasks"),
        "last_task": orch.get("last_task"),
        "last_sync_text": _rel(orch.get("last_sync"), now),
        "next": nexts,
        "upcoming_personal": (
            upcoming_personal(schedule.get("personal") or [],
                              datetime.fromtimestamp(now))
            if schedule else []),
        "recent_tasks": [{"slug": t.get("slug"), "status": t.get("status"),
                          "time_text": _rel(t.get("ts"), now)}
                         for t in orch.get("recent_tasks", [])[:8]],
        "degraded": bool(fetch_error),
        "degraded_reason": fetch_error,
    }
