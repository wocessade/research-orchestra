import unittest
from unittest import mock

from feed_status import (
    DEFAULT_MONITOR_API,
    FRESH_S,
    aggregate,
    dashboard_url,
    fetch_dashboard,
)

DASH = {
    "orchestra": {
        "queue_len": 2, "active_tasks": 1, "last_task": "T-20260820-model-smoke",
        "last_sync": 1755700000,
        "recent_tasks": [{"slug": f"T-{i}", "status": "done", "ts": 1755700000 - i * 60}
                         for i in range(12)],
        "host": {"load1": 0.3, "mem_pct": 38},
    },
    "orchestra_last_report": {"broker": 1755700000},
}
NOW = 1755700030.0  # 最后上报 30s 前

_SCHED = {"system": {"radar": "23:30"}, "personal": []}


class FetchDashboardTest(unittest.TestCase):
    def test_success(self):
        resp = mock.Mock()
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        resp.read.return_value = b'{"ok": true}'
        with mock.patch("feed_status.urllib.request.urlopen", return_value=resp) as u:
            state, err = fetch_dashboard(DEFAULT_MONITOR_API, "tok")
        self.assertEqual(state, {"ok": True})
        self.assertIsNone(err)
        req = u.call_args.args[0]
        self.assertEqual(req.headers.get("X-monitor-token"), "tok")

    def test_no_token(self):
        state, err = fetch_dashboard(DEFAULT_MONITOR_API, None)
        self.assertIsNone(state)
        self.assertEqual(err, "no_token")

    def test_network_error(self):
        import urllib.error
        with mock.patch("feed_status.urllib.request.urlopen",
                        side_effect=urllib.error.URLError("boom")):
            state, err = fetch_dashboard(DEFAULT_MONITOR_API, "tok")
        self.assertIsNone(state)
        self.assertIn("boom", err)

    def test_bad_json(self):
        resp = mock.Mock()
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        resp.read.return_value = b"not json"
        with mock.patch("feed_status.urllib.request.urlopen", return_value=resp):
            state, err = fetch_dashboard(DEFAULT_MONITOR_API, "tok")
        self.assertIsNone(state)
        self.assertIsNotNone(err)

    def test_invalid_dashboard_json_shape(self):
        resp = mock.Mock()
        resp.__enter__ = mock.Mock(return_value=resp)
        resp.__exit__ = mock.Mock(return_value=False)
        resp.read.return_value = b"[1, 2]"
        with mock.patch("feed_status.urllib.request.urlopen", return_value=resp):
            state, err = fetch_dashboard(DEFAULT_MONITOR_API, "tok")
        self.assertIsNone(state)
        self.assertEqual(err, "invalid_dashboard")


class DashboardUrlTest(unittest.TestCase):
    def test_derivation(self):
        self.assertEqual(dashboard_url(DEFAULT_MONITOR_API),
                         "http://192.168.0.200:5000/api/dashboard")


class AggregateTest(unittest.TestCase):
    def test_online_full(self):
        status = aggregate(DASH, None, _SCHED, NOW)
        self.assertIn("在线", status["4b"])
        self.assertIn("load 0.3", status["4b"])
        self.assertIn("mem 38%", status["4b"])
        self.assertEqual(status["queue_len"], 2)
        self.assertEqual(status["active_tasks"], 1)
        self.assertFalse(status["degraded"])

    def test_offline_degraded(self):
        status = aggregate(None, "no_token", _SCHED, NOW)
        self.assertIn("离线", status["4b"])
        self.assertIn("离线", status["walnut"])
        self.assertTrue(status["degraded"])
        self.assertEqual(status["degraded_reason"], "no_token")

    def test_recent_tasks_truncated(self):
        status = aggregate(DASH, None, _SCHED, NOW)
        self.assertEqual(len(status["recent_tasks"]), 8)

    def test_next_from_schedule(self):
        status = aggregate(DASH, None, _SCHED, NOW)
        self.assertTrue(status["next"])
        self.assertIn(status["next"][0]["label"],
                      {"雷达", "冷备到核桃派", "NAS 盘内备份", "周日整理"})
        self.assertIn("后", status["next"][0]["in_text"])

    def test_fresh_exactly_at_boundary_is_online(self):
        dashboard = {"orchestra_last_report": {"ts": NOW - FRESH_S},
                     "orchestra": {}}
        status = aggregate(dashboard, None, None, NOW)
        self.assertIn("在线", status["4b"])

    def test_stale_report_is_offline(self):
        dashboard = {"orchestra_last_report": {"ts": NOW - FRESH_S - 0.1},
                     "orchestra": {}}
        status = aggregate(dashboard, None, None, NOW)
        self.assertIn("离线", status["4b"])

    def test_recent_task_does_not_replace_missing_report(self):
        dashboard = {"orchestra": {"recent_tasks": [{"ts": NOW - 1}]}}
        status = aggregate(dashboard, None, None, NOW)
        self.assertIn("离线", status["4b"])


if __name__ == "__main__":
    unittest.main()

