"""executor.py 单元测试（shell 分支真跑，dsh 分支用 mock，避免依赖真实 dsh）。"""
import json
import os
import tempfile
import unittest
from unittest import mock

import executor
import taskfile

def make_spec(
    body,
    executor="shell",
    timeout=30,
    mode="execute",
    detail="standard",
    required_outputs=(),
    json_outputs=(),
    validation_output=None,
):
    return taskfile.TaskSpec(
        slug="T-20260819-test", executor=executor, net="optional",
        result_dir="T-20260819-test", timeout=timeout, body=body,
        mode=mode, detail=detail,
        required_outputs=required_outputs,
        json_outputs=json_outputs,
        validation_output=validation_output,
    )

class TestShellExecutor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tasks = os.path.join(self.tmp.name, "tasks")
        self.results = os.path.join(self.tmp.name, "results")
        os.makedirs(self.tasks)
        os.makedirs(self.results)

    def tearDown(self):
        self.tmp.cleanup()

    def test_shell_ok(self):
        spec = make_spec("echo broker-ok")
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "done")
        self.assertIsNone(error)
        outdir = os.path.join(self.results, "T-20260819-test", "attempt-1")
        with open(os.path.join(outdir, "stdout.log"), encoding="utf-8") as f:
            self.assertIn("broker-ok", f.read())
        with open(os.path.join(outdir, "state.json"), encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["executor"], "shell")
        self.assertEqual(state["mode"], "execute")
        self.assertEqual(state["detail"], "standard")

    def test_shell_fail_exit_code(self):
        spec = make_spec("exit 3")
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("exit code 3", error)

    def test_shell_timeout(self):
        # Windows cmd 无原生 sleep，POSIX shell 直接用 sleep。
        body = "ping -n 31 127.0.0.1 >nul" if os.name == "nt" else "sleep 2"
        spec = make_spec(body, timeout=1)
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("timeout", error)

    def test_unknown_command_fails(self):
        # cmd/sh 对未知命令返回非零退出码（错误文本跨平台各异，只断言失败与错误信息）
        spec = make_spec("nonexistent-cmd-xyz")
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIsNotNone(error)

    def test_exit_zero_with_missing_output_fails_validation(self):
        spec = make_spec("echo process-ok", required_outputs=("result.json",))
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("artifact validation failed", error)
        self.assertIn("missing required output", error)
        outdir = os.path.join(self.results, "T-20260819-test", "attempt-1")
        with open(os.path.join(outdir, "state.json"), encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state["output_validation"]["status"], "failed")

    def test_validate_outputs_accepts_valid_json_and_passed_marker(self):
        outdir = executor.Path(self.tmp.name) / "validation-ok"
        outdir.mkdir()
        (outdir / "result.json").write_text('{"items": [1]}', encoding="utf-8")
        (outdir / "validation.json").write_text(
            '{"status": "passed"}',
            encoding="utf-8",
        )
        spec = make_spec(
            "unused",
            required_outputs=("result.json", "validation.json"),
            json_outputs=("result.json", "validation.json"),
            validation_output="validation.json",
        )
        self.assertEqual(executor.validate_task_outputs(spec, outdir), [])

    def test_validate_outputs_rejects_invalid_json(self):
        outdir = executor.Path(self.tmp.name) / "invalid-json"
        outdir.mkdir()
        (outdir / "result.json").write_text("{broken", encoding="utf-8")
        spec = make_spec(
            "unused",
            required_outputs=("result.json",),
            json_outputs=("result.json",),
        )
        errors = executor.validate_task_outputs(spec, outdir)
        self.assertEqual(len(errors), 1)
        self.assertIn("invalid JSON output", errors[0])

    def test_validate_outputs_rejects_failed_marker(self):
        outdir = executor.Path(self.tmp.name) / "validation-failed"
        outdir.mkdir()
        (outdir / "validation.json").write_text(
            '{"status": "failed"}',
            encoding="utf-8",
        )
        spec = make_spec(
            "unused",
            required_outputs=("validation.json",),
            json_outputs=("validation.json",),
            validation_output="validation.json",
        )
        errors = executor.validate_task_outputs(spec, outdir)
        self.assertEqual(
            errors,
            ["validation status is not passed: validation.json"],
        )

    def test_validate_outputs_rejects_symlink_escape(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unsupported")
        outdir = executor.Path(self.tmp.name) / "symlink-output"
        outdir.mkdir()
        outside = executor.Path(self.tmp.name) / "outside.json"
        outside.write_text('{"ok": true}', encoding="utf-8")
        try:
            os.symlink(outside, outdir / "result.json")
        except OSError as exc:
            self.skipTest(f"cannot create symlink: {exc}")
        spec = make_spec(
            "unused",
            required_outputs=("result.json",),
            json_outputs=("result.json",),
        )
        errors = executor.validate_task_outputs(spec, outdir)
        self.assertIn("path escapes workspace", errors[0])

    def test_result_dir_symlink_escape_is_rejected(self):
        outside = executor.Path(self.tmp.name) / "outside-results"
        outside.mkdir()
        link = executor.Path(self.results) / "T-20260819-test"
        try:
            os.symlink(outside, link)
        except OSError as exc:
            self.skipTest(f"cannot create symlink: {exc}")
        spec = make_spec("echo should-not-run")
        with self.assertRaises(ValueError) as cm:
            executor.run_task(spec, self.tasks, self.results)
        self.assertIn("path escapes workspace", str(cm.exception))

    def test_attempt_increments(self):
        spec = make_spec("echo ok")
        executor.run_task(spec, self.tasks, self.results)
        executor.run_task(spec, self.tasks, self.results)
        base = os.path.join(self.results, "T-20260819-test")
        self.assertTrue(os.path.isdir(os.path.join(base, "attempt-1")))
        self.assertTrue(os.path.isdir(os.path.join(base, "attempt-2")))

    def test_attempt_allocator_skips_existing_directories_atomically(self):
        base = executor.Path(self.results) / "atomic"
        (base / "attempt-1").mkdir(parents=True)
        attempt, outdir = executor._allocate_attempt_dir(base)
        self.assertEqual(attempt, 2)
        self.assertTrue(outdir.is_dir())

    @mock.patch("subprocess.Popen")
    def test_shell_cwd_is_attempt_dir(self, mock_popen):
        proc = mock_popen.return_value
        proc.communicate.return_value = ("ok", "")
        proc.returncode = 0
        spec = make_spec("echo ok")
        status, _ = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "done")
        outdir = str(
            (executor.Path(self.results) / "T-20260819-test" / "attempt-1").resolve()
        )
        self.assertEqual(mock_popen.call_args.kwargs["cwd"], outdir)  # 任务工作区=attempt 目录

class TestDshExecutor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tasks = os.path.join(self.tmp.name, "tasks")
        self.results = os.path.join(self.tmp.name, "results")
        os.makedirs(self.tasks)
        os.makedirs(self.results)

    def tearDown(self):
        self.tmp.cleanup()

    @mock.patch("subprocess.Popen")
    def test_dsh_prompt_contains_output_dir(self, mock_popen):
        proc = mock_popen.return_value
        proc.communicate.return_value = ("done", "")
        proc.returncode = 0
        spec = make_spec("分析数据", executor="dsh")
        status, _ = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "done")
        args, kwargs = mock_popen.call_args
        # 与 executor 内 pathlib 归一化一致：分段 join，避免嵌入正斜杠不匹配
        outdir = str(
            (executor.Path(self.results) / "T-20260819-test" / "attempt-1").resolve()
        )
        self.assertIn("dsh", args[0][0])
        self.assertIn(outdir, args[0][3])  # cmd = [dsh, --profile, <profile>, prompt] → prompt 在索引 3
        self.assertEqual(kwargs["cwd"], outdir)  # dsh 沙箱 workspace-write：cwd 即输出目录

    def test_build_dsh_prompt_applies_mode_and_detail(self):
        spec = make_spec(
            "检查这段代码",
            executor="dsh",
            mode="audit",
            detail="deep",
        )
        outdir = executor.Path("/tmp/result")
        prompt = executor.build_dsh_prompt(spec, outdir)
        self.assertIn("任务模式: audit", prompt)
        self.assertIn("反证", prompt)
        self.assertIn("验证方法", prompt)
        self.assertIn("输出详略: deep", prompt)
        self.assertIn("只有新增信息才能增加篇幅", prompt)
        self.assertIn("任务正文:\n检查这段代码", prompt)

    def test_brief_mode_asks_to_remove_repetition(self):
        spec = make_spec(
            "汇报状态",
            executor="dsh",
            mode="brief",
            detail="brief",
        )
        prompt = executor.build_dsh_prompt(spec, executor.Path("/tmp/result"))
        self.assertIn("同义重复", prompt)
        self.assertIn("紧凑输出", prompt)

class TestCheckNet(unittest.TestCase):
    @mock.patch("socket.create_connection")
    def test_net_ok(self, mock_conn):
        self.assertTrue(executor.check_net())

    @mock.patch("socket.create_connection", side_effect=OSError("down"))
    def test_net_down(self, mock_conn):
        self.assertFalse(executor.check_net())

if __name__ == "__main__":
    unittest.main()
