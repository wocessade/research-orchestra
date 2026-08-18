"""executor.py 单元测试（shell 分支真跑，dsh 分支用 mock，避免依赖真实 dsh）。"""
import json
import os
import tempfile
import unittest
from unittest import mock

import executor
import taskfile

def make_spec(body, executor="shell", timeout=30):
    return taskfile.TaskSpec(
        slug="T-20260819-test", executor=executor, net="optional",
        result_dir="results/T-20260819-test", timeout=timeout, body=body,
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
        outdir = os.path.join(self.results, "results/T-20260819-test", "attempt-1")
        self.assertIn("broker-ok", open(os.path.join(outdir, "stdout.log"), encoding="utf-8").read())
        state = json.load(open(os.path.join(outdir, "state.json"), encoding="utf-8"))
        self.assertEqual(state["status"], "done")
        self.assertEqual(state["executor"], "shell")

    def test_shell_fail_exit_code(self):
        spec = make_spec("exit 3")
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("exit code 3", error)

    def test_shell_timeout(self):
        # cmd 原生 sleep 写法：ping -n 31 等待约 30s（测试约定在 Git Bash/Windows 下运行）
        spec = make_spec("ping -n 31 127.0.0.1 >nul", timeout=1)
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("timeout", error)

    def test_unknown_command_fails(self):
        # cmd/sh 对未知命令返回非零退出码（错误文本跨平台各异，只断言失败与错误信息）
        spec = make_spec("nonexistent-cmd-xyz")
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIsNotNone(error)

    def test_attempt_increments(self):
        spec = make_spec("echo ok")
        executor.run_task(spec, self.tasks, self.results)
        executor.run_task(spec, self.tasks, self.results)
        base = os.path.join(self.results, "results/T-20260819-test")
        self.assertTrue(os.path.isdir(os.path.join(base, "attempt-1")))
        self.assertTrue(os.path.isdir(os.path.join(base, "attempt-2")))

class TestDshExecutor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tasks = os.path.join(self.tmp.name, "tasks")
        self.results = os.path.join(self.tmp.name, "results")
        os.makedirs(self.tasks)
        os.makedirs(self.results)

    def tearDown(self):
        self.tmp.cleanup()

    @mock.patch("subprocess.run")
    def test_dsh_prompt_contains_output_dir(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout="done", stderr="")
        spec = make_spec("分析数据", executor="dsh")
        status, _ = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "done")
        args, kwargs = mock_run.call_args
        outdir = os.path.join(self.results, "results/T-20260819-test", "attempt-1")
        self.assertIn("dsh", args[0][0])
        self.assertIn(outdir, args[0][3])  # cmd = [dsh, --profile, <profile>, prompt] → prompt 在索引 3
        self.assertEqual(kwargs["cwd"], self.tasks)

class TestCheckNet(unittest.TestCase):
    @mock.patch("socket.create_connection")
    def test_net_ok(self, mock_conn):
        self.assertTrue(executor.check_net())

    @mock.patch("socket.create_connection", side_effect=OSError("down"))
    def test_net_down(self, mock_conn):
        self.assertFalse(executor.check_net())

if __name__ == "__main__":
    unittest.main()
