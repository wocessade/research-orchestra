#!/usr/bin/env python3
"""部署迁移前阻断尚未终态的旧单体雷达任务。"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path


_LEGACY_SLUG = re.compile(r"^T-[^-]+-nightly-radar$")
_TERMINAL = {"done", "blocked", "invalid"}


def _is_terminal(status: str, attempts: int, max_attempts: int) -> bool:
    return status in _TERMINAL or (
        status == "failed" and attempts >= max_attempts
    )


def find_legacy_blockers(
    tasks_dir: Path, db_path: Path, max_attempts: int
) -> list[dict]:
    rows: dict[str, tuple[str, int]] = {}
    if db_path.exists():
        # closing()：with 只 commit 不 close，连接-游标引用环会延迟关闭，
        # Windows 上残留句柄导致文件被锁（临时目录清理失败）
        with closing(sqlite3.connect(db_path)) as conn:
            for slug, status, attempts in conn.execute(
                "SELECT slug, status, attempts FROM tasks"
            ):
                if _LEGACY_SLUG.fullmatch(slug):
                    rows[slug] = (status, attempts)

    blockers = []
    active_files = {
        path.stem for path in tasks_dir.glob("T-*-nightly-radar.md")
        if _LEGACY_SLUG.fullmatch(path.stem)
    }
    for slug in sorted(active_files | set(rows)):
        row = rows.get(slug)
        if row is None:
            blockers.append({
                "slug": slug,
                "status": "unregistered",
                "reason": "active legacy task file has no database state",
            })
            continue
        status, attempts = row
        if not _is_terminal(status, attempts, max_attempts):
            blockers.append({
                "slug": slug,
                "status": status,
                "attempts": attempts,
                "reason": "legacy monolithic task is not terminal",
            })
    return blockers


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks-dir", required=True)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--config")
    parser.add_argument("--max-attempts", type=int)
    args = parser.parse_args(argv)
    max_attempts = args.max_attempts
    if max_attempts is None:
        max_attempts = 2
        if args.config:
            config = json.loads(Path(args.config).read_text(encoding="utf-8"))
            max_attempts = int(config.get("max_attempts", max_attempts))
    blockers = find_legacy_blockers(
        Path(args.tasks_dir), Path(args.db_path), max_attempts
    )
    if blockers:
        print(json.dumps({
            "status": "blocked",
            "reason": "unfinished legacy radar tasks",
            "tasks": blockers,
        }, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "ok", "tasks": []}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
