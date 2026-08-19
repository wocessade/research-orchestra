"""codex_modes.py — three Codex agent-mode protocols for CC (subsystem-3).

Wraps codex_exec.run_codex into three mission-mode protocols used by the CC
orchestrator (mission 027):

  * mutual-review  — codex reviews a diff and returns a JSON findings array
                     (severity/file/line/issue/suggestion per finding).
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
  * Divergence computation is mechanical (returncodes, unified_diff, file
    set comparison) — no LLM involved.
"""
import argparse
import difflib
import json
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
    "OUTPUT CONTRACT: your entire reply must be exactly one valid JSON array, "
    "with no markdown code fences (no ```), no prose, and no explanation. "
    "Each finding object must have exactly these fields:\n"
    '  {"severity": "high"|"med"|"low", "file": "<path or empty string>",\n'
    '   "line": <1-based int or null>, "issue": "<one sentence>",\n'
    '   "suggestion": "<one sentence>"}\n'
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
    "OUTPUT CONTRACT: your entire reply must be exactly one valid JSON array "
    "with one object per claim, in any order, with no markdown code fences, "
    "no prose, and no explanation:\n"
    '  [{"claim_index": <int>, "verdict": "true"|"false"|"unsure", "reason": "<one sentence>"}]\n'
    "CLAIMS:\n"
)

_VALID_SEVERITIES = ("high", "med", "low")


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

def _extract_json_array(text):
    """Lenient: strip ``` fences, slice first '[' .. last ']', json.loads.

    Returns the parsed list, or None when no valid JSON array is present.
    """
    if not text or not isinstance(text, str):
        return None
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, list) else None


def _normalize_finding(item):
    """Field-level type validation for one finding dict; None if not a dict.

    severity invalid -> "low"; line non-numeric -> None; non-str fields -> "".
    """
    if not isinstance(item, dict):
        return None
    severity = item.get("severity")
    if not isinstance(severity, str) or severity not in _VALID_SEVERITIES:
        severity = "low"
    file_ = item.get("file")
    if not isinstance(file_, str):
        file_ = ""
    line = item.get("line")
    if isinstance(line, bool):
        line = None
    elif isinstance(line, int):
        pass
    elif isinstance(line, str) and line.strip().lstrip("-").isdigit():
        line = int(line)
    else:
        line = None
    issue = item.get("issue")
    if not isinstance(issue, str):
        issue = ""
    suggestion = item.get("suggestion")
    if not isinstance(suggestion, str):
        suggestion = ""
    return {
        "severity": severity, "file": file_, "line": line,
        "issue": issue, "suggestion": suggestion,
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
                "raw": raw, "error": result.get("error_type") or result.get("status")}
    array = _extract_json_array(raw)
    if array is None:
        return {"mode": "mutual-review", "status": "error", "findings": [],
                "raw": raw, "error": "parse_failed"}
    findings = []
    for item in array:
        finding = _normalize_finding(item)
        if finding is not None:
            findings.append(finding)
    return {"mode": "mutual-review", "status": "ok", "findings": findings, "raw": raw}


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
                "raw": raw, "error": error}

    if result.get("status") != "ok":
        return error_result(result.get("error_type") or result.get("status"))

    codex_files = _list_py_files(codex_impl)
    if not codex_files:
        return error_result("codex_impl_empty")

    t_runner = run_tests if run_tests is not None else _default_run_tests
    command = _build_test_command(tests_dir)
    cc_rc, cc_out = t_runner(list(command), impl_dir, _test_env(impl_dir))
    cx_rc, cx_out = t_runner(list(command), impl_dir, _test_env(codex_impl))
    cc_tests = {"command": list(command), "returncode": cc_rc, "stdout_tail": _tail(cc_out)}
    codex_tests = {"command": list(command), "returncode": cx_rc, "stdout_tail": _tail(cx_out)}
    divergences = _compute_divergences(
        impl_dir, codex_impl, cc_rc, cx_rc, cc_out, cx_out, tests_dir)
    return {"mode": "dual-implement", "status": "ok", "cc_tests": cc_tests,
            "codex_tests": codex_tests, "divergences": divergences,
            "impl_files": codex_files, "raw": raw}


# ---------------------------------------------------------------------------
# Mode 3: claim check
# ---------------------------------------------------------------------------

def _claim_check_error(raw: str, claims_list: List[str], verdicts: List[Optional[str]],
                       provided: bool, error: str) -> Dict:
    entries = []
    for i, claim in enumerate(claims_list):
        entries.append({"claim": claim, "cc_verdict": verdicts[i], "codex_verdict": None,
                        "codex_reason": None, "agree": None})
    return {"mode": "claim-check", "status": "error", "claims": entries,
            "disagree": [], "raw": raw, "error": error, "cc_verdicts_provided": provided}


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
    array = _extract_json_array(raw)
    if array is None:
        return _claim_check_error(raw, claims_list, verdicts, provided, "parse_failed")

    codex_verdicts = [None] * len(claims_list)
    codex_reasons = [None] * len(claims_list)
    for item in array:
        if not isinstance(item, dict):
            continue
        idx = item.get("claim_index")
        if isinstance(idx, bool) or not isinstance(idx, int):
            continue
        if not 0 <= idx < len(claims_list):
            continue
        verdict = _normalize_verdict(item.get("verdict"))
        if verdict is not None:
            codex_verdicts[idx] = verdict
        reason = item.get("reason")
        codex_reasons[idx] = reason if isinstance(reason, str) else None

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
        entries.append({"claim": claim, "cc_verdict": cv, "codex_verdict": xv,
                        "codex_reason": codex_reasons[i], "agree": agree})
    return {"mode": "claim-check", "status": "ok", "claims": entries,
            "disagree": disagree, "raw": raw, "cc_verdicts_provided": provided}


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
