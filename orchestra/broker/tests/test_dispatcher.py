"""dispatcher.py 单元测试（注入 fake run/check_net，全流程临时目录）。"""
import json
import os
import tempfile
import threading
import time
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

def write_task(tasks_dir, name, executor="shell", net="optional", depends_on=None):
    md = (TASK_MD.replace("# T-20260819-a", f"# {name}")
                 .replace("executor: shell", f"executor: {executor}")
                 .replace("net: optional", f"net: {net}")
                 .replace("T-20260819-a", f"{name}"))
    if depends_on:
        md = md.replace("---\n", f"depends_on: {', '.join(depends_on)}\n---\n")
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

    def test_dependency_waits_without_consuming_attempt(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-10-fetch")
        write_task(
            self.cfg["tasks_dir"],
            "T-20260819-20-rank",
            depends_on=["T-20260819-10-fetch"],
        )
        calls = []

        def run(spec, *_args, **_kwargs):
            calls.append(spec.slug)
            if spec.slug.endswith("10-fetch"):
                return "failed", "temporary"
            return "done", None

        result = dispatcher.one_cycle(
            self.cfg, self.conn, run=run, check_net_fn=lambda: True
        )
        self.assertEqual(calls, ["T-20260819-10-fetch"])
        self.assertEqual(
            result["waiting_dependencies"],
            [{
                "slug": "T-20260819-20-rank",
                "dependencies": ["T-20260819-10-fetch"],
            }],
        )
        rank = db.get_task(self.conn, "T-20260819-20-rank")
        self.assertEqual(rank[1], "queued")
        self.assertEqual(rank[2], 0)

    def test_dependency_runs_after_predecessor_finishes_same_cycle(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-10-fetch")
        write_task(
            self.cfg["tasks_dir"],
            "T-20260819-20-rank",
            depends_on=["T-20260819-10-fetch"],
        )
        calls = []

        def run(spec, *_args, **_kwargs):
            calls.append(spec.slug)
            return "done", None

        result = dispatcher.one_cycle(
            self.cfg, self.conn, run=run, check_net_fn=lambda: True
        )
        self.assertEqual(
            calls,
            ["T-20260819-10-fetch", "T-20260819-20-rank"],
        )
        self.assertEqual(result["waiting_dependencies"], [])
        self.assertEqual(len(db.list_tasks(self.conn, "done")), 2)

    def test_missing_dependency_becomes_invalid_and_is_archived(self):
        write_task(
            self.cfg["tasks_dir"],
            "T-20260819-child",
            depends_on=["T-20260819-missing"],
        )
        result = dispatcher.one_cycle(
            self.cfg, self.conn, run=mock.Mock(), check_net_fn=lambda: True
        )
        row = db.get_task(self.conn, "T-20260819-child")
        self.assertEqual(row[1], "invalid")
        self.assertIn("missing dependencies", row[4])
        self.assertEqual(len(result["invalid_dependencies"]), 1)
        self.assertTrue(os.path.exists(os.path.join(
            self.cfg["tasks_dir"], "archive", "T-20260819-child.md"
        )))

    def test_injection_marker_hides_partial_radar_pipeline(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-nightly-radar-10-fetch")
        marker = os.path.join(self.cfg["tasks_dir"], ".radar-inject-20260819")
        open(marker, "w", encoding="utf-8").close()
        run = mock.Mock(return_value=("done", None))
        result = dispatcher.one_cycle(
            self.cfg, self.conn, run=run, check_net_fn=lambda: True
        )
        self.assertEqual(result["executed"], [])
        self.assertEqual(db.list_tasks(self.conn), [])
        run.assert_not_called()

    def test_dependency_cycle_becomes_invalid(self):
        write_task(
            self.cfg["tasks_dir"], "T-20260819-a",
            depends_on=["T-20260819-b"],
        )
        write_task(
            self.cfg["tasks_dir"], "T-20260819-b",
            depends_on=["T-20260819-a"],
        )
        result = dispatcher.one_cycle(
            self.cfg, self.conn, run=mock.Mock(), check_net_fn=lambda: True
        )
        self.assertEqual(
            {row[0] for row in db.list_tasks(self.conn, "invalid")},
            {"T-20260819-a", "T-20260819-b"},
        )
        self.assertEqual(len(result["invalid_dependencies"]), 2)

    def test_terminal_failed_dependency_blocks_downstream(self):
        write_task(self.cfg["tasks_dir"], "T-20260819-10-fetch")
        write_task(
            self.cfg["tasks_dir"], "T-20260819-20-rank",
            depends_on=["T-20260819-10-fetch"],
        )
        failing = mock.Mock(return_value=("failed", "boom"))
        first = dispatcher.one_cycle(
            self.cfg, self.conn, run=failing, check_net_fn=lambda: True
        )
        self.assertEqual(len(first["waiting_dependencies"]), 1)
        second = dispatcher.one_cycle(
            self.cfg, self.conn, run=failing, check_net_fn=lambda: True
        )
        rank = db.get_task(self.conn, "T-20260819-20-rank")
        self.assertEqual(rank[1], "blocked")
        self.assertEqual(rank[2], 0)
        self.assertIn("failed after 2 attempts", rank[4])
        self.assertEqual(len(second["blocked_dependencies"]), 1)

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

    def test_reporter_loop_reports_until_stopped(self):
        # D15：独立 reporter 线程——主循环执行长任务期间按 poll_interval 持续上报，
        # stop_event 置位后退出（join 后调用数不再增长）
        cfg = dict(self.cfg, poll_interval=0.05)
        stop = threading.Event()
        with mock.patch("dispatcher.report_status") as report:
            t = threading.Thread(target=dispatcher._reporter_loop, args=(cfg, stop), daemon=True)
            t.start()
            deadline = time.time() + 5
            while report.call_count < 3 and time.time() < deadline:
                time.sleep(0.02)
            self.assertGreaterEqual(report.call_count, 3)  # 持续上报（≥3 次）
            stop.set()
            t.join(timeout=2)
            self.assertFalse(t.is_alive())  # 线程已结束
            count = report.call_count
            time.sleep(0.15)  # 大于 poll_interval：确认停止后不再上报
            self.assertEqual(report.call_count, count)

    def test_build_payload_includes_running_task(self):
        # D15 面板可见性契约：running 任务必须同时出现在 active_tasks 与
        # recent_tasks（面板「运行中」帧的数据来源）
        db.register_task(self.conn, "T-20260819-d15", "optional", "results/T-20260819-d15")
        db.claim_task(self.conn, "T-20260819-d15")  # status=running
        payload = dispatcher.build_payload(self.conn)
        self.assertEqual(payload["active_tasks"], 1)
        self.assertEqual(payload["recent_tasks"][0]["slug"], "T-20260819-d15")
        self.assertEqual(payload["recent_tasks"][0]["status"], "running")

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
        self.assertEqual(payload["blocked_tasks"], 0)
        self.assertEqual(payload["invalid_tasks"], 0)

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
        self.assertNotIn("host", payload)  # 本机无 /proc（如 Windows）→ 无 host 键

    def test_build_payload_host_stats(self):
        payload = dispatcher.build_payload(self.conn, host_stats={"load1": 0.3, "mem_pct": 38})
        self.assertEqual(payload["host"], {"load1": 0.3, "mem_pct": 38})
        # 既有字段不受影响
        self.assertEqual(payload["broker_health"], "ok")
        self.assertEqual(payload["recent_tasks"], [])

    def test_build_payload_no_host_key_when_stats_none(self):
        # 注入 None（或读 /proc 失败）→ 不含 host 键，向后兼容
        with mock.patch.object(dispatcher, "read_host_stats", return_value=None):
            payload = dispatcher.build_payload(self.conn)
        self.assertNotIn("host", payload)

    def test_read_host_stats_parses_proc(self):
        # Path.read_text 走 io.open 不走 builtins.open，故直接 mock Path.read_text
        fake = {
            "/proc/loadavg": "0.34 0.21 0.18 1/223 456\n",
            "/proc/meminfo": "MemTotal:       1024000 kB\nMemAvailable:   634880 kB\n",
        }
        with mock.patch.object(dispatcher.Path, "read_text", autospec=True,
                               side_effect=lambda self: fake[self.as_posix()]):
            stats = dispatcher.read_host_stats()
        self.assertEqual(stats, {"load1": 0.3, "mem_pct": 38})  # round(0.34,1)=0.3；已用 38% → 38

    def test_read_host_stats_none_when_missing(self):
        # /proc 不存在（Windows/容器）或解析失败 → None
        with mock.patch.object(dispatcher.Path, "read_text", side_effect=FileNotFoundError):
            self.assertIsNone(dispatcher.read_host_stats())
        with mock.patch.object(dispatcher.Path, "read_text", side_effect=ValueError("garbage")):
            self.assertIsNone(dispatcher.read_host_stats())

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
