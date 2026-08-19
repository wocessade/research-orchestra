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

    # ─── /api/dashboard 携带 orchestra 块 ──────

    def test_dashboard_returns_orchestra_blocks(self):
        self.post_orchestra({"queue_len": 7})
        resp = self.client.get("/api/dashboard", headers=AUTH)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("orchestra", data)
        self.assertIn("orchestra_last_report", data)
        self.assertEqual(data["orchestra"]["queue_len"], 7)

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
