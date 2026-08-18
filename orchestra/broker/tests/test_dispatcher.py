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
result: results/T-20260819-a
---
echo ok
"""

def write_task(tasks_dir, name, executor="shell", net="optional"):
    md = (TASK_MD.replace("# T-20260819-a", f"# {name}")
                 .replace("executor: shell", f"executor: {executor}")
                 .replace("net: optional", f"net: {net}")
                 .replace("results/T-20260819-a", f"results/{name}"))
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

    def test_recovery_marks_running_failed(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-a")
        db.register_task(self.conn, "T-20260819-a", "optional", "results/T-20260819-a")
        db.claim_task(self.conn, "T-20260819-a")
        n = db.recover_running(self.conn)  # 模拟重启恢复
        self.assertEqual(n, 1)
        dispatcher.one_cycle(self.cfg, self.conn, run=mock.Mock(return_value=("done", None)), check_net_fn=lambda: True)
        self.assertEqual(db.list_tasks(self.conn, "done")[0][0], "T-20260819-a")  # 重试成功

if __name__ == "__main__":
    unittest.main()
