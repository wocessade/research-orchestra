"""taskfile.py 单元测试。"""
import os
import tempfile
import unittest

import taskfile

SAMPLE = """# T-20260819-demo
executor: shell
net: optional
result: T-20260819-demo
timeout: 60
---
echo hello
"""

class TestParseTaskfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "T-20260819-demo.md")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(SAMPLE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_ok(self):
        spec = taskfile.parse_taskfile(self.path)
        self.assertEqual(spec.slug, "T-20260819-demo")
        self.assertEqual(spec.executor, "shell")
        self.assertEqual(spec.net, "optional")
        self.assertEqual(spec.result_dir, "T-20260819-demo")
        self.assertEqual(spec.timeout, 60)
        self.assertEqual(spec.body, "echo hello")

    def test_default_timeout(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: shell\n" "net: optional\n" "result: r\n" "---\necho hi\n")
        self.assertEqual(taskfile.parse_taskfile(self.path).timeout, 3600)

    def test_missing_field_raises(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: shell\n" "---\necho hi\n")
        with self.assertRaises(ValueError) as cm:
            taskfile.parse_taskfile(self.path)
        self.assertIn("缺少字段", str(cm.exception))

    def test_bad_executor_raises(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: codex\n" "net: optional\n" "result: r\n" "---\nx\n")
        with self.assertRaises(ValueError):
            taskfile.parse_taskfile(self.path)

    def test_empty_body_raises(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: shell\n" "net: optional\n" "result: r\n" "---\n")
        with self.assertRaises(ValueError):
            taskfile.parse_taskfile(self.path)

if __name__ == "__main__":
    unittest.main()
