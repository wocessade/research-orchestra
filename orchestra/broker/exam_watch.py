#!/usr/bin/env python3
"""雨课堂考试放出监控（stdlib only）。每轮由 systemd oneshot 调用。"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
DEFAULT_CLASSROOM = "25631011"
DEFAULT_SKU = "12651805"
DEFAULT_COOKIE = "/home/liuxfs/broker-data/exam_cookie.txt"
DEFAULT_STATE = "/home/liuxfs/broker-data/exam_watch_state.json"
DEFAULT_ALERT = "/home/liuxfs/broker-data/results/exam_alert.json"
DEFAULT_BEAT = "/home/liuxfs/broker-data/results/exam_watch_beat.json"
DEFAULT_SENDER = "/usr/local/bin/send_email.py"
EVAL_PATH = "/c27/online_courseware/evaluation/score_setting/get_sku_evaluation_list_readonly/"
CHAPTER_PATH = "/mooc-api/v1/lms/learn/course/chapter"
ORIGIN = "https://changjiang.yuketang.cn"
LEAF_EXAM = 5
HTTP_TIMEOUT = 15


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def parse_cookie_map(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in raw.replace("\n", ";").split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        if name:
            out[name] = value.strip()
    return out


def build_headers(cookie_raw: str, classroom_id: str) -> dict[str, str]:
    cookies = parse_cookie_map(cookie_raw)
    csrf = cookies.get("csrftoken") or cookies.get("csrf_token") or ""
    uv = cookies.get("uv_id") or cookies.get("uv-id") or cookies.get("uvId") or ""
    university = cookies.get("university_id") or cookies.get("university-id") or "2937"
    header_cookie = cookie_raw.strip().replace("\n", "; ")
    return {
        "Cookie": header_cookie,
        "User-Agent": UA,
        "x-csrftoken": csrf,
        "uv-id": uv,
        "classroom-id": str(classroom_id),
        "university-id": str(university),
        "xt-agent": "web",
        "xtbz": "ykt",
        "Referer": f"{ORIGIN}/v2/web/studentLog/{classroom_id}",
    }


def exam_use_count(payload: dict) -> int:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    tags = data.get("evaluation_tag_list") if isinstance(data, dict) else None
    if not isinstance(tags, list):
        return 0
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        if tag.get("name") == "考试":
            try:
                return int(tag.get("use_count") or 0)
            except (TypeError, ValueError):
                return 0
    return 0


def exam_leaf_names(payload: dict) -> list[str]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    chapters = data.get("course_chapter") if isinstance(data, dict) else None
    if not isinstance(chapters, list):
        return []
    names: list[str] = []
    for chapter in chapters:
        if not isinstance(chapter, dict):
            continue
        leaves = chapter.get("section_leaf_list")
        if not isinstance(leaves, list):
            continue
        for leaf in leaves:
            if not isinstance(leaf, dict):
                continue
            if leaf.get("leaf_type") == LEAF_EXAM:
                name = str(leaf.get("name") or "").strip()
                if name:
                    names.append(name)
    return names


class AuthExpired(Exception):
    pass


def _read_json_url(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read() or b""
        except OSError:
            pass
        text = body.decode("utf-8", errors="replace")
        if exc.code == 401 or "Authentication credentials were not provided" in text:
            raise AuthExpired(text[:200]) from exc
        raise
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise urllib.error.URLError(f"invalid json from {url}") from exc
    if not isinstance(payload, dict):
        raise urllib.error.URLError(f"non-object json from {url}")
    return payload


def default_send_mail(subject: str, body: str, sender: Path) -> int:
    if not sender.is_file():
        return 10
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".txt", delete=False
    ) as tmp:
        tmp.write(body)
        body_path = tmp.name
    try:
        proc = subprocess.run(
            [sys.executable, str(sender), subject, body_path],
            capture_output=True, text=True, check=False,
        )
        return proc.returncode
    except OSError:
        return 10
    finally:
        try:
            os.unlink(body_path)
        except OSError:
            pass


def _exam_released(use_count: int, names: list[str]) -> bool:
    return use_count > 0 or len(names) > 0


def _alert_payload(use_count: int, names: list[str], source: str) -> dict:
    found_at = _now()
    leaf_count = len(names)
    if names:
        detail = "、".join(names)
    else:
        detail = "考试已放出，请登录雨课堂查看"
    return {
        "exam_found": True,
        "exam_names": names,
        "leaf_count": leaf_count,
        "use_count": use_count,
        "found_at": found_at,
        "source": source,
        "alerted": True,
        "message": f"雨课堂：考试已放出（{leaf_count or use_count}个）——{detail}",
    }


def _cookie_alert() -> dict:
    return {
        "exam_found": False,
        "cookie_expired": True,
        "exam_names": [],
        "leaf_count": 0,
        "use_count": 0,
        "found_at": _now(),
        "source": "auth",
        "alerted": True,
        "message": "雨课堂 cookie 已过期，请重新导出并上传 4B",
    }


def _beat_payload(state: dict, status: str) -> dict:
    return {
        "status": status,
        "last_check": state.get("last_check") or _now(),
        "last_check_ts": int(datetime.now(timezone.utc).timestamp()),
        "exam_found": bool(state.get("exam_found")),
        "cookie_expired": bool(state.get("cookie_expired")),
        "use_count": int(state.get("use_count") or 0),
        "leaf_count": int(state.get("leaf_count") or 0),
        "last_error": state.get("last_error"),
    }


def _maybe_mail(state: dict, send_mail, subject: str, body: str) -> dict:
    rc = send_mail(subject, body)
    state["mail_failed"] = rc != 0
    return state


def run(*, classroom_id: str, sku_id: str, cookie_file: Path, state_file: Path,
        alert_file: Path, beat_file: Path, send_mail) -> int:
    state = _load_json(state_file) or {}
    if state.get("cookie_expired"):
        _write_json(beat_file, _beat_payload(state, "done"))
        return 0
    if state.get("exam_found") and not state.get("mail_failed"):
        _write_json(beat_file, _beat_payload(state, "done"))
        return 0

    if state.get("exam_found") and state.get("mail_failed"):
        prior = _load_json(alert_file) or {}
        msg = prior.get("message") or "雨课堂：考试已放出，请登录雨课堂查看"
        state = _maybe_mail(state, send_mail, "雨课堂考试已放出", str(msg))
        state["last_check"] = _now()
        _write_json(state_file, state)
        _write_json(beat_file, _beat_payload(state, "done"))
        return 0

    try:
        cookie_raw = cookie_file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cookie file unreadable: {cookie_file} ({exc})", file=sys.stderr)
        return 1
    if not cookie_raw.strip():
        print(f"cookie file empty: {cookie_file}", file=sys.stderr)
        return 1

    headers = build_headers(cookie_raw, classroom_id)
    eval_url = f"{ORIGIN}{EVAL_PATH}{sku_id}/"
    chapter_url = f"{ORIGIN}{CHAPTER_PATH}?cid={classroom_id}"
    try:
        eval_payload = _read_json_url(eval_url, headers)
        chapter_payload = _read_json_url(chapter_url, headers)
    except AuthExpired:
        alert = _cookie_alert()
        _write_json(alert_file, alert)
        state = {
            "exam_found": False,
            "cookie_expired": True,
            "use_count": 0,
            "leaf_count": 0,
            "exam_names": [],
            "last_check": _now(),
            "last_error": "401",
            "alerted": True,
        }
        state = _maybe_mail(
            state, send_mail, "雨课堂 cookie 已过期", alert["message"]
        )
        _write_json(state_file, state)
        _write_json(beat_file, _beat_payload(state, "done"))
        return 0
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        state["last_error"] = str(exc)
        state["last_check"] = _now()
        _write_json(state_file, state)
        _write_json(beat_file, _beat_payload(state, "error"))
        return 0

    use_count = exam_use_count(eval_payload)
    names = exam_leaf_names(chapter_payload)
    released = _exam_released(use_count, names)
    if not released:
        state = {
            "exam_found": False,
            "cookie_expired": False,
            "use_count": use_count,
            "leaf_count": 0,
            "exam_names": [],
            "last_check": _now(),
            "last_error": None,
            "mail_failed": False,
            "alerted": False,
        }
        _write_json(state_file, state)
        _write_json(beat_file, _beat_payload(state, "ok"))
        return 0

    source = "eval" if use_count > 0 else "chapter"
    if use_count > 0 and names:
        source = "eval+chapter"
    alert = _alert_payload(use_count, names, source)
    if not alert_file.exists():
        _write_json(alert_file, alert)
    else:
        existing = _load_json(alert_file)
        if not (isinstance(existing, dict) and existing.get("exam_found")):
            _write_json(alert_file, alert)
    state = {
        "exam_found": True,
        "cookie_expired": False,
        "use_count": use_count,
        "leaf_count": len(names),
        "exam_names": names,
        "last_check": _now(),
        "last_error": None,
        "alerted": True,
        "found_at": alert.get("found_at"),
    }
    persisted = _load_json(alert_file) or alert
    state = _maybe_mail(
        state, send_mail, "雨课堂考试已放出", str(persisted.get("message") or alert["message"])
    )
    _write_json(state_file, state)
    _write_json(beat_file, _beat_payload(state, "done"))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="雨课堂考试放出监控")
    parser.add_argument("--classroom-id", default=DEFAULT_CLASSROOM)
    parser.add_argument("--sku-id", default=DEFAULT_SKU)
    parser.add_argument(
        "--cookie-file",
        default=os.environ.get("EXAM_COOKIE_FILE", DEFAULT_COOKIE),
    )
    parser.add_argument(
        "--state-file",
        default=os.environ.get("EXAM_STATE_FILE", DEFAULT_STATE),
    )
    parser.add_argument(
        "--alert-file",
        default=os.environ.get("EXAM_ALERT_FILE", DEFAULT_ALERT),
    )
    parser.add_argument(
        "--beat-file",
        default=os.environ.get("EXAM_BEAT_FILE", DEFAULT_BEAT),
    )
    parser.add_argument(
        "--sender",
        default=os.environ.get("EXAM_SENDER", DEFAULT_SENDER),
    )
    args = parser.parse_args(argv)

    def send_mail(subject: str, body: str) -> int:
        return default_send_mail(subject, body, Path(args.sender))

    try:
        return run(
            classroom_id=str(args.classroom_id),
            sku_id=str(args.sku_id),
            cookie_file=Path(args.cookie_file),
            state_file=Path(args.state_file),
            alert_file=Path(args.alert_file),
            beat_file=Path(args.beat_file),
            send_mail=send_mail,
        )
    except Exception as exc:  # noqa: BLE001 — oneshot: 崩溃记 journal，exit 1
        print(f"exam_watch failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
