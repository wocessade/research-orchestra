"""dispatcher.py 单元测试（注入 fake run/check_net，全流程临时目录）。"""
import json
import os
import tempfile
import unittest
from unittest import mock

import db
import dispatcher

TASK_MD = """# T-20260819-a
executor: shell
net: optional
result: T-20260819-a
---
echo ok
"""

def write_task(tasks_dir, name, executor="shell", net="optional"):
    md = (TASK_MD.replace("# T-20260819-a", f"# {name}")
                 .replace("executor: shell", f"executor: {executor}")
                 .replace("net: optional", f"net: {net}")
                 .replace("T-20260819-a", f"{name}"))
    with open(os.path.join(tasks_dir, f"{name}.md"), "w", encoding="utf-8") as f:
        f.write(md)

def make_cfg(tmp):
    return {
        "tasks_dir": os.path.join(tmp, "tasks"),
        "results_dir": os.path.join(tmp, "results"),
        "db_path": os.path.join(tmp, "broker.db"),
        "poll_interval": 1, "max_attempts": 2, "dsh_profile": "headless",
        "api_url": "", "monitor_token": "",
    }

class TestDispatcher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        for d in ("tasks", "results"):
            os.makedirs(os.path.join(self.tmp.name, d))
        self.cfg = make_cfg(self.tmp.name)
        self.conn = db.init_db(self.cfg["db_path"])

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_full_cycle_queued_to_done(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        fake_run = mock.Mock(return_value=("done", None))
        r = dispatcher.one_cycle(self.cfg, self.conn, run=fake_run, check_net_fn=lambda: True)
        self.assertEqual(r["executed"], ["T-20260819-a"])
        self.assertEqual(db.list_tasks(self.conn, "done")[0][0], "T-20260819-a")

    def test_failure_retry_then_final_failed(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        fake_run = mock.Mock(return_value=("failed", "boom"))
        dispatcher.one_cycle(self.cfg, self.conn, run=fake_run, check_net_fn=lambda: True)  # attempt 1
        dispatcher.one_cycle(self.cfg, self.conn, run=fake_run, check_net_fn=lambda: True)  # attempt 2
        self.assertEqual(db.list_tasks(self.conn, "failed")[0][1], "failed")  # attempts=2 终态
        r = dispatcher.one_cycle(self.cfg, self.conn, run=fake_run, check_net_fn=lambda: True)
        self.assertEqual(r["executed"], [])  # 不再执行

    def test_required_task_skipped_when_offline(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a", net="required")
        fake_run = mock.Mock()
        r = dispatcher.one_cycle(self.cfg, self.conn, run=fake_run, check_net_fn=lambda: False)
        self.assertEqual(r["skipped_net"], ["T-20260819-a"])
        fake_run.assert_not_called()
        self.assertEqual(db.list_tasks(self.conn, "queued")[0][0], "T-20260819-a")

    def test_idempotent_register(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(return_value=("done", None)), check_net_fn=lambda: True)
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(), check_net_fn=lambda: True)
        self.assertEqual(len(db.list_tasks(self.conn)), 1)  # done 不重跑

    def test_task_file_deleted_goes_final_failed(self):
        # 哨兵审计发现：文件被删时若不递增 attempts 会永久 requeue 空转
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(return_value=("failed", "x")), check_net_fn=lambda: True)
        os.remove(os.path.join(self.cfg["tasks_dir"], "T-20260819-a.md"))
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(), check_net_fn=lambda: True)  # attempts=1
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(), check_net_fn=lambda: True)  # attempts=2
        row = db.list_tasks(self.conn, "failed")[0]
        self.assertEqual(row[2], 2)  # attempts=2 终态
        r = dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(), check_net_fn=lambda: True)
        self.assertEqual(r["executed"], [])  # 不再空转

    def test_done_task_file_archived(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(return_value=("done", None)), check_net_fn=lambda: True)
        self.assertFalse(os.path.exists(os.path.join(self.cfg["tasks_dir"], "T-20260819-a.md")))
        self.assertTrue(os.path.exists(os.path.join(self.cfg["tasks_dir"], "archive", "T-20260819-a.md")))

    def test_retryable_failed_file_stays(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(return_value=("failed", "boom")), check_net_fn=lambda: True)
        # attempts=1 < max_attempts=2 → 文件必须留在 tasks/ 供重试
        self.assertTrue(os.path.exists(os.path.join(self.cfg["tasks_dir"], "T-20260819-a.md")))

    def test_recovery_marks_running_failed(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        db.register_task(self.conn, "T-20260819-a", "optional", "results/T-20260819-a")
        db.claim_task(self.conn, "T-20260819-a")
        n = db.recover_running(self.conn)  # 模拟重启恢复
        self.assertEqual(n, 1)
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(return_value=("done", None)), check_net_fn=lambda: True)
        self.assertEqual(db.list_tasks(self.conn, "done")[0][0], "T-20260819-a")  # 重试成功

    def test_executor_exception_goes_failed(self):
        # 哨兵审计 CONCERN-4：执行器抛异常必须落库 failed，不能永久卡 running
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        boom = mock.Mock(side_effect=RuntimeError("disk full"))
        dispatcher.one_cycle(self.cfg, self.conn, run=boom, check_net_fn=lambda: True)
        row = db.list_tasks(self.conn, "failed")[0]
        self.assertEqual(row[0], "T-20260819-a")
        self.assertIn("executor exception", row[4])
        # attempts=1 < max_attempts → 下一轮重试；重试又崩则 attempts=2 终态
        dispatcher.one_cycle(self.cfg, self.conn, run=boom, check_net_fn=lambda: True)
        self.assertEqual(db.list_tasks(self.conn, "failed")[0][2], 2)

    def test_build_payload_fields(self):
        # queued/running/done 混合
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(return_value=("done", None)), check_net_fn=lambda: True)
        db.register_task(self.conn, "T-20260819-b", "optional", "r")
        db.claim_task(self.conn, "T-20260819-b")  # running
        db.register_task(self.conn, "T-20260819-c", "optional", "r")  # queued
        payload = dispatcher.build_payload(self.conn)
        self.assertEqual(payload["broker_health"], "ok")
        self.assertEqual(payload["queue_len"], 2)   # queued + running
        self.assertEqual(payload["active_tasks"], 1)
        self.assertEqual(payload["last_task"], "T-20260819-a")  # 最近 done slug

    def test_build_payload_recent_tasks(self):
        # 6 个任务：2 done、1 running、3 queued；时间戳直接写入保证排序确定性
        for i in range(6):
            db.register_task(self.conn, f"T-20260819-r{i}", "optional", "r")
        db.claim_task(self.conn, "T-20260819-r1")
        db.finish_task(self.conn, "T-20260819-r1", "done")
        db.claim_task(self.conn, "T-20260819-r2")
        db.finish_task(self.conn, "T-20260819-r2", "done")
        db.claim_task(self.conn, "T-20260819-r3")
        for i in range(6):
            self.conn.execute(
                "UPDATE tasks SET created_at=?, started_at=NULL, done_at=NULL WHERE slug=?",
                (f"2026-08-19T10:0{i}:00+00:00", f"T-20260819-r{i}"),
            )
        self.conn.execute("UPDATE tasks SET started_at='2026-08-19T10:10:00+00:00' WHERE slug='T-20260819-r3'")
        self.conn.execute("UPDATE tasks SET done_at='2026-08-19T10:11:00+00:00' WHERE slug='T-20260819-r2'")
        self.conn.execute("UPDATE tasks SET done_at='2026-08-19T10:12:00+00:00' WHERE slug='T-20260819-r1'")
        self.conn.commit()
        payload = dispatcher.build_payload(self.conn)
        recent = payload["recent_tasks"]
        self.assertEqual(len(recent), 5)  # cap 5
        # ts 降序：r1(done 10:12) > r2(done 10:11) > r3(started 10:10) > r5 > r4 (created_at)
        self.assertEqual([r["slug"] for r in recent],
                         ["T-20260819-r1", "T-20260819-r2", "T-20260819-r3",
                          "T-20260819-r5", "T-20260819-r4"])
        self.assertEqual(recent[0], {"slug": "T-20260819-r1", "status": "done",
                                     "ts": "2026-08-19T10:12:00+00:00"})
        for item in recent:  # 每项 key 齐全
            self.assertEqual(set(item), {"slug", "status", "ts"})

    def test_build_payload_empty(self):
        payload = dispatcher.build_payload(self.conn)
        self.assertEqual(payload["broker_health"], "ok")
        self.assertEqual(payload["queue_len"], 0)
        self.assertEqual(payload["active_tasks"], 0)
        self.assertIsNone(payload["last_task"])
        self.assertEqual(payload["recent_tasks"], [])

    def test_bad_taskfile_archived_as_bad(self):
        # 哨兵审计 INFO-4：解析失败的任务文件按 .bad 归档，防每 30s 刷错误日志
        with open(os.path.join(self.cfg["tasks_dir"], "T-20260819-x.md"), "w", encoding="utf-8") as f:
            f.write("# T-20260819-x\nexecutor: shell\nnet: optional\nresult: T-20260819-x\ntimeout: notanumber\n---\necho x\n")
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(), check_net_fn=lambda: True)
        self.assertFalse(os.path.exists(os.path.join(self.cfg["tasks_dir"], "T-20260819-x.md")))
        self.assertTrue(os.path.exists(os.path.join(self.cfg["tasks_dir"], "archive", "T-20260819-x.md.bad")))
        self.assertEqual(len(db.list_tasks(self.conn)), 0)  # 未注册

if __name__ == "__main__":
    unittest.main()
