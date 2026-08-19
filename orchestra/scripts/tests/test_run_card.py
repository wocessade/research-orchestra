"""Tests for run_card.py — experiment card command extractor and ingest glue.

Stdlib unittest only. run_card.py is stdlib-only; the engine scripts
(validate_experiment_card.py / ingest_run.py) are invoked via subprocess and
are mocked here with unittest.mock.
"""
import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import run_card

# ---------------------------------------------------------------------------
# Card fixtures (module level so fences are never indented)
# ---------------------------------------------------------------------------

CARD_NO_COMMANDS = """\
---
id: EXP-001
---

# EXP-001

Manual card, no Commands section.
"""

CARD_SHARED_BARE = """\
## Commands

```
echo hello
echo world
```
"""

CARD_SHARED_BASH = """\
## Commands

```bash
echo hello
echo world
```
"""

CARD_TWO_ARMS = """\
---
id: EXP-001
status: designed
---

# EXP-001

## Commands

```bash
echo shared
```

# arm: ctl
```bash
python extract_single.py --out result.json
python score.py --out metrics.json
```

# arm: trt
```bash
python score.py --out metrics.json
```
"""

CARD_DUP_ARMS = """\
## Commands

# arm: ctl
```
echo one
```

# arm: trt
```
echo two
```

# arm: ctl
```
echo three
```
"""

CARD_ARM_BEFORE_SHARED = """\
## Commands

# arm: ctl
```bash
echo ctl-first
```

```bash
echo shared-late
```
"""

CARD_SECTION_STOP = """\
## Commands

```bash
echo yes
```

## Results

```bash
echo no
```
"""

CARD_BLANK_BEFORE_FENCE = """\
## Commands

# arm: ctl

```bash
echo ctl
```
"""

CARD_STRAY_ANNOTATION = """\
## Commands

# arm: ctl
Some prose line here.

```bash
echo shared
```
"""

CARD_EMPTY_COMMANDS = """\
## Commands

## Results

some results text
"""


# ---------------------------------------------------------------------------
# extract_commands
# ---------------------------------------------------------------------------

class ExtractCommandsTest(unittest.TestCase):
    def test_no_commands_section_returns_empty(self):
        self.assertEqual(run_card.extract_commands(CARD_NO_COMMANDS), "")

    def test_single_shared_block_bare_fence(self):
        self.assertEqual(
            run_card.extract_commands(CARD_SHARED_BARE), "echo hello\necho world"
        )

    def test_single_shared_block_bash_fence(self):
        self.assertEqual(
            run_card.extract_commands(CARD_SHARED_BASH), "echo hello\necho world"
        )

    def test_arm_none_lists_arm_ids(self):
        self.assertEqual(run_card.extract_commands(CARD_TWO_ARMS, None), "ctl\ntrt")
        self.assertEqual(run_card.extract_commands(CARD_TWO_ARMS), "ctl\ntrt")

    def test_arm_filter_ctl(self):
        self.assertEqual(
            run_card.extract_commands(CARD_TWO_ARMS, "ctl"),
            "echo shared\n\npython extract_single.py --out result.json\npython score.py --out metrics.json",
        )

    def test_arm_filter_trt(self):
        self.assertEqual(
            run_card.extract_commands(CARD_TWO_ARMS, "trt"),
            "echo shared\n\npython score.py --out metrics.json",
        )

    def test_unknown_arm_raises_value_error(self):
        with self.assertRaises(ValueError):
            run_card.extract_commands(CARD_TWO_ARMS, "bogus")

    def test_arm_ids_deduped_in_order(self):
        self.assertEqual(run_card.extract_commands(CARD_DUP_ARMS), "ctl\ntrt")
        self.assertEqual(
            run_card.extract_commands(CARD_DUP_ARMS, "ctl"), "echo one\n\necho three"
        )
        self.assertEqual(run_card.extract_commands(CARD_DUP_ARMS, "trt"), "echo two")

    def test_blocks_joined_in_appearance_order(self):
        self.assertEqual(
            run_card.extract_commands(CARD_ARM_BEFORE_SHARED, "ctl"),
            "echo ctl-first\n\necho shared-late",
        )
        self.assertEqual(run_card.extract_commands(CARD_ARM_BEFORE_SHARED), "ctl")

    def test_section_stops_at_next_h2_heading(self):
        self.assertEqual(run_card.extract_commands(CARD_SECTION_STOP), "echo yes")

    def test_blank_lines_between_annotation_and_fence(self):
        self.assertEqual(run_card.extract_commands(CARD_BLANK_BEFORE_FENCE), "ctl")
        self.assertEqual(
            run_card.extract_commands(CARD_BLANK_BEFORE_FENCE, "ctl"), "echo ctl"
        )

    def test_stray_arm_annotation_ignored_when_not_before_fence(self):
        self.assertEqual(run_card.extract_commands(CARD_STRAY_ANNOTATION), "echo shared")
        with self.assertRaises(ValueError):
            run_card.extract_commands(CARD_STRAY_ANNOTATION, "ctl")

    def test_empty_commands_section_returns_empty(self):
        self.assertEqual(run_card.extract_commands(CARD_EMPTY_COMMANDS), "")


# ---------------------------------------------------------------------------
# parse_card_id
# ---------------------------------------------------------------------------

class ParseCardIdTest(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(
            run_card.parse_card_id("---\nid: EXP-001\nstatus: designed\n---\nbody"),
            "EXP-001",
        )

    def test_inline_comment_stripped(self):
        self.assertEqual(
            run_card.parse_card_id("---\nid: EXP-001  # main comparison card\n---\n"),
            "EXP-001",
        )

    def test_comment_inside_quotes_preserved(self):
        self.assertEqual(
            run_card.parse_card_id('---\nid: "EXP#001"  # note\n---\n'), '"EXP#001"'
        )

    def test_no_front_matter_raises(self):
        with self.assertRaises(ValueError):
            run_card.parse_card_id("# EXP-001\n\nbody only\n")

    def test_unclosed_front_matter_raises(self):
        with self.assertRaises(ValueError):
            run_card.parse_card_id("---\nid: EXP-001\n")

    def test_missing_id_raises(self):
        with self.assertRaises(ValueError):
            run_card.parse_card_id("---\nstatus: designed\n---\n")

    def test_empty_id_raises(self):
        with self.assertRaises(ValueError):
            run_card.parse_card_id("---\nid:\n---\n")


# ---------------------------------------------------------------------------
# do_commands / do_ingest / main
# ---------------------------------------------------------------------------

class _FixtureMixin:
    """Tempdir fixture: card.md (EXP-001 with ctl/trt arms) + metrics.json."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.card = self.root / "card.md"
        self.card.write_text(CARD_TWO_ARMS, encoding="utf-8")
        self.metrics = self.root / "metrics.json"
        self.metrics.write_text(
            json.dumps(
                {
                    "run_id": "run-20260819-0001",
                    "exp_id": "EXP-001",
                    "status": "completed",
                    "metrics": {"accuracy": 0.75},
                }
            ),
            encoding="utf-8",
        )
        self.research_root = self.root / ".research"
        self.engine_dir = self.root / "engine"

    def _args(self, **overrides):
        defaults = dict(
            metrics=str(self.metrics),
            card=str(self.card),
            research_root=str(self.research_root),
            engine_dir=str(self.engine_dir),
            paper_dir=None,
            open_neg_on_fail=False,
        )
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def _capture(self, fn, *args, **kwargs):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = fn(*args, **kwargs)
        return rc, out.getvalue()


class DoCommandsTest(_FixtureMixin, unittest.TestCase):
    def test_lists_arms(self):
        rc, out = self._capture(run_card.do_commands, self.card)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "ctl\ntrt\n")

    def test_arm_filter(self):
        rc, out = self._capture(run_card.do_commands, self.card, "ctl")
        self.assertEqual(rc, 0)
        self.assertEqual(
            out,
            "echo shared\n\npython extract_single.py --out result.json\npython score.py --out metrics.json\n",
        )

    def test_unknown_arm_exits_2(self):
        rc, out = self._capture(run_card.do_commands, self.card, "nope")
        self.assertEqual(rc, 2)
        self.assertIn("unknown arm", out)


class DoIngestTest(_FixtureMixin, unittest.TestCase):
    def _do_ingest(self, **overrides):
        return self._capture(run_card.do_ingest, self._args(**overrides))

    @mock.patch("run_card.subprocess.run")
    def test_exp_id_mismatch_is_hard(self, run):
        self.metrics.write_text(
            json.dumps({"run_id": "run-1", "exp_id": "EXP-999"}), encoding="utf-8"
        )
        rc, out = self._do_ingest()
        self.assertEqual(rc, 2)
        run.assert_not_called()
        self.assertIn("HARD: exp_id mismatch: metrics=EXP-999 card=EXP-001", out)

    @mock.patch("run_card.subprocess.run")
    def test_validate_failure_is_hard_and_skips_ingest(self, run):
        run.return_value = SimpleNamespace(returncode=2)
        rc, out = self._do_ingest()
        self.assertEqual(rc, 2)
        self.assertEqual(run.call_count, 1)
        cmd = run.call_args.args[0]
        self.assertIn(sys.executable, cmd)
        self.assertIn("validate_experiment_card.py", cmd[1])
        self.assertNotIn("ingest_run.py", " ".join(cmd))
        self.assertIn("HARD: card validation failed", out)

    @mock.patch("run_card.subprocess.run")
    def test_success_path(self, run):
        run.side_effect = [
            SimpleNamespace(returncode=0),
            SimpleNamespace(returncode=0),
        ]
        rc, out = self._do_ingest()
        self.assertEqual(rc, 0)
        self.assertEqual(run.call_count, 2)
        validate_cmd = run.call_args_list[0].args[0]
        ingest_cmd = run.call_args_list[1].args[0]
        self.assertIn(sys.executable, validate_cmd)
        self.assertIn("validate_experiment_card.py", validate_cmd[1])
        self.assertIn(str(self.card), validate_cmd[2])
        self.assertIn(sys.executable, ingest_cmd)
        self.assertIn("ingest_run.py", ingest_cmd[1])
        self.assertIn(str(self.metrics), ingest_cmd)
        self.assertIn("--research-root", ingest_cmd)
        self.assertIn(str(self.research_root), ingest_cmd)
        self.assertNotIn("--paper-dir", ingest_cmd)
        self.assertNotIn("--open-neg-on-fail", ingest_cmd)
        self.assertIn("OK: ingested run-20260819-0001 → EXP-001", out)

    @mock.patch("run_card.subprocess.run")
    def test_ingest_failure_rc_passthrough(self, run):
        run.side_effect = [
            SimpleNamespace(returncode=0),
            SimpleNamespace(returncode=2),
        ]
        rc, out = self._do_ingest()
        self.assertEqual(rc, 2)
        self.assertNotIn("OK: ingested", out)

    @mock.patch("run_card.subprocess.run")
    def test_extra_flags_appended(self, run):
        run.side_effect = [
            SimpleNamespace(returncode=0),
            SimpleNamespace(returncode=0),
        ]
        paper = self.root / "paper"
        rc, _ = self._do_ingest(paper_dir=str(paper), open_neg_on_fail=True)
        self.assertEqual(rc, 0)
        ingest_cmd = run.call_args_list[1].args[0]
        self.assertIn("--paper-dir", ingest_cmd)
        self.assertIn(str(paper), ingest_cmd)
        self.assertIn("--open-neg-on-fail", ingest_cmd)

    @mock.patch("run_card.subprocess.run")
    def test_default_engine_dir(self, run):
        run.side_effect = [
            SimpleNamespace(returncode=0),
            SimpleNamespace(returncode=0),
        ]
        rc, _ = self._do_ingest(engine_dir=None)
        self.assertEqual(rc, 0)
        expected = str(Path.home() / ".claude" / "skills" / "academic-research-engine")
        self.assertIn(expected, run.call_args_list[0].args[0][1])
        self.assertIn(expected, run.call_args_list[1].args[0][1])

    @mock.patch("run_card.subprocess.run")
    def test_card_without_id_is_hard(self, run):
        self.card.write_text("---\nstatus: designed\n---\nbody\n", encoding="utf-8")
        rc, out = self._do_ingest()
        self.assertEqual(rc, 2)
        run.assert_not_called()
        self.assertIn("HARD:", out)


class MainTest(_FixtureMixin, unittest.TestCase):
    def test_main_commands_lists_arms(self):
        rc, out = self._capture(run_card.main, ["commands", str(self.card)])
        self.assertEqual(rc, 0)
        self.assertEqual(out, "ctl\ntrt\n")

    def test_main_commands_unknown_arm_exits_2(self):
        rc, _ = self._capture(
            run_card.main, ["commands", str(self.card), "--arm", "nope"]
        )
        self.assertEqual(rc, 2)

    @mock.patch("run_card.subprocess.run")
    def test_main_ingest_ok(self, run):
        run.side_effect = [
            SimpleNamespace(returncode=0),
            SimpleNamespace(returncode=0),
        ]
        rc, out = self._capture(
            run_card.main,
            [
                "ingest",
                str(self.metrics),
                "--card",
                str(self.card),
                "--engine-dir",
                str(self.engine_dir),
                "--research-root",
                str(self.research_root),
            ],
        )
        self.assertEqual(rc, 0)
        self.assertIn("OK: ingested run-20260819-0001 → EXP-001", out)


if __name__ == "__main__":
    unittest.main()
