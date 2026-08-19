#!/usr/bin/env python3
"""Shared scoring script for EXP-001 (used by BOTH arms — fairness control).

Input formats (both files):
    gold.json   -> {"fields": {"<field_name>": "<standard value>"}}
    result.json -> {"fields": {"<field_name>": "<extracted value>"}}

Scoring rule:
    fields_total   = number of fields in gold
    fields_correct = number of gold fields whose result value equals the
                     gold value; before comparison both sides are
                     normalized by stripping leading/trailing whitespace
                     (str(value).strip()); no other normalization is
                     applied, so scoring is exact match at field level.
    accuracy       = correct / total, rounded to 4 decimal places

Output (--out): metrics.json compliant with
    academic-shared/research/metrics.schema.json
    (required keys: run_id, exp_id, status, metrics; additionalProperties
     allows the notes key).

stdlib only — no third-party packages.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def norm(value: object) -> str:
    """Normalize a field value for comparison: strip surrounding whitespace."""
    return str(value).strip()


def load_fields(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data.get("fields"), dict):
        print(f"ERROR: {path} must contain a \"fields\" object", file=sys.stderr)
        raise SystemExit(2)
    return data["fields"]


def score(gold: dict, result: dict) -> dict:
    total = len(gold)
    correct = 0
    for name, gold_value in gold.items():
        if name in result and norm(result[name]) == norm(gold_value):
            correct += 1
    return {
        "fields_total": total,
        "fields_correct": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gold", required=True, type=Path,
                    help="path to gold.json ({'fields': {...}})")
    ap.add_argument("--result", required=True, type=Path,
                    help="path to result.json ({'fields': {...}})")
    ap.add_argument("--exp-id", required=True, dest="exp_id",
                    help="experiment id, e.g. EXP-001")
    ap.add_argument("--run-id", dest="run_id",
                    default=datetime.now().strftime("run-%Y%m%d-%H%M%S"),
                    help="default: run-YYYYMMDD-HHMMSS from datetime.now()")
    ap.add_argument("--out", required=True, type=Path,
                    help="path to write metrics.json (parent dirs created)")
    args = ap.parse_args()

    gold = load_fields(args.gold)
    result = load_fields(args.result)
    m = score(gold, result)

    out_path: Path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": args.run_id,
        "exp_id": args.exp_id,
        "status": "completed",
        "metrics": m,
        "notes": "scored by score.py against gold.json",
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"OK: {args.run_id} accuracy={m['accuracy']} "
          f"({m['fields_correct']}/{m['fields_total']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
