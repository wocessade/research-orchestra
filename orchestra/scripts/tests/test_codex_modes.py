"""Tests for codex_modes.py — three Codex agent-mode protocols.

Stdlib unittest only. The real codex subprocess is never touched: every mode
function accepts an injectable `run` (default codex_exec.run_codex) and
dual_implement additionally accepts `run_tests`, so all tests use fakes
returning preset dicts / (returncode, stdout) pairs — zero real codex calls.

Run from orchestra/scripts:
    python -m unittest discover -s tests -v
"""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import codex_modes


def make_run(result=None, text="", status="ok", error_type=None):
    """Factory for an injectable fake run_codex that records calls.

    run(prompt, model=None, timeout=None, cwd=None) -> preset result dict.
    """
    calls = []

    def run(prompt, model=None, timeout=None, cwd=None):
        calls.append({"prompt": prompt, "model": model, "timeout": timeout, "cwd": cwd})
        if result is not None:
            return result
        return {
            "status": status, "text": text, "session_id": None, "model": model,
            "elapsed_s": 0.0, "events": 0, "error_type": error_type, "raw_lines": [],
        }

    run.calls = calls
    return run


def make_run_tests(cc=(0, "cc tests ok"), codex=(0, "codex tests ok")):
    """Factory for an injectable fake run_tests that records calls.

    The CC run is the first call (PYTHONPATH points at impl_dir), the codex
    run the second (PYTHONPATH contains codex_impl).
    """
    calls = []

    def run_tests(command, cwd, env=None):
        calls.append({"command": list(command), "cwd": cwd, "env": dict(env or {})})
        pythonpath = (env or {}).get("PYTHONPATH", "")
        if "codex_impl" in pythonpath:
            return codex
        return cc

    run_tests.calls = calls
    return run_tests


# ---------------------------------------------------------------------------
# build_prompt — pure template assembly
# ---------------------------------------------------------------------------

class BuildPromptTest(unittest.TestCase):
    def test_mutual_review_template(self):
        prompt = codex_modes.build_prompt("mutual-review", {
            "diff": "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-foo\n+bar\n",
            "context": "",
        })
        self.assertIn("JSON array", prompt)
        self.assertIn("no markdown", prompt)
        self.assertIn("severity", prompt)
        self.assertIn("--- a/x.py", prompt)
        self.assertNotIn("ADDITIONAL CONTEXT", prompt)

    def test_mutual_review_context_included_when_given(self):
        prompt = codex_modes.build_prompt("mutual-review", {
            "diff": "d", "context": "module x.py is hot-path",
        })
        self.assertIn("ADDITIONAL CONTEXT", prompt)
        self.assertIn("module x.py is hot-path", prompt)

    def test_dual_implement_template(self):
        prompt = codex_modes.build_prompt("dual-implement", {
            "spec": "Implement a counter.", "impl_dir": "C:/work/impl",
            "tests_dir": "C:/work/tests",
        })
        self.assertIn("codex_impl", prompt)
        self.assertIn("C:/work/impl", prompt)
        self.assertIn("C:/work/tests", prompt)
        self.assertIn("Implement a counter.", prompt)
        self.assertIn("JSON", prompt)
        self.assertIn("no markdown", prompt)

    def test_claim_check_template_with_list(self):
        prompt = codex_modes.build_prompt("claim-check", {"claims": ["alpha", "beta"]})
        self.assertIn('"alpha"', prompt)
        self.assertIn('"beta"', prompt)
        self.assertIn("claim_index", prompt)
        self.assertIn("true", prompt)
        self.assertIn("false", prompt)
        self.assertIn("unsure", prompt)

    def test_claim_check_template_with_json_string(self):
        prompt = codex_modes.build_prompt("claim-check", {"claims": '["gamma"]'})
        self.assertIn('"gamma"', prompt)

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            codex_modes.build_prompt("no-such-mode", {})


# ---------------------------------------------------------------------------
# mutual_review
# ---------------------------------------------------------------------------

FINDINGS_JSON = json.dumps([
    {"severity": "high", "file": "a/x.py", "line": 12, "issue": "N+1 query",
     "suggestion": "batch the query"},
    {"severity": "low", "file": "a/x.py", "line": 3, "issue": "style",
     "suggestion": "reformat"},
])


class MutualReviewTest(unittest.TestCase):
    def test_ok_parses_findings(self):
        run = make_run(text=FINDINGS_JSON)
        result = codex_modes.mutual_review("--- a\n+++ b\n", run=run)
        self.assertEqual(result["mode"], "mutual-review")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["findings"]), 2)
        self.assertEqual(result["findings"][0]["severity"], "high")
        self.assertEqual(result["findings"][0]["line"], 12)
        self.assertEqual(result["findings"][1]["severity"], "low")
        self.assertEqual(result["raw"], FINDINGS_JSON)

    def test_prompt_contains_diff_and_context(self):
        run = make_run(text=FINDINGS_JSON)
        codex_modes.mutual_review("THE-DIFF", context="THE-CONTEXT", run=run)
        prompt = run.calls[0]["prompt"]
        self.assertIn("THE-DIFF", prompt)
        self.assertIn("THE-CONTEXT", prompt)

    def test_default_timeout_300_and_model_forwarded(self):
        run = make_run(text=FINDINGS_JSON)
        codex_modes.mutual_review("d", run=run)
        self.assertEqual(run.calls[0]["timeout"], 300)
        self.assertIsNone(run.calls[0]["model"])
        run2 = make_run(text=FINDINGS_JSON)
        codex_modes.mutual_review("d", run=run2, model="gpt-5-codex", timeout=90)
        self.assertEqual(run2.calls[0]["timeout"], 90)
        self.assertEqual(run2.calls[0]["model"], "gpt-5-codex")

    def test_markdown_fence_stripped(self):
        run = make_run(text="```json\n" + FINDINGS_JSON + "\n```")
        result = codex_modes.mutual_review("d", run=run)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["findings"]), 2)

    def test_prose_wrapped_array_salvaged(self):
        run = make_run(text="Here are my findings:\n" + FINDINGS_JSON + "\nHope that helps.")
        result = codex_modes.mutual_review("d", run=run)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["findings"]), 2)

    def test_severity_and_line_validation(self):
        run = make_run(text=json.dumps([
            {"severity": "BLOCKER", "file": 7, "line": "oops", "issue": 3, "suggestion": None},
            {"severity": "med", "line": "42", "file": "x.py", "issue": "i", "suggestion": "s"},
            {"severity": "high", "line": True, "file": "x.py", "issue": "i", "suggestion": "s"},
        ]))
        result = codex_modes.mutual_review("d", run=run)
        findings = result["findings"]
        self.assertEqual(findings[0]["severity"], "low")   # invalid severity -> low
        self.assertEqual(findings[0]["file"], "")          # non-str -> ""
        self.assertIsNone(findings[0]["line"])             # non-numeric -> null
        self.assertEqual(findings[0]["issue"], "")         # non-str -> ""
        self.assertEqual(findings[1]["line"], 42)          # numeric string accepted
        self.assertIsNone(findings[2]["line"])             # bool is not a line

    def test_non_dict_items_skipped(self):
        run = make_run(text='[{"severity": "high", "file": "x.py", "line": 1, '
                            '"issue": "i", "suggestion": "s"}, "garbage", 42]')
        result = codex_modes.mutual_review("d", run=run)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["findings"]), 1)

    def test_empty_array_is_ok(self):
        run = make_run(text="[]")
        result = codex_modes.mutual_review("d", run=run)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["findings"], [])

    def test_parse_failed_degrades(self):
        run = make_run(text="I refuse to review this diff.")
        result = codex_modes.mutual_review("d", run=run)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "parse_failed")
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["raw"], "I refuse to review this diff.")

    def test_empty_text_degrades(self):
        run = make_run(text="")
        result = codex_modes.mutual_review("d", run=run)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "parse_failed")

    def test_run_failure_degrades(self):
        run = make_run(text="partial", status="error", error_type="rate_limit")
        result = codex_modes.mutual_review("d", run=run)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "rate_limit")
        self.assertEqual(result["findings"], [])

    def test_run_timeout_degrades(self):
        run = make_run(text="", status="timeout")
        result = codex_modes.mutual_review("d", run=run)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "timeout")


# ---------------------------------------------------------------------------
# dual_implement
# ---------------------------------------------------------------------------

class DualImplementTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.impl_dir = self.root / "impl"
        self.tests_dir = self.root / "tests"
        self.impl_dir.mkdir()
        self.tests_dir.mkdir()
        self.codex_impl = self.impl_dir / "codex_impl"

    def _write_codex_impl(self, content):
        self.codex_impl.mkdir()
        (self.codex_impl / "impl.py").write_text(content, encoding="utf-8")

    def test_ok_basic_no_divergences(self):
        (self.impl_dir / "impl.py").write_text("X = 1\n", encoding="utf-8")
        self._write_codex_impl("X = 1\n")
        (self.tests_dir / "test_impl.py").write_text("def test_x(): pass", encoding="utf-8")
        run = make_run(text="[]")
        t = make_run_tests()
        result = codex_modes.dual_implement(
            "spec", str(self.impl_dir), str(self.tests_dir), run=run, run_tests=t
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["divergences"], [])
        self.assertEqual(result["cc_tests"]["returncode"], 0)
        self.assertEqual(result["codex_tests"]["returncode"], 0)
        self.assertEqual(result["cc_tests"]["stdout_tail"], "cc tests ok")
        self.assertEqual(result["codex_tests"]["stdout_tail"], "codex tests ok")
        self.assertEqual(result["impl_files"], [str(self.codex_impl / "impl.py")])
        self.assertEqual(result["raw"], "[]")
        # two test runs with the same command
        self.assertEqual(len(t.calls), 2)
        self.assertEqual(t.calls[0]["command"], t.calls[1]["command"])
        self.assertIn("pytest", t.calls[0]["command"])
        # CC run points PYTHONPATH at impl_dir, codex run at codex_impl
        self.assertNotIn("codex_impl", t.calls[0]["env"]["PYTHONPATH"])
        self.assertIn("codex_impl", t.calls[1]["env"]["PYTHONPATH"])

    def test_default_timeout_600(self):
        (self.impl_dir / "impl.py").write_text("X = 1\n", encoding="utf-8")
        self._write_codex_impl("X = 1\n")
        run = make_run(text="[]")
        t = make_run_tests()
        codex_modes.dual_implement(
            "s", str(self.impl_dir), str(self.tests_dir), run=run, run_tests=t
        )
        self.assertEqual(run.calls[0]["timeout"], 600)

    def test_prompt_contains_spec_and_dirs(self):
        (self.impl_dir / "impl.py").write_text("X = 1\n", encoding="utf-8")
        self._write_codex_impl("X = 1\n")
        run = make_run(text="[]")
        codex_modes.dual_implement(
            "THE-SPEC", str(self.impl_dir), str(self.tests_dir),
            run=run, run_tests=make_run_tests(),
        )
        prompt = run.calls[0]["prompt"]
        self.assertIn("THE-SPEC", prompt)
        self.assertIn(str(self.impl_dir), prompt)
        self.assertIn(str(self.codex_impl), prompt)
        self.assertIn(str(self.tests_dir), prompt)

    def test_behavior_divergence_when_test_outcome_differs(self):
        (self.impl_dir / "impl.py").write_text("X = 1\n", encoding="utf-8")
        self._write_codex_impl("X = 1\n")
        (self.tests_dir / "test_impl.py").write_text("def test_x(): pass", encoding="utf-8")
        run = make_run(text="[]")
        t = make_run_tests(cc=(0, "ok"), codex=(1, "FAILED tests/test_impl.py::test_x"))
        result = codex_modes.dual_implement(
            "s", str(self.impl_dir), str(self.tests_dir), run=run, run_tests=t
        )
        kinds = [d["kind"] for d in result["divergences"]]
        self.assertIn("behavior", kinds)
        bd = [d for d in result["divergences"] if d["kind"] == "behavior"][0]
        self.assertEqual(bd["file"], "tests/test_impl.py")
        self.assertIn("codex", bd["detail"])

    def test_interface_divergence_on_same_file_diff(self):
        (self.impl_dir / "impl.py").write_text("X = 1\n", encoding="utf-8")
        self._write_codex_impl("X = 2\n")
        run = make_run(text="[]")
        t = make_run_tests()
        result = codex_modes.dual_implement(
            "s", str(self.impl_dir), str(self.tests_dir), run=run, run_tests=t
        )
        ids = [d for d in result["divergences"] if d["kind"] == "interface"]
        self.assertEqual(len(ids), 1)
        self.assertEqual(ids[0]["file"], "impl.py")
        self.assertIn("-X = 1", ids[0]["detail"])
        self.assertIn("+X = 2", ids[0]["detail"])

    def test_style_divergence_on_file_set_difference(self):
        (self.impl_dir / "impl.py").write_text("X = 1\n", encoding="utf-8")
        (self.impl_dir / "cc_extra.py").write_text("Y = 2\n", encoding="utf-8")
        self.codex_impl.mkdir()
        (self.codex_impl / "impl.py").write_text("X = 1\n", encoding="utf-8")
        (self.codex_impl / "codex_extra.py").write_text("Z = 3\n", encoding="utf-8")
        run = make_run(text="[]")
        t = make_run_tests()
        result = codex_modes.dual_implement(
            "s", str(self.impl_dir), str(self.tests_dir), run=run, run_tests=t
        )
        st = [d for d in result["divergences"] if d["kind"] == "style"]
        self.assertEqual(len(st), 2)
        self.assertEqual({d["file"] for d in st}, {"cc_extra.py", "codex_extra.py"})
        # codex_impl subtree is not part of the CC side
        self.assertNotIn("codex_impl/impl.py", [d["file"] for d in result["divergences"]])

    def test_all_three_kinds_combined(self):
        (self.impl_dir / "impl.py").write_text("X = 1\n", encoding="utf-8")
        self.codex_impl.mkdir()
        (self.codex_impl / "impl.py").write_text("X = 2\n", encoding="utf-8")
        (self.codex_impl / "extra.py").write_text("Y = 3\n", encoding="utf-8")
        run = make_run(text="[]")
        t = make_run_tests(cc=(1, "FAILED tests/test_impl.py::test_x"), codex=(0, "ok"))
        result = codex_modes.dual_implement(
            "s", str(self.impl_dir), str(self.tests_dir), run=run, run_tests=t
        )
        self.assertEqual({d["kind"] for d in result["divergences"]},
                         {"behavior", "interface", "style"})

    def test_unittest_detection_when_no_pytest_marker(self):
        (self.impl_dir / "impl.py").write_text("X = 1\n", encoding="utf-8")
        self._write_codex_impl("X = 1\n")
        (self.tests_dir / "helper.py").write_text("def helper(): return 1", encoding="utf-8")
        run = make_run(text="[]")
        t = make_run_tests()
        codex_modes.dual_implement(
            "s", str(self.impl_dir), str(self.tests_dir), run=run, run_tests=t
        )
        self.assertIn("unittest", t.calls[0]["command"])

    def test_codex_impl_missing_is_error(self):
        (self.impl_dir / "impl.py").write_text("X = 1\n", encoding="utf-8")
        run = make_run(text="[]")
        t = make_run_tests()
        result = codex_modes.dual_implement(
            "s", str(self.impl_dir), str(self.tests_dir), run=run, run_tests=t
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "codex_impl_empty")
        self.assertIsNone(result["cc_tests"])
        self.assertEqual(t.calls, [])  # no test run attempted

    def test_codex_impl_empty_is_error(self):
        self.codex_impl.mkdir()
        run = make_run(text="[]")
        result = codex_modes.dual_implement(
            "s", str(self.impl_dir), str(self.tests_dir), run=run
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "codex_impl_empty")

    def test_run_failure_is_error(self):
        run = make_run(text="", status="error", error_type="unknown")
        result = codex_modes.dual_implement(
            "s", str(self.impl_dir), str(self.tests_dir), run=run
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "unknown")


# ---------------------------------------------------------------------------
# claim_check
# ---------------------------------------------------------------------------

class ClaimCheckTest(unittest.TestCase):
    def test_ok_with_cc_verdicts(self):
        run = make_run(text=json.dumps([
            {"claim_index": 0, "verdict": "true", "reason": "r0"},
            {"claim_index": 1, "verdict": "true", "reason": "r1"},
            {"claim_index": 2, "verdict": "unsure", "reason": "r2"},
        ]))
        result = codex_modes.claim_check(
            ["a", "b", "c"], cc_verdicts=["true", "false", "unsure"], run=run
        )
        self.assertEqual(result["mode"], "claim-check")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["disagree"], [1])
        self.assertTrue(result["cc_verdicts_provided"])
        entries = result["claims"]
        self.assertEqual(entries[0]["claim"], "a")
        self.assertEqual(entries[0]["cc_verdict"], "true")
        self.assertEqual(entries[0]["codex_verdict"], "true")
        self.assertEqual(entries[0]["codex_reason"], "r0")
        self.assertTrue(entries[0]["agree"])
        self.assertFalse(entries[1]["agree"])
        self.assertTrue(entries[2]["agree"])

    def test_no_cc_verdicts_all_null_and_disagree_empty(self):
        run = make_run(text=json.dumps([{"claim_index": 0, "verdict": "true", "reason": "r"}]))
        result = codex_modes.claim_check(["a"], run=run)
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["cc_verdicts_provided"])
        self.assertEqual(result["disagree"], [])
        entry = result["claims"][0]
        self.assertIsNone(entry["cc_verdict"])
        self.assertIsNone(entry["agree"])

    def test_claims_as_json_string(self):
        run = make_run(text="[]")
        result = codex_modes.claim_check('["x", "y"]', run=run)
        self.assertEqual(result["status"], "ok")
        self.assertEqual([e["claim"] for e in result["claims"]], ["x", "y"])

    def test_missing_codex_verdicts_leave_nulls(self):
        run = make_run(text=json.dumps([{"claim_index": 0, "verdict": "true", "reason": "r"}]))
        result = codex_modes.claim_check(["a", "b"], cc_verdicts=["true", "false"], run=run)
        entry = result["claims"][1]
        self.assertIsNone(entry["codex_verdict"])
        self.assertIsNone(entry["agree"])
        self.assertEqual(result["disagree"], [])

    def test_verdict_case_insensitive_and_bool(self):
        run = make_run(text=json.dumps([
            {"claim_index": 0, "verdict": "TRUE", "reason": "r"},
            {"claim_index": 1, "verdict": "false", "reason": "r"},
        ]))
        result = codex_modes.claim_check(["a", "b"], cc_verdicts=[True, False], run=run)
        self.assertEqual(result["claims"][0]["codex_verdict"], "true")
        self.assertEqual(result["claims"][0]["cc_verdict"], "true")
        self.assertEqual(result["claims"][1]["codex_verdict"], "false")
        self.assertTrue(result["claims"][0]["agree"])
        self.assertTrue(result["claims"][1]["agree"])

    def test_invalid_verdict_ignored(self):
        run = make_run(text=json.dumps([{"claim_index": 0, "verdict": "maybe", "reason": "r"}]))
        result = codex_modes.claim_check(["a"], cc_verdicts=["true"], run=run)
        self.assertIsNone(result["claims"][0]["codex_verdict"])
        self.assertIsNone(result["claims"][0]["agree"])
        self.assertEqual(result["disagree"], [])

    def test_cc_verdicts_shorter_than_claims_padded(self):
        run = make_run(text="[]")
        result = codex_modes.claim_check(["a", "b"], cc_verdicts=["true"], run=run)
        self.assertEqual(result["claims"][0]["cc_verdict"], "true")
        self.assertIsNone(result["claims"][1]["cc_verdict"])

    def test_out_of_range_claim_index_ignored(self):
        run = make_run(text=json.dumps([{"claim_index": 9, "verdict": "true", "reason": "r"}]))
        result = codex_modes.claim_check(["a"], run=run)
        self.assertEqual(result["status"], "ok")
        self.assertIsNone(result["claims"][0]["codex_verdict"])

    def test_default_timeout_300(self):
        run = make_run(text="[]")
        codex_modes.claim_check(["a"], run=run)
        self.assertEqual(run.calls[0]["timeout"], 300)

    def test_prompt_contains_claims(self):
        run = make_run(text="[]")
        codex_modes.claim_check(["alpha"], run=run)
        self.assertIn("alpha", run.calls[0]["prompt"])

    def test_parse_failed_degrades(self):
        run = make_run(text="claims are all true.")
        result = codex_modes.claim_check(["a"], cc_verdicts=["true"], run=run)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "parse_failed")
        self.assertEqual(result["disagree"], [])
        self.assertIsNone(result["claims"][0]["codex_verdict"])

    def test_run_failure_degrades(self):
        run = make_run(text="", status="error", error_type="authentication")
        result = codex_modes.claim_check(["a"], run=run)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"], "authentication")


# ---------------------------------------------------------------------------
# main — CLI layer
# ---------------------------------------------------------------------------

class MainCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _capture(self, argv):
        out = io.StringIO()
        with mock.patch("sys.stdout", out):
            rc = codex_modes.main(argv)
        return rc, out.getvalue()

    @mock.patch("codex_modes.mutual_review")
    def test_mutual_review_subcommand(self, mr):
        mr.return_value = {"mode": "mutual-review", "status": "ok", "findings": [], "raw": ""}
        diff_file = self.root / "diff.patch"
        diff_file.write_text("--- a\n+++ b\n", encoding="utf-8")
        out_file = self.root / "review.json"
        rc, out = self._capture(["mutual-review", str(diff_file), "--out", str(out_file)])
        self.assertEqual(rc, 0)
        self.assertIn(str(out_file), out)
        args, kwargs = mr.call_args
        self.assertEqual(args[0], "--- a\n+++ b\n")
        self.assertEqual(kwargs["timeout"], 300)
        self.assertIsNone(kwargs["model"])
        saved = json.loads(out_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "ok")

    @mock.patch("codex_modes.mutual_review")
    def test_mutual_review_with_context_and_model(self, mr):
        mr.return_value = {"mode": "mutual-review", "status": "ok", "findings": [], "raw": ""}
        diff_file = self.root / "diff.patch"
        diff_file.write_text("d", encoding="utf-8")
        ctx_file = self.root / "ctx.txt"
        ctx_file.write_text("context text", encoding="utf-8")
        out_file = self.root / "review.json"
        rc, _ = self._capture(["mutual-review", str(diff_file), "--context", str(ctx_file),
                               "--model", "gpt-5-codex", "--out", str(out_file)])
        self.assertEqual(rc, 0)
        _, kwargs = mr.call_args
        self.assertEqual(kwargs["context"], "context text")
        self.assertEqual(kwargs["model"], "gpt-5-codex")

    @mock.patch("codex_modes.mutual_review")
    def test_mutual_review_error_exit_code_1(self, mr):
        mr.return_value = {"mode": "mutual-review", "status": "error", "findings": [],
                           "raw": "", "error": "parse_failed"}
        diff_file = self.root / "diff.patch"
        diff_file.write_text("d", encoding="utf-8")
        out_file = self.root / "review.json"
        rc, _ = self._capture(["mutual-review", str(diff_file), "--out", str(out_file)])
        self.assertEqual(rc, 1)
        saved = json.loads(out_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "error")

    @mock.patch("codex_modes.dual_implement")
    def test_dual_implement_subcommand(self, di):
        di.return_value = {"mode": "dual-implement", "status": "ok", "cc_tests": {},
                           "codex_tests": {}, "divergences": [], "impl_files": [], "raw": ""}
        spec_file = self.root / "spec.md"
        spec_file.write_text("the spec", encoding="utf-8")
        out_file = self.root / "dual.json"
        impl_dir = self.root / "impl"
        tests_dir = self.root / "tests"
        rc, out = self._capture(["dual-implement", str(spec_file), "--impl-dir", str(impl_dir),
                                 "--tests-dir", str(tests_dir), "--out", str(out_file)])
        self.assertEqual(rc, 0)
        self.assertIn(str(out_file), out)
        args, kwargs = di.call_args
        self.assertEqual(args[0], "the spec")
        self.assertEqual(args[1], str(impl_dir))
        self.assertEqual(args[2], str(tests_dir))
        self.assertEqual(kwargs["timeout"], 600)

    @mock.patch("codex_modes.claim_check")
    def test_claim_check_subcommand_with_cc_verdicts(self, cc):
        cc.return_value = {"mode": "claim-check", "status": "ok", "claims": [],
                           "disagree": [], "raw": ""}
        claims_file = self.root / "claims.json"
        claims_file.write_text('["a", "b"]', encoding="utf-8")
        verdicts_file = self.root / "verdicts.json"
        verdicts_file.write_text('["true", "false"]', encoding="utf-8")
        out_file = self.root / "claims.json"
        rc, _ = self._capture(["claim-check", str(claims_file), "--cc-verdicts",
                               str(verdicts_file), "--out", str(out_file)])
        self.assertEqual(rc, 0)
        args, kwargs = cc.call_args
        self.assertEqual(args[0], ["a", "b"])
        self.assertEqual(kwargs["cc_verdicts"], ["true", "false"])
        self.assertEqual(kwargs["timeout"], 300)

    @mock.patch("codex_modes.claim_check")
    def test_claim_check_error_exit_code_1(self, cc):
        cc.return_value = {"mode": "claim-check", "status": "error", "claims": [],
                           "disagree": [], "raw": "", "error": "parse_failed"}
        claims_file = self.root / "claims.json"
        claims_file.write_text('["a"]', encoding="utf-8")
        out_file = self.root / "claims.json"
        rc, _ = self._capture(["claim-check", str(claims_file), "--out", str(out_file)])
        self.assertEqual(rc, 1)

    def test_parser_defaults(self):
        p = codex_modes.build_parser()
        mr = p.parse_args(["mutual-review", "diff.patch"])
        self.assertEqual(mr.timeout, 300)
        self.assertEqual(mr.out, "review.json")
        self.assertIsNone(mr.model)
        self.assertIsNone(mr.context)
        di = p.parse_args(["dual-implement", "spec.md", "--impl-dir", "a", "--tests-dir", "b"])
        self.assertEqual(di.timeout, 600)
        self.assertEqual(di.out, "dual.json")
        cc = p.parse_args(["claim-check", "claims.json"])
        self.assertEqual(cc.timeout, 300)
        self.assertEqual(cc.out, "claims.json")
        self.assertIsNone(cc.cc_verdicts)


if __name__ == "__main__":
    unittest.main()
