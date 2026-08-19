"""deploy_broker.sh 文件清单与模板迁移回归。"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "deploy_broker.sh"
# 跨平台：Linux 用 /bin/bash，Windows 开发机用 PATH 中的 bash（Git Bash）
BASH = shutil.which("bash") or "/bin/bash"


class DeployBrokerContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SCRIPT.read_text(encoding="utf-8")

    def test_uploads_new_runtime_modules(self):
        for name in (
            "artifact_validators.py",
            "radar_render.py",
            "radar_notify.py",
            "migration_guard.py",
        ):
            with self.subTest(name=name):
                self.assertIn(name, self.text)

    def test_uploads_staged_templates_and_removes_legacy_template(self):
        self.assertIn('templates/nightly-radar-*.md', self.text)
        self.assertIn("rm -f templates/nightly-radar.md", self.text)

    def test_legacy_task_guard_runs_from_tmp_before_any_live_upload(self):
        temporary_guard_upload = self.text.index(
            'scp -q "$ROOT/broker/migration_guard.py"'
        )
        guard = self.text.index('python3 "$GUARD_REMOTE"')
        runtime_upload = self.text.index(
            'scp -q "$ROOT"/broker/{db.py'
        )
        template_upload = self.text.index(
            'scp -q "$ROOT"/templates/nightly-radar-*.md'
        )
        unit_upload = self.text.index(
            'scp -q "$ROOT"/broker/orchestra-broker.service'
        )
        remove_template = self.text.index("rm -f templates/nightly-radar.md")
        restart = self.text.index("sudo systemctl restart orchestra-broker.service")
        self.assertIn('GUARD_REMOTE="/tmp/orchestra-migration-guard-$$.py"', self.text)
        self.assertLess(temporary_guard_upload, guard)
        self.assertLess(guard, runtime_upload)
        self.assertLess(guard, template_upload)
        self.assertLess(guard, unit_upload)
        self.assertLess(guard, remove_template)
        self.assertLess(guard, restart)
        self.assertIn('--db-path "$REMOTE_ROOT/db/broker.db"', self.text)

    def test_preflight_failure_exits_before_live_files_can_be_overwritten(self):
        preflight_end = self.text.index("\nPREFLIGHT\n") + len("\nPREFLIGHT\n")
        first_live_upload = self.text.index('scp -q "$ROOT"/broker/{db.py')
        self.assertLess(preflight_end, first_live_upload)
        preflight = self.text[:preflight_end]
        self.assertIn("set -euo pipefail", preflight)
        self.assertIn('python3 "$GUARD_REMOTE"', preflight)
        self.assertNotIn(':/home/liuxfs/broker/"', preflight)
        self.assertNotIn("/etc/systemd/system/", preflight)

    def test_broker_stopped_between_preflight_and_live_upload(self):
        # M-6：门禁（PREFLIGHT）通过后、首次覆盖在役文件前必须先停旧 broker，
        # 门禁快照与文件覆盖间的 TOCTOU 窗口归零；末尾 restart 负责拉起。
        preflight_end = self.text.index("\nPREFLIGHT\n") + len("\nPREFLIGHT\n")
        first_live_upload = self.text.index('scp -q "$ROOT"/broker/{db.py')
        stop = self.text.index("sudo systemctl stop orchestra-broker.service")
        restart = self.text.index("sudo systemctl restart orchestra-broker.service")
        self.assertLess(preflight_end, stop)
        self.assertLess(stop, first_live_upload)
        self.assertLess(stop, restart)

    def test_broker_recovery_trap_registered_after_stop(self):
        # M-6 失败兜底：stop 之后中途失败要有 EXIT trap 把 broker 拉回（start），
        # 且 trap 注册必须先于首次在役文件覆盖，保证失败路径也有恢复。
        stop = self.text.index("sudo systemctl stop orchestra-broker.service")
        trap_register = self.text.index("trap recover_broker EXIT")
        start = self.text.index("sudo systemctl start orchestra-broker.service")
        first_live_upload = self.text.index('scp -q "$ROOT"/broker/{db.py')
        self.assertLess(stop, trap_register)
        self.assertLess(stop, start)
        self.assertLess(trap_register, first_live_upload)

    def test_preflight_failure_performs_no_live_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            trace = root / "trace"
            for name, body in {
                "scp": (
                    'printf "scp" >> "$TRACE"\n'
                    'for arg in "$@"; do printf "\\t%s" "$arg" >> "$TRACE"; done\n'
                    'printf "\\n" >> "$TRACE"\n'
                ),
                "ssh": (
                    'printf "ssh\\t%s\\n" "$*" >> "$TRACE"\n'
                    'case "$*" in *GUARD_REMOTE=*bash\\ -s*) exit 2 ;; esac\n'
                ),
            }.items():
                wrapper = bin_dir / name
                wrapper.write_text("#!/bin/sh\n" + body, encoding="utf-8")
                wrapper.chmod(0o755)
            env = os.environ.copy()
            env.update({
                "ORCHESTRA_SSH_HOST": "test-host",
                "PATH": str(bin_dir) + os.pathsep + env["PATH"],
                # as_posix：bash 重定向不转换反斜杠路径，会写进错误文件名
                "TRACE": trace.as_posix(),
            })

            result = subprocess.run(
                [BASH, str(SCRIPT)],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            calls = trace.read_text(encoding="utf-8").splitlines()
            scp_calls = [line for line in calls if line.startswith("scp\t")]
            self.assertEqual(len(scp_calls), 1)
            self.assertIn("migration_guard.py", scp_calls[0])
            self.assertIn(":/tmp/orchestra-migration-guard-", scp_calls[0])
            self.assertNotIn(":/home/liuxfs/broker", "\n".join(calls))
            self.assertNotIn("/etc/systemd/system", "\n".join(calls))


if __name__ == "__main__":
    unittest.main()
