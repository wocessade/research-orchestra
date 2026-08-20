"""console-schedule.toml 解析、事件展开与 ICS 生成（stdlib only）。

system 段是 4B systemd timer 的镜像声明，权威在 Pi `systemctl list-timers`；
ICS 生成显式事件实例（窗口 前30天~后60天），floating 本地时间（无 TZ 后缀）。
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_DOW = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_KNOWN_SYSTEM = ("radar", "cold_backup", "nas_backup", "housekeeping")
_SYSTEM_TITLES = {"radar": "夜间雷达", "cold_backup": "冷备到核桃派",
                  "nas_backup": "NAS 盘内备份", "housekeeping": "周日整理"}
_DEFAULT_DURATION = timedelta(minutes=30)
WINDOW_BEFORE = timedelta(days=30)
WINDOW_AFTER = timedelta(days=60)
UPCOMING_DAYS = 14
_HEADER = (
    "# 日程单一事实源。system 段 = 4B systemd timer 的镜像声明（权威在 Pi systemctl list-timers，\n"
    "# deploy/运维改动 timer 时同步改本文件）；personal 段 = 手录日程。\n"
)
_SYSTEM_COMMENTS = {
    "radar": "每日夜间雷达注入（orchestra-timer）",
    "cold_backup": "每日冷备到核桃派（orchestra-backup）",
    "nas_backup": "每日 NAS 盘内备份（nas-backup）",
}


@dataclass(frozen=True)
class Event:
    start: datetime
    end: datetime
    summary: str
    uid: str
    note: str = ""
    done: bool = False
    series_id: str = ""
    repeat: str = ""


def parse_schedule(text: str) -> dict:
    """解析 console-schedule.toml；结构非法抛 ValueError（带说明）。"""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"schedule TOML 解析失败: {exc}") from exc
    system = data.get("system", {})
    personal = data.get("personal", [])
    if not isinstance(system, dict) or not isinstance(personal, list):
        raise ValueError("system 必须是表、personal 必须是数组")
    _validate_system(system)
    return {"system": system, "personal": _assign_ids(
        [_parse_personal(p) for p in personal])}


def _validate_system(system: dict) -> None:
    for key, val in system.items():
        if key not in _KNOWN_SYSTEM:
            raise ValueError(f"未知 system 项: {key}（允许 {sorted(_KNOWN_SYSTEM)}）")
        if key == "housekeeping":
            ok = (isinstance(val, dict)
                  and _TIME.fullmatch(str(val.get("time", "")))
                  and val.get("dow") in _DOW)
            if not ok:
                raise ValueError("housekeeping 必须是 { time='HH:MM', dow='mon'..'sun' }")
        elif not isinstance(val, str) or not _TIME.fullmatch(val):
            raise ValueError(f"{key} 必须是 'HH:MM' 字符串")


def _parse_personal(item: dict) -> dict:
    if not isinstance(item, dict):
        raise ValueError(f"personal 条目必须是表: {item!r}")
    d = item.get("date")
    if isinstance(d, datetime):
        d = d.date()
    elif isinstance(d, str):
        try:
            d = date.fromisoformat(d)
        except ValueError:
            d = None
    if not isinstance(d, date):
        raise ValueError(f"personal 缺 date 或类型错误: {item!r}")
    t = item.get("time")
    if not isinstance(t, str) or not _TIME.fullmatch(t):
        raise ValueError(f"personal 缺 time('HH:MM') 或格式错误: {item!r}")
    hh, mm = map(int, t.split(":"))
    title = str(item.get("title", "")).strip()
    if not title:
        raise ValueError(f"personal 缺 title: {item!r}")
    return {"date": d, "time": time(hh, mm), "title": title,
            "note": str(item.get("note", "")).strip(),
            "repeat": _parse_repeat(item.get("repeat")),
            "done": bool(item.get("done", False)),
            "done_dates": _parse_done_dates(item.get("done_dates"))}


def _parse_repeat(value) -> str:
    if value in (None, "", False):
        return ""
    text = str(value).strip().lower()
    if text == "weekly":
        return "weekly"
    raise ValueError("repeat 只允许 weekly 或留空")


def _parse_done_dates(value) -> list:
    if value in (None, "", False):
        return []
    if not isinstance(value, list):
        raise ValueError("done_dates 必须是日期数组")
    out = []
    for item in value:
        if isinstance(item, datetime):
            out.append(item.date())
        elif isinstance(item, date):
            out.append(item)
        elif isinstance(item, str):
            try:
                out.append(date.fromisoformat(item))
            except ValueError as exc:
                raise ValueError(f"done_dates 含非法日期: {item}") from exc
        else:
            raise ValueError(f"done_dates 含非法项: {item!r}")
    return sorted(set(out))


def personal_uid(item: dict) -> str:
    dt = datetime.combine(item["date"], item["time"])
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", item["title"])[:24].strip("-").lower()
    return f"personal-{dt:%Y%m%dT%H%M}-{slug or 'event'}"


def _assign_ids(personal: list) -> list:
    seen: dict[str, int] = {}
    out = []
    for item in personal:
        base = personal_uid(item)
        n = seen.get(base, 0)
        seen[base] = n + 1
        ident = base if n == 0 else f"{base}-{n + 1}"
        row = dict(item)
        row["id"] = ident
        out.append(row)
    return out


def _toml_str(s: str) -> str:
    return '"' + (s.replace("\\", "\\\\").replace('"', '\\"')
                  .replace("\n", "\\n").replace("\r", "")) + '"'


def dump_schedule(sched: dict) -> str:
    """序列化日程；不写 personal id（由 date/time/title 派生）。"""
    lines = [_HEADER.rstrip(), "", "[system]"]
    system = sched.get("system") or {}
    for key in ("radar", "cold_backup", "nas_backup"):
        if key in system:
            pad = " " * max(1, 23 - len(key) - len(str(system[key])))
            lines.append(f'{key} = "{system[key]}"{pad}# {_SYSTEM_COMMENTS[key]}')
    hs = system.get("housekeeping")
    if hs:
        lines.append(
            f'housekeeping = {{ time = "{hs["time"]}", dow = "{hs["dow"]}" }}'
            "   # 周日 housekeeping")
    lines.append("")
    for item in sched.get("personal") or []:
        lines.append("[[personal]]")
        lines.append(f'date = "{item["date"].isoformat()}"')
        lines.append(f'time = "{item["time"].strftime("%H:%M")}"')
        lines.append(f"title = {_toml_str(item['title'])}")
        if item.get("note"):
            lines.append(f"note = {_toml_str(item['note'])}")
        if item.get("repeat") == "weekly":
            lines.append('repeat = "weekly"')
        if item.get("done"):
            lines.append("done = true")
        dates = item.get("done_dates") or []
        if dates:
            joined = ", ".join(f'"{d.isoformat()}"' for d in dates)
            lines.append(f"done_dates = [{joined}]")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_schedule(path, sched: dict) -> None:
    from pathlib import Path
    text = dump_schedule(sched)
    parse_schedule(text)  # 落盘前自检，坏结构不覆盖
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def rebuild_personal_ics(out_dir, sched: dict) -> None:
    from pathlib import Path
    today = datetime.now().date()
    text = build_ics(
        expand_personal(sched["personal"], today - WINDOW_BEFORE,
                        today + WINDOW_AFTER), "Personal")
    (Path(out_dir) / "personal.ics").write_text(text, encoding="utf-8", newline="")


def new_personal(raw: dict) -> dict:
    return _parse_personal({
        "date": raw.get("date"),
        "time": raw.get("time"),
        "title": raw.get("title"),
        "note": raw.get("note", ""),
        "repeat": raw.get("repeat", ""),
        "done": raw.get("done", False),
        "done_dates": raw.get("done_dates"),
    })


def add_personal(sched: dict, raw: dict) -> dict:
    item = new_personal(raw)
    return {"system": sched["system"],
            "personal": _assign_ids(list(sched["personal"]) + [item])}


def update_personal(sched: dict, ident: str, raw: dict) -> dict:
    item = new_personal(raw)
    personal = list(sched["personal"])
    for i, old in enumerate(personal):
        if old.get("id") == ident:
            if "done" not in raw:
                item["done"] = old.get("done", False)
            if "done_dates" not in raw:
                item["done_dates"] = list(old.get("done_dates") or [])
            personal[i] = item
            return {"system": sched["system"], "personal": _assign_ids(personal)}
    raise KeyError(ident)


def toggle_personal_done(sched: dict, ident: str, on_date: str | None = None) -> dict:
    personal = list(sched["personal"])
    for i, old in enumerate(personal):
        if old.get("id") != ident:
            continue
        item = dict(old)
        if item.get("repeat") == "weekly":
            if not on_date:
                raise ValueError("周重复完成需要 date")
            try:
                day = date.fromisoformat(on_date)
            except ValueError as exc:
                raise ValueError("date 必须是 YYYY-MM-DD") from exc
            dates = set(item.get("done_dates") or [])
            if day in dates:
                dates.remove(day)
            else:
                dates.add(day)
            item["done_dates"] = sorted(dates)
        else:
            item["done"] = not bool(item.get("done"))
        personal[i] = item
        return {"system": sched["system"], "personal": _assign_ids(personal)}
    raise KeyError(ident)


def delete_personal(sched: dict, ident: str) -> dict:
    personal = [p for p in sched["personal"] if p.get("id") != ident]
    if len(personal) == len(sched["personal"]):
        raise KeyError(ident)
    return {"system": sched["system"], "personal": _assign_ids(personal)}


def personal_public(item: dict) -> dict:
    return {
        "id": item["id"],
        "date": item["date"].isoformat(),
        "time": item["time"].strftime("%H:%M"),
        "title": item["title"],
        "note": item.get("note", ""),
        "repeat": item.get("repeat") or "",
        "done": bool(item.get("done")),
        "done_dates": [d.isoformat() for d in (item.get("done_dates") or [])],
    }


def expand_system(system: dict, start: date, end: date) -> list[Event]:
    events = []
    d = start
    while d <= end:
        for key in ("radar", "cold_backup", "nas_backup"):
            if key in system:
                hh, mm = map(int, system[key].split(":"))
                st = datetime(d.year, d.month, d.day, hh, mm)
                events.append(Event(st, st + _DEFAULT_DURATION, _SYSTEM_TITLES[key],
                                    f"sys-{key}-{d:%Y%m%d}"))
        hs = system.get("housekeeping")
        if hs and _DOW[hs["dow"]] == d.weekday():
            hh, mm = map(int, hs["time"].split(":"))
            st = datetime(d.year, d.month, d.day, hh, mm)
            events.append(Event(st, st + _DEFAULT_DURATION, _SYSTEM_TITLES["housekeeping"],
                                f"sys-housekeeping-{d:%Y%m%d}"))
        d += timedelta(days=1)
    return events


def expand_personal(personal: list, start: date, end: date) -> list[Event]:
    events = []
    for item in personal:
        series = item.get("id") or personal_uid(item)
        note = item.get("note") or ""
        if item.get("repeat") == "weekly":
            d = item["date"]
            while d < start:
                d += timedelta(days=7)
            done_set = set(item.get("done_dates") or [])
            while d <= end:
                dt = datetime.combine(d, item["time"])
                events.append(Event(
                    dt, dt + timedelta(hours=1), item["title"],
                    f"{series}-{d:%Y%m%d}", note,
                    d in done_set, series, "weekly"))
                d += timedelta(days=7)
        else:
            dt = datetime.combine(item["date"], item["time"])
            if start <= dt.date() <= end:
                events.append(Event(
                    dt, dt + timedelta(hours=1), item["title"],
                    series, note, bool(item.get("done")), series, ""))
    return events


def _escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def build_ics(events: list[Event], cal_name: str) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//ResearchOrchestra//Console//CN", f"X-WR-CALNAME:{cal_name}"]
    for ev in sorted(events, key=lambda e: e.start):
        lines += ["BEGIN:VEVENT", f"UID:{ev.uid}",
                  f"DTSTART:{ev.start:%Y%m%dT%H%M%S}",
                  f"DTEND:{ev.end:%Y%m%dT%H%M%S}",
                  f"SUMMARY:{_escape(ev.summary)}"]
        if ev.note:
            lines.append(f"DESCRIPTION:{_escape(ev.note)}")
        if ev.done:
            lines.append("STATUS:COMPLETED")
        if ev.series_id:
            lines.append(f"X-ORCHESTRA-SERIES:{ev.series_id}")
        if ev.repeat:
            lines.append(f"X-ORCHESTRA-REPEAT:{ev.repeat}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def next_system_events(system: dict, now: datetime) -> list[dict]:
    """每个 system 项计算下一次触发时刻（严格晚于 now），按时间升序。"""
    result = []
    for key, label in (("radar", "雷达"), ("cold_backup", "冷备到核桃派"),
                       ("nas_backup", "NAS 盘内备份"), ("housekeeping", "周日整理")):
        if key not in system:
            continue
        if key == "housekeeping":
            spec = system[key]
            hh, mm = map(int, spec["time"].split(":"))
            days_ahead = (_DOW[spec["dow"]] - now.weekday()) % 7
            nxt = (now + timedelta(days=days_ahead)).replace(
                hour=hh, minute=mm, second=0, microsecond=0)
            if nxt <= now:
                nxt += timedelta(days=7)
        else:
            hh, mm = map(int, system[key].split(":"))
            nxt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if nxt <= now:
                nxt += timedelta(days=1)
        result.append({"label": label, "at": nxt})
    result.sort(key=lambda r: r["at"])
    return result


def upcoming_personal(personal: list, now: datetime,
                      days: int = UPCOMING_DAYS) -> list[dict]:
    """未完成个人事项，窗口为现在起 days 天（含今天尚未开始的）。"""
    if days < 0 or not personal:
        return []
    start = now.date()
    end = start + timedelta(days=days)
    rows = []
    for ev in expand_personal(personal, start, end):
        if ev.done or ev.start < now:
            continue
        days_left = (ev.start.date() - now.date()).days
        if days_left <= 0:
            urgency = "due-0"
        elif days_left <= 2:
            urgency = "due-2"
        elif days_left <= 7:
            urgency = "due-7"
        else:
            urgency = "due-14"
        if days_left == 0:
            in_text = f"今天 {ev.start:%H:%M}"
        elif days_left == 1:
            in_text = "明天"
        else:
            in_text = f"{days_left} 天后"
        rows.append({
            "title": ev.summary,
            "at": ev.start.strftime("%Y-%m-%d %H:%M"),
            "in_text": in_text,
            "note": ev.note,
            "days_left": days_left,
            "urgency": urgency,
        })
    rows.sort(key=lambda r: (r["at"], r["title"]))
    return rows
