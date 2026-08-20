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
            current = {"title": m.group(2).strip(), "time": ts, "text": ""}
            if not current["title"]:
                current = None
                continue
            entries.append(current)
            continue
        if current is None:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        current["text"] = (current["text"] + "\n" + stripped).strip()
        d = _DECISION.match(stripped)
        if d:
            current["pending"] = d.group(1).strip()
        a = _ALERT.match(stripped)
        if a:
            current["alerts"] = a.group(1).strip()
    entries.sort(key=lambda e: e["time"], reverse=True)
    latest = [{"title": e["title"], "time": e["time"].strftime("%Y-%m-%d %H:%M"),
               "time_text": e["time"].strftime("%m-%d %H:%M"), "text": e["text"]}
              for e in entries[:5]]
    pending = [{"title": e["title"], "time_text": e["time"].strftime("%m-%d %H:%M"),
                "text": e["pending"]} for e in entries if e.get("pending")]
    alerts = [{"title": e["title"], "time_text": e["time"].strftime("%m-%d %H:%M"),
               "text": e["alerts"]} for e in entries if e.get("alerts")]
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


def append_alert(messages_path: Path, text: str) -> bool:
    """追加自动告警留言；与最后一条重复则跳过。返回是否追加。"""
    existing = messages_path.read_text(encoding="utf-8") if messages_path.exists() else ""
    if f"- 告警：{text}" in existing.split("\n\n")[-1]:
        return False
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with messages_path.open("a", encoding="utf-8") as f:
        f.write(f"\n## {stamp} — 自动告警\n- 告警：{text}\n")
    return True
