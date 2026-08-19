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
        self.assertEqual(spec.mode, "execute")
        self.assertEqual(spec.detail, "standard")
        self.assertEqual(spec.required_outputs, ())
        self.assertEqual(spec.json_outputs, ())
        self.assertIsNone(spec.validation_output)

    def test_default_timeout(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: shell\n" "net: optional\n" "result: r\n" "---\necho hi\n")
        spec = taskfile.parse_taskfile(self.path)
        self.assertEqual(spec.timeout, 3600)
        self.assertEqual(spec.depends_on, ())

    def test_depends_on_parsed(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(
                "# T-20260819-demo\n"
                "executor: shell\n"
                "net: optional\n"
                "result: r\n"
                "depends_on: T-20260819-fetch, T-20260819-rank\n"
                "---\necho hi\n"
            )
        spec = taskfile.parse_taskfile(self.path)
        self.assertEqual(
            spec.depends_on,
            ("T-20260819-fetch", "T-20260819-rank"),
        )

    def test_self_dependency_raises(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(
                "# T-20260819-demo\n"
                "executor: shell\n"
                "net: optional\n"
                "result: r\n"
                "depends_on: T-20260819-demo\n"
                "---\necho hi\n"
            )
        with self.assertRaises(ValueError) as cm:
            taskfile.parse_taskfile(self.path)
        self.assertIn("任务自身", str(cm.exception))

    def test_duplicate_dependency_raises(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(
                "# T-20260819-demo\n"
                "executor: shell\n"
                "net: optional\n"
                "result: r\n"
                "depends_on: T-1, T-1\n"
                "---\necho hi\n"
            )
        with self.assertRaises(ValueError) as cm:
            taskfile.parse_taskfile(self.path)
        self.assertIn("重复任务", str(cm.exception))

    def test_mode_and_detail_parsed(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(
                "# T-20260819-demo\n"
                "executor: dsh\n"
                "net: optional\n"
                "result: r\n"
                "mode: audit\n"
                "detail: deep\n"
                "---\nreview code\n"
            )
        spec = taskfile.parse_taskfile(self.path)
        self.assertEqual(spec.mode, "audit")
        self.assertEqual(spec.detail, "deep")

    def test_invalid_mode_raises(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(
                "# T-20260819-demo\n"
                "executor: dsh\n"
                "net: optional\n"
                "result: r\n"
                "mode: guess\n"
                "---\nx\n"
            )
        with self.assertRaises(ValueError) as cm:
            taskfile.parse_taskfile(self.path)
        self.assertIn("mode 必须为", str(cm.exception))

    def test_invalid_detail_raises(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(
                "# T-20260819-demo\n"
                "executor: dsh\n"
                "net: optional\n"
                "result: r\n"
                "detail: enormous\n"
                "---\nx\n"
            )
        with self.assertRaises(ValueError) as cm:
            taskfile.parse_taskfile(self.path)
        self.assertIn("detail 必须为", str(cm.exception))

    def test_output_contract_parsed(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(
                "# T-20260819-demo\n"
                "executor: dsh\n"
                "net: optional\n"
                "result: r\n"
                "required_outputs: digest.json, digest.txt, validation.json\n"
                "json_outputs: digest.json, validation.json\n"
                "validation_output: validation.json\n"
                "---\nx\n"
            )
        spec = taskfile.parse_taskfile(self.path)
        self.assertEqual(
            spec.required_outputs,
            ("digest.json", "digest.txt", "validation.json"),
        )
        self.assertEqual(
            spec.json_outputs,
            ("digest.json", "validation.json"),
        )
        self.assertEqual(spec.validation_output, "validation.json")

    def test_output_contract_rejects_parent_path(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(
                "# T-20260819-demo\n"
                "executor: dsh\n"
                "net: optional\n"
                "result: r\n"
                "required_outputs: ../secret.json\n"
                "---\nx\n"
            )
        with self.assertRaises(ValueError) as cm:
            taskfile.parse_taskfile(self.path)
        self.assertIn("相对路径", str(cm.exception))

    def test_result_rejects_parent_absolute_and_windows_drive_paths(self):
        for result_path in ("../outside", "/tmp/outside", "C:\\outside"):
            with self.subTest(result_path=result_path):
                with open(self.path, "w", encoding="utf-8") as f:
                    f.write(
                        "# T-20260819-demo\n"
                        "executor: shell\n"
                        "net: optional\n"
                        f"result: {result_path}\n"
                        "---\necho hi\n"
                    )
                with self.assertRaises(ValueError) as cm:
                    taskfile.parse_taskfile(self.path)
                self.assertIn("result 只能包含", str(cm.exception))

    def test_json_output_must_be_required(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(
                "# T-20260819-demo\n"
                "executor: dsh\n"
                "net: optional\n"
                "result: r\n"
                "required_outputs: digest.txt\n"
                "json_outputs: digest.json\n"
                "---\nx\n"
            )
        with self.assertRaises(ValueError) as cm:
            taskfile.parse_taskfile(self.path)
        self.assertIn("必须同时出现在 required_outputs", str(cm.exception))

    def test_validation_output_must_be_json(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(
                "# T-20260819-demo\n"
                "executor: dsh\n"
                "net: optional\n"
                "result: r\n"
                "required_outputs: validation.json\n"
                "validation_output: validation.json\n"
                "---\nx\n"
            )
        with self.assertRaises(ValueError) as cm:
            taskfile.parse_taskfile(self.path)
        self.assertIn("必须同时出现在 json_outputs", str(cm.exception))

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

    def test_model_field_optional_default_none(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: shell\n" "net: optional\n" "result: r\n" "---\necho hi\n")
        self.assertIsNone(taskfile.parse_taskfile(self.path).model)

    def test_model_field_passthrough(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: shell\n" "net: optional\n" "result: r\n" "model: flash\n" "---\necho hi\n")
        self.assertEqual(taskfile.parse_taskfile(self.path).model, "flash")
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: shell\n" "net: optional\n" "result: r\n" "model: pro\n" "---\necho hi\n")
        self.assertEqual(taskfile.parse_taskfile(self.path).model, "pro")

    def test_model_field_not_validated(self):
        # 档位校验责任在写卡的 CC；解析层透传不校验
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("# T-1\n" "executor: shell\n" "net: optional\n" "result: r\n" "model: weird-tier\n" "---\necho hi\n")
        self.assertEqual(taskfile.parse_taskfile(self.path).model, "weird-tier")

if __name__ == "__main__":
    unittest.main()
