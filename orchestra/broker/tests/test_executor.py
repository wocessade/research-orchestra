"""executor.py 单元测试（shell 分支真跑，dsh 分支用 mock，避免依赖真实 dsh）。"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import executor
import taskfile

def make_spec(body, executor="shell", timeout=30, model=None):
    return taskfile.TaskSpec(
        slug="T-20260819-test", executor=executor, net="optional",
        result_dir="T-20260819-test", timeout=timeout, body=body, model=model,
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
        base = os.path.join(self.results, "T-20260819-test")
        self.assertTrue(os.path.isdir(os.path.join(base, "attempt-1")))
        self.assertTrue(os.path.isdir(os.path.join(base, "attempt-2")))

    @mock.patch("subprocess.Popen")
    def test_shell_cwd_is_attempt_dir(self, mock_popen):
        proc = mock_popen.return_value
        proc.communicate.return_value = ("ok", "")
        proc.returncode = 0
        spec = make_spec("echo ok")
        status, _ = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "done")
        outdir = os.path.join(self.results, "T-20260819-test", "attempt-1")
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
        outdir = os.path.join(self.results, "T-20260819-test", "attempt-1")
        self.assertIn("dsh", args[0][0])
        self.assertIn(outdir, args[0][3])  # cmd = [dsh, --profile, <profile>, prompt] → prompt 在索引 3
        self.assertEqual(kwargs["cwd"], outdir)  # dsh 沙箱 workspace-write：cwd 即输出目录

    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("subprocess.Popen")
    def test_dsh_model_appends_patch(self, popen, _exists):
        proc = popen.return_value
        proc.communicate.return_value = ("", "")
        proc.returncode = 0
        spec = make_spec("分析数据", executor="dsh", model="flash")
        status, _ = executor.run_task(spec, self.tasks, self.results)
        argv = popen.call_args.args[0]
        self.assertIn("--patch", argv)
        self.assertEqual(argv[argv.index("--patch") + 1], "/mnt/broker/dsh-patches/flash.yml")
        self.assertEqual(status, "done")

    @mock.patch("os.path.exists", return_value=False)
    @mock.patch("subprocess.Popen")
    def test_dsh_model_missing_patch_fails(self, popen, _exists):
        spec = make_spec("分析数据", executor="dsh", model="pro")
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("model patch not found", error)
        popen.assert_not_called()
        # state.json 仍落盘
        self.assertTrue(any(Path(self.results).rglob("state.json")))

    @mock.patch("os.path.exists", return_value=True)
    @mock.patch("subprocess.Popen")
    def test_dsh_no_model_no_patch(self, popen, _exists):
        proc = popen.return_value
        proc.communicate.return_value = ("", "")
        proc.returncode = 0
        executor.run_task(make_spec("分析数据", executor="dsh", model=None), self.tasks, self.results)
        self.assertNotIn("--patch", popen.call_args.args[0])

class PathValidationTest(unittest.TestCase):
    """result_dir 路径逃逸防护（finding #1）：越界早退，不建目录不写 state.json。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tasks = os.path.join(self.tmp.name, "tasks")
        self.results = os.path.join(self.tmp.name, "results")
        os.makedirs(self.tasks)
        os.makedirs(self.results)

    def tearDown(self):
        self.tmp.cleanup()

    def _spec(self, result_dir, body="echo ok"):
        return taskfile.TaskSpec(
            slug="T-pathval", executor="shell", net="optional",
            result_dir=result_dir, timeout=30, body=body,
        )

    def test_relative_escape_rejected_no_dir_created(self):
        spec = self._spec("../../evil")
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("escapes", error)
        # 漏洞本体断言：逃逸目标目录不得创建、results 内外均不得出现 attempt 目录与 state.json
        escape_target = (Path(self.results) / "../../evil").resolve()
        self.assertFalse(escape_target.exists())
        self.assertEqual(list(Path(self.tmp.name).rglob("state.json")), [])
        self.assertEqual(list(Path(self.tmp.name).rglob("attempt-*")), [])

    @mock.patch("subprocess.Popen")
    def test_legal_relative_subdir_executes_in_results_root(self, mock_popen):
        proc = mock_popen.return_value
        proc.communicate.return_value = ("ok", "")
        proc.returncode = 0
        spec = self._spec("sub/dir")
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "done")
        self.assertIsNone(error)
        # outdir 落在 results_root 内（sub/dir/attempt-1），cwd 为工作区
        outdir = os.path.join(self.results, "sub", "dir", "attempt-1")
        self.assertTrue(os.path.isdir(outdir))
        self.assertEqual(mock_popen.call_args.kwargs["cwd"], outdir)
        with open(os.path.join(outdir, "state.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["status"], "done")

    def test_absolute_result_dir_rejected(self):
        outside = os.path.join(self.tmp.name, "outside")
        spec = self._spec(outside)
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("escapes", error)
        self.assertFalse(os.path.exists(outside))
        self.assertEqual(list(Path(self.tmp.name).rglob("state.json")), [])


class WindowsTreeKillTest(unittest.TestCase):
    """Finding #3：Windows 超时分支用 taskkill /T 杀整棵进程树（proc.kill() 留孤儿孙进程）。"""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tasks = os.path.join(self.tmp.name, "tasks")
        self.results = os.path.join(self.tmp.name, "results")
        os.makedirs(self.tasks)
        os.makedirs(self.results)

    def tearDown(self):
        self.tmp.cleanup()

    @unittest.skipUnless(os.name == "nt", "Windows 分支：taskkill 整树杀")
    @mock.patch("subprocess.run")
    @mock.patch("subprocess.Popen")
    def test_timeout_kills_process_tree(self, mock_popen, mock_run):
        # communicate 首次抛 TimeoutExpired → 触发超时分支；第二次正常返回（kill 后收尾）
        proc = mock_popen.return_value
        proc.pid = 4242
        proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="dsh", timeout=60),
            ("", ""),
        ]
        spec = make_spec("timeout-now", timeout=60)
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("timeout", error)
        # taskkill 整树杀：argv 精确匹配（PID 取 proc 实例属性比对）
        mock_run.assert_called_once()
        self.assertEqual(
            mock_run.call_args.args[0],
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
        )
        self.assertEqual(mock_run.call_args.kwargs["timeout"], 10)
        self.assertIs(mock_run.call_args.kwargs.get("capture_output"), True)

    @unittest.skipUnless(os.name == "nt", "Windows 分支：taskkill 整树杀")
    @mock.patch("subprocess.run")
    @mock.patch("subprocess.Popen")
    def test_timeout_stdout_stderr_still_written(self, mock_popen, mock_run):
        # 回归：超时后 communicate 第二次返回的 stdout/stderr 仍落盘
        proc = mock_popen.return_value
        proc.pid = 4242
        proc.communicate.side_effect = [
            subprocess.TimeoutExpired(cmd="dsh", timeout=60),
            ("partial-out", "partial-err"),
        ]
        spec = make_spec("timeout-now", timeout=60)
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "failed")
        self.assertIn("timeout", error)
        outdir = os.path.join(self.results, "T-20260819-test", "attempt-1")
        with open(os.path.join(outdir, "stdout.log"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "partial-out")
        with open(os.path.join(outdir, "stderr.log"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "partial-err")

class TestCheckNet(unittest.TestCase):
    @mock.patch("socket.create_connection")
    def test_net_ok(self, mock_conn):
        self.assertTrue(executor.check_net())

    @mock.patch("socket.create_connection", side_effect=OSError("down"))
    def test_net_down(self, mock_conn):
        self.assertFalse(executor.check_net())

class AtomicAttemptTest(unittest.TestCase):
    """attempt 目录原子分配（TOCTOU 修复）：mkdir 不带 exist_ok，FileExistsError 即重试。

    竞态模拟用 autospec + 可调用 side_effect（前 N 次抛 FileExistsError、之后委托真
    mkdir）：探针实测 side_effect 列表直接放 real_mkdir 会因 mock 实例绑定丢失 self，
    故用计数器委托。Path.mkdir(parents=True) 内部会递归调父目录 mkdir（同样经过
    mock），因此断言以落点 attempt-N 与任务状态为准，不断言精确调用次数。
    """
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tasks = os.path.join(self.tmp.name, "tasks")
        self.results = os.path.join(self.tmp.name, "results")
        os.makedirs(self.tasks)
        os.makedirs(self.results)

    def tearDown(self):
        self.tmp.cleanup()

    def _flaky_mkdir(self, fail_first_n):
        """构造 flaky Path.mkdir：前 fail_first_n 次抛 FileExistsError，之后走真 mkdir。"""
        real_mkdir = Path.mkdir
        def flaky(self, *args, **kwargs):
            if flaky.n < fail_first_n:
                flaky.n += 1
                raise FileExistsError
            return real_mkdir(self, *args, **kwargs)
        flaky.n = 0
        return flaky

    def test_precreated_dirs_skip_to_next(self):
        # 回归：预创建 attempt-1/attempt-2 → 新任务落 attempt-3（既有语义不破坏）
        base = os.path.join(self.results, "T-20260819-test")
        os.makedirs(os.path.join(base, "attempt-1"))
        os.makedirs(os.path.join(base, "attempt-2"))
        spec = make_spec("echo skip-ok")
        status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "done")
        self.assertIsNone(error)
        outdir = os.path.join(base, "attempt-3")
        self.assertTrue(os.path.isdir(outdir))
        with open(os.path.join(outdir, "state.json"), encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state["attempt"], 3)
        self.assertEqual(state["status"], "done")

    def test_race_retries_on_file_exists(self):
        # 竞态：attempt-1 的 mkdir 抛 FileExistsError（他方先建）→ 重试落 attempt-2 且任务 done
        flaky = self._flaky_mkdir(fail_first_n=1)
        with mock.patch.object(Path, "mkdir", autospec=True, side_effect=flaky):
            spec = make_spec("echo race-ok")
            status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "done")
        self.assertIsNone(error)
        base = os.path.join(self.results, "T-20260819-test")
        self.assertTrue(os.path.isdir(os.path.join(base, "attempt-2")))
        with open(os.path.join(base, "attempt-2", "state.json"), encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state["attempt"], 2)
        self.assertEqual(state["status"], "done")

    def test_continuous_races_retry_to_third(self):
        # 连续竞态：前两次 mkdir 均抛 FileExistsError → 第三次成功落 attempt-3
        flaky = self._flaky_mkdir(fail_first_n=2)
        with mock.patch.object(Path, "mkdir", autospec=True, side_effect=flaky):
            spec = make_spec("echo race3-ok")
            status, error = executor.run_task(spec, self.tasks, self.results)
        self.assertEqual(status, "done")
        self.assertIsNone(error)
        base = os.path.join(self.results, "T-20260819-test")
        self.assertTrue(os.path.isdir(os.path.join(base, "attempt-3")))
        with open(os.path.join(base, "attempt-3", "state.json"), encoding="utf-8") as f:
            state = json.load(f)
        self.assertEqual(state["attempt"], 3)
        self.assertEqual(state["status"], "done")

if __name__ == "__main__":
    unittest.main()
