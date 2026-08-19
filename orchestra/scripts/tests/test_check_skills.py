"""check_skills.py contract tests."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import check_skills


class CheckSkillsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.skill = self.root / "demo-skill"
        self.skill.mkdir()
        (self.skill / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
        scripts = self.skill / "scripts"
        scripts.mkdir()
        (scripts / "run.py").write_text("print('ok')\n", encoding="utf-8")

    def spec(self, expected_digest=None, required=True):
        return {
            "id": "demo",
            "source": "external",
            "path": str(self.skill),
            "required": required,
            "used_by": ["test"],
            "entrypoints": ["SKILL.md", "scripts/run.py"],
            "contract_files": ["SKILL.md", "scripts/run.py"],
            "expected_digest": expected_digest,
            "input_contract": "input",
            "output_contract": "output",
        }

    def test_missing_skill(self):
        spec = self.spec()
        spec["path"] = str(self.root / "missing")
        result = check_skills.inspect_skill(spec)
        self.assertEqual(result["status"], "missing")
        self.assertIsNone(result["actual_digest"])

    def test_incomplete_skill_lists_missing_entrypoints(self):
        spec = self.spec()
        spec["entrypoints"].append("scripts/missing.py")
        result = check_skills.inspect_skill(spec)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["missing_entrypoints"], ["scripts/missing.py"])

    def test_unlocked_then_ok_with_expected_digest(self):
        unlocked = check_skills.inspect_skill(self.spec())
        self.assertEqual(unlocked["status"], "unlocked")
        locked = check_skills.inspect_skill(
            self.spec(expected_digest=unlocked["actual_digest"])
        )
        self.assertEqual(locked["status"], "ok")

    def test_changed_contract_is_drifted(self):
        initial = check_skills.inspect_skill(self.spec())
        spec = self.spec(expected_digest=initial["actual_digest"])
        (self.skill / "SKILL.md").write_text("# Changed\n", encoding="utf-8")
        result = check_skills.inspect_skill(spec)
        self.assertEqual(result["status"], "drifted")

    def test_lock_current_updates_manifest_and_strict_passes(self):
        manifest = self.root / "skills.json"
        manifest.write_text(
            json.dumps({"schema_version": 1, "skills": [self.spec()]}),
            encoding="utf-8",
        )
        output = io.StringIO()
        with mock.patch("sys.stdout", output):
            rc = check_skills.main([
                "--manifest", str(manifest), "--lock-current", "--strict",
            ])
        self.assertEqual(rc, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["locks_updated"], 1)
        saved = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertIsNotNone(saved["skills"][0]["expected_digest"])

    def test_strict_fails_for_required_unlocked_skill(self):
        manifest = self.root / "skills.json"
        manifest.write_text(
            json.dumps({"schema_version": 1, "skills": [self.spec()]}),
            encoding="utf-8",
        )
        with mock.patch("sys.stdout", io.StringIO()):
            rc = check_skills.main(["--manifest", str(manifest), "--strict"])
        self.assertEqual(rc, 1)

    def test_optional_missing_skill_does_not_fail_manifest(self):
        spec = self.spec(required=False)
        spec["path"] = str(self.root / "missing")
        report = check_skills.inspect_manifest({
            "schema_version": 1,
            "skills": [spec],
        })
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["skills"][0]["status"], "missing")

    def test_manifest_rejects_unknown_and_missing_fields(self):
        spec = self.spec()
        del spec["output_contract"]
        spec["surprise"] = True
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            check_skills.validate_manifest({
                "schema_version": 1,
                "skills": [spec],
            })

    def test_manifest_rejects_duplicate_ids(self):
        spec = self.spec()
        with self.assertRaisesRegex(ValueError, "duplicate skill id"):
            check_skills.validate_manifest({
                "schema_version": 1,
                "skills": [spec, dict(spec)],
            })

    def test_validate_relative_file_rejects_windows_absolute_probes(self):
        # Windows 漏检探针：/abs（root）、C:foo（drive-relative）、C:/foo（drive）、
        # UNC \\server\share —— 全部必须拒绝（跨平台闭环，H-1）。
        probes = ["/abs", "C:foo", "C:/foo", "\\\\server\\share"]
        for probe in probes:
            with self.subTest(probe=probe):
                with self.assertRaisesRegex(ValueError, "unsafe relative path"):
                    check_skills._validate_relative_file(probe, "test.field")

    def test_manifest_rejects_unsafe_and_uncovered_entrypoints(self):
        spec = self.spec()
        spec["entrypoints"] = ["../escape.py"]
        with self.assertRaisesRegex(ValueError, "unsafe relative path"):
            check_skills.validate_manifest({
                "schema_version": 1,
                "skills": [spec],
            })
        spec = self.spec()
        spec["entrypoints"].append("scripts/other.py")
        with self.assertRaisesRegex(ValueError, "included in contract_files"):
            check_skills.validate_manifest({
                "schema_version": 1,
                "skills": [spec],
            })

    def test_manifest_rejects_malformed_digest_and_non_boolean_required(self):
        spec = self.spec(expected_digest="ABC")
        with self.assertRaisesRegex(ValueError, "lowercase SHA-256"):
            check_skills.validate_manifest({
                "schema_version": 1,
                "skills": [spec],
            })
        spec = self.spec()
        spec["required"] = 1
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            check_skills.validate_manifest({
                "schema_version": 1,
                "skills": [spec],
            })

    def test_cli_reports_invalid_manifest_without_traceback(self):
        manifest = self.root / "skills.json"
        manifest.write_text('{"schema_version": 1, "skills": []}', encoding="utf-8")
        output = io.StringIO()
        err = io.StringIO()
        with mock.patch("sys.stdout", output), mock.patch("sys.stderr", err):
            rc = check_skills.main(["--manifest", str(manifest), "--strict"])
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "invalid")
        self.assertNotIn("Traceback", err.getvalue())

    def test_cli_recursion_error_reports_invalid_without_traceback(self):
        # 深嵌套 manifest 触发 json.loads RecursionError（非 ValueError 子类，M-7）。
        manifest = self.root / "skills.json"
        manifest.write_text("[" * 200000 + "]" * 200000, encoding="utf-8")
        output = io.StringIO()
        err = io.StringIO()
        with mock.patch("sys.stdout", output), mock.patch("sys.stderr", err):
            rc = check_skills.main(["--manifest", str(manifest), "--strict"])
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "invalid")
        self.assertNotIn("Traceback", err.getvalue())

    def test_cli_lock_current_write_failure_reports_invalid_without_traceback(self):
        # --lock-current 写失败（只读 manifest → PermissionError）必须结构化处理（M-8）。
        manifest = self.root / "skills.json"
        manifest.write_text(
            json.dumps({"schema_version": 1, "skills": [self.spec()]}),
            encoding="utf-8",
        )
        manifest.chmod(0o444)
        self.addCleanup(manifest.chmod, 0o644)
        output = io.StringIO()
        err = io.StringIO()
        with mock.patch("sys.stdout", output), mock.patch("sys.stderr", err):
            rc = check_skills.main(["--manifest", str(manifest), "--lock-current"])
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(output.getvalue())["status"], "invalid")
        self.assertNotIn("Traceback", err.getvalue())


if __name__ == "__main__":
    unittest.main()
