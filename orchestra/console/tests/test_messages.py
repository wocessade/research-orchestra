import unittest
from pathlib import Path

from feed_messages import append_alert, build_messages_html, parse_messages

SAMPLE = """## 2026-08-21 08:05 — deploy 窗口建议
4B 已 14 天未部署，032 修复包待真机验证

## 2026-08-21 08:00 — 雷达日报已出
top5 中 2 篇与你方向相关，建议精读
- 待决：SD 旧副本是否删除？

## 2026-08-20 23:59 — 自动告警
- 告警：usage-monitor 不可达
"""


class ParseMessagesTest(unittest.TestCase):
    def test_sections_sorted_desc(self):
        msgs = parse_messages(SAMPLE)
        self.assertEqual([m["title"] for m in msgs["latest"]],
                         ["deploy 窗口建议", "雷达日报已出", "自动告警"])

    def test_text_accumulated(self):
        msgs = parse_messages(SAMPLE)
        self.assertIn("4B 已 14 天未部署", msgs["latest"][0]["text"])

    def test_pending_and_alerts(self):
        msgs = parse_messages(SAMPLE)
        self.assertEqual([p["text"] for p in msgs["pending"]], ["SD 旧副本是否删除？"])
        self.assertEqual([a["text"] for a in msgs["alerts"]], ["usage-monitor 不可达"])

    def test_malformed_section_skipped(self):
        msgs = parse_messages("## 不是时间 — 标题\n正文\n## 2026-08-21 09:00 — 好\nok")
        self.assertEqual([m["title"] for m in msgs["latest"]], ["好"])

    def test_empty_input(self):
        msgs = parse_messages("")
        self.assertEqual(msgs, {"latest": [], "pending": [], "alerts": []})


class BuildMessagesHtmlTest(unittest.TestCase):
    def test_escaping(self):
        msgs = parse_messages("## 2026-08-21 09:00 — <script>\n<evil>")
        html = build_messages_html(msgs)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)


class AppendAlertTest(unittest.TestCase):
    def test_append_and_dedup(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "messages.md"
            self.assertTrue(append_alert(p, "usage-monitor 不可达"))
            self.assertFalse(append_alert(p, "usage-monitor 不可达"))
            self.assertEqual(p.read_text(encoding="utf-8").count("usage-monitor"), 1)


if __name__ == "__main__":
    unittest.main()
