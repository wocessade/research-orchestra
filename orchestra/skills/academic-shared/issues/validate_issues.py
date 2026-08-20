#!/usr/bin/env python3
"""Validate .paper/issues.csv for the P1 issues contract."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REQUIRED = [
    "issue_id",
    "section",
    "claim_id",
    "contribution_id",
    "evidence_status",
    "artifact_path",
    "notes",
    "done",
]
STATUSES = {"planned", "placeholder", "verified"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", type=Path)
    ap.add_argument("--require-verified-results", action="store_true",
                    help="HARD if any section starting with 4/result/exp is not verified")
    args = ap.parse_args()
    if not args.csv_path.is_file():
        print(f"HARD: missing {args.csv_path}")
        return 2
    with args.csv_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("HARD: empty issues.csv")
        return 2
    missing = [c for c in REQUIRED if c not in (rows[0].keys() if rows else [])]
    # header check via reader fieldnames
    with args.csv_path.open(encoding="utf-8", newline="") as f:
        fieldnames = csv.DictReader(f).fieldnames or []
    missing = [c for c in REQUIRED if c not in fieldnames]
    if missing:
        print(f"HARD: missing columns {missing}")
        return 2
    hard = 0
    soft = 0
    for i, r in enumerate(rows, 1):
        st = (r.get("evidence_status") or "").strip().lower()
        if st not in STATUSES:
            print(f"HARD: row {i} bad evidence_status={st!r}")
            hard += 1
        if not (r.get("issue_id") or "").strip():
            print(f"HARD: row {i} empty issue_id")
            hard += 1
        if st == "verified" and not (r.get("artifact_path") or "").strip():
            print(f"SOFT: row {i} verified but empty artifact_path")
            soft += 1
        sec = (r.get("section") or "").lower()
        if args.require_verified_results and any(k in sec for k in ("4.", "result", "exp", "ablation")):
            if st != "verified":
                print(f"HARD: results row {i} section={sec} status={st} (need verified)")
                hard += 1
    if hard:
        print(f"FAIL: {hard} hard issue(s), {soft} soft")
        return 2
    print(f"OK: {len(rows)} issues ({soft} soft warnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
