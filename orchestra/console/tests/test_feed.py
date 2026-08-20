import argparse
import copy
import json
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from console_feed import cmd_refresh

MONITOR = {"orchestra": {"queue_len": 1, "recent_tasks": [], "host": {"load1": 0.1, "mem_pct": 20}},
           "orchestra_last_report": {"ts": 1755700000}}


def _fresh_monitor(*args, **kwargs):
    m = copy.deepcopy(MONITOR)
    m["orchestra_last_report"]["ts"] = int(time.time()) - 30
    return m, None


class RefreshTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.console = base / "console"
        self.console.mkdir()
        (self.console / "console-schedule.toml").write_text(
            '[system]\nradar = "23:30"\n\n[[personal]]\n'
            f'date = "{date.today():%Y-%m-%d}"\ntime = "09:00"\ntitle = "今天的事"\n',
            encoding="utf-8")
        (self.console / "messages.md").write_text(
            "## 2026-08-21 08:00 — 早上好\n第一条\n", encoding="utf-8")
        self.out = base / "out"
        self.results = base / "results"
        self.results.mkdir()
        self.research = base / ".research"

    def tearDown(self):
        self.tmp.cleanup()

    def _args(self, **kw):
        defaults = dict(console_dir=str(self.console), out_dir=str(self.out),
                        results_root=str(self.results),
                        research_root=str(self.research), no_sync=True)
        defaults.update(kw)
        return argparse.Namespace(**defaults)

    def test_refresh_writes_all_outputs(self):
        with mock.patch("console_feed.fetch_dashboard", side_effect=_fresh_monitor):
            rc = cmd_refresh(self._args())
        self.assertEqual(rc, 0)
        for name in ("status.json", "radar.json", "messages.json",
                     "system.ics", "personal.ics", "digest.html",
                     "messages.html", "feed.log"):
            self.assertTrue((self.out / name).exists(), name)
        status = json.loads((self.out / "status.json").read_text(encoding="utf-8"))
        self.assertIn("在线", status["4b"])
        self.assertEqual(status["queue_len"], 1)
        self.assertEqual(status["experiments"], {"available": False, "cards": []})
        ics = (self.out / "system.ics").read_text(encoding="utf-8")
        self.assertIn("夜间雷达", ics)
        self.assertIn("今天的事", (self.out / "personal.ics").read_text(encoding="utf-8"))

    def test_refresh_degrades_when_fetch_fails(self):
        with mock.patch("console_feed.fetch_dashboard", return_value=(None, "no_token")):
            rc = cmd_refresh(self._args())
        self.assertEqual(rc, 0)  # 降级不报错
        status = json.loads((self.out / "status.json").read_text(encoding="utf-8"))
        self.assertTrue(status["degraded"])
        self.assertIn("离线", status["walnut"])
        for name in ("messages.json", "radar.json", "digest.html", "messages.html"):
            self.assertTrue((self.out / name).exists(), name)

    def test_refresh_bad_schedule_keeps_ics_and_alerts(self):
        (self.console / "console-schedule.toml").write_text("[[personal]]", encoding="utf-8")
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "system.ics").write_text("OLD", encoding="utf-8")  # 伪造上次产物
        with mock.patch("console_feed.fetch_dashboard", side_effect=_fresh_monitor):
            rc = cmd_refresh(self._args())
        self.assertEqual(rc, 0)
        self.assertEqual((self.out / "system.ics").read_text(encoding="utf-8"), "OLD")
        msgs = (self.console / "messages.md").read_text(encoding="utf-8")
        self.assertIn("自动告警", msgs)
        self.assertIn("日程解析失败", msgs)

    def test_refresh_bad_schedule_writes_empty_ics_on_first_run(self):
        (self.console / "console-schedule.toml").write_text("[[personal]]", encoding="utf-8")
        with mock.patch("console_feed.fetch_dashboard", side_effect=_fresh_monitor):
            rc = cmd_refresh(self._args())
        self.assertEqual(rc, 0)
        for name in ("system.ics", "personal.ics"):
            self.assertTrue((self.out / name).exists(), name)
            self.assertIn("BEGIN:VCALENDAR",
                          (self.out / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
