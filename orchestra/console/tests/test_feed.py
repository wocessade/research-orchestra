import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from console_feed import cmd_refresh

MONITOR = {"orchestra": {"queue_len": 1, "recent_tasks": [], "host": {"load1": 0.1, "mem_pct": 20}},
           "orchestra_last_report": {"broker": 1755700000}}


def _fresh_monitor(*args, **kwargs):
    m = copy.deepcopy(MONITOR)
    m["orchestra_last_report"]["broker"] = int(time.time()) - 30
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
        self.assertIn("upcoming_personal", status)
        self.assertIsInstance(status["upcoming_personal"], list)
        ics_bytes = (self.out / "system.ics").read_bytes()
        self.assertNotIn(b"\r\r", ics_bytes)
        self.assertIn(b"BEGIN:VCALENDAR\r\n", ics_bytes)
        personal_bytes = (self.out / "personal.ics").read_bytes()
        self.assertNotIn(b"\r\r", personal_bytes)
        self.assertIn(b"BEGIN:VCALENDAR\r\n", personal_bytes)
        ics = (self.out / "system.ics").read_text(encoding="utf-8")
        self.assertIn("夜间雷达", ics)
        self.assertIn("今天的事", (self.out / "personal.ics").read_text(encoding="utf-8"))

    def test_refresh_degrades_when_fetch_fails(self):
        with mock.patch("console_feed.fetch_dashboard", return_value=(None, "no_token")):
            rc = cmd_refresh(self._args())
        self.assertEqual(rc, 0)  # 降级不报错
        status = json.loads((self.out / "status.json").read_text(encoding="utf-8"))
        self.assertTrue(status["degraded"])
        self.assertIn("未配置 token", status["walnut"])
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
            raw = (self.out / name).read_bytes()
            self.assertNotIn(b"\r\r", raw)
            self.assertIn(b"BEGIN:VCALENDAR\r\n", raw)

    def test_refresh_merges_ops_into_messages_json(self):
        with mock.patch("console_feed.fetch_dashboard", return_value=(None, "down")):
            rc = cmd_refresh(self._args())
        self.assertEqual(rc, 0)
        msgs = json.loads((self.out / "messages.json").read_text(encoding="utf-8"))
        self.assertTrue(any(a["title"] in ("4B 离线", "核桃派离线") for a in msgs["alerts"]))
        self.assertEqual(msgs["latest"][0]["title"], "早上好")

    def test_refresh_sync_skip_without_bash_or_scp(self):
        with mock.patch("console_feed.fetch_dashboard", side_effect=_fresh_monitor), \
             mock.patch("console_feed.shutil.which", return_value=None), \
             mock.patch("console_feed.subprocess.run") as run:
            rc = cmd_refresh(self._args(no_sync=False))
        self.assertEqual(rc, 0)
        run.assert_not_called()
        log = (self.out / "feed.log").read_text(encoding="utf-8")
        self.assertIn("缺 bash 与 scp", log)

    def test_refresh_sync_scp_defaults_host(self):
        def which(name):
            return r"C:\Windows\System32\OpenSSH\scp.exe" if name == "scp" else None

        fake = mock.Mock(returncode=0)
        with mock.patch("console_feed.fetch_dashboard", side_effect=_fresh_monitor), \
             mock.patch("console_feed.shutil.which", side_effect=which), \
             mock.patch("console_feed.subprocess.run", return_value=fake) as run, \
             mock.patch.dict(os.environ, {"ORCHESTRA_SSH_HOST": "", "ORCHESTRA_REMOTE_ROOT": ""}, clear=False):
            rc = cmd_refresh(self._args(no_sync=False))
        self.assertEqual(rc, 0)
        self.assertEqual(run.call_count, 2)
        first = run.call_args_list[0].args[0]
        self.assertEqual(first[0], r"C:\Windows\System32\OpenSSH\scp.exe")
        self.assertEqual(first[1], "-rq")
        self.assertIn("liuxfs@192.168.0.250:/home/liuxfs/broker-data/results/.", first[2])
        if sys.platform == "win32":
            for call in run.call_args_list:
                self.assertEqual(
                    call.kwargs.get("creationflags"),
                    subprocess.CREATE_NO_WINDOW)
        log = (self.out / "feed.log").read_text(encoding="utf-8")
        self.assertIn("sync_pull scp", log)
        self.assertIn("host=192.168.0.250", log)

    def test_refresh_sync_windows_prefers_scp_over_bash(self):
        def which(name):
            if name == "scp":
                return r"C:\Windows\System32\OpenSSH\scp.exe"
            if name == "bash":
                return r"C:\Git\bin\bash.exe"
            return None

        fake = mock.Mock(returncode=0)
        with mock.patch("console_feed.fetch_dashboard", side_effect=_fresh_monitor), \
             mock.patch("console_feed.shutil.which", side_effect=which), \
             mock.patch("console_feed.sys.platform", "win32"), \
             mock.patch("console_feed.subprocess.run", return_value=fake) as run:
            rc = cmd_refresh(self._args(no_sync=False))
        self.assertEqual(rc, 0)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0][0],
                         r"C:\Windows\System32\OpenSSH\scp.exe")
        for call in run.call_args_list:
            self.assertEqual(
                call.kwargs.get("creationflags"),
                subprocess.CREATE_NO_WINDOW)

    def test_refresh_appends_exam_alert_once(self):
        alert = {
            "exam_found": True,
            "exam_names": ["入学考试"],
            "leaf_count": 1,
            "use_count": 1,
            "found_at": "2026-08-25T09:00:00+00:00",
            "source": "chapter",
            "alerted": True,
        }
        (self.results / "exam_alert.json").write_text(
            json.dumps(alert, ensure_ascii=False), encoding="utf-8")
        with mock.patch("console_feed.fetch_dashboard", side_effect=_fresh_monitor):
            self.assertEqual(cmd_refresh(self._args()), 0)
            self.assertEqual(cmd_refresh(self._args()), 0)
        md = (self.console / "messages.md").read_text(encoding="utf-8")
        self.assertEqual(md.count("- 考试："), 1)
        msgs = json.loads((self.out / "messages.json").read_text(encoding="utf-8"))
        self.assertTrue(
            any("雨课堂：考试已放出" in (m.get("title") or "") for m in msgs["latest"]))


if __name__ == "__main__":
    unittest.main()
