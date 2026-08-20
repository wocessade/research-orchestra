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

    def test_malformed_section_after_valid_is_skipped_without_absorbing_text(self):
        text = """## 2026-08-21 09:00 — 好
有效正文
## 不是时间 — 坏
不应并入有效正文
"""
        msgs = parse_messages(text)
        self.assertEqual([m["title"] for m in msgs["latest"]], ["好"])
        self.assertEqual(msgs["latest"][0]["text"], "有效正文")

    def test_multiple_pending_and_alerts_preserve_line_order(self):
        text = """## 2026-08-21 09:00 — 批量事件
- 待决：先决定 A
- 告警：先告警 B
- 待决：再决定 C
- 告警：再告警 D
"""
        msgs = parse_messages(text)
        self.assertEqual([p["text"] for p in msgs["pending"]], ["先决定 A", "再决定 C"])
        self.assertEqual([a["text"] for a in msgs["alerts"]], ["先告警 B", "再告警 D"])

    def test_empty_input(self):
        msgs = parse_messages("")
        self.assertEqual(msgs, {"latest": [], "pending": [], "alerts": []})


class BuildMessagesHtmlTest(unittest.TestCase):
    def test_escaping(self):
        msgs = parse_messages("## 2026-08-21 09:00 — <script>\n<evil>")
        html = build_messages_html(msgs)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("<meta charset='utf-8'>", html)
        self.assertIn("white-space:pre-wrap", html)


class AppendAlertTest(unittest.TestCase):
    def test_append_and_dedup(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "messages.md"
            self.assertTrue(append_alert(p, "usage-monitor 不可达"))
            self.assertFalse(append_alert(p, "usage-monitor 不可达"))
            self.assertEqual(p.read_text(encoding="utf-8").count("usage-monitor"), 1)
    def test_body_prose_does_not_trigger_dedup(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "messages.md"
            p.write_text(
                "## 2026-08-21 09:00 — 说明\n"
                "正文提到 - 告警：usage-monitor 不可达 但不是告警行\n",
                encoding="utf-8",
            )
            self.assertTrue(append_alert(p, "usage-monitor 不可达"))

    def test_append_not_suppressed_by_older_year(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "messages.md"
            p.write_text(
                "## 2025-08-20 21:00 — 自动告警\n"
                "- 告警：usage-monitor 不可达\n\n"
                "## 2026-08-20 22:00 — 正常留言\n"
                "系统运行正常\n",
                encoding="utf-8",
            )
            self.assertTrue(append_alert(p, "usage-monitor 不可达"))
            content = p.read_text(encoding="utf-8")
            self.assertEqual(content.count("- 告警：usage-monitor 不可达"), 2)
            self.assertIn("— 自动告警\n- 告警：usage-monitor 不可达\n", content)

    def test_final_raw_section_controls_dedup(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "messages.md"
            p.write_text(
                "## 2025-08-20 21:00 — 自动告警\n"
                "- 告警：usage-monitor 不可达\n\n"
                "## 2026-08-20 21:00 — 自动告警\n"
                "- 告警：usage-monitor 不可达\n\n"
                "## 2026-08-20 22:00 — 正常留言\n"
                "系统运行正常\n",
                encoding="utf-8",
            )
            self.assertTrue(append_alert(p, "usage-monitor 不可达"))

    def test_append_prose_in_final_section_not_matching(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "messages.md"
            p.write_text(
                "## 2026-08-21 09:00 — 说明\n"
                "正文提到 usage-monitor 不可达，但不是告警行\n",
                encoding="utf-8",
            )
            self.assertTrue(append_alert(p, "usage-monitor 不可达"))

            p.write_text(
                "## 2026-08-21 09:00 — 自动告警\n"
                "- 告警：usage-monitor 不可达\n",
                encoding="utf-8",
            )
            self.assertFalse(append_alert(p, "usage-monitor 不可达"))

    def test_existing_alert_line_triggers_dedup(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "messages.md"
            p.write_text(
                "## 2026-08-21 09:00 — 自动告警\n"
                "- 告警：usage-monitor 不可达\n",
                encoding="utf-8",
            )
            self.assertFalse(append_alert(p, "usage-monitor 不可达"))


if __name__ == "__main__":
    unittest.main()
