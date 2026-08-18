"""Broker 任务状态库：SQLite WAL，stdlib only。"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    slug TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',  -- queued|running|done|failed
    attempts INTEGER NOT NULL DEFAULT 0,
    net_req TEXT NOT NULL DEFAULT 'optional',
    result_path TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    done_at TEXT
);
"""

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_SCHEMA)
    conn.commit()
    return conn

def register_task(conn: sqlite3.Connection, slug: str, net_req: str, result_path: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO tasks (slug, net_req, result_path, created_at) VALUES (?,?,?,?)",
        (slug, net_req, result_path, _now()),
    )
    conn.commit()

def claim_task(conn: sqlite3.Connection, slug: str) -> bool:
    cur = conn.execute(
        "UPDATE tasks SET status='running', started_at=?, attempts=attempts+1, error=NULL "
        "WHERE slug=? AND status='queued'",
        (_now(), slug),
    )
    conn.commit()
    return cur.rowcount == 1

def finish_task(conn: sqlite3.Connection, slug: str, status: str, error: str | None = None) -> None:
    conn.execute(
        "UPDATE tasks SET status=?, done_at=?, error=? WHERE slug=?",
        (status, _now(), error, slug),
    )
    conn.commit()

def requeue_failed(conn: sqlite3.Connection, max_attempts: int) -> int:
    n = conn.execute(
        "UPDATE tasks SET status='queued', error=NULL WHERE status='failed' AND attempts < ?",
        (max_attempts,),
    ).rowcount
    conn.commit()
    return n

def recover_running(conn: sqlite3.Connection) -> int:
    n = conn.execute(
        "UPDATE tasks SET status='failed', done_at=?, error='recovered after restart' "
        "WHERE status='running'",
        (_now(),),
    ).rowcount
    conn.commit()
    return n

def get_task(conn: sqlite3.Connection, slug: str) -> tuple | None:
    return conn.execute(
        "SELECT slug, status, attempts, net_req, error FROM tasks WHERE slug=?",
        (slug,),
    ).fetchone()

def list_tasks(conn: sqlite3.Connection, status: str | None = None) -> list[tuple]:
    if status:
        return conn.execute(
            "SELECT slug, status, attempts, net_req, error FROM tasks WHERE status=?",
            (status,),
        ).fetchall()
    return conn.execute(
        "SELECT slug, status, attempts, net_req, error FROM tasks"
    ).fetchall()
