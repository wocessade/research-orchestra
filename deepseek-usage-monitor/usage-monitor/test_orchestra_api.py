"""POST /api/orchestra 状态上报 API 测试 (unittest + app.test_client)。

参考同目录 test_dashboard.py 的既有模式 (test_dashboard 为硬件渲染测试,
本文件为纯逻辑 API 测试)。MONITOR_TOKEN 默认空 = 鉴权直通,
故测试开头先设置测试 token, 再导入 app (app 在 import 时读取 config)。
"""

import json
import time
import unittest

import config

config.MONITOR_TOKEN = "test-token-026"

import app  # noqa: E402  # 必须在 MONITOR_TOKEN 设置之后导入

TEST_TOKEN = "test-token-026"
AUTH = {"X-Monitor-Token": TEST_TOKEN}

ORCH_INIT = {
    "broker_health": "unknown",
    "queue_len": None,
    "active_tasks": None,
    "last_task": None,
    "last_sync": None,
    "recent_tasks": [],
    "host": {},
}


class OrchestraApiTest(unittest.TestCase):
    def setUp(self):
        app.app.testing = True
        self.client = app.app.test_client()
        with app.state_lock:
            app.state["orchestra"] = dict(ORCH_INIT)
            app.state["orchestra_last_report"] = {"broker": 0, "sync": 0}

    def post_orchestra(self, body, headers=None):
        # data=json.dumps 而非 json= kwarg: Flask test client 的 json= 会
        # 以 sort_keys=True 序列化 (flask DefaultJSONProvider), 破坏
        # "merged 按接收顺序" 的语义; 直接塞 body 保序。
        return self.client.post(
            "/api/orchestra",
            data=json.dumps(body),
            content_type="application/json",
            headers=headers if headers is not None else AUTH,
        )

    def orch_state(self):
        with app.state_lock:
            return dict(app.state["orchestra"])

    def last_report(self):
        with app.state_lock:
            return dict(app.state["orchestra_last_report"])

    # ─── 鉴权 ──────────────────────────────────

    def test_no_token_401(self):
        resp = self.post_orchestra({"queue_len": 1}, headers={})
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(resp.get_json()["ok"])

    def test_wrong_token_401(self):
        resp = self.post_orchestra(
            {"queue_len": 1}, headers={"X-Monitor-Token": "wrong"}
        )
        self.assertEqual(resp.status_code, 401)

    # ─── 部分字段合并 ──────────────────────────

    def test_partial_merge_queue_len_only(self):
        resp = self.post_orchestra({"queue_len": 3})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json(), {"ok": True, "merged": ["queue_len"]})
        state = self.orch_state()
        self.assertEqual(state["queue_len"], 3)
        # 其余字段不动
        self.assertEqual(state["broker_health"], "unknown")
        self.assertIsNone(state["active_tasks"])
        self.assertIsNone(state["last_task"])
        self.assertIsNone(state["last_sync"])

    # ─── source 刷新时间戳 ─────────────────────

    def test_source_sync_refreshes_sync_timestamp(self):
        self.post_orchestra({"source": "sync", "queue_len": 1})
        rep = self.last_report()
        self.assertGreater(rep["sync"], 0)
        self.assertEqual(rep["broker"], 0)

    def test_default_source_refreshes_broker_timestamp(self):
        # 先 sync 再缺省 source (broker)
        self.post_orchestra({"source": "sync", "queue_len": 1})
        sync_ts = self.last_report()["sync"]
        time.sleep(0.01)
        self.post_orchestra({"queue_len": 2})
        rep = self.last_report()
        self.assertGreater(rep["broker"], 0)
        self.assertEqual(rep["sync"], sync_ts)

    def test_invalid_source_defaults_to_broker(self):
        self.post_orchestra({"source": "foo", "queue_len": 1})
        rep = self.last_report()
        self.assertGreater(rep["broker"], 0)
        self.assertEqual(rep["sync"], 0)

    # ─── 非法字段忽略, 不计入 merged ───────────

    def test_invalid_queue_len_string_ignored(self):
        resp = self.post_orchestra({"queue_len": "abc"})
        self.assertEqual(resp.get_json(), {"ok": True, "merged": []})
        self.assertIsNone(self.orch_state()["queue_len"])

    def test_negative_queue_len_ignored(self):
        resp = self.post_orchestra({"queue_len": -1})
        self.assertEqual(resp.get_json(), {"ok": True, "merged": []})
        self.assertIsNone(self.orch_state()["queue_len"])

    def test_negative_active_tasks_ignored(self):
        self.post_orchestra({"active_tasks": -2})
        self.assertIsNone(self.orch_state()["active_tasks"])

    def test_last_task_non_string_ignored(self):
        self.post_orchestra({"last_task": 123})
        self.assertIsNone(self.orch_state()["last_task"])

    def test_last_task_empty_string_ignored(self):
        self.post_orchestra({"last_task": ""})
        self.assertIsNone(self.orch_state()["last_task"])

    def test_broker_health_empty_string_ignored(self):
        self.post_orchestra({"broker_health": ""})
        self.assertEqual(self.orch_state()["broker_health"], "unknown")

    def test_unknown_field_ignored(self):
        resp = self.post_orchestra({"nonsense": 1, "queue_len": 2})
        self.assertEqual(
            resp.get_json(), {"ok": True, "merged": ["queue_len"]}
        )

    # ─── 全字段合并 ────────────────────────────

    def test_full_merge(self):
        body = {
            "broker_health": "up",
            "queue_len": 2,
            "active_tasks": 1,
            "last_task": "T-20260819-e2e-dsh",
            "last_sync": 1750000000.25,
        }
        resp = self.post_orchestra(body)
        self.assertEqual(
            resp.get_json()["merged"],
            ["broker_health", "queue_len", "active_tasks", "last_task", "last_sync"],
        )
        state = self.orch_state()
        self.assertEqual(state["broker_health"], "up")
        self.assertEqual(state["queue_len"], 2)
        self.assertEqual(state["active_tasks"], 1)
        self.assertEqual(state["last_task"], "T-20260819-e2e-dsh")
        self.assertEqual(state["last_sync"], 1750000000.25)

    # ─── 重复上报覆盖旧值 ──────────────────────

    def test_repeat_report_overwrites_old_value(self):
        self.post_orchestra({"queue_len": 3})
        resp = self.post_orchestra({"queue_len": 5})
        self.assertEqual(resp.get_json(), {"ok": True, "merged": ["queue_len"]})
        self.assertEqual(self.orch_state()["queue_len"], 5)

    # ─── recent_tasks 合并 (D9: 列表整表替换) ─────

    def _tasks(self, n):
        return [
            {"slug": f"T-20260819-task-{i}", "status": "running", "ts": 100.0 + i}
            for i in range(n)
        ]

    def test_recent_tasks_valid_merge(self):
        resp = self.post_orchestra({"recent_tasks": self._tasks(2)})
        self.assertEqual(
            resp.get_json(), {"ok": True, "merged": ["recent_tasks"]}
        )
        tasks = self.orch_state()["recent_tasks"]
        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["slug"], "T-20260819-task-0")
        self.assertEqual(tasks[0]["status"], "running")
        self.assertEqual(tasks[0]["ts"], 100.0)

    def test_recent_tasks_accepts_iso_ts(self):
        resp = self.post_orchestra(
            {"recent_tasks": [
                {"slug": "T-a", "status": "done",
                 "ts": "2026-08-19T10:00:00+00:00"},
            ]}
        )
        self.assertEqual(resp.get_json(), {"ok": True, "merged": ["recent_tasks"]})
        self.assertEqual(
            self.orch_state()["recent_tasks"][0]["ts"],
            "2026-08-19T10:00:00+00:00",
        )

    def test_recent_tasks_invalid_items_dropped(self):
        resp = self.post_orchestra(
            {"recent_tasks": [
                "not-a-dict",                                # 非 dict
                {"slug": "", "status": "done", "ts": 1},     # 空 slug
                {"slug": "T-b", "status": "", "ts": 1},      # 空 status
                {"slug": "T-c", "status": "done", "ts": None},  # bad ts
                {"slug": "T-d", "status": "done", "ts": True},  # bool ts
                {"slug": "T-e", "status": "done", "ts": 1},  # 合法
            ]}
        )
        self.assertEqual(resp.get_json(), {"ok": True, "merged": ["recent_tasks"]})
        tasks = self.orch_state()["recent_tasks"]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["slug"], "T-e")

    def test_recent_tasks_whole_table_replace(self):
        self.post_orchestra({"recent_tasks": self._tasks(2)})
        resp = self.post_orchestra({"recent_tasks": [self._tasks(1)[0]]})
        self.assertEqual(resp.get_json(), {"ok": True, "merged": ["recent_tasks"]})
        tasks = self.orch_state()["recent_tasks"]
        self.assertEqual(len(tasks), 1)  # 整表替换, 不残留旧条目

    def test_recent_tasks_capped_at_8(self):
        resp = self.post_orchestra({"recent_tasks": self._tasks(10)})
        self.assertEqual(resp.get_json(), {"ok": True, "merged": ["recent_tasks"]})
        tasks = self.orch_state()["recent_tasks"]
        self.assertEqual(len(tasks), 8)  # cap 8
        self.assertEqual(tasks[-1]["slug"], "T-20260819-task-7")

    def test_recent_tasks_non_list_ignored(self):
        resp = self.post_orchestra({"recent_tasks": "T-xxx"})
        self.assertEqual(resp.get_json(), {"ok": True, "merged": []})
        self.assertEqual(self.orch_state()["recent_tasks"], [])

    def test_recent_tasks_empty_list_clears(self):
        self.post_orchestra({"recent_tasks": self._tasks(2)})
        resp = self.post_orchestra({"recent_tasks": []})
        self.assertEqual(resp.get_json(), {"ok": True, "merged": ["recent_tasks"]})
        self.assertEqual(self.orch_state()["recent_tasks"], [])

    # ─── host 合并 (D10: 设备负载/内存逐项校验) ──

    def test_host_valid_merge(self):
        resp = self.post_orchestra({"host": {"load1": 0.5, "mem_pct": 60}})
        self.assertEqual(resp.get_json(), {"ok": True, "merged": ["host"]})
        self.assertEqual(
            self.orch_state()["host"], {"load1": 0.5, "mem_pct": 60}
        )

    def test_host_null_values_clears(self):
        resp = self.post_orchestra({"host": {"load1": None, "mem_pct": None}})
        self.assertEqual(resp.get_json(), {"ok": True, "merged": ["host"]})
        self.assertEqual(
            self.orch_state()["host"], {"load1": None, "mem_pct": None}
        )

    def test_host_invalid_items_dropped(self):
        # 全部非法 → 不合并, host 不变
        resp = self.post_orchestra(
            {"host": {"load1": "heavy", "mem_pct": 101, "extra": 5}}
        )
        self.assertEqual(resp.get_json(), {"ok": True, "merged": []})
        self.assertEqual(self.orch_state()["host"], {})
        # 部分非法 → 合法项覆盖, 非法项保留原值
        self.post_orchestra({"host": {"load1": 0.3, "mem_pct": 38}})
        resp = self.post_orchestra({"host": {"load1": True, "mem_pct": 45}})
        self.assertEqual(resp.get_json(), {"ok": True, "merged": ["host"]})
        self.assertEqual(
            self.orch_state()["host"], {"load1": 0.3, "mem_pct": 45}
        )

    def test_host_non_dict_ignored(self):
        resp = self.post_orchestra({"host": [0.3, 38]})
        self.assertEqual(resp.get_json(), {"ok": True, "merged": []})
        self.assertEqual(self.orch_state()["host"], {})

    def test_host_merged_echo_with_other_fields(self):
        """merged 顺序回显: host 与其它字段同报时均在数组内"""
        resp = self.post_orchestra(
            {"queue_len": 4, "host": {"load1": 0.3, "mem_pct": 38}}
        )
        self.assertEqual(
            resp.get_json(), {"ok": True, "merged": ["queue_len", "host"]}
        )

    # ─── /api/dashboard 携带 orchestra 块 ──────

    def test_dashboard_returns_orchestra_blocks(self):
        self.post_orchestra(
            {"queue_len": 7, "recent_tasks": self._tasks(2),
             "host": {"load1": 0.3, "mem_pct": 38}}
        )
        resp = self.client.get("/api/dashboard", headers=AUTH)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("orchestra", data)
        self.assertIn("orchestra_last_report", data)
        self.assertEqual(data["orchestra"]["queue_len"], 7)
        self.assertEqual(len(data["orchestra"]["recent_tasks"]), 2)
        self.assertEqual(
            data["orchestra"]["host"], {"load1": 0.3, "mem_pct": 38}
        )

    def test_dashboard_carries_self_status(self):
        """self_status 初始块经 /api/dashboard 可达"""
        resp = self.client.get("/api/dashboard", headers=AUTH)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("self_status", resp.get_json())
        self.assertIsNone(resp.get_json()["self_status"]["load1"])
        self.assertIsNone(resp.get_json()["self_status"]["mem_pct"])

    # ─── /health 新鲜度 ────────────────────────

    def test_health_age_seconds_orchestra(self):
        age = self.client.get("/health").get_json()["age_seconds"]
        self.assertIn("orchestra_broker", age)
        self.assertIn("orchestra_sync", age)
        # 未上报 = None
        self.assertIsNone(age["orchestra_broker"])
        self.assertIsNone(age["orchestra_sync"])

    def test_health_age_after_report(self):
        self.post_orchestra({"queue_len": 1})  # broker 上报
        age = self.client.get("/health").get_json()["age_seconds"]
        self.assertIsInstance(age["orchestra_broker"], int)
        self.assertGreaterEqual(age["orchestra_broker"], 0)
        self.assertIsNone(age["orchestra_sync"])

        self.post_orchestra({"source": "sync", "queue_len": 2})
        age = self.client.get("/health").get_json()["age_seconds"]
        self.assertIsInstance(age["orchestra_sync"], int)
        self.assertGreaterEqual(age["orchestra_sync"], 0)


if __name__ == "__main__":
    unittest.main()
