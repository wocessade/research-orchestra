"""旧单体雷达任务部署迁移门禁测试。"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

import migration_guard


class MigrationGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tasks = self.root / "tasks"
        self.tasks.mkdir()
        self.db = self.root / "broker.db"
        # 显式 commit+close：sqlite3 默认 legacy 隔离级下 DML 需显式 commit，
        # 且 close 必须在临时目录清理前完成（Windows 文件锁）
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "CREATE TABLE tasks (slug TEXT, status TEXT, attempts INTEGER)"
            )
            conn.commit()
        finally:
            conn.close()

    def add_row(self, slug, status, attempts=0):
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "INSERT INTO tasks VALUES (?, ?, ?)", (slug, status, attempts)
            )
            conn.commit()
        finally:
            conn.close()

    def test_blocks_unregistered_active_legacy_task_file(self):
        (self.tasks / "T-20260820-nightly-radar.md").write_text("legacy", encoding="utf-8")
        blockers = migration_guard.find_legacy_blockers(self.tasks, self.db, 2)
        self.assertEqual(blockers[0]["status"], "unregistered")

    def test_blocks_queued_running_and_retryable_failed_legacy_rows(self):
        for date, status, attempts in (
            ("20260820", "queued", 0),
            ("20260821", "running", 1),
            ("20260822", "failed", 1),
        ):
            self.add_row(f"T-{date}-nightly-radar", status, attempts)
        blockers = migration_guard.find_legacy_blockers(self.tasks, self.db, 2)
        self.assertEqual(
            {item["status"] for item in blockers},
            {"queued", "running", "failed"},
        )

    def test_allows_terminal_legacy_and_ignores_staged_tasks(self):
        self.add_row("T-20260820-nightly-radar", "done", 1)
        self.add_row("T-20260821-nightly-radar", "failed", 2)
        self.add_row("T-20260822-nightly-radar", "blocked", 0)
        self.add_row("T-20260823-nightly-radar", "invalid", 0)
        self.add_row("T-20260820-nightly-radar-10-fetch", "running", 1)
        blockers = migration_guard.find_legacy_blockers(self.tasks, self.db, 2)
        self.assertEqual(blockers, [])


if __name__ == "__main__":
    unittest.main()
