"""Tests for codex_exec.py — codex exec --json wrapper with error classification.

Stdlib unittest only. codex_exec.py is stdlib-only; the real `codex exec`
subprocess is replaced by an injectable fake runner (signature
runner(argv, input_bytes, timeout, cwd) -> (returncode, stdout, stderr)),
which may also raise subprocess.TimeoutExpired / FileNotFoundError.

Fixture streams are calibrated against the real smoke capture
D:\\Temp\\codex-smoke-events.jsonl (codex-cli 0.148.0, 2026-08-19):
9 NDJSON lines containing WS reconnect noise events and one
item.completed/agent_message. Key real-world structure facts:
  * agent_message text lives at item.completed.item.text
  * there is NO session_id field anywhere in the stream; the only id is
    thread.started.thread_id (parser must fall back to it)
  * transport noise arrives as {"type":"error","message":"Reconnecting..."}
    and as item.completed with item.type="error" (WebSocket->HTTPS fallback)
"""
import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import codex_exec

# ---------------------------------------------------------------------------
# Real smoke stream, verbatim from D:\Temp\codex-smoke-events.jsonl (9 lines)
# ---------------------------------------------------------------------------

THREAD_ID = "01a01932-dcee-7bd3-9356-dbcdd9c0ce13"

REAL_STREAM = [
    '{"type":"thread.started","thread_id":"01a01932-dcee-7bd3-9356-dbcdd9c0ce13"}',
    '{"type":"turn.started"}',
    '{"type":"error","message":"Reconnecting... 2/5 (request timed out)"}',
    '{"type":"error","message":"Reconnecting... 3/5 (request timed out)"}',
    '{"type":"error","message":"Reconnecting... 4/5 (request timed out)"}',
    '{"type":"error","message":"Reconnecting... 5/5 (request timed out)"}',
    '{"type":"item.completed","item":{"id":"item_0","type":"error","message":"Falling back from WebSockets to HTTPS transport. request timed out"}}',
    '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"codex-smoke-ok"}}',
    '{"type":"turn.completed","usage":{"input_tokens":18204,"cached_input_tokens":1408,"cache_write_input_tokens":0,"output_tokens":122,"reasoning_output_tokens":111}}',
]

REAL_STREAM_TEXT = "\n".join(REAL_STREAM) + "\n"


def make_runner(git_rc=0, codex_rc=0, codex_stdout="", codex_stderr="", exc=None):
    """Factory for an injectable fake subprocess runner that records calls.

    git probes (argv[0] == "git") return git_rc; the codex invocation
    returns codex_rc/codex_stdout/codex_stderr or raises exc.
    """
    calls = []

    def runner(argv, input_bytes, timeout, cwd):
        calls.append((list(argv), input_bytes, timeout, cwd))
        if argv[0] == "git":
            return (git_rc, "", "")
        if exc is not None:
            raise exc
        return (codex_rc, codex_stdout, codex_stderr)

    runner.calls = calls
    return runner


# ---------------------------------------------------------------------------
# parse_events — pure function
# ---------------------------------------------------------------------------

class ParseEventsTest(unittest.TestCase):
    def test_real_smoke_stream(self):
        """Calibration: the 9-line real capture parses to the smoke text."""
        r = codex_exec.parse_events(REAL_STREAM)
        self.assertEqual(r["text"], "codex-smoke-ok")
        # No session_id field exists in the real stream; fall back to thread_id
        self.assertEqual(r["session_id"], THREAD_ID)
        self.assertIsNone(r["model"])
        self.assertIsNone(r["error_type"])
        self.assertEqual(r["events"], 9)

    def test_websocket_fallback_noise_is_not_network_error(self):
        """'Reconnecting...' / 'Falling back from WebSockets to HTTPS'
        are transport noise, NOT a network failure classification."""
        r = codex_exec.parse_events(REAL_STREAM)
        self.assertIsNone(r["error_type"])

    def test_session_id_from_item_completed_wins(self):
        lines = [
            '{"type":"thread.started","thread_id":"t1"}',
            '{"type":"item.completed","session_id":"sid-9","item":{"id":"i1","type":"agent_message","text":"hi"}}',
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["session_id"], "sid-9")

    def test_session_id_inside_item_wins(self):
        lines = [
            '{"type":"thread.started","thread_id":"t1"}',
            '{"type":"item.completed","item":{"id":"i1","session_id":"sid-in-item","type":"agent_message","text":"hi"}}',
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["session_id"], "sid-in-item")

    def test_authentication_error_event(self):
        lines = [
            '{"type":"error","message":"not logged in, please run codex login"}',
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["error_type"], "authentication")
        self.assertEqual(r["text"], "")
        self.assertEqual(r["events"], 1)

    def test_authentication_error_item(self):
        lines = [
            '{"type":"item.completed","item":{"id":"i0","type":"error","message":"401 Unauthorized: authentication required"}}',
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["error_type"], "authentication")

    def test_rate_limit_error(self):
        lines = [
            '{"type":"error","message":"Rate limit exceeded for model: 429 too many requests"}',
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["error_type"], "rate_limit")

    def test_network_error(self):
        lines = [
            '{"type":"error","message":"network error: failed to connect to api.openai.com"}',
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["error_type"], "network")

    def test_trust_error(self):
        lines = [
            '{"type":"item.completed","item":{"id":"i0","type":"error","message":"Not inside a trusted directory"}}',
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["error_type"], "trust")

    def test_sandbox_error(self):
        lines = [
            '{"type":"error","message":"sandbox policy: command not permitted"}',
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["error_type"], "sandbox")

    def test_empty_stream(self):
        r = codex_exec.parse_events([])
        self.assertEqual(r["text"], "")
        self.assertIsNone(r["session_id"])
        self.assertEqual(r["error_type"], "unknown")
        self.assertEqual(r["events"], 0)

    def test_noise_only_stream_marks_unknown(self):
        """No item.completed and only transport noise -> error marker."""
        lines = [
            '{"type":"error","message":"Reconnecting... 2/5 (request timed out)"}',
            '{"type":"turn.started"}',
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["text"], "")
        self.assertEqual(r["error_type"], "unknown")
        self.assertEqual(r["events"], 2)

    def test_non_json_lines_skipped(self):
        lines = [
            "NOT JSON {{",
            '{"type":"thread.started","thread_id":"t1"}',
            "",
            "\x00garbage\n",
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["events"], 1)
        self.assertEqual(r["session_id"], "t1")

    def test_multiple_agent_messages_joined_with_newline(self):
        lines = [
            '{"type":"item.completed","item":{"id":"i1","type":"agent_message","text":"first"}}',
            '{"type":"item.completed","item":{"id":"i2","type":"agent_message","text":"second"}}',
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["text"], "first\nsecond")

    def test_model_extracted_from_event(self):
        lines = [
            '{"type":"turn.started","model":"gpt-5-codex"}',
            '{"type":"item.completed","item":{"id":"i1","type":"agent_message","text":"ok"}}',
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["model"], "gpt-5-codex")

    def test_unknown_event_types_tolerated(self):
        """Unknown event types (e.g. WS transport events) never raise."""
        lines = [
            '{"type":"something.weird","foo":1}',
            '{"type":"item.completed","item":{"id":"i1","type":"agent_message","text":"fine"}}',
        ]
        r = codex_exec.parse_events(lines)
        self.assertEqual(r["text"], "fine")
        self.assertIsNone(r["error_type"])
        self.assertEqual(r["events"], 2)


# ---------------------------------------------------------------------------
# run_codex — subprocess orchestration
# ---------------------------------------------------------------------------

class RunCodexTest(unittest.TestCase):
    def test_success_with_real_stream(self):
        runner = make_runner(codex_stdout=REAL_STREAM_TEXT)
        r = codex_exec.run_codex(
            "prompt here", None, timeout=30, cwd="C:/work", runner=runner
        )
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["text"], "codex-smoke-ok")
        self.assertEqual(r["session_id"], THREAD_ID)
        self.assertIsNone(r["error_type"])
        self.assertEqual(r["events"], 9)
        self.assertGreaterEqual(r["elapsed_s"], 0.0)

    def test_prompt_goes_via_stdin_never_argv(self):
        runner = make_runner(codex_stdout=REAL_STREAM_TEXT)
        prompt = "SECRET-PROMPT-CONTENT-xyz"
        codex_exec.run_codex(prompt, None, timeout=30, cwd=None, runner=runner)
        codex_call = [c for c in runner.calls if c[0][0] != "git"]
        self.assertEqual(len(codex_call), 1)
        argv, input_bytes, _, _ = codex_call[0]
        self.assertEqual(input_bytes, prompt.encode("utf-8"))
        for token in argv:
            self.assertNotIn(prompt, token)

    @mock.patch("codex_exec.resolve_codex", return_value="codex")
    def test_argv_shape_and_model_flag(self, _resolve):
        runner = make_runner(codex_stdout=REAL_STREAM_TEXT)
        codex_exec.run_codex(
            "p", "gpt-5-codex", timeout=30, cwd=None, runner=runner
        )
        argv = [c for c in runner.calls if c[0][0] != "git"][0][0]
        self.assertEqual(argv[0], "codex")
        self.assertEqual(argv[1], "exec")
        self.assertIn("--json", argv)
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "gpt-5-codex")

    @mock.patch(
        "codex_exec.resolve_codex",
        side_effect=FileNotFoundError(2, "codex not found on PATH", "codex"),
    )
    def test_not_installed_when_resolve_fails(self, _resolve):
        runner = make_runner(codex_stdout=REAL_STREAM_TEXT)
        r = codex_exec.run_codex("p", None, 5, cwd=None, runner=runner)
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["error_type"], "not_installed")
        # No codex invocation ever reached the runner.
        self.assertEqual(runner.calls, [])

    def test_resolve_codex_found(self):
        self.assertTrue(codex_exec.resolve_codex())

    def test_git_repo_cwd_no_extra_flag(self):
        runner = make_runner(git_rc=0, codex_stdout=REAL_STREAM_TEXT)
        codex_exec.run_codex("p", None, 30, cwd="C:/work", runner=runner)
        argv = [c for c in runner.calls if c[0][0] != "git"][0][0]
        self.assertNotIn("--skip-git-repo-check", argv)

    def test_non_git_cwd_appends_skip_flag(self):
        runner = make_runner(git_rc=128, codex_stdout=REAL_STREAM_TEXT)
        codex_exec.run_codex("p", None, 30, cwd="C:/work", runner=runner)
        argv = [c for c in runner.calls if c[0][0] != "git"][0][0]
        self.assertIn("--skip-git-repo-check", argv)

    def test_skip_git_check_forces_flag_even_in_repo(self):
        runner = make_runner(git_rc=0, codex_stdout=REAL_STREAM_TEXT)
        codex_exec.run_codex(
            "p", None, 30, cwd="C:/work", skip_git_check=True, runner=runner
        )
        argv = [c for c in runner.calls if c[0][0] != "git"][0][0]
        self.assertIn("--skip-git-repo-check", argv)

    def test_git_probe_uses_dash_c_and_runner(self):
        runner = make_runner(git_rc=0, codex_stdout=REAL_STREAM_TEXT)
        codex_exec.run_codex("p", None, 30, cwd="C:/work", runner=runner)
        git_call = [c for c in runner.calls if c[0][0] == "git"][0]
        self.assertEqual(git_call[0], ["git", "-C", "C:/work", "rev-parse", "--git-dir"])

    def test_timeout_returns_timeout_status(self):
        runner = make_runner(exc=subprocess.TimeoutExpired(cmd=["codex"], timeout=5))
        r = codex_exec.run_codex("p", None, 5, cwd=None, runner=runner)
        self.assertEqual(r["status"], "timeout")
        self.assertIsNone(r["error_type"])
        self.assertEqual(r["text"], "")

    def test_default_runner_timeout_does_not_hang(self):
        """Real Popen path: a sleeping child is killed on timeout and the
        runner raises promptly (regression: subprocess.run's internal
        post-kill drain can hang forever on Windows .cmd trees)."""
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            codex_exec._default_runner(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                b"",
                2,
                None,
            )
        self.assertLess(time.monotonic() - started, 30)

    def test_not_installed_returns_error(self):
        runner = make_runner(exc=FileNotFoundError(2, "no such file", "codex"))
        r = codex_exec.run_codex("p", None, 5, cwd=None, runner=runner)
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["error_type"], "not_installed")

    def test_auth_failure_in_stderr(self):
        runner = make_runner(
            codex_rc=1, codex_stderr="Error: not logged in, please run codex login"
        )
        r = codex_exec.run_codex("p", None, 5, cwd=None, runner=runner)
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["error_type"], "authentication")

    def test_auth_failure_in_event_stream(self):
        runner = make_runner(
            codex_rc=0,
            codex_stdout='{"type":"error","message":"401 authentication failed"}\n',
        )
        r = codex_exec.run_codex("p", None, 5, cwd=None, runner=runner)
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["error_type"], "authentication")

    def test_unknown_failure_classified_unknown(self):
        runner = make_runner(codex_rc=1, codex_stderr="boom: something blew up")
        r = codex_exec.run_codex("p", None, 5, cwd=None, runner=runner)
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["error_type"], "unknown")

    def test_empty_stdout_rc0_is_error_unknown(self):
        runner = make_runner(codex_rc=0, codex_stdout="")
        r = codex_exec.run_codex("p", None, 5, cwd=None, runner=runner)
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["error_type"], "unknown")

    def test_model_falls_back_to_requested_model(self):
        """Real stream has no model field; the requested model is reported."""
        runner = make_runner(codex_stdout=REAL_STREAM_TEXT)
        r = codex_exec.run_codex(
            "p", "gpt-5-codex", 5, cwd=None, runner=runner
        )
        self.assertEqual(r["model"], "gpt-5-codex")

    def test_result_has_raw_lines_for_events_jsonl(self):
        runner = make_runner(codex_stdout=REAL_STREAM_TEXT)
        r = codex_exec.run_codex("p", None, 5, cwd=None, runner=runner)
        self.assertEqual(r["raw_lines"], REAL_STREAM)


# ---------------------------------------------------------------------------
# main — CLI layer
# ---------------------------------------------------------------------------

class MainCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _ok_result(self, **overrides):
        r = {
            "status": "ok",
            "text": "codex-smoke-ok",
            "session_id": THREAD_ID,
            "model": None,
            "elapsed_s": 3.2,
            "events": 9,
            "error_type": None,
            "raw_lines": list(REAL_STREAM),
        }
        r.update(overrides)
        return r

    def _capture(self, argv, stdin_text=None):
        out = io.StringIO()
        with mock.patch("sys.stdout", out), mock.patch(
            "sys.stdin", io.StringIO(stdin_text or "")
        ):
            rc = codex_exec.main(argv)
        return rc, out.getvalue()

    @mock.patch("codex_exec.run_codex")
    def test_run_stdin_dash_ok(self, run):
        run.return_value = self._ok_result()
        json_out = self.root / "result.json"
        rc, out = self._capture(["run", "-", "--json-out", str(json_out)], "hi there")
        self.assertEqual(rc, 0)
        run.assert_called_once()
        args, kwargs = run.call_args
        self.assertEqual(args[0], "hi there")
        result = json.loads(out)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["text"], "codex-smoke-ok")
        saved = json.loads(json_out.read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "ok")

    @mock.patch("codex_exec.run_codex")
    def test_run_prompt_from_file(self, run):
        run.return_value = self._ok_result()
        prompt_file = self.root / "prompt.txt"
        prompt_file.write_text("from file prompt", encoding="utf-8")
        rc, _ = self._capture(["run", str(prompt_file)])
        self.assertEqual(rc, 0)
        self.assertEqual(run.call_args.args[0], "from file prompt")

    @mock.patch("codex_exec.run_codex")
    def test_out_dir_writes_text_and_events_jsonl(self, run):
        run.return_value = self._ok_result()
        out_dir = self.root / "out"
        rc, _ = self._capture(["run", "-", "--out", str(out_dir)], "p")
        self.assertEqual(rc, 0)
        self.assertEqual(
            (out_dir / "text.txt").read_text(encoding="utf-8"), "codex-smoke-ok"
        )
        saved_events = (out_dir / "events.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        self.assertEqual(saved_events, REAL_STREAM)

    @mock.patch("codex_exec.run_codex")
    def test_model_timeout_skip_flags_forwarded(self, run):
        run.return_value = self._ok_result()
        rc, _ = self._capture(
            ["run", "-", "--model", "gpt-5-codex", "--timeout", "42", "--skip-git-check"],
            "p",
        )
        self.assertEqual(rc, 0)
        _, kwargs = run.call_args
        self.assertEqual(kwargs["model"], "gpt-5-codex")
        self.assertEqual(kwargs["timeout"], 42)
        self.assertTrue(kwargs["skip_git_check"])

    @mock.patch("codex_exec.run_codex")
    def test_timeout_exit_code_3(self, run):
        run.return_value = self._ok_result(status="timeout", error_type=None, text="")
        rc, _ = self._capture(["run", "-"], "p")
        self.assertEqual(rc, 3)

    @mock.patch("codex_exec.run_codex")
    def test_auth_failure_exit_code_4(self, run):
        run.return_value = self._ok_result(
            status="error", error_type="authentication", text=""
        )
        rc, _ = self._capture(["run", "-"], "p")
        self.assertEqual(rc, 4)

    @mock.patch("codex_exec.run_codex")
    def test_not_installed_exit_code_2(self, run):
        run.return_value = self._ok_result(
            status="error", error_type="not_installed", text=""
        )
        rc, _ = self._capture(["run", "-"], "p")
        self.assertEqual(rc, 2)

    @mock.patch("codex_exec.run_codex")
    def test_generic_failure_exit_code_1(self, run):
        run.return_value = self._ok_result(
            status="error", error_type="unknown", text=""
        )
        rc, _ = self._capture(["run", "-"], "p")
        self.assertEqual(rc, 1)

    def test_default_timeout_is_120(self):
        parsed = codex_exec.build_parser().parse_args(["run", "-"])
        self.assertEqual(parsed.timeout, 120)


if __name__ == "__main__":
    unittest.main()
