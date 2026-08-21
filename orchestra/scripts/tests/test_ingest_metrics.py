"""ingest_run.validate_metrics fail-closed (Opus / GPT-SOL P0)."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def _load_ingest():
    path = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "academic-research-engine"
        / "scripts"
        / "ingest_run.py"
    )
    spec = importlib.util.spec_from_file_location("ingest_run_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


VALID = {
    "run_id": "run-20260819-0001",
    "exp_id": "EXP-001",
    "status": "completed",
    "metrics": {"accuracy": 0.75},
}


class ValidateMetricsFailClosedTest(unittest.TestCase):
    def setUp(self):
        self.mod = _load_ingest()

    def test_missing_jsonschema_is_error(self):
        with mock.patch.object(self.mod, "jsonschema", None):
            errs = self.mod.validate_metrics(VALID)
        self.assertTrue(any("jsonschema" in e for e in errs), errs)

    def test_missing_schema_file_is_error(self):
        missing = Path(tempfile.gettempdir()) / "orchestra-no-metrics.schema.json"
        if missing.exists():
            missing.unlink()
        with mock.patch.object(self.mod, "SCHEMA_PATH", missing):
            errs = self.mod.validate_metrics(VALID)
        self.assertTrue(any("schema" in e.lower() for e in errs), errs)

    def test_valid_metrics_pass_when_schema_available(self):
        try:
            import jsonschema  # noqa: F401
        except ImportError:
            self.skipTest("jsonschema not installed")
        self.assertTrue(self.mod.SCHEMA_PATH.is_file())
        self.assertEqual(self.mod.validate_metrics(VALID), [])

    def test_cli_missing_schema_exits_2(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        metrics = Path(tmp.name) / "metrics.json"
        metrics.write_text(json.dumps(VALID), encoding="utf-8")
        missing = Path(tmp.name) / "absent.schema.json"
        argv = ["ingest_run.py", str(metrics)]
        out = io.StringIO()
        with mock.patch.object(self.mod, "SCHEMA_PATH", missing), mock.patch(
            "sys.argv", argv
        ), contextlib.redirect_stdout(out):
            rc = self.mod.main()
        self.assertEqual(rc, 2)
        self.assertIn("schema", out.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
