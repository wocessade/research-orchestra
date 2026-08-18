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

if __name__ == "__main__":
    unittest.main()
