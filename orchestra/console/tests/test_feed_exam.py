"""parse/merge/append 雨课堂 exam_alert 与 exam_watch_beat。"""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from feed_exam import (
    append_exam_marker,
    exam_beat_ops,
    merge_exam_alert,
    parse_exam_alert,
    parse_exam_beat,
)


ALERT = {
    "exam_found": True,
    "exam_names": ["入学考试"],
    "leaf_count": 1,
    "use_count": 1,
    "found_at": "2026-08-25T09:00:00+00:00",
    "source": "eval+chapter",
    "alerted": True,
}


class ParseExamAlertTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "exam_alert.json"

    def test_missing_file_is_none(self):
        self.assertIsNone(parse_exam_alert(self.path))

    def test_invalid_json_is_none(self):
        self.path.write_text("{", encoding="utf-8")
        self.assertIsNone(parse_exam_alert(self.path))

    def test_valid_alert(self):
        self.path.write_text(json.dumps(ALERT), encoding="utf-8")
        data = parse_exam_alert(self.path)
        self.assertTrue(data["exam_found"])
        self.assertEqual(data["exam_names"], ["入学考试"])


class MergeExamAlertTest(unittest.TestCase):
    def test_inserts_latest_when_new(self):
        human = {"latest": [{"title": "早上好", "text": "x"}], "pending": [], "alerts": []}
        out = merge_exam_alert(human, ALERT, "")
        self.assertEqual(out["latest"][0]["title"], "雨课堂：考试已放出（1个）——入学考试")
        self.assertEqual(out["latest"][1]["title"], "早上好")

    def test_skips_when_found_at_already_in_messages(self):
        human = {"latest": [{"title": "早上好"}], "pending": [], "alerts": []}
        text = "found_at=2026-08-25T09:00:00+00:00"
        out = merge_exam_alert(human, ALERT, text)
        self.assertEqual(out["latest"][0]["title"], "早上好")

    def test_ignores_non_found(self):
        human = {"latest": [], "pending": [], "alerts": []}
        out = merge_exam_alert(human, {"exam_found": False}, "")
        self.assertEqual(out["latest"], [])


class AppendExamMarkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "messages.md"
        self.path.write_text("## 2026-08-21 08:00 — 早上好\n你好\n", encoding="utf-8")

    def test_writes_exam_prefix_once(self):
        self.assertTrue(append_exam_marker(self.path, ALERT))
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("- 考试：雨课堂：考试已放出（1个）——入学考试", text)
        self.assertIn("2026-08-25T09:00:00+00:00", text)
        self.assertFalse(append_exam_marker(self.path, ALERT))
        self.assertEqual(text.count("- 考试："), 1)

    def test_cookie_expired_goes_to_alert(self):
        expired = {
            "exam_found": False,
            "cookie_expired": True,
            "found_at": "2026-08-25T10:00:00+00:00",
            "source": "auth",
            "message": "雨课堂 cookie 已过期，请重新导出并上传 4B",
        }
        self.assertTrue(append_exam_marker(self.path, expired))
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("- 告警：", text)
        self.assertIn("cookie 已过期", text)
        self.assertFalse(append_exam_marker(self.path, expired))


class ParseExamBeatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "exam_watch_beat.json"

    def test_missing_file_is_none(self):
        self.assertIsNone(parse_exam_beat(self.path))

    def test_valid_beat(self):
        self.path.write_text(json.dumps({"status": "ok", "last_check_ts": 1}), encoding="utf-8")
        data = parse_exam_beat(self.path)
        self.assertEqual(data["status"], "ok")


class ExamBeatOpsTest(unittest.TestCase):
    NOW = datetime(2026, 8, 25, 12, 0, 0)

    def _beat(self, **kw):
        base = {"status": "ok", "last_check_ts": self.NOW.timestamp(),
                "exam_found": False, "cookie_expired": False,
                "use_count": 0, "leaf_count": 0, "last_error": None}
        base.update(kw)
        return base

    def test_missing_beat_is_silent(self):
        ops = exam_beat_ops(None, now=self.NOW)
        self.assertEqual(ops["items"], [])

    def test_ok_beat_goes_latest(self):
        ops = exam_beat_ops(self._beat(), now=self.NOW)
        self.assertEqual(ops["item_type"], "latest")
        self.assertEqual(ops["items"][0]["title"], "雨课堂监控")
        self.assertIn("正常", ops["items"][0]["text"])

    def test_stale_beat_goes_alerts(self):
        beat = self._beat(last_check_ts=self.NOW.timestamp() - 3600)
        ops = exam_beat_ops(beat, now=self.NOW)
        self.assertEqual(ops["item_type"], "alerts")
        self.assertIn("心跳超时", ops["items"][0]["text"])

    def test_stale_beat_with_fresh_file_goes_alerts(self):
        beat = self._beat(last_check_ts=self.NOW.timestamp() - 3600)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "exam_watch_beat.json"
            path.write_text("{}", encoding="utf-8")
            ops = exam_beat_ops(beat, beat_path=path, now=self.NOW)
        self.assertEqual(ops["item_type"], "alerts")
        self.assertIn("心跳超时", ops["items"][0]["text"])

    def test_stale_beat_with_stale_file_is_silent(self):
        # 文件也旧 = 本机 refresh 停摆（睡眠/断网），非 exam-watch 中断，不误报
        beat = self._beat(last_check_ts=self.NOW.timestamp() - 3600)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "exam_watch_beat.json"
            path.write_text("{}", encoding="utf-8")
            old = self.NOW.timestamp() - 100 * 60
            import os
            os.utime(path, (old, old))
            ops = exam_beat_ops(beat, beat_path=path, now=self.NOW)
        self.assertEqual(ops["items"], [])

    def test_error_status_latest_with_err(self):
        beat = self._beat(status="error", last_error="timeout")
        ops = exam_beat_ops(beat, now=self.NOW)
        self.assertEqual(ops["item_type"], "latest")
        self.assertIn("timeout", ops["items"][0]["text"])

    def test_done_cookie_expired_goes_alerts(self):
        beat = self._beat(status="done", cookie_expired=True)
        ops = exam_beat_ops(beat, now=self.NOW)
        self.assertEqual(ops["item_type"], "alerts")
        self.assertIn("cookie 已过期", ops["items"][0]["text"])

    def test_done_exam_found_no_item(self):
        beat = self._beat(status="done", exam_found=True)
        ops = exam_beat_ops(beat, now=self.NOW)
        self.assertEqual(ops["items"], [])


if __name__ == "__main__":
    unittest.main()
