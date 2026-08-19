"""send_email.py 退出码契约测试（M-4：确定性拒信 exit 10，模糊失败 exit 1）。"""
import smtplib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import send_email


class SendEmailExitCodeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.body = Path(self.tmp.name) / "body.txt"
        self.body.write_text("digest", encoding="utf-8")
        patcher = mock.patch.dict(
            "os.environ", {"SMTP_USER": "u@qq.com", "SMTP_PASS": "pw"}, clear=False
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, side_effect):
        with mock.patch("smtplib.SMTP_SSL") as mock_smtp:
            s = mock_smtp.return_value
            s.login.return_value = None
            s.sendmail.side_effect = side_effect
            with mock.patch.object(
                sys, "argv", ["send_email.py", "主题", str(self.body)]
            ):
                return send_email.main()

    def test_recipients_refused_returns_not_sent(self):
        rc = self._run(smtplib.SMTPRecipientsRefused({"a@b.c": (550, b"no")}))
        self.assertEqual(rc, send_email.NOT_SENT_EXIT_CODE)

    def test_data_error_returns_not_sent(self):
        rc = self._run(smtplib.SMTPDataError(552, b"quota exceeded"))
        self.assertEqual(rc, send_email.NOT_SENT_EXIT_CODE)

    def test_ambiguous_failure_returns_unknown(self):
        rc = self._run(OSError("connection dropped mid-send"))
        self.assertEqual(rc, 1)

    def test_success_returns_zero(self):
        rc = self._run(None)
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
