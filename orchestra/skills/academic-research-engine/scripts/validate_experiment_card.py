#!/usr/bin/env python3
"""Validate .research experiment card.md (YAML front-matter + required sections)."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_FM = ["id", "hypothesis_ids", "status"]
STATUSES = {"designed", "running", "completed", "aborted"}
ID_RE = re.compile(r"^EXP-\d{3,}$")
H_RE = re.compile(r"^H-\d{3,}$")


def strip_inline_comment(val: str) -> str:
    """Strip YAML-style inline comments outside quotes."""
    in_single = in_double = False
    out = []
    i = 0
    while i < len(val):
        ch = val[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            out.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
        elif ch == "#" and not in_single and not in_double:
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).strip()


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_raw, body = parts[1], parts[2]
    data: dict[str, str] = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        data[key.strip()] = strip_inline_comment(val.strip())
    return data, body


def parse_list(val: str) -> list[str]:
    val = strip_inline_comment(val.strip())
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
    if not val or val.lower() == "null":
        return []
    return [val.strip("'\"")]


def body_has_criteria(body: str) -> tuple[bool, bool]:
    low = body.lower()
    return ("success criteria" in low, "failure criteria" in low)


def validate(path: Path) -> int:
    if not path.is_file():
        print(f"HARD: missing {path}")
        return 2
    text = path.read_text(encoding="utf-8")
    fm, body = parse_front_matter(text)
    hard = 0
    soft = 0
    for k in REQUIRED_FM:
        if k not in fm or not str(fm[k]).strip():
            print(f"HARD: missing front-matter key {k}")
            hard += 1
    exp_id = fm.get("id", "").strip()
    if exp_id and not ID_RE.match(exp_id):
        print(f"HARD: bad id {exp_id!r} (want EXP-NNN)")
        hard += 1
    status = fm.get("status", "").strip().lower()
    if status and status not in STATUSES:
        print(f"HARD: bad status {status!r}")
        hard += 1
    hyps = parse_list(fm.get("hypothesis_ids", ""))
    if "hypothesis_ids" in fm and not hyps:
        print("HARD: hypothesis_ids empty")
        hard += 1
    for h in hyps:
        if not H_RE.match(h):
            print(f"HARD: bad hypothesis id {h!r}")
            hard += 1
    fl = fm.get("failure_loop", "null").strip().lower()
    if fl not in {"null", "tune", "redesign", "rehypothesis", ""}:
        print(f"HARD: bad failure_loop {fl!r}")
        hard += 1
    has_s, has_f = body_has_criteria(body)
    if not has_s:
        print("HARD: body missing 'Success criteria' section")
        hard += 1
    if not has_f:
        print("HARD: body missing 'Failure criteria' section")
        hard += 1
    if "compute_budget" not in text:
        print("SOFT: no compute_budget mentioned")
        soft += 1
    if hard:
        print(f"FAIL: {hard} hard, {soft} soft — {path}")
        return 2
    print(f"OK: {path.name} status={status} hyps={hyps} ({soft} soft)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("card", type=Path, help="Path to experiments/EXP-*/card.md")
    args = ap.parse_args()
    return validate(args.card)


if __name__ == "__main__":
    raise SystemExit(main())