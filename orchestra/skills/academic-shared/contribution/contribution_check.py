#!/usr/bin/env python3
"""Check confirmed_contribution.md for contribution gate."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path, help="Path to confirmed_contribution.md")
    args = ap.parse_args()
    if not args.path.is_file():
        print(f"HARD: missing file {args.path}")
        return 2
    text = args.path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"user_confirmed\s*:\s*(true|false)", text, re.I)
    if not m:
        print("HARD: user_confirmed field missing")
        return 2
    if m.group(1).lower() != "true":
        print("HARD: user_confirmed is not true")
        return 2
    rows = re.findall(r"^\|\s*C\d+\s*\|", text, re.M)
    if len(rows) < 1:
        print("HARD: need >=1 contribution row (C1...)")
        return 2
    if re.search(r"explore\s+\w+|研究一下|随便写", text, re.I):
        print("SOFT: vague language detected — tighten contributions")
    print(f"OK: confirmed with {len(rows)} contribution row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
