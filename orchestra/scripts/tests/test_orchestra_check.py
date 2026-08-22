"""orchestra_check.py thin gate tests."""
from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
from unittest import mock

import orchestra_check


class TrackedIgnoredTest(unittest.TestCase):
    def test_filters_results_and_logs_prefixes(self):
        with mock.patch.object(orchestra_check.subprocess, "run") as run:
            run.return_value = mock.Mock(
                returncode=0,
                stdout="orchestra/results/foo\0orchestra/logs/bar\0README.md\0",
            )
            files = orchestra_check.tracked_ignored_files(Path("."))
        self.assertEqual(
            files,
            ["orchestra/results/foo", "orchestra/logs/bar"],
        )


class BuildReportTest(unittest.TestCase):
    def test_ok_false_when_skills_strict_fails(self):
        def fake_run(cmd, cwd=None, **kwargs):
            if "check_skills.py" in " ".join(cmd):
                return mock.Mock(returncode=1, stdout="", stderr="")
            if cmd[:2] == ["git", "rev-parse"]:
                return mock.Mock(returncode=0, stdout="abc123\n", stderr="")
            if cmd[:3] == ["git", "ls-files", "-z"]:
                return mock.Mock(returncode=0, stdout="", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(orchestra_check.subprocess, "run", side_effect=fake_run):
            report = orchestra_check.build_report(python="py")
        self.assertFalse(report["ok"])
        self.assertEqual(report["git_sha"], "abc123")
        self.assertEqual(report["steps"]["check_skills"]["rc"], 1)
        self.assertEqual(report["steps"]["broker_tests"]["rc"], 0)
        self.assertEqual(report["steps"]["tracked_ignored"]["rc"], 0)

    def test_ok_false_when_results_still_tracked(self):
        def fake_run(cmd, cwd=None, **kwargs):
            if cmd[:3] == ["git", "ls-files", "-z"]:
                return mock.Mock(
                    returncode=0,
                    stdout="orchestra/results/x.json\0",
                    stderr="",
                )
            if cmd[:2] == ["git", "rev-parse"]:
                return mock.Mock(returncode=0, stdout="deadbeef\n", stderr="")
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(orchestra_check.subprocess, "run", side_effect=fake_run):
            report = orchestra_check.build_report()
        self.assertFalse(report["ok"])
        self.assertEqual(
            report["steps"]["tracked_ignored"]["files"],
            ["orchestra/results/x.json"],
        )

    def test_main_prints_json(self):
        fake = {"ok": True, "git_sha": "x", "steps": {}}
        buf = io.StringIO()
        with mock.patch.object(orchestra_check, "build_report", return_value=fake):
            with mock.patch("sys.stdout", buf):
                rc = orchestra_check.main([])
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue())["ok"], True)


if __name__ == "__main__":
    unittest.main()
