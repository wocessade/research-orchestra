"""inject_daily.sh 四阶段注入测试。"""
import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import taskfile


BROKER_DIR = Path(__file__).resolve().parents[1]
ORCHESTRA_DIR = BROKER_DIR.parent
SCRIPT = BROKER_DIR / "inject_daily.sh"
TEMPLATES = ORCHESTRA_DIR / "templates"


class TestInjectDaily(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tasks = self.root / "tasks"
        self.results = self.root / "results"
        self.results.mkdir()
        self.env = os.environ.copy()
        self.env.update({
            "ORCHESTRA_DATE": "20260820",
            "ORCHESTRA_TASKS_DIR": str(self.tasks),
            "ORCHESTRA_RESULTS_DIR": str(self.results),
            "ORCHESTRA_TEMPLATES_DIR": str(TEMPLATES),
        })

    def run_inject(self, env=None):
        return subprocess.run(
            ["/bin/bash", str(SCRIPT)],
            env=env or self.env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_injects_four_ordered_tasks_with_dependencies(self):
        result = self.run_inject()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("4 new task(s)", result.stdout)

        files = sorted(self.tasks.glob("T-*.md"))
        self.assertEqual(
            [path.name for path in files],
            [
                "T-20260820-nightly-radar-10-fetch.md",
                "T-20260820-nightly-radar-20-rank.md",
                "T-20260820-nightly-radar-30-render.md",
                "T-20260820-nightly-radar-40-notify.md",
            ],
        )

        specs = [taskfile.parse_taskfile(path) for path in files]
        self.assertEqual(specs[0].depends_on, ())
        self.assertEqual(
            specs[1].depends_on,
            ("T-20260820-nightly-radar-10-fetch",),
        )
        self.assertEqual(
            specs[2].depends_on,
            ("T-20260820-nightly-radar-20-rank",),
        )
        self.assertEqual(
            specs[3].depends_on,
            ("T-20260820-nightly-radar-30-render",),
        )
        self.assertEqual(
            [spec.executor for spec in specs],
            ["dsh", "dsh", "shell", "shell"],
        )
        self.assertEqual(
            [(spec.mode, spec.detail) for spec in specs],
            [
                ("execute", "brief"),
                ("audit", "deep"),
                ("execute", "brief"),
                ("brief", "brief"),
            ],
        )
        self.assertEqual(
            [spec.validator for spec in specs],
            ["radar-fetch", "radar-rank", "radar-render", None],
        )
        self.assertEqual(
            specs[0].required_outputs,
            ("papers_all.json", "fetch_summary.json"),
        )
        self.assertEqual(
            specs[1].required_outputs,
            ("scored_papers.json", "ranking_summary.json"),
        )
        self.assertEqual(
            specs[2].required_outputs,
            ("digest.json", "digest.txt", "top5.json", "validation.json"),
        )
        self.assertEqual(specs[2].validation_output, "validation.json")
        self.assertEqual(specs[3].required_outputs, ("notification.json",))
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("{{DATE}}", text)
            self.assertNotIn("{{RESULTS_ROOT}}", text)
            self.assertIn("20260820", text)
        self.assertIn(str(self.results), files[-1].read_text(encoding="utf-8"))

    def test_second_run_is_idempotent_and_missing_stage_is_recreated(self):
        first = self.run_inject()
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_inject()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("0 new task(s)", second.stdout)

        missing = self.tasks / "T-20260820-nightly-radar-30-render.md"
        missing.unlink()
        third = self.run_inject()
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertIn("1 new task(s)", third.stdout)
        self.assertTrue(missing.exists())

    def test_missing_template_fails_without_partial_file(self):
        incomplete_templates = self.root / "incomplete-templates"
        incomplete_templates.mkdir()
        for name in (
            "nightly-radar-fetch.md",
            "nightly-radar-rank.md",
            "nightly-radar-render.md",
        ):
            shutil.copy(TEMPLATES / name, incomplete_templates / name)
        env = dict(self.env, ORCHESTRA_TEMPLATES_DIR=str(incomplete_templates))
        result = self.run_inject(env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing template", result.stderr)
        self.assertEqual(list(self.tasks.glob("T-*.md")), [])
        self.assertEqual(list(self.tasks.glob("*.tmp.*")), [])
        self.assertEqual(list(self.tasks.glob(".radar-inject-*")), [])

    def test_failure_cleans_only_owned_marker(self):
        broken_templates = self.root / "broken-templates"
        shutil.copytree(TEMPLATES, broken_templates)
        (broken_templates / "nightly-radar-rank.md").write_text("", encoding="utf-8")
        env = dict(self.env, ORCHESTRA_TEMPLATES_DIR=str(broken_templates))
        result = self.run_inject(env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.tasks.glob("T-*.md")), [])
        self.assertFalse((self.tasks / ".radar-inject-20260820").exists())
        self.assertEqual(list(self.tasks.glob(".radar-stage-*")), [])

    def test_stale_marker_after_crash_is_reclaimed_and_missing_stages_are_filled(self):
        self.tasks.mkdir()
        marker = self.tasks / ".radar-inject-20260820"
        marker.mkdir()
        existing = self.tasks / "T-20260820-nightly-radar-10-fetch.md"
        existing.write_text(
            (TEMPLATES / "nightly-radar-fetch.md").read_text(encoding="utf-8")
            .replace("{{DATE}}", "20260820")
            .replace("{{RESULTS_ROOT}}", str(self.results)),
            encoding="utf-8",
        )

        result = self.run_inject()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3 new task(s)", result.stdout)
        self.assertEqual(len(list(self.tasks.glob("T-*.md"))), 4)
        self.assertFalse(marker.exists())

    def test_live_reused_pid_with_different_starttime_is_reclaimed(self):
        proc_root = self.root / "proc"
        boot_id = "test-boot-id"
        (proc_root / "sys/kernel/random").mkdir(parents=True)
        (proc_root / "sys/kernel/random/boot_id").write_text(
            boot_id + "\n", encoding="utf-8"
        )
        live_pid = os.getpid()
        (proc_root / str(live_pid)).mkdir()
        stat_fields = ["S"] + ["0"] * 18 + ["222"]
        (proc_root / str(live_pid) / "stat").write_text(
            f"{live_pid} (python ) test worker) " + " ".join(stat_fields) + "\n",
            encoding="utf-8",
        )
        self.tasks.mkdir()
        marker = self.tasks / ".radar-inject-20260820"
        marker.mkdir()
        (marker / "owner").write_text(
            f"{socket.gethostname()}:{boot_id}:{live_pid}:111\n",
            encoding="utf-8",
        )
        env = dict(self.env, ORCHESTRA_PROC_ROOT=str(proc_root))

        result = self.run_inject(env=env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("4 new task(s)", result.stdout)
        self.assertEqual(len(list(self.tasks.glob("T-*.md"))), 4)
        self.assertFalse(marker.exists())

    def test_missing_proc_falls_back_to_live_pid_compatibility(self):
        self.tasks.mkdir()
        marker = self.tasks / ".radar-inject-20260820"
        marker.mkdir()
        (marker / "owner").write_text(
            f"{socket.gethostname()}:unknown:{os.getpid()}:unknown\n",
            encoding="utf-8",
        )
        env = dict(
            self.env,
            ORCHESTRA_PROC_ROOT=str(self.root / "missing-proc"),
        )

        result = self.run_inject(env=env)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already running", result.stderr)
        self.assertEqual(list(self.tasks.glob("T-*.md")), [])
        self.assertTrue(marker.exists())

    def test_same_date_injections_are_mutually_exclusive(self):
        slow_bin = self.root / "bin"
        slow_bin.mkdir()
        real_sed = shutil.which("sed")
        wrapper = slow_bin / "sed"
        wrapper.write_text(
            "#!/bin/sh\nsleep 1\nexec " + real_sed + ' "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        env = dict(self.env, PATH=str(slow_bin) + os.pathsep + self.env["PATH"])
        first = subprocess.Popen(
            ["/bin/bash", str(SCRIPT)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        marker = self.tasks / ".radar-inject-20260820"
        for _ in range(100):
            if (marker / "owner").is_file():
                break
            time.sleep(0.02)
        self.assertTrue((marker / "owner").is_file())

        second = self.run_inject()
        first_stdout, first_stderr = first.communicate(timeout=10)

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already running", second.stderr)
        self.assertEqual(first.returncode, 0, first_stderr)
        self.assertIn("4 new task(s)", first_stdout)
        self.assertEqual(len(list(self.tasks.glob("T-*.md"))), 4)
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
