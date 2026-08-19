"""codex_modes.py — three Codex agent-mode protocols for CC (subsystem-3).

Wraps codex_exec.run_codex into three mission-mode protocols used by the CC
orchestrator (mission 027):

  * mutual-review  — codex reviews a diff and returns evidence-backed findings
                     with triggers, impact, uncertainty, and validation steps.
  * dual-implement — codex writes a parallel implementation under
                     <impl_dir>/codex_impl, then the SAME test suite is run
                     against both implementations and mechanical divergences
                     (behavior / interface / style) are computed.
  * claim-check    — codex verdicts true/false/unsure per claim; agreement
                     with CC's own verdicts (passed in by the caller) is
                     reported per claim and as a disagree index list.

Design decisions:
  * The codex subprocess is never invoked from this module directly — every
    mode accepts `run` (default: codex_exec.run_codex) and dual_implement
    additionally accepts `run_tests`, so tests inject fakes and there are
    zero real codex calls outside the mission run.
  * Timeouts default to 300s (cold start on this machine is ~3 min) and
    600s for dual-implement, which asks codex to write multiple files.
  * Output is strictly machine-readable: prompts demand a bare JSON value
    (no markdown fences, no prose). Parse failures degrade to
    status="error" with error="parse_failed" instead of raising; run
    failures degrade with error = error_type or status from run_codex.
    Successful results keep only normalized data; failed results retain raw
    model text for diagnostics, avoiding duplicate structured/raw payloads.
  * Divergence computation is mechanical (returncodes, unified_diff, file
    set comparison) — no LLM involved.
"""
import argparse
import difflib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional

import codex_exec

# ---------------------------------------------------------------------------
# Prompt templates (fixed protocol prefixes + user content, concatenated)
# ---------------------------------------------------------------------------

_MUTUAL_REVIEW_PREFIX = (
    "You are a code reviewer performing a mutual review of a code diff.\n"
    "Review for concrete correctness, security, reliability, performance, "
    "maintainability, or testing risks. Do not report a pure style preference "
    "unless it has a concrete impact. Before finalizing a finding, look for "
    "counter-evidence and state remaining uncertainty.\n"
    "OUTPUT CONTRACT: your entire reply must be exactly one valid JSON array, "
    "with no markdown code fences (no ```), no prose, and no explanation. "
    "Each finding object must have exactly these fields:\n"
    '  {"id": "<stable finding id such as F-001>",\n'
    '   "severity": "high"|"med"|"low",\n'
    '   "category": "correctness"|"security"|"reliability"|"performance"|'
    '"maintainability"|"testing"|"other",\n'
    '   "file": "<primary path or empty string>",\n'
    '   "line_start": <1-based int or null>, "line_end": <1-based int or null>,\n'
    '   "claim": "<complete explanation of the problem; no artificial sentence limit>",\n'
    '   "evidence": [{"file": "<path>", "line_start": <int or null>, '
    '"line_end": <int or null>, "excerpt": "<relevant code or observed fact>"}],\n'
    '   "trigger": "<conditions required to reproduce the problem>",\n'
    '   "impact": "<concrete consequence if triggered>",\n'
    '   "counter_evidence": "<facts that weaken the finding, or empty string>",\n'
    '   "confidence": <number from 0.0 to 1.0>,\n'
    '   "uncertainties": ["<missing context or unresolved question>"],\n'
    '   "suggested_fix": "<specific repair direction; no artificial sentence limit>",\n'
    '   "validation_test": "<test or check that proves the repair>"}\n'
    "Use [] when there is nothing to report.\n\n"
    "DIFF TO REVIEW:\n"
)

_DUAL_IMPL_PREFIX = (
    "You are an implementation engineer. Implement the specification below by "
    "writing files on disk. Create the directory impl_dir/codex_impl (shown "
    "below) if it does not exist, and put ALL implementation files inside it. "
    "Read the tests in tests_dir and make your implementation pass them. Use "
    "the standard library unless the specification requires otherwise. Do not "
    "modify anything outside codex_impl.\n"
    "OUTPUT CONTRACT: after writing the files, your entire reply must be "
    "exactly one valid JSON array (a manifest of the files you wrote), with "
    "no markdown code fences, no prose, and no explanation:\n"
    '  [{"file": "<relative path under codex_impl>", "summary": "<what it does>"}]\n'
    "SPECIFICATION:\n"
)

_CLAIM_CHECK_PREFIX = (
    "You are a claim verifier. For each claim below, decide whether it is "
    "TRUE, FALSE, or UNSURE (UNSURE = not enough information to decide).\n"
    "Evaluate the available support and counter-evidence before choosing a "
    "verdict. Do not force a binary conclusion when context is missing.\n"
    "OUTPUT CONTRACT: your entire reply must be exactly one valid JSON array "
    "with one object per claim, in any order, with no markdown code fences, "
    "no prose, and no explanation:\n"
    '  [{"claim_index": <int>, "verdict": "true"|"false"|"unsure",\n'
    '    "reason": "<complete reasoning; no artificial sentence limit>",\n'
    '    "evidence": ["<fact supporting the verdict>"],\n'
    '    "counter_evidence": ["<fact weakening the verdict>"],\n'
    '    "missing_context": ["<information needed for a stronger verdict>"],\n'
    '    "confidence": <number from 0.0 to 1.0>}]\n'
    "CLAIMS:\n"
)

_VALID_SEVERITIES = ("high", "med", "low")
_VALID_CATEGORIES = (
    "correctness", "security", "reliability", "performance",
    "maintainability", "testing", "other",
)
_FINDING_REQUIRED_FIELDS = (
    "id", "severity", "category", "file", "line_start", "line_end", "claim",
    "evidence", "trigger", "impact", "counter_evidence", "confidence",
    "uncertainties", "suggested_fix", "validation_test",
)
_CLAIM_REQUIRED_FIELDS = (
    "claim_index", "verdict", "reason", "evidence", "counter_evidence",
    "missing_context", "confidence",
)


def build_prompt(mode: str, payload: Optional[Dict]) -> str:
    """Assemble the fixed protocol template + user content for a mode.

    payload fields per mode:
      mutual-review  -> {diff, context}            (context may be empty)
      dual-implement -> {spec, impl_dir, tests_dir}
      claim-check    -> {claims}                   (list or JSON-array string)

    Raises ValueError for unknown modes.
    """
    payload = payload or {}
    if mode == "mutual-review":
        diff = str(payload.get("diff", ""))
        context = str(payload.get("context") or "")
        parts = [_MUTUAL_REVIEW_PREFIX, diff]
        if context.strip():
            parts += ["\n\nADDITIONAL CONTEXT:\n", context]
        return "".join(parts)
    if mode == "dual-implement":
        impl_dir = str(payload.get("impl_dir", ""))
        codex_impl = str(payload.get("codex_impl") or os.path.join(impl_dir, "codex_impl"))
        return "".join([
            _DUAL_IMPL_PREFIX,
            str(payload.get("spec", "")),
            "\n\nIMPL_DIR: ", impl_dir,
            "\nCODEX_IMPL_DIR: ", codex_impl,
            "\nTESTS_DIR: ", str(payload.get("tests_dir", "")),
            "\n",
        ])
    if mode == "claim-check":
        return "".join([_CLAIM_CHECK_PREFIX, _claims_to_json(payload.get("claims"))])
    raise ValueError("unknown mode: %r" % (mode,))


def _normalize_claims(claims) -> List[str]:
    """claims may be a list or a JSON-array string; always return [str]."""
    if isinstance(claims, str):
        try:
            parsed = json.loads(claims)
        except json.JSONDecodeError:
            parsed = None
        claims = parsed if isinstance(parsed, list) else [claims]
    if not isinstance(claims, list):
        claims = [claims]
    return [str(c) for c in claims]


def _claims_to_json(claims) -> str:
    return json.dumps(_normalize_claims(claims), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Lenient JSON array extraction / finding normalization
# ---------------------------------------------------------------------------

def _extract_json_array_with_protocol(text):
    """Parse a JSON array and report whether format repair was required."""
    meta = {"status": "invalid", "repair_actions": []}
    if not text or not isinstance(text, str):
        return None, meta
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
        meta["repair_actions"].append("removed_markdown_fence")
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end <= start:
        return None, meta
    if start != 0 or end != len(cleaned) - 1:
        meta["repair_actions"].append("removed_surrounding_prose")
    try:
        obj = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None, meta
    if not isinstance(obj, list):
        return None, meta
    meta["status"] = "repaired" if meta["repair_actions"] else "valid"
    return obj, meta


def _extract_json_array(text):
    """Backward-compatible parsed-array helper."""
    array, _meta = _extract_json_array_with_protocol(text)
    return array


def _protocol_meta(parse_meta, dropped_items=0, missing_fields=None,
                   invalid_fields=None, extra_repairs=None):
    missing_fields = missing_fields or []
    invalid_fields = invalid_fields or []
    repairs = list(parse_meta.get("repair_actions", []))
    repairs.extend(extra_repairs or [])
    if dropped_items or missing_fields or invalid_fields:
        status = "partial"
    elif repairs:
        status = "repaired"
    else:
        status = parse_meta.get("status", "invalid")
    return {
        "status": status,
        "repair_actions": repairs,
        "dropped_items": dropped_items,
        "missing_fields": missing_fields,
        "invalid_fields": invalid_fields,
    }


def _normalize_line(value):
    """Return a strictly typed positive line number or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    return None


def _normalize_text(value, default=""):
    return value if isinstance(value, str) else default


def _normalize_string_list(value) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _normalize_confidence(value):
    if isinstance(value, bool):
        return None
    if (isinstance(value, (int, float)) and math.isfinite(value)
            and 0.0 <= value <= 1.0):
        return float(value)
    return None


def _valid_line(value) -> bool:
    return value is None or (
        isinstance(value, int) and not isinstance(value, bool) and value > 0
    )


def _line_range_is_valid(start, end) -> bool:
    return _valid_line(start) and _valid_line(end) and (
        start is None or end is None or start <= end
    )


def _normalize_evidence(value) -> List[Dict]:
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if not isinstance(item, dict):
            continue
        start = item.get("line_start")
        end = item.get("line_end")
        if (
            set(item) != {"file", "line_start", "line_end", "excerpt"}
            or not isinstance(item.get("file"), str)
            or not isinstance(item.get("excerpt"), str)
            or not _line_range_is_valid(start, end)
        ):
            continue
        normalized.append({
            "file": item["file"],
            "line_start": start,
            "line_end": end,
            "excerpt": item["excerpt"],
        })
    return normalized


def _validate_string_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_evidence(value, item_index: int) -> List[Dict]:
    invalid = []
    if not isinstance(value, list):
        return [{"index": item_index, "field": "evidence"}]
    required = {"file", "line_start", "line_end", "excerpt"}
    for evidence_index, evidence in enumerate(value):
        prefix = "evidence[%d]" % evidence_index
        if not isinstance(evidence, dict):
            invalid.append({"index": item_index, "field": prefix})
            continue
        if set(evidence) != required:
            invalid.append({"index": item_index, "field": prefix + ".fields"})
        for field in ("file", "excerpt"):
            if not isinstance(evidence.get(field), str):
                invalid.append({"index": item_index, "field": prefix + "." + field})
        start = evidence.get("line_start")
        end = evidence.get("line_end")
        if not _valid_line(start):
            invalid.append({"index": item_index, "field": prefix + ".line_start"})
        if not _valid_line(end):
            invalid.append({"index": item_index, "field": prefix + ".line_end"})
        if _valid_line(start) and _valid_line(end) and not _line_range_is_valid(start, end):
            invalid.append({"index": item_index, "field": prefix + ".line_range"})
    return invalid


def _with_protocol_outcome(result: Dict, protocol: Dict, raw: str) -> Dict:
    """Apply protocol status to the public result and retain diagnostic raw."""
    result["protocol"] = protocol
    protocol_status = protocol.get("status")
    if protocol_status == "valid":
        result["status"] = "ok"
    elif protocol_status == "repaired":
        result["status"] = "ok"
        result["raw"] = raw
    else:
        result["status"] = "error"
        result["raw"] = raw
        result.setdefault("error", "protocol_%s" % protocol_status)
    return result


def _normalize_finding(item, index: int = 0):
    """Normalize one evidence-backed finding; accepts the legacy v1 aliases.

    Legacy input aliases remain readable during migration:
      line -> line_start/line_end, issue -> claim, suggestion -> suggested_fix.
    """
    if not isinstance(item, dict):
        return None
    severity = item.get("severity")
    if not isinstance(severity, str) or severity not in _VALID_SEVERITIES:
        severity = "low"
    category = item.get("category")
    if not isinstance(category, str) or category not in _VALID_CATEGORIES:
        category = "other"
    line_start = _normalize_line(item.get("line_start", item.get("line")))
    line_end = _normalize_line(item.get("line_end", item.get("line")))
    finding_id = _normalize_text(item.get("id")).strip() or "F-%03d" % (index + 1)
    return {
        "id": finding_id,
        "severity": severity,
        "category": category,
        "file": _normalize_text(item.get("file")),
        "line_start": line_start,
        "line_end": line_end,
        "claim": _normalize_text(item.get("claim", item.get("issue"))),
        "evidence": _normalize_evidence(item.get("evidence")),
        "trigger": _normalize_text(item.get("trigger")),
        "impact": _normalize_text(item.get("impact")),
        "counter_evidence": _normalize_text(item.get("counter_evidence")),
        "confidence": _normalize_confidence(item.get("confidence")),
        "uncertainties": _normalize_string_list(item.get("uncertainties")),
        "suggested_fix": _normalize_text(
            item.get("suggested_fix", item.get("suggestion"))
        ),
        "validation_test": _normalize_text(item.get("validation_test")),
    }


def _normalize_verdict(v):
    """true/false/unsure (case-insensitive, JSON bools accepted); None if invalid."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    return v if v in ("true", "false", "unsure") else None


# ---------------------------------------------------------------------------
# Mode 1: mutual review
# ---------------------------------------------------------------------------

def mutual_review(diff: str, context: Optional[str] = None, run: Optional[Callable] = None,
                  model: Optional[str] = None, timeout: int = 300) -> Dict:
    """Codex reviews `diff` and returns normalized findings.

    Expected codex output: a JSON array of finding objects. Parse failures
    degrade to status="error"/error="parse_failed" instead of raising.
    """
    runner = run if run is not None else codex_exec.run_codex
    prompt = build_prompt("mutual-review", {"diff": diff, "context": context})
    result = runner(prompt, model=model, timeout=timeout, cwd=os.getcwd())
    raw = result.get("text", "")
    if result.get("status") != "ok":
        return {"mode": "mutual-review", "status": "error", "findings": [],
                "raw": raw, "error": result.get("error_type") or result.get("status"),
                "protocol": _protocol_meta({"status": "invalid"})}
    array, parse_meta = _extract_json_array_with_protocol(raw)
    if array is None:
        return {"mode": "mutual-review", "status": "error", "findings": [],
                "raw": raw, "error": "parse_failed",
                "protocol": _protocol_meta({"status": "invalid"})}
    findings = []
    dropped_items = 0
    missing_fields = []
    invalid_fields = []
    extra_repairs = []
    seen_ids = set()
    for index, item in enumerate(array):
        if not isinstance(item, dict):
            dropped_items += 1
            continue
        missing = [field for field in _FINDING_REQUIRED_FIELDS if field not in item]
        if "claim" in missing and "issue" in item:
            missing.remove("claim")
            extra_repairs.append(f"item[{index}].issue_to_claim")
        if "suggested_fix" in missing and "suggestion" in item:
            missing.remove("suggested_fix")
            extra_repairs.append(f"item[{index}].suggestion_to_suggested_fix")
        if "line_start" in missing and "line" in item:
            missing.remove("line_start")
            extra_repairs.append(f"item[{index}].line_to_line_start")
        if "line_end" in missing and "line" in item:
            missing.remove("line_end")
            extra_repairs.append(f"item[{index}].line_to_line_end")
        if missing:
            missing_fields.append({"index": index, "fields": missing})
        allowed_fields = set(_FINDING_REQUIRED_FIELDS) | {"line", "issue", "suggestion"}
        if not set(item).issubset(allowed_fields):
            invalid_fields.append({"index": index, "field": "unexpected_fields"})
        finding_id = item.get("id")
        if not isinstance(finding_id, str) or not finding_id.strip():
            invalid_fields.append({"index": index, "field": "id"})
        elif finding_id.strip() in seen_ids:
            invalid_fields.append({"index": index, "field": "duplicate_id"})
        else:
            seen_ids.add(finding_id.strip())
        severity = item.get("severity")
        if not isinstance(severity, str) or severity not in _VALID_SEVERITIES:
            invalid_fields.append({"index": index, "field": "severity"})
        category = item.get("category")
        if not isinstance(category, str) or category not in _VALID_CATEGORIES:
            invalid_fields.append({"index": index, "field": "category"})
        for field in (
            "file", "claim", "trigger", "impact", "counter_evidence",
            "suggested_fix", "validation_test",
        ):
            value = item.get(field)
            if field == "claim" and field not in item and "issue" in item:
                value = item.get("issue")
            elif field == "suggested_fix" and field not in item and "suggestion" in item:
                value = item.get("suggestion")
            if not isinstance(value, str):
                invalid_fields.append({"index": index, "field": field})
        line_start_value = item.get("line_start", item.get("line"))
        line_end_value = item.get("line_end", item.get("line"))
        if not _valid_line(line_start_value):
            invalid_fields.append({"index": index, "field": "line_start"})
        if not _valid_line(line_end_value):
            invalid_fields.append({"index": index, "field": "line_end"})
        if (
            _valid_line(line_start_value) and _valid_line(line_end_value)
            and not _line_range_is_valid(line_start_value, line_end_value)
        ):
            invalid_fields.append({"index": index, "field": "line_range"})
        if _normalize_confidence(item.get("confidence")) is None:
            invalid_fields.append({"index": index, "field": "confidence"})
        if not _validate_string_list(item.get("uncertainties")):
            invalid_fields.append({"index": index, "field": "uncertainties"})
        invalid_fields.extend(_validate_evidence(item.get("evidence"), index))
        finding = _normalize_finding(item, index=index)
        if finding is not None:
            findings.append(finding)
    protocol = _protocol_meta(
        parse_meta,
        dropped_items=dropped_items,
        missing_fields=missing_fields,
        invalid_fields=invalid_fields,
        extra_repairs=extra_repairs,
    )
    return _with_protocol_outcome({
        "mode": "mutual-review",
        "findings": findings,
    }, protocol, raw)


# ---------------------------------------------------------------------------
# Mode 2: dual implement
# ---------------------------------------------------------------------------

_TEST_RUN_TIMEOUT = 300

_FAILED_RE = re.compile(r"FAILED\s+([^\s:]+\.py)")


def _list_py_files(root: str, skip: Optional[str] = None) -> List[str]:
    """Sorted absolute .py paths under root; the skip subtree is excluded."""
    if not os.path.isdir(root):
        return []
    root = os.path.abspath(root)
    skip = os.path.abspath(skip) if skip else None
    files = []
    for dirpath, dirs, filenames in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        abs_dir = os.path.abspath(dirpath)
        if skip and (abs_dir == skip or abs_dir.startswith(skip + os.sep)):
            dirs[:] = []
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                files.append(os.path.normpath(os.path.join(abs_dir, fn)))
    return sorted(files)


def _list_relative_files(root: str) -> List[str]:
    """Return every real file under root as a sorted POSIX relative path."""
    if not os.path.isdir(root):
        return []
    files = []
    for dirpath, dirs, filenames in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            if os.path.isfile(path):
                files.append(Path(os.path.relpath(path, root)).as_posix())
    return sorted(files)


def _valid_manifest_path(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    return (
        not path.is_absolute()
        and "\\" not in value
        and value == path.as_posix()
        and "." not in path.parts
        and ".." not in path.parts
    )


def _detect_test_runner(tests_dir: str) -> str:
    """pytest when any .py under tests_dir starts with test_ or mentions
    pytest; otherwise unittest discover."""
    if not os.path.isdir(tests_dir):
        return "unittest"
    for dirpath, _dirs, filenames in os.walk(tests_dir):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            if fn.startswith("test_"):
                return "pytest"
            try:
                content = Path(dirpath, fn).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "pytest" in content:
                return "pytest"
    return "unittest"


def _build_test_command(tests_dir: str) -> List[str]:
    if _detect_test_runner(tests_dir) == "pytest":
        return [sys.executable, "-m", "pytest", "-q", tests_dir]
    return [sys.executable, "-m", "unittest", "discover", "-s", tests_dir]


def _test_env(impl_path: str) -> Dict:
    """Environment with impl_path prepended to PYTHONPATH (tests import the
    implementation under test from the right directory)."""
    env = os.environ.copy()
    old = env.get("PYTHONPATH")
    env["PYTHONPATH"] = impl_path if not old else impl_path + os.pathsep + old
    return env


def _default_run_tests(command: List[str], cwd: str, env: Optional[Dict] = None):
    """subprocess.run + capture; returns (returncode, combined stdout+stderr)."""
    try:
        proc = subprocess.run(
            command, cwd=cwd, capture_output=True, timeout=_TEST_RUN_TIMEOUT, env=env
        )
    except subprocess.TimeoutExpired:
        return (124, "test run timed out after %ds" % _TEST_RUN_TIMEOUT)
    out = (proc.stdout or b"").decode("utf-8", "replace")
    err = (proc.stderr or b"").decode("utf-8", "replace")
    return (proc.returncode, out + err)


def _tail(text: str, n: int = 40) -> str:
    if not text:
        return ""
    return "\n".join(text.splitlines()[-n:])


def _failing_test_file(output: str, tests_dir: str) -> str:
    """Best-effort extraction of the failing test path from runner output."""
    m = _FAILED_RE.search(output or "")
    if m:
        return m.group(1)
    return str(tests_dir)


def _compute_divergences(impl_dir: str, codex_impl: str, cc_rc: int, codex_rc: int,
                         cc_out: str, codex_out: str, tests_dir: str) -> List[Dict]:
    """Mechanical divergence detection: test outcome, same-file content diff,
    and file set difference."""
    divergences = []
    cc_pass = cc_rc == 0
    codex_pass = codex_rc == 0
    if cc_pass != codex_pass:
        if cc_pass:
            file_ = _failing_test_file(codex_out, tests_dir)
            detail = "codex implementation fails the shared tests (rc=%d)" % codex_rc
        else:
            file_ = _failing_test_file(cc_out, tests_dir)
            detail = "cc implementation fails the shared tests (rc=%d)" % cc_rc
        divergences.append({"kind": "behavior", "file": file_, "detail": detail})

    cc_files = _list_py_files(impl_dir, skip=codex_impl)
    cx_files = _list_py_files(codex_impl)
    cc_rel = {os.path.relpath(p, impl_dir): p for p in cc_files}
    cx_rel = {os.path.relpath(p, codex_impl): p for p in cx_files}

    for rel in sorted(set(cc_rel) & set(cx_rel)):
        cc_lines = Path(cc_rel[rel]).read_text(
            encoding="utf-8", errors="replace").splitlines(keepends=True)
        cx_lines = Path(cx_rel[rel]).read_text(
            encoding="utf-8", errors="replace").splitlines(keepends=True)
        if cc_lines == cx_lines:
            continue
        diff_lines = list(difflib.unified_diff(
            cc_lines, cx_lines, fromfile="cc/" + rel, tofile="codex/" + rel))
        divergences.append({
            "kind": "interface",
            "file": rel,
            "detail": "\n".join(diff_lines[:10]),
        })

    for rel in sorted(set(cc_rel) - set(cx_rel)):
        divergences.append({
            "kind": "style",
            "file": rel,
            "detail": "file exists in cc implementation but not in codex implementation",
        })
    for rel in sorted(set(cx_rel) - set(cc_rel)):
        divergences.append({
            "kind": "style",
            "file": rel,
            "detail": "file exists in codex implementation but not in cc implementation",
        })
    return divergences


def dual_implement(spec: str, impl_dir: str, tests_dir: str,
                   run: Optional[Callable] = None, run_tests: Optional[Callable] = None,
                   model: Optional[str] = None, timeout: int = 600) -> Dict:
    """Codex writes a parallel implementation under <impl_dir>/codex_impl,
    then the same test suite runs against both implementations and mechanical
    divergences (behavior / interface / style) are computed.

    run_tests (injectable for tests) has the signature
        run_tests(command, cwd, env) -> (returncode, stdout_text)
    and is used twice: once with PYTHONPATH pointing at impl_dir (CC side)
    and once at impl_dir/codex_impl (codex side).
    """
    runner = run if run is not None else codex_exec.run_codex
    impl_dir = os.path.abspath(impl_dir)
    tests_dir = os.path.abspath(tests_dir)
    codex_impl = os.path.join(impl_dir, "codex_impl")
    prompt = build_prompt("dual-implement", {
        "spec": spec, "impl_dir": impl_dir, "tests_dir": tests_dir,
    })
    result = runner(prompt, model=model, timeout=timeout, cwd=os.getcwd())
    raw = result.get("text", "")

    def error_result(error: str) -> Dict:
        return {"mode": "dual-implement", "status": "error", "cc_tests": None,
                "codex_tests": None, "divergences": [], "impl_files": [],
                "raw": raw, "error": error,
                "protocol": _protocol_meta({"status": "invalid"})}

    if result.get("status") != "ok":
        return error_result(result.get("error_type") or result.get("status"))

    manifest, parse_meta = _extract_json_array_with_protocol(raw)
    if manifest is None:
        return error_result("parse_failed")
    dropped_items = 0
    missing_fields = []
    invalid_fields = []
    manifest_files = []
    seen_manifest_files = set()
    for index, item in enumerate(manifest):
        if not isinstance(item, dict):
            dropped_items += 1
            continue
        missing = [field for field in ("file", "summary") if field not in item]
        if missing:
            missing_fields.append({"index": index, "fields": missing})
        if set(item) != {"file", "summary"}:
            invalid_fields.append({"index": index, "field": "fields"})
        file_value = item.get("file")
        if not _valid_manifest_path(file_value):
            invalid_fields.append({"index": index, "field": "file"})
        elif file_value in seen_manifest_files:
            invalid_fields.append({"index": index, "field": "duplicate_file"})
        else:
            seen_manifest_files.add(file_value)
            manifest_files.append(file_value)
        if not isinstance(item.get("summary"), str):
            invalid_fields.append({"index": index, "field": "summary"})

    codex_files = _list_py_files(codex_impl)
    if not codex_files:
        return error_result("codex_impl_empty")
    actual_files = _list_relative_files(codex_impl)
    missing_from_disk = sorted(set(manifest_files) - set(actual_files))
    missing_from_manifest = sorted(set(actual_files) - set(manifest_files))
    if missing_from_disk:
        invalid_fields.append({
            "field": "manifest_files_missing_from_disk",
            "files": missing_from_disk,
        })
    if missing_from_manifest:
        invalid_fields.append({
            "field": "files_missing_from_manifest",
            "files": missing_from_manifest,
        })
    protocol = _protocol_meta(
        parse_meta,
        dropped_items=dropped_items,
        missing_fields=missing_fields,
        invalid_fields=invalid_fields,
    )
    if protocol["status"] in ("partial", "invalid"):
        return _with_protocol_outcome(
            {"mode": "dual-implement", "cc_tests": None,
             "codex_tests": None, "divergences": [],
             "impl_files": codex_files},
            protocol,
            raw,
        )

    t_runner = run_tests if run_tests is not None else _default_run_tests
    command = _build_test_command(tests_dir)
    cc_rc, cc_out = t_runner(list(command), impl_dir, _test_env(impl_dir))
    cx_rc, cx_out = t_runner(list(command), impl_dir, _test_env(codex_impl))
    cc_tests = {"command": list(command), "returncode": cc_rc, "stdout_tail": _tail(cc_out)}
    codex_tests = {"command": list(command), "returncode": cx_rc, "stdout_tail": _tail(cx_out)}
    divergences = _compute_divergences(
        impl_dir, codex_impl, cc_rc, cx_rc, cc_out, cx_out, tests_dir)
    return _with_protocol_outcome(
        {"mode": "dual-implement", "cc_tests": cc_tests,
         "codex_tests": codex_tests, "divergences": divergences,
         "impl_files": codex_files},
        protocol,
        raw,
    )


# ---------------------------------------------------------------------------
# Mode 3: claim check
# ---------------------------------------------------------------------------

def _claim_check_error(raw: str, claims_list: List[str], verdicts: List[Optional[str]],
                       provided: bool, error: str) -> Dict:
    entries = []
    for i, claim in enumerate(claims_list):
        entries.append({"claim": claim, "cc_verdict": verdicts[i], "codex_verdict": None,
                        "codex_reason": None, "codex_evidence": [],
                        "codex_counter_evidence": [], "codex_missing_context": [],
                        "codex_confidence": None, "agree": None})
    return {"mode": "claim-check", "status": "error", "claims": entries,
            "disagree": [], "raw": raw, "error": error,
            "cc_verdicts_provided": provided,
            "protocol": _protocol_meta({"status": "invalid"})}


def claim_check(claims, cc_verdicts: Optional[List] = None, run: Optional[Callable] = None,
                model: Optional[str] = None, timeout: int = 300) -> Dict:
    """Codex verdicts true/false/unsure per claim; agreement vs CC verdicts.

    cc_verdicts (v1): list of true/false/unsure (or JSON bools / null) with
    the same length as claims; when omitted all entries get cc_verdict=null,
    agree is not computable (None) and disagree=[] with
    cc_verdicts_provided=False.
    """
    runner = run if run is not None else codex_exec.run_codex
    claims_list = _normalize_claims(claims)
    prompt = build_prompt("claim-check", {"claims": claims_list})
    provided = isinstance(cc_verdicts, list)
    verdicts = [None] * len(claims_list)
    if provided:
        for i in range(min(len(cc_verdicts), len(claims_list))):
            verdicts[i] = _normalize_verdict(cc_verdicts[i])

    result = runner(prompt, model=model, timeout=timeout, cwd=os.getcwd())
    raw = result.get("text", "")
    if result.get("status") != "ok":
        return _claim_check_error(raw, claims_list, verdicts, provided,
                                  result.get("error_type") or result.get("status"))
    array, parse_meta = _extract_json_array_with_protocol(raw)
    if array is None:
        return _claim_check_error(raw, claims_list, verdicts, provided, "parse_failed")

    codex_verdicts = [None] * len(claims_list)
    codex_reasons = [None] * len(claims_list)
    codex_evidence = [[] for _ in claims_list]
    codex_counter_evidence = [[] for _ in claims_list]
    codex_missing_context = [[] for _ in claims_list]
    codex_confidence = [None] * len(claims_list)
    dropped_items = 0
    missing_fields = []
    invalid_fields = []
    seen_indices = set()
    for item_index, item in enumerate(array):
        if not isinstance(item, dict):
            dropped_items += 1
            continue
        missing = [field for field in _CLAIM_REQUIRED_FIELDS if field not in item]
        if missing:
            missing_fields.append({"index": item_index, "fields": missing})
        if set(item) != set(_CLAIM_REQUIRED_FIELDS):
            invalid_fields.append({"index": item_index, "field": "fields"})
        idx = item.get("claim_index")
        if isinstance(idx, bool) or not isinstance(idx, int):
            dropped_items += 1
            invalid_fields.append({"index": item_index, "field": "claim_index"})
            continue
        if not 0 <= idx < len(claims_list):
            dropped_items += 1
            invalid_fields.append({"index": item_index, "field": "claim_index"})
            continue
        if idx in seen_indices:
            dropped_items += 1
            invalid_fields.append({"index": item_index, "field": "duplicate_claim_index"})
            continue
        seen_indices.add(idx)
        verdict_value = item.get("verdict")
        verdict = _normalize_verdict(verdict_value)
        if isinstance(verdict_value, str) and verdict_value in ("true", "false", "unsure"):
            codex_verdicts[idx] = verdict
        else:
            invalid_fields.append({"index": item_index, "field": "verdict"})
        reason = item.get("reason")
        codex_reasons[idx] = reason if isinstance(reason, str) else None
        if not isinstance(reason, str):
            invalid_fields.append({"index": item_index, "field": "reason"})
        for field in ("evidence", "counter_evidence", "missing_context"):
            if not _validate_string_list(item.get(field)):
                invalid_fields.append({"index": item_index, "field": field})
        codex_evidence[idx] = _normalize_string_list(item.get("evidence"))
        codex_counter_evidence[idx] = _normalize_string_list(item.get("counter_evidence"))
        codex_missing_context[idx] = _normalize_string_list(item.get("missing_context"))
        codex_confidence[idx] = _normalize_confidence(item.get("confidence"))
        if codex_confidence[idx] is None:
            invalid_fields.append({"index": item_index, "field": "confidence"})

    for claim_index in range(len(claims_list)):
        if claim_index not in seen_indices:
            missing_fields.append({
                "claim_index": claim_index,
                "fields": list(_CLAIM_REQUIRED_FIELDS),
            })

    entries = []
    disagree = []
    for i, claim in enumerate(claims_list):
        cv, xv = verdicts[i], codex_verdicts[i]
        if cv is None or xv is None:
            agree = None
        else:
            agree = cv == xv
            if not agree:
                disagree.append(i)
        entries.append({
            "claim": claim,
            "cc_verdict": cv,
            "codex_verdict": xv,
            "codex_reason": codex_reasons[i],
            "codex_evidence": codex_evidence[i],
            "codex_counter_evidence": codex_counter_evidence[i],
            "codex_missing_context": codex_missing_context[i],
            "codex_confidence": codex_confidence[i],
            "agree": agree,
        })
    protocol = _protocol_meta(
        parse_meta,
        dropped_items=dropped_items,
        missing_fields=missing_fields,
        invalid_fields=invalid_fields,
    )
    return _with_protocol_outcome({
        "mode": "claim-check",
        "claims": entries,
        "disagree": disagree,
        "cc_verdicts_provided": provided,
    }, protocol, raw)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex_modes.py",
        description="Three Codex agent modes for CC "
                    "(mutual review, dual implement, claim check).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    mr = sub.add_parser("mutual-review", help="Codex reviews a diff; findings JSON written to --out.")
    mr.add_argument("diff_file", help="Path to the diff under review.")
    mr.add_argument("--context", default=None, help="Optional extra context file.")
    mr.add_argument("--model", default=None, help="Codex model to use.")
    mr.add_argument("--timeout", type=int, default=300, help="Timeout in seconds (default 300).")
    mr.add_argument("--out", default="review.json", help="Output JSON path (default review.json).")

    di = sub.add_parser("dual-implement",
                        help="Codex writes a parallel implementation; tests run against both.")
    di.add_argument("spec_file", help="Path to the specification file.")
    di.add_argument("--impl-dir", required=True,
                    help="CC implementation dir; codex writes into <impl-dir>/codex_impl.")
    di.add_argument("--tests-dir", required=True, help="Shared test suite dir (pytest or unittest).")
    di.add_argument("--model", default=None, help="Codex model to use.")
    di.add_argument("--timeout", type=int, default=600, help="Timeout in seconds (default 600).")
    di.add_argument("--out", default="dual.json", help="Output JSON path (default dual.json).")

    cc = sub.add_parser("claim-check", help="Codex verdicts per claim; agreement vs CC verdicts.")
    cc.add_argument("claims_file", help="JSON array file of claims.")
    cc.add_argument("--cc-verdicts", default=None,
                    help="Optional JSON array of CC verdicts (true/false/unsure/null).")
    cc.add_argument("--model", default=None, help="Codex model to use.")
    cc.add_argument("--timeout", type=int, default=300, help="Timeout in seconds (default 300).")
    cc.add_argument("--out", default="claims.json", help="Output JSON path (default claims.json).")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "mutual-review":
        diff = Path(args.diff_file).read_text(encoding="utf-8")
        context = Path(args.context).read_text(encoding="utf-8") if args.context else None
        result = mutual_review(diff, context=context, model=args.model, timeout=args.timeout)
    elif args.command == "dual-implement":
        spec = Path(args.spec_file).read_text(encoding="utf-8")
        result = dual_implement(spec, args.impl_dir, args.tests_dir,
                                model=args.model, timeout=args.timeout)
    elif args.command == "claim-check":
        claims = json.loads(Path(args.claims_file).read_text(encoding="utf-8"))
        cc_verdicts = None
        if args.cc_verdicts:
            cc_verdicts = json.loads(Path(args.cc_verdicts).read_text(encoding="utf-8"))
        result = claim_check(claims, cc_verdicts=cc_verdicts,
                             model=args.model, timeout=args.timeout)
    else:
        return 1

    out_path = Path(args.out)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(str(out_path))  # CC review entry point
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
