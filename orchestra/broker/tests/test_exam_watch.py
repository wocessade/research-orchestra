"""雨课堂 exam-watch：判定、状态幂等、401/超时、邮件与退出码。"""
from __future__ import annotations

import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError, URLError

import exam_watch


EVAL_ZERO = {
    "data": {
        "evaluation_tag_list": [
            {"id": 12, "name": "考试", "use_count": 0, "score_proportion": 0.5},
            {"id": 1, "name": "作业", "use_count": 3},
        ]
    }
}
EVAL_ONE = {
    "data": {
        "evaluation_tag_list": [
            {"id": 12, "name": "考试", "use_count": 1, "score_proportion": 0.5},
        ]
    }
}
CHAPTER_NONE = {
    "data": {
        "course_chapter": [
            {
                "name": "入学",
                "section_leaf_list": [
                    {"id": 1, "name": "课件A", "leaf_type": 7},
                ],
            }
        ]
    }
}
CHAPTER_EXAM = {
    "data": {
        "course_chapter": [
            {
                "name": "考核",
                "section_leaf_list": [
                    {"id": 9, "name": "入学考试", "leaf_type": 5},
                    {"id": 8, "name": "课件B", "leaf_type": 7},
                ],
            }
        ]
    }
}


def _json_resp(payload: dict):
    raw = json.dumps(payload).encode("utf-8")
    resp = BytesIO(raw)
    resp.status = 200
    return resp


class ExtractSignalsTest(unittest.TestCase):
    def test_use_count_from_exam_name(self):
        self.assertEqual(exam_watch.exam_use_count(EVAL_ZERO), 0)
        self.assertEqual(exam_watch.exam_use_count(EVAL_ONE), 1)

    def test_missing_exam_name_is_zero(self):
        data = {"data": {"evaluation_tag_list": [{"id": 12, "name": "测验", "use_count": 9}]}}
        self.assertEqual(exam_watch.exam_use_count(data), 0)

    def test_leaf_type_5_names(self):
        names = exam_watch.exam_leaf_names(CHAPTER_EXAM)
        self.assertEqual(names, ["入学考试"])
        self.assertEqual(exam_watch.exam_leaf_names(CHAPTER_NONE), [])


class ExamWatchRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.cookie = base / "exam_cookie.txt"
        self.cookie.write_text(
            "sessionid=s1; csrftoken=tok; uv_id=u1; university_id=2937",
            encoding="utf-8",
        )
        self.state = base / "state.json"
        self.alert = base / "results" / "exam_alert.json"
        self.beat = base / "results" / "exam_watch_beat.json"
        self.sender = base / "send_email.py"
        self.sender.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        self.mail_calls = []

    def _run(self, eval_body, chapter_body, mail_rc=0):
        def urlopen(req, timeout=15):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "get_sku_evaluation_list_readonly" in url:
                return _json_resp(eval_body)
            if "course/chapter" in url:
                return _json_resp(chapter_body)
            raise AssertionError(url)

        def send_mail(subject, body):
            self.mail_calls.append((subject, body))
            return mail_rc

        with mock.patch("exam_watch.urllib.request.urlopen", side_effect=urlopen):
            return exam_watch.run(
                classroom_id="25631011",
                sku_id="12651805",
                cookie_file=self.cookie,
                state_file=self.state,
                alert_file=self.alert,
                beat_file=self.beat,
                send_mail=send_mail,
            )

    def test_first_baseline_zero_silent(self):
        rc = self._run(EVAL_ZERO, CHAPTER_NONE)
        self.assertEqual(rc, 0)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertFalse(state["exam_found"])
        self.assertEqual(state["use_count"], 0)
        self.assertFalse(self.alert.exists())
        self.assertEqual(self.mail_calls, [])
        beat = json.loads(self.beat.read_text(encoding="utf-8"))
        self.assertEqual(beat["status"], "ok")
        self.assertFalse(beat["exam_found"])
        self.assertIn("last_check_ts", beat)

    def test_first_round_already_released_alerts(self):
        rc = self._run(EVAL_ONE, CHAPTER_EXAM)
        self.assertEqual(rc, 0)
        alert = json.loads(self.alert.read_text(encoding="utf-8"))
        self.assertTrue(alert["exam_found"])
        self.assertEqual(alert["use_count"], 1)
        self.assertEqual(alert["leaf_count"], 1)
        self.assertEqual(alert["exam_names"], ["入学考试"])
        self.assertTrue(alert["alerted"])
        self.assertEqual(len(self.mail_calls), 1)
        self.assertIn("考试", self.mail_calls[0][0])
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertTrue(state["exam_found"])

    def test_eval_signal_alone_is_enough(self):
        rc = self._run(EVAL_ONE, CHAPTER_NONE)
        self.assertEqual(rc, 0)
        alert = json.loads(self.alert.read_text(encoding="utf-8"))
        self.assertTrue(alert["exam_found"])
        self.assertEqual(alert["use_count"], 1)
        self.assertEqual(alert["leaf_count"], 0)

    def test_leaf_signal_alone_is_enough(self):
        rc = self._run(EVAL_ZERO, CHAPTER_EXAM)
        self.assertEqual(rc, 0)
        alert = json.loads(self.alert.read_text(encoding="utf-8"))
        self.assertTrue(alert["exam_found"])
        self.assertEqual(alert["exam_names"], ["入学考试"])

    def test_already_found_is_idempotent(self):
        self._run(EVAL_ONE, CHAPTER_EXAM)
        self.mail_calls.clear()
        rc = self._run(EVAL_ONE, CHAPTER_EXAM)
        self.assertEqual(rc, 0)
        self.assertEqual(self.mail_calls, [])

    def test_http_401_alerts_once_then_stops(self):
        def urlopen(req, timeout=15):
            raise HTTPError(
                "https://x/eval", 401, "Unauthorized",
                hdrs=None, fp=BytesIO(b'{"detail":"Authentication credentials were not provided"}'),
            )

        def send_mail(subject, body):
            self.mail_calls.append((subject, body))
            return 0

        with mock.patch("exam_watch.urllib.request.urlopen", side_effect=urlopen):
            rc = exam_watch.run(
                classroom_id="25631011", sku_id="12651805",
                cookie_file=self.cookie, state_file=self.state,
                alert_file=self.alert, beat_file=self.beat,
                send_mail=send_mail,
            )
        self.assertEqual(rc, 0)
        alert = json.loads(self.alert.read_text(encoding="utf-8"))
        self.assertFalse(alert["exam_found"])
        self.assertIn("cookie", alert.get("message", "").lower() + json.dumps(alert, ensure_ascii=False).lower())
        self.assertEqual(len(self.mail_calls), 1)
        beat = json.loads(self.beat.read_text(encoding="utf-8"))
        self.assertEqual(beat["status"], "done")
        self.assertTrue(beat["cookie_expired"])

        self.mail_calls.clear()
        with mock.patch("exam_watch.urllib.request.urlopen", side_effect=urlopen):
            rc2 = exam_watch.run(
                classroom_id="25631011", sku_id="12651805",
                cookie_file=self.cookie, state_file=self.state,
                alert_file=self.alert, beat_file=self.beat,
                send_mail=send_mail,
            )
        self.assertEqual(rc2, 0)
        self.assertEqual(self.mail_calls, [])

    def test_timeout_records_error_no_alert(self):
        def urlopen(req, timeout=15):
            raise URLError("timed out")

        with mock.patch("exam_watch.urllib.request.urlopen", side_effect=urlopen):
            rc = exam_watch.run(
                classroom_id="25631011", sku_id="12651805",
                cookie_file=self.cookie, state_file=self.state,
                alert_file=self.alert, beat_file=self.beat,
                send_mail=lambda *_: 0,
            )
        self.assertEqual(rc, 0)
        self.assertFalse(self.alert.exists())
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertTrue(state.get("last_error"))
        self.assertEqual(self.mail_calls, [])
        beat = json.loads(self.beat.read_text(encoding="utf-8"))
        self.assertEqual(beat["status"], "error")
        self.assertIn("timed out", beat["last_error"])

    def test_mail_failure_retries_next_round(self):
        rc = self._run(EVAL_ONE, CHAPTER_EXAM, mail_rc=10)
        self.assertEqual(rc, 0)
        self.assertTrue(self.alert.exists())
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertTrue(state["mail_failed"])
        self.assertEqual(len(self.mail_calls), 1)

        stamp = self.alert.read_text(encoding="utf-8")
        rc2 = self._run(EVAL_ONE, CHAPTER_EXAM, mail_rc=0)
        self.assertEqual(rc2, 0)
        self.assertEqual(len(self.mail_calls), 2)
        self.assertEqual(self.alert.read_text(encoding="utf-8"), stamp)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertFalse(state["mail_failed"])


class CookieHeaderTest(unittest.TestCase):
    def test_headers_include_csrf_and_ids(self):
        headers = exam_watch.build_headers(
            "sessionid=s; csrftoken=tok; uv_id=uv99", "25631011"
        )
        self.assertEqual(headers["x-csrftoken"], "tok")
        self.assertEqual(headers["uv-id"], "uv99")
        self.assertEqual(headers["classroom-id"], "25631011")
        self.assertEqual(headers["xt-agent"], "web")
        self.assertEqual(headers["xtbz"], "ykt")
        self.assertIn("sessionid=s", headers["Cookie"])


if __name__ == "__main__":
    unittest.main()
