"""雨课堂监控状态 → 控制台（stdlib only）：exam_alert.json 告警 + exam_watch_beat.json 心跳。"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from feed_messages import append_alert

BEAT_STALE_S = 45 * 60  # 心跳 45 分钟未更新判失联（10min 轮询 + jitter 余量）
BEAT_FILE_STALE_S = 70 * 60  # beat 文件 70 分钟未刷新 = 本机 refresh 停摆（睡眠/断网），非 exam-watch 自身问题


def parse_exam_alert(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def exam_latest_title(exam_alert: dict) -> str:
    names = [str(n) for n in (exam_alert.get("exam_names") or []) if str(n).strip()]
    leaf = exam_alert.get("leaf_count")
    use = exam_alert.get("use_count")
    try:
        n = int(leaf or 0) or int(use or 0)
    except (TypeError, ValueError):
        n = 0
    detail = "、".join(names) if names else "请登录雨课堂查看"
    return f"雨课堂：考试已放出（{n}个）——{detail}"


def merge_exam_alert(human: dict, exam_alert: dict | None, messages_text: str) -> dict:
    out = {
        "latest": list(human.get("latest") or []),
        "pending": list(human.get("pending") or []),
        "alerts": list(human.get("alerts") or []),
    }
    if not exam_alert or not exam_alert.get("exam_found"):
        return out
    found_at = str(exam_alert.get("found_at") or "")
    if found_at and found_at in (messages_text or ""):
        return out
    title = exam_latest_title(exam_alert)
    item = {
        "title": title,
        "time": found_at,
        "time_text": found_at[5:16] if len(found_at) >= 16 else (found_at or "系统"),
        "text": "scp 后回看控制台",
    }
    out["latest"] = [item] + out["latest"]
    return out


def append_exam_marker(messages_path: Path, exam_alert: dict | None) -> bool:
    if not exam_alert:
        return False
    found_at = str(exam_alert.get("found_at") or "")
    existing = messages_path.read_text(encoding="utf-8") if messages_path.exists() else ""
    if found_at and found_at in existing:
        return False
    if exam_alert.get("cookie_expired") or exam_alert.get("source") == "auth":
        msg = str(exam_alert.get("message") or "雨课堂 cookie 已过期，请重新导出并上传 RK3528")
        if found_at:
            msg = f"{msg}（{found_at}）"
        return append_alert(messages_path, msg)
    if not exam_alert.get("exam_found"):
        return False
    title = exam_latest_title(exam_alert)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- 考试：{title}（found_at={found_at}；scp 后回看控制台）\n"
    with messages_path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {stamp} — {title}\n{line}")
    return True


def parse_exam_beat(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return data if isinstance(data, dict) else None


def _beat_time_text(beat: dict) -> str:
    ts = beat.get("last_check_ts")
    if isinstance(ts, (int, float)) and ts:
        return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
    last_check = str(beat.get("last_check") or "")
    m = re.match(r"(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})", last_check)
    if m:
        return f"{m.group(1)[5:]} {m.group(2)}"
    return "—"


def exam_beat_ops(beat: dict | None, beat_path: Path | None = None,
                  now: datetime | None = None,
                  stale_s: int = BEAT_STALE_S,
                  file_stale_s: int = BEAT_FILE_STALE_S) -> dict:
    """心跳 → 控制台派生条目。返回值结构与 derive_ops 条目一致。"""
    now = now or datetime.now()
    if not beat:
        # 无 beat = 盒子从未上报或未部署；RK3528 离线/同步失败由 derive_ops 覆盖，不重复刷屏
        return {"items": [], "item_type": "latest"}
    ts = beat.get("last_check_ts")
    if isinstance(ts, (int, float)) and ts and (now.timestamp() - ts) > stale_s:
        # 区分真中断与误报：beat 文件本身也很旧 = 本机 refresh 停摆（睡眠/断网）
        # 此时无法判断 exam-watch 状态，静默等待 refresh 恢复（RK3528 离线由 derive_ops 覆盖）
        if beat_path is not None:
            try:
                file_age = now.timestamp() - beat_path.stat().st_mtime
            except OSError:
                file_age = 0
            if file_age > file_stale_s:
                return {"items": [], "item_type": "alerts"}
        return {"items": [{"title": "雨课堂监控", "time": "", "time_text": _beat_time_text(beat),
                           "text": "心跳超时（RK3528 轮询中断）"}], "item_type": "alerts"}
    status = str(beat.get("status") or "")
    time_text = _beat_time_text(beat)
    if status in ("ok", "error"):
        st = "正常" if status == "ok" else "网络异常（下轮重试）"
        err = f" · {beat.get('last_error')}" if beat.get("last_error") else ""
        return {"items": [{"title": "雨课堂监控", "time": "", "time_text": time_text,
                           "text": f"{st} · 考试未放出{err}"}], "item_type": "latest"}
    if status == "done":
        if beat.get("cookie_expired"):
            return {"items": [{"title": "雨课堂监控", "time": "", "time_text": time_text,
                               "text": "cookie 已过期，请重新导出并上传 RK3528"}], "item_type": "alerts"}
        if beat.get("exam_found"):
            return {"items": [], "item_type": "latest"}
    return {"items": [{"title": "雨课堂监控", "time": "", "time_text": time_text,
                       "text": "状态未知"}], "item_type": "latest"}
