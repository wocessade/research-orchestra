"""messages.md 解析与 HTML 生成（stdlib only）。

协议：每条以 `## YYYY-MM-DD HH:MM — 标题` 起始，正文行合并为 text；
`- 待决：X` 行进 pending，`- 告警：X` 行进 alerts。时间倒序渲染。
分工纪律：CLAUDE.md 挂账是权威清单，本文件只放增量事件与状态变化。
"""
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

_SECTION = re.compile(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) — (.+)$")
_DECISION = re.compile(r"^- 待决：(.+)$")
_ALERT = re.compile(r"^- 告警：(.+)$")


def parse_messages(text: str) -> dict:
    entries = []
    current = None
    for line in text.splitlines():
        m = _SECTION.match(line)
        if m:
            try:
                ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
            except ValueError:
                current = None
                continue
            current = {"title": m.group(2).strip(), "time": ts, "text": "",
                       "pending": [], "alerts": []}
            if not current["title"]:
                current = None
                continue
            entries.append(current)
            continue
        if line.startswith("## "):
            current = None
            continue
        if current is None:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        current["text"] = (current["text"] + "\n" + stripped).strip()
        d = _DECISION.match(stripped)
        if d:
            current["pending"].append(d.group(1).strip())
        a = _ALERT.match(stripped)
        if a:
            current["alerts"].append(a.group(1).strip())
    entries.sort(key=lambda e: e["time"], reverse=True)
    latest = [{"title": e["title"], "time": e["time"].strftime("%Y-%m-%d %H:%M"),
               "time_text": e["time"].strftime("%m-%d %H:%M"), "text": e["text"]}
              for e in entries[:5]]
    pending = [{"title": e["title"], "time_text": e["time"].strftime("%m-%d %H:%M"),
                "text": text} for e in entries for text in e["pending"]]
    alerts = [{"title": e["title"], "time_text": e["time"].strftime("%m-%d %H:%M"),
               "text": text} for e in entries for text in e["alerts"]]
    return {"latest": latest, "pending": pending, "alerts": alerts}


def build_messages_html(msgs: dict) -> str:
    parts = []
    for e in msgs["latest"]:
        parts.append(f"[{e['time']}] {e['title']}")
        if e["text"]:
            parts.append(e["text"])
    for d in msgs["pending"]:
        parts.append(f"[待决] {d['title']}：{d['text']}")
    for a in msgs["alerts"]:
        parts.append(f"[告警] {a['title']}：{a['text']}")
    body = "\n\n".join(parts) or "（暂无留言）"
    return ("<!doctype html><meta charset='utf-8'>"
            "<body style='margin:12px;font-family:monospace;white-space:pre-wrap'>"
            + html.escape(body) + "</body>")


def _ops_item(title: str, text: str, time_text: str = "系统") -> dict:
    return {"title": title, "time": "", "time_text": time_text, "text": text}


def derive_ops(status: dict | None, radar: dict | None,
               sync_note: str | None = None) -> dict:
    status = status or {}
    radar = radar or {}
    alerts: list[dict] = []
    latest: list[dict] = []
    four_b = str(status.get("4b") or "")
    walnut = str(status.get("walnut") or "")
    if "未配置 token" in four_b or "未配置 token" in walnut:
        alerts.append(_ops_item(
            "监控未鉴权",
            "ORCHESTRA_MONITOR_TOKEN 未生效，4B/核桃派状态无法刷新"))
    else:
        if "离线" in four_b:
            alerts.append(_ops_item("4B 离线", four_b))
        if "离线" in walnut:
            alerts.append(_ops_item("核桃派离线", walnut))
    note = sync_note if sync_note is not None else status.get("sync_note")
    if isinstance(note, str) and note.strip():
        bad = ("timeout" in note or "skipped" in note or "缺 bash" in note)
        m_res = re.search(r"results=(\d+)", note)
        m_log = re.search(r"logs=(\d+)", note)
        m_ex = re.search(r"exit=(\d+)", note)
        if m_res and int(m_res.group(1)) != 0:
            bad = True
        if m_log and int(m_log.group(1)) != 0:
            bad = True
        if m_ex and int(m_ex.group(1)) != 0:
            bad = True
        if bad:
            alerts.append(_ops_item("同步失败", note[:180]))
    if radar.get("available"):
        date = str(radar.get("date") or "")
        stages = radar.get("stages") or []
        n_top = len(radar.get("top5") or [])
        notify = next((s for s in stages if s.get("name") == "notify"), None)
        notify_st = (notify or {}).get("status") or "—"
        stamp = date[5:] if len(date) >= 10 else (date or "雷达")
        latest.append(_ops_item(
            f"雷达 {date}".strip(),
            f"notify {notify_st} · top5 {n_top}", stamp))
        for stage in stages:
            st = str(stage.get("status") or "")
            if st in ("failed", "error", "timeout"):
                alerts.append(_ops_item(
                    "雷达阶段失败",
                    f"{stage.get('name')} {st}"))
    last = status.get("last_task")
    if isinstance(last, dict) and last.get("slug"):
        latest.append(_ops_item(
            "最近任务", f"{last.get('slug')} {last.get('status') or ''}".strip()))
    elif isinstance(last, str) and last.strip():
        latest.append(_ops_item("最近任务", last.strip()))
    for att in status.get("attempts") or []:
        if att.get("status") == "failed":
            alerts.append(_ops_item("任务失败", str(att.get("task") or "attempt")))
    return {"latest": latest[:8], "pending": [], "alerts": alerts}


def _dedupe(items: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out = []
    for item in items:
        key = (item.get("title"), item.get("text"))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def merge_board(human: dict, status: dict | None = None,
                radar: dict | None = None, sync_note: str | None = None) -> dict:
    ops = derive_ops(status, radar, sync_note)
    pending = []
    for item in human.get("pending") or []:
        row = dict(item)
        row["dismissable"] = True
        pending.append(row)
    return {
        "latest": _dedupe((ops.get("latest") or []) + (human.get("latest") or []))[:8],
        "pending": pending[:24],
        "alerts": _dedupe((ops.get("alerts") or []) + (human.get("alerts") or []))[:24],
    }


def append_pending(messages_path: Path, text: str) -> None:
    cleaned = " ".join(str(text).split())
    if not cleaned:
        raise ValueError("空待决")
    if len(cleaned) > 200:
        raise ValueError("待决过长")
    existing = messages_path.read_text(encoding="utf-8") if messages_path.exists() else ""
    if any(p["text"] == cleaned for p in parse_messages(existing)["pending"]):
        return
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with messages_path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {stamp} — 待决（首页）\n- 待决：{cleaned}\n")


def _strip_empty_home_pending(text: str) -> str:
    """撤掉待决后清掉空的「待决（首页）」分节，避免留言栏留空标题。"""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    header = re.compile(r"^## \d{4}-\d{2}-\d{2} \d{2}:\d{2} — 待决（首页）\s*$")
    while i < len(lines):
        if header.match(lines[i].rstrip("\n")):
            j = i + 1
            chunk = []
            while j < len(lines) and not lines[j].startswith("## "):
                chunk.append(lines[j])
                j += 1
            body = "".join(chunk)
            if re.search(r"^- 待决：", body, re.M):
                out.append(lines[i])
                out.extend(chunk)
            i = j
            continue
        out.append(lines[i])
        i += 1
    cleaned = "".join(out)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip() + ("\n" if cleaned.strip() else "")


def remove_pending(messages_path: Path, text: str) -> None:
    cleaned = " ".join(str(text).split())
    if not cleaned:
        raise ValueError("空待决")
    content = messages_path.read_text(encoding="utf-8") if messages_path.exists() else ""
    target = f"- 待决：{cleaned}"
    lines = content.splitlines(keepends=True)
    new_lines = []
    removed = False
    for line in lines:
        if not removed and line.strip() == target:
            removed = True
            continue
        new_lines.append(line)
    if not removed:
        raise KeyError(cleaned)
    messages_path.write_text(
        _strip_empty_home_pending("".join(new_lines)), encoding="utf-8")


def append_alert(messages_path: Path, text: str) -> bool:
    """追加自动告警留言；最后一个原始分节含相同告警行则跳过。返回是否追加。"""
    existing = messages_path.read_text(encoding="utf-8") if messages_path.exists() else ""
    lines = existing.splitlines()
    section_starts = [i for i, line in enumerate(lines) if line.startswith("## ")]
    expected = f"- 告警：{text}"
    if section_starts:
        final_section = lines[section_starts[-1] + 1:]
        if any(line == expected for line in final_section):
            return False
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with messages_path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {stamp} — 自动告警\n- 告警：{text}\n")
    return True
