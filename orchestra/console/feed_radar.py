"""本地 results/ 与 .research 扫描（stdlib only）。

兼容两种雷达布局：SOL 四阶段（T-YYYYMMDD-{10-fetch,20-rank,30-render,40-notify}）
与旧单体（T-YYYYMMDD-nightly-radar）；top5.json 兼容 SOL dict 格式与旧三元组格式。
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

_DIR = re.compile(
    r"^T-(\d{8})-(?:nightly-radar-(10-fetch|20-rank|30-render|40-notify)"
    r"|(10-fetch|20-rank|30-render|40-notify)|nightly-radar)$"
)
_STAGES = (("10-fetch", "fetch"), ("20-rank", "rank"),
           ("30-render", "render"), ("40-notify", "notify"))
_FRONT = re.compile(r"^(\w+):\s*(.+)$")


def _state(path: Path) -> dict:
    try:
        return json.loads((path / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def best_attempt(task_dir: Path) -> Path | None:
    attempts = sorted(
        (p for p in task_dir.glob("attempt-*")
         if re.fullmatch(r"attempt-(\d+)", p.name) and (p / "state.json").exists()),
        key=lambda p: int(re.fullmatch(r"attempt-(\d+)", p.name).group(1)), reverse=True)
    return attempts[0] if attempts else None


def _pick_artifact_attempt(task_dir: Path) -> Path | None:
    """优先 done 且有 digest.txt 的 attempt；否则第一个有 digest.txt 的。"""
    attempts = sorted(
        (p for p in task_dir.glob("attempt-*")
         if re.fullmatch(r"attempt-(\d+)", p.name)),
        key=lambda p: int(re.fullmatch(r"attempt-(\d+)", p.name).group(1)), reverse=True)
    for att in attempts:
        if (att / "digest.txt").exists() and _state(att).get("status") == "done":
            return att
    for att in attempts:
        if (att / "digest.txt").exists():
            return att
    return None


def _normalize_top5(top5_path: Path, papers_by_id: dict) -> list[dict]:
    try:
        raw = json.loads(top5_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    rows = []
    for item in raw:
        if isinstance(item, dict):  # SOL 格式
            aid = item.get("arxiv_id")
            if not isinstance(aid, str) or not aid.strip():
                continue
            rows.append({"id": aid, "title": item.get("title") or papers_by_id.get(aid, {}).get("title") or aid,
                         "total": item.get("total")})
        elif (isinstance(item, (list, tuple)) and len(item) >= 2
              and isinstance(item[0], (int, float)) and isinstance(item[1], str)
              and item[1].strip()):
            rows.append({"id": item[1], "title": papers_by_id.get(item[1], {}).get("title") or item[1],
                         "total": item[0]})
    return rows


def _index_radar(root: Path) -> dict:
    by_date = {}
    if not root.is_dir():
        return by_date
    for p in root.iterdir():
        m = _DIR.match(p.name)
        if p.is_dir() and m:
            slug = m.group(2) or m.group(3) or "nightly-radar"
            by_date.setdefault(m.group(1), {})[slug] = p
    return by_date


def _iso_date(compact: str) -> str:
    return f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"


def _compact_date(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) == 8 else None


def list_radar_dates(root: Path, limit: int = 14) -> list[dict]:
    """最近若干期日报索引（不含正文），新→旧。"""
    by_date = _index_radar(root)
    rows = []
    for compact in sorted(by_date, reverse=True)[:limit]:
        day = by_date[compact]
        four = any(k in day for k in ("10-fetch", "20-rank", "30-render", "40-notify"))
        art_dir = day.get("30-render") if four else day.get("nightly-radar")
        att = _pick_artifact_attempt(art_dir) if art_dir else None
        rows.append({
            "date": _iso_date(compact),
            "mode": "four-stage" if four else "legacy",
            "has_digest": bool(att and (att / "digest.txt").exists()),
        })
    return rows


def _radar_from_day(compact: str, day: dict) -> dict:
    if "10-fetch" in day or "20-rank" in day or "30-render" in day or "40-notify" in day:
        mode = "four-stage"
        stages = []
        for slug, label in _STAGES:
            row = {"name": label}
            if slug in day:
                att = best_attempt(day[slug])
                st = _state(att) if att else {}
                row.update({"status": st.get("status", "missing"),
                            "time": st.get("started_at")})
            else:
                row.update({"status": "missing", "time": None})
            stages.append(row)
        art_dir = day.get("30-render")
    else:
        mode = "legacy"
        task = day["nightly-radar"]
        stages = []
        for att in sorted(
                (p for p in task.glob("attempt-*")
                 if re.fullmatch(r"attempt-(\d+)", p.name)),
                key=lambda p: int(re.fullmatch(r"attempt-(\d+)", p.name).group(1))):
            st = _state(att)
            stages.append({"name": att.name,
                           "status": st.get("status", "unknown"),
                           "time": st.get("started_at")})
        art_dir = task
    att = _pick_artifact_attempt(art_dir) if art_dir else None
    top5, digest_txt, validation = [], "", None
    if att:
        papers = []
        try:
            papers = json.loads((att / "digest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        papers_by_id = {p.get("arxiv_id"): p for p in papers if isinstance(p, dict)}
        top5 = _normalize_top5(att / "top5.json", papers_by_id)
        try:
            digest_txt = (att / "digest.txt").read_text(encoding="utf-8")
        except OSError:
            digest_txt = ""
        try:
            validation = json.loads((att / "validation.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    for row in top5:
        aid = row.get("id") or ""
        row["abs_url"] = f"https://arxiv.org/abs/{aid}" if aid else ""
        row["pdf_url"] = f"https://arxiv.org/pdf/{aid}" if aid else ""
    return {"available": True, "date": _iso_date(compact),
            "mode": mode, "stages": stages, "top5": top5,
            "validation": validation, "digest_txt": digest_txt}


def find_radar(root: Path, date: str | None = None) -> dict:
    by_date = _index_radar(root)
    history = list_radar_dates(root)
    if not by_date:
        return {"available": False, "history": history}
    compact = _compact_date(date)
    if date and not compact:
        return {"available": False, "date": date, "error": "bad_date",
                "history": history}
    if compact:
        if compact not in by_date:
            return {"available": False, "date": _iso_date(compact),
                    "error": "not_found", "history": history}
        payload = _radar_from_day(compact, by_date[compact])
    else:
        latest = max(by_date)
        payload = _radar_from_day(latest, by_date[latest])
    payload["history"] = history
    return payload


def build_digest_html(radar: dict) -> str:
    if not radar.get("available"):
        body = "无雷达数据（结果目录为空或 sync_pull 未运行）"
    else:
        val = radar["validation"].get("status") if radar["validation"] else "—"
        meta = f"{radar['date']} · {radar['mode']} · validation {val}"
        body = meta + "\n\n" + radar["digest_txt"]
    return ("<!doctype html><meta charset='utf-8'>"
            "<body style='margin:12px;font-family:monospace;white-space:pre-wrap'>"
            + html.escape(body) + "</body>")


def scan_attempts(results_root: Path, limit: int = 10) -> list[dict]:
    rows = []
    if limit <= 0 or not results_root.is_dir():
        return rows
    dirs = sorted(results_root.iterdir(),
                  key=lambda p: (p.stat().st_mtime, p.name), reverse=True)
    for task_dir in dirs:
        if not task_dir.is_dir():
            continue
        att = best_attempt(task_dir)
        if att is None:
            continue
        st = _state(att)
        rows.append({"task": task_dir.name, "attempt": int(re.fullmatch(r"attempt-(\d+)", att.name).group(1)),
                     "status": st.get("status", "unknown"),
                     "started_at": st.get("started_at"), "error": st.get("error")})
        if len(rows) >= limit:
            break
    return rows


def scan_experiments(research_root: Path) -> dict:
    cards = []
    root = research_root / "experiments"
    if not root.is_dir():
        return {"available": False, "cards": cards}
    for card in sorted(root.glob("*/card.md")):
        try:
            text = card.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        meta = {}
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                for line in parts[1].splitlines():
                    m = _FRONT.match(line.strip())
                    if m:
                        meta[m.group(1)] = m.group(2).strip()
        cards.append({"id": meta.get("id", card.parent.name),
                      "status": meta.get("status", "unknown"),
                      "updated": meta.get("updated", "")})
    return {"available": True, "cards": cards}
