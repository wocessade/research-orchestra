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


@dataclass(frozen=True)
class Event:
    start: datetime
    end: datetime
    summary: str
    uid: str
    note: str = ""


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
    return {"system": system, "personal": [_parse_personal(p) for p in personal]}


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
            "note": str(item.get("note", "")).strip()}


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
        dt = datetime.combine(item["date"], item["time"])
        if start <= dt.date() <= end:
            slug = re.sub(r"\W+", "-", item["title"])[:24] or "event"
            events.append(Event(dt, dt + timedelta(hours=1), item["title"],
                                f"personal-{dt:%Y%m%d}-{slug}", item["note"]))
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
