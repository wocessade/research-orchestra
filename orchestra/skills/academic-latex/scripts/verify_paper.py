#!/usr/bin/env python3
"""Mechanical checks for academic LaTeX papers."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
# biblatex + natbib + classic
CITE_RE = re.compile(
    r"\\(?:cite|citep|citet|citepp|citepalt|citepalp|citeauthor|citeyear|"
    r"autocite|textcite|footcite|parencite|smartcite|fullcite|citeyearpar)\*?"
    r"(?:\[[^\]]*\]){0,2}\{([^}]+)\}"
)
REF_RE = re.compile(r"\\(?:ref|cref|Cref|eqref|autoref)\{([^}]+)\}")
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
BIBENTRY_RE = re.compile(r"@(?!string\b|comment\b|preamble\b)(\w+)\s*\{\s*([^,\s}]+)", re.I)
MARKER_RE = re.compile(r"\[CLAIM NEEDS EVIDENCE\]|PLACEHOLDER_[A-Za-z0-9_]+|(?<![A-Za-z])TODO(?![A-Za-z])")
INCLUDE_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
LOCATOR_RE = re.compile(r"\b(doi|eprint|url|isbn)\s*=", re.I)

AI_WORDS = [
    "leverage", "delve", "pivotal", "paramount", "underscore", "seamless",
    "holistic", "groundbreaking", "cutting-edge", "burgeoning", "multifaceted",
    "paradigm shift", "unprecedented",
]


def strip_tex_comments(text: str) -> str:
    """Remove % comments, respecting \% escapes."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "%" and (i == 0 or text[i - 1] != "\\"):
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def collect_tex(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.tex") if ".git" not in p.parts]


def load_bib(root: Path) -> tuple[set[str], dict[str, str]]:
    """Return (keys, key->raw_entry_text)."""
    keys: set[str] = set()
    bodies: dict[str, str] = {}
    for bib in root.rglob("*.bib"):
        text = bib.read_text(encoding="utf-8", errors="replace")
        for m in BIBENTRY_RE.finditer(text):
            key = m.group(2).strip()
            keys.add(key)
            # rough body: from match to next @ or EOF
            start = m.start()
            nxt = text.find("\n@", start + 1)
            bodies[key] = text[start: nxt if nxt != -1 else len(text)]
    return keys, bodies


def split_keys(blob: str) -> list[str]:
    return [k.strip() for k in blob.split(",") if k.strip()]


def load_cross_ref(path: Path) -> list[dict]:
    """Load cross-reference checks from a JSON file.

    Supports two formats:

    1. Explicit checks (preferred):
       {"checks": [{"label": "...", "regex": "...", "expected": "0.913",
                     "file_pattern": ".*\\.tex$", "tolerance": 0.005}]}

    2. Shorthand key→value map (auto-generates checks):
       {"values": {"overall_f1": 0.913, "overall_accuracy": 0.918},
        "tolerance": 0.005}

    Returns a list of check dicts with keys:
      label, regex, expected (str), file_pattern, tolerance
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    checks = []
    default_tolerance = float(data.get("tolerance", 0.005))
    default_file_pattern = data.get("file_pattern", r".*\.tex$")

    if "checks" in data:
        for c in data["checks"]:
            checks.append({
                "label": c["label"],
                "regex": c["regex"],
                "expected": str(c["expected"]),
                "file_pattern": c.get("file_pattern", default_file_pattern),
                "tolerance": float(c.get("tolerance", default_tolerance)),
            })
    elif "values" in data:
        for key, expected in data["values"].items():
            # Auto-generate a flexible regex: key name appearing near a number
            human_key = key.replace("_", " ")
            pattern = rf"{re.escape(human_key)}[:\s=]*\s*([0-9]+\.[0-9]+)"
            checks.append({
                "label": key,
                "regex": pattern,
                "expected": str(expected),
                "file_pattern": default_file_pattern,
                "tolerance": default_tolerance,
            })
    return checks


def run_cross_ref(root: Path, checks: list[dict]) -> list[dict]:
    """Run cross-reference checks. Returns list of hard-failure dicts."""
    failures = []
    file_re = re.compile  # cached for speed

    for check in checks:
        label = check["label"]
        expected_str = check["expected"]
        pattern = re.compile(check["regex"], re.IGNORECASE)
        file_pat = re.compile(check["file_pattern"])
        tolerance = check["tolerance"]
        found = False
        found_value = None
        found_file = None

        # Try to parse expected as float for numeric comparison
        try:
            expected_num = float(expected_str)
            numeric = True
        except ValueError:
            numeric = False

        for tex in collect_tex(root):
            if not file_pat.search(str(tex)):
                continue
            raw = tex.read_text(encoding="utf-8", errors="replace")
            text = strip_tex_comments(raw)
            for m in pattern.finditer(text):
                captured = m.group(1) if m.lastindex else m.group(0)
                found = True
                found_value = captured
                found_file = str(tex.relative_to(root))
                rel = found_file

                if numeric:
                    try:
                        actual = float(captured)
                    except ValueError:
                        continue
                    if not math.isclose(actual, expected_num, rel_tol=0, abs_tol=tolerance):
                        failures.append({
                            "file": rel,
                            "kind": "cross_ref_mismatch",
                            "msg": (
                                f"{label}: expected {expected_str}, "
                                f"found {captured} (diff={abs(actual - expected_num):.4f})"
                            ),
                        })
                break  # first match per file per check
            if found:
                break

        if not found:
            failures.append({
                "file": "cross-ref",
                "kind": "cross_ref_not_found",
                "msg": f"{label}: expected {expected_str} — no match for pattern '{check['regex']}' in any file",
            })

    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify academic LaTeX paper tree")
    ap.add_argument("paper_root", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--allow-cjk", action="store_true", help="Do not hard-fail on CJK")
    ap.add_argument("--cross-ref", type=Path, metavar="JSON",
                    help="Cross-reference checks: verify .tex numbers match a ground-truth JSON")
    args = ap.parse_args()
    root = args.paper_root.resolve()
    if not root.exists():
        print(f"ERROR: {root} does not exist", file=sys.stderr)
        return 2

    hard: list[dict] = []
    soft: list[dict] = []
    bib_keys, bib_bodies = load_bib(root)
    labels: set[str] = set()
    cite_keys: set[str] = set()
    ref_keys: set[str] = set()
    placeholders_seen: set[str] = set()

    for tex in collect_tex(root):
        raw = tex.read_text(encoding="utf-8", errors="replace")
        text = strip_tex_comments(raw)
        rel = str(tex.relative_to(root))
        for m in LABEL_RE.finditer(text):
            labels.add(m.group(1).strip())
        for m in CITE_RE.finditer(text):
            for k in split_keys(m.group(1)):
                cite_keys.add(k)
        for m in REF_RE.finditer(text):
            for k in split_keys(m.group(1)):
                ref_keys.add(k)
        if not args.allow_cjk and CJK_RE.search(text):
            hard.append({"file": rel, "kind": "cjk_leakage", "msg": "CJK characters in TeX body"})
        for m in MARKER_RE.finditer(text):
            msg = m.group(0)
            if msg.startswith("PLACEHOLDER_"):
                placeholders_seen.add(msg)
                continue  # counted once under placeholder_cite
            hard.append({"file": rel, "kind": "unresolved_marker", "msg": msg})
        for m in INCLUDE_RE.finditer(text):
            inc = m.group(1).strip()
            # skip graphicx macros / extensionless will try common suffixes
            candidates = [root / inc]
            if not Path(inc).suffix:
                for ext in (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg"):
                    candidates.append(root / f"{inc}{ext}")
            if not any(c.exists() for c in candidates):
                soft.append({"file": rel, "kind": "missing_include", "msg": inc})
        low = text.lower()
        for w_ in AI_WORDS:
            if w_ in low:
                soft.append({"file": rel, "kind": "ai_vocab", "msg": w_})

    for bib in root.rglob("*.bib"):
        raw = bib.read_text(encoding="utf-8", errors="replace")
        text = strip_tex_comments(raw)
        rel = str(bib.relative_to(root))
        if not args.allow_cjk and CJK_RE.search(text):
            hard.append({"file": rel, "kind": "cjk_leakage", "msg": "CJK characters in bib"})
        for m in MARKER_RE.finditer(text):
            msg = m.group(0)
            if msg.startswith("PLACEHOLDER_"):
                placeholders_seen.add(msg)
                continue
            hard.append({"file": rel, "kind": "unresolved_marker", "msg": msg})

    if cite_keys and not bib_keys:
        hard.append({"file": "bib", "kind": "no_bib_file", "msg": "citations present but no usable .bib entries found"})

    for k in sorted(cite_keys):
        if k.startswith("PLACEHOLDER_") or k in placeholders_seen:
            hard.append({"file": "cite", "kind": "placeholder_cite", "msg": k})
        elif bib_keys and k not in bib_keys:
            hard.append({"file": "cite", "kind": "missing_bib", "msg": k})

    for k in sorted(placeholders_seen):
        if k not in cite_keys:
            hard.append({"file": "cite", "kind": "placeholder_cite", "msg": k})

    for k in sorted(ref_keys):
        if k and k not in labels:
            hard.append({"file": "ref", "kind": "missing_label", "msg": k})

    for key in sorted(bib_keys):
        if key not in cite_keys:
            soft.append({"file": "bib", "kind": "unused_bib", "msg": key})
        body = bib_bodies.get(key, "")
        if body and not LOCATOR_RE.search(body):
            soft.append({"file": "bib", "kind": "no_locator", "msg": f"{key} missing doi/eprint/url/isbn"})

    # --- cross-ref checks ---
    cross_ref_failures: list[dict] = []
    if args.cross_ref:
        cross_path: Path = args.cross_ref
        if not cross_path.exists():
            hard.append({"file": "cross-ref", "kind": "cross_ref_file_missing",
                          "msg": str(cross_path)})
        else:
            try:
                xchecks = load_cross_ref(cross_path)
                cross_ref_failures = run_cross_ref(root, xchecks)
                hard.extend(cross_ref_failures)
            except Exception as exc:
                hard.append({"file": "cross-ref", "kind": "cross_ref_error",
                              "msg": f"{type(exc).__name__}: {exc}"})

    result = {
        "paper_root": str(root),
        "hard": hard,
        "soft": soft,
        "counts": {"hard": len(hard), "soft": len(soft), "cites": len(cite_keys), "labels": len(labels)},
        "status": "FAIL" if hard else "CLEAN",
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"verify_paper: {result['status']}  hard={len(hard)} soft={len(soft)}")
        for h in hard[:50]:
            print(f"  HARD [{h['kind']}] {h['file']}: {h['msg']}")
        if len(hard) > 50:
            print(f"  ... {len(hard) - 50} more hard")
        for s in soft[:20]:
            print(f"  soft [{s['kind']}] {s['file']}: {s['msg']}")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())