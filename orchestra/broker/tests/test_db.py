"""db.py 单元测试（stdlib unittest，tempfile 隔离）。"""
import os
import tempfile
import unittest

import db  # noqa: E402

class TestDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = db.init_db(os.path.join(self.tmp.name, "broker.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_register_is_idempotent(self):
        db.register_task(self.conn, "T-001", "optional", "results/T-001")
        db.register_task(self.conn, "T-001", "optional", "results/T-001")
        self.assertEqual(len(db.list_tasks(self.conn)), 1)

    def test_claim_finish_flow(self):
        db.register_task(self.conn, "T-001", "required", "r")
        self.assertTrue(db.claim_task(self.conn, "T-001"))
        self.assertFalse(db.claim_task(self.conn, "T-001"))  # 不可重复抢
        self.assertEqual(db.list_tasks(self.conn, "running")[0][0], "T-001")
        db.finish_task(self.conn, "T-001", "done")
        row = db.list_tasks(self.conn, "done")[0]
        self.assertEqual(row[0], "T-001")
        self.assertEqual(row[4], None)  # error 为空

    def test_finish_failed_with_error(self):
        db.register_task(self.conn, "T-002", "optional", "r")
        db.claim_task(self.conn, "T-002")
        db.finish_task(self.conn, "T-002", "failed", "exit code 1")
        self.assertEqual(db.list_tasks(self.conn, "failed")[0][4], "exit code 1")

    def test_requeue_failed_respects_max_attempts(self):
        db.register_task(self.conn, "T-003", "optional", "r")
        db.claim_task(self.conn, "T-003")
        db.finish_task(self.conn, "T-003", "failed", "x")
        self.assertEqual(db.requeue_failed(self.conn, max_attempts=1), 0)  # attempts=1 不重试
        self.assertEqual(db.requeue_failed(self.conn, max_attempts=2), 1)  # 回 queued
        db.claim_task(self.conn, "T-003")
        db.finish_task(self.conn, "T-003", "failed", "y")
        self.assertEqual(db.requeue_failed(self.conn, max_attempts=2), 0)  # attempts=2 终态

    def test_recover_running(self):
        db.register_task(self.conn, "T-004", "optional", "r")
        db.claim_task(self.conn, "T-004")
        n = db.recover_running(self.conn)
        self.assertEqual(n, 1)
        self.assertEqual(db.list_tasks(self.conn, "failed")[0][4], "recovered after restart")

    def test_list_recent_empty(self):
        self.assertEqual(db.list_recent(self.conn), [])

    def test_list_recent_order_and_coalesce(self):
        # 兜底优先级：done_at > started_at > created_at；时间戳直接写入保证确定性
        # （_now 秒级精度，两次调用可能同秒）
        for slug in ("T-a", "T-b", "T-c"):
            db.register_task(self.conn, slug, "optional", "r")
        db.claim_task(self.conn, "T-a")
        db.finish_task(self.conn, "T-a", "done")  # done_at 已有
        db.claim_task(self.conn, "T-b")           # running：无 done_at，用 started_at
        # T-c 保持 queued：两者皆无，用 created_at
        for slug, ts in [
            ("T-a", "2026-08-19T01:00:00+00:00"),
            ("T-b", "2026-08-19T02:00:00+00:00"),
            ("T-c", "2026-08-19T03:00:00+00:00"),
        ]:
            self.conn.execute("UPDATE tasks SET created_at=? WHERE slug=?", (ts, slug))
        self.conn.execute("UPDATE tasks SET started_at='2026-08-19T04:00:00+00:00' WHERE slug='T-b'")
        self.conn.execute("UPDATE tasks SET done_at='2026-08-19T05:00:00+00:00' WHERE slug='T-a'")
        self.conn.commit()
        rows = db.list_recent(self.conn)
        # 降序：T-a(done_at 05:00) > T-b(started_at 04:00) > T-c(created_at 03:00)
        self.assertEqual([r[0] for r in rows], ["T-a", "T-b", "T-c"])
        self.assertEqual(rows[0], ("T-a", "done", "2026-08-19T05:00:00+00:00"))
        self.assertEqual(rows[1], ("T-b", "running", "2026-08-19T04:00:00+00:00"))
        self.assertEqual(rows[2], ("T-c", "queued", "2026-08-19T03:00:00+00:00"))

    def test_list_recent_limit(self):
        for i in range(8):
            self.conn.execute(
                "INSERT INTO tasks (slug, status, net_req, result_path, created_at) "
                "VALUES (?,?,?,?,?)",
                (f"T-{i:03d}", "queued", "optional", "r", f"2026-08-19T{i+1:02d}:00:00+00:00"),
            )
        self.conn.commit()
        rows = db.list_recent(self.conn)  # 默认上限 5
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0][0], "T-007")  # 最新在前
        self.assertEqual(rows[-1][0], "T-003")
        self.assertEqual([r[0] for r in db.list_recent(self.conn, limit=3)],
                         ["T-007", "T-006", "T-005"])

if __name__ == "__main__":
    unittest.main()
